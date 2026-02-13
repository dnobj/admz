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
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


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
"""


def _default_db_path() -> Path:
    """Resolve the shared ADMZ SQLite database path."""
    return Path(
        os.getenv("ADMZ_DB_PATH", str(Path.home() / ".admz" / "admz.db"))
    )


class CaptureStore:
    """
    SQLite-backed store for credential capture sessions.

    Uses the same database file as the device registry so that both the
    MCP server (stdio subprocess) and the API server (uvicorn) can see
    the same capture tokens.  WAL mode allows concurrent readers/writers.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        """Open a short-lived connection (safe for cross-process use)."""
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self):
        conn = self._connect()
        try:
            conn.executescript(_CAPTURE_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def create_session(
        self,
        device_id: str,
        account_id: str = "default",
        account_type: str = "service",
        purpose: str = "",
        ttl: float = 600.0,
    ) -> CaptureSession:
        """Create a new capture session and return it."""
        self._cleanup()

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
        )

        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO capture_sessions "
                "(token, device_id, account_id, account_type, purpose, created_at, ttl, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (token, device_id, account_id, account_type, purpose, now, ttl, "pending"),
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
        finally:
            conn.close()

        if row is None:
            return None

        session = CaptureSession(
            token=row[0],
            device_id=row[1],
            account_id=row[2],
            account_type=row[3],
            purpose=row[4],
            created_at=row[5],
            ttl=row[6],
            status=CaptureStatus(row[7]),
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


# Module-level singleton so the API routes and MCP server share state.
# Both processes connect to the same SQLite file on disk.
capture_store = CaptureStore()
