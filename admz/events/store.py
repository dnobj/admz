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
    return Path(os.getenv("ADMZ_DB_PATH", str(Path.home() / ".admz" / "admz.db")))


class EventStore:
    """SQLite-backed append-only event log."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        try:
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
                conn.commit()
        except sqlite3.Error as exc:  # pragma: no cover — defensive
            logger.warning("EventStore table creation failed: %s", exc)

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
            logger.warning("EventStore append failed: %s", exc)
            return False

    def query(
        self,
        *,
        source: Optional[str] = None,
        type_filter: Optional[str] = None,
        device_id: Optional[str] = None,
        device_filter: Optional[str] = None,
        since_ms: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Return events newest-first with optional filters.

        ``type_filter`` / ``device_filter`` are case-insensitive substring
        matches; ``device_id`` is an exact match; ``since_ms`` bounds by epoch ms.
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
