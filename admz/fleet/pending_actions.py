"""Pending device actions — one-shot, trigger-based deferred actions.

A pending action is a **pre-authorized** follow-up to run on a device when a
condition becomes true (e.g. "when it comes back in needsetup, re-provision
it"). It exists so a long, reboot-spanning operation (a factory reset) doesn't
block a chat turn: the operator approves the whole sequence up front, and the
health monitor's sweep fires the follow-up when the device's state matches the
trigger.

SECURITY: creation must only happen AFTER the operator approved the FULL
sequence at the confirm gate (`admz/api/routes/confirm.py`). This store is a
storage + firing primitive and does NOT itself gate. Firing runs the
pre-authorized action with NO new prompt (no one is present), so the upstream
approval must cover every step. Every action carries an expiry, fires once
(atomic claim), is cancellable, and is audited.

The health monitor is the evaluator (`admz/fleet/health.py` sweep). If the
monitor is disabled, pending actions sit until they expire.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

# --- trigger conditions (device state that fires the action) ----------------
TRIGGER_NEEDS_SETUP = "on_needs_setup"   # device came back factory-defaulted
TRIGGER_ONLINE = "on_online"             # device reachable + auth OK
VALID_TRIGGERS = {TRIGGER_NEEDS_SETUP, TRIGGER_ONLINE}


def trigger_for_status(status: str) -> Optional[str]:
    """The trigger a device health status satisfies, or None. (online already
    means auth-confirmed in the health model, so it covers 'auth ok'.)"""
    if status == "needs_setup":
        return TRIGGER_NEEDS_SETUP
    if status == "online":
        return TRIGGER_ONLINE
    return None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_device_actions (
    id              TEXT PRIMARY KEY,
    device_id       TEXT NOT NULL,
    action_json     TEXT NOT NULL,
    trigger         TEXT NOT NULL,
    baseline_bootid TEXT NOT NULL DEFAULT '',
    approved_by     TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    created_at      REAL NOT NULL,
    expires_at      REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    last_error      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_pending_device
    ON pending_device_actions(device_id, status);
"""

_COLS = (
    "id, device_id, action_json, trigger, baseline_bootid, approved_by, "
    "description, created_at, expires_at, status, last_error"
)
_COL_KEYS = [c.strip() for c in _COLS.split(",")]

DEFAULT_TTL_SECONDS = 24 * 3600.0


def _default_db_path() -> Path:
    return Path(os.getenv("ADMZ_DB_PATH", str(Path.home() / ".admz" / "admz.db")))


def _row_to_dict(row) -> Dict[str, Any]:
    d = dict(zip(_COL_KEYS, row))
    try:
        d["action"] = json.loads(d["action_json"]) if d["action_json"] else {}
    except Exception:  # noqa: BLE001
        d["action"] = {}
    return d


class PendingActionStore:
    """SQLite-backed store for deferred device actions (shares ``admz.db``)."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self):
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def create(
        self,
        *,
        device_id: str,
        action: Dict[str, Any],
        trigger: str,
        approved_by: str = "",
        description: str = "",
        baseline_bootid: str = "",
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ) -> str:
        """Record a pre-authorized deferred action. Returns its id."""
        if trigger not in VALID_TRIGGERS:
            raise ValueError(f"unknown trigger {trigger!r}")
        pid = uuid.uuid4().hex
        now = time.time()
        conn = self._connect()
        try:
            conn.execute(
                f"INSERT INTO pending_device_actions ({_COLS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (pid, device_id, json.dumps(action), trigger, baseline_bootid or "",
                 approved_by or "", description or "", now, now + ttl_seconds,
                 "pending", ""),
            )
            conn.commit()
        finally:
            conn.close()
        return pid

    def list_active_for(self, device_id: str) -> List[Dict[str, Any]]:
        now = time.time()
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT {_COLS} FROM pending_device_actions "
                "WHERE device_id=? AND status='pending' AND expires_at > ? "
                "ORDER BY created_at",
                (device_id, now),
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_dict(r) for r in rows]

    def list_active(self) -> List[Dict[str, Any]]:
        now = time.time()
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT {_COLS} FROM pending_device_actions "
                "WHERE status='pending' AND expires_at > ? ORDER BY created_at",
                (now,),
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_dict(r) for r in rows]

    def claim_for_trigger(self, device_id: str, trigger: str) -> List[Dict[str, Any]]:
        """Atomically mark this device's matching pending actions as ``fired``
        and return them — so a concurrent sweep can't double-fire (fire-once)."""
        now = time.time()
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT {_COLS} FROM pending_device_actions "
                "WHERE device_id=? AND trigger=? AND status='pending' AND expires_at > ? "
                "ORDER BY created_at",
                (device_id, trigger, now),
            ).fetchall()
            claimed = []
            for r in rows:
                cur = conn.execute(
                    "UPDATE pending_device_actions SET status='fired' "
                    "WHERE id=? AND status='pending'",
                    (r[0],),
                )
                if cur.rowcount == 1:
                    claimed.append(_row_to_dict(r))
            conn.commit()
        finally:
            conn.close()
        return claimed

    def mark(self, pid: str, status: str, error: str = "") -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE pending_device_actions SET status=?, last_error=? WHERE id=?",
                (status, error or "", pid),
            )
            conn.commit()
        finally:
            conn.close()

    def cancel(self, pid: str) -> bool:
        """Operator-cancel a still-pending action. Returns True if it was."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE pending_device_actions SET status='cancelled' "
                "WHERE id=? AND status='pending'",
                (pid,),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def expire_stale(self) -> int:
        """Mark past-expiry pending actions as ``expired``. Returns the count."""
        now = time.time()
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE pending_device_actions SET status='expired' "
                "WHERE status='pending' AND expires_at <= ?",
                (now,),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def get(self, pid: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            r = conn.execute(
                f"SELECT {_COLS} FROM pending_device_actions WHERE id=?", (pid,)
            ).fetchone()
        finally:
            conn.close()
        return _row_to_dict(r) if r else None


# Module singleton (shares admz.db with the registry/confirm store).
pending_actions = PendingActionStore()


# --- handler registry: action_type -> async fn(action, device_id) -----------
# Real handlers (reprovision / restore / ...) are registered at app startup in
# Slice 3, closing over the AppContext. Tests register fakes.
PendingHandler = Callable[[Dict[str, Any], str], Awaitable[None]]
_HANDLERS: Dict[str, PendingHandler] = {}


def register_pending_handler(action_type: str, fn: PendingHandler) -> None:
    _HANDLERS[action_type] = fn


async def execute_pending_action(action: Dict[str, Any], device_id: str) -> None:
    """Run a claimed pending action via its registered handler. Raises on
    failure (the caller records ``last_error`` + marks ``failed``)."""
    atype = (action or {}).get("action", "")
    fn = _HANDLERS.get(atype)
    if fn is None:
        raise ValueError(f"no handler registered for deferred action {atype!r}")
    await fn(action, device_id)
