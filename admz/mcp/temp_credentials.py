"""Temporary device accounts, tracked in SQLite so they outlive the process.

Creates short-lived device user accounts so the LLM gets usable credentials
without ever seeing the real admin password. A background loop removes expired
accounts from devices; startup reconciliation catches whatever that loop missed.

Why this is persistent (GH #314)
--------------------------------
This was an **in-memory dict**, and all three of its failure modes came from
that one fact:

1. If the process died between create and cleanup the record was gone and the
   account on the device was orphaned with **no trace anywhere in ADMZ** —
   invisible to the roster, to drift, to an audit query.
2. After ``_MAX_CLEANUP_ATTEMPTS`` failures the loop **deleted the record** and
   logged a warning. The device kept a working account and ADMZ discarded its
   only evidence — destroying the information in exactly the case a human most
   needs it.
3. The shutdown sweep lived in an ``except asyncio.CancelledError`` handler, so
   a crash, ``SIGKILL`` or power loss skipped it.

The sharpest instance was not an unlucky race: the MCP server runs as a
**per-principal subprocess reaped after ``ADMZ_MCP_POOL_IDLE_SECONDS``
(default 300 s)**, while the TTL ceiling was 3600 s. A one-hour credential
outlived by 55 minutes the very process holding its only record — the default
configuration meeting a permitted TTL. See :func:`max_ttl_seconds`.

An orphaned temp account is **indistinguishable from a permanent one**: same
group, same capabilities, and Axis devices do not expire accounts. "Temporary"
exists only as ADMZ's intention to come back and delete it, so the record of
that intention is the whole mechanism.

What is deliberately NOT stored
-------------------------------
**The temp password.** Cleanup needs ``device_id`` and ``username`` only —
``_remove_temp_user`` authenticates with the *admin* credential from the
registry, never the temp one. Persisting the temp password would put a live
device credential in the database to no purpose, which is the opposite of
ADR-0010's "we encrypt secrets, not metadata" threshold. It is held in memory
for the single response that returns it to the caller and never written down.

A row read back from SQLite therefore has ``password=""``. That is not a lossy
round trip — nothing reads it.
"""

from __future__ import annotations

import logging
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Axis cameras have a 14-character username limit.
# "at_" prefix (3 chars) + 8 hex chars = 11 chars total → safe.
_USERNAME_PREFIX = "at_"
_USERNAME_HEX_LEN = 8
_PASSWORD_LENGTH = 16
_MAX_PER_DEVICE = 3
_MAX_CLEANUP_ATTEMPTS = 5

#: TTL bounds a caller may ask for, before the ceiling reconciliation below.
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 3600

#: Row states. A record is only ever removed after the device account is
#: confirmed gone; everything else transitions to ``orphaned``.
STATE_ACTIVE = "active"
STATE_ORPHANED = "orphaned"


def _pool_idle_seconds() -> Optional[float]:
    """The MCP pool's idle-reap timeout, or None if it cannot be determined.

    Read through ``chatbot.mcp_pool`` so there is one resolver for this value
    rather than a second copy of the env parsing to keep in step (#255). The
    import is lazy and failure-tolerant: ``admz.mcp`` must not hard-depend on
    ``admz.chatbot``.

    "Am I a pool subprocess?" is answered by ``ADMZ_MCP_NO_SCHEDULER``, which
    ``chatbot/mcp_pool.py`` and ``chatbot/voice.py`` already set on exactly the
    processes the reaper owns. A first draft invented a second env var for this
    and the capability drift guard rejected it as unclassified — correctly,
    since it was a new signal for a question an existing one already answers
    (#255). A standalone ``python -m admz mcp`` has no reaper to outlive, so no
    ceiling applies.
    """
    if not os.getenv("ADMZ_MCP_NO_SCHEDULER"):
        return None
    try:
        from admz.chatbot.mcp_pool import _resolve_idle_seconds
        return float(_resolve_idle_seconds())
    except Exception:  # noqa: BLE001 — absent, unimportable, or misconfigured
        return None


def max_ttl_seconds() -> int:
    """The effective TTL ceiling, reconciled against the pool reaper (#314).

    A credential must not be allowed to outlive the process responsible for
    cleaning it up. The pool reaps an idle MCP subprocess after
    ``ADMZ_MCP_POOL_IDLE_SECONDS`` (default 300 s) while the nominal ceiling is
    3600 s, so the *default* configuration permitted a credential that outlived
    its own tracker by 55 minutes.

    Persistence alone does not close that: the record survives, but nothing
    acts on it until some process next starts and reconciles, which could be
    arbitrarily long. Clamping bounds the exposure directly; reconciliation is
    the backstop for when the clamp cannot apply (no pool, or an operator who
    raised the idle timeout).

    Never returns less than :data:`MIN_TTL_SECONDS` — a ceiling below the floor
    would make every request fail rather than be shortened.
    """
    idle = _pool_idle_seconds()
    if idle is None:
        return MAX_TTL_SECONDS
    return max(MIN_TTL_SECONDS, min(MAX_TTL_SECONDS, int(idle)))


