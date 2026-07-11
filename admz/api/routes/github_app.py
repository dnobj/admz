"""GitHub App "Connect GitHub" flow for config-repo backup (ADR-0045).

A streamlined, redirect-and-approve setup: the operator clicks "Connect GitHub"
→ GitHub creates the App from a manifest and hands back its credentials → the
operator installs it on the config repo → ADMZ can then mint short-lived
installation tokens to push. No PAT, no SSH key to paste.

The two GitHub redirect callbacks arrive as top-level cross-site GETs, so they
can't rely on the ADMZ session cookie — they self-authenticate via an HMAC-signed,
short-lived ``state`` param (mirrors the ``/api/acs/rule-fired`` exempt+self-auth
precedent). ``connect``/``test``/``disconnect`` require an authenticated principal.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import logging
import secrets as _pysecrets
import time
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from admz.api.context import AppContext, get_context
from admz.github_app import client as gh_client
from admz.github_app import secrets as gh_secrets

logger = logging.getLogger(__name__)
router = APIRouter()

_STATE_TTL = 900  # seconds a signed OAuth state stays valid


# ---------------------------------------------------------------------------
# Signed OAuth state (CSRF guard; ties the callback to a connect request)
# ---------------------------------------------------------------------------


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_state(phase: str, *, now: Optional[float] = None) -> str:
    body = _b64(json.dumps({
        "phase": phase,
        "nonce": _pysecrets.token_urlsafe(12),
        "exp": int((now or time.time()) + _STATE_TTL),
    }, separators=(",", ":")).encode())
    sig = hmac.new(gh_secrets.signing_key(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(sig)}"


def verify_state(state: str, *, phase: str, now: Optional[float] = None) -> bool:
    try:
        body, sig = state.split(".", 1)
        expected = hmac.new(gh_secrets.signing_key(), body.encode(),
                            hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(sig)):
            return False
        payload = json.loads(_unb64(body))
    except Exception:  # noqa: BLE001
        return False
    if payload.get("phase") != phase:
        return False
    return payload.get("exp", 0) >= int(now or time.time())


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _require_principal(request: Request):
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal
    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    return principal


def _audit(principal, event: str, *, success: bool = True,
           details: Optional[dict] = None, error: str = "") -> None:
    from admz.audit import record_event
    try:
        record_event(principal, event, resource="github-app",
                     success=success, error_message=error, details=details or {})
    except Exception:  # noqa: BLE001 - audit must never break the flow
        pass


def _resolve_and_set_remote(ctx: AppContext) -> Optional[str]:
    """Pick the config repo the App can push to and point the config-repo
    ``origin`` at it (token is injected at push time, never stored in the URL)."""
    try:
        token = gh_client.get_installation_token(
            gh_secrets.get_app_id(), gh_secrets.get_private_key(),
            gh_secrets.get_installation_id(), use_cache=False,
        )
        repos = gh_client.list_installation_repositories(token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not resolve installation repos: %s", exc)
        return None
    want = gh_secrets.get_config_repo()
    chosen = None
    if want:
        chosen = next((r for r in repos if r["full_name"] == want), None)
    if chosen is None and repos:
        chosen = repos[0]  # a single installed repo is the common case
    if not chosen:
        return None
    full = chosen["full_name"]
    gh_secrets.set_config_repo(full)
    ctx.git_repo.set_remote_url(f"https://x-access-token@github.com/{full}.git")
    return full


def _complete_connection(ctx: AppContext) -> Optional[str]:
    """Finish wiring after the operator installed the App on GitHub: discover the
    installation via the App JWT (so we don't depend on the post-install redirect
    firing), store its id, resolve the config repo, and set the origin. Returns
    the repo full_name, or None if the App isn't installed yet."""
    app_id, pem = gh_secrets.get_app_id(), gh_secrets.get_private_key()
    if not (app_id and pem):
        return None
    try:
        installs = gh_client.list_app_installations(app_id, pem)
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not list app installations: %s", exc)
        return None
    if not installs:
        return None
    # Prefer the installation whose account owns the desired config repo.
    want = gh_secrets.get_config_repo()
    want_owner = want.split("/")[0] if want and "/" in want else None
    chosen = None
    if want_owner:
        chosen = next((i for i in installs if i.get("account") == want_owner), None)
    if chosen is None:
        chosen = installs[0]
    gh_secrets.set_installation_id(chosen["id"])
    return _resolve_and_set_remote(ctx)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api/github/connect")
async def github_connect(request: Request, ctx: AppContext = Depends(get_context)):
    """Kick off the GitHub App **manifest** flow — auto-submit the manifest to
    GitHub, which creates the App and redirects to our setup callback."""
    await _require_principal(request)
    base = str(request.base_url).rstrip("/")
    manifest = {
        "name": f"ADMZ config backup ({request.url.hostname})",
        "url": base,
        "redirect_url": f"{base}/api/github/setup/callback",
        # Post-installation redirect — GitHub sends the operator back here after
        # they install the App, so ADMZ learns the installation automatically.
        "setup_url": f"{base}/api/github/install/callback",
        "setup_on_update": False,
        "public": False,
        "default_permissions": {"contents": "write", "metadata": "read"},
        "default_events": [],
    }
    state = sign_state("setup")
    action = f"https://github.com/settings/apps/new?state={quote(state, safe='')}"
    manifest_val = html.escape(json.dumps(manifest), quote=True)
    body = (
        "<!doctype html><meta charset=utf-8>"
        f"<form id=f method=post action=\"{action}\">"
        f"<input type=hidden name=manifest value=\"{manifest_val}\"></form>"
        "<script>document.getElementById('f').submit()</script>"
        "<p>Redirecting to GitHub to create the ADMZ backup app…</p>"
    )
    return HTMLResponse(body)


