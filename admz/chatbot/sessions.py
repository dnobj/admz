"""Per-principal chatbot session + conversation store.

Holds three things per principal, all in the shared SQLite database
(``~/.admz/admz.db`` by default):

* a vestigial Gemini ``interaction_id`` pointer (kept for backward
  compatibility — the models API the manual function-calling loop uses
  ignores it; context is replayed from ``chat_history`` instead),
* the **active conversation** pointer, and
* the **conversations** themselves (``chat_conversations`` rows) plus
  their messages (``chat_history`` rows tagged with ``conversation_id``).

A *conversation* is simply a labelled set of ``chat_history`` rows. The
console lists a principal's conversations newest-first, lets them open
(replay) and continue an older one, start a new one, and rename/delete.
"Clear chat" now *starts a new conversation* rather than deleting
history — the old conversation stays available in the list.

Uses per-call connections so it's safe under FastAPI's request-per-task
model; WAL mode makes the active-conversation pointer cross-process safe.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


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
    role         TEXT NOT NULL,        -- 'user' | 'model' | 'event'
    text         TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_history_principal_id
    ON chat_history(principal, id);

CREATE TABLE IF NOT EXISTS chat_conversations (
    id            TEXT PRIMARY KEY,
    principal     TEXT NOT NULL,
    title         TEXT NOT NULL DEFAULT '',
    title_source  TEXT NOT NULL DEFAULT 'pending',  -- pending|snippet|llm|manual|backfill
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_conv_principal_updated
    ON chat_conversations(principal, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_action_links (
    token            TEXT PRIMARY KEY,   -- confirm/capture session token
    principal        TEXT NOT NULL,
    conversation_id  TEXT NOT NULL,
    kind             TEXT NOT NULL,      -- 'confirm' | 'capture'
    label            TEXT NOT NULL DEFAULT '',
    created_at       REAL NOT NULL
);
"""


# Default cap on prior turns surfaced to the LLM. One "turn" = one
# user message + one assistant response = 2 history rows. Each turn
# costs a few hundred tokens of context (much less than the MCP tool
# catalog at ~6700 tokens, so 10 turns is comfortable).
DEFAULT_HISTORY_TURNS = 10

# Max characters for the provisional snippet title taken from the first
# user message (until the LLM title lands).
_SNIPPET_LEN = 48


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def snippet_title(text: str, limit: int = _SNIPPET_LEN) -> str:
    """A provisional one-line title from the first user message."""
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"  # ellipsis


