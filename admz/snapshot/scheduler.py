import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SnapshotSchedule:
    """A scheduled job. Name kept for back-compat (existing
    ``schedules.json`` entries deserialise into this shape) but
    each row now carries a ``job_type`` so the scheduler can run
    snapshots, drift audits, and other recurring jobs through the
    same loop machinery. See ADR-0026 + FR-SCH-010..014.
    """

    id: str
    description: str
    interval_seconds: int
    # Snapshot-shaped scope (kept for back-compat + still meaningful
    # for drift_audit too). Hierarchy-aware fields will be added
    # under FR-SCH-012 once Slice 2 of the Org/Site/Group work lands.
    tag_filter: Optional[str] = None
    device_ids: Optional[List[str]] = None
    enabled: bool = True
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    last_result: Optional[str] = None
    # FR-SCH-010 — job_type drives handler-registry dispatch. Default
    # "snapshot" so legacy schedules.json entries migrate cleanly
    # (no operator action required, per ADR-0026's migration note).
    job_type: str = "snapshot"
    # Free-form job-type-specific knobs. drift_audit currently uses
    # no params; reserved for future handlers (cert-expiry, rotation,
    # etc.).
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["device_ids"] is None:
            del d["device_ids"]
        if d["tag_filter"] is None:
            del d["tag_filter"]
        # Drop params from the wire shape when empty so the file
        # stays uncluttered for the common snapshot case.
        if not d.get("params"):
            d.pop("params", None)
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SnapshotSchedule":
        # Migration (ADR-0026): legacy rows have no `job_type` field;
        # default to "snapshot" so pre-Phase-X persisted schedules
        # keep working.
        d = dict(d)
        d.setdefault("job_type", "snapshot")
        d.setdefault("params", {})
        return SnapshotSchedule(**{
            k: v for k, v in d.items()
            if k in SnapshotSchedule.__dataclass_fields__
        })

    @property
    def interval_human(self) -> str:
        s = self.interval_seconds
        if s < 60:
            return f"{s}s"
        if s < 3600:
            return f"{s // 60}m"
        if s < 86400:
            return f"{s // 3600}h"
        return f"{s // 86400}d"


# Back-compat alias. ADR-0026 calls this `ScheduledJob`; we expose
# both names so callers and tests can use whichever reads cleaner
# at the call site.
ScheduledJob = SnapshotSchedule


# ---------------------------------------------------------------------------
# Handler registry (FR-SCH-010)
# ---------------------------------------------------------------------------
#
# A `(job_type, async handler)` map. Handlers receive the live
# ``ScheduledJob`` plus a context bag the scheduler builds at
# construction time. Adding a new periodic capability means
# registering a new handler — not standing up a parallel scheduler
# (ADR-0026). The pattern mirrors ADR-0015 (pluggable facets) and
# ADR-0011 (pluggable backends).
JobHandler = Callable[
    ["SnapshotSchedule", "JobContext"], Awaitable[Dict[str, Any]],
]

_HANDLERS: Dict[str, JobHandler] = {}


def register_job_handler(job_type: str) -> Callable[[JobHandler], JobHandler]:
    """Decorator: register an async handler for a job_type.

    Production handlers register at import time. Tests can register
    additional handlers via the same decorator (no helper needed)
    and clean up by popping the key — see test_unified_scheduler.py.
    """

    def _wrap(fn: JobHandler) -> JobHandler:
        _HANDLERS[job_type] = fn
        return fn

    return _wrap


def get_job_handler(job_type: str) -> Optional[JobHandler]:
    """Public accessor — used by handlers that need to delegate
    (e.g. a composite handler that runs snapshot + drift in sequence)."""
    return _HANDLERS.get(job_type)


def list_job_types() -> List[str]:
    """Introspect registered handlers. Used by the REST/MCP
    schedule-create endpoints to validate the operator's choice."""
    return sorted(_HANDLERS)


@dataclass
class JobContext:
    """Bundle of dependencies handed to each job handler.

    Not the same as ``Components`` — handlers should depend on the
    narrow set they actually need so the bundle stays cohesive. If
    a handler needs something not here, add it (don't reach for a
    global)."""

    snapshot_engine: Any = None
    drift_detector: Any = None


