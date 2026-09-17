"""The discovery scan store (ADR-0072 §1).

One table in ``admz.db``. A row is one run of ``discover_network_devices``:
who ran it, what it was asked to scan, and every device it found. The console's
discovery widget reads it back by ``scan_id``, and the add route builds its
approval session from it, so what gets registered is what the scan saw, never
what a request body claims.

Why a store rather than the tool result the browser already has: that copy is
capped at 50 list items (``chatbot/client.py::_redact_for_display``), and the
MCP handler that ran the scan lives in a per-principal subprocess, so the API
process can only see the scan through the database.

A row is a record of one run, not a cache that accumulates findings
(KL-DISC-002 stands). Rows are purged after :data:`RETENTION_SECONDS`.

What a row may hold: identifiers, addresses, the device's self-reported
metadata and ``to_registry_dict()``. Never a credential. Device-written strings
are data; every surface that shows them escapes them.

Like every store here, construction does no I/O and the database path is
resolved at call time (#254/#258).
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

#: A scan row is deleted this long after it was taken.
RETENTION_SECONDS = 24 * 3600
#: Saves run the purge at most this often, per process.
PURGE_INTERVAL_SECONDS = 300.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS discovery_scans (
    scan_id          TEXT PRIMARY KEY,
    principal        TEXT NOT NULL,
    conversation_id  TEXT NOT NULL DEFAULT '',
    subnet           TEXT NOT NULL DEFAULT '',
    axis_only        INTEGER NOT NULL DEFAULT 0,
    created_at       REAL NOT NULL,
    devices_json     TEXT NOT NULL DEFAULT '[]',
    add_key          TEXT NOT NULL DEFAULT '',
    add_token        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_discovery_scans_created
    ON discovery_scans(created_at);
"""

_COLS = ("scan_id", "principal", "conversation_id", "subnet", "axis_only",
         "created_at", "devices_json", "add_key", "add_token")
_SELECT = f"SELECT {', '.join(_COLS)} FROM discovery_scans"


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


@dataclass
class DiscoveryScan:
    """One recorded run of ``discover_network_devices``."""

    scan_id: str
    principal: str
    conversation_id: str = ""
    subnet: str = ""
    axis_only: bool = False
    created_at: float = 0.0
    devices: List[Dict[str, Any]] = field(default_factory=list)
    #: The selection the last add approval was opened for, and its token —
    #: so a retry of the same selection reuses the session (and its
    #: per-token password lockout) instead of minting a fresh one.
    add_key: str = ""
    add_token: str = ""

    def age_seconds(self, now: Optional[float] = None) -> float:
        return max(0.0, (time.time() if now is None else now) - self.created_at)


def _row_to_scan(row: tuple) -> DiscoveryScan:
    d = dict(zip(_COLS, row))
    try:
        devices = json.loads(d["devices_json"] or "[]")
    except (TypeError, ValueError):
        devices = []
    return DiscoveryScan(
        scan_id=d["scan_id"],
        principal=d["principal"],
        conversation_id=d["conversation_id"] or "",
        subnet=d["subnet"] or "",
        axis_only=bool(d["axis_only"]),
        created_at=float(d["created_at"] or 0),
        devices=[x for x in devices if isinstance(x, dict)]
        if isinstance(devices, list) else [],
        add_key=d["add_key"] or "",
        add_token=d["add_token"] or "",
    )


class DiscoveryScanStore:
    """SQLite-backed record of discovery runs (shares ``admz.db``)."""

    def __init__(self, db_path: Optional[str] = None):
        """No I/O: this class backs a module-level singleton (#254/#258)."""
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set = set()
        self._ready_lock = threading.Lock()
        self._last_purge: Dict[str, float] = {}

    @property
    def _db_path(self) -> str:
        """Resolved at CALL time, never cached at construction (#258)."""
        return self._explicit_db_path or str(_default_db_path())

    def _connect(self) -> sqlite3.Connection:
        path = self._db_path
        if path not in self._ready:
            with self._ready_lock:
                if path not in self._ready:
                    from admz.paths import ensure_parent_dir

                    ensure_parent_dir(path)
                    self._create_schema(path)
                    self._ready.add(path)
        conn = sqlite3.connect(path, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _create_schema(self, path: str) -> None:
        conn = sqlite3.connect(path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ writes
    def save_scan(
        self,
        *,
        principal: str,
        devices: List[Dict[str, Any]],
        subnet: str = "",
        axis_only: bool = False,
        now: Optional[float] = None,
    ) -> DiscoveryScan:
        """Record one run and return it, with a fresh unguessable ``scan_id``."""
        if not principal:
            raise ValueError("a scan needs a principal")
        now = time.time() if now is None else now
        scan = DiscoveryScan(
            scan_id=secrets.token_urlsafe(24),
            principal=principal,
            subnet=subnet or "",
            axis_only=bool(axis_only),
            created_at=now,
            devices=list(devices),
        )
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO discovery_scans "
                "(scan_id, principal, conversation_id, subnet, axis_only, "
                " created_at, devices_json) VALUES (?, ?, '', ?, ?, ?, ?)",
                (scan.scan_id, scan.principal, scan.subnet,
                 1 if scan.axis_only else 0, scan.created_at,
                 json.dumps(scan.devices, default=str)),
            )
            self._maybe_purge(conn, now)
        finally:
            conn.close()
        return scan

    def bind_conversation(
        self, scan_id: str, principal: str, conversation_id: str,
    ) -> bool:
        """Attach the conversation the scan's turn ran in.

        Only the scan's own principal can bind it, and only once: a scan
        belongs to the turn that produced it.
        """
        if not (scan_id and principal and conversation_id):
            return False
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE discovery_scans SET conversation_id = ? "
                "WHERE scan_id = ? AND principal = ? AND conversation_id = ''",
                (conversation_id, scan_id, principal),
            )
            return cur.rowcount > 0
        finally:
            conn.close()

    def remember_add(
        self, scan_id: str, principal: str, add_key: str, add_token: str,
    ) -> None:
        """Record the approval session opened for a selection of this scan."""
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE discovery_scans SET add_key = ?, add_token = ? "
                "WHERE scan_id = ? AND principal = ?",
                (add_key, add_token, scan_id, principal),
            )
        finally:
            conn.close()

    def _maybe_purge(self, conn: sqlite3.Connection, now: float) -> None:
        path = self._db_path
        if now - self._last_purge.get(path, 0.0) < PURGE_INTERVAL_SECONDS:
            return
        self._last_purge[path] = now
        conn.execute(
            "DELETE FROM discovery_scans WHERE created_at < ?",
            (now - RETENTION_SECONDS,),
        )

    # ------------------------------------------------------------------- reads
    def get_scan(
        self, scan_id: str, *, now: Optional[float] = None,
    ) -> Optional[DiscoveryScan]:
        """The scan, or ``None`` when unknown or past retention."""
        if not scan_id:
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                f"{_SELECT} WHERE scan_id = ?", (scan_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        scan = _row_to_scan(row)
        if scan.age_seconds(now) > RETENTION_SECONDS:
            return None
        return scan

    def count(self) -> int:
        conn = self._connect()
        try:
            return int(conn.execute(
                "SELECT COUNT(*) FROM discovery_scans").fetchone()[0])
        finally:
            conn.close()


discovery_scans = DiscoveryScanStore()
