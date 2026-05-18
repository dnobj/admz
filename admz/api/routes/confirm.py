"""
Web routes for operation confirmation gate.

GET  /confirm/{token}             → render the confirmation form
POST /confirm/{token}             → validate and complete the session
GET  /api/confirm/{token}/status  → poll session status (JSON, for MCP)
"""

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from admz.api.confirm_store import (
    confirm_store,
    ConfirmStatus,
    verify_confirm_password,
)
from admz.fleet_settings import fleet_settings


router = APIRouter()

template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))


# ── JSON status endpoint (polled by MCP tool) ───────────────────────────

@router.get("/api/confirm/{token}/status", tags=["confirm"])
async def confirm_status(token: str):
    """Check the status of a confirmation session.  Returns status only."""
    session = confirm_store.get_session(token)
    if session is None:
        return {"status": "expired_or_not_found"}

    return {
        "status": session.effective_status.value,
        "device_id": session.device_id,
        "operation_id": session.operation_id,
        "confirmation_level": session.confirmation_level,
    }


# ── Web form endpoints (opened in user's browser) ───────────────────────

@router.get("/confirm/{token}", response_class=HTMLResponse, tags=["confirm"])
async def confirm_form(request: Request, token: str):
    """Render the confirmation form for a valid token."""
    session = confirm_store.get_session(token)

    if session is None:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    if session.effective_status == ConfirmStatus.COMPLETED:
        return templates.TemplateResponse(
            "confirm_done.html",
            {
                "request": request,
                "title": "Plan Confirmed" if session.is_plan else "Operation Confirmed",
                "session": session,
                "is_plan": session.is_plan,
                "plan_summary": session.plan_summary if session.is_plan else None,
            },
        )

    if session.effective_status == ConfirmStatus.EXPIRED:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    # Determine if a password field is needed
    needs_password = session.confirmation_level == "url_and_password"
    password_hash = fleet_settings.get("confirm_password_hash")
    # If url_and_password but no password configured, fall back to url_only
    if needs_password and not password_hash:
        needs_password = False

    is_plan = session.is_plan
    plan_summary = session.plan_summary if is_plan else None

    return templates.TemplateResponse(
        "confirm_form.html",
        {
            "request": request,
            "title": "Confirm Plan" if is_plan else "Confirm Operation",
            "token": token,
            "session": session,
            "needs_password": needs_password,
            "is_plan": is_plan,
            "plan_summary": plan_summary,
        },
    )


@router.post("/confirm/{token}", response_class=HTMLResponse, tags=["confirm"])
async def confirm_submit(
    request: Request,
    token: str,
    confirm_password: Optional[str] = Form(None),
):
    """Process the confirmation form submission."""
    session = confirm_store.get_session(token)

    if session is None or session.effective_status != ConfirmStatus.PENDING:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    # Check password if required
    if session.confirmation_level == "url_and_password":
        password_hash = fleet_settings.get("confirm_password_hash")
        if password_hash:
            if not confirm_password or not verify_confirm_password(
                confirm_password, password_hash
            ):
                is_plan = session.is_plan
                plan_summary = session.plan_summary if is_plan else None
                # Re-render form with error
                return templates.TemplateResponse(
                    "confirm_form.html",
                    {
                        "request": request,
                        "title": "Confirm Plan" if is_plan else "Confirm Operation",
                        "token": token,
                        "session": session,
                        "needs_password": True,
                        "error": "Incorrect confirmation password.",
                        "is_plan": is_plan,
                        "plan_summary": plan_summary,
                    },
                )

    # Mark session as completed
    if not confirm_store.complete_session(token, confirmed_by="web"):
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    is_plan = session.is_plan
    plan_summary = session.plan_summary if is_plan else None

    return templates.TemplateResponse(
        "confirm_done.html",
        {
            "request": request,
            "title": "Plan Confirmed" if is_plan else "Operation Confirmed",
            "session": session,
            "is_plan": is_plan,
            "plan_summary": plan_summary,
        },
    )
