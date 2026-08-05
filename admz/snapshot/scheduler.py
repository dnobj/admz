"""Time-based task evaluator (ADR-0037, was the SnapshotScheduler).

Schedule tasks now live in the unified SQLite ``tasks`` store (``admz.tasks``),
not ``schedules.json`` — so the cross-process merge/reconcile hack is gone
(SQLite is the source of truth; a periodic re-query adopts tasks created by other
processes). This module keeps the interval-loop machinery + the ``SnapshotSchedule``
public API (so REST/MCP callers are unchanged) and dispatches through the unified
handler registry (``admz.tasks.handlers``).
"""

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# Importing handlers registers the built-in action handlers (snapshot /
# drift_audit / survey / reprovision) into the unified registry.
from admz.tasks import handlers as _task_handlers
from admz.tasks.handlers import (  # noqa: F401 — re-exported for back-compat
    TaskContext,
    execute_task_action,
    register_task_handler,
)
from admz.tasks.handlers import TaskContext as JobContext  # back-compat alias
from admz.tasks import store as _store_mod
from admz.tasks.store import TRIGGER_SCHEDULE, Task

logger = logging.getLogger(__name__)


@dataclass
class SnapshotSchedule:
    """Back-compat shape for the REST/MCP schedule surface. Converted to/from a
    unified :class:`admz.tasks.store.Task` at the scheduler boundary."""

    id: str
    description: str
    interval_seconds: int
    tag_filter: Optional[str] = None
    device_ids: Optional[List[str]] = None
    enabled: bool = True
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    last_result: Optional[str] = None
    job_type: str = "snapshot"
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["device_ids"] is None:
            del d["device_ids"]
        if d["tag_filter"] is None:
            del d["tag_filter"]
        if not d.get("params"):
            d.pop("params", None)
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SnapshotSchedule":
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


# Back-compat alias (ADR-0026 name).
ScheduledJob = SnapshotSchedule


def _to_task(s: SnapshotSchedule) -> Task:
    return Task(
        id=s.id,
        description=s.description or "",
        trigger_kind=TRIGGER_SCHEDULE,
        interval_seconds=s.interval_seconds,
        next_run=s.next_run,
        last_run=s.last_run,
        last_result=s.last_result,
        action_type=s.job_type or "snapshot",
        action_params=dict(s.params or {}),
        tag_filter=s.tag_filter,
        device_ids=s.device_ids,
        enabled=s.enabled,
        status="active",
    )


def _to_schedule(t: Task) -> SnapshotSchedule:
    return SnapshotSchedule(
        id=t.id,
        description=t.description,
        interval_seconds=t.interval_seconds,
        tag_filter=t.tag_filter,
        device_ids=t.device_ids,
        enabled=t.enabled,
        last_run=t.last_run,
        next_run=t.next_run,
        last_result=t.last_result,
        job_type=t.action_type,
        params=dict(t.action_params or {}),
    )


# ---------------------------------------------------------------------------
# Handler-registry back-compat shims (delegate to the unified registry)
# ---------------------------------------------------------------------------

def register_job_handler(job_type: str):
    """Back-compat alias for ``register_task_handler``."""
    return register_task_handler(job_type)


def get_job_handler(job_type: str):
    return _task_handlers.get_task_handler(job_type)


def list_job_types() -> List[str]:
    return _task_handlers.list_action_types()