def clamp_ttl(requested: int) -> int:
    """Clamp a requested TTL into the effective window, loudly when shortened."""
    ceiling = max_ttl_seconds()
    value = max(MIN_TTL_SECONDS, min(ceiling, int(requested)))
    if int(requested) > ceiling:
        logger.info(
            "temp credential TTL %ss shortened to %ss: the MCP pool reaps an "
            "idle subprocess sooner, and a credential must not outlive the "
            "process that cleans it up (#314)",
            int(requested), value,
        )
    return value


@dataclass
class TempCredential:
    """A temporary device account.

    ``password`` is populated only on the in-memory object returned at
    creation. It is never persisted and is empty on any row read back.
    """

    device_id: str
    username: str
    password: str
    group: str
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = 300
    cleanup_attempts: int = 0
    state: str = STATE_ACTIVE
    last_error: str = ""

    @property
    def expires_at(self) -> float:
        return self.created_at + self.ttl_seconds

    @property
    def expires_at_iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.expires_at))

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

    @property
    def should_retry_cleanup(self) -> bool:
        return self.cleanup_attempts < _MAX_CLEANUP_ATTEMPTS


_SCHEMA = """
CREATE TABLE IF NOT EXISTS temp_credentials (
    device_id        TEXT NOT NULL,
    username         TEXT NOT NULL,
    grp              TEXT NOT NULL,
    created_at       REAL NOT NULL,
    ttl_seconds      INTEGER NOT NULL,
    cleanup_attempts INTEGER NOT NULL DEFAULT 0,
    state            TEXT NOT NULL DEFAULT 'active',
    last_error       TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (device_id, username)
);
CREATE INDEX IF NOT EXISTS idx_temp_credentials_state
    ON temp_credentials(state);
"""


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


_SELECT = ("SELECT device_id, username, grp, created_at, ttl_seconds, "
           "cleanup_attempts, state, last_error FROM temp_credentials")


def _row_to_cred(row) -> TempCredential:
    return TempCredential(
        device_id=row[0], username=row[1], password="", group=row[2],
        created_at=row[3], ttl_seconds=row[4], cleanup_attempts=row[5],
        state=row[6], last_error=row[7],
    )


