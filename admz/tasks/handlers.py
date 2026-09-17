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
    from admz.notices.producers import SOURCE_DRIFT_AUDIT, notice_provenance

    # ADR-0071 §2: notices this sweep raises name the audit and this task;
    # `notify_console: false` keeps a quiet cadence from raising any.
    notify_console = (task.action_params or {}).get("notify_console", True)
    if isinstance(notify_console, str):
        notify_console = notify_console.strip().lower() not in ("0", "false", "no", "off")
    with notice_provenance(SOURCE_DRIFT_AUDIT, task_id=task.id,
                           notify_console=bool(notify_console)):
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
    # ADR-0063: say what the sweep did NOT read, and why. Facet reads skipped
    # because the device is known to lack the API are working as intended;
    # unverified facets are reads that failed. Appended only when non-zero so
    # the common all-clear summary reads as it always has.
    skipped = sum(
        1 for r in reports
        for status in getattr(r, "facet_status", {}).values()
        if status == "skipped"
    )
    unverified = sum(
        len(getattr(r, "facets_unverified", []) or []) for r in reports
    )
    if skipped or unverified:
        summary += (
            f", {skipped} facet(s) skipped as unsupported"
            f", {unverified} unverified"
        )
    return {"success": True, "checked": len(reports), "drifted": drifted,
            "clean": clean, "new_alerts": len(new_alerts),
            "transitions": transitions, "facet_reads_skipped": skipped,
            "facets_unverified": unverified, "summary": summary}


@register_task_handler("capability_survey")
async def _run_capability_survey(task: Task, ctx: TaskContext) -> Dict[str, Any]:
    """ADR-0063 / FR-KNW-012: enumerate device APIs via each device's own
    ``getApiList`` and record POSITIVES into the local capability store.
    Runs for every install — this is the survey-for-everyone half; pushing
    anything to the atlas stays behind ``survey.contributor`` and is a
    different task type (``survey``). Two shapes: a one-shot detection task
    (firmware changed / onboarding) carries its device; the recurring
    schedule sweeps the fleet."""
    from admz.device_capabilities import run_capability_survey

    registry = ctx.registry or getattr(ctx.snapshot_engine, "registry", None)
    catalog = ctx.catalog or getattr(ctx.snapshot_engine, "catalog", None)
    executors = ctx.executors or getattr(ctx.snapshot_engine, "executors", None)
    if registry is None or catalog is None or executors is None:
        return {"success": False, "error": "no registry/catalog/executors",
                "summary": "error: capability survey context incomplete"}

    if task.device_ids:
        device_ids = list(task.device_ids)
    elif task.device_id:
        device_ids = [task.device_id]
    else:
        device_ids = [
            d.get("device_id", d.get("id", "")) for d in registry.list_devices()
        ]

    surveyed = failed = apis = 0
    last_error = ""
    for did in device_ids:
        if not did:
            continue
        result = await run_capability_survey(
            device_id=did, registry=registry, catalog=catalog,
            executors=executors,
        )
        if result.get("success"):
            surveyed += 1
            apis += int(result.get("recorded") or 0)
        else:
            failed += 1
            last_error = str(result.get("error") or "")
    summary = f"surveyed {surveyed} device(s): {apis} API positive(s) recorded"
    if failed:
        summary += f", {failed} device(s) failed"
    # A one-shot detection task exists to survey ITS device: if that failed,
    # the task failed — returning success would consume the trigger silently
    # (#455 review, MAJOR-1; the device is commonly mid-reboot right after
    # the firmware change that queued us). The recurring fleet sweep stays
    # success-with-counts: a schedule is not failed by one device's bad hour.
    single_device_failed = (
        task.trigger_kind == "detection" and surveyed == 0 and failed > 0
    )
    return {"success": not single_device_failed,
            "surveyed": surveyed, "failed": failed,
            "apis_recorded": apis, "summary": summary,
            "error": last_error if single_device_failed else None}


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
    layer 3). It raises a Console notice (ADR-0071 §2), keyed per task and
    device, so repeated firings bump one row; the audit row the evaluator
    writes on every firing stays the durable record. A store failure is a
    failure (#455), never a silent success."""
    from admz.notices.producers import event_notice

    msg = (task.action_params or {}).get("message") or task.description or "event detected"
    try:
        notice = event_notice(task, str(msg))
    except Exception as exc:  # noqa: BLE001 — reported, not swallowed
        logger.warning("notify: could not raise a notice for %s: %s", task.id, exc)
        return {"success": False, "error": f"notice not raised: {exc}",
                "summary": f"notify failed: {exc}"}
    return {"success": True, "notice_id": notice.id,
            "summary": f"notify: {msg} (notice #{notice.id})"}


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
    """Deferred re-provision of a factory-defaulted device — ADR-0037's
    ``reprovision`` detection task, which since ADR-0068 is refused rather than
    performed (below). Moved from recovery_actions.py; now reads deps from
    ``ctx`` instead of a startup closure.

    ``attended=False`` (ADR-0068) — **this handler no longer provisions.** It
    reports a refusal instead, and that is the point rather than a regression.

    Since ADR-0068 provisioning writes the fleet **break-glass** root password
    — one value, shared across every device ADMZ provisions, known to the
    operator by design. This handler fires unattended, on the health sweep's
    schedule, up to 24h after an operator approved the task, against whatever
    host answers at the device's registered address *at that later moment*. The
    trigger (``needsetup=yes``) is itself an unauthenticated device response and
    nothing on this path re-verifies the peer (#185; #326 for the residual). So
    a spoofed peer — a reassigned DHCP lease, ARP spoofing, the port a
    decommissioned camera vacated — would walk away with a credential valid on
    every device ADMZ has provisioned. That is a fleet-wide credential handed to
    whoever answered, which is categorically worse than the per-device generated
    password this path used to write.

    The previous answer was ``allow_fleet_default=False``: opt out of the shared
    secret and generate per device. ADR-0068 removes that flag, because the root
    password now has its own setting — and removing it *without* this refusal
    would have made this handler silently START sending the shared value, which
    is the exposure the ADR exists to prevent. The refusal is therefore
    structural, not a comment.

    **Deferring to an attended flow is what this file already recommended** as
    the honest fix for #185/#326, alongside real peer identity (unverified as
    buildable today). This is that deferral. The visible cost: a factory-
    defaulted device that appears while nobody is watching stays
    ``needs_setup`` until an operator onboards it, where before it would have
    been provisioned with a password only ADMZ held.
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
        attended=False,
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error") or "provision failed")
    logger.info("deferred reprovision succeeded for %s", device_id)
    # Carry the SOURCE forward, never the password (GH #326). `provisioning`
    # already distinguishes provided / fleet_default / generated, and this
    # handler was dropping it on the floor — so the audit row for a fired
    # reprovision could not say which mode produced the credential it just
    # created. That is the forensic question #326's phantom-provision gap makes
    # worth answering: an operator looking at a suspect provision needs to know
    # what was set, and the alternative is inferring it from the code path that
    # was live at the time.
    return {
        "success": True,
        "summary": f"re-provisioned {device_id}",
        "password_source": result.get("password_source"),
    }
