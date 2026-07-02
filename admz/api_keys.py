"""API-key store for programmatic clients (agents, automation, integrations).

Keys are minted by Windows-authenticated operators via the web UI and
handed to agents that need to call the ADMZ REST API. They are an
alternative to Windows IWA for callers that don't have a Windows
session — e.g. an LLM agent running in the cloud.

The token format is ``admz_<43 url-safe chars>`` — a fixed prefix for
easy log-greppability followed by 32 bytes of entropy (~256 bits).
Only the hash is stored at rest (PBKDF2-SHA256, 600 000 iterations).

Schema (lives in the shared ADMZ SQLite database alongside ``devices``,
``capture_sessions``, ``confirm_sessions``, and ``fleet_settings``)::

    api_keys
    --------
    id            INTEGER PRIMARY KEY AUTOINCREMENT
    key_hash      TEXT     -- "salt_hex:hash_hex"
    display_name  TEXT     -- shown in the UI ("nightly-snapshot-bot")
    created_by    TEXT     -- the Windows principal who minted it
    created_at    REAL     -- unix timestamp
    expires_at    REAL     -- optional; NULL == never expires
    last_used_at  REAL     -- updated on each successful auth
    revoked       INTEGER  -- 0/1
    scopes        TEXT     -- reserved; "*" for v1
    groups_json   TEXT     -- snapshot of creator's groups (for RBAC)

Concurrency: short-lived connections (WAL mode), same pattern as
``capture_store`` / ``confirm_store`` / ``fleet_settings``.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


_API_KEY_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash      TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    created_by    TEXT NOT NULL,
    created_at    REAL NOT NULL,
    expires_at    REAL,
    last_used_at  REAL,
    revoked       INTEGER NOT NULL DEFAULT 0,
    scopes        TEXT NOT NULL DEFAULT '*',
    groups_json   TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_api_keys_revoked ON api_keys(revoked);
"""

_HASH_ALGO = "sha256"
_HASH_ITERATIONS = 600_000
_SALT_BYTES = 16

_KEY_PREFIX = "admz_"
_KEY_ENTROPY_BYTES = 32


# ---------------------------------------------------------------------------
# Hashing helpers (mirror the confirm-password helpers in confirm_store)
# ---------------------------------------------------------------------------


def _hash_key(plaintext: str) -> str:
    """PBKDF2-SHA256 hash. Stored format: ``salt_hex:hash_hex``."""
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        _HASH_ALGO, plaintext.encode(), salt, _HASH_ITERATIONS
    )
    return salt.hex() + ":" + dk.hex()


def _verify_key(plaintext: str, stored_hash: str) -> bool:
    try:
        salt_hex, dk_hex = stored_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
    except (ValueError, AttributeError):
        return False

    dk = hashlib.pbkdf2_hmac(
        _HASH_ALGO, plaintext.encode(), salt, _HASH_ITERATIONS
    )
    return secrets.compare_digest(dk, expected)


def _generate_key() -> str:
    """Return a fresh ``admz_<43-char-random>`` key string."""
    return _KEY_PREFIX + secrets.token_urlsafe(_KEY_ENTROPY_BYTES)


