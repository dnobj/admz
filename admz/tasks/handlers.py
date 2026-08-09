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
#: Action types installed from a module, so a re-install can tell "refresh my
#: own handler" from "collide with a built-in" (GH #172).
_MODULE_INSTALLED: set = set()
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


def install_module_task_handlers(module_registry: Any) -> int:
    """Merge every module's ``task_handlers()`` into the registry (GH #172).

    ``contract.py`` lists ``task_handlers()`` among the seven factories *"the
    platform calls … and merges"*, present tense, and
    ``ModuleRegistry.task_handlers_all`` implements the merge — but nothing
    invoked it. Six of the seven merges are wired; this was the only orphan. So
    a module implementing the documented contract had its handlers **silently
    dropped**, surfacing much later and far from the cause as
    ``ValueError: no handler registered for action …`` from
    :func:`execute_task_action`.

    Returns how many were installed.

    **A module may not replace a built-in.** The built-ins register at import
    via ``@register_task_handler``, so an override here would be a module
    quietly taking over ``snapshot`` or ``reprovision`` for the whole fleet —
    load-order-dependent and invisible. Refused and logged; the module's other
    handlers still install.

    This is a guard against accident, **not a boundary**: ``register_task_handler``
    is public and unconditional, so a module that calls it directly at import
    still wins. Making that impossible means giving registration an ownership
    model, which is a larger change than #172 and is not attempted here.

    Re-running (a second lifespan, a reload, a test) is a no-op for identical
    handlers and a **refresh** for changed ones — a module's own previous
    installation is not a built-in and must not be reported as one.
    """
    installed = 0
    for action_type, handler in (module_registry.task_handlers_all() or {}).items():
        existing = _HANDLERS.get(action_type)
        if existing is handler:
            continue          # same install re-run (a second lifespan): no-op
        if action_type in _MODULE_INSTALLED:
            # A module handler we installed before, now different: this is a
            # refresh, not an override. Refusing it would pin the *stale*
            # callable — and report it as a built-in clash, which it is not.
            _HANDLERS[action_type] = handler
            installed += 1
            continue
        if existing is not None:
            logger.warning(
                "module task handler for %r refused: %r is already registered "
                "as a built-in, and modules may not replace built-ins",
                action_type, action_type)
            continue
        _HANDLERS[action_type] = handler
        _MODULE_INSTALLED.add(action_type)
        installed += 1
    if installed:
        logger.info("installed %d module task handler(s)", installed)
    return installed


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


@register_task_handler("notify")
async def _run_notify(task: Task, ctx: TaskContext) -> Dict[str, Any]:
    """A safe 'flag this happened' action for event-pattern detections (ADR-0041
    layer 3). The durable record is the audit row the evaluator writes on every
    firing; this just carries the operator's message (and is the seam for a future
    webhook/email)."""
    msg = (task.action_params or {}).get("message") or task.description or "event detected"
    return {"success": True, "summary": f"notify: {msg}"}


@register_task_handler("acs_action")
async def _run_acs_action(task: Task, ctx: TaskContext) -> Dict[str, Any]:
    """Fire an ACS Pro recording action on a camera when a detection matches.
    SERVICE-AFFECTING — runs without the interactive gate, so the evaluator only
    invokes it for a rule whose ``pre_authorized`` flag is set. Bypasses the gate
    intentionally (the authorization was captured at rule creation) but is audited."""
    from admz.modules.acs_pro.client import run_acs_op

    p = task.action_params or {}
    op = (p.get("acs_op") or "start_recording").lower()
    camera_id = p.get("camera_id")
    if not camera_id:
        return {"success": False, "error": "no camera_id", "summary": "error: acs_action missing camera_id"}
    op_ids = {"start_recording": "RecordingControlFacade:StartRecording",
              "stop_recording": "RecordingControlFacade:StopRecording",
              "bookmark": "BookmarkFacade:AddBookmark"}
    op_id = op_ids.get(op)
    if op_id is None:
        return {"success": False, "error": "bad acs_op", "summary": f"error: unknown acs_op {op!r}"}
    params: Dict[str, Any] = {"cameraId": {"Id": camera_id}}
    if op == "bookmark":
        import datetime
        params["time"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        params["name"] = p.get("name") or "ADMZ detection"
        params["description"] = p.get("description") or task.description or ""
    r = await run_acs_op(ctx.catalog, ctx.executors, op_id, params)
    ok = bool(r.get("success"))
    return {"success": ok, "status_code": r.get("status_code"),
            "summary": f"acs {op}: {'ok' if ok else (r.get('message') or 'failed')}"}


@register_task_handler("reprovision")
async def _run_reprovision(task: Task, ctx: TaskContext) -> Dict[str, Any]:
    """Re-provision a factory-defaulted device — create the admin account with
    a freshly generated, per-call password (never logged/returned). Moved from
    recovery_actions.py; now reads deps from ``ctx`` instead of a startup
    closure.

    ``allow_fleet_default=False`` (GH #185) — deliberate, not an oversight.
    This handler fires unattended, on the health sweep's schedule, up to 24h
    after an operator approved the task — against whatever host answers at
    the device's registered address *at that later moment*. The trigger
    (``needsetup=yes``) is itself an unauthenticated device response, and
    nothing on this path re-verifies the peer before firing (that's the whole
    of GH #185's investigation — no verifiable identity exists here; see the
    handoff for why). Sending the shared fleet-wide ``default_password`` to
    an unverified peer hands a fleet-wide credential to whoever answered.
    Sending a fresh generated one instead doesn't verify the peer either —
    nothing here can — but it makes who the peer turns out to be matter much
    less: see :func:`admz.provisioning.provision_factory_default`'s
    ``allow_fleet_default`` docstring for the full reasoning. The interactive
    ``provision_device`` MCP path is untouched — a human drives that write at
    the moment it happens, a different threat shape.

    **What this does NOT fix, on purpose — do not read a green test suite as
    "GH #185 closed":** ADMZ's registry still ends up believing it holds a
    working credential for a device it may never have actually contacted (the
    real device, still factory-default, was simply never reached), and *some*
    secret is still sent in cleartext to an unverified peer. Both need either
    real peer identity (unverified as buildable today) or deferring this
    action to an attended flow — a real trade, not a bug fix. Tracked as a
    separate, harder issue referencing #185 and this fix.
    """
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
        allow_fleet_default=False,
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error") or "provision failed")
    logger.info("deferred reprovision succeeded for %s", device_id)
    return {"success": True, "summary": f"re-provisioned {device_id}"}
