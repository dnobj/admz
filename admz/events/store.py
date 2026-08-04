"""Append-only event store (ADR-0041 layer 2).

Mirrors the ``DeviceHealthStore`` / ``TaskStore`` SQLite+WAL pattern: one table
in the shared ``~/.admz/admz.db``, per-call connections, idempotent schema. Rows
are the canonical normalized-event shape (see :mod:`admz.events.normalize`).
Inserts are **idempotent** (``INSERT OR IGNORE`` on a content-hash ``id``) so a
reconnecting stream that re-emits an event never double-stores it.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id           TEXT PRIMARY KEY,
    ts           TEXT NOT NULL,
    ts_ms        INTEGER NOT NULL DEFAULT 0,
    source       TEXT NOT NULL,
    type         TEXT,
    device_id    TEXT,
    device_name  TEXT,
    summary      TEXT,
    data         TEXT NOT NULL DEFAULT '{}',
    created_at   REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts_ms DESC);
CREATE INDEX IF NOT EXISTS idx_events_device ON events(device_id, ts_ms DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
"""

_COLS = ("id", "ts", "ts_ms", "source", "type", "device_id", "device_name", "summary", "data", "created_at")


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


class EventStore:
    """SQLite-backed append-only event log."""

    def __init__(self, db_path: Optional[str] = None):
        """No I/O here -- constructing a store must not touch the
        filesystem, because this class backs a module-level singleton
        and anything done here happens at *import* (#254/#258)."""
        # Monotonic count of appends lost to a swallowed sqlite error. `append`
        # returns False for a duplicate AND for a DB failure, so its return value
        # alone cannot tell a caller which happened. ADR-0057 gates ACS firing on
        # that return value and needs to report store outages without changing
        # `append`'s signature (three device-ingest callers depend on it), so the
        # count is exposed as plain additive state instead.
        self.append_errors = 0
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
        tables exist. Swallowed exactly as before -- a failure here left the tables absent and let the first real query surface it, and that is preserved.
        """
        try:
            conn = sqlite3.connect(path)
            try:
                conn.executescript(_SCHEMA)
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:  # pragma: no cover - defensive
            logger.warning("EventStore table creation failed: %s", exc)

    def _ensure_table(self) -> None:
        """Retained for callers that reach for it by name; ensuring now happens
        inside :meth:`_connect`."""
        self._connect().close()
    def append(self, event: Dict[str, Any]) -> bool:
        """Insert one normalized event. Idempotent (dedup on ``id``).

        Returns True if a new row was written, False if it was a duplicate (or
        on a swallowed DB error — appends must never break the ingest loop).
        """
        row = (
            event.get("id"),
            event.get("ts") or "",
            int(event.get("ts_ms") or 0),
            event.get("source") or "device",
            event.get("type"),
            event.get("device_id"),
            event.get("device_name"),
            event.get("summary"),
            json.dumps(event.get("data") or {}, default=str),
            float(event.get("created_at") or time.time()),
        )
        try:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO events "
                    "(id, ts, ts_ms, source, type, device_id, device_name, summary, data, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()
        except sqlite3.Error as exc:  # pragma: no cover — defensive
            self.append_errors += 1
            logger.warning("EventStore append failed: %s", exc)
            return False

    def query(
        self,
        *,
        source: Optional[str] = None,
        type_filter: Optional[str] = None,
        device_id: Optional[str] = None,
        device_filter: Optional[str] = None,
        q: Optional[str] = None,
        since_ms: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Return events newest-first with optional filters.

        ``type_filter`` / ``device_filter`` are case-insensitive substring
        matches; ``device_id`` is an exact match; ``since_ms`` bounds by epoch
        ms. ``q`` is a general text search — every whitespace-separated term
        must appear somewhere in the event (summary, type, device name, or the
        raw data payload), so "port 1 active" narrows the way an operator
        expects.
        """
        where: List[str] = []
        args: List[Any] = []
        if source:
            where.append("source = ?")
            args.append(source)
        if device_id:
            where.append("device_id = ?")
            args.append(device_id)
        if type_filter:
            where.append("LOWER(type) LIKE ?")
            args.append(f"%{type_filter.lower()}%")
        if device_filter:
            where.append("LOWER(COALESCE(device_name, '')) LIKE ?")
            args.append(f"%{device_filter.lower()}%")
        for term in (q or "").split():
            where.append(
                "LOWER(COALESCE(summary,'') || ' ' || COALESCE(type,'') || ' ' "
                "|| COALESCE(device_name,'') || ' ' || COALESCE(data,'')) LIKE ?"
            )
            args.append(f"%{term.lower()}%")
        if since_ms is not None:
            where.append("ts_ms >= ?")
            args.append(int(since_ms))
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        sql = (
            "SELECT id, ts, ts_ms, source, type, device_id, device_name, summary, data, created_at "
            f"FROM events {clause} ORDER BY ts_ms DESC, created_at DESC LIMIT ?"
        )
        args.append(int(limit))
        try:
            conn = self._connect()
            try:
                rows = conn.execute(sql, args).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as exc:  # pragma: no cover — defensive
            logger.warning("EventStore query failed: %s", exc)
            return []
        out: List[Dict[str, Any]] = []
        for r in rows:
            rec = dict(zip(_COLS, r))
            try:
                rec["data"] = json.loads(rec["data"]) if rec["data"] else {}
            except (TypeError, ValueError):
                rec["data"] = {}
            out.append(rec)
        return out

    def count(self) -> int:
        try:
            conn = self._connect()
            try:
                return int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
            finally:
                conn.close()
        except sqlite3.Error:  # pragma: no cover — defensive
            return 0

    def prune(self, *, older_than_ms: Optional[int] = None,
              keep_max: Optional[int] = None) -> int:
        """Delete old events. ``older_than_ms`` drops anything older than a cutoff;
        ``keep_max`` keeps only the newest N rows. Returns rows deleted.

        Cheap in the watch-scoped world (the store holds only watched hits) and
        the backstop against any single chatty watched topic growing without end.
        """
        total = 0
        try:
            conn = self._connect()
            try:
                if older_than_ms is not None:
                    cur = conn.execute("DELETE FROM events WHERE ts_ms < ?", (int(older_than_ms),))
                    total += max(cur.rowcount, 0)
                if keep_max is not None:
                    cur = conn.execute(
                        "DELETE FROM events WHERE id NOT IN "
                        "(SELECT id FROM events ORDER BY ts_ms DESC, created_at DESC LIMIT ?)",
                        (int(keep_max),),
                    )
                    total += max(cur.rowcount, 0)
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:  # pragma: no cover — defensive
            logger.warning("EventStore prune failed: %s", exc)
        return total

    def enforce_retention(self) -> int:
        """Apply the configured retention (days, then max-rows). Returns deleted."""
        from admz.events import config as cfg
        deleted = 0
        days = cfg.events_retention_days()
        if days and days > 0:
            cutoff_ms = int((time.time() - days * 86400) * 1000)
            deleted += self.prune(older_than_ms=cutoff_ms)
        max_rows = cfg.events_max_rows()
        if max_rows and max_rows > 0:
            deleted += self.prune(keep_max=max_rows)
        return deleted

    def activity_since(
        self,
        *,
        since_ms: int,
        source: Optional[str] = None,
        type_filter: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """"Did this signal fire since ``since_ms`` — and when last?"

        One indexed aggregate instead of pulling rows: :meth:`query` answers
        per-event, but a rollup (the Demos readiness panel) only needs
        ``{"count", "last_ms"}``. Filters match :meth:`query` semantics —
        ``device_id`` exact, ``type_filter`` a case-insensitive substring.
        """
        where: List[str] = ["ts_ms >= ?"]
        args: List[Any] = [int(since_ms)]
        if source:
            where.append("source = ?")
            args.append(source)
        if device_id:
            where.append("device_id = ?")
            args.append(device_id)
        if type_filter:
            where.append("LOWER(type) LIKE ?")
            args.append(f"%{type_filter.lower()}%")
        sql = (f"SELECT COUNT(*), MAX(ts_ms) FROM events "
               f"WHERE {' AND '.join(where)}")
        try:
            conn = self._connect()
            try:
                row = conn.execute(sql, args).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:  # pragma: no cover — defensive
            logger.warning("EventStore activity_since failed: %s", exc)
            return {"count": 0, "last_ms": None}
        count = int(row[0] or 0)
        return {"count": count, "last_ms": int(row[1]) if row[1] else None}

    def count_since(self, *, since_ms: int, **kw) -> int:
        """Convenience: just the count from :meth:`activity_since`."""
        return self.activity_since(since_ms=since_ms, **kw)["count"]

    def prune_before(self, ts_ms: int) -> int:
        """Delete events older than ``ts_ms`` (retention hook). Returns rows removed."""
        try:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM events WHERE ts_ms < ?", (int(ts_ms),))
                conn.commit()
                return cur.rowcount
            finally:
                conn.close()
        except sqlite3.Error:  # pragma: no cover — defensive
            return 0


# Module-level singleton (bound to the default DB; app build rebinds via DI).
event_store = EventStore()
