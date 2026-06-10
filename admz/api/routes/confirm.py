"""
Web routes for operation confirmation gate.

GET  /confirm/{token}                → render the confirmation form
POST /confirm/{token}                → validate and complete the session
GET  /api/confirm/{token}/status     → poll session status (JSON, for MCP)
GET  /api/chat/confirm/{token}       → session details JSON (for chat client)
POST /api/chat/confirm/{token}       → approve/deny in-chat, JSON response
"""

from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from admz.api.context import AppContext, get_context
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
from admz.api.templating import configure as _configure_templates  # noqa: E402
_configure_templates(templates)


# ── Shared approval core (HTML form + JSON chat twin) ────────────────────
#
# H-5/D-6 (review 2026-06-10): the two POST handlers duplicated the whole
# gate sequence (rate limit → session → lockout → password → complete →
# execute) and neither wrote audit rows — the riskiest executions in the
# system (url_* approvals) were invisible to the audit log.  Both handlers
# now call this helper and only shape the response.


class _Approval:
    """Outcome of an approval attempt; handlers map status → response."""

    __slots__ = ("status", "session", "outcome")

    def __init__(self, status, session=None, outcome=None):
        self.status = status        # completed | rate_limited | expired |
        self.session = session      #   locked | wrong_password
        self.outcome = outcome      # execution result when completed


def _session_resource(session) -> str:
    """Audit resource string for a confirm session (catalog.py convention)."""
    if session.is_plan:
        return f"plan:{session.plan_id}"
    return f"device:{session.device_id}/op:{session.operation_id}"


