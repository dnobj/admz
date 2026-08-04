"""Server-side web sessions for browser logins (ADR-0033).

A session is minted after a successful Windows-credential login
(:mod:`admz.win_auth`) and carried by the ``admz_session`` cookie. The
cookie value is a 256-bit random bearer token; only its SHA-256 hash is
stored, so a copy of ``admz.db`` cannot be replayed into a session
(mirrors the API-key posture, but SHA-256 suffices here: the token is
high-entropy random, not a human secret, so no slow KDF is needed).

The stored row carries a JSON snapshot of the authenticated
:class:`~admz.auth.Principal` (name / display_name / domain / groups /
source) — the same fields the chat layer forwards to the MCP subprocess
via ``ADMZ_PRINCIPAL_*``. Group membership is therefore frozen at login
time (like API-key group snapshots); re-login refreshes it.

Sessions are revocable (logout) and expire after
``ADMZ_SESSION_TTL_SECONDS`` (default 12 h) of inactivity — ``resolve``
slides ``last_seen_at`` forward, so an active operator isn't logged out
mid-day while an abandoned session dies on schedule.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


SESSION_COOKIE = "admz_session"

_DEFAULT_TTL_SECONDS = 12 * 60 * 60  # 12 hours


def _ttl_seconds() -> float:
    raw = os.getenv("ADMZ_SESSION_TTL_SECONDS", "")
    if not raw:
        return float(_DEFAULT_TTL_SECONDS)
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "ADMZ_SESSION_TTL_SECONDS=%r is not a number; using %ds default",
            raw, _DEFAULT_TTL_SECONDS,
        )
        return float(_DEFAULT_TTL_SECONDS)
    if value <= 0:
        return float(_DEFAULT_TTL_SECONDS)
    return value


_SCHEMA = """
CREATE TABLE IF NOT EXISTS web_sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash     TEXT NOT NULL UNIQUE,
    principal_json TEXT NOT NULL,
    created_at     REAL NOT NULL,
    expires_at     REAL NOT NULL,
    last_seen_at   REAL NOT NULL,
    revoked        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_web_sessions_hash ON web_sessions(token_hash);
"""


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class SessionPrincipal:
    """The principal snapshot a session resolves to."""

    name: str
    display_name: str
    domain: Optional[str]
    groups: List[str]
    source: str


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


class SessionStore:
    """SQLite-backed web sessions. Same connection model as the other
    SQLite stores: short-lived connections per call, WAL mode."""

    def __init__(self, db_path: Optional[str] = None):
        """No I/O here -- constructing a store must not touch the filesystem
        (#254/#258). This one had no ``_ensure_table``: it ran the schema
        inline in ``__init__``, which is the same defect in a different shape.
        """
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set = set()
        self._ready_lock = threading.Lock()

    @property
    def _db_path(self) -> str:
        """Resolved at CALL time, not cached at construction (#258).

        Stays a ``str`` -- callers read this attribute and hand it straight to
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
        """Open our own connection -- via ``_connect`` this would recurse.

        ``_ready`` is keyed by path rather than a boolean, so a rebind runs
        the schema against the new file. No column migration on this table.
        """
        conn = sqlite3.connect(path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _ensure_table(self) -> None:
        """Parity with the other sixteen stores; ensuring happens inside
        :meth:`_connect`."""
        self._connect().close()

    # ---- create ---------------------------------------------------------

    def create(self, principal) -> str:
        """Mint a session for an authenticated principal; returns the
        plaintext bearer token (set it as the cookie — it exists nowhere
        else). ``principal`` is any object with name/display_name/domain/
        groups/source attributes (an :class:`admz.auth.Principal`)."""
        token = secrets.token_urlsafe(32)
        now = time.time()
        snapshot = {
            "name": getattr(principal, "name", ""),
            "display_name": getattr(principal, "display_name", ""),
            "domain": getattr(principal, "domain", None),
            "groups": list(getattr(principal, "groups", []) or []),
            "source": getattr(principal, "source", "windows-local"),
        }
        if not snapshot["name"]:
            raise ValueError("principal.name is required for a session")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO web_sessions "
                "(token_hash, principal_json, created_at, expires_at, "
                " last_seen_at, revoked) VALUES (?, ?, ?, ?, ?, 0)",
                (
                    _hash_token(token),
                    json.dumps(snapshot),
                    now,
                    now + _ttl_seconds(),
                    now,
                ),
            )
            conn.commit()
        return token

    # ---- resolve --------------------------------------------------------

    def resolve(self, token: str) -> Optional[SessionPrincipal]:
        """Return the principal snapshot for a live session, sliding the
        expiry forward; None for unknown/expired/revoked tokens."""
        if not token:
            return None
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, principal_json, expires_at, revoked "
                "FROM web_sessions WHERE token_hash=?",
                (_hash_token(token),),
            ).fetchone()
            if row is None:
                return None
            sid, principal_json, expires_at, revoked = row
            if revoked or now > expires_at:
                return None
            # Sliding expiry: activity keeps the session alive.
            conn.execute(
                "UPDATE web_sessions SET last_seen_at=?, expires_at=? "
                "WHERE id=?",
                (now, now + _ttl_seconds(), sid),
            )
            conn.commit()
        try:
            data = json.loads(principal_json)
        except json.JSONDecodeError:  # pragma: no cover — defensive
            logger.warning("web_sessions row %s holds invalid JSON", sid)
            return None
        return SessionPrincipal(
            name=data.get("name", ""),
            display_name=data.get("display_name", "") or data.get("name", ""),
            domain=data.get("domain"),
            groups=list(data.get("groups", []) or []),
            source=data.get("source", "windows-local"),
        )

    # ---- revoke / maintenance -------------------------------------------

    def revoke(self, token: str) -> bool:
        """Revoke (logout). Returns True if a live row was revoked."""
        if not token:
            return False
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE web_sessions SET revoked=1 "
                "WHERE token_hash=? AND revoked=0",
                (_hash_token(token),),
            )
            conn.commit()
            return cur.rowcount > 0

    def purge_expired(self) -> int:
        """Delete expired + revoked rows; returns the count removed."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM web_sessions WHERE revoked=1 OR expires_at < ?",
                (time.time(),),
            )
            conn.commit()
            return cur.rowcount


# Lazy module singleton (H-2 lesson: importing a module must not create
# ~/.admz/admz.db as a side effect). Tests reset via set_session_store().
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store


def set_session_store(store: Optional[SessionStore]) -> None:
    """Test seam: inject a store on a tmp DB (None resets to lazy default)."""
    global _session_store
    _session_store = store
