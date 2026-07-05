"""Web routes for capturing a rule's RECIPIENT credentials out of band.

GET  /capture/rule/{token}  → render the recipient-credential form
POST /capture/rule/{token}  → hold the secret in web-process memory (keyed by the
                              rule's confirm token) and show the approval button.

``create_action_rule`` creates the confirm session (carrying the pending rule
spec — NOT the secret) before sending the user here; this route only adds the
secret via :mod:`admz.rules.capture` and points the user at ``/confirm/{token}``.
The secret never enters chat, the confirm-session payload, the audit log, or any
on-disk store. See ADR-0043.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

from admz.api.confirm_store import ConfirmStatus, confirm_store
from admz.rate_limit import client_key_from_request, rate_limiter
from admz.rules.capture import stash_rule_secrets

router = APIRouter()

template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))
from admz.api.templating import configure as _configure_templates  # noqa: E402
_configure_templates(templates)


def _rule_session(token: str):
    """The PENDING ``create_action_rule`` confirm session awaiting a recipient
    secret for this token, or None (expired / wrong kind / already resolved)."""
    session = confirm_store.get_session(token)
    if session is None or session.effective_status != ConfirmStatus.PENDING:
        return None
    action = session.action
    if not session.is_action or action.get("action") != "create_action_rule":
        return None
    if not action.get("requires_secret_capture"):
        return None
    return session


@router.get("/capture/rule/{token}", response_class=HTMLResponse, tags=["capture"])
async def rule_capture_form(request: Request, token: str):
    """Render the recipient-credential entry form for a valid token."""
    session = _rule_session(token)
    if session is None:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )
    action = session.action
    return templates.TemplateResponse(
        "rule_capture_form.html",
        {
            "request": request,
            "title": "Enter recipient credentials",
            "token": token,
            "device_id": action.get("device_id"),
            "rule_name": action.get("rule_name"),
            "summary": session.danger_description,
            "secret_fields": action.get("secret_fields") or [],
        },
    )


@router.post("/capture/rule/{token}", response_class=HTMLResponse, tags=["capture"])
async def rule_capture_submit(request: Request, token: str):
    """Hold the submitted recipient secret in memory and show the approval link."""
    if not rate_limiter.check("capture", client_key_from_request(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many attempts from this address. Try again in a few minutes.",
        )
    session = _rule_session(token)
    if session is None:
        return templates.TemplateResponse(
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )
    action = session.action
    fields = action.get("secret_fields") or []
    form = await request.form()
    values: Dict[str, str] = {}
    for f in fields:
        name = f.get("name") if isinstance(f, dict) else None
        if not name:
            continue
        val: Optional[str] = form.get(name)
        if val is not None:
            values[name] = str(val)
    stash_rule_secrets(token, values)
    return templates.TemplateResponse(
        "rule_capture_done.html",
        {
            "request": request,
            "title": "Credentials saved",
            "token": token,
            "device_id": action.get("device_id"),
            "rule_name": action.get("rule_name"),
        },
    )