async def _approve_session(
    request: Request,
    token: str,
    confirm_password: Optional[str],
    ctx: "AppContext",
    confirmed_by: str,
) -> _Approval:
    """Run the full approval gate and (on success) execute the held work.

    Writes audit rows for the two security-relevant outcomes: a failed
    password attempt and the approval itself (with the execution result).
    Never logs the submitted password.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)

    if not rate_limiter.check("confirm", client_key_from_request(request)):
        return _Approval("rate_limited")

    session = confirm_store.get_session(token)
    if session is None or session.effective_status != ConfirmStatus.PENDING:
        return _Approval("expired")

    if _is_locked(token):
        return _Approval("locked", session=session)

    if session.confirmation_level == "url_and_password":
        password_hash = fleet_settings.get("confirm_password_hash")
        if password_hash:
            if not confirm_password or not verify_confirm_password(
                confirm_password, password_hash
            ):
                now_locked = _record_password_failure(token)
                record_event(
                    principal, "confirm.password_failed",
                    resource=_session_resource(session),
                    success=False,
                    error_message="incorrect confirmation password",
                    details={
                        "confirmed_by": confirmed_by,
                        "locked_out": now_locked,
                    },
                )
                return _Approval("wrong_password", session=session)

    _clear_password_failures(token)

    if not confirm_store.complete_session(token, confirmed_by=confirmed_by):
        return _Approval("expired")

    from admz import operations

    outcome = await operations.execute_approved_session(
        session,
        catalog=ctx.catalog,
        registry=ctx.registry,
        executors=ctx.executors,
        plan_engine=ctx.plan_engine,
    )

    record_event(
        principal, "confirm.approve",
        resource=_session_resource(session),
        success=bool(outcome.get("success")),
        error_message="" if outcome.get("success") else str(outcome.get("error") or ""),
        details={
            "confirmed_by": confirmed_by,
            "risk_level": session.risk_level,
            "confirmation_level": session.confirmation_level,
            "is_plan": session.is_plan,
        },
    )

    return _Approval("completed", session=session, outcome=outcome)


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
    ctx: AppContext = Depends(get_context),
):
    """Process the confirmation form submission."""
    result = await _approve_session(request, token, confirm_password, ctx, "web")

    if result.status == "rate_limited":
        raise HTTPException(
            status_code=429,
            detail="Too many confirm attempts from this address. Try again in a few minutes.",
        )

    if result.status == "expired":
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    session = result.session
    is_plan = session.is_plan
    plan_summary = session.plan_summary if is_plan else None

    if result.status in ("locked", "wrong_password"):
        error = (
            "Too many failed attempts. This confirmation link is temporarily locked."
            if result.status == "locked"
            else "Incorrect confirmation password."
        )
        return templates.TemplateResponse(
            "confirm_form.html",
            {
                "request": request,
                "title": "Confirm Plan" if is_plan else "Confirm Operation",
                "token": token,
                "session": session,
                "needs_password": True,
                "error": error,
                "is_plan": is_plan,
                "plan_summary": plan_summary,
            },
            status_code=429 if result.status == "locked" else 200,
        )

    return templates.TemplateResponse(
        "confirm_done.html",
        {
            "request": request,
            "title": "Plan Confirmed" if is_plan else "Operation Confirmed",
            "session": session,
            "is_plan": is_plan,
            "plan_summary": plan_summary,
            "outcome": result.outcome,
            "executed": True,
        },
    )


# ── JSON twin for in-chat approval (Phase 5C) ───────────────────────────────
#
# The chat client (admz/api/static/chat.js) detects /confirm/{token}
# URLs in the assistant's streamed text, replaces them with an inline
# approval card, and uses these endpoints to fetch session details +
# submit approval — all without leaving the chat tab.
#
# These mirror the HTML form-handler above but return JSON. Same
# ConfirmStore, same rate limit, same per-token lockout, same fleet
# password — the only difference is the response shape.


@router.get("/api/chat/confirm/{token}", tags=["confirm"])
async def chat_confirm_details(token: str):
    """Return session details for the in-chat approval card.

    Used by the chat client to populate the approval card after
    detecting a confirmation URL in the assistant's text. The
    response intentionally mirrors the fields the HTML form would
    render: device, operation, risk, danger description, whether a
    password is required, and (if it's a plan) the plan summary.
    """
    session = confirm_store.get_session(token)
    if session is None:
        return JSONResponse(
            status_code=410,
            content={"status": "expired_or_not_found"},
        )

    if session.effective_status == ConfirmStatus.EXPIRED:
        return JSONResponse(
            status_code=410, content={"status": "expired"}
        )

    needs_password = session.confirmation_level == "url_and_password"
    if needs_password and not fleet_settings.get("confirm_password_hash"):
        # Same fallback as the HTML route: no password configured →
        # downgrade to url_only so the operator isn't permanently
        # locked out.
        needs_password = False

    return {
        "status": session.effective_status.value,
        "device_id": session.device_id,
        "operation_id": session.operation_id,
        "risk_level": session.risk_level,
        "confirmation_level": session.confirmation_level,
        "danger_description": session.danger_description,
        "needs_password": needs_password,
        "is_plan": session.is_plan,
        "plan_summary": session.plan_summary if session.is_plan else None,
    }


@router.post("/api/chat/confirm/{token}", tags=["confirm"])
async def chat_confirm_submit(
    request: Request,
    token: str,
    confirm_password: Optional[str] = Form(None),
    ctx: AppContext = Depends(get_context),
):
    """Approve a confirmation session from within chat.

    Returns JSON ``{"status": "completed"}`` on success, or
    ``{"status": "<reason>", "error": "..."}`` on failure. HTTP
    status codes mirror the HTML route: 410 expired, 429
    rate-limited or locked out, 403 wrong password.

    Always returns a body (even on error) so the chat client can
    render a meaningful card update without parsing HTML.
    """
    result = await _approve_session(request, token, confirm_password, ctx, "chat")

    if result.status == "rate_limited":
        return JSONResponse(
            status_code=429,
            content={
                "status": "rate_limited",
                "error": (
                    "Too many confirm attempts from this address. "
                    "Try again in a few minutes."
                ),
            },
        )

    if result.status == "expired":
        return JSONResponse(
            status_code=410,
            content={"status": "expired_or_not_found"},
        )

    if result.status == "locked":
        return JSONResponse(
            status_code=429,
            content={
                "status": "locked",
                "error": (
                    "Too many failed password attempts. "
                    "This confirmation link is temporarily locked."
                ),
            },
        )

    if result.status == "wrong_password":
        return JSONResponse(
            status_code=403,
            content={
                "status": "wrong_password",
                "error": "Incorrect confirmation password.",
            },
        )

    session = result.session
    return {
        "status": "completed",
        "is_plan": session.is_plan,
        "device_id": session.device_id,
        "operation_id": session.operation_id,
        "outcome": result.outcome,
    }
