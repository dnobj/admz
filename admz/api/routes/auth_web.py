"""Browser login/logout for the windows-local auth backend (ADR-0033).

GET  /login   — the sign-in form (exempt from auth — it's where you
                become authenticated).
POST /login   — validates the submitted Windows credentials against the
                box itself (LogonUserW: local SAM accounts; domain
                accounts when domain-joined), mints a server-side
                session, and sets the ``admz_session`` cookie.
POST /logout  — revokes the session and clears the cookie.

The submitted password exists only for the duration of the LogonUserW
call — never stored, never logged, never echoed (the same invariant as
device passwords). Failures return a deliberately generic message and
are rate-limited per client IP (the ``login`` policy in
:mod:`admz.rate_limit`) and audited.
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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
                 error: str = "") -> None:
    try:
        from admz.audit import audit_log
        audit_log.record(
            requester=username or "(empty)",
            auth_source="windows-local",
            action="auth.login",
            resource="session",
            details={"client": client_key_from_request(request)},
            success=success,
            error_message=error,
        )
    except Exception:  # pragma: no cover — audit must never block login
        logger.exception("login audit row failed")


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
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": "Sign in",
            "next": _safe_next(request.query_params.get("next", "")),
            "error": None,
        },
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next_path: str = Form("/devices", alias="next"),
):
    from admz.session_store import SESSION_COOKIE, get_session_store
    from admz.win_auth import WinAuthUnavailable, validate_windows_credentials

    target = _safe_next(next_path)

    def _fail(message: str, status_code: int = 401):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "title": "Sign in",
                "next": target,
                "error": message,
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

    # Build the principal exactly the shape the rest of ADMZ expects
    # (auth.Principal fields; forwarded to MCP via ADMZ_PRINCIPAL_*).
    from admz.auth import Principal

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
    _audit_login(request, full_name, success=True)

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
