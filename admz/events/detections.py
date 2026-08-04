"""Event-pattern detection rules (ADR-0041 layer 3).

A *detection rule* is a standing, **recurring** rule — "when motion on the `lab`
cameras, snapshot" — that fires every time a matching event arrives. That's the
key difference from the one-shot ``detection`` *task* trigger (``tasks/store.py``,
claim→fired), so rules live in their own ``event_detections`` table here; the
:mod:`admz.events.evaluator` reuses the task action-handlers to actually *do* the
action.

The model is deliberately forward-compatible (the user will iterate toward
multi-source, timing, and combinations): ``source`` reserves ACS/other event
sources, ``match`` is stored as JSON so it can grow into an AND/OR/sequence tree,
and ``active_window`` reserves a timing gate (unused in v1).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Service-affecting actions fire autonomously, so they require an explicit
# per-rule pre-authorization set by an authenticated creator.
SERVICE_AFFECTING_ACTIONS = {"acs_action"}
SAFE_ACTIONS = {"snapshot", "drift_audit", "notify"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS event_detections (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL DEFAULT '',
    enabled         INTEGER NOT NULL DEFAULT 1,
    source          TEXT NOT NULL DEFAULT 'device',
    device_id       TEXT,
    tag             TEXT,
    match_json      TEXT NOT NULL DEFAULT '{}',
    action_type     TEXT NOT NULL DEFAULT 'notify',
    action_params   TEXT NOT NULL DEFAULT '{}',
    pre_authorized  INTEGER NOT NULL DEFAULT 0,
    cooldown_seconds INTEGER NOT NULL DEFAULT 0,
    active_window   TEXT,
    created_by      TEXT NOT NULL DEFAULT '',
    created_at      REAL NOT NULL DEFAULT 0,
    last_fired_ms   INTEGER NOT NULL DEFAULT 0,
    fire_count      INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT NOT NULL DEFAULT ''
);
"""

_COLS = ("id", "name", "enabled", "source", "device_id", "tag", "match", "action_type",
         "action_params", "pre_authorized", "cooldown_seconds", "active_window",
         "created_by", "created_at", "last_fired_ms", "fire_count", "last_error")


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


@dataclass
class EventDetection:
    id: str
    name: str = ""
    enabled: bool = True
    source: str = "device"
    device_id: Optional[str] = None
    tag: Optional[str] = None
    match: Dict[str, Any] = field(default_factory=dict)
    action_type: str = "notify"
    action_params: Dict[str, Any] = field(default_factory=dict)
    pre_authorized: bool = False
    cooldown_seconds: int = 0
    active_window: Optional[Dict[str, Any]] = None
    created_by: str = ""
    created_at: float = 0.0
    last_fired_ms: int = 0
    fire_count: int = 0
    last_error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "enabled": self.enabled,
            "source": self.source, "device_id": self.device_id, "tag": self.tag,
            "match": self.match, "action_type": self.action_type,
            "action_params": self.action_params, "pre_authorized": self.pre_authorized,
            "cooldown_seconds": self.cooldown_seconds, "active_window": self.active_window,
            "created_by": self.created_by, "created_at": self.created_at,
            "last_fired_ms": self.last_fired_ms, "fire_count": self.fire_count,
            "last_error": self.last_error,
        }