INTERVAL_UNITS = {
    "s": 1,
    "sec": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
}


def parse_interval(text: str) -> int:
    text = text.strip().lower()
    for suffix, multiplier in sorted(
        INTERVAL_UNITS.items(), key=lambda x: -len(x[0])
    ):
        if text.endswith(suffix):
            num_part = text[: -len(suffix)].strip()
            try:
                return int(float(num_part) * multiplier)
            except ValueError:
                pass

    try:
        return int(text)
    except ValueError:
        raise ValueError(
            f"Cannot parse interval '{text}'. "
            "Use format like '30m', '2h', '1d', or seconds as integer."
        )


class SnapshotScheduler:

    def __init__(
        self,
        snapshot_engine,
        schedule_path: str,
        drift_detector=None,
    ):
        self.engine = snapshot_engine
        self.drift_detector = drift_detector
        self.schedule_path = Path(schedule_path)
        self.schedules: Dict[str, SnapshotSchedule] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        # KL-SCH-005 — per-job lock fixing the run_now ↔ interval-loop
        # race. Both call paths now go through ``_execute_schedule``,
        # which acquires the per-job lock before doing any work.
        self._job_locks: Dict[str, asyncio.Lock] = {}
        self._running = False

    # JobScheduler alias matches ADR-0026's preferred name.
    # Operators / contributors can use either at the call site.

    def _lock_for(self, schedule_id: str) -> asyncio.Lock:
        lock = self._job_locks.get(schedule_id)
        if lock is None:
            lock = asyncio.Lock()
            self._job_locks[schedule_id] = lock
        return lock

    def _job_context(self) -> JobContext:
        """Build the bundle of deps handlers expect. Constructed
        per execution so dynamic re-injection works in tests."""
        return JobContext(
            snapshot_engine=self.engine,
            drift_detector=self.drift_detector,
        )

    def add_schedule(self, schedule: SnapshotSchedule) -> SnapshotSchedule:
        now = datetime.now(timezone.utc)
        if not schedule.next_run:
            schedule.next_run = (
                now + timedelta(seconds=schedule.interval_seconds)
            ).isoformat()

        self.schedules[schedule.id] = schedule
        self._save()

        if self._running and schedule.enabled:
            self._start_task(schedule)

        return schedule

    def update_schedule(
        self, schedule_id: str, **kwargs
    ) -> Optional[SnapshotSchedule]:
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            return None

        for key, value in kwargs.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)

        if "interval_seconds" in kwargs:
            schedule.next_run = (
                datetime.now(timezone.utc)
                + timedelta(seconds=schedule.interval_seconds)
            ).isoformat()

        self._save()

        if self._running:
            self._cancel_task(schedule_id)
            if schedule.enabled:
                self._start_task(schedule)

        return schedule

    def remove_schedule(self, schedule_id: str) -> bool:
        self._cancel_task(schedule_id)
        if schedule_id in self.schedules:
            del self.schedules[schedule_id]
            self._save()
            return True
        return False

    def get_schedule(self, schedule_id: str) -> Optional[SnapshotSchedule]:
        return self.schedules.get(schedule_id)

    def list_schedules(self) -> List[SnapshotSchedule]:
        return list(self.schedules.values())

    async def start(self):
        self._load()
        self._running = True
        for schedule in self.schedules.values():
            if schedule.enabled:
                self._start_task(schedule)
        logger.info(
            "Scheduler started with %d schedule(s)",
            sum(1 for s in self.schedules.values() if s.enabled),
        )

    async def stop(self):
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        logger.info("Scheduler stopped")

    async def run_now(self, schedule_id: str) -> Dict[str, Any]:
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            return {"success": False, "error": f"Schedule not found: {schedule_id}"}
        return await self._execute_schedule(schedule)

    def _start_task(self, schedule: SnapshotSchedule):
        self._cancel_task(schedule.id)
        task = asyncio.create_task(self._schedule_loop(schedule))
        self._tasks[schedule.id] = task

    def _cancel_task(self, schedule_id: str):
        task = self._tasks.pop(schedule_id, None)
        if task and not task.done():
            task.cancel()

    async def _schedule_loop(self, schedule: SnapshotSchedule):
        try:
            while True:
                wait = self._seconds_until_next(schedule)
                if wait > 0:
                    await asyncio.sleep(wait)

                await self._execute_schedule(schedule)

                schedule.next_run = (
                    datetime.now(timezone.utc)
                    + timedelta(seconds=schedule.interval_seconds)
                ).isoformat()
                self._save()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Schedule loop %s crashed", schedule.id)

    async def _execute_schedule(
        self, schedule: SnapshotSchedule
    ) -> Dict[str, Any]:
        """FR-SCH-010 — dispatch through the handler registry.

        KL-SCH-005 — per-job lock prevents the ``run_now`` ↔
        interval-loop race for the same schedule. Both call paths
        funnel here.

        FR-SCH-013 — every execution writes one audit row attributed
        to the synthetic ``scheduler`` principal so automated runs
        are distinguishable from operator / anonymous traffic.
        """
        async with self._lock_for(schedule.id):
            handler = _HANDLERS.get(schedule.job_type)
            if handler is None:
                msg = (
                    f"No handler registered for job_type "
                    f"{schedule.job_type!r}. Registered: "
                    f"{list_job_types()}"
                )
                logger.error("Schedule %s: %s", schedule.id, msg)
                schedule.last_run = datetime.now(timezone.utc).isoformat()
                schedule.last_result = f"error: {msg}"
                self._save()
                self._audit_run(schedule, success=False, error=msg)
                return {
                    "success": False,
                    "schedule_id": schedule.id,
                    "error": msg,
                }

            logger.info(
                "Running scheduled job (%s): %s",
                schedule.job_type, schedule.id,
            )
            now = datetime.now(timezone.utc)
            ctx = self._job_context()
            try:
                result = await handler(schedule, ctx)
            except Exception as e:
                logger.exception(
                    "Schedule %s (%s) failed",
                    schedule.id, schedule.job_type,
                )
                schedule.last_run = now.isoformat()
                schedule.last_result = f"error: {e}"
                self._save()
                self._audit_run(schedule, success=False, error=str(e))
                return {
                    "success": False,
                    "schedule_id": schedule.id,
                    "job_type": schedule.job_type,
                    "error": str(e),
                }

            # Handler is expected to return a dict with at least
            # ``success`` + a human-readable ``summary``. We propagate
            # the full body so callers (run_now via REST/MCP) see
            # everything; we also persist the summary to last_result
            # so the next list_schedules call shows progress at a
            # glance.
            success = bool(result.get("success", True))
            summary = result.get("summary") or _default_summary(result)
            schedule.last_run = now.isoformat()
            schedule.last_result = summary
            self._save()
            self._audit_run(schedule, success=success, summary=summary)
            result.setdefault("schedule_id", schedule.id)
            result.setdefault("job_type", schedule.job_type)
            return result

    def _audit_run(
        self,
        schedule: SnapshotSchedule,
        *,
        success: bool,
        summary: str = "",
        error: str = "",
    ) -> None:
        """FR-SCH-013 — attribute every scheduled execution to the
        synthetic ``scheduler`` principal so the audit log
        distinguishes automated runs from operator + anonymous
        actions.
        """
        try:
            from admz import audit as _audit_mod
            _audit_mod.audit_log.record(
                requester="scheduler",
                auth_source="scheduler",
                action=f"scheduler.run.{schedule.job_type}",
                resource=f"schedule:{schedule.id}",
                details={
                    "interval_seconds": schedule.interval_seconds,
                    "tag_filter": schedule.tag_filter,
                    "device_ids": schedule.device_ids,
                    "summary": summary,
                },
                success=success,
                error_message=error,
            )
        except Exception:  # pragma: no cover — never let audit break a run
            logger.exception("scheduler audit row failed")

    def _seconds_until_next(self, schedule: SnapshotSchedule) -> float:
        if not schedule.next_run:
            return 0
        try:
            next_dt = datetime.fromisoformat(schedule.next_run)
            if next_dt.tzinfo is None:
                next_dt = next_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return max(0, (next_dt - now).total_seconds())
        except (ValueError, TypeError):
            return 0

    def _save(self):
        self.schedule_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            sid: s.to_dict() for sid, s in self.schedules.items()
        }
        with open(self.schedule_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        if not self.schedule_path.exists():
            return
        try:
            with open(self.schedule_path) as f:
                data = json.load(f)
            for sid, sdata in data.items():
                self.schedules[sid] = SnapshotSchedule.from_dict(sdata)
        except Exception:
            logger.exception("Failed to load schedules from %s", self.schedule_path)


# ---------------------------------------------------------------------------
# Built-in job handlers
# ---------------------------------------------------------------------------


def _default_summary(result: Dict[str, Any]) -> str:
    """Fallback ``last_result`` string when a handler omits ``summary``."""
    if not result.get("success", True):
        return f"error: {result.get('error', 'unknown')}"
    return "completed"


@register_job_handler("snapshot")
async def _run_snapshot_job(
    schedule: SnapshotSchedule, ctx: JobContext,
) -> Dict[str, Any]:
    """FR-SCH-010 — re-implements the previous hardcoded snapshot
    behavior as a registered handler. No semantic change."""
    if ctx.snapshot_engine is None:
        return {
            "success": False,
            "error": "scheduler not configured with snapshot_engine",
            "summary": "error: snapshot_engine missing",
        }
    snapshots = await ctx.snapshot_engine.snapshot_fleet(
        device_ids=schedule.device_ids,
        tag_filter=schedule.tag_filter,
        message=f"Scheduled: {schedule.description}",
    )
    succeeded = sum(1 for s in snapshots if s.succeeded_facets)
    failed = sum(
        1 for s in snapshots if s.failed_facets and not s.succeeded_facets
    )
    summary = (
        f"{succeeded} succeeded, {failed} failed"
        if failed
        else f"{succeeded} succeeded"
    )
    return {
        "success": True,
        "devices_snapshot": len(snapshots),
        "succeeded": succeeded,
        "failed": failed,
        "summary": summary,
    }


@register_job_handler("drift_audit")
async def _run_drift_audit_job(
    schedule: SnapshotSchedule, ctx: JobContext,
) -> Dict[str, Any]:
    """FR-SCH-011 — scheduled configuration audit.

    Runs ``DriftDetector.check_fleet_drift`` over the schedule's
    scope (``device_ids`` / ``tag_filter`` for now; hierarchy fields
    land under FR-SCH-012). Each report is passed through
    ``DriftAlertStore.process_report`` which emits an ``appeared`` /
    ``changed`` / ``cleared`` transition row when the device's
    drift state has actually changed since last check — the cron-
    spam-of-the-same-drift problem is handled there, not here.
    """
    if ctx.drift_detector is None:
        return {
            "success": False,
            "error": "scheduler not configured with drift_detector",
            "summary": "error: drift_detector missing",
        }

    reports = await ctx.drift_detector.check_fleet_drift(
        tag_filter=schedule.tag_filter,
    )

    # KL-DRF-004 — feed each report through the alert store. Devices
    # whose drift signature is unchanged emit no alert; new drift,
    # changed drift, and cleared drift each emit one row.
    from admz.snapshot import drift_alerts as _da_mod
    new_alerts = []
    for report in reports:
        alert = _da_mod.drift_alerts.process_report(report)
        if alert is not None:
            new_alerts.append(alert)

    drifted = sum(1 for r in reports if r.has_drift)
    clean = len(reports) - drifted
    transitions = {
        "appeared": 0, "changed": 0, "cleared": 0,
    }
    for a in new_alerts:
        transitions[a.transition] = transitions.get(a.transition, 0) + 1
    summary = (
        f"checked {len(reports)} device(s): "
        f"{drifted} drifted / {clean} clean, "
        f"{len(new_alerts)} new alert(s) "
        f"({transitions['appeared']}↑ {transitions['changed']}↔ "
        f"{transitions['cleared']}↓)"
    )

    return {
        "success": True,
        "checked": len(reports),
        "drifted": drifted,
        "clean": clean,
        "new_alerts": len(new_alerts),
        "transitions": transitions,
        "summary": summary,
    }
