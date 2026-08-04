"""
Multi-level confirmation gate for dangerous operations.

This module provides a SQLite-backed session store for operation
confirmations.  The strictest levels (url_and_password, url_only)
require the user to click a URL and optionally enter a password in
their browser — the LLM can only *poll* these sessions, not complete
them.

Confirmation levels (from strictest to most permissive):

  url_and_password  – click URL + enter password in browser
  url_only          – click URL + click "Confirm" in browser
  llm_confirm       – LLM calls confirm tool (current behaviour)
  none              – execute immediately, no gate

Default mapping from risk level → confirmation level:

  dangerous         → url_and_password
  service-affecting → url_only
  normal            → none
  read-only         → none
  action            → url_only   (ACS Pro and other server-target families)
  read              → none       (ditto)

The table itself lives in :mod:`admz.confirm_policy`, a leaf module, so that
``fleet_settings`` can derive the protected ``confirm_level_*`` keys from it
without an import cycle. It is re-exported below under its original name.

Both `dangerous` and `service-affecting` default to a URL/widget flow so that
consent for any device-affecting operation is a deterministic, human-only step
(the LLM cannot self-approve a url_* gate) rather than an LLM judgement call.
Operators can relax this per risk class via the ``confirm_level_<risk>`` fleet
setting (e.g. back to ``llm_confirm`` for lower-friction in-chat confirmation).
"""

import hashlib
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Optional


# ── Defaults ────────────────────────────────────────────────────────────

# The risk → confirmation-level table and the valid-level vocabulary moved to
# admz/confirm_policy.py, a leaf that imports nothing from admz. This module
# already imports fleet_settings at module scope (see the re-export below), so
# fleet_settings cannot import *this* module to derive the protected
# confirm_level_* keys from the table — that direction is an import cycle. The
# vocabulary moved down to a shared leaf instead, and is re-exported here under
# its original name for the callers (and tests) that import it from here.
# Same pattern, and same reason, as the PROTECTED_SETTING_KEYS re-export.
from admz.confirm_policy import (  # noqa: E402,F401
    _DEFAULT_CONFIRMATION_LEVELS,
    VALID_CONFIRMATION_LEVELS,
    CONFIRM_LEVEL_KEY_PREFIX,
    confirm_level_key,
    is_confirm_level_key,
)

# Fleet-setting keys that are protected from anonymous / MCP writes.
# CR-3: relocated to admz/fleet_settings.py so the concept lives next
# to the rest of fleet-settings policy. Kept as a re-export here for
# back-compat with the many callers that still do
# ``from admz.api.confirm_store import PROTECTED_SETTING_KEYS``.
from admz.fleet_settings import (  # noqa: E402,F401
    PROTECTED_SETTING_KEYS,
    is_protected_setting,
)


class ConfirmStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass
class ConfirmSession:
    """A single operation confirmation session."""

    token: str
    device_id: str
    operation_id: str
    family: str
    params_json: str
    risk_level: str
    confirmation_level: str
    danger_description: str = ""
    plan_id: str = ""
    plan_summary_json: str = ""
    plan_steps_json: str = ""
    # ADR-0034: registry-level actions (accept_baseline, delete_device)
    # gated through the same widget. JSON: {"action": "...", ...payload}.
    action_json: str = ""
    created_at: float = field(default_factory=time.time)
    ttl: float = 300.0  # 5 minutes
    status: ConfirmStatus = ConfirmStatus.PENDING
    confirmed_by: str = ""

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl

    @property
    def effective_status(self) -> ConfirmStatus:
        # Completed and denied are terminal — they hold past the TTL so a
        # late status poll still reports what actually happened.
        if self.status in (ConfirmStatus.COMPLETED, ConfirmStatus.DENIED):
            return self.status
        if self.is_expired:
            return ConfirmStatus.EXPIRED
        return ConfirmStatus.PENDING

    @property
    def params(self) -> Dict[str, str]:
        """Deserialise the stored params JSON."""
        try:
            return json.loads(self.params_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @property
    def is_plan(self) -> bool:
        """True if this session confirms a multi-step plan."""
        return self.plan_id != ""

    @property
    def is_action(self) -> bool:
        """True if this session confirms a registry-level action
        (ADR-0034: accept_baseline, delete_device)."""
        return self.action_json != ""

    @property
    def action(self) -> dict:
        """Deserialise the stored action JSON."""
        try:
            return json.loads(self.action_json) if self.action_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @property
    def plan_summary(self) -> dict:
        """Deserialise the stored plan summary JSON."""
        try:
            return json.loads(self.plan_summary_json) if self.plan_summary_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}


