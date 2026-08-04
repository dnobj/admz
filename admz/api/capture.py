"""
Out-of-band credential capture via one-time URLs.

This module enables secure credential collection outside the LLM context
window.  The flow:

1. MCP tool (or API call) creates a capture session -> returns a URL
2. User clicks the URL in their chat client -> opens a browser form
3. User enters credentials in the browser (never touches LLM context)
4. Credentials are stored directly in the device registry
5. MCP tool polls for completion -> returns status only (no secrets)

Tokens are short-lived, single-use, and stored in the shared SQLite
database so that both the MCP server process and the API server process
can see and manage them.
"""

import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class CaptureStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"


@dataclass
class CaptureSession:
    """A single credential-capture session."""

    token: str
    device_id: str
    account_id: str
    account_type: str = "service"
    purpose: str = ""
    created_at: float = field(default_factory=time.time)
    ttl: float = 600.0  # 10 minutes
    status: CaptureStatus = CaptureStatus.PENDING
    device_ids: List[str] = field(default_factory=list)

    @property
    def all_device_ids(self) -> List[str]:
        """Return batch device_ids if set, otherwise a single-element list."""
        return self.device_ids if self.device_ids else [self.device_id]

    @property
    def is_batch(self) -> bool:
        return len(self.device_ids) > 1

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl

    @property
    def effective_status(self) -> CaptureStatus:
        if self.status == CaptureStatus.COMPLETED:
            return CaptureStatus.COMPLETED
        if self.is_expired:
            return CaptureStatus.EXPIRED
        return CaptureStatus.PENDING


_CAPTURE_SCHEMA = """
CREATE TABLE IF NOT EXISTS capture_sessions (
    token        TEXT PRIMARY KEY,
    device_id    TEXT NOT NULL,
    account_id   TEXT NOT NULL,
    account_type TEXT NOT NULL DEFAULT 'service',
    purpose      TEXT NOT NULL DEFAULT '',
    created_at   REAL NOT NULL,
    ttl          REAL NOT NULL DEFAULT 600.0,
    status       TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS capture_session_devices (
    token      TEXT NOT NULL,
    device_id  TEXT NOT NULL,
    PRIMARY KEY (token, device_id),
    FOREIGN KEY (token) REFERENCES capture_sessions(token) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fleet_capture_sessions (
    token        TEXT PRIMARY KEY,
    setting_key  TEXT NOT NULL,
    label        TEXT NOT NULL DEFAULT '',
    created_at   REAL NOT NULL,
    ttl          REAL NOT NULL DEFAULT 600.0,
    status       TEXT NOT NULL DEFAULT 'pending'
);
"""


def _default_db_path() -> Path:
    """Resolve the shared ADMZ SQLite database path."""
    from admz.paths import db_path
    return db_path()