INTERVAL_UNITS = {
    "s": 1, "sec": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
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


# How often the running scheduler re-queries the store to adopt/drop schedule
# tasks created/removed by another process (replaces the old disk reconcile).
_RECONCILE_INTERVAL_SECONDS = 30


class SnapshotScheduler:
    """Runs schedule tasks (from the unified store) on their intervals."""

    def __init__(self, snapshot_engine, schedule_path: str = "", drift_detector=None,
                 store=None):
        self.engine = snapshot_engine
        self.drift_detector = drift_detector
        # ``schedule_path`` retained for signature compatibility; storage is the
        # SQLite tasks store now (ADR-0037). Read the singleton at construction
        # so tests can monkeypatch ``admz.tasks.store.tasks_store``.
        self.store = store if store is not None else _store_mod.tasks_store
        self._tasks: Dict[str, asyncio.Task] = {}
        self._job_locks: Dict[str, asyncio.Lock] = {}
        self._running = False
        self._reconcile_task: Optional[asyncio.Task] = None

    def _ctx(self) -> TaskContext:
        return TaskContext(
            snapshot_engine=self.engine, drift_detector=self.drift_detector,
        )

    def _lock_for(self, task_id: str) -> asyncio.Lock:
        lock = self._job_locks.get(task_id)
        if lock is None:
            lock = asyncio.Lock()
            self._job_locks[task_id] = lock
        return lock

    # ----- CRUD (SnapshotSchedule in/out for back-compat) -----------------

    def add_schedule(self, schedule: SnapshotSchedule) -> SnapshotSchedule:
        if not schedule.next_run:
            schedule.next_run = (
                datetime.now(timezone.utc)
                + timedelta(seconds=schedule.interval_seconds)
            ).isoformat()
        self.store.upsert(_to_task(schedule))
        if self._running and schedule.enabled:
            self._start_task(schedule.id)
        return schedule

    def update_schedule(self, schedule_id: str, **kwargs) -> Optional[SnapshotSchedule]:
        task = self.store.get(schedule_id)
        if task is None or task.trigger_kind != TRIGGER_SCHEDULE:
            return None
        # Map SnapshotSchedule field names onto Task fields.
        if "job_type" in kwargs:
            task.action_type = kwargs.pop("job_type")
        if "params" in kwargs:
            task.action_params = kwargs.pop("params") or {}
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        if "interval_seconds" in kwargs:
            task.next_run = (
                datetime.now(timezone.utc)
                + timedelta(seconds=task.interval_seconds)
            ).isoformat()
        self.store.upsert(task)
        if self._running:
            self._cancel_task(schedule_id)
            if task.enabled:
                self._start_task(schedule_id)
        return _to_schedule(task)

    def remove_schedule(self, schedule_id: str) -> bool:
        self._cancel_task(schedule_id)
        return self.store.delete(schedule_id)

    def get_schedule(self, schedule_id: str) -> Optional[SnapshotSchedule]:
        task = self.store.get(schedule_id)
        if task is None or task.trigger_kind != TRIGGER_SCHEDULE:
            return None
        return _to_schedule(task)

    def list_schedules(self) -> List[SnapshotSchedule]:
        return [_to_schedule(t) for t in self.store.schedule_tasks()]

    # ----- lifecycle ------------------------------------------------------

    async def start(self):
        self._running = True
        for t in self.store.schedule_tasks(enabled_only=True):
            self._start_task(t.id)
        self._reconcile_task = asyncio.create_task(self._reconcile_loop())
        logger.info(
            "Scheduler started with %d schedule task(s)",
            len(self.store.schedule_tasks(enabled_only=True)),
        )

    async def stop(self):
        self._running = False
        if self._reconcile_task is not None:
            self._reconcile_task.cancel()
            self._reconcile_task = None
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        logger.info("Scheduler stopped")

    async def _reconcile_loop(self) -> None:
        """Adopt/drop schedule-task loops as the store changes (cross-process)."""
        try:
            while self._running:
                await asyncio.sleep(_RECONCILE_INTERVAL_SECONDS)
                if not self._running:
                    break
                try:
                    self._reconcile()
                except Exception:  # pragma: no cover
                    logger.exception("schedule reconcile failed")
        except asyncio.CancelledError:
            pass

    def _reconcile(self) -> None:
        want = {t.id for t in self.store.schedule_tasks(enabled_only=True)}
        have = set(self._tasks.keys())
        for sid in want - have:
            self._start_task(sid)
            logger.info("Adopted schedule task %s", sid)
        for sid in have - want:
            self._cancel_task(sid)
            logger.info("Dropped schedule task %s", sid)

    async def run_now(self, schedule_id: str, *,
                      allow_paused: bool = False) -> Dict[str, Any]:
        """Fire a schedule on demand (GH #156).

        ``enabled`` means **"do not run automatically"**, not "do not run at
        all". Three things in the code say so, and none of them is about
        on-demand runs: :meth:`update_schedule` cancels and restarts the
        *timer* and nothing else; FR-SCH-008 says a paused schedule is
        "skipped", which is what a loop does with its turn; and the UI toggle
        reads "Paused", a scheduler word. A maintenance window exists to stop
        *unattended* work, which is not what an operator deliberately pressing
        a button is doing.

        So a pause does not revoke an operator's ability to run the thing —
        but an on-demand fire still needs **someone to have expressed that
        override**, and only one caller has anyone who could. Hence
        ``allow_paused`` rather than a blanket ``and task.enabled``:

        * ``POST /api/tasks/{id}/run`` and ``POST /api/schedules/{id}/run``
          pass ``is_interactive(principal)``. A console operator clicking ▶ on
          a row labelled "Paused" *is* the expression of intent. Refusing them
          teaches un-pause → run → re-pause, and the last step is the one
          people forget — which leaves the schedule live, the opposite of what
          the refusal was protecting.
        * The MCP tool passes nothing. The model calling ``run_snapshot_schedule``
          has no way to mean "I know it is paused, do it anyway", because
          nobody expressed that. It gets the default.

        **Default False on purpose.** A caller added later is refused until it
        deliberately opts in, which is the failure direction ADR-0053 argues
        for: the mistake is silent otherwise, and this is exactly the class of
        gap #156 records — one path honouring a flag while three do not.
        """
        task = self.store.get(schedule_id)
        if task is None or task.trigger_kind != TRIGGER_SCHEDULE:
            return {"success": False, "error": f"Schedule not found: {schedule_id}"}
        if not task.enabled and not allow_paused:
            return {
                "success": False,
                "error": (
                    f"Schedule '{schedule_id}' is paused (enabled=false) and "
                    "was not run. Enable it first, or run it from the web "
                    "console, where an operator can override a pause "
                    "deliberately."
                ),
                "paused": True,
            }
        return await self._execute(task)

    # ----- loop + execution ----------------------------------------------

    def _start_task(self, task_id: str):
        self._cancel_task(task_id)
        self._tasks[task_id] = asyncio.create_task(self._schedule_loop(task_id))

    def _cancel_task(self, task_id: str):
        task = self._tasks.pop(task_id, None)
        if task and not task.done():
            task.cancel()

    async def _schedule_loop(self, task_id: str):
        try:
            while True:
                task = self.store.get(task_id)
                if task is None or task.trigger_kind != TRIGGER_SCHEDULE \
                        or not task.enabled:
                    return  # removed / disabled elsewhere → stop this loop
                wait = self._seconds_until_next(task)
                if wait > 0:
                    await asyncio.sleep(wait)
                task = self.store.get(task_id)  # re-read (may have changed)
                if task is None or not task.enabled:
                    return
                await self._execute(task)
                next_run = (
                    datetime.now(timezone.utc)
                    + timedelta(seconds=task.interval_seconds)
                ).isoformat()
                self.store.update(task_id, next_run=next_run)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Schedule loop %s crashed", task_id)

    async def _execute(self, task: Task) -> Dict[str, Any]:
        async with self._lock_for(task.id):
            now_iso = datetime.now(timezone.utc).isoformat()
            try:
                result = await execute_task_action(task, self._ctx())
            except ValueError as e:  # no handler registered
                msg = str(e)
                logger.error("Schedule %s: %s", task.id, msg)
                self.store.set_run_result(task.id, last_run=now_iso,
                                          last_result=f"error: {msg}")
                self._audit_run(task, success=False, error=msg)
                return {"success": False, "schedule_id": task.id, "error": msg}
            except Exception as e:
                logger.exception("Schedule %s (%s) failed", task.id, task.action_type)
                self.store.set_run_result(task.id, last_run=now_iso,
                                          last_result=f"error: {e}")
                self._audit_run(task, success=False, error=str(e))
                return {"success": False, "schedule_id": task.id,
                        "job_type": task.action_type, "error": str(e)}

            success = bool(result.get("success", True))
            summary = result.get("summary") or _task_handlers.default_summary(result)
            self.store.set_run_result(task.id, last_run=now_iso, last_result=summary)
            self._audit_run(task, success=success, summary=summary)
            result.setdefault("schedule_id", task.id)
            result.setdefault("job_type", task.action_type)
            return result

    def _audit_run(self, task: Task, *, success: bool, summary: str = "",
                   error: str = "") -> None:
        try:
            from admz import audit as _audit_mod
            _audit_mod.audit_log.record(
                requester="scheduler",
                auth_source="scheduler",
                action=f"scheduler.run.{task.action_type}",
                resource=f"schedule:{task.id}",
                details={
                    "interval_seconds": task.interval_seconds,
                    "tag_filter": task.tag_filter,
                    "device_ids": task.device_ids,
                    "summary": summary,
                },
                success=success,
                error_message=error,
            )
        except Exception:  # pragma: no cover
            logger.exception("scheduler audit row failed")

    def _seconds_until_next(self, task: Task) -> float:
        if not task.next_run:
            return 0
        try:
            next_dt = datetime.fromisoformat(task.next_run)
            if next_dt.tzinfo is None:
                next_dt = next_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return max(0, (next_dt - now).total_seconds())
        except (ValueError, TypeError):
            return 0
