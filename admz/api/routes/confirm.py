"""
Web routes for operation confirmation gate.

GET  /confirm/{token}                → render the confirmation form
POST /confirm/{token}                → validate and complete the session
GET  /api/confirm/{token}/status     → poll session status (JSON, for MCP)
GET  /api/chat/confirm/{token}       → session details JSON (for chat client)
POST /api/chat/confirm/{token}       → approve/deny in-chat, JSON response
"""

import logging

from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

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

    __slots__ = ("status", "session", "outcome", "detail")

    def __init__(self, status, session=None, outcome=None, detail=""):
        self.status = status        # completed | rate_limited | expired |
        self.session = session      #   locked | wrong_password | not_authorized
        self.outcome = outcome      # execution result when completed
        self.detail = detail        # operator-facing text for not_authorized


def _session_resource(session) -> str:
    """Audit resource string for a confirm session (catalog.py convention)."""
    if session.is_plan:
        return f"plan:{session.plan_id}"
    return f"device:{session.device_id}/op:{session.operation_id}"


#: Identifier keys copied VERBATIM out of a session's action payload.
#:
#: An ALLOW-LIST, and it must stay one — the same discipline as
#: ``audit.OUTCOME_IDENTITY_KEYS`` (#246: *"Allow-listed identifiers only —
#: never ``**outcome``"*). Every entry is either the executor name or an
#: identifier the ADR-0056 drift-attribution join actually consumes
#: (``attribution.py`` reads ``rule_id``/``ruleId`` and ``rule_name``, nothing
#: else). Do NOT add a key because it looks harmless: the invariant the tests
#: enforce is that **no request VALUE reaches the audit log**, because that log
#: is never pruned (there is no DELETE in ``audit.py``) while the confirm row it
#: mirrors is about to be stripped (#266). A value added here outlives
#: everything else in the system.
_ACTION_IDENTITY_KEYS = ("action", "rule_id", "rule_name")


