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
