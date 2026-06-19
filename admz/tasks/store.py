"""The unified ``tasks`` store (ADR-0037) — one SQLite table backing both the
schedule (time-based, recurring) and detection (event-based, one-shot) triggers.

This replaces ``schedules.json`` (and its cross-process merge/reconcile hack) and
the ``pending_device_actions`` table with a single source of truth. SQLite WAL +
atomic conditional UPDATE give cross-process safety for free — the same fire-once
claim the pending store used, now for any process that opens ``admz.db``.

SECURITY (unchanged from the pending store): a detection task with a destructive
action (e.g. ``reprovision``) must only be created AFTER the operator approved the
full sequence. This module stores + claims; it does not gate. Firing runs the
pre-authorized action with no new prompt, so the upstream approval must cover it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- trigger kinds ----------------------------------------------------------
TRIGGER_SCHEDULE = "schedule"     # time-based, recurring
TRIGGER_DETECTION = "detection"   # event-based, one-shot
VALID_TRIGGER_KINDS = {TRIGGER_SCHEDULE, TRIGGER_DETECTION}

# --- detection events (the device-state that fires a detection task) --------
EVENT_NEEDS_SETUP = "on_needs_setup"   # device came back factory-defaulted
EVENT_ONLINE = "on_online"             # device reachable + auth OK
VALID_EVENTS = {EVENT_NEEDS_SETUP, EVENT_ONLINE}

DEFAULT_TTL_SECONDS = 24 * 3600.0


def event_for_status(status: str) -> Optional[str]:
    """The detection event a device health status satisfies, or None.

    (online already means auth-confirmed in the health model.) Ported from the
    pending store's ``trigger_for_status``."""
    if status == "needs_setup":
        return EVENT_NEEDS_SETUP
    if status == "online":
        return EVENT_ONLINE
    return None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    description     TEXT NOT NULL DEFAULT '',
    trigger_kind    TEXT NOT NULL DEFAULT 'schedule',
    interval_seconds INTEGER NOT NULL DEFAULT 0,
    next_run        TEXT,
    last_run        TEXT,
    last_result     TEXT,
    event           TEXT NOT NULL DEFAULT '',
    device_id       TEXT NOT NULL DEFAULT '',
    baseline_bootid TEXT NOT NULL DEFAULT '',
    expires_at      REAL NOT NULL DEFAULT 0,
    action_type     TEXT NOT NULL DEFAULT 'snapshot',
    action_params   TEXT NOT NULL DEFAULT '{}',
    tag_filter      TEXT,
    device_ids      TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1,
    status          TEXT NOT NULL DEFAULT 'active',
    approved_by     TEXT NOT NULL DEFAULT '',
    created_at      REAL NOT NULL DEFAULT 0,
    last_error      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tasks_kind ON tasks(trigger_kind, status);
