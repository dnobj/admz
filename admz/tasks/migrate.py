"""One-time migration of the two legacy stores into the unified ``tasks`` table
(ADR-0037): ``schedules.json`` → schedule tasks, ``pending_device_actions`` →
detection tasks.

Idempotent (skips ids already present) and non-destructive: the pending table is
left in place; ``schedules.json`` is renamed to ``schedules.json.migrated`` as a
backup only after its rows are imported. Safe to run on every startup; safe to
dry-run against a copy of the live DB + schedules file.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from admz.tasks.store import (
    TRIGGER_DETECTION,
    TRIGGER_SCHEDULE,
    Task,
    TaskStore,
    _default_db_path,
)

logger = logging.getLogger(__name__)


def _default_schedules_path() -> Path:
    from admz.paths import schedules_path
    return schedules_path()


def migrate_legacy(
    *,
    db_path: Optional[str] = None,
    schedules_path: Optional[str] = None,
    backup: bool = True,
) -> Dict[str, Any]:
    """Import legacy schedules + pending actions into the unified ``tasks`` table.

    Returns a summary dict. Idempotent: re-running migrates only rows whose id is
    not already a task."""
    db_path = str(db_path or _default_db_path())
    sched_path = Path(schedules_path) if schedules_path else _default_schedules_path()
    store = TaskStore(db_path)
    summary: Dict[str, Any] = {
        "schedules_migrated": 0, "pending_migrated": 0, "skipped": 0,
        "schedules_backup": None,
    }

    # 1) schedules.json -> schedule tasks
    if sched_path.exists():
        try:
            raw = json.loads(sched_path.read_text(encoding="utf-8") or "{}") or {}
        except Exception:  # noqa: BLE001
            logger.warning("migrate: could not read %s", sched_path, exc_info=True)
            raw = {}
        for sid, sdata in raw.items():
            if not isinstance(sdata, dict):
                continue
            if store.get(sid) is not None:
                summary["skipped"] += 1
                continue
            store.upsert(Task(
                id=sid,
                description=sdata.get("description", "") or "",
                trigger_kind=TRIGGER_SCHEDULE,
                interval_seconds=int(sdata.get("interval_seconds", 0) or 0),
                next_run=sdata.get("next_run"),
                last_run=sdata.get("last_run"),
                last_result=sdata.get("last_result"),
                action_type=sdata.get("job_type", "snapshot") or "snapshot",
                action_params=sdata.get("params") or {},
                tag_filter=sdata.get("tag_filter"),
                device_ids=sdata.get("device_ids"),
                enabled=bool(sdata.get("enabled", True)),
                status="active",
            ))
            summary["schedules_migrated"] += 1
        if backup and summary["schedules_migrated"]:
            bak = sched_path.with_name(sched_path.name + ".migrated")
            try:
                sched_path.replace(bak)
                summary["schedules_backup"] = str(bak)
            except Exception:  # noqa: BLE001
                logger.warning("migrate: backup rename failed", exc_info=True)

    # 2) pending_device_actions -> detection tasks (leave the old table intact)
    conn = sqlite3.connect(db_path)
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='pending_device_actions'"
        ).fetchone()
        if exists:
            rows = conn.execute(
                "SELECT id, device_id, action_json, trigger, baseline_bootid, "
                "approved_by, description, created_at, expires_at, status, "
                "last_error FROM pending_device_actions"
            ).fetchall()
        else:
            rows = []
    finally:
        conn.close()

    for r in rows:
        (pid, did, action_json, trig, bootid, approved_by, desc,
         created_at, expires_at, status, last_error) = r
        if store.get(pid) is not None:
            summary["skipped"] += 1
            continue
        try:
            action = json.loads(action_json) if action_json else {}
        except Exception:  # noqa: BLE001
            action = {}
        store.upsert(Task(
            id=pid,
            device_id=did or "",
            device_ids=[did] if did else None,
            trigger_kind=TRIGGER_DETECTION,
            event=trig or "",
            baseline_bootid=bootid or "",
            expires_at=float(expires_at or 0),
            action_type=action.get("action", ""),
            action_params={k: v for k, v in action.items() if k != "action"},
            approved_by=approved_by or "",
            description=desc or "",
            created_at=float(created_at or 0),
            status=status or "pending",
            last_error=last_error or "",
        ))
        summary["pending_migrated"] += 1

    logger.info(
        "tasks migration: %d schedule(s), %d pending action(s) imported (%d skipped)",
        summary["schedules_migrated"], summary["pending_migrated"],
        summary["skipped"],
    )
    return summary
