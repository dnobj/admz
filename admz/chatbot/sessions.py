"""Per-principal chatbot session store.

Stores only :class:`previous_interaction_id` per principal — no
message bodies. Transcripts live in Google's server-side
conversation store keyed by that ID. "Clear chat" deletes the
row; the next turn starts a new server-side interaction.

Shares the same SQLite database file as the device registry and
fleet settings (``~/.admz/admz.db`` by default). Uses per-call
connections so it's safe under FastAPI's request-per-task model.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    principal       TEXT PRIMARY KEY,
    interaction_id  TEXT NOT NULL,
    model           TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    principal    TEXT NOT NULL,
    role         TEXT NOT NULL,        -- 'user' | 'model'
    text         TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_history_principal_id
    ON chat_history(principal, id);
"""


# Default cap on prior turns surfaced to the LLM. One "turn" = one
# user message + one assistant response = 2 history rows. Each turn
# costs a few hundred tokens of context (much less than the MCP tool
# catalog at ~6700 tokens, so 10 turns is comfortable).
DEFAULT_HISTORY_TURNS = 10


def _default_db_path() -> Path:
    return Path(
        os.getenv("ADMZ_DB_PATH", str(Path.home() / ".admz" / "admz.db"))
    )


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatSessionStore:
    """SQLite-backed per-principal session pointer store."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def get_interaction_id(self, principal: str) -> Optional[str]:
        """Return the stored Gemini interaction_id for this principal, if any."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT interaction_id FROM chat_sessions WHERE principal=?",
                (principal,),
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row else None

    def set_interaction_id(
        self, principal: str, interaction_id: str, model: str
    ) -> None:
        """Upsert the principal's interaction pointer + last-used model."""
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO chat_sessions (principal, interaction_id, model, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(principal) DO UPDATE SET "
                "    interaction_id = excluded.interaction_id, "
                "    model          = excluded.model, "
                "    updated_at     = excluded.updated_at",
                (principal, interaction_id, model, _utc_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def clear(self, principal: str) -> bool:
        """Drop the principal's session pointer. Returns True if a row existed."""
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM chat_sessions WHERE principal=?", (principal,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def last_model(self, principal: str) -> Optional[str]:
        """The model the principal most recently used (for UI prefill)."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT model FROM chat_sessions WHERE principal=?",
                (principal,),
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row else None

    # ------------------------------------------------------------------
    # Conversation history (chat_history table)
    # ------------------------------------------------------------------
    #
    # We store per-turn (user_msg, assistant_msg) pairs because the
    # Gemini models API needs the full history fed back as a
    # contents=[...] array each call. The previous_interaction_id
    # approach only works with the Interactions API surface, which
    # doesn't support MCP tools — so we maintain history ourselves.

    def append_turn(
        self, principal: str, user_message: str, assistant_message: str
    ) -> None:
        """Record one turn (user + assistant) in history.

        Empty assistant responses (e.g. budget rejections, errors)
        skip the record — replaying them in subsequent turns would
        confuse the LLM with messages it didn't actually send.
        """
        if not assistant_message:
            return
        conn = self._connect()
        try:
            now = _utc_iso()
            conn.execute(
                "INSERT INTO chat_history (principal, role, text, created_at) "
                "VALUES (?, 'user', ?, ?)",
                (principal, user_message, now),
            )
            conn.execute(
                "INSERT INTO chat_history (principal, role, text, created_at) "
                "VALUES (?, 'model', ?, ?)",
                (principal, assistant_message, now),
            )
            conn.commit()
        finally:
            conn.close()

    def get_history(
        self, principal: str, max_turns: int = DEFAULT_HISTORY_TURNS
    ) -> list:
        """Return last ``max_turns`` turns as a chronologically-ordered
        list of ``{"role": "user"|"model", "text": ...}`` dicts.

        Suitable for converting into the Gemini ``contents=[...]``
        wire shape: each item becomes ``{"role": role, "parts": [{"text": ...}]}``.
        """
        if max_turns <= 0:
            return []
        # 2 rows per turn (user + model). Fetch the latest 2*max_turns
        # rows, then reverse to chronological order.
        limit = max_turns * 2
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT role, text FROM chat_history "
                "WHERE principal=? "
                "ORDER BY id DESC LIMIT ?",
                (principal, limit),
            ).fetchall()
        finally:
            conn.close()
        return [{"role": r, "text": t} for r, t in reversed(rows)]

    def clear_history(self, principal: str) -> int:
        """Delete all history rows for ``principal``. Returns row count.

        Called by the /chat/clear route alongside dropping the
        interaction_id pointer.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                "DELETE FROM chat_history WHERE principal=?", (principal,)
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


# Module-level singleton.
chat_sessions = ChatSessionStore()
