"""Tests for admz.chatbot.sessions — per-principal interaction pointer store."""

import pytest

from admz.chatbot.sessions import ChatSessionStore


@pytest.fixture
def store(tmp_path):
    return ChatSessionStore(str(tmp_path / "admz.db"))


class TestChatSessionStore:
    def test_get_returns_none_for_unknown(self, store):
        assert store.get_interaction_id("AXIS\\alice") is None
        assert store.last_model("AXIS\\alice") is None

    def test_set_then_get_round_trip(self, store):
        store.set_interaction_id("AXIS\\alice", "int-abc", "gemini-2.5-pro")
        assert store.get_interaction_id("AXIS\\alice") == "int-abc"
        assert store.last_model("AXIS\\alice") == "gemini-2.5-pro"

    def test_upsert_overwrites_existing(self, store):
        store.set_interaction_id("AXIS\\alice", "int-1", "gemini-2.5-flash")
        store.set_interaction_id("AXIS\\alice", "int-2", "gemini-2.5-pro")
        assert store.get_interaction_id("AXIS\\alice") == "int-2"
        assert store.last_model("AXIS\\alice") == "gemini-2.5-pro"

    def test_clear_drops_row(self, store):
        store.set_interaction_id("AXIS\\alice", "int-x", "gemini-2.5-pro")
        assert store.clear("AXIS\\alice") is True
        assert store.get_interaction_id("AXIS\\alice") is None

    def test_clear_unknown_principal_returns_false(self, store):
        assert store.clear("AXIS\\ghost") is False

    def test_two_principals_are_isolated(self, store):
        store.set_interaction_id("AXIS\\alice", "alice-int", "gemini-2.5-pro")
        store.set_interaction_id("AXIS\\bob", "bob-int", "gemini-2.5-flash")
        assert store.get_interaction_id("AXIS\\alice") == "alice-int"
        assert store.get_interaction_id("AXIS\\bob") == "bob-int"

        # Clearing one doesn't touch the other.
        store.clear("AXIS\\alice")
        assert store.get_interaction_id("AXIS\\alice") is None
        assert store.get_interaction_id("AXIS\\bob") == "bob-int"


# ---------------------------------------------------------------------------
# Chat history (real-history threading for the Gemini models API)
# ---------------------------------------------------------------------------


class TestChatHistory:
    def test_empty_history_for_new_principal(self, store):
        assert store.get_history("alice") == []

    def test_append_then_get_round_trip(self, store):
        store.append_turn("alice", "hi", "hello there")
        hist = store.get_history("alice")
        assert hist == [
            {"role": "user", "text": "hi"},
            {"role": "model", "text": "hello there"},
        ]

    def test_multiple_turns_chronological_order(self, store):
        store.append_turn("alice", "msg1", "reply1")
        store.append_turn("alice", "msg2", "reply2")
        store.append_turn("alice", "msg3", "reply3")
        hist = store.get_history("alice")
        # Expect chronological order: msg1, reply1, msg2, reply2, ...
        assert [h["text"] for h in hist] == [
            "msg1", "reply1", "msg2", "reply2", "msg3", "reply3",
        ]
        # Roles alternate.
        assert [h["role"] for h in hist] == [
            "user", "model", "user", "model", "user", "model",
        ]

    def test_history_capped_by_max_turns(self, store):
        for i in range(20):
            store.append_turn("alice", f"u{i}", f"m{i}")
        hist = store.get_history("alice", max_turns=3)
        # 3 turns = 6 rows, the latest three.
        assert len(hist) == 6
        assert hist[0]["text"] == "u17"
        assert hist[-1]["text"] == "m19"

    def test_empty_assistant_response_not_stored(self, store):
        """Errors / budget rejections produce empty responses;
        replaying them would confuse the LLM next turn."""
        store.append_turn("alice", "asked something", "")
        assert store.get_history("alice") == []

    def test_history_isolated_per_principal(self, store):
        store.append_turn("alice", "alice-msg", "alice-reply")
        store.append_turn("bob", "bob-msg", "bob-reply")
        assert [h["text"] for h in store.get_history("alice")] == [
            "alice-msg", "alice-reply"
        ]
        assert [h["text"] for h in store.get_history("bob")] == [
            "bob-msg", "bob-reply"
        ]

    def test_clear_history_drops_all_rows(self, store):
        store.append_turn("alice", "msg1", "reply1")
        store.append_turn("alice", "msg2", "reply2")
        count = store.clear_history("alice")
        assert count == 4
        assert store.get_history("alice") == []

    def test_clear_unknown_principal_returns_zero(self, store):
        assert store.clear_history("ghost") == 0

    def test_max_turns_zero_returns_empty(self, store):
        store.append_turn("alice", "msg", "reply")
        assert store.get_history("alice", max_turns=0) == []
