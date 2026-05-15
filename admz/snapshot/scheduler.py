import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SnapshotSchedule:
    id: str
    description: str
    interval_seconds: int
    tag_filter: Optional[str] = None
    device_ids: Optional[List[str]] = None
    enabled: bool = True
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    last_result: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["device_ids"] is None:
            del d["device_ids"]
        if d["tag_filter"] is None:
            del d["tag_filter"]
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SnapshotSchedule":
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

    def __init__(self, snapshot_engine, schedule_path: str):
        self.engine = snapshot_engine
        self.schedule_path = Path(schedule_path)
        self.schedules: Dict[str, SnapshotSchedule] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False

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
        logger.info("Running scheduled snapshot: %s", schedule.id)
        now = datetime.now(timezone.utc)

        try:
            snapshots = await self.engine.snapshot_fleet(
                device_ids=schedule.device_ids,
                tag_filter=schedule.tag_filter,
                message=f"Scheduled: {schedule.description}",
            )
            succeeded = sum(1 for s in snapshots if s.succeeded_facets)
            failed = sum(1 for s in snapshots if s.failed_facets and not s.succeeded_facets)

            schedule.last_run = now.isoformat()
            schedule.last_result = (
                f"{succeeded} succeeded, {failed} failed"
                if failed
                else f"{succeeded} succeeded"
            )
            self._save()

            return {
                "success": True,
                "schedule_id": schedule.id,
                "devices_snapshot": len(snapshots),
                "succeeded": succeeded,
                "failed": failed,
            }

        except Exception as e:
            logger.exception("Scheduled snapshot %s failed", schedule.id)
            schedule.last_run = now.isoformat()
            schedule.last_result = f"error: {e}"
            self._save()
            return {
                "success": False,
                "schedule_id": schedule.id,
                "error": str(e),
            }

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
