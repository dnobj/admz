"""Tests for the conversation layer of ChatSessionStore.

Covers: conversation CRUD, the active-conversation pointer, owner
scoping, active-scoped append/history, provisional snippet titling, and
the one-time non-destructive backfill of pre-existing chat_history rows.
"""

import sqlite3

import pytest

from admz.chatbot.sessions import ChatSessionStore, snippet_title


@pytest.fixture
def store(tmp_path):
    return ChatSessionStore(str(tmp_path / "admz.db"))


# ---------------------------------------------------------------------------
# Conversation CRUD + active pointer
# ---------------------------------------------------------------------------


class TestConversations:
    def test_create_sets_active(self, store):
        cid = store.create_conversation("alice")
        assert store.get_active_conversation("alice") == cid
        convs = store.list_conversations("alice")
        assert len(convs) == 1 and convs[0]["id"] == cid and convs[0]["active"]

    def test_create_inactive(self, store):
        a = store.create_conversation("alice")
        b = store.create_conversation("alice", make_active=False)
        assert store.get_active_conversation("alice") == a
        ids = {c["id"]: c["active"] for c in store.list_conversations("alice")}
        assert ids[a] is True and ids[b] is False

    def test_list_newest_first(self, store):
        a = store.create_conversation("alice")
        store.append_turn("alice", "first", "r1")        # bumps a
        b = store.create_conversation("alice")
        store.append_turn("alice", "second", "r2")       # bumps b (now active)
        order = [c["id"] for c in store.list_conversations("alice")]
        assert order[0] == b and order[1] == a

    def test_switch_active(self, store):
        a = store.create_conversation("alice")
        b = store.create_conversation("alice")
        assert store.get_active_conversation("alice") == b
        assert store.set_active_conversation("alice", a) is True
        assert store.get_active_conversation("alice") == a

    def test_switch_active_rejects_foreign(self, store):
        a = store.create_conversation("alice")
        b = store.create_conversation("bob")
        # alice cannot adopt bob's conversation
        assert store.set_active_conversation("alice", b) is False
        assert store.get_active_conversation("alice") == a

    def test_get_messages_owner_scoped(self, store):
        a = store.create_conversation("alice")
        store.append_turn("alice", "hi", "hello")
        assert [m["text"] for m in store.get_messages("alice", a)] == ["hi", "hello"]
        # bob cannot read alice's conversation
        assert store.get_messages("bob", a) == []

    def test_get_conversation_owner_scoped(self, store):
        a = store.create_conversation("alice")
        assert store.get_conversation("alice", a)["id"] == a
        assert store.get_conversation("bob", a) is None

    def test_rename_pins_manual(self, store):
        a = store.create_conversation("alice")
        store.append_turn("alice", "drift check", "ok")   # snippet title
        assert store.get_conversation("alice", a)["title_source"] == "snippet"
        assert store.rename_conversation("alice", a, "My drift convo") is True
        meta = store.get_conversation("alice", a)
        assert meta["title"] == "My drift convo" and meta["title_source"] == "manual"

    def test_rename_rejects_foreign(self, store):
        a = store.create_conversation("alice")
        assert store.rename_conversation("bob", a, "hijack") is False

    def test_delete_repoints_active(self, store):
        a = store.create_conversation("alice")
        store.append_turn("alice", "a", "ra")
        b = store.create_conversation("alice")          # active = b
        store.append_turn("alice", "b", "rb")
        assert store.get_active_conversation("alice") == b
        assert store.delete_conversation("alice", b) is True
        # active repoints to the remaining conversation
        assert store.get_active_conversation("alice") == a
        assert len(store.list_conversations("alice")) == 1

    def test_delete_last_clears_active(self, store):
        a = store.create_conversation("alice")
        store.append_turn("alice", "a", "ra")
        assert store.delete_conversation("alice", a) is True
        assert store.get_active_conversation("alice") is None
        assert store.list_conversations("alice") == []

    def test_delete_rejects_foreign(self, store):
        a = store.create_conversation("alice")
        assert store.delete_conversation("bob", a) is False
        assert store.get_conversation("alice", a) is not None


# ---------------------------------------------------------------------------
# Active-scoped append / history
# ---------------------------------------------------------------------------


