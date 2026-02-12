"""
Web routes for out-of-band credential capture.

GET  /capture/{token}   → render the credential entry form
POST /capture/{token}   → save credentials and show confirmation
GET  /api/capture        → create a new capture session (JSON)
GET  /api/capture/{token}/status → poll session status (JSON)
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from admz.api.capture import capture_store, CaptureStatus
from admz.device_registry import DeviceRegistry
from admz.exceptions import DeviceNotFoundError, BackendError


router = APIRouter()

template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))


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
        return templates.TemplateResponse(
            "capture_done.html",
            {
                "request": request,
                "title": "Credentials Saved",
                "device_id": session.device_id,
                "account_id": session.account_id,
            },
        )

    if session.effective_status == CaptureStatus.EXPIRED:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    # Get device info for display
    try:
        device = registry.get_device_info(session.device_id)
    except DeviceNotFoundError:
        device = {"device_id": session.device_id}

    return templates.TemplateResponse(
        "capture_form.html",
        {
            "request": request,
            "title": "Enter Credentials",
            "token": token,
            "session": session,
            "device": device,
        },
    )


@router.post("/capture/{token}", response_class=HTMLResponse, tags=["capture"])
async def capture_submit(
    request: Request,
    token: str,
    username: str = Form(...),
    password: str = Form(...),
    registry: DeviceRegistry = Depends(get_registry),
):
    """Process the submitted credentials."""
    session = capture_store.get_session(token)

    if session is None or session.effective_status != CaptureStatus.PENDING:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    # Store credentials directly in the registry
    account_data = {
        "username": username,
        "password": password,
        "account_type": session.account_type,
        "purpose": session.purpose,
    }

    try:
        if registry.account_exists(session.device_id, session.account_id):
            # Remove and re-add to update
            registry.remove_account(session.device_id, session.account_id)
        registry.add_account(session.device_id, session.account_id, account_data)
    except DeviceNotFoundError:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Device Not Found",
                "message": f"Device '{session.device_id}' no longer exists.",
                "title": "Error",
            },
            status_code=404,
        )
    except BackendError as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Storage Error",
                "message": str(e),
                "title": "Error",
            },
            status_code=500,
        )

    # Mark session as completed (token is now single-use)
    capture_store.complete_session(token)

    return templates.TemplateResponse(
        "capture_done.html",
        {
            "request": request,
            "title": "Credentials Saved",
            "device_id": session.device_id,
            "account_id": session.account_id,
        },
    )