CREATE INDEX IF NOT EXISTS idx_tasks_device ON tasks(device_id, status);
"""

# Column order MUST match the table definition above (used for SELECT * mapping).
_COLS = (
    "id, description, trigger_kind, interval_seconds, next_run, last_run, "
    "last_result, event, device_id, baseline_bootid, expires_at, action_type, "
    "action_params, tag_filter, device_ids, enabled, status, approved_by, "
    "created_at, last_error"
)
_COL_KEYS = [c.strip() for c in _COLS.split(",")]


def _default_db_path() -> Path:
    return Path(os.getenv("ADMZ_DB_PATH", str(Path.home() / ".admz" / "admz.db")))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Task:
    """One unit of deferred/automated work. A single shape covers both trigger
    kinds; the ``trigger_kind`` discriminator says which fields are meaningful."""

    id: str
    description: str = ""
    trigger_kind: str = TRIGGER_SCHEDULE
    # --- schedule trigger (time-based, recurring) ---
    interval_seconds: int = 0
    next_run: Optional[str] = None      # ISO
    last_run: Optional[str] = None      # ISO
    last_result: Optional[str] = None
    # --- detection trigger (event-based, one-shot) ---
    event: str = ""                     # EVENT_NEEDS_SETUP / EVENT_ONLINE
    device_id: str = ""                 # the single target device (indexed claim)
    baseline_bootid: str = ""
    expires_at: float = 0.0             # unix; 0 = no expiry (schedule tasks)
    # --- action ---
    action_type: str = "snapshot"       # snapshot|drift_audit|survey|reprovision
    action_params: Dict[str, Any] = field(default_factory=dict)
    # --- target (schedule scope) ---
    tag_filter: Optional[str] = None
    device_ids: Optional[List[str]] = None
    # --- common ---
    enabled: bool = True
    status: str = "active"              # schedule: active; detection: pending/...
    approved_by: str = ""
    created_at: float = 0.0
    last_error: str = ""

    # Aliases so ported handlers + the UI read naturally.
    @property
    def name(self) -> str:
        return self.description

    @property
    def action(self) -> Dict[str, Any]:
        """The pending-store-shaped action dict (``{"action": type, ...params}``)
        — keeps back-compat with the detection handler signature + audit code."""
        return {"action": self.action_type, **(self.action_params or {})}

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

    def to_dict(self) -> Dict[str, Any]:
        """Wire shape for the REST/MCP surface + UI."""
        return {
            "id": self.id,
            "description": self.description,
            "name": self.description,
            "trigger_kind": self.trigger_kind,
            "interval_seconds": self.interval_seconds,
            "interval_human": self.interval_human if self.interval_seconds else None,
            "next_run": self.next_run,
            "last_run": self.last_run,
            "last_result": self.last_result,
            "event": self.event or None,
            "device_id": self.device_id or None,
            "baseline_bootid": self.baseline_bootid or None,
            "expires_at": self.expires_at or None,
            "action_type": self.action_type,
            "action_params": self.action_params,
            "tag_filter": self.tag_filter,
            "device_ids": self.device_ids,
            "enabled": self.enabled,
            "status": self.status,
            "approved_by": self.approved_by,
            "created_at": self.created_at,
            "last_error": self.last_error or None,
        }


def _row_to_task(row) -> Task:
    d = dict(zip(_COL_KEYS, row))
    try:
        params = json.loads(d["action_params"]) if d["action_params"] else {}
    except Exception:  # noqa: BLE001
        params = {}
    try:
        dev_ids = json.loads(d["device_ids"]) if d["device_ids"] else None
    except Exception:  # noqa: BLE001
        dev_ids = None
    return Task(
        id=d["id"],
        description=d["description"] or "",
        trigger_kind=d["trigger_kind"],
        interval_seconds=int(d["interval_seconds"] or 0),
        next_run=d["next_run"],
        last_run=d["last_run"],
        last_result=d["last_result"],
        event=d["event"] or "",
        device_id=d["device_id"] or "",
        baseline_bootid=d["baseline_bootid"] or "",
        expires_at=float(d["expires_at"] or 0),
        action_type=d["action_type"] or "snapshot",
        action_params=params,
        tag_filter=d["tag_filter"],
        device_ids=dev_ids,
        enabled=bool(d["enabled"]),
        status=d["status"] or "active",
        approved_by=d["approved_by"] or "",
        created_at=float(d["created_at"] or 0),
        last_error=d["last_error"] or "",
    )


class TaskStore:
    """SQLite-backed unified task store (shares ``admz.db``)."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # ----- write ----------------------------------------------------------

    def upsert(self, task: Task) -> Task:
        """Insert or replace a task by id."""
        if not task.created_at:
            task.created_at = time.time()
        conn = self._connect()
        try:
            conn.execute(
                f"INSERT OR REPLACE INTO tasks ({_COLS}) "
                "VALUES (" + ", ".join("?" * len(_COL_KEYS)) + ")",
                (
                    task.id, task.description or "", task.trigger_kind,
                    int(task.interval_seconds or 0), task.next_run, task.last_run,
                    task.last_result, task.event or "", task.device_id or "",
                    task.baseline_bootid or "", float(task.expires_at or 0),
                    task.action_type or "snapshot",
                    json.dumps(task.action_params or {}),
                    task.tag_filter,
                    json.dumps(task.device_ids) if task.device_ids else None,
                    1 if task.enabled else 0, task.status or "active",
                    task.approved_by or "", float(task.created_at or 0),
                    task.last_error or "",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return task

    def create_schedule(
        self,
        *,
        description: str,
        interval_seconds: int,
        action_type: str = "snapshot",
        action_params: Optional[Dict[str, Any]] = None,
        tag_filter: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
        enabled: bool = True,
        task_id: Optional[str] = None,
        next_run: Optional[str] = None,
    ) -> Task:
        """Create a recurring schedule task. next_run defaults to now+interval."""
        if not next_run:
            next_run = (
                datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)
            ).isoformat()
        task = Task(
            id=task_id or uuid.uuid4().hex,
            description=description,
            trigger_kind=TRIGGER_SCHEDULE,
            interval_seconds=interval_seconds,
            next_run=next_run,
            action_type=action_type,
            action_params=action_params or {},
            tag_filter=tag_filter,
            device_ids=device_ids,
            enabled=enabled,
            status="active",
            created_at=time.time(),
        )
        return self.upsert(task)

    def create_detection(
        self,
        *,
        device_id: str,
        event: str,
        action_type: str,
        action_params: Optional[Dict[str, Any]] = None,
        approved_by: str = "",
        description: str = "",
        baseline_bootid: str = "",
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        task_id: Optional[str] = None,
    ) -> str:
        """Create a one-shot detection task (pre-authorized). Returns its id."""
        if event not in VALID_EVENTS:
            raise ValueError(f"unknown detection event {event!r}")
        now = time.time()
        task = Task(
            id=task_id or uuid.uuid4().hex,
            description=description,
            trigger_kind=TRIGGER_DETECTION,
            event=event,
            device_id=device_id,
            device_ids=[device_id],
            baseline_bootid=baseline_bootid or "",
            expires_at=now + ttl_seconds,
            action_type=action_type,
            action_params=action_params or {},
            approved_by=approved_by or "",
            status="pending",
            created_at=now,
        )
        self.upsert(task)
        return task.id

    def update(self, task_id: str, **fields) -> Optional[Task]:
        """Patch fields on a task by id (only known columns). Returns the task."""
        task = self.get(task_id)
        if task is None:
            return None
        for k, v in fields.items():
            if hasattr(task, k):
                setattr(task, k, v)
        return self.upsert(task)

    def set_run_result(
        self, task_id: str, *, last_run: str, last_result: str,
        next_run: Optional[str] = None,
    ) -> None:
        """Record the outcome of a schedule run (+ advance next_run)."""
        sets = ["last_run=?", "last_result=?"]
        args: List[Any] = [last_run, last_result]
        if next_run is not None:
            sets.append("next_run=?")
            args.append(next_run)
        args.append(task_id)
        conn = self._connect()
        try:
            conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id=?", args)
            conn.commit()
        finally:
            conn.close()

    def delete(self, task_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def mark(self, task_id: str, status: str, error: str = "") -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE tasks SET status=?, last_error=? WHERE id=?",
                (status, error or "", task_id),
            )
            conn.commit()
        finally:
            conn.close()

    def cancel(self, task_id: str) -> bool:
        """Operator-cancel a still-pending detection task. Returns True if it was.

        (Schedule tasks are removed with :meth:`delete`; this is the detection
        counterpart that only flips a *pending* one to cancelled.)"""
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE tasks SET status='cancelled' "
                "WHERE id=? AND trigger_kind='detection' AND status='pending'",
                (task_id,),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def expire_stale(self) -> int:
        """Mark past-expiry pending detection tasks as ``expired``. Returns count."""
        now = time.time()
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE tasks SET status='expired' "
                "WHERE trigger_kind='detection' AND status='pending' "
                "AND expires_at > 0 AND expires_at <= ?",
                (now,),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    # ----- read -----------------------------------------------------------

    def get(self, task_id: str) -> Optional[Task]:
        conn = self._connect()
        try:
            r = conn.execute(
                f"SELECT {_COLS} FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
        finally:
            conn.close()
        return _row_to_task(r) if r else None

    def list(
        self,
        *,
        trigger_kind: Optional[str] = None,
        device_id: Optional[str] = None,
        active_only: bool = False,
    ) -> List[Task]:
        """List tasks, optionally filtered. ``active_only`` keeps schedule tasks
        plus *pending, unexpired* detection tasks (the surfaces an operator
        should see). ``device_id`` matches detection target OR schedule scope."""
        where = []
        args: List[Any] = []
        if trigger_kind:
            where.append("trigger_kind=?")
            args.append(trigger_kind)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT {_COLS} FROM tasks{clause} ORDER BY created_at", args
            ).fetchall()
        finally:
            conn.close()
        tasks = [_row_to_task(r) for r in rows]
        now = time.time()
        if active_only:
            tasks = [
                t for t in tasks
                if t.trigger_kind == TRIGGER_SCHEDULE
                or (t.status == "pending" and (not t.expires_at or t.expires_at > now))
            ]
        if device_id:
            tasks = [t for t in tasks if self._targets_device(t, device_id)]
        return tasks

    @staticmethod
    def _targets_device(task: Task, device_id: str) -> bool:
        if task.device_id == device_id:
            return True
        return bool(task.device_ids) and device_id in task.device_ids

    def list_active_for(self, device_id: str) -> List[Task]:
        """Pending, unexpired detection tasks for one device (device-detail view)."""
        now = time.time()
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT {_COLS} FROM tasks "
                "WHERE trigger_kind='detection' AND device_id=? AND status='pending' "
                "AND (expires_at = 0 OR expires_at > ?) ORDER BY created_at",
                (device_id, now),
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_task(r) for r in rows]

    def list_active_detections(self) -> List[Task]:
        now = time.time()
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT {_COLS} FROM tasks "
                "WHERE trigger_kind='detection' AND status='pending' "
                "AND (expires_at = 0 OR expires_at > ?) ORDER BY created_at",
                (now,),
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_task(r) for r in rows]

    def schedule_tasks(self, *, enabled_only: bool = False) -> List[Task]:
        """All schedule tasks (the scheduler loop's source of truth)."""
        conn = self._connect()
        try:
            if enabled_only:
                rows = conn.execute(
                    f"SELECT {_COLS} FROM tasks "
                    "WHERE trigger_kind='schedule' AND enabled=1 ORDER BY created_at"
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT {_COLS} FROM tasks "
                    "WHERE trigger_kind='schedule' ORDER BY created_at"
                ).fetchall()
        finally:
            conn.close()
        return [_row_to_task(r) for r in rows]

    # ----- fire-once claim (detection; ported from pending_actions) -------

    def claim_for_event(self, device_id: str, event: str) -> List[Task]:
        """Atomically mark this device's matching pending detection tasks as
        ``fired`` and return them — so a concurrent sweep can't double-fire."""
        now = time.time()
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT {_COLS} FROM tasks "
                "WHERE trigger_kind='detection' AND device_id=? AND event=? "
                "AND status='pending' AND (expires_at = 0 OR expires_at > ?) "
                "ORDER BY created_at",
                (device_id, event, now),
            ).fetchall()
            claimed: List[Task] = []
            for r in rows:
                cur = conn.execute(
                    "UPDATE tasks SET status='fired' WHERE id=? AND status='pending'",
                    (r[0],),
                )
                if cur.rowcount == 1:
                    claimed.append(_row_to_task(r))
            conn.commit()
        finally:
            conn.close()
        return claimed


# Module singleton (shares admz.db with the registry/confirm/pending stores).
tasks_store = TaskStore()