class ChatSessionStore:
    """SQLite-backed per-principal session + conversation store."""

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
            self._migrate_columns(conn)
            conn.commit()
        finally:
            conn.close()
        # Backfill pre-existing history into per-principal conversations.
        # Separate connection/transaction so a failure here can't leave
        # the schema half-created.
        self._backfill_conversations()

    # ------------------------------------------------------------------
    # Idempotent column migrations (ALTER … ADD COLUMN only if absent)
    # ------------------------------------------------------------------

    @staticmethod
    def _columns(conn: sqlite3.Connection, table: str) -> set:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {r[1] for r in rows}

    def _migrate_columns(self, conn: sqlite3.Connection) -> None:
        if "conversation_id" not in self._columns(conn, "chat_history"):
            conn.execute("ALTER TABLE chat_history ADD COLUMN conversation_id TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_conv "
                "ON chat_history(conversation_id, id)"
            )
        if "active_conversation_id" not in self._columns(conn, "chat_sessions"):
            conn.execute(
                "ALTER TABLE chat_sessions ADD COLUMN active_conversation_id TEXT"
            )

    def _backfill_conversations(self) -> None:
        """Assign any orphan ``chat_history`` rows (conversation_id IS
        NULL) to one new conversation per principal, set it active, and
        leave everything else untouched. Idempotent: once rows carry a
        conversation_id they're excluded, so re-running is a no-op.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            principals = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT principal FROM chat_history "
                    "WHERE conversation_id IS NULL"
                ).fetchall()
            ]
            for principal in principals:
                last_at = conn.execute(
                    "SELECT MAX(created_at) FROM chat_history "
                    "WHERE principal=? AND conversation_id IS NULL",
                    (principal,),
                ).fetchone()[0] or _utc_iso()
                conv_id = _new_id()
                conn.execute(
                    "INSERT INTO chat_conversations "
                    "(id, principal, title, title_source, created_at, updated_at) "
                    "VALUES (?, ?, 'Earlier conversation', 'backfill', ?, ?)",
                    (conv_id, principal, last_at, last_at),
                )
                conn.execute(
                    "UPDATE chat_history SET conversation_id=? "
                    "WHERE principal=? AND conversation_id IS NULL",
                    (conv_id, principal),
                )
                # Adopt as active only if the principal has no active pointer.
                self._upsert_active(conn, principal, conv_id, only_if_unset=True)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Interaction pointer (vestigial — kept for back-compat)
    # ------------------------------------------------------------------

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
        return (row[0] or None) if row else None

    def set_interaction_id(
        self, principal: str, interaction_id: str, model: str
    ) -> None:
        """Upsert the principal's interaction pointer + last-used model.

        Preserves any existing ``active_conversation_id``.
        """
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO chat_sessions "
                "(principal, interaction_id, model, updated_at) "
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
        """Drop the principal's session pointer row (interaction +
        active-conversation). Returns True if a row existed.
        """
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
        return (row[0] or None) if row else None

    # ------------------------------------------------------------------
    # Active-conversation pointer (stored on the chat_sessions row)
    # ------------------------------------------------------------------

    @staticmethod
    def _upsert_active(
        conn: sqlite3.Connection,
        principal: str,
        conversation_id: Optional[str],
        *,
        only_if_unset: bool = False,
    ) -> None:
        """Set ``active_conversation_id`` for a principal within ``conn``.

        Inserts a chat_sessions row with empty interaction/model sentinels
        if none exists yet (interaction_id is NOT NULL — '' satisfies it
        and reads back as None via :meth:`get_interaction_id`).
        """
        now = _utc_iso()
        if only_if_unset:
            update = (
                "active_conversation_id = "
                "COALESCE(chat_sessions.active_conversation_id, excluded.active_conversation_id)"
            )
        else:
            update = "active_conversation_id = excluded.active_conversation_id"
        conn.execute(
            "INSERT INTO chat_sessions "
            "(principal, interaction_id, model, updated_at, active_conversation_id) "
            "VALUES (?, '', '', ?, ?) "
            "ON CONFLICT(principal) DO UPDATE SET " + update,
            (principal, now, conversation_id),
        )

    def get_active_conversation(self, principal: str) -> Optional[str]:
        """The principal's active conversation id, or None.

        Validated against ``chat_conversations`` — a dangling pointer
        (e.g. the conversation was deleted) reads back as None.
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT s.active_conversation_id FROM chat_sessions s "
                "JOIN chat_conversations c "
                "  ON c.id = s.active_conversation_id AND c.principal = s.principal "
                "WHERE s.principal=?",
                (principal,),
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row else None

    def set_active_conversation(self, principal: str, conversation_id: str) -> bool:
        """Switch the principal's active conversation. Ownership-checked;
        returns False if the conversation doesn't belong to the principal.
        """
        conn = self._connect()
        try:
            owns = conn.execute(
                "SELECT 1 FROM chat_conversations WHERE id=? AND principal=?",
                (conversation_id, principal),
            ).fetchone()
            if not owns:
                return False
            self._upsert_active(conn, principal, conversation_id)
            conn.commit()
            return True
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def create_conversation(
        self,
        principal: str,
        title: str = "",
        title_source: str = "pending",
        make_active: bool = True,
    ) -> str:
        """Create a new (empty) conversation and return its id.

        Made active by default — subsequent turns append to it.
        """
        conv_id = _new_id()
        now = _utc_iso()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO chat_conversations "
                "(id, principal, title, title_source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (conv_id, principal, title, title_source, now, now),
            )
            if make_active:
                self._upsert_active(conn, principal, conv_id)
            conn.commit()
        finally:
            conn.close()
        return conv_id

    def _ensure_active_conversation(
        self, conn: sqlite3.Connection, principal: str
    ) -> str:
        """Return the active conversation id within ``conn``, creating one
        (and adopting it as active) if the principal has none."""
        row = conn.execute(
            "SELECT s.active_conversation_id FROM chat_sessions s "
            "JOIN chat_conversations c "
            "  ON c.id = s.active_conversation_id AND c.principal = s.principal "
            "WHERE s.principal=?",
            (principal,),
        ).fetchone()
        if row and row[0]:
            return row[0]
        conv_id = _new_id()
        now = _utc_iso()
        conn.execute(
            "INSERT INTO chat_conversations "
            "(id, principal, title, title_source, created_at, updated_at) "
            "VALUES (?, ?, '', 'pending', ?, ?)",
            (conv_id, principal, now, now),
        )
        self._upsert_active(conn, principal, conv_id)
        return conv_id

    def get_conversation(self, principal: str, conversation_id: str) -> Optional[dict]:
        """Metadata for one conversation (ownership-checked) or None."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT c.id, c.title, c.title_source, c.created_at, c.updated_at, "
                "       (SELECT COUNT(*) FROM chat_history h "
                "          WHERE h.conversation_id = c.id) AS msg_count "
                "FROM chat_conversations c "
                "WHERE c.id=? AND c.principal=?",
                (conversation_id, principal),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return {
            "id": row[0],
            "title": row[1],
            "title_source": row[2],
            "created_at": row[3],
            "updated_at": row[4],
            "message_count": row[5],
        }

    def list_conversations(self, principal: str) -> List[dict]:
        """All of the principal's conversations, newest-first."""
        active = self.get_active_conversation(principal)
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT c.id, c.title, c.title_source, c.created_at, c.updated_at, "
                "       (SELECT COUNT(*) FROM chat_history h "
                "          WHERE h.conversation_id = c.id) AS msg_count "
                "FROM chat_conversations c "
                "WHERE c.principal=? "
                "ORDER BY c.updated_at DESC, c.created_at DESC",
                (principal,),
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "id": r[0],
                "title": r[1],
                "title_source": r[2],
                "created_at": r[3],
                "updated_at": r[4],
                "message_count": r[5],
                "active": r[0] == active,
            }
            for r in rows
        ]

    def get_messages(self, principal: str, conversation_id: str) -> List[dict]:
        """Full transcript of a conversation (ownership-checked).

        Returns ``[{"role", "text", "created_at"}]`` in chronological
        order. Empty list if the conversation isn't the principal's.
        """
        conn = self._connect()
        try:
            owns = conn.execute(
                "SELECT 1 FROM chat_conversations WHERE id=? AND principal=?",
                (conversation_id, principal),
            ).fetchone()
            if not owns:
                return []
            rows = conn.execute(
                "SELECT role, text, created_at FROM chat_history "
                "WHERE principal=? AND conversation_id=? ORDER BY id ASC",
                (principal, conversation_id),
            ).fetchall()
        finally:
            conn.close()
        return [{"role": r[0], "text": r[1], "created_at": r[2]} for r in rows]

    def set_title(
        self, principal: str, conversation_id: str, title: str, source: str
    ) -> bool:
        """Set a conversation's title (ownership-checked)."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE chat_conversations SET title=?, title_source=? "
                "WHERE id=? AND principal=?",
                (title, source, conversation_id, principal),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def rename_conversation(
        self, principal: str, conversation_id: str, title: str
    ) -> bool:
        """User-driven rename — pins the title (title_source='manual')."""
        return self.set_title(principal, conversation_id, title, "manual")

    def delete_conversation(self, principal: str, conversation_id: str) -> bool:
        """Delete a conversation and its messages (ownership-checked).

        If it was the active conversation, repoint active at the most
        recently-updated remaining conversation (or clear it).
        """
        conn = self._connect()
        try:
            owns = conn.execute(
                "SELECT 1 FROM chat_conversations WHERE id=? AND principal=?",
                (conversation_id, principal),
            ).fetchone()
            if not owns:
                return False
            conn.execute(
                "DELETE FROM chat_history WHERE principal=? AND conversation_id=?",
                (principal, conversation_id),
            )
            conn.execute(
                "DELETE FROM chat_conversations WHERE id=? AND principal=?",
                (conversation_id, principal),
            )
            active = conn.execute(
                "SELECT active_conversation_id FROM chat_sessions WHERE principal=?",
                (principal,),
            ).fetchone()
            if active and active[0] == conversation_id:
                nxt = conn.execute(
                    "SELECT id FROM chat_conversations WHERE principal=? "
                    "ORDER BY updated_at DESC, created_at DESC LIMIT 1",
                    (principal,),
                ).fetchone()
                self._upsert_active(conn, principal, nxt[0] if nxt else None)
            conn.commit()
            return True
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Conversation history (chat_history table, scoped to the active conv)
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
        """Record one turn (user + assistant) on the active conversation.

        Lazily creates an active conversation if the principal has none.
        Sets a provisional snippet title from the first user message when
        the conversation hasn't been titled yet, and bumps the
        conversation's ``updated_at`` for recency ordering.

        Empty assistant responses (e.g. budget rejections, errors) skip
        the record — replaying them in subsequent turns would confuse the
        LLM with messages it didn't actually send.
        """
        if not assistant_message:
            return
        conn = self._connect()
        try:
            conv_id = self._ensure_active_conversation(conn, principal)
            now = _utc_iso()
            conn.execute(
                "INSERT INTO chat_history "
                "(principal, role, text, created_at, conversation_id) "
                "VALUES (?, 'user', ?, ?, ?)",
                (principal, user_message, now, conv_id),
            )
            conn.execute(
                "INSERT INTO chat_history "
                "(principal, role, text, created_at, conversation_id) "
                "VALUES (?, 'model', ?, ?, ?)",
                (principal, assistant_message, now, conv_id),
            )
            # Provisional snippet title until the LLM title lands.
            conn.execute(
                "UPDATE chat_conversations SET title=?, title_source='snippet' "
                "WHERE id=? AND title_source='pending'",
                (snippet_title(user_message), conv_id),
            )
            conn.execute(
                "UPDATE chat_conversations SET updated_at=? WHERE id=?",
                (now, conv_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Console event notes — out-of-band action outcomes the model must
    # see in subsequent turns (card approvals, credential-form completions).
    # ------------------------------------------------------------------

    # Links live this long at most; confirm/capture sessions themselves
    # expire in minutes, so a day covers every legitimate resolution.
    _ACTION_LINK_TTL_SECONDS = 24 * 3600.0

    def link_action(
        self,
        token: str,
        principal: str,
        conversation_id: str,
        kind: str,
        label: str = "",
    ) -> None:
        """Remember which conversation spawned a confirm/capture session so
        its out-of-band resolution can be noted back into that conversation.
        ``label`` is caller-safe metadata only (op/action + device) — never
        params or secrets."""
        now = time.time()
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM chat_action_links WHERE created_at < ?",
                (now - self._ACTION_LINK_TTL_SECONDS,),
            )
            conn.execute(
                "INSERT OR REPLACE INTO chat_action_links "
                "(token, principal, conversation_id, kind, label, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (token, principal, conversation_id, kind, label, now),
            )
            conn.commit()
        finally:
            conn.close()

    def pop_action_link(self, token: str) -> Optional[dict]:
        """Fetch-and-delete the link for ``token`` (one note per session).
        Returns ``{principal, conversation_id, kind, label}`` or None for
        tokens that never came from a chat turn (REST/dev approvals)."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT principal, conversation_id, kind, label "
                "FROM chat_action_links WHERE token=?",
                (token,),
            ).fetchone()
            if row is None:
                return None
            conn.execute("DELETE FROM chat_action_links WHERE token=?", (token,))
            conn.commit()
        finally:
            conn.close()
        return {
            "principal": row[0],
            "conversation_id": row[1],
            "kind": row[2],
            "label": row[3],
        }

    def append_event(
        self, principal: str, conversation_id: str, text: str
    ) -> bool:
        """Append one ``role='event'`` note to a specific conversation.

        Unlike :meth:`append_turn` this takes an explicit conversation —
        the resolution may land while the principal has a different (or no)
        active conversation. No-ops (returns False) when the conversation
        doesn't exist or belongs to someone else."""
        if not text:
            return False
        conn = self._connect()
        try:
            owned = conn.execute(
                "SELECT 1 FROM chat_conversations WHERE id=? AND principal=?",
                (conversation_id, principal),
            ).fetchone()
            if owned is None:
                return False
            now = _utc_iso()
            conn.execute(
                "INSERT INTO chat_history "
                "(principal, role, text, created_at, conversation_id) "
                "VALUES (?, 'event', ?, ?, ?)",
                (principal, text, now, conversation_id),
            )
            conn.execute(
                "UPDATE chat_conversations SET updated_at=? WHERE id=?",
                (now, conversation_id),
            )
            conn.commit()
        finally:
            conn.close()
        return True

    def get_history(
        self, principal: str, max_turns: int = DEFAULT_HISTORY_TURNS
    ) -> list:
        """Return last ``max_turns`` turns of the **active conversation**
        as a chronologically-ordered list of
        ``{"role": "user"|"model", "text": ...}`` dicts.

        Suitable for converting into the Gemini ``contents=[...]`` wire
        shape. Returns ``[]`` when the principal has no active conversation
        (e.g. a brand-new conversation before its first turn).
        """
        if max_turns <= 0:
            return []
        active = self.get_active_conversation(principal)
        if not active:
            return []
        # 2 rows per turn (user + model). Fetch the latest 2*max_turns
        # rows, then reverse to chronological order.
        limit = max_turns * 2
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT role, text FROM chat_history "
                "WHERE principal=? AND conversation_id=? "
                "ORDER BY id DESC LIMIT ?",
                (principal, active, limit),
            ).fetchall()
        finally:
            conn.close()
        return [{"role": r, "text": t} for r, t in reversed(rows)]

    def clear_history(self, principal: str) -> int:
        """Delete ALL history rows for ``principal`` across every
        conversation, and remove the now-empty conversation rows. Returns
        the number of history rows deleted.

        Retained for back-compat / tests. The console's "Clear chat"
        button now starts a *new* conversation instead of calling this.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                "DELETE FROM chat_history WHERE principal=?", (principal,)
            )
            conn.execute(
                "DELETE FROM chat_conversations WHERE principal=?", (principal,)
            )
            # Clear the dangling active pointer if a session row exists —
            # without creating one for a principal that had nothing.
            conn.execute(
                "UPDATE chat_sessions SET active_conversation_id=NULL "
                "WHERE principal=?",
                (principal,),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


# Module-level singleton.
chat_sessions = ChatSessionStore()