def _approved_work_fields(session) -> Dict[str, Any]:
    """A **value-free** description of what was approved, for the audit row.

    #270: gated sessions created from the web API (``/catalog/execute``,
    ``/plans/{id}/execute``, ``/snapshot/revert``, the ``gate_task_write`` and
    ``gate_demo_write`` routes, ...) never pass through an MCP tool call, so
    nothing recorded what they asked for — only ``confirm.approve``, which
    carried identifiers alone. Roughly 13 call sites across 8 route modules.

    Records **keys, counts and identifiers, never values**. Routing the payload
    through ``redact_structure`` was considered and rejected: it masks by key
    *name* only (``password``/``token``/``*key*``…), so ``root.RemoteSyslog.Server``,
    a webhook ``upload_url`` and every plan-step parameter would sail straight
    into the never-pruned audit log — strictly worse than the confirm row #266
    deletes. Keys answer *what was touched*; the device (drift/snapshot) remains
    the source of truth for *what it now is*, which is exactly the split
    ADR-0056 already relies on.

    ``danger_description`` is deliberately NOT included. It reads as safe —
    ``capabilities.describe_rule`` builds it from the survey's human labels —
    but ``tasks/gated.py::describe_create`` interpolates ``tag_filter``,
    ``interval`` and ``action_type``, i.e. request values. One describer being
    label-based does not make the field label-based.
    """
    fields: Dict[str, Any] = {
        # Joins this row to the confirm receipt that survives #266's strip.
        "confirm_token": session.token,
        "operation_id": session.operation_id,
        "device_id": session.device_id,
    }
    if session.is_plan:
        # plan.to_summary() carries step/operation/device/risk but NOT step
        # params, so operation ids and a count are safe; per-step `description`
        # is skipped because it is free text that may quote a value.
        steps = (session.plan_summary or {}).get("steps")
        steps = steps if isinstance(steps, list) else []
        fields["plan_steps"] = len(steps)
        ops = sorted({str(s.get("operation")) for s in steps
                      if isinstance(s, dict) and s.get("operation")})
        if ops:
            fields["plan_operations"] = ops
    elif session.is_action:
        action = session.action or {}
        # TOP-LEVEL keys only — no recursion. A nested `action_params` or
        # `fields` list contributes its own name and nothing from inside it.
        keys = sorted(str(k) for k in action if k not in _ACTION_IDENTITY_KEYS)
        if keys:
            fields["action_keys"] = keys
        for key in _ACTION_IDENTITY_KEYS:
            value = action.get(key)
            # Non-empty scalars only, mirroring outcome_identity_fields: the
            # audit store serialises with default=str and would happily
            # stringify a dict it was handed.
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                continue
            text = str(value).strip()
            if text:
                fields[key] = text
    else:
        params = session.params or {}
        if params:
            fields["param_keys"] = sorted(str(k) for k in params)
    return fields


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
    from admz.audit import outcome_identity_fields, record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)

    if not rate_limiter.check("confirm", client_key_from_request(request)):
        return _Approval("rate_limited")

    session = confirm_store.get_session(token)
    if session is None or session.effective_status != ConfirmStatus.PENDING:
        return _Approval("expired")

    if _is_locked(token):
        return _Approval("locked", session=session)

    # GH #178 — AUTHORIZATION. Until now this path made no authorization
    # decision at all: the principal above was resolved only to write audit
    # rows, so any authenticated user could approve anything, while *reading* a
    # credential required group membership. The gate guarding device writes was
    # weaker than the one guarding credential reads.
    #
    # Both approve entry points (the web form and the chat twin) funnel through
    # this helper, so one check covers both. Denial is deliberately NOT gated —
    # stopping a pending action is safe, and requiring privilege to say "no"
    # would be the wrong asymmetry.
    #
    # ANONYMOUS is handled at the call site, not inside the predicate — the same
    # split `principal_can_reveal` documents ("caller should consult the fleet
    # flag to decide"). Under ADMZ_AUTH_BACKEND=none, the default, there is no
    # identity at all, so group membership is not absent but *undefined*;
    # refusing would make a fresh install unable to approve anything, which is a
    # lockout of a different population. #178 scopes this the same way — it
    # rewrote its own headline because the unauthenticated framing "does not
    # hold under windows-local". So: allow, but never silently. Unlike the
    # password fail-open #178 was filed for, which left no trace whatsoever,
    # this records the decision on every approval and warns in the log.
    from admz.authz import principal_can_approve, approver_groups
    may_approve, authz_reason = principal_can_approve(principal)
    if not may_approve and authz_reason == "anonymous":
        logger.warning(
            "Approving with NO identity: ADMZ_AUTH_BACKEND has no authentication "
            "backend, so the approver group (%s) cannot be evaluated. Possession "
            "of the token is sufficient on this install.",
            ", ".join(approver_groups()))
        may_approve, authz_reason = True, "anonymous-no-identity"
    if not may_approve:
        record_event(
            principal, "confirm.denied_unauthorized",
            resource=_session_resource(session), success=False,
            error_message=f"not authorized to approve ({authz_reason})",
            details={"confirmed_by": confirmed_by, "decision": authz_reason,
                     "approver_groups": approver_groups()},
        )
        return _Approval(
            "not_authorized", session=session,
            detail=("Approving requires membership in one of the approver groups "
                    f"({', '.join(approver_groups())}). Decision: {authz_reason}."))

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

    # Wrap the registry so an approved ACS-Pro action (synthetic 'acs-server'
    # target) resolves to the configured server at the execution tail. The view
    # is transparent for every device session (it only intercepts 'acs-server').
    from admz.modules.acs_pro.registry_view import AcsRegistryView

    outcome = await operations.execute_approved_session(
        session,
        catalog=ctx.catalog,
        registry=AcsRegistryView(ctx.registry),
        executors=ctx.executors,
        plan_engine=ctx.plan_engine,
        git_repo=ctx.git_repo,
    )

    record_event(
        principal, "confirm.approve",
        resource=_session_resource(session),
        success=bool(outcome.get("success")),
        error_message="" if outcome.get("success") else str(outcome.get("error") or ""),
        details={
            "confirmed_by": confirmed_by,
            # WHY this principal was allowed to approve (#178) — "group:<name>"
            # for a real identity, "anonymous-no-identity" when there is no auth
            # backend to evaluate. Recorded on every approval so the degraded
            # case is auditable rather than invisible.
            "authz": authz_reason,
            "risk_level": session.risk_level,
            "confirmation_level": session.confirmation_level,
            "is_plan": session.is_plan,
            # #270 — WHAT was approved, key-only. Every approval funnels through
            # this helper whatever created the session, so web-API origins that
            # never touched an MCP tool call are covered by construction rather
            # than by each of ~13 call sites remembering. Spread BEFORE
            # outcome_identity_fields so a real outcome id always wins over a
            # requested one.
            **_approved_work_fields(session),
            # Allow-listed identifiers only — never ``**outcome``, whose shape
            # varies per operation and can carry device payloads. Empty for
            # operations that return none, leaving the row as it was.
            **outcome_identity_fields(outcome),
        },
    )

    _note_resolution_to_chat(token, session, outcome, confirmed_by)

    return _Approval("completed", session=session, outcome=outcome)


