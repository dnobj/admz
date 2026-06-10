"""Single gated-execution core shared by MCP, REST, and the plan engine.

ADMZ exposes device operations over three surfaces (the stdio MCP server, the
FastAPI REST API, and the plan engine). Historically each implemented the
confirmation gate independently, which drifted: only MCP honored the
configurable per-risk policy, REST hardcoded a dangerous-only check, and plans
used a separate boolean. This module is the single place that maps an
operation's ``risk_level`` to its effective confirmation level
(``get_confirmation_level``, ADR-0006) and runs the one shared execution tail.
ADR-0008 anticipated this as the "shared package" that removes the duplication.

It is deliberately a **leaf**: it imports only ``confirm_store`` (policy +
session store) and the typed exceptions, and receives ``catalog`` /
``registry`` / ``executors`` / ``store`` as parameters. It must never import
``admz.mcp.server``, ``admz.api.context``, or any route module, so it stays
importable from both the stdio MCP process and the uvicorn process with no
import cycle. ``get_confirmation_level`` already lazy-imports ``fleet_settings``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from admz.api.confirm_store import (
    ConfirmSession,
    ConfirmStatus,
    get_confirmation_level,
)
from admz.exceptions import (
    AccountNotFoundError,
    DeviceNotFoundError,
    NoExecutorError,
    OperationNotFoundError,
)
from admz.executor.models import StepResult

# Single source of truth (was duplicated in mcp/server.py + routes/catalog.py).
CONFIRM_TOKEN_TTL_SECONDS = 300  # 5 minutes

# Strictness ordering, used to pick a plan's required level across its steps.
_LEVEL_ORDER = {"none": 0, "llm_confirm": 1, "url_only": 2, "url_and_password": 3}


# --------------------------------------------------------------------------
# Confirmation policy (one function the whole app shares)
# --------------------------------------------------------------------------


def resolve_confirmation(risk_level: str) -> str:
    """Effective confirmation level for a risk class (the single policy fn)."""
    return get_confirmation_level(risk_level)


def _resolve_store(store: Any) -> Any:
    """Return ``store`` if given, else the CURRENT module-level confirm_store.

    Read lazily (not bound at import) because test fixtures reassign
    ``admz.api.confirm_store.confirm_store`` to a per-test store; freezing a
    reference at import time would make this module read a stale store.
    """
    if store is not None:
        return store
    from admz.api.confirm_store import confirm_store
    return confirm_store


# --------------------------------------------------------------------------
# Blocked-envelope construction (formerly inline in mcp/server.py)
# --------------------------------------------------------------------------


def block_reason(risk: str, level: str, *, is_plan: bool = False) -> str:
    noun = "plan" if is_plan else "operation"
    return (
        f"This {noun} is classified as '{risk}' and requires "
        f"{level} confirmation."
    )


def build_block_message(
    risk: str, level: str, token: str, *, is_plan: bool = False
) -> str:
    """LLM-facing next-step guidance. Moved verbatim out of mcp/server.py so
    MCP and REST emit identical wording (REST emitted none before)."""
    if is_plan:
        if level == "llm_confirm":
            return (
                f"This plan is classified as '{risk}' and requires user "
                f"confirmation. If the user has ALREADY clearly consented in "
                f"this conversation, re-call execute_plan with "
                f"confirm_dangerous=true to proceed. Otherwise summarize the "
                f"plan's steps and ask for their consent first."
            )
        return (
            f"This plan is classified as '{risk}' and requires confirmation "
            f"via the web UI. Present the user with the confirmation URL "
            f"(/confirm/{token}). The page will ask for "
            + ("a password and " if level == "url_and_password" else "")
            + "explicit approval. The plan cannot be executed via the chatbot "
            "alone."
        )
    if level == "llm_confirm":
        return (
            f"This operation is classified as '{risk}' and requires user "
            f"confirmation. **If the user has already given clear consent in "
            f"this conversation** (e.g. they said 'yes', 'go ahead', "
            f"'proceed', or otherwise agreed when you described the action), "
            f"call confirm_dangerous_operation with this confirm_token "
            f"IMMEDIATELY — don't re-ask. Otherwise, briefly summarize what "
            f"will happen and ask for their consent before calling "
            f"confirm_dangerous_operation."
        )
    return (
        f"This operation is classified as '{risk}' and requires confirmation "
        f"via the web UI. Present the user with the confirmation URL "
        f"(/confirm/{token}). The page will ask for "
        + ("a password and " if level == "url_and_password" else "")
        + "explicit approval. The operation cannot be completed via the "
        "chatbot alone."
    )


def blocked_envelope(
    session: ConfirmSession, *, reason: Optional[str] = None, is_plan: bool = False
) -> Dict[str, Any]:
    """The ONE canonical blocked response both surfaces return."""
    if reason is None:
        reason = block_reason(
            session.risk_level, session.confirmation_level, is_plan=is_plan
        )
    return {
        "blocked": True,
        "risk_level": session.risk_level,
        "confirmation_level": session.confirmation_level,
        "reason": reason,
        "confirm_token": session.token,
        "confirm_tool": "confirm_dangerous_operation",
        "confirm_url": f"/confirm/{session.token}",
        "message": build_block_message(
            session.risk_level, session.confirmation_level, session.token,
            is_plan=is_plan,
        ),
    }


# --------------------------------------------------------------------------
# The execution tail (formerly duplicated in server.py, catalog.py, engine.py)
# --------------------------------------------------------------------------


async def run_execution_tail(
    *,
    device_id: str,
    operation_id: str,
    family: str,
    params: Mapping[str, str],
    catalog: Any,
    registry: Any,
    executors: Mapping[str, Any],
) -> StepResult:
    """Load op → pick executor → fetch device+creds → execute.

    Raises ``OperationNotFoundError`` / ``NoExecutorError`` /
    ``DeviceNotFoundError`` so each surface can shape its own error response.
    A device with no stored account (factory-default) falls back to empty
    credentials, matching the prior per-surface behavior.
    """
    operation = catalog.get_operation(family, operation_id)
    if not operation:
        raise OperationNotFoundError(
            f"Operation '{operation_id}' not found in the {family} catalog"
        )

    executor = executors.get(family)
    if not executor:
        raise NoExecutorError(f"No executor available for API family '{family}'")

    if not registry.device_exists(device_id):
        raise DeviceNotFoundError(f"Device not found: {device_id}")

    device = registry.get_device_info(device_id)
    device["device_id"] = device_id
    try:
        credentials = registry.get_credentials(device_id)
    except AccountNotFoundError:
        credentials = {"username": "", "password": ""}

    result = await executor.execute(
        operation.to_executor_dict(), device, credentials, dict(params or {})
    )

    # Connectivity self-healing: if the executor had to correct the device's
    # scheme/auth (it connect-refused on the configured scheme, or the auth
    # method was wrong), persist the corrected profile so the next call uses
    # it directly. Best-effort — a backend without update_device_info (e.g.
    # Vault, pending H-4) just keeps re-healing per call.
    learned = getattr(result, "learned_auth", None)
    if learned:
        _persist_learned_auth(registry, device_id, device.get("auth"), learned)

    return result


def _persist_learned_auth(
    registry: Any, device_id: str, current_auth: Any, learned: Mapping[str, str]
) -> None:
    import logging

    merged = dict(current_auth) if isinstance(current_auth, dict) else {}
    merged.update(learned)
    if merged == current_auth:
        return
    try:
        registry.update_device_info(device_id, {"auth": merged})
        logging.getLogger(__name__).info(
            "Self-healed connectivity profile for %s: %s", device_id, dict(learned)
        )
    except Exception as exc:  # pragma: no cover - best effort
        logging.getLogger(__name__).debug(
            "Could not persist self-healed auth for %s: %s", device_id, exc
        )


def normalize_result(
    result: StepResult,
    *,
    confirmed: bool = False,
    risk_level: str = "",
    confirmation_level: str = "",
) -> Dict[str, Any]:
    """Shared success/result dict. ``confirmed=True`` (a token was consumed)
    adds the ``confirmed``/``confirmed_dangerous``/risk fields the prior
    confirm paths returned."""
    out: Dict[str, Any] = {
        "success": result.success,
        "operation_id": result.operation_id,
        "device_id": result.device_id,
        "status_code": result.status_code,
        "duration_ms": result.duration_ms,
    }
    if confirmed:
        # 'confirmed_dangerous' kept for backward compat with earlier clients.
        out["confirmed_dangerous"] = True
        out["confirmed"] = True
        if risk_level:
            out["risk_level"] = risk_level
        if confirmation_level:
            out["confirmation_level"] = confirmation_level
    if result.success:
        out["data"] = result.parsed_data
    else:
        out["error"] = result.error
    if result.warnings:
        out["warnings"] = result.warnings
    return out


# --------------------------------------------------------------------------
# Single-op gated entry point + confirm consumption
# --------------------------------------------------------------------------


async def execute_gated_operation(
    *,
    device_id: str,
    operation_id: str,
    family: str,
    params: Mapping[str, str],
    catalog: Any,
    registry: Any,
    executors: Mapping[str, Any],
    store: Any = None,
) -> Dict[str, Any]:
    """Risk → level. ``none`` runs inline and returns a normalized result;
    any other level creates a confirm session and returns the blocked
    envelope WITHOUT executing.

    The risk gate runs before the operation-existence check (matching the
    prior MCP ordering): an unknown op whose risk resolves to ``none`` reaches
    ``run_execution_tail`` and raises ``OperationNotFoundError`` for the caller
    to shape.
    """
    store = _resolve_store(store)
    risk = catalog.get_risk_level(family, operation_id)
    level = resolve_confirmation(risk)

    if level != "none":
        op = catalog.get_operation(family, operation_id)
        # Most informative reason available: danger_description for dangerous
        # ops, service_impact for service-affecting ops, else generic.
        if op is not None and getattr(op, "danger_description", ""):
            reason = op.danger_description
        elif op is not None and getattr(op, "service_impact", ""):
            reason = op.service_impact
        else:
            reason = block_reason(risk, level)
        session = store.create_session(
            device_id=device_id,
            operation_id=operation_id,
            family=family,
            params=dict(params or {}),
            risk_level=risk,
            confirmation_level=level,
            danger_description=reason,
            ttl=CONFIRM_TOKEN_TTL_SECONDS,
        )
        return blocked_envelope(session, reason=reason)

    result = await run_execution_tail(
        device_id=device_id,
        operation_id=operation_id,
        family=family,
        params=params,
        catalog=catalog,
        registry=registry,
        executors=executors,
    )
    return normalize_result(result)


async def consume_confirmation(
    token: str,
    *,
    catalog: Any,
    registry: Any,
    executors: Mapping[str, Any],
    store: Any = None,
    confirmed_by: str,
    enforce_url_flow_block: bool,
) -> Dict[str, Any]:
    """The ONE token-consumption path for single operations.

    Looks up the session; if ``enforce_url_flow_block`` refuses ``url_*`` levels
    (a passwordless caller — MCP, the JSON REST endpoint — must not complete a
    URL/password gate); atomically completes the session; re-runs the execution
    tail; returns a normalized, ``confirmed=True`` result.

    Plan sessions are NOT executed here — they are run by the plan engine via
    the web-form approval path. Callers that might receive a plan token should
    branch on ``session.is_plan`` before calling this.
    """
    store = _resolve_store(store)
    session = store.get_session(token)
    if session is None or session.effective_status != ConfirmStatus.PENDING:
        return {"success": False, "error": "Invalid or expired confirmation token."}

    if enforce_url_flow_block and session.confirmation_level in (
        "url_only",
        "url_and_password",
    ):
        return {
            "success": False,
            "error": (
                f"This operation requires '{session.confirmation_level}' "
                f"confirmation, which must be completed via the web UI. "
                f"Direct the user to /confirm/{token}."
            ),
            "confirm_url": f"/confirm/{token}",
            "confirmation_level": session.confirmation_level,
        }

    if not store.complete_session(token, confirmed_by=confirmed_by):
        return {
            "success": False,
            "error": (
                "Confirmation token already used or expired before this "
                "request completed."
            ),
        }

    try:
        result = await run_execution_tail(
            device_id=session.device_id,
            operation_id=session.operation_id,
            family=session.family,
            params=session.params,
            catalog=catalog,
            registry=registry,
            executors=executors,
        )
    except OperationNotFoundError:
        return {
            "success": False,
            "error": f"Operation '{session.operation_id}' no longer found in catalog",
        }
    except NoExecutorError:
        return {
            "success": False,
            "error": f"No executor for family '{session.family}'",
        }

    return normalize_result(
        result,
        confirmed=True,
        risk_level=session.risk_level,
        confirmation_level=session.confirmation_level,
    )


def _register_plan_from_session(plan_engine: Any, session: "ConfirmSession") -> None:
    """Reconstruct an ExecutionPlan from a confirm session's stored step data
    and register it in plan_engine._plans so run_plan can find it.

    Called when the approving process is different from the one that created
    the plan (C-1: chat MCP subprocess creates plan, uvicorn process approves).
    """
    from admz.plans.models import ExecutionPlan, FailurePolicy, PlanStatus, PlanStep

    steps_data = json.loads(session.plan_steps_json or "[]")
    summary = session.plan_summary
    steps = [
        PlanStep(
            step_number=s["step_number"],
            operation_id=s["operation_id"],
            device_id=s["device_id"],
            params=s.get("params", {}),
            description=s.get("description", ""),
            risk_level=s.get("risk_level", "normal"),
            family=s.get("family", "vapix"),
            depends_on=s.get("depends_on", []),
        )
        for s in steps_data
    ]
    try:
        on_failure = FailurePolicy(summary.get("on_failure", "stop"))
    except ValueError:
        on_failure = FailurePolicy.STOP

    plan = ExecutionPlan(
        plan_id=session.plan_id,
        description=summary.get("description", ""),
        steps=steps,
        on_failure=on_failure,
        status=PlanStatus.APPROVED,
        risk_summary=summary.get("risk_summary", {}),
    )
    plan_engine.register_plan(plan)


async def execute_approved_session(
    session: ConfirmSession,
    *,
    catalog: Any,
    registry: Any,
    executors: Mapping[str, Any],
    plan_engine: Any = None,
) -> Dict[str, Any]:
    """Run the op/plan held by an ALREADY-completed confirm session.

    The web form (``/confirm/{token}``) and the in-chat approval twin verify
    the password and complete the session themselves, then call this to
    actually perform the approved work — closing the gap where ``url_*`` ops
    were marked approved but never executed. Returns a normalized outcome dict.
    """
    if session.is_plan:
        if plan_engine is None:
            return {"success": False, "error": "Plan engine unavailable"}
        # If this process didn't create the plan (e.g. the plan was created
        # in a chat MCP subprocess but approved via the web UI in the uvicorn
        # process) the in-memory dict won't have it.  Reconstruct from the
        # serialized step data stored in the confirm session.
        if plan_engine.get_plan(session.plan_id) is None and session.plan_steps_json:
            _register_plan_from_session(plan_engine, session)
        try:
            plan = await plan_engine.run_plan(session.plan_id)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {
            "success": all(r.success for r in plan.results),
            "is_plan": True,
            **plan.to_results(),
        }

    try:
        result = await run_execution_tail(
            device_id=session.device_id,
            operation_id=session.operation_id,
            family=session.family,
            params=session.params,
            catalog=catalog,
            registry=registry,
            executors=executors,
        )
    except OperationNotFoundError:
        return {
            "success": False,
            "error": f"Operation '{session.operation_id}' no longer found in catalog",
        }
    except NoExecutorError:
        return {"success": False, "error": f"No executor for family '{session.family}'"}
    except DeviceNotFoundError:
        return {"success": False, "error": f"Device not found: {session.device_id}"}

    return normalize_result(
        result,
        confirmed=True,
        risk_level=session.risk_level,
        confirmation_level=session.confirmation_level,
    )


# --------------------------------------------------------------------------
# Plan-level gate (same configurable per-risk policy, applied to plans)
# --------------------------------------------------------------------------


def _plan_level_and_risk(steps: Sequence[Any]) -> Tuple[str, str]:
    """Return (max required confirmation level, the risk that drove it)."""
    best_level, best_risk = "none", "read-only"
    for step in steps:
        risk = getattr(step, "risk_level", "") or "read-only"
        level = resolve_confirmation(risk)
        if _LEVEL_ORDER.get(level, 0) > _LEVEL_ORDER.get(best_level, 0):
            best_level, best_risk = level, risk
    return best_level, best_risk


def resolve_plan_confirmation(steps: Sequence[Any]) -> str:
    """Max required confirmation level across all of a plan's steps."""
    return _plan_level_and_risk(steps)[0]


