"""Watched events — a reusable library of bookmarked event *patterns* (ADR-0041).

A *watched event* is the **trigger half** of a detection: a named, saved event
pattern (``source`` + scope + ``match``) the operator bookmarks from the live
Activity feed and later picks from when building a detection — WITHOUT an action.
It is deliberately NOT a :class:`~admz.events.detections.EventDetection`: it has no
action / cooldown / pre_authorized / enabled / fire bookkeeping, so it never
enters the live firing path and bookmarking never flips ingest on. "Convert to
detection" is a pure UI hand-off (pre-fill the builder → create a brand-new
detection), so one watched event can seed many detections and is never mutated.

The store mirrors :class:`~admz.events.detections.DetectionStore` (same SQLite DB
file, WAL, version counter, CRUD) minus the firing-only columns.
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

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watched_events (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT 'device',
    device_id   TEXT,
    tag         TEXT,
    match_json  TEXT NOT NULL DEFAULT '{}',
    notes       TEXT NOT NULL DEFAULT '',
    created_by  TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL DEFAULT 0
);
"""

_COLS = ("id", "name", "source", "device_id", "tag", "match", "notes",
         "created_by", "created_at")


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


@dataclass
class WatchedEvent:
    id: str
    name: str = ""
    source: str = "device"
    device_id: Optional[str] = None
    tag: Optional[str] = None
    match: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    created_by: str = ""
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "source": self.source,
            "device_id": self.device_id, "tag": self.tag, "match": self.match,
            "notes": self.notes, "created_by": self.created_by,
            "created_at": self.created_at,
        }


class WatchedEventStore:
    """SQLite store for bookmarked event patterns (one process: the web app)."""

    def __init__(self, db_path: Optional[str] = None):
        """No I/O here -- constructing a store must not touch the
        filesystem, because this class backs a module-level singleton
        and anything done here happens at *import* (#254/#258)."""
        self._version = 0  # bumped on every mutation (parity with DetectionStore)
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
            logger.warning("WatchedEventStore table creation failed: %s", exc)

    def _ensure_table(self) -> None:
        """Retained for callers that reach for it by name; ensuring now happens
        inside :meth:`_connect`."""
        self._connect().close()

    @staticmethod
    def _row_to_obj(r) -> WatchedEvent:
        d = dict(zip(_COLS, r))
        try:
            d["match"] = json.loads(d["match"]) if d["match"] else {}
        except (TypeError, ValueError):
            d["match"] = {}
        return WatchedEvent(**d)

    def create(self, w: WatchedEvent) -> str:
        w.id = w.id or uuid.uuid4().hex[:12]
        w.created_at = w.created_at or time.time()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO watched_events (id, name, source, device_id, tag, "
                "match_json, notes, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (w.id, w.name, w.source, w.device_id, w.tag,
                 json.dumps(w.match or {}), w.notes, w.created_by, w.created_at),
            )
            conn.commit()
        finally:
            conn.close()
        self._bump()
        return w.id

    def get(self, watch_id: str) -> Optional[WatchedEvent]:
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT id, name, source, device_id, tag, match_json, notes, "
                "created_by, created_at FROM watched_events WHERE id=?",
                (watch_id,),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_obj(r) if r else None

    def list(self) -> List[WatchedEvent]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, name, source, device_id, tag, match_json, notes, "
                "created_by, created_at FROM watched_events ORDER BY created_at DESC"
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_obj(r) for r in rows]

    def update(self, watch_id: str, **fields: Any) -> bool:
        allowed = {"name", "device_id", "tag", "match", "notes"}
        sets, args = [], []
        for k, v in fields.items():
            if k not in allowed:
                continue
            col = "match_json" if k == "match" else k
            if k == "match":
                v = json.dumps(v or {})
            sets.append(f"{col}=?")
            args.append(v)
        if not sets:
            return False
        args.append(watch_id)
        conn = self._connect()
        try:
            cur = conn.execute(
                f"UPDATE watched_events SET {', '.join(sets)} WHERE id=?", args)
            conn.commit()
            ok = cur.rowcount > 0
        finally:
            conn.close()
        if ok:
            self._bump()
        return ok

    def delete(self, watch_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM watched_events WHERE id=?", (watch_id,))
            conn.commit()
            ok = cur.rowcount > 0
        finally:
            conn.close()
        if ok:
            self._bump()
        return ok


# Module-level singleton (app build rebinds to the resolved DB path).
watched_event_store = WatchedEventStore()
