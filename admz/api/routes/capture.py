"""
Web routes for out-of-band credential capture.

GET  /capture/{token}   → render the credential entry form
POST /capture/{token}   → save credentials and show confirmation
GET  /api/capture        → create a new capture session (JSON)
GET  /api/capture/{token}/status → poll session status (JSON)
"""

import logging

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from admz.api.capture import capture_store, CaptureStatus
from admz.device_registry import DeviceRegistry
from admz.exceptions import DeviceNotFoundError, BackendError
from admz.fleet_settings import fleet_settings
from admz.rate_limit import rate_limiter, client_key_from_request
from admz.setting_policy import is_llm_writable


router = APIRouter()

template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))
from admz.api.templating import configure as _configure_templates  # noqa: E402
_configure_templates(templates)


def get_registry() -> DeviceRegistry:
    from admz.api.main import registry
    if registry is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")
    return registry


# ── JSON API endpoints (used by MCP tool) ─────────────────────────────────

@router.post("/api/capture", tags=["capture"])
async def create_capture_session(
    device_id: str,
    account_id: str = "default",
    account_type: str = "service",
    purpose: str = "",
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Create a credential capture session and return its URL.

    The URL can be given to a user to enter credentials out of band.
    """
    # Verify the device exists
    if not registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    session = capture_store.create_session(
        device_id=device_id,
        account_id=account_id,
        account_type=account_type,
        purpose=purpose,
    )

    return {
        "token": session.token,
        "url": f"/capture/{session.token}",
        "device_id": device_id,
        "account_id": account_id,
        "expires_in_seconds": int(session.ttl),
    }


@router.get("/api/capture/{token}/status", tags=["capture"])
async def capture_status(token: str):
    """
    Check the status of a capture session.

    Returns status only — never returns credentials.
    """
    session = capture_store.get_session(token)
    if session is None:
        return {"status": "expired_or_not_found"}

    return {
        "status": session.effective_status.value,
        "device_id": session.device_id,
        "account_id": session.account_id,
    }


# ── Web form endpoints (opened in user's browser) ─────────────────────────

@router.get("/capture/{token}", response_class=HTMLResponse, tags=["capture"])
async def capture_form(
    request: Request,
    token: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """Render the credential capture form for a valid token."""
    session = capture_store.get_session(token)

    if session is None:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    if session.effective_status == CaptureStatus.COMPLETED:
        ctx = {
            "request": request,
            "title": "Credentials Saved",
            "device_id": session.device_id,
            "account_id": session.account_id,
        }
        if session.is_batch:
            ctx["device_ids"] = session.all_device_ids
            ctx["is_batch"] = True
        return templates.TemplateResponse("capture_done.html", ctx)

    if session.effective_status == CaptureStatus.EXPIRED:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    # Build device info for display
    is_batch = session.is_batch
    devices: List[Dict] = []
    for did in session.all_device_ids:
        try:
            info = registry.get_device_info(did)
            info["device_id"] = did
        except DeviceNotFoundError:
            info = {"device_id": did}
        devices.append(info)

    return templates.TemplateResponse(
        "capture_form.html",
        {
            "request": request,
            "title": "Enter Credentials",
            "token": token,
            "session": session,
            "device": devices[0] if devices else {},
            "devices": devices,
            "is_batch": is_batch,
        },
    )


def _note_capture_to_chat(token: str, saved: List[str]) -> None:
    """Tell the originating chat conversation (if any) that credentials
    were stored — the model otherwise keeps asking the user to "let me
    know once you've set the password". Device ids only; NEVER the
    password or username. Best-effort: a note failure must not affect
    the capture."""
    try:
        from admz.chatbot.sessions import chat_sessions

        link = chat_sessions.pop_action_link(token)
        if link is not None:
            chat_sessions.append_event(
                link["principal"], link["conversation_id"],
                "[console] The user submitted credentials for device(s) "
                f"{', '.join(saved)} via the secure capture form; they were "
                "stored server-side. (The password is not available in this "
                "conversation.)",
            )
    except Exception:  # noqa: BLE001 - never break a capture on a note
        logger.debug("chat capture note failed for %s", token, exc_info=True)


@router.post("/capture/{token}", response_class=HTMLResponse, tags=["capture"])
async def capture_submit(
    request: Request,
    token: str,
    username: str = Form(...),
    password: str = Form(...),
    registry: DeviceRegistry = Depends(get_registry),
):
    """Process the submitted credentials."""
    # Phase 4 stretch: per-IP rate limit. The token is 256-bit and
    # single-use, so brute force isn't the threat — overwrite races
    # and accidental double-submits are. 10 attempts then 10/minute.
    if not rate_limiter.check("capture", client_key_from_request(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many capture attempts from this address. Try again in a few minutes.",
        )

    session = capture_store.get_session(token)

    if session is None or session.effective_status != CaptureStatus.PENDING:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    account_data = {
        "username": username,
        "password": password,
        "account_type": session.account_type,
        "purpose": session.purpose,
    }

    # Store credentials for all target devices (batch or single).
    # Use update_account when the account exists — atomic, no window
    # during which the account is observably missing. Fall back to
    # add_account for fresh ones.
    saved: List[str] = []
    errors: List[Dict] = []

    for did in session.all_device_ids:
        try:
            if registry.account_exists(did, session.account_id):
                registry.update_account(did, session.account_id, account_data)
            else:
                registry.add_account(did, session.account_id, account_data)
            saved.append(did)
        except DeviceNotFoundError:
            errors.append({"device_id": did, "error": "Device not found"})
        except BackendError as e:
            errors.append({"device_id": did, "error": str(e)})

    if not saved:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Storage Error",
                "message": "Failed to save credentials for any device.",
                "title": "Error",
            },
            status_code=500,
        )

    # Mark session as completed (token is now single-use)
    capture_store.complete_session(token)

    _note_capture_to_chat(token, saved)

    ctx = {
        "request": request,
        "title": "Credentials Saved",
        "device_id": session.device_id,
        "account_id": session.account_id,
    }

    if session.is_batch:
        ctx["is_batch"] = True
        ctx["device_ids"] = session.all_device_ids
        ctx["saved"] = saved
        ctx["errors"] = errors

    return templates.TemplateResponse("capture_done.html", ctx)


# ── Fleet setting capture (password never touches LLM) ─────────────────

@router.get("/capture/fleet/{token}", response_class=HTMLResponse, tags=["capture"])
async def fleet_capture_form(request: Request, token: str):
    """Render the fleet setting capture form."""
    session = capture_store.get_fleet_session(token)

    if session is None:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    if session.effective_status == CaptureStatus.COMPLETED:
        return templates.TemplateResponse(
            "capture_fleet_done.html",
            {
                "request": request,
                "title": "Setting Saved",
                "setting_key": session.setting_key,
                "label": session.label,
            },
        )

    if session.effective_status == CaptureStatus.EXPIRED:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    return templates.TemplateResponse(
        "capture_fleet_form.html",
        {
            "request": request,
            "title": "Set Fleet Password",
            "token": token,
            "session": session,
        },
    )


@router.post("/capture/fleet/{token}", response_class=HTMLResponse, tags=["capture"])
async def fleet_capture_submit(
    request: Request,
    token: str,
    password: str = Form(...),
    username: str = Form("admin"),
):
    """Process the submitted fleet credentials (username + password)."""
    session = capture_store.get_fleet_session(token)

    if session is None or session.effective_status != CaptureStatus.PENDING:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    # ADR-0053: this route is reached with a one-time token minted by the MCP
    # tool, so the key travelled through a session row rather than through the
    # gate at ``mcp/server.py::_set_fleet_setting``. Re-check it here: a stale
    # session created before the allow-set narrowed, or a session row edited
    # out from under us, must not become a write path for a protected key.
    # Defence in depth — the mint side is gated too.
    if not is_llm_writable(session.setting_key):
        logger.warning(
            "fleet capture refused: %r is not LLM-writable", session.setting_key
        )
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    fleet_settings.set(session.setting_key, password)
    fleet_settings.set("default_username", username.strip() or "admin")
    capture_store.complete_fleet_session(token)

    return templates.TemplateResponse(
        "capture_fleet_done.html",
        {
            "request": request,
            "title": "Setting Saved",
            "setting_key": session.setting_key,
            "label": session.label,
        },
    )