class CaptureStore:
    """
    SQLite-backed store for credential capture sessions.

    Uses the same database file as the device registry so that both the
    MCP server (stdio subprocess) and the API server (uvicorn) can see
    the same capture tokens.  WAL mode allows concurrent readers/writers.
    """

    def __init__(self, db_path: Optional[str] = None):
        """No I/O here -- constructing a store must not touch the
        filesystem, because this class backs a module-level singleton
        and anything done here happens at *import* (#254/#258)."""
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
        """Open a short-lived connection (safe for cross-process use)."""
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
        tables exist. Failures propagate, as they did from ``__init__``; only the moment they can surface moved.
        """
        conn = sqlite3.connect(path)
        try:
            conn.executescript(_CAPTURE_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _ensure_table(self) -> None:
        """Retained for callers that reach for it by name; ensuring now happens
        inside :meth:`_connect`."""
        self._connect().close()
    def create_session(
        self,
        device_id: str,
        account_id: str = "default",
        account_type: str = "service",
        purpose: str = "",
        ttl: float = 600.0,
        device_ids: Optional[List[str]] = None,
    ) -> CaptureSession:
        """Create a new capture session and return it.

        Args:
            device_id: Primary device ID (used for single-device sessions).
            account_id: Account identifier.
            account_type: Account type label.
            purpose: Description of what this account is for.
            ttl: Time-to-live in seconds.
            device_ids: For batch mode — list of device IDs to receive
                the same credentials.  When provided, *device_id* is set
                to the first entry for backwards-compatibility.
        """
        self._cleanup()

        # Normalise batch vs single
        if device_ids and len(device_ids) > 1:
            batch_ids = device_ids
            device_id = device_ids[0]
        else:
            batch_ids = []

        token = secrets.token_urlsafe(32)
        now = time.time()
        session = CaptureSession(
            token=token,
            device_id=device_id,
            account_id=account_id,
            account_type=account_type,
            purpose=purpose,
            created_at=now,
            ttl=ttl,
            device_ids=batch_ids,
        )

        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO capture_sessions "
                "(token, device_id, account_id, account_type, purpose, created_at, ttl, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (token, device_id, account_id, account_type, purpose, now, ttl, "pending"),
            )
            for did in batch_ids:
                conn.execute(
                    "INSERT INTO capture_session_devices (token, device_id) VALUES (?, ?)",
                    (token, did),
                )
            conn.commit()
        finally:
            conn.close()

        return session

    def get_session(self, token: str) -> Optional[CaptureSession]:
        """Look up a session by token.  Returns None if not found or expired."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT token, device_id, account_id, account_type, purpose, "
                "created_at, ttl, status FROM capture_sessions WHERE token=?",
                (token,),
            ).fetchone()

            if row is None:
                return None

            # Check for batch device_ids
            batch_rows = conn.execute(
                "SELECT device_id FROM capture_session_devices WHERE token=?",
                (token,),
            ).fetchall()
        finally:
            conn.close()

        batch_ids = [r[0] for r in batch_rows] if batch_rows else []

        session = CaptureSession(
            token=row[0],
            device_id=row[1],
            account_id=row[2],
            account_type=row[3],
            purpose=row[4],
            created_at=row[5],
            ttl=row[6],
            status=CaptureStatus(row[7]),
            device_ids=batch_ids,
        )

        if session.is_expired and session.status != CaptureStatus.COMPLETED:
            return None

        return session

    def complete_session(self, token: str) -> bool:
        """Mark a session as completed.  Returns False if not found / expired."""
        session = self.get_session(token)
        if session is None or session.effective_status != CaptureStatus.PENDING:
            return False

        conn = self._connect()
        try:
            conn.execute(
                "UPDATE capture_sessions SET status=? WHERE token=?",
                ("completed", token),
            )
            conn.commit()
        finally:
            conn.close()

        return True

    def _cleanup(self):
        """Remove sessions that expired more than 60 s ago."""
        cutoff = time.time() - 60
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM capture_sessions "
                "WHERE status != 'completed' AND (created_at + ttl) < ?",
                (cutoff,),
            )
            conn.commit()
        finally:
            conn.close()


    # ── Fleet setting capture ────────────────────────────────────────────

    def create_fleet_session(
        self,
        setting_key: str,
        label: str = "",
        ttl: float = 600.0,
    ) -> "FleetCaptureSession":
        """Create a capture session for a fleet-wide setting."""
        self._cleanup()
        token = secrets.token_urlsafe(32)
        now = time.time()
        session = FleetCaptureSession(
            token=token,
            setting_key=setting_key,
            label=label,
            created_at=now,
            ttl=ttl,
        )
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO fleet_capture_sessions "
                "(token, setting_key, label, created_at, ttl, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (token, setting_key, label, now, ttl, "pending"),
            )
            conn.commit()
        finally:
            conn.close()
        return session

    def get_fleet_session(self, token: str) -> Optional["FleetCaptureSession"]:
        """Look up a fleet capture session by token."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT token, setting_key, label, created_at, ttl, status "
                "FROM fleet_capture_sessions WHERE token=?",
                (token,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        session = FleetCaptureSession(
            token=row[0],
            setting_key=row[1],
            label=row[2],
            created_at=row[3],
            ttl=row[4],
            status=CaptureStatus(row[5]),
        )
        if session.is_expired and session.status != CaptureStatus.COMPLETED:
            return None
        return session

    def complete_fleet_session(self, token: str) -> bool:
        """Mark a fleet capture session as completed."""
        session = self.get_fleet_session(token)
        if session is None or session.effective_status != CaptureStatus.PENDING:
            return False
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE fleet_capture_sessions SET status=? WHERE token=?",
                ("completed", token),
            )
            conn.commit()
        finally:
            conn.close()
        return True


@dataclass
class FleetCaptureSession:
    """A capture session for a fleet-wide setting (e.g. default password)."""

    token: str
    setting_key: str
    label: str = ""
    created_at: float = field(default_factory=time.time)
    ttl: float = 600.0
    status: CaptureStatus = CaptureStatus.PENDING

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl

    @property
    def effective_status(self) -> CaptureStatus:
        if self.status == CaptureStatus.COMPLETED:
            return CaptureStatus.COMPLETED
        if self.is_expired:
            return CaptureStatus.EXPIRED
        return CaptureStatus.PENDING


# Module-level singleton so the API routes and MCP server share state.
# Both processes connect to the same SQLite file on disk.
capture_store = CaptureStore()
