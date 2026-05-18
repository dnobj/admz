"""
Temporary credential manager for ADMZ MCP server.

Creates short-lived device user accounts so the LLM gets usable
credentials without ever seeing the real admin password.  A background
loop removes expired accounts from devices automatically.
"""

import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# Axis cameras have a 14-character username limit.
# "at_" prefix (3 chars) + 8 hex chars = 11 chars total → safe.
_USERNAME_PREFIX = "at_"
_USERNAME_HEX_LEN = 8
_PASSWORD_LENGTH = 16
_MAX_PER_DEVICE = 3
_MAX_CLEANUP_ATTEMPTS = 5


@dataclass
class TempCredential:
    """A temporary device account tracked in memory."""

    device_id: str
    username: str
    password: str
    group: str
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = 300
    cleanup_attempts: int = 0

    @property
    def expires_at(self) -> float:
        return self.created_at + self.ttl_seconds

    @property
    def expires_at_iso(self) -> str:
        return time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.expires_at)
        )

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

    @property
    def should_retry_cleanup(self) -> bool:
        return self.cleanup_attempts < _MAX_CLEANUP_ATTEMPTS


class TempCredentialManager:
    """In-memory tracker for temporary device accounts."""

    def __init__(self) -> None:
        # Key: (device_id, username)
        self._active: Dict[Tuple[str, str], TempCredential] = {}

    @staticmethod
    def generate_username() -> str:
        return _USERNAME_PREFIX + secrets.token_hex(_USERNAME_HEX_LEN // 2)

    @staticmethod
    def generate_password() -> str:
        return secrets.token_urlsafe(_PASSWORD_LENGTH)[:_PASSWORD_LENGTH]

    def count_active_for_device(self, device_id: str) -> int:
        return sum(
            1
            for (did, _), cred in self._active.items()
            if did == device_id and not cred.is_expired
        )

    def register(self, cred: TempCredential) -> None:
        self._active[(cred.device_id, cred.username)] = cred

    def remove(self, device_id: str, username: str) -> Optional[TempCredential]:
        return self._active.pop((device_id, username), None)

    def get_expired(self) -> List[TempCredential]:
        return [c for c in self._active.values() if c.is_expired]

    def list_active(self, device_id: Optional[str] = None) -> List[Dict]:
        """Return metadata for active creds (never includes passwords)."""
        results = []
        for cred in self._active.values():
            if device_id and cred.device_id != device_id:
                continue
            results.append({
                "device_id": cred.device_id,
                "username": cred.username,
                "group": cred.group,
                "created_at": cred.created_at,
                "ttl_seconds": cred.ttl_seconds,
                "expires_at": cred.expires_at_iso,
                "is_expired": cred.is_expired,
            })
        return results

    def get_all(self) -> List[TempCredential]:
        """Return all tracked credentials (for shutdown cleanup)."""
        return list(self._active.values())

    @property
    def max_per_device(self) -> int:
        return _MAX_PER_DEVICE
