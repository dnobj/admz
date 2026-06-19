"""Unified task-action handler registry (ADR-0037).

One registry keyed by ``action_type`` (snapshot / drift_audit / survey /
reprovision) replaces the two it grew out of: the scheduler's
``register_job_handler`` and the pending-store's ``register_pending_handler``.

A handler is ``async (task: Task, ctx: TaskContext) -> dict``. ``TaskContext`` is a
superset of the old ``JobContext`` (it also carries ``registry`` / ``catalog`` /
``executors`` for device-mutating actions like reprovision), so the schedule
handlers port unchanged. Both evaluators — the scheduler interval loop and the
health-monitor sweep — dispatch through :func:`execute_task_action`.

``set_task_context`` is called once at app startup (the way
``register_recovery_handlers`` was) so the detection side can resolve deps it
doesn't hold locally; the scheduler passes its own context explicitly.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from admz.tasks.store import Task

logger = logging.getLogger(__name__)


@dataclass
class TaskContext:
    """Dependencies handed to task handlers. A superset of the old ``JobContext``
    (snapshot_engine + drift_detector) plus the registry/catalog/executors that
    device-mutating detection actions need."""

    snapshot_engine: Any = None
    drift_detector: Any = None
    registry: Any = None
    catalog: Any = None
    executors: Any = None


TaskHandler = Callable[["Task", "TaskContext"], Awaitable[Dict[str, Any]]]

_HANDLERS: Dict[str, TaskHandler] = {}
_CONTEXT: Optional[TaskContext] = None


def register_task_handler(action_type: str) -> Callable[[TaskHandler], TaskHandler]:
    """Decorator: register an async handler for an ``action_type``."""

    def _wrap(fn: TaskHandler) -> TaskHandler:
        _HANDLERS[action_type] = fn
        return fn

    return _wrap


def get_task_handler(action_type: str) -> Optional[TaskHandler]:
    return _HANDLERS.get(action_type)


def list_action_types() -> List[str]:
    return sorted(_HANDLERS)


def set_task_context(ctx: TaskContext) -> None:
    """Install the default context (from Components) used when an evaluator
    dispatches without passing one — the detection side relies on this."""
    global _CONTEXT
    _CONTEXT = ctx


def get_task_context() -> Optional[TaskContext]:
    return _CONTEXT


async def execute_task_action(
    task: Task, ctx: Optional[TaskContext] = None
) -> Dict[str, Any]:
    """Dispatch a task to its registered handler. ``ctx`` falls back to the
    startup-installed default. Raises ``ValueError`` if no handler is registered;
    propagates the handler's own exception on failure (the caller records it)."""
    handler = _HANDLERS.get(task.action_type)
    if handler is None:
        raise ValueError(
            f"no handler registered for action {task.action_type!r}; "
            f"registered: {list_action_types()}"
        )
    return await handler(task, ctx or _CONTEXT or TaskContext())


def default_summary(result: Dict[str, Any]) -> str:
    """Fallback ``last_result`` string when a handler omits ``summary``."""
    if not result.get("success", True):
        return f"error: {result.get('error', 'unknown')}"
    return result.get("summary") or "completed"


# ---------------------------------------------------------------------------
# Built-in handlers (moved from snapshot/scheduler.py + recovery_actions.py)
# ---------------------------------------------------------------------------


@register_task_handler("snapshot")
async def _run_snapshot(task: Task, ctx: TaskContext) -> Dict[str, Any]:
    """Snapshot the task's scope (FR-SCH-010). Unchanged behavior."""
    if ctx.snapshot_engine is None:
        return {"success": False, "error": "no snapshot_engine",
                "summary": "error: snapshot_engine missing"}
    snapshots = await ctx.snapshot_engine.snapshot_fleet(
        device_ids=task.device_ids,
        tag_filter=task.tag_filter,
        message=f"Scheduled: {task.description}",
    )
    succeeded = sum(1 for s in snapshots if s.succeeded_facets)
    failed = sum(
        1 for s in snapshots if s.failed_facets and not s.succeeded_facets
    )
    summary = (
        f"{succeeded} succeeded, {failed} failed" if failed
        else f"{succeeded} succeeded"
    )
    return {"success": True, "devices_snapshot": len(snapshots),
            "succeeded": succeeded, "failed": failed, "summary": summary}


@register_task_handler("drift_audit")
async def _run_drift_audit(task: Task, ctx: TaskContext) -> Dict[str, Any]:
    """Scheduled configuration audit over the task scope (FR-SCH-011)."""
    if ctx.drift_detector is None:
        return {"success": False, "error": "no drift_detector",
                "summary": "error: drift_detector missing"}
    reports = await ctx.drift_detector.check_fleet_drift(tag_filter=task.tag_filter)
    # KL-DRF-004 — count the alert transitions the detector recorded this sweep.
    new_alerts = [
        r.alert_transition for r in reports if getattr(r, "alert_transition", None)
    ]
    drifted = sum(1 for r in reports if r.has_drift)
    clean = len(reports) - drifted
    transitions = {"appeared": 0, "changed": 0, "cleared": 0}
    for t in new_alerts:
        transitions[t] = transitions.get(t, 0) + 1
    summary = (
        f"checked {len(reports)} device(s): {drifted} drifted / {clean} clean, "
        f"{len(new_alerts)} new alert(s) "
        f"({transitions['appeared']}↑ {transitions['changed']}↔ "
        f"{transitions['cleared']}↓)"
    )
    return {"success": True, "checked": len(reports), "drifted": drifted,
            "clean": clean, "new_alerts": len(new_alerts),
            "transitions": transitions, "summary": summary}


@register_task_handler("survey")
async def _run_survey(task: Task, ctx: TaskContext) -> Dict[str, Any]:
    """Scheduled survey/contributor run (read-only). Gated by survey_mode_enabled;
    the collector is synchronous so it runs in a worker thread."""
    from admz.survey.runner import run_survey

    report = await asyncio.to_thread(
        run_survey, submit=True, device_ids=task.device_ids
    )
    d = report.to_dict()
    d["success"] = report.status not in ("error",)
    d["summary"] = f"survey: {report.status} — {report.message}"
    return d


@register_task_handler("reprovision")
async def _run_reprovision(task: Task, ctx: TaskContext) -> Dict[str, Any]:
    """Re-provision a factory-defaulted device — create the admin from the fleet
    default password (never logged/returned). Moved from recovery_actions.py;
    now reads deps from ``ctx`` instead of a startup closure."""
    from admz.provisioning import provision_factory_default

    device_id = task.device_id or (task.device_ids or [""])[0]
    if ctx.registry is None:
        raise RuntimeError("reprovision: task context has no registry")
    info = ctx.registry.get_device_info(device_id)
    host = info.get("host") or info.get("ip_address")
    if not host:
        raise ValueError(f"device {device_id} has no host to provision")
    result = await provision_factory_default(
        ctx.catalog, ctx.executors, ctx.registry,
        device_id=device_id, host=host,
        username=(task.action_params or {}).get("username", "root"),
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error") or "provision failed")
    logger.info("deferred reprovision succeeded for %s", device_id)
    return {"success": True, "summary": f"re-provisioned {device_id}"}
