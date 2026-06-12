"""Browser login/logout for the windows-local auth backend (ADR-0033/0035).

GET  /login     — the sign-in page: a "continue as the signed-in Windows
                  user" button (SSO, when available) above the credential
                  form (exempt from auth — it's where you become
                  authenticated).
GET  /login/sso — HTTP Negotiate (SPNEGO) single sign-on (ADR-0035): the
                  browser and Windows complete a Kerberos/NTLM handshake
                  (no password typed); success mints the same server-side
                  session the form does. Covered by the "/login" exempt
                  prefix.
POST /login     — validates the submitted Windows credentials against the
                  box itself (LogonUserW: local SAM accounts; domain
                  accounts when domain-joined), mints a server-side
                  session, and sets the ``admz_session`` cookie.
POST /logout    — revokes the session and clears the cookie.

The submitted password exists only for the duration of the LogonUserW
call — never stored, never logged, never echoed (the same invariant as
device passwords). Failures return a deliberately generic message and
are rate-limited per client IP (the ``login``/``login-sso`` policies in
:mod:`admz.rate_limit`) and audited.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from admz.rate_limit import client_key_from_request, rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter()

template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))


def _safe_next(raw: str) -> str:
    """Only allow same-site relative redirect targets (no scheme/host —
    blocks open-redirect via ?next=https://evil)."""
    if not raw or not raw.startswith("/") or raw.startswith("//"):
        return "/devices"
    if urlparse(raw).netloc:
        return "/devices"
    return raw


def _audit_login(request: Request, username: str, *, success: bool,
                 error: str = "", method: str = "form") -> None:
    try:
        from admz.audit import audit_log
        audit_log.record(
            requester=username or "(empty)",
            auth_source="windows-local",
            action="auth.login",
            resource="session",
            details={
                "client": client_key_from_request(request),
                "method": method,
            },
            success=success,
            error_message=error,
        )
    except Exception:  # pragma: no cover — audit must never block login
        logger.exception("login audit row failed")


def _establish_session(request: Request, identity, target: str,
                       *, method: str) -> RedirectResponse:
    """Shared tail of both sign-in methods (form + SSO): build the
    Principal, mint the server-side session, set the cookie, audit."""
    from admz.auth import Principal
    from admz.session_store import SESSION_COOKIE, get_session_store

    full_name = (
        f"{identity.domain}\\{identity.username}"
        if identity.domain else identity.username
    )
    principal = Principal(
        name=full_name,
        display_name=identity.username,
        domain=identity.domain,
        groups=list(identity.groups),
        source="windows-local",
        is_anonymous=False,
    )
    token = get_session_store().create(principal)
    _audit_login(request, full_name, success=True, method=method)

    resp = RedirectResponse(url=target, status_code=303)
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        # No Secure flag: the deployment is plain HTTP on localhost
        # (KL-AUTH-006). A TLS-fronted deployment should set
        # ADMZ_SESSION_COOKIE_SECURE=1.
        secure=_cookie_secure(),
        max_age=None,  # session-scoped cookie; server-side TTL governs
    )
    return resp


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    from admz.session_store import SESSION_COOKIE, get_session_store

    # Already signed in? Straight through.
    token = request.cookies.get(SESSION_COOKIE, "")
    if token and get_session_store().resolve(token) is not None:
        return RedirectResponse(
            url=_safe_next(request.query_params.get("next", "")),
            status_code=303,
        )
    from admz.win_sspi import sso_available

    error = None
    if request.query_params.get("sso") == "failed":
        error = (
            "Single sign-on didn't work in this browser — sign in with "
            "your username and password instead."
        )
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": "Sign in",
            "next": _safe_next(request.query_params.get("next", "")),
            "error": error,
            "sso_available": sso_available(),
        },
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next_path: str = Form("/devices", alias="next"),
):
    from admz.win_auth import WinAuthUnavailable, validate_windows_credentials

    target = _safe_next(next_path)

    def _fail(message: str, status_code: int = 401):
        from admz.win_sspi import sso_available

        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "title": "Sign in",
                "next": target,
                "error": message,
                "sso_available": sso_available(),
            },
            status_code=status_code,
        )

    if not rate_limiter.check("login", client_key_from_request(request)):
        _audit_login(request, username, success=False, error="rate-limited")
        return _fail(
            "Too many sign-in attempts — wait a moment and try again.",
            status_code=429,
        )

    try:
        identity = validate_windows_credentials(username, password)
    except WinAuthUnavailable as exc:
        logger.error("windows-local login unavailable: %s", exc)
        _audit_login(request, username, success=False, error="unavailable")
        return _fail(
            "Windows sign-in isn't available on this server.",
            status_code=503,
        )
    finally:
        # Belt-and-braces: drop the only reference to the plaintext.
        del password

    if identity is None:
        _audit_login(request, username, success=False, error="bad-credentials")
        return _fail("Sign-in failed — check your username and password.")

    return _establish_session(request, identity, target, method="form")