def _note_resolution_to_chat(
    token: str, session, outcome: dict, confirmed_by: str
) -> None:
    """Write a ``[console]`` event note into the conversation that spawned
    this session (if any), so the model knows in subsequent turns that the
    approval happened and how execution went. Metadata only — op/action id,
    device, surface, success/truncated error. NEVER params (they can carry
    secrets) and never a password. Best-effort: a note failure must not
    affect the approval result."""
    try:
        from admz.chatbot.sessions import chat_sessions

        link = chat_sessions.pop_action_link(token)
        if link is None:
            return  # not chat-originated (REST/dev approval)

        what = session.operation_id or "operation"
        if what.startswith("action:"):
            what = what.split(":", 1)[1]
        if session.is_plan:
            what = f"plan {session.plan_id or ''}".strip()
        surface = (
            "the confirmation card in this chat"
            if confirmed_by == "chat" else "the confirmation web page"
        )
        if outcome.get("success"):
            text = (
                f"[console] The user approved \"{what}\" on device "
                f"{session.device_id} via {surface}; it executed successfully."
            )
        else:
            err = str(outcome.get("error") or "unknown error")[:200]
            text = (
                f"[console] The user approved \"{what}\" on device "
                f"{session.device_id} via {surface}, but execution FAILED: {err}"
            )
        chat_sessions.append_event(
            link["principal"], link["conversation_id"], text
        )
    except Exception:  # noqa: BLE001 - never break an approval on a note
        logger.debug("chat resolution note failed for %s", token, exc_info=True)


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
            request,
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    if session.effective_status == ConfirmStatus.COMPLETED:
        return templates.TemplateResponse(
            request,
            "confirm_done.html",
            {
                "request": request,
                "title": "Plan Confirmed" if session.is_plan else "Operation Confirmed",
                "session": session,
                "is_plan": session.is_plan,
                "plan_summary": session.plan_summary if session.is_plan else None,
            },
        )

    if session.effective_status in (ConfirmStatus.EXPIRED, ConfirmStatus.DENIED):
        # Denied is terminal: never re-render an armed form for it.
        return templates.TemplateResponse(
            request,
            "capture_expired.html",
            {
                "request": request,
                "title": ("Request Denied"
                          if session.effective_status == ConfirmStatus.DENIED
                          else "Link Expired"),
            },
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
        request,
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
            request,
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    session = result.session
    is_plan = session.is_plan
    plan_summary = session.plan_summary if is_plan else None

    if result.status == "not_authorized":
        # 403, and the session stays PENDING — a caller who lacks the group must
        # not consume the token, so the right operator can still approve it.
        return templates.TemplateResponse(
            request,
            "confirm_form.html",
            {
                "request": request,
                "title": "Confirm Plan" if is_plan else "Confirm Operation",
                "token": token,
                "session": session,
                "needs_password": session.confirmation_level == "url_and_password",
                "error": result.detail,
                "is_plan": is_plan,
                "plan_summary": plan_summary,
            },
            status_code=403,
        )

    if result.status in ("locked", "wrong_password"):
        error = (
            "Too many failed attempts. This confirmation link is temporarily locked."
            if result.status == "locked"
            else "Incorrect confirmation password."
        )
        return templates.TemplateResponse(
            request,
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
        request,
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

    if result.status == "not_authorized":
        # The token is NOT consumed — the session stays pending so an operator
        # who is in the group can still approve it (#178).
        return JSONResponse(
            status_code=403,
            content={"status": "not_authorized", "error": result.detail},
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


@router.post("/api/chat/confirm/{token}/deny", tags=["confirm"])
async def chat_confirm_deny(
    request: Request,
    token: str,
    ctx: AppContext = Depends(get_context),
):
    """Explicitly decline a pending confirmation session.

    Terminal like an approval: the token can never be consumed afterwards
    (previously "deny" was purely client-side and the session silently
    lingered until TTL). Audited, and — when the session came from a chat
    turn — noted back into the conversation so the model knows the user
    said no instead of treating the action as still pending.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)

    if not rate_limiter.check("confirm", client_key_from_request(request)):
        return JSONResponse(
            status_code=429,
            content={"status": "rate_limited",
                     "error": "Too many confirm attempts from this address."},
        )

    session = confirm_store.get_session(token)
    if session is None or session.effective_status != ConfirmStatus.PENDING:
        return JSONResponse(status_code=410, content={"status": "expired"})

    if not confirm_store.deny_session(token, denied_by="chat"):
        return JSONResponse(status_code=410, content={"status": "expired"})

    # GH #170: denial is a terminal outcome for a captured rule-recipient
    # secret too, same as a successful approval consuming it. This is the
    # only deny path that exists (the plain web /confirm/{token} form has no
    # deny action), so this is the only place that needs the call. A no-op,
    # not an error, when this token never had a rule-secret stash — most
    # denials don't.
    from admz.rules.capture import discard_rule_secrets
    discard_rule_secrets(token)

    record_event(
        principal, "confirm.deny",
        resource=_session_resource(session),
        details={
            "risk_level": session.risk_level,
            "confirmation_level": session.confirmation_level,
            "is_plan": session.is_plan,
        },
    )

    _note_denial_to_chat(token, session)

    return {
        "status": "denied",
        "device_id": session.device_id,
        "operation_id": session.operation_id,
    }


def _note_denial_to_chat(token: str, session) -> None:
    """`[console]` note: the user explicitly declined — the action was NOT
    executed. Same linkage/secrecy rules as _note_resolution_to_chat."""
    try:
        from admz.chatbot.sessions import chat_sessions

        link = chat_sessions.pop_action_link(token)
        if link is None:
            return
        what = session.operation_id or "operation"
        if what.startswith("action:"):
            what = what.split(":", 1)[1]
        if session.is_plan:
            what = f"plan {session.plan_id or ''}".strip()
        chat_sessions.append_event(
            link["principal"], link["conversation_id"],
            f"[console] The user DENIED \"{what}\" on device "
            f"{session.device_id} via the confirmation card — the action "
            "was NOT executed. Do not retry it unless the user asks again.",
        )
    except Exception:  # noqa: BLE001 - never break a denial on a note
        logger.debug("chat denial note failed for %s", token, exc_info=True)