def looks_like_api_key(value: str) -> bool:
    """Cheap prefix check so we don't PBKDF2-hash arbitrary garbage."""
    return isinstance(value, str) and value.startswith(_KEY_PREFIX)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class ApiKey:
    """A row in the ``api_keys`` table.

    Note: ``key_hash`` is the stored hash. The plaintext key is only
    returned by :meth:`ApiKeyStore.create` — never readable afterwards.
    """

    id: int
    display_name: str
    created_by: str
    created_at: float
    key_hash: str = ""
    expires_at: Optional[float] = None
    last_used_at: Optional[float] = None
    revoked: bool = False
    scopes: str = "*"
    groups: List[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and time.time() > self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.revoked and not self.is_expired


@dataclass
class CreatedApiKey:
    """The one-time return value of :meth:`ApiKeyStore.create`.

    The ``plaintext`` field is the only place the unhashed key ever
    exists in the system — show it to the operator once and discard.
    """

    record: ApiKey
    plaintext: str


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


class ApiKeyStore:
    """SQLite-backed CRUD for API keys.

    Same connection model as the other SQLite stores: short-lived
    connections per call, WAL mode, so multiple ADMZ processes (e.g.
    a future split between MCP and API) can safely share the file.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        # Defensive: ensure parent dir exists so the SQLite connect
        # doesn't fail on a fresh install where ~/.admz/ hasn't been
        # created yet by another component.
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        with self._connect() as conn:
            conn.executescript(_API_KEY_SCHEMA)
            conn.commit()

    # ---- create -------------------------------------------------------

    def create(
        self,
        display_name: str,
        created_by: str,
        *,
        expires_at: Optional[float] = None,
        groups: Optional[List[str]] = None,
    ) -> CreatedApiKey:
        """Generate a new key. The plaintext is in the return value
        and **nowhere else** — callers must show it to the operator
        immediately."""
        if not display_name or not display_name.strip():
            raise ValueError("display_name must be a non-empty string")
        if not created_by:
            raise ValueError("created_by is required for audit")

        plaintext = _generate_key()
        key_hash = _hash_key(plaintext)
        created_at = time.time()
        groups = list(groups or [])

        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO api_keys "
                "(key_hash, display_name, created_by, created_at, expires_at, "
                "last_used_at, revoked, scopes, groups_json) "
                "VALUES (?, ?, ?, ?, ?, NULL, 0, '*', ?)",
                (
                    key_hash, display_name.strip(), created_by, created_at,
                    expires_at, json.dumps(groups),
                ),
            )
            conn.commit()
            new_id = cursor.lastrowid

        record = ApiKey(
            id=new_id,
            display_name=display_name.strip(),
            created_by=created_by,
            created_at=created_at,
            key_hash=key_hash,
            expires_at=expires_at,
            last_used_at=None,
            revoked=False,
            scopes="*",
            groups=groups,
        )
        return CreatedApiKey(record=record, plaintext=plaintext)

    # ---- list / get ---------------------------------------------------

    def list(self, *, include_revoked: bool = False) -> List[ApiKey]:
        sql = (
            "SELECT id, key_hash, display_name, created_by, created_at, "
            "expires_at, last_used_at, revoked, scopes, groups_json "
            "FROM api_keys"
        )
        if not include_revoked:
            sql += " WHERE revoked = 0"
        sql += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [self._row_to_apikey(r) for r in rows]

    def get(self, id_: int) -> Optional[ApiKey]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, key_hash, display_name, created_by, created_at, "
                "expires_at, last_used_at, revoked, scopes, groups_json "
                "FROM api_keys WHERE id = ?",
                (id_,),
            ).fetchone()
        return self._row_to_apikey(row) if row else None

    # ---- authenticate -------------------------------------------------

    def authenticate(self, plaintext: str) -> Optional[ApiKey]:
        """Find the row matching ``plaintext`` and return it if active.

        Returns None if no key matches, the key is revoked, or it has
        expired. Side-effect: ``last_used_at`` is bumped to now.
        """
        if not looks_like_api_key(plaintext):
            return None

        # Linear scan with PBKDF2 verify. For v1 this is acceptable —
        # a typical install will have a handful of keys, not thousands.
        # A future O(1) lookup could add a "lookup hash" (HMAC of key
        # with a server-wide secret) as an indexed column.
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, key_hash, display_name, created_by, created_at, "
                "expires_at, last_used_at, revoked, scopes, groups_json "
                "FROM api_keys WHERE revoked = 0"
            ).fetchall()

            for row in rows:
                key_hash = row[1]
                if _verify_key(plaintext, key_hash):
                    key = self._row_to_apikey(row)
                    if not key.is_active:
                        return None
                    now = time.time()
                    conn.execute(
                        "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                        (now, key.id),
                    )
                    conn.commit()
                    key.last_used_at = now
                    return key

        return None

    # ---- revoke / delete ----------------------------------------------

    def revoke(self, id_: int) -> bool:
        """Mark a key revoked. Returns False if the key doesn't exist
        or is already revoked."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE api_keys SET revoked = 1 "
                "WHERE id = ? AND revoked = 0",
                (id_,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, id_: int) -> bool:
        """Hard-delete a row. Use sparingly — revoke preserves audit history."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM api_keys WHERE id = ?", (id_,))
            conn.commit()
            return cursor.rowcount > 0

    # ---- helpers ------------------------------------------------------

    @staticmethod
    def _row_to_apikey(row) -> ApiKey:
        if row is None:
            return None  # type: ignore[return-value]
        try:
            groups = json.loads(row[9])
        except (json.JSONDecodeError, TypeError):
            groups = []
        return ApiKey(
            id=row[0],
            key_hash=row[1],
            display_name=row[2],
            created_by=row[3],
            created_at=row[4],
            expires_at=row[5],
            last_used_at=row[6],
            revoked=bool(row[7]),
            scopes=row[8],
            groups=groups,
        )


# Module-level singleton — matches the pattern of capture_store /
# confirm_store / fleet_settings.
api_key_store = ApiKeyStore()