class TestActiveScopedHistory:
    def test_append_lazily_creates_active(self, store):
        assert store.get_active_conversation("alice") is None
        store.append_turn("alice", "hi", "hello")
        cid = store.get_active_conversation("alice")
        assert cid is not None
        assert [m["text"] for m in store.get_messages("alice", cid)] == ["hi", "hello"]

    def test_history_scoped_to_active(self, store):
        a = store.create_conversation("alice")
        store.append_turn("alice", "in-a", "ra")
        b = store.create_conversation("alice")           # switch active to b
        store.append_turn("alice", "in-b", "rb")
        # active history is only b's turn
        assert [h["text"] for h in store.get_history("alice")] == ["in-b", "rb"]
        # switching back surfaces a's history
        store.set_active_conversation("alice", a)
        assert [h["text"] for h in store.get_history("alice")] == ["in-a", "ra"]

    def test_snippet_title_set_once(self, store):
        store.append_turn("alice", "Has the lobby camera drifted from baseline?", "…")
        cid = store.get_active_conversation("alice")
        meta = store.get_conversation("alice", cid)
        assert meta["title_source"] == "snippet"
        assert meta["title"].startswith("Has the lobby camera")
        # A second turn does NOT overwrite the snippet title.
        store.append_turn("alice", "and the garage one?", "…")
        assert store.get_conversation("alice", cid)["title"] == meta["title"]

    def test_snippet_does_not_override_manual(self, store):
        a = store.create_conversation("alice", title="Pinned", title_source="manual")
        store.append_turn("alice", "first message here", "…")
        assert store.get_conversation("alice", a)["title"] == "Pinned"

    def test_updated_at_bumps_on_append(self, store):
        a = store.create_conversation("alice")
        t0 = store.get_conversation("alice", a)["updated_at"]
        store.append_turn("alice", "hi", "hello")
        t1 = store.get_conversation("alice", a)["updated_at"]
        assert t1 >= t0


def test_snippet_title_truncates():
    assert snippet_title("short") == "short"
    long = "x" * 80
    out = snippet_title(long, limit=48)
    assert len(out) == 48 and out.endswith("…")
    assert snippet_title("  multi   space\nhere ") == "multi space here"


# ---------------------------------------------------------------------------
# Backfill migration (idempotent, non-destructive)
# ---------------------------------------------------------------------------


def _seed_legacy_history(db_path, principal, pairs):
    """Write pre-migration chat_history rows (no conversation_id) directly,
    simulating an older DB."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chat_history ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, principal TEXT, role TEXT, "
        "text TEXT, created_at TEXT)"
    )
    for u, m in pairs:
        conn.execute(
            "INSERT INTO chat_history (principal, role, text, created_at) "
            "VALUES (?, 'user', ?, '2026-01-01T00:00:00+00:00')",
            (principal, u),
        )
        conn.execute(
            "INSERT INTO chat_history (principal, role, text, created_at) "
            "VALUES (?, 'model', ?, '2026-01-01T00:00:01+00:00')",
            (principal, m),
        )
    conn.commit()
    conn.close()


class TestBackfill:
    def test_backfill_assigns_one_conversation_per_principal(self, tmp_path):
        db = str(tmp_path / "admz.db")
        _seed_legacy_history(db, "alice", [("u1", "m1"), ("u2", "m2")])
        _seed_legacy_history(db, "bob", [("u3", "m3")])

        store = ChatSessionStore(db)  # __init__ runs the backfill

        alice_convs = store.list_conversations("alice")
        bob_convs = store.list_conversations("bob")
        assert len(alice_convs) == 1 and len(bob_convs) == 1
        assert alice_convs[0]["title"] == "Earlier conversation"
        assert alice_convs[0]["title_source"] == "backfill"
        # All of alice's legacy rows are now in her conversation, active.
        cid = alice_convs[0]["id"]
        assert store.get_active_conversation("alice") == cid
        assert [m["text"] for m in store.get_messages("alice", cid)] == [
            "u1", "m1", "u2", "m2"
        ]
        # No row loss.
        assert alice_convs[0]["message_count"] == 4
        assert bob_convs[0]["message_count"] == 2

    def test_backfill_is_idempotent(self, tmp_path):
        db = str(tmp_path / "admz.db")
        _seed_legacy_history(db, "alice", [("u1", "m1")])
        ChatSessionStore(db)                 # first run backfills
        store2 = ChatSessionStore(db)        # second run must be a no-op
        convs = store2.list_conversations("alice")
        assert len(convs) == 1               # not duplicated
        assert convs[0]["message_count"] == 2

    def test_backfill_preserves_existing_active(self, tmp_path):
        db = str(tmp_path / "admz.db")
        store = ChatSessionStore(db)
        # alice already has a live conversation + active pointer
        existing = store.create_conversation("alice")
        store.append_turn("alice", "live", "reply")
        # now simulate orphan legacy rows arriving + a re-init
        _seed_legacy_history(db, "alice", [("old", "oldreply")])
        store2 = ChatSessionStore(db)
        # backfill must NOT steal the active pointer from the live convo
        assert store2.get_active_conversation("alice") == existing
        assert len(store2.list_conversations("alice")) == 2

    def test_reinit_without_legacy_is_noop(self, store, tmp_path):
        store.append_turn("alice", "hi", "hello")
        before = store.list_conversations("alice")
        store2 = ChatSessionStore(store._db_path)
        after = store2.list_conversations("alice")
        assert len(before) == len(after) == 1