async def _run_plan_results(plan_engine: Any, plan_id: str) -> Dict[str, Any]:
    plan = await plan_engine.run_plan(plan_id)
    return {"success": True, **plan.to_results()}


async def execute_gated_plan(
    plan_engine: Any,
    plan_id: str,
    *,
    store: Any = None,
    confirm_dangerous: bool = False,
) -> Dict[str, Any]:
    """Apply the per-risk confirmation policy to a whole plan (ADR-0005 +
    ADR-0006). The plan's required level is the strictest level across its
    steps:

      - ``none``        → run immediately.
      - ``llm_confirm`` → ``confirm_dangerous=True`` runs it; else blocked
                          with ``retry_with={confirm_dangerous: True}``.
      - ``url_*``       → boolean is insufficient; create (or reuse) a plan
                          confirm session and return a blocked envelope whose
                          ``/confirm/{token}`` page approves AND runs the plan.
    """
    store = _resolve_store(store)
    plan = plan_engine.get_plan(plan_id)
    if plan is None:
        return {"success": False, "error": f"Plan not found: {plan_id}"}

    level, risk = _plan_level_and_risk(plan.steps)

    if level == "none":
        return await _run_plan_results(plan_engine, plan_id)

    if level == "llm_confirm":
        if confirm_dangerous:
            return await _run_plan_results(plan_engine, plan_id)
        return {
            "success": False,
            "blocked": True,
            "reason": "plan_requires_confirmation",
            "risk_level": risk,
            "confirmation_level": "llm_confirm",
            "message": build_block_message(risk, "llm_confirm", "", is_plan=True),
            "retry_with": {"confirm_dangerous": True},
        }

    # url_only / url_and_password — deterministic web/widget approval required.
    session = store.get_session_by_plan(plan_id)
    if session is None:
        device_ids = {getattr(s, "device_id", "") for s in plan.steps}
        first = plan.steps[0] if plan.steps else None
        device_id = (
            first.device_id if (first and len(device_ids) == 1) else "multiple"
        )
        # Serialize the full step data so the approving process (which may be a
        # different uvicorn process than the MCP subprocess that created the plan)
        # can reconstruct and execute the plan from the confirm session alone.
        plan_steps_json = json.dumps([s.to_dict() for s in plan.steps])
        session = store.create_session(
            device_id=device_id,
            operation_id=f"plan:{plan_id}",
            family=(getattr(first, "family", "vapix") if first else "vapix"),
            params={},
            risk_level=risk,
            confirmation_level=level,
            danger_description="",
            plan_id=plan_id,
            plan_summary_json=json.dumps(plan.to_summary()),
            plan_steps_json=plan_steps_json,
            ttl=CONFIRM_TOKEN_TTL_SECONDS,
        )
    env = blocked_envelope(session, is_plan=True)
    env["success"] = False
    return env