@router.get("/login/sso")
async def login_sso(request: Request):
    """HTTP Negotiate single sign-on (ADR-0035).

    The dance, all on this one endpoint (it is never issued anywhere
    else, so no other page can trigger a browser auth prompt):

    1. Bare GET → 401 + ``WWW-Authenticate: Negotiate``. A supporting
       browser (Edge/Chrome treat localhost as intranet) retries with an
       ``Authorization: Negotiate <token>`` header; anything else shows
       the fallback body linking back to the form.
    2. Token legs go to Windows via ``AcceptSecurityContext``. NTLM needs
       a challenge round-trip → another 401 carrying our token; Kerberos
       usually completes in one.
    3. Completion yields the browser user's Windows identity → the same
       session/cookie/audit tail as the form (``_establish_session``).
    """
    from admz import win_sspi

    target = _safe_next(request.query_params.get("next", ""))
    fail_url = f"/login?sso=failed&next={quote(target, safe='')}"

    if not win_sspi.sso_available():
        return RedirectResponse(url=fail_url, status_code=303)

    def _challenge(blob: bytes = b"") -> Response:
        value = "Negotiate"
        if blob:
            value = f"Negotiate {base64.b64encode(blob).decode('ascii')}"
        return HTMLResponse(
            "<html><body>Single sign-on is not available in this "
            f"browser — <a href=\"{fail_url}\">use the sign-in form</a>."
            "</body></html>",
            status_code=401,
            headers={"WWW-Authenticate": value},
        )

    in_blob = win_sspi.decode_negotiate_header(
        request.headers.get("authorization", "")
    )
    if in_blob is None:
        # Leg 0: invite the browser to negotiate.
        return _challenge()

    if not rate_limiter.check("login-sso", client_key_from_request(request)):
        _audit_login(request, "(sso)", success=False, error="rate-limited",
                     method="negotiate")
        return RedirectResponse(url=fail_url, status_code=303)

    # NTLM's legs ride one TCP connection — the client (host, port) pair
    # identifies a parked partial handshake.
    client = request.client or ("?", 0)
    key = (getattr(client, "host", "?"), getattr(client, "port", 0))

    handshake = win_sspi.pending_handshakes.pop(key)
    if handshake is None:
        try:
            handshake = win_sspi.NegotiateHandshake()
        except win_sspi.WinAuthUnavailable as exc:
            logger.error("Negotiate SSO unavailable: %s", exc)
            return RedirectResponse(url=fail_url, status_code=303)

    status, out_blob, identity = handshake.step(in_blob)

    if status == win_sspi.CONTINUE:
        win_sspi.pending_handshakes.put(key, handshake)
        return _challenge(out_blob)

    if status == win_sspi.COMPLETE and identity is not None:
        return _establish_session(
            request, identity, target, method="negotiate"
        )

    _audit_login(request, "(sso)", success=False, error="handshake-failed",
                 method="negotiate")
    return RedirectResponse(url=fail_url, status_code=303)


def _cookie_secure() -> bool:
    import os
    return (os.getenv("ADMZ_SESSION_COOKIE_SECURE", "") or "").strip().lower() in (
        "1", "true", "yes", "on",
    )


@router.post("/logout")
async def logout(request: Request):
    from admz.session_store import SESSION_COOKIE, get_session_store

    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        revoked = get_session_store().revoke(token)
        principal = getattr(getattr(request, "state", None), "principal", None)
        _audit_login(
            request,
            getattr(principal, "name", "(session)"),
            success=revoked,
            error="" if revoked else "no-live-session",
        )
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp
