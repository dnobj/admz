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

import inspect
import json
import logging
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

from admz.approval_context import approved
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


def missing_credentials_warning(
    registry: Any, device_id: str, family: str = "vapix"
) -> str:
    """Non-empty warning when the device has no stored credentials.

    Every gated vapix operation authenticates, so approving one against a
    credential-less device just burns the approval on a 401. Best-effort:
    no registry at gate time (some callers pass None) or a lookup error
    means no warning — the gate itself must never break on this check.
    """
    if family != "vapix" or registry is None:
        return ""
    try:
        creds = registry.get_credentials(device_id)
    except AccountNotFoundError:
        creds = None
    except Exception:  # noqa: BLE001 - backend hiccup: can't tell, don't cry wolf
        return ""
    if creds and creds.get("password"):
        return ""
    return (
        "NOTE: ADMZ has no stored credentials for this device — this "
        "operation requires authentication and will fail with 401 if "
        "approved. Set credentials first (onboard the device or use the "
        "credential capture form)."
    )


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
    # ADR-0039: only persist for families that self-heal (edge devices). A
    # server target (ACS Pro) authenticates per-connection and must not have
    # its stored auth rewritten — a no-op for vapix (self_heals() defaults True).
    learned = getattr(result, "learned_auth", None)
    if learned and getattr(executor, "self_heals", lambda: True)():
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
        # Don't let the user approve something doomed to 401: every gated
        # vapix op authenticates, so if ADMZ holds no credentials for the
        # device, say so on the confirm card BEFORE they click approve.
        # (Live case: an approved factory reset failed with 401 because the
        # device had never been onboarded.)
        cred_warning = missing_credentials_warning(registry, device_id, family)
        if cred_warning:
            reason = f"{reason} {cred_warning}".strip()

        # #334: a gated op's params are persisted verbatim into
        # confirm_sessions.params_json and rendered unmasked on the approval
        # page — for an op like pwdgrp.cgi:update-user, one of those params is
        # a new device password. Strip catalog-declared secret-shaped values
        # (never the keys) before either happens; the approval page prompts
        # for them separately (secret_fields) and the value is merged back in
        # at execution time, never stored. VAPIX-only: no other family's
        # Operation.request is known to use this placeholder convention, and
        # secret_param_names degrades to "nothing to strip" for a shape it
        # doesn't recognise, so this is additive, not a silent narrowing for
        # families it doesn't apply to.
        caller_params = dict(params or {})
        stored_params = caller_params
        secret_fields: list = []
        if family == "vapix" and op is not None:
            try:
                from admz.executor.vapix import secret_param_names

                secret_keys = secret_param_names(op, caller_params)
            except Exception:  # noqa: BLE001
                # A bug in detection must not crash the gate itself — but
                # note this fails toward LEAVING params as given, not toward
                # stripping everything: a value we failed to classify still
                # reaches params_json unmasked, same as before this fix,
                # rather than the gate silently blocking every operation in
                # this family. Logged loudly so it doesn't fail silently too.
                logger.warning(
                    "secret_param_names failed for %s — leaving params as "
                    "given", operation_id, exc_info=True)
                secret_keys = set()
            if secret_keys:
                stored_params = {
                    k: v for k, v in caller_params.items() if k not in secret_keys
                }
                secret_fields = sorted(secret_keys)

        session = store.create_session(
            device_id=device_id,
            operation_id=operation_id,
            family=family,
            params=stored_params,
            secret_fields=secret_fields,
            risk_level=risk,
            confirmation_level=level,
            danger_description=reason,
            ttl=CONFIRM_TOKEN_TTL_SECONDS,
        )
        env = blocked_envelope(session, reason=reason)
        if cred_warning:
            env["credential_warning"] = cred_warning
            env["message"] = f"{env.get('message', '')} {cred_warning}".strip()
        if secret_fields:
            env["message"] = (
                f"{env.get('message', '')} This operation needs "
                f"{', '.join(secret_fields)} entered securely on the "
                "confirmation page — it is not accepted here."
            ).strip()
        return env

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

    # #334: this path (chat's confirm_dangerous_operation / the JSON REST
    # endpoint) has no way to collect a secret value — accepting one here
    # would just re-open the hole this fix closes, letting it arrive through
    # a tool argument instead of params. So a session with unresolved secret
    # fields is refused unconditionally, same shape as the url_* block above,
    # even for an operator who has reconfigured this risk class to
    # llm_confirm: a credential-bearing operation always needs the web form,
    # regardless of what confirm_level_<risk> says for everything else.
    if session.secret_fields:
        return {
            "success": False,
            "error": (
                f"This operation requires {', '.join(session.secret_fields)} "
                "to be entered securely on the confirmation page — it cannot "
                f"be supplied here. Direct the user to /confirm/{token}."
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

    # #281: strip the payload only now that the outcome is known, and only on
    # success. A failed write keeps the value that was requested: there is no
    # device state to consult for a write that did not land, so this row is the
    # only remaining record of what was asked for. ADR-0056 makes drift the
    # source of truth for writes that SUCCEEDED, which is why the success case
    # can drop it immediately.
    #
    # Bounded, not indefinite: ConfirmStore._cleanup strips any completed row
    # older than PAYLOAD_RETENTION_SECONDS, so the forensic window closes on its
    # own. That sweep also covers a process death between complete_session and
    # here, which would otherwise leave a successful write's payload behind.
    # Not getattr(result, "success", False): run_execution_tail returns a
    # StepResult, and normalize_result below reads result.success unguarded. A
    # defaulted getattr here would fail SILENT on a rename — quietly never
    # stripping again — while the line after it failed loud.
    if result.success:
        store.strip_payload(token)

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
        # The completion hook rides the plan summary across the approving
        # process boundary (ADR-0050) — this line is the whole cross-process story.
        on_complete=summary.get("on_complete"),
    )
    plan_engine.register_plan(plan)


# --------------------------------------------------------------------------
# Action sessions (ADR-0034) — registry-level actions behind the same widget
# --------------------------------------------------------------------------
#
# accept_baseline and delete_device don't execute a catalog operation, so the
# per-op gate can't hold them — but they're consequential, so they go through
# the SAME link/widget approval as device writes. The MCP handler validates
# the request, serializes it into an action session, and returns the standard
# blocked envelope; the confirm route's approval path dispatches here.


def tombstone_device(device_id: str, git_repo: Any, *, removed_by: str = "") -> None:
    """Record a deliberate device removal in the git config repo.

    Writes ``fleet/{device_id}/REMOVED.yaml`` and commits it (reusing the
    ADR-0031 Audit-commit pattern) so the repo shows the device was retired
    on purpose, distinct from a device that merely went stale. The config
    history is kept. Best-effort: a tombstone failure must never block the
    deletion, so callers wrap this loosely and it swallows its own errors.
    """
    if git_repo is None:
        return
    try:
        import time as _t
        import yaml as _yaml
        device_dir = git_repo.device_path(device_id)
        device_dir.mkdir(parents=True, exist_ok=True)
        (device_dir / "REMOVED.yaml").write_text(
            _yaml.safe_dump(
                {
                    "removed": True,
                    "removed_at": _t.time(),
                    "removed_by": removed_by or "",
                    "reason": "device deleted from the registry",
                },
                default_flow_style=False, sort_keys=True,
            )
        )
        git_repo.commit_snapshot(
            device_id, message=f"Removed: {device_id}", auto_push=True,
        )
    except Exception:  # pragma: no cover — tombstone is best-effort
        logger.warning("tombstone commit failed for %s", device_id, exc_info=True)


def refresh_drift_after_accept(
    device_id: str, accepted_sha: Any, latest_observed_sha: Any,
) -> None:
    """Reconcile the drift cache right after a baseline is blessed, so the
    UI shows the new state immediately instead of lingering on the stale
    "drifted" signature until the next manual/scheduled Check drift.

    Accepting the *latest observation* means the last live read now equals
    the baseline → zero drift by construction; record an in-sync signature
    (this also logs a "cleared" transition if it had been drifting). When an
    older/specific commit is accepted we can't claim in-sync, so the cached
    signature is dropped and the next check recomputes. Best-effort: a cache
    hiccup must never fail the accept itself.
    """
    try:
        from admz.snapshot import drift_alerts as _da
        if latest_observed_sha and accepted_sha == latest_observed_sha:
            from admz.snapshot.models import DriftReport
            _da.drift_alerts.process_report(
                DriftReport(device_id=device_id, has_drift=False,
                            fields=[], observed_sha=accepted_sha)
            )
        else:
            _da.drift_alerts.clear_baseline(device_id)
    except Exception:  # pragma: no cover — cache refresh is best-effort
        logger.warning(
            "drift-cache refresh after accept failed for %s",
            device_id, exc_info=True,
        )


def _action_accept_baseline(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    device_id = action["device_id"]
    target = action["baseline_sha"]
    previous = action.get("previous_baseline_sha")
    registry.set_config_pointers(device_id, baseline_sha=target)
    note = (action.get("note") or "").strip()
    if git_repo and note:
        try:
            import time as _t
            import yaml as _yaml
            device_dir = git_repo.device_path(device_id)
            device_dir.mkdir(parents=True, exist_ok=True)
            (device_dir / "BASELINE.yaml").write_text(
                _yaml.safe_dump({
                    "accepted_at": _t.time(),
                    "accepted_by": action.get("accepted_by", ""),
                    "baseline_sha": target,
                    "note": note,
                }, default_flow_style=False, sort_keys=True)
            )
            git_repo.commit_snapshot(
                device_id, message=f"Accept baseline: {device_id}", auto_push=True,
            )
        except Exception:
            logger.warning("baseline note commit failed for %s", device_id, exc_info=True)
    latest = None
    try:
        latest = registry.get_device_info(device_id).get("latest_observed_sha")
    except Exception:
        latest = None
    refresh_drift_after_accept(device_id, target, latest)
    return {
        "success": True,
        "action": "accept_baseline",
        "device_id": device_id,
        "baseline_sha": target,
        "previous_baseline_sha": previous,
        "message": (
            f"Baseline for {device_id} is now {target[:12]}. Drift is "
            "measured against it; restore_device (ref omitted) replays it."
        ),
    }


def _action_delete_device(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    device_id = action["device_id"]
    if not registry.device_exists(device_id):
        return {
            "success": False,
            "action": "delete_device",
            "error": f"Device not found: {device_id}",
        }
    # Record the deliberate removal in git (history retained), then remove
    # the registry row + accounts.
    tombstone_device(device_id, git_repo, removed_by=action.get("removed_by", ""))
    registry.remove_device(device_id)
    return {
        "success": True,
        "action": "delete_device",
        "device_id": device_id,
        "message": f"Device {device_id} and its accounts were removed.",
    }


def _action_create_task(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved create-task: write the task the session was holding.

    The scheduler lives on the app context — approvals always execute in
    the uvicorn process (web form or chat twin), where it exists."""
    from admz.api.context import get_context
    from admz.tasks.gated import TaskSpecError, apply_create_task

    spec = {k: v for k, v in action.items()
            if k not in ("action", "_confirmed_by")}
    try:
        task = apply_create_task(
            spec,
            scheduler=get_context().scheduler,
            registry=registry,
            approved_by=action.get("_confirmed_by") or "confirm-widget",
        )
    except TaskSpecError as exc:
        return {"success": False, "action": "create_task", "error": str(exc)}
    return {
        "success": True, "action": "create_task", "task": task,
        "message": f"Task '{task.get('id')}' created.",
    }


def _action_update_task(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved update-task: apply the held field changes."""
    from admz.api.context import get_context
    from admz.tasks.gated import TaskSpecError, apply_update_task

    task_id = action.get("task_id") or ""
    fields = {k: v for k, v in action.items()
              if k not in ("action", "task_id", "_confirmed_by")}
    try:
        task = apply_update_task(
            task_id, fields, scheduler=get_context().scheduler,
        )
    except TaskSpecError as exc:
        return {"success": False, "action": "update_task", "error": str(exc)}
    return {
        "success": True, "action": "update_task", "task": task,
        "message": f"Task '{task_id}' updated.",
    }


def _action_delete_task(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved delete-task: remove the schedule the session was holding."""
    from admz.api.context import get_context
    from admz.tasks.gated import TaskSpecError, apply_delete_task

    task_id = action.get("task_id") or ""
    try:
        result = apply_delete_task(task_id, scheduler=get_context().scheduler)
    except TaskSpecError as exc:
        return {"success": False, "action": "delete_task", "error": str(exc)}
    return {
        "success": True, "action": "delete_task", **result,
        "message": f"Task '{task_id}' removed.",
    }


async def _action_assign_demo_fragment(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved fragment capture: run the shared core the session was holding.

    The core re-checks drift at APPLY time, so the captured values come from
    the diff as it exists NOW — not as it looked when the widget was raised."""
    from admz.api.context import get_context
    from admz.demos.actions import (
        DemoActionError, assign_fragment_core, resolve_demo,
    )

    ctx = get_context()
    try:
        demo = resolve_demo(ctx.demo_store, action.get("demo") or "")
        result = await assign_fragment_core(
            ctx, demo,
            fields=list(action.get("fields") or []),
            role=action.get("role"),
            mode=action.get("mode") or "set",
            principal=action.get("_confirmed_by") or "confirm-widget",
        )
    except DemoActionError as exc:
        return {"success": False, "action": "assign_demo_fragment",
                "error": str(exc)}
    n = len(result.get("added") or [])
    return {
        "success": True, "action": "assign_demo_fragment", **result,
        "message": f"Assigned {n} field(s) to demo '{demo.name}'.",
    }


def _action_adopt_demo(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved adopt: mark the demo active. The core re-runs BOTH guards
    (legacy-scenario hold + same-key overlap) at apply time — a conflict that
    appeared since approval fails cleanly instead of slipping through."""
    from admz.api.context import get_context
    from admz.demos.actions import (
        DemoActionError, adopt_demo_core, resolve_demo,
    )

    ctx = get_context()
    try:
        demo = resolve_demo(ctx.demo_store, action.get("demo") or "")
        result = adopt_demo_core(
            ctx, demo, principal=action.get("_confirmed_by") or "confirm-widget",
        )
    except DemoActionError as exc:
        return {"success": False, "action": "adopt_demo", "error": str(exc)}
    return {"action": "adopt_demo", **result}


async def _action_start_demo_survey(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved deep survey: start the run the operator agreed to (#199).

    Runs the SAME ``start_survey_core`` the ungated route would have called, so
    an approved survey cannot drift from an unapproved one. The 409 for "one is
    already running" is re-checked here rather than at approval time — minutes
    can pass between the widget and the click.
    """
    from admz.api.context import get_context
    from admz.demos.inference import collect

    ctx = get_context()
    try:
        run = collect.start_survey_core(
            ctx, ctx.inference_run_store,
            register_new=bool(action.get("register_new", True)),
            timeout=float(action.get("timeout") or 5.0),
            subnet=action.get("subnet") or None,
            proposal_store=ctx.proposal_store,
            include_weak=bool(action.get("include_weak", True)),
            principal=action.get("_confirmed_by") or "confirm-widget",
        )
    except collect.SurveyAlreadyRunningError as exc:
        return {"success": False, "action": "start_demo_survey", "error": str(exc)}
    return {"success": True, "action": "start_demo_survey", "started": True,
            "run": run.header(),
            "message": f"Deep survey started (run {run.id})."}


async def _action_register_discovered_device(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved register-and-onboard of one discovered device (#199).

    Onboarding is what makes this more than a registry write: a factory-default
    unit gets an admin account created on it. The registry add and the onboard
    stay together here exactly as the tool does them — decoupling the two is
    item 3 of #199 and deliberately not done under cover of this gate.
    """
    from admz.onboarding import onboard_device_credentials

    device_id = action.get("device_id") or ""
    info = dict(action.get("device_info") or {})
    if not device_id:
        return {"success": False, "action": "register_discovered_device",
                "error": "device_id is required"}
    registry.add_device(device_id, info)
    from admz.api.context import get_context

    ctx = get_context()
    onboarding = await onboard_device_credentials(
        device_id=device_id, registry=registry,
        catalog=ctx.catalog, executors=ctx.executors)
    return {
        "success": True, "action": "register_discovered_device",
        "device_id": device_id, "onboarding": onboarding,
        "message": (f"Device '{device_id}' registered. "
                    + str(onboarding.get("message", ""))).strip(),
    }


def _resolve_device_and_creds(registry: Any, device_id: str) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Device info dict (with ``device_id`` set) + credentials, mirroring
    ``run_execution_tail`` — empty creds if the device has no stored account."""
    device = registry.get_device_info(device_id)
    device["device_id"] = device_id
    try:
        creds = registry.get_credentials(device_id)
    except AccountNotFoundError:
        creds = {"username": "", "password": ""}
    return device, creds


async def _action_create_action_rule(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved create-action-rule: re-render the rule via the atlas (merging any
    captured recipient secrets) and run the SOAP create sequence on the device.

    Building at execute time keeps rendered bodies — and any inlined secret — out
    of the confirm session; the session held only the spec."""
    from admz.api.context import get_context
    from admz.rules import capabilities, runner
    from admz.rules.runner import RuleRunnerError

    device_id = action.get("device_id") or ""
    model = action.get("model") or ""
    condition_id = action.get("condition_id") or ""
    action_token = action.get("action_token") or ""
    rule_name = action.get("rule_name") or "AtlasRule"
    param_choices = dict(action.get("param_choices") or {})

    # Recipient secrets captured out-of-context via the secure form are merged
    # here at execute time — never stored in the confirm session. The stash is
    # keyed by the confirm token, injected as ``_token`` by
    # execute_approved_session.
    if action.get("requires_secret_capture"):
        from admz.rules.capture import consume_captured_rule_secrets
        secrets = consume_captured_rule_secrets(action.get("_token") or "")
        if not secrets:
            return {
                "success": False, "action": "create_action_rule",
                "error": ("Recipient credentials were not captured (or the secure "
                          "form expired). Ask the user to re-enter them via the "
                          "secure link, then approve again."),
            }
        param_choices.update(secrets)

    if not registry.device_exists(device_id):
        return {"success": False, "action": "create_action_rule",
                "error": f"Device not found: {device_id}"}
    if not model:
        try:
            model = (registry.get_device_info(device_id) or {}).get("model") or ""
        except Exception:  # noqa: BLE001
            model = ""

    result = capabilities.build(
        model, condition_id, action_token,
        param_choices=param_choices, rule_name=rule_name,
    )
    if not getattr(result, "available", False):
        return {"success": False, "action": "create_action_rule",
                "error": getattr(result, "error", None)
                or "The rule cannot be built for this device."}

    ctx = get_context()
    executor = ctx.executors.get("vapix")
    if executor is None:
        return {"success": False, "action": "create_action_rule",
                "error": "No VAPIX executor available."}
    device, creds = _resolve_device_and_creds(registry, device_id)
    try:
        out = await runner.create_rule(
            catalog=ctx.catalog, executor=executor, device=device, creds=creds,
            config_body=result.config_body, rule_body=result.rule_body,
        )
    except RuleRunnerError as exc:
        return {"success": False, "action": "create_action_rule",
                "error": str(exc), "steps": exc.steps}

    # ADR-0050 Phase B: correlate the rule with a demo (membership + auto-signal
    # from its condition topic). Best-effort — a bookkeeping failure must never
    # falsify the successful rule creation.
    demo_id = action.get("demo_id")
    if demo_id and out.get("rule_id"):
        try:
            from admz.demos import actions as _da
            demo = ctx.demo_store.get(demo_id)
            if demo is not None:
                _da.attach_rule_to_demo(ctx, demo, {
                    "device_id": device_id, "rule_id": out.get("rule_id"),
                    "rule_name": rule_name, "condition_id": condition_id,
                    "condition_topic": action.get("condition_topic"),
                })
        except Exception:  # noqa: BLE001
            logger.warning("attach_rule_to_demo failed for %s", demo_id, exc_info=True)

    return {
        "success": True, "action": "create_action_rule", "device_id": device_id,
        "rule_id": out.get("rule_id"), "config_id": out.get("config_id"),
        "rule_name": rule_name,
        "message": (f"Rule '{rule_name}' created on {device_id} "
                    f"(rule id {out.get('rule_id')})."),
    }


async def _action_delete_action_rule(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved delete-action-rule: remove the rule (and its linked config)."""
    from admz.api.context import get_context
    from admz.rules import runner
    from admz.rules.runner import RuleRunnerError

    device_id = action.get("device_id") or ""
    rule_id = str(action.get("rule_id") or "")
    if not registry.device_exists(device_id):
        return {"success": False, "action": "delete_action_rule",
                "error": f"Device not found: {device_id}"}
    ctx = get_context()
    executor = ctx.executors.get("vapix")
    if executor is None:
        return {"success": False, "action": "delete_action_rule",
                "error": "No VAPIX executor available."}
    device, creds = _resolve_device_and_creds(registry, device_id)
    try:
        out = await runner.delete_rule(
            catalog=ctx.catalog, executor=executor, device=device, creds=creds,
            rule_id=rule_id,
        )
    except RuleRunnerError as exc:
        return {"success": False, "action": "delete_action_rule",
                "error": str(exc), "steps": exc.steps}

    # ADR-0050 Phase B: drop this rule's demo membership (reverse-scan). Best-effort.
    try:
        from admz.demos import actions as _da
        _da.detach_rule_from_demo(ctx, rule_id, device_id)
    except Exception:  # noqa: BLE001
        logger.warning("detach_rule_from_demo failed for rule %s", rule_id, exc_info=True)

    return {
        "success": True, "action": "delete_action_rule", "device_id": device_id,
        **out,
        "message": (f"Rule {rule_id} removed from {device_id}"
                    + (f" (config {out.get('removed_config')} also removed)."
                       if out.get("removed_config") else ".")),
    }


async def _action_set_event_ingest(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved set-event-ingest (ADR-0050 Phase C): flip the fleet capture flag
    and start/stop + reconcile the WS supervisor in the web process — mirrors
    ``POST /api/events/control``. Ingest is prompted, never auto (user decision)."""
    from admz import capabilities
    from admz.api.context import get_context

    enabled = bool(action.get("enabled"))
    # #164: through the sanctioned writer, not `fleet_settings.set` directly.
    # This caller is ALREADY approved, and needs no bypass token to say so —
    # `set_enabled` sits BELOW the approval boundary (it audits and enforces
    # toggleability; the reveal ceremony lives in the route), so an approved
    # caller simply uses it. That is the structural difference from ADR-0059,
    # where the proposed chokepoint IS the gate and an approved caller would
    # re-trigger it.
    capabilities.set_enabled(
        "events.device_ingest", enabled,
        action.get("_confirmed_by") or "confirm-widget",
        reason="approved via the confirmation widget",
    )
    try:
        ctx = get_context()
        if enabled:
            await ctx.event_supervisor.start()
            await ctx.event_supervisor.reconcile()
        else:
            await ctx.event_supervisor.stop()
    except Exception as exc:  # noqa: BLE001 — flag is set; supervisor best-effort
        return {"success": False, "action": "set_event_ingest",
                "error": f"flag set, but supervisor did not (re)start cleanly: {exc}"}
    return {
        "success": True, "action": "set_event_ingest", "enabled": enabled,
        "message": (f"Event capture is now {'ON' if enabled else 'OFF'}. "
                    + ("Watched-device streams (re)started."
                       if enabled else "Streams stopped.")),
    }


#: The device operation a temp credential actually performs. Named here so the
#: gate and the executor cannot drift onto different operations.
TEMP_CREDENTIAL_OP = "pwdgrp.cgi:add-user"

#: The operation a firmware import STAGES FOR. The import itself touches no
#: device — it copies bytes into the directory ``executor/vapix.py``'s
#: ``_upload_path_allowed`` vouches for, and the executor will later upload
#: whatever is in there with no content check. So an import is in effect a
#: pre-authorisation of that upload, and inherits its classification rather
#: than asserting a second opinion about how risky it is (#188, #313's shape).
FIRMWARE_IMPORT_STAGES_FOR = "firmwaremanagement.cgi:upgrade"


async def _action_import_firmware(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved copy of caller-named files into the firmware cache (#188).

    Runs after a human approves the widget. Pure filesystem work with no
    per-process state, so it is safe in whichever process consumes the session.
    """
    from admz.firmware.downloader import import_firmware_files

    directory = str(action.get("directory") or "")
    if not directory:
        return {"success": False, "action": "import_firmware",
                "error": "directory is required"}

    result = await import_firmware_files(directory)
    return {
        "success": True, "action": "import_firmware", "directory": directory,
        "imported": [{"source": s, "cached_at": d} for s, d in result.imported],
        "skipped": [{"source": s, "reason": r} for s, r in result.skipped],
        "errors": [{"source": s, "error": e} for s, e in result.errors],
        "summary": (f"Imported {len(result.imported)}, "
                    f"skipped {len(result.skipped)}, "
                    f"errors {len(result.errors)}"),
    }

#: permissions → VAPIX group mapping. Mirrors the MCP tool's table; kept beside
#: the executor because this is now where the account is created.
_TEMP_PERM_MAP = {
    "admin": {"group": "root", "sgrp": "admin:operator:viewer:ptz"},
    "operator": {"group": "users", "sgrp": "operator:viewer:ptz"},
    "viewer": {"group": "users", "sgrp": "viewer"},
}


async def _action_create_temp_credentials(
    action: Mapping[str, Any], registry: Any, git_repo: Any = None,
) -> Dict[str, Any]:
    """Approved creation of a short-lived device account (#313).

    Runs **after** a human approves the widget, in whichever process consumes
    the confirm session. That is only safe because #314 made the temp-credential
    record a shared SQLite store: while it was per-process memory, creating the
    account here would have registered it in a tracker the MCP process could
    never see, orphaning it on every use.

    The temp password is **generated here**, at execution time, and returned in
    the outcome. It is deliberately not part of the session payload, so no
    credential is written into ``confirm_sessions.action_json`` — the invariant
    #194/#276 exist to protect.
    """
    from admz.mcp.temp_credentials import TempCredential, TempCredentialManager
    from admz.provisioning import execute_on_host

    device_id = str(action.get("device_id") or "")
    permissions = str(action.get("permissions") or "")
    ttl = int(action.get("ttl_seconds") or 300)
    perm = _TEMP_PERM_MAP.get(permissions)
    if not device_id or perm is None:
        return {"success": False, "action": "create_temp_credentials",
                "error": f"invalid device_id/permissions ({permissions!r})"}

    from admz.api.context import get_context
    ctx = get_context()

    info = registry.get_device_info(device_id) or {}
    host = info.get("host") or info.get("ip_address")
    if not host:
        return {"success": False, "action": "create_temp_credentials",
                "error": f"Device '{device_id}' has no host/IP configured."}
    try:
        admin_creds = registry.get_credentials(device_id, "default")
    except Exception:  # noqa: BLE001
        return {"success": False, "action": "create_temp_credentials",
                "error": f"No admin credentials stored for '{device_id}'."}

    mgr = TempCredentialManager()
    username = mgr.generate_username()
    password = mgr.generate_password()

    ok, error = await execute_on_host(
        ctx.catalog, ctx.executors, host, TEMP_CREDENTIAL_OP,
        {"user": username, "pwd": password, "grp": perm["group"],
         "sgrp": perm["sgrp"], "comment": "ADMZ temp account"},
        credentials=admin_creds,
    )
    if not ok:
        return {"success": False, "action": "create_temp_credentials",
                "error": f"Failed to create temp user on device: {error}"}

    cred = TempCredential(
        device_id=device_id, username=username, password=password,
        group=perm["group"], ttl_seconds=ttl,
    )
    # Register BEFORE returning. If this raised, the account would exist with
    # no record — the #314 failure, reintroduced at a new site.
    mgr.register(cred)

    return {
        "success": True, "action": "create_temp_credentials",
        "device_id": device_id, "username": username, "password": password,
        "permissions": permissions, "ttl_seconds": ttl,
        "expires_at": cred.expires_at_iso,
    }


_ACTION_EXECUTORS = {
    "accept_baseline": _action_accept_baseline,
    "delete_device": _action_delete_device,
    "set_event_ingest": _action_set_event_ingest,
    "create_task": _action_create_task,
    "update_task": _action_update_task,
    "delete_task": _action_delete_task,
    "create_action_rule": _action_create_action_rule,
    "delete_action_rule": _action_delete_action_rule,
    # ADR-0047: the drift-affecting demo writes (capture + adopt re-label what
    # counts as drift, so LLM/api-key callers hold them for the widget).
    "assign_demo_fragment": _action_assign_demo_fragment,
    "adopt_demo": _action_adopt_demo,
    # #199: discovery-driven provisioning. A scan chooses the device set, so
    # the operator approves a blast radius rather than a device.
    "start_demo_survey": _action_start_demo_survey,
    "register_discovered_device": _action_register_discovered_device,
    # #313: creating a device account through create_temp_credentials bypassed
    # the confirmation gate entirely — the catalog risk_level was never
    # consulted on that path, so #165's reclassification did not reach it.
    "create_temp_credentials": _action_create_temp_credentials,
    # #188: copying files into the firmware cache is a write into the trusted
    # side of _upload_path_allowed's boundary, so it takes the widget.
    "import_firmware": _action_import_firmware,
}


def create_action_session(
    *,
    action: str,
    device_id: str,
    payload: Mapping[str, Any],
    reason: str,
    store: Any = None,
    operator_configurable: bool = False,
    risk: str = "service-affecting",
) -> Any:
    """Create a confirm session holding a registry-level action.

    ``risk`` lets a caller hand in a classification it read from the **catalog**
    rather than accepting this default, so a gate can inherit the same
    risk_level the generic execution path would apply to the same device
    operation instead of asserting a second, parallel opinion (#313). Callers
    that do not pass it keep the historical ``service-affecting``, so nothing
    that existed before changes.

    ``url_only`` by default, regardless of fleet overrides — the whole point of
    ADR-0034 is that every destructive action takes the deterministic
    human/widget path (parity with how reboots are approved). ADR-0034:60-62
    states that pin explicitly ("fleet-level overrides do not soften actions").

    ``operator_configurable=True`` resolves the level through the normal
    ``service-affecting`` row of :data:`confirm_policy._DEFAULT_CONFIRMATION_LEVELS`
    instead, so ``/confirm-settings`` can raise *or lower* it like any other
    risk class. The risk class is unchanged either way — this selects how the
    level is *resolved*, it does not invent a level or a second table.

    That opt-out exists because an operator decision can ask for it, which is
    the case for survey/discovery provisioning (#199): the operator's judgement
    was "a click is proportionate, requiring the confirmation password by
    default is not — but let me change my mind in the UI". Everything that does
    not pass the flag keeps ADR-0034's pin, so this widens nothing by default.
    """
    if action not in _ACTION_EXECUTORS:
        raise ValueError(f"Unknown action: {action}")
    store = _resolve_store(store)
    return store.create_session(
        device_id=device_id,
        operation_id=f"action:{action}",
        family="admz",
        params={},
        risk_level=risk,
        confirmation_level=(resolve_confirmation(risk) if operator_configurable
                            else "url_only"),
        danger_description=reason,
        action_json=json.dumps({"action": action, **dict(payload)}),
        ttl=CONFIRM_TOKEN_TTL_SECONDS,
    )


async def execute_approved_session(
    session: ConfirmSession,
    *,
    catalog: Any,
    registry: Any,
    executors: Mapping[str, Any],
    plan_engine: Any = None,
    git_repo: Any = None,
    secret_values: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Run the op/plan/action held by an ALREADY-completed confirm session.

    The web form (``/confirm/{token}``) and the in-chat approval twin verify
    the password and complete the session themselves, then call this to
    actually perform the approved work — closing the gap where ``url_*`` ops
    were marked approved but never executed. Returns a normalized outcome dict.

    ``secret_values`` (#334): values for ``session.secret_fields``, submitted
    on the approval page and merged into ``params`` here — never persisted,
    never logged, held only in this call's local scope. Refuses (rather than
    executing with the field silently omitted or guessed at) if any
    ``secret_fields`` name is absent from ``secret_values`` or empty — what a
    device does with a credential-shaped VAPIX param it wasn't given is not
    something to find out by sending the request anyway.
    """
    if session.is_action:
        action = dict(session.action)
        # Who clicked approve — task creations record it as approved_by.
        action["_confirmed_by"] = session.confirmed_by
        # The confirm token, so a rule action can find its out-of-band captured
        # recipient secret (held in web-process memory keyed by this token).
        action["_token"] = session.token
        executor = _ACTION_EXECUTORS.get(action.get("action", ""))
        if executor is None:
            return {
                "success": False,
                "error": f"Unknown action in session: {action.get('action')!r}",
            }
        # ADR-0059: everything the approved action does runs inside the
        # approved context, so a chokepoint gate downstream can tell "the
        # operator already said yes to this" from "a fresh call arrived".
        # Unused until the gate lands (slice 2) — this slice only establishes
        # the marker, so behaviour here is unchanged.
        #
        # The context manager resets in `finally`, and this `try/except` sits
        # INSIDE it: an executor that raises still unwinds the token. A test
        # asserts exactly that, because the failure mode is silent.
        try:
            with approved(str(action.get("action") or "")):
                outcome = executor(action, registry, git_repo=git_repo)
                if inspect.isawaitable(outcome):
                    outcome = await outcome  # device-touching actions (rules) are async
                return outcome
        except Exception as exc:  # noqa: BLE001 — surface, don't crash the route
            return {
                "success": False,
                "action": action.get("action"),
                "error": f"{type(exc).__name__}: {exc}",
            }

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

    # #334: merge the operator-supplied secret values back in — never
    # persisted, this dict lives only for the remainder of this call.
    exec_params = session.params
    if session.secret_fields:
        supplied = secret_values or {}
        missing = [f for f in session.secret_fields if not supplied.get(f)]
        if missing:
            return {
                "success": False,
                "error": (
                    f"{', '.join(missing)} was not supplied — this operation "
                    "cannot run without it. Nothing was sent to the device."
                ),
            }
        exec_params = {**session.params,
                       **{f: supplied[f] for f in session.secret_fields}}

    try:
        result = await run_execution_tail(
            device_id=session.device_id,
            operation_id=session.operation_id,
            family=session.family,
            params=exec_params,
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