class DetectionStore:
    """SQLite store for recurring detection rules (one process: the web app)."""

    def __init__(self, db_path: Optional[str] = None):
        """No I/O here -- constructing a store must not touch the
        filesystem, because this class backs a module-level singleton
        and anything done here happens at *import* (#254/#258)."""
        self._version = 0  # bumped on every mutation; the evaluator reloads on change
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set = set()
        self._ready_lock = threading.Lock()

    @property
    def _db_path(self) -> str:
        """Resolved at CALL time, not cached at construction (#258).

        Caching in ``__init__`` is what froze the path: an ``ADMZ_HOME`` or
        ``ADMZ_DB_PATH`` set afterwards was ignored for the life of the
        process. Deferring *construction* does not fix that -- measured, the
        stores that were already lazy froze identically, just later.

        Stays a ``str``: tests read this attribute and pass it straight to
        ``sqlite3.connect()``.
        """
        return self._explicit_db_path or str(_default_db_path())

    @property
    def version(self) -> int:
        return self._version

    def _bump(self) -> None:
        self._version += 1

    def _connect(self) -> sqlite3.Connection:
        path = self._db_path
        if path not in self._ready:  # fast path: no lock once warm
            with self._ready_lock:
                if path not in self._ready:  # double-checked
                    from admz.paths import ensure_parent_dir

                    ensure_parent_dir(path)
                    self._create_schema(path)
                    self._ready.add(path)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _create_schema(self, path: str) -> None:
        """Open our own connection -- routing through ``_connect`` would recurse.

        ``_ready`` is keyed by path rather than a boolean, so a rebind runs the
        schema against the new file instead of assuming the previous one's
        tables exist. Swallowed exactly as before -- a failure here left the
        tables absent and let the first real query surface it, and that is
        preserved.
        """
        try:
            conn = sqlite3.connect(path)
            try:
                conn.executescript(_SCHEMA)
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:  # pragma: no cover - defensive
            logger.warning("DetectionStore table creation failed: %s", exc)

    def _ensure_table(self) -> None:
        """Retained for callers that reach for it by name; ensuring now happens
        inside :meth:`_connect`."""
        self._connect().close()

    @staticmethod
    def _row_to_obj(r) -> EventDetection:
        d = dict(zip(_COLS, r))
        d["enabled"] = bool(d["enabled"])
        d["pre_authorized"] = bool(d["pre_authorized"])
        for k in ("match", "action_params"):
            try:
                d[k] = json.loads(d[k]) if d[k] else {}
            except (TypeError, ValueError):
                d[k] = {}
        try:
            d["active_window"] = json.loads(d["active_window"]) if d["active_window"] else None
        except (TypeError, ValueError):
            d["active_window"] = None
        return EventDetection(**d)

    def create(self, det: EventDetection) -> str:
        det.id = det.id or uuid.uuid4().hex[:12]
        det.created_at = det.created_at or time.time()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO event_detections (id, name, enabled, source, device_id, tag, "
                "match_json, action_type, action_params, pre_authorized, cooldown_seconds, "
                "active_window, created_by, created_at, last_fired_ms, fire_count, last_error) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (det.id, det.name, int(det.enabled), det.source, det.device_id, det.tag,
                 json.dumps(det.match or {}), det.action_type, json.dumps(det.action_params or {}),
                 int(det.pre_authorized), int(det.cooldown_seconds),
                 json.dumps(det.active_window) if det.active_window else None,
                 det.created_by, det.created_at, det.last_fired_ms, det.fire_count, det.last_error),
            )
            conn.commit()
        finally:
            conn.close()
        self._bump()
        return det.id

    def get(self, det_id: str) -> Optional[EventDetection]:
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT id, name, enabled, source, device_id, tag, match_json, action_type, "
                "action_params, pre_authorized, cooldown_seconds, active_window, created_by, "
                "created_at, last_fired_ms, fire_count, last_error FROM event_detections WHERE id=?",
                (det_id,),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_obj(r) if r else None

    def list(self, enabled_only: bool = False) -> List[EventDetection]:
        clause = "WHERE enabled=1 " if enabled_only else ""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, name, enabled, source, device_id, tag, match_json, action_type, "
                "action_params, pre_authorized, cooldown_seconds, active_window, created_by, "
                f"created_at, last_fired_ms, fire_count, last_error FROM event_detections {clause}"
                "ORDER BY created_at DESC"
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_obj(r) for r in rows]

    def update(self, det_id: str, **fields: Any) -> bool:
        allowed = {"name", "enabled", "device_id", "tag", "match", "action_type",
                   "action_params", "pre_authorized", "cooldown_seconds", "active_window", "last_error"}
        sets, args = [], []
        for k, v in fields.items():
            if k not in allowed:
                continue
            col = "match_json" if k == "match" else k
            if k in ("match", "action_params", "active_window"):
                v = json.dumps(v) if v is not None else None
            elif k in ("enabled", "pre_authorized"):
                v = int(bool(v))
            sets.append(f"{col}=?")
            args.append(v)
        if not sets:
            return False
        args.append(det_id)
        conn = self._connect()
        try:
            cur = conn.execute(f"UPDATE event_detections SET {', '.join(sets)} WHERE id=?", args)
            conn.commit()
            ok = cur.rowcount > 0
        finally:
            conn.close()
        if ok:
            self._bump()
        return ok

    def record_fire(self, det_id: str, ts_ms: int, error: str = "") -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE event_detections SET last_fired_ms=?, fire_count=fire_count+1, last_error=? WHERE id=?",
                (int(ts_ms), error, det_id),
            )
            conn.commit()
        finally:
            conn.close()
        # not a structural change → no version bump (evaluator keeps its rule list)

    def delete(self, det_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM event_detections WHERE id=?", (det_id,))
            conn.commit()
            ok = cur.rowcount > 0
        finally:
            conn.close()
        if ok:
            self._bump()
        return ok


# Module-level singleton (app build rebinds to the resolved DB path).
detection_store = DetectionStore()