_CONFIRM_SCHEMA = """
CREATE TABLE IF NOT EXISTS confirm_sessions (
    token               TEXT PRIMARY KEY,
    device_id           TEXT NOT NULL,
    operation_id        TEXT NOT NULL,
    family              TEXT NOT NULL DEFAULT 'vapix',
    params_json         TEXT NOT NULL DEFAULT '{}',
    risk_level          TEXT NOT NULL,
    confirmation_level  TEXT NOT NULL,
    danger_description  TEXT NOT NULL DEFAULT '',
    plan_id             TEXT NOT NULL DEFAULT '',
    plan_summary_json   TEXT NOT NULL DEFAULT '',
    plan_steps_json     TEXT NOT NULL DEFAULT '',
    action_json         TEXT NOT NULL DEFAULT '',
    created_at          REAL NOT NULL,
    ttl                 REAL NOT NULL DEFAULT 300.0,
    status              TEXT NOT NULL DEFAULT 'pending',
    confirmed_by        TEXT NOT NULL DEFAULT ''
);
"""


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


class ConfirmStore:
    """
    SQLite-backed store for operation confirmation sessions.

    Uses the same database file as the device registry and capture store
    so that both the MCP server (stdio) and the API server (uvicorn) can
    see the same sessions.  WAL mode allows concurrent readers/writers.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        from admz.paths import ensure_parent_dir
        ensure_parent_dir(self._db_path)
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self):
        conn = self._connect()
        try:
            conn.executescript(_CONFIRM_SCHEMA)
            # Migration: add later columns to existing tables
            for col, ddl in (
                ("plan_summary_json", "TEXT NOT NULL DEFAULT ''"),
                ("plan_steps_json",   "TEXT NOT NULL DEFAULT ''"),
                ("action_json",       "TEXT NOT NULL DEFAULT ''"),
            ):
                try:
                    conn.execute(
                        f"ALTER TABLE confirm_sessions ADD COLUMN {col} {ddl}"
                    )
                    conn.commit()
                except sqlite3.OperationalError:
                    pass  # column already exists
            conn.commit()
        finally:
            conn.close()

    def create_session(
        self,
        device_id: str,
        operation_id: str,
        family: str,
        params: Dict[str, str],
        risk_level: str,
        confirmation_level: str,
        danger_description: str = "",
        plan_id: str = "",
        plan_summary_json: str = "",
        plan_steps_json: str = "",
        action_json: str = "",
        ttl: float = 300.0,
    ) -> ConfirmSession:
        """Create a new confirmation session and return it."""
        self._cleanup()

        token = secrets.token_urlsafe(32)
        now = time.time()
        params_json = json.dumps(params)

        session = ConfirmSession(
            token=token,
            device_id=device_id,
            operation_id=operation_id,
            family=family,
            params_json=params_json,
            risk_level=risk_level,
            confirmation_level=confirmation_level,
            danger_description=danger_description,
            plan_id=plan_id,
            plan_summary_json=plan_summary_json,
            plan_steps_json=plan_steps_json,
            action_json=action_json,
            created_at=now,
            ttl=ttl,
        )

        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO confirm_sessions "
                "(token, device_id, operation_id, family, params_json, "
                "risk_level, confirmation_level, danger_description, plan_id, "
                "plan_summary_json, plan_steps_json, action_json, "
                "created_at, ttl, status, confirmed_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    token, device_id, operation_id, family, params_json,
                    risk_level, confirmation_level, danger_description, plan_id,
                    plan_summary_json, plan_steps_json, action_json,
                    now, ttl, "pending", "",
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return session

    def get_session(self, token: str) -> Optional[ConfirmSession]:
        """Look up a session by token.  Returns None if not found or expired."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT token, device_id, operation_id, family, params_json, "
                "risk_level, confirmation_level, danger_description, plan_id, "
                "plan_summary_json, plan_steps_json, created_at, ttl, status, confirmed_by, "
                "action_json "
                "FROM confirm_sessions WHERE token=?",
                (token,),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None

        session = ConfirmSession(
            token=row[0],
            device_id=row[1],
            operation_id=row[2],
            family=row[3],
            params_json=row[4],
            risk_level=row[5],
            confirmation_level=row[6],
            danger_description=row[7],
            plan_id=row[8],
            plan_summary_json=row[9],
            plan_steps_json=row[10],
            created_at=row[11],
            ttl=row[12],
            status=ConfirmStatus(row[13]),
            confirmed_by=row[14],
            action_json=row[15] or "",
        )

        if session.is_expired and session.status not in (
            ConfirmStatus.COMPLETED, ConfirmStatus.DENIED
        ):
            return None

        return session

    def complete_session(self, token: str, confirmed_by: str = "web") -> bool:
        """
        Mark a session as completed, and **strip its payload** (GH #266).

        Uses UPDATE ... WHERE status='pending' for concurrency safety —
        only the first caller succeeds.  Returns False if the session is
        not found, already completed, or expired.

        The four payload columns are cleared in the SAME statement as the status
        transition, deliberately: the ``status='pending'`` guard then makes the
        strip fire exactly once, exactly on the transition, and **never on a
        pending row**. A separate UPDATE could run without the transition, and
        ``plan_steps_json`` is the cross-process transport — the approving
        uvicorn process may not be the MCP subprocess that built the plan, and it
        reconstructs the plan from this row — so stripping early would break
        execution outright. After approval it is inert.

        WHY strip at all: ``_cleanup`` never deletes a completed row, so before
        this every approved action's arguments — device parameters, rule
        definitions, webhook URLs, whole restore plans — persisted in ``admz.db``
        indefinitely, in the same file as the device registry, with nothing
        redacting them. The row survives as a **receipt** (token, status,
        confirmed_by, operation_id, device_id, timestamps); what it was *for* is
        recorded key-only on the ``confirm.approve`` audit row (#270), joined
        back to this row by the token.

        SAFE ONLY BECAUSE OF THE CALLER ORDERING: every consumer of the payload
        works from the ``ConfirmSession`` object fetched *before* this runs
        (``routes/confirm.py`` get_session -> complete_session ->
        execute_approved_session; same shape in ``operations.py``). This method
        only touches the database, never that in-memory object. A future
        refactor that re-fetches the session after completion would silently get
        an empty payload — ``tests/test_confirm_payload_strip.py`` pins the
        ordering for exactly that reason.
        """
        session = self.get_session(token)
        if session is None or session.effective_status != ConfirmStatus.PENDING:
            return False

        conn = self._connect()
        try:
            cursor = conn.execute(
                "UPDATE confirm_sessions "
                "SET status=?, confirmed_by=?, "
                # params_json keeps a valid empty JSON object; the other three
                # are '' — the schema default for each, and what their accessors
                # already treat as "nothing stored".
                "    params_json='{}', action_json='', "
                "    plan_summary_json='', plan_steps_json='' "
                "WHERE token=? AND status='pending'",
                ("completed", confirmed_by, token),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def deny_session(self, token: str, denied_by: str = "web") -> bool:
        """Mark a PENDING session as denied — the user explicitly declined.

        Terminal like completed (a denied token can never be consumed).
        Same concurrency guard as :meth:`complete_session`: only the first
        state transition wins. Returns False when the session is missing,
        expired, or already resolved.
        """
        session = self.get_session(token)
        if session is None or session.effective_status != ConfirmStatus.PENDING:
            return False

        conn = self._connect()
        try:
            cursor = conn.execute(
                "UPDATE confirm_sessions "
                "SET status=?, confirmed_by=? "
                "WHERE token=? AND status='pending'",
                ("denied", denied_by, token),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_session_by_plan(self, plan_id: str) -> Optional[ConfirmSession]:
        """Look up a pending session by plan_id."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT token, device_id, operation_id, family, params_json, "
                "risk_level, confirmation_level, danger_description, plan_id, "
                "plan_summary_json, plan_steps_json, created_at, ttl, status, confirmed_by, "
                "action_json "
                "FROM confirm_sessions WHERE plan_id=? AND status='pending' "
                "ORDER BY created_at DESC LIMIT 1",
                (plan_id,),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None

        session = ConfirmSession(
            token=row[0],
            device_id=row[1],
            operation_id=row[2],
            family=row[3],
            params_json=row[4],
            risk_level=row[5],
            confirmation_level=row[6],
            danger_description=row[7],
            plan_id=row[8],
            plan_summary_json=row[9],
            plan_steps_json=row[10],
            created_at=row[11],
            ttl=row[12],
            status=ConfirmStatus(row[13]),
            confirmed_by=row[14],
            action_json=row[15] or "",
        )

        if session.is_expired:
            return None

        return session

    def _cleanup(self):
        """Delete **un-acted-on** sessions that expired more than 60s ago.

        Note the ``status != 'completed'`` predicate: a completed session is
        never deleted, so the retention rule is the opposite of what the name
        suggests — abandoned sessions are reaped on a 300s TTL, approved ones are
        kept forever. That is deliberate (the row is the approval **receipt**),
        but it was not always stated: this docstring used to read "Remove
        sessions that expired more than 60s ago", i.e. it described what the code
        would do *without* the exclusion, which is what made the predicate look
        like an inverted bug rather than a retention choice (GH #266). The
        exclusion arrived in the original confirm-store commit with no recorded
        rationale, and nothing else documented it.

        What made keeping them forever *safe* is that ``complete_session`` now
        strips the payload columns on the way in, so a retained row carries who
        approved what and when, and none of the arguments.

        Rows completed BEFORE that change still hold their payload — this is
        forward-only by design. Rewriting them is a destructive migration over
        production data and is the operator's call, not this method's.
        """
        cutoff = time.time() - 60
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM confirm_sessions "
                "WHERE status != 'completed' AND (created_at + ttl) < ?",
                (cutoff,),
            )
            conn.commit()
        finally:
            conn.close()


# ── Password hashing helpers ────────────────────────────────────────────

_HASH_ALGO = "sha256"
_HASH_ITERATIONS = 600_000


def hash_confirm_password(password: str) -> str:
    """Hash a confirmation password using PBKDF2.  Returns 'salt:hash' hex."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(
        _HASH_ALGO, password.encode(), salt, _HASH_ITERATIONS
    )
    return salt.hex() + ":" + dk.hex()


def verify_confirm_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored 'salt:hash' string."""
    try:
        salt_hex, dk_hex = stored_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
    except (ValueError, AttributeError):
        return False

    dk = hashlib.pbkdf2_hmac(
        _HASH_ALGO, password.encode(), salt, _HASH_ITERATIONS
    )
    return dk == expected


# ── Confirmation level lookup ───────────────────────────────────────────

def get_confirmation_level(risk_level: str) -> str:
    """
    Return the effective confirmation level for a given risk level.

    Checks fleet_settings for overrides (e.g. 'confirm_level_dangerous'),
    falling back to built-in defaults.
    """
    from admz.fleet_settings import fleet_settings

    key = f"confirm_level_{risk_level}"
    override = fleet_settings.get(key)
    if override and override in VALID_CONFIRMATION_LEVELS:
        return override

    return _DEFAULT_CONFIRMATION_LEVELS.get(risk_level, "none")


# Module-level singleton.
confirm_store = ConfirmStore()
