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
from admz.rate_limit import rate_limiter, client_key_from_request


# Per-token in-memory tracker of failed password attempts.
# Maps token -> (failed_count, locked_until_timestamp).
# After _MAX_PW_ATTEMPTS failures the session is locked for
# _PW_LOCKOUT_SECONDS. Cleared on successful submit (the session is
# then completed and never re-attempted).
import threading
import time as _time
_PW_ATTEMPTS: dict = {}
_PW_ATTEMPTS_LOCK = threading.Lock()
_MAX_PW_ATTEMPTS = 5
_PW_LOCKOUT_SECONDS = 300.0


def _record_password_failure(token: str) -> bool:
    """Increment fail-count for token. Returns True if now locked out."""
    with _PW_ATTEMPTS_LOCK:
        count, locked_until = _PW_ATTEMPTS.get(token, (0, 0.0))
        count += 1
        if count >= _MAX_PW_ATTEMPTS:
            locked_until = _time.time() + _PW_LOCKOUT_SECONDS
        _PW_ATTEMPTS[token] = (count, locked_until)
        return locked_until > _time.time()


def _is_locked(token: str) -> bool:
    with _PW_ATTEMPTS_LOCK:
        _, locked_until = _PW_ATTEMPTS.get(token, (0, 0.0))
        return locked_until > _time.time()


def _clear_password_failures(token: str) -> None:
    with _PW_ATTEMPTS_LOCK:
        _PW_ATTEMPTS.pop(token, None)


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
    # Phase 4 stretch: per-IP rate limit on confirm POST. Catches
    # password-attempt hammering before the per-token lockout kicks in.
    if not rate_limiter.check("confirm", client_key_from_request(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many confirm attempts from this address. Try again in a few minutes.",
        )

    session = confirm_store.get_session(token)

    if session is None or session.effective_status != ConfirmStatus.PENDING:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    # Phase 4 stretch: per-token password-attempt lockout. After
    # _MAX_PW_ATTEMPTS failures within _PW_LOCKOUT_SECONDS we refuse
    # this token entirely until the lockout clears. Defeats slow brute
    # force of the confirm password.
    if _is_locked(token):
        is_plan = session.is_plan
        plan_summary = session.plan_summary if is_plan else None
        return templates.TemplateResponse(
            "confirm_form.html",
            {
                "request": request,
                "title": "Confirm Plan" if is_plan else "Confirm Operation",
                "token": token,
                "session": session,
                "needs_password": True,
                "error": "Too many failed attempts. This confirmation link is temporarily locked.",
                "is_plan": is_plan,
                "plan_summary": plan_summary,
            },
            status_code=429,
        )

    # Check password if required
    if session.confirmation_level == "url_and_password":
        password_hash = fleet_settings.get("confirm_password_hash")
        if password_hash:
            if not confirm_password or not verify_confirm_password(
                confirm_password, password_hash
            ):
                # Record the failure and (potentially) trigger lockout
                _record_password_failure(token)
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

    # Success: clear any partial failure history for this token
    _clear_password_failures(token)

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
