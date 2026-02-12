"""
Out-of-band credential capture via one-time URLs.

This module enables secure credential collection outside the LLM context
window.  The flow:

1. MCP tool (or API call) creates a capture session → returns a URL
2. User clicks the URL in their chat client → opens a browser form
3. User enters credentials in the browser (never touches LLM context)
4. Credentials are stored directly in the device registry
5. MCP tool polls for completion → returns status only (no secrets)

Tokens are short-lived, single-use, and held in memory only.
"""

import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


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


class CaptureStore:
    """
    In-memory store for credential capture sessions.

    Thread-safe for the single-process FastAPI use case.
    Sessions auto-expire after their TTL.
    """

    def __init__(self):
        self._sessions: Dict[str, CaptureSession] = {}

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
        session = CaptureSession(
            token=token,
            device_id=device_id,
            account_id=account_id,
            account_type=account_type,
            purpose=purpose,
            ttl=ttl,
        )
        self._sessions[token] = session
        return session

    def get_session(self, token: str) -> Optional[CaptureSession]:
        """Look up a session by token.  Returns None if not found or expired."""
        session = self._sessions.get(token)
        if session is None:
            return None
        if session.is_expired and session.status != CaptureStatus.COMPLETED:
            return None
        return session

    def complete_session(self, token: str) -> bool:
        """Mark a session as completed.  Returns False if not found / expired."""
        session = self.get_session(token)
        if session is None or session.effective_status != CaptureStatus.PENDING:
            return False
        session.status = CaptureStatus.COMPLETED
        return True

    def _cleanup(self):
        """Remove sessions that expired more than 60 s ago."""
        cutoff = time.time() - 60
        expired = [
            t
            for t, s in self._sessions.items()
            if s.status != CaptureStatus.COMPLETED
            and (s.created_at + s.ttl) < cutoff
        ]
        for t in expired:
            del self._sessions[t]


# Module-level singleton so the API routes and MCP server share state.
capture_store = CaptureStore()