class TempCredentialManager:
    """SQLite-backed tracker for temporary device accounts.

    Same connection model as the other ADMZ stores: no I/O in ``__init__``,
    the path resolved at **call** time, short-lived connections, WAL (#258).
    The public API is unchanged from the in-memory version so the one caller
    (``admz/mcp/server.py``) keeps a single way to reach it.
    """

    def __init__(self, db_path: Optional[str] = None):
        """No I/O here — constructing a store must not touch the filesystem
        (#254/#258). Binding the path in ``__init__`` is what froze it against
        an ``ADMZ_HOME`` set afterwards, and is how a test can reach a real
        database."""
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set = set()
        self._ready_lock = threading.Lock()

    @property
    def _db_path(self) -> str:
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
        """Own connection — routing through ``_connect`` would recurse.

        ``_ready`` is keyed by path rather than a boolean so a rebind runs the
        schema against the new file instead of assuming the previous one's
        tables exist.
        """
        conn = sqlite3.connect(path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # --- generation --------------------------------------------------------

    @staticmethod
    def generate_username() -> str:
        return _USERNAME_PREFIX + secrets.token_hex(_USERNAME_HEX_LEN // 2)

    @staticmethod
    def generate_password() -> str:
        return secrets.token_urlsafe(_PASSWORD_LENGTH)[:_PASSWORD_LENGTH]

    # --- reads -------------------------------------------------------------

    def count_active_for_device(self, device_id: str) -> int:
        """Unexpired, non-orphaned records for one device.

        Orphaned rows are excluded on purpose: they represent an account ADMZ
        failed to remove, and counting them toward the per-device limit would
        lock an operator out of creating new credentials because of a past
        failure. They are surfaced by :meth:`list_orphaned` instead.
        """
        now = time.time()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM temp_credentials WHERE device_id=? "
                "AND state=? AND (created_at + ttl_seconds) > ?",
                (device_id, STATE_ACTIVE, now),
            ).fetchone()
        finally:
            conn.close()
        return int(row[0]) if row else 0

    def get_expired(self) -> List[TempCredential]:
        """Active records past their TTL — the cleanup loop's work list."""
        now = time.time()
        conn = self._connect()
        try:
            rows = conn.execute(
                f"{_SELECT} WHERE state=? AND (created_at + ttl_seconds) <= ?",
                (STATE_ACTIVE, now),
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_cred(r) for r in rows]

    def get_all(self) -> List[TempCredential]:
        """Every active record (shutdown sweep + startup reconciliation)."""
        conn = self._connect()
        try:
            rows = conn.execute(
                f"{_SELECT} WHERE state=?", (STATE_ACTIVE,)).fetchall()
        finally:
            conn.close()
        return [_row_to_cred(r) for r in rows]

    def list_orphaned(self) -> List[TempCredential]:
        """Accounts ADMZ created and could not remove.

        This list is the whole point of #314: previously it could not exist,
        because the record was deleted at exactly the moment it became
        interesting.
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                f"{_SELECT} WHERE state=?", (STATE_ORPHANED,)).fetchall()
        finally:
            conn.close()
        return [_row_to_cred(r) for r in rows]

    def list_active(self, device_id: Optional[str] = None) -> List[Dict]:
        """Metadata for tracked creds (never includes passwords — none stored).

        Includes orphaned rows, flagged, because a caller asking "what temp
        accounts exist on this device?" needs the ones ADMZ failed to remove
        more than the ones it will remove on schedule.
        """
        conn = self._connect()
        try:
            if device_id:
                rows = conn.execute(
                    f"{_SELECT} WHERE device_id=?", (device_id,)).fetchall()
            else:
                rows = conn.execute(_SELECT).fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            cred = _row_to_cred(r)
            out.append({
                "device_id": cred.device_id,
                "username": cred.username,
                "group": cred.group,
                "created_at": cred.created_at,
                "ttl_seconds": cred.ttl_seconds,
                "expires_at": cred.expires_at_iso,
                "is_expired": cred.is_expired,
                "state": cred.state,
                "cleanup_attempts": cred.cleanup_attempts,
                "last_error": cred.last_error,
            })
        return out

    # --- writes ------------------------------------------------------------

    def register(self, cred: TempCredential) -> None:
        """Record a created account. The password is deliberately not stored."""
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO temp_credentials (device_id, username, grp, "
                "created_at, ttl_seconds, cleanup_attempts, state, last_error) "
                "VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(device_id, username) DO UPDATE SET "
                "grp=excluded.grp, created_at=excluded.created_at, "
                "ttl_seconds=excluded.ttl_seconds, cleanup_attempts=0, "
                "state=excluded.state, last_error=''",
                (cred.device_id, cred.username, cred.group, cred.created_at,
                 int(cred.ttl_seconds), 0, STATE_ACTIVE, ""),
            )
            conn.commit()
        finally:
            conn.close()

    def remove(self, device_id: str, username: str) -> Optional[TempCredential]:
        """Delete a record. **Only** after the device account is confirmed gone.

        Never call this on a cleanup failure — that is the #314 defect. Use
        :meth:`mark_orphaned`.
        """
        conn = self._connect()
        try:
            row = conn.execute(
                f"{_SELECT} WHERE device_id=? AND username=?",
                (device_id, username)).fetchone()
            if row is None:
                return None
            conn.execute(
                "DELETE FROM temp_credentials WHERE device_id=? AND username=?",
                (device_id, username))
            conn.commit()
        finally:
            conn.close()
        return _row_to_cred(row)

    def record_cleanup_failure(self, device_id: str, username: str,
                               error: str = "") -> int:
        """Increment the attempt counter. Returns the new count."""
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE temp_credentials SET cleanup_attempts = "
                "cleanup_attempts + 1, last_error=? "
                "WHERE device_id=? AND username=?",
                (str(error)[:200], device_id, username))
            conn.commit()
            row = conn.execute(
                "SELECT cleanup_attempts FROM temp_credentials "
                "WHERE device_id=? AND username=?",
                (device_id, username)).fetchone()
        finally:
            conn.close()
        return int(row[0]) if row else 0

    def mark_orphaned(self, device_id: str, username: str,
                      error: str = "") -> None:
        """Give up removing this account, but **keep the record** (#314).

        The account still exists on the device. Deleting the row here — which
        is what the code used to do — destroys ADMZ's only evidence of an
        account it created and could not remove.
        """
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE temp_credentials SET state=?, last_error=? "
                "WHERE device_id=? AND username=?",
                (STATE_ORPHANED, str(error)[:200], device_id, username))
            conn.commit()
        finally:
            conn.close()
        logger.error(
            "ORPHANED temp account %s on device %s: ADMZ created it and could "
            "not remove it after %d attempts. The account still exists on the "
            "device with group-level access and Axis devices do not expire "
            "accounts — remove it by hand. The record is retained (#314) and "
            "is listed by list_temp_credentials.",
            username, device_id, _MAX_CLEANUP_ATTEMPTS,
        )

    @property
    def max_per_device(self) -> int:
        return _MAX_PER_DEVICE

    @property
    def max_cleanup_attempts(self) -> int:
        return _MAX_CLEANUP_ATTEMPTS