@router.get("/api/github/setup/callback")
async def github_setup_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    ctx: AppContext = Depends(get_context),
):
    """GitHub redirects here after creating the App. Exchange the one-time code
    for the App credentials, store them, then redirect to install the App."""
    if not verify_state(state, phase="setup"):
        raise HTTPException(status_code=400, detail="invalid or expired state")
    from admz.auth import get_current_principal
    principal = await get_current_principal(request)
    try:
        creds = gh_client.exchange_manifest_code(code)
    except gh_client.GitHubAppError as exc:
        _audit(principal, "github_app.register", success=False, error=str(exc))
        return RedirectResponse("/settings?github_error=register#github-backup",
                                status_code=303)
    gh_secrets.save_app(
        creds["id"], creds.get("slug", ""), creds["pem"],
        client_secret=creds.get("client_secret"),
    )
    _audit(principal, "github_app.register",
           details={"app_id": str(creds["id"]), "slug": creds.get("slug")})
    install_state = sign_state("install")
    slug = creds.get("slug")
    url = (f"https://github.com/apps/{quote(str(slug))}/installations/new"
           f"?state={quote(install_state, safe='')}")
    return RedirectResponse(url, status_code=303)


@router.get("/api/github/install/callback")
async def github_install_callback(
    request: Request,
    ctx: AppContext = Depends(get_context),
    installation_id: Optional[str] = Query(None),
    setup_action: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
):
    """GitHub's post-install redirect (the App's Setup URL). It does NOT carry
    our signed ``state``, so we authenticate by *discovering* the installation
    with the App JWT (only our App's private key can list its installations)
    rather than trusting the query params."""
    if not gh_secrets.get_app_id():
        return RedirectResponse("/settings?github_error=register#github-backup",
                                status_code=303)
    from admz.auth import get_current_principal
    principal = await get_current_principal(request)
    if setup_action == "cancel":
        return RedirectResponse("/settings?github_error=cancelled#github-backup",
                                status_code=303)
    repo = _complete_connection(ctx)
    if not repo:
        _audit(principal, "github_app.install", success=False,
               error="no installation found")
        return RedirectResponse("/settings?github_error=install#github-backup",
                                status_code=303)
    _audit(principal, "github_app.install",
           details={"installation_id": gh_secrets.get_installation_id(), "repo": repo})
    return RedirectResponse("/settings?github_connected=1#github-backup",
                            status_code=303)


@router.post("/api/github/refresh")
async def github_refresh(request: Request, ctx: AppContext = Depends(get_context)):
    """Finish / repair a connection by discovering the installation via the App
    JWT. Used by the "Finish connecting" button when the post-install redirect
    didn't fire, or to re-resolve after changing which repos are installed."""
    principal = await _require_principal(request)
    if not gh_secrets.get_app_id():
        return JSONResponse(
            {"ok": False, "error": "no app registered — click Connect GitHub first"})
    repo = _complete_connection(ctx)
    from admz.audit import record_event
    record_event(principal, "github_app.refresh", resource="github-app",
                 success=bool(repo), details={"repo": repo})
    if not repo:
        return JSONResponse(
            {"ok": False,
             "error": "app not installed yet — install it on GitHub, then retry"})
    return JSONResponse({"ok": True, "connected": gh_secrets.is_connected(),
                         "repo": repo})


@router.post("/api/github/test")
async def github_test(request: Request, ctx: AppContext = Depends(get_context)):
    """Verify the connection: mint a fresh token + list the installation's repos
    (proves App auth + install + repo access). Never returns any secret."""
    principal = await _require_principal(request)
    if not gh_secrets.is_connected():
        return JSONResponse({"ok": False, "error": "not connected"})
    try:
        token = gh_client.get_installation_token(
            gh_secrets.get_app_id(), gh_secrets.get_private_key(),
            gh_secrets.get_installation_id(), use_cache=False,
        )
        repos = [r["full_name"] for r in gh_client.list_installation_repositories(token)]
    except Exception as exc:  # noqa: BLE001
        _audit(request, "github_app.test", success=False, error=str(exc))
        return JSONResponse({"ok": False, "error": str(exc)[:200]})
    want = gh_secrets.get_config_repo()
    ok = bool(want and want in repos)
    from admz.audit import record_event
    record_event(principal, "github_app.test", resource="github-app",
                 success=ok, details={"repo": want, "repo_count": len(repos)})
    return JSONResponse({"ok": ok, "repo": want, "repos": repos})


@router.post("/api/github/disconnect")
async def github_disconnect(request: Request, ctx: AppContext = Depends(get_context)):
    """Forget the App + installation and remove the config-repo remote."""
    principal = await _require_principal(request)
    gh_client.clear_token_cache()
    gh_secrets.clear()
    try:
        ctx.git_repo.set_remote_url(None)
    except Exception:  # noqa: BLE001
        pass
    from admz.audit import record_event
    record_event(principal, "github_app.disconnect", resource="github-app",
                 success=True)
    return JSONResponse({"ok": True})
