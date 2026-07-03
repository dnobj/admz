"""Console event notes — the model learns when out-of-band actions resolve.

Approving a confirmation card (or completing a credential-capture form)
happens outside the chat turn loop; these notes write a non-sensitive
``role='event'`` row back into the originating conversation so subsequent
turns treat the outcome as ground truth. Never passwords, never op params.
"""

import time

import pytest

from admz.chatbot.client import _build_contents
from admz.chatbot.sessions import ChatSessionStore


@pytest.fixture
def store(tmp_path):
    return ChatSessionStore(str(tmp_path / "admz.db"))


def _conversation(store, principal="alice"):
    """A conversation with one real turn (mirrors live usage)."""
    store.append_turn(principal, "remove the P3408", "Please approve the card.")
    return store.get_active_conversation(principal)


# ---------------------------------------------------------------------------
# Link store
# ---------------------------------------------------------------------------


class TestActionLinks:
    def test_link_pop_round_trip(self, store):
        conv = _conversation(store)
        store.link_action("tok-1", "alice", conv, "confirm", label="delete_device")
        link = store.pop_action_link("tok-1")
        assert link == {
            "principal": "alice", "conversation_id": conv,
            "kind": "confirm", "label": "delete_device",
        }
        # single-use: second pop finds nothing
        assert store.pop_action_link("tok-1") is None

    def test_pop_unknown_token(self, store):
        assert store.pop_action_link("never-linked") is None

    def test_old_links_cleaned_on_insert(self, store, monkeypatch):
        conv = _conversation(store)
        ancient = time.time() - 2 * 24 * 3600
        monkeypatch.setattr(time, "time", lambda: ancient)
        store.link_action("tok-old", "alice", conv, "confirm")
        monkeypatch.undo()
        store.link_action("tok-new", "alice", conv, "capture")
        assert store.pop_action_link("tok-old") is None
        assert store.pop_action_link("tok-new") is not None


# ---------------------------------------------------------------------------
# append_event
# ---------------------------------------------------------------------------


class TestAppendEvent:
    def test_event_row_lands_in_conversation(self, store):
        conv = _conversation(store)
        ok = store.append_event("alice", conv, "[console] approved; executed.")
        assert ok is True
        msgs = store.get_messages("alice", conv)
        assert msgs[-1]["role"] == "event"
        assert msgs[-1]["text"] == "[console] approved; executed."

    def test_event_visible_in_model_history(self, store):
        conv = _conversation(store)
        store.append_event("alice", conv, "[console] approved; executed.")
        hist = store.get_history("alice")
        assert hist[-1] == {"role": "event",
                            "text": "[console] approved; executed."}

    def test_wrong_principal_is_noop(self, store):
        conv = _conversation(store)
        assert store.append_event("mallory", conv, "[console] x") is False
        assert all(m["role"] != "event" for m in store.get_messages("alice", conv))

    def test_unknown_conversation_is_noop(self, store):
        assert store.append_event("alice", "ghost-conv", "[console] x") is False

    def test_empty_text_is_noop(self, store):
        conv = _conversation(store)
        assert store.append_event("alice", conv, "") is False


# ---------------------------------------------------------------------------
# Model-context mapping
# ---------------------------------------------------------------------------


class TestBuildContents:
    def test_event_rides_as_user_turn(self):
        items = _build_contents(
            [
                {"role": "user", "text": "remove it"},
                {"role": "model", "text": "approve the card"},
                {"role": "event", "text": "[console] approved; executed."},
            ],
            "what devices do I have?",
        )
        roles = [i["role"] for i in items]
        assert roles == ["user", "model", "user", "user"]
        assert items[2]["parts"][0]["text"].startswith("[console]")


# ---------------------------------------------------------------------------
# Tool-result token scanning (routes/chat.py)
# ---------------------------------------------------------------------------


class TestScanActionTokens:
    def test_finds_confirm_and_capture_urls(self):
        from admz.api.routes.chat import _scan_action_tokens

        result = {
            "blocked": True,
            "confirm_url": "/confirm/AAAAAAAAAAAAAAAAAAAAAAAA",
            "nested": {"url": "http://localhost:4242/capture/BBBBBBBBBBBBBBBBBBBBBBBB"},
        }
        found = _scan_action_tokens(result, "execute_operation")
        assert ("confirm", "AAAAAAAAAAAAAAAAAAAAAAAA", "execute_operation") in found
        assert ("capture", "BBBBBBBBBBBBBBBBBBBBBBBB", "execute_operation") in found

    def test_fleet_capture_urls_ignored(self):
        from admz.api.routes.chat import _scan_action_tokens

        result = {"capture_url": "/capture/fleet/CCCCCCCCCCCCCCCCCCCCCCCC"}
        assert _scan_action_tokens(result, "set_fleet_setting") == []

    def test_dedupes_and_survives_garbage(self):
        from admz.api.routes.chat import _scan_action_tokens

        result = {"a": "/confirm/DDDDDDDDDDDDDDDDDDDDDDDD",
                  "b": "/confirm/DDDDDDDDDDDDDDDDDDDDDDDD"}
        assert len(_scan_action_tokens(result, "t")) == 1
        assert _scan_action_tokens(object(), "t") == []


# ---------------------------------------------------------------------------
# Confirm resolution note (routes/confirm.py)
# ---------------------------------------------------------------------------


class _FakeSession:
    def __init__(self, operation_id="action:delete_device", is_plan=False):
        self.operation_id = operation_id
        self.device_id = "E82725315CDF"
        self.is_plan = is_plan
        self.plan_id = ""


class TestConfirmResolutionNote:
    def _note(self, store, monkeypatch, outcome, confirmed_by="chat",
              session=None, token="tok-c"):
        import admz.chatbot.sessions as sessions_mod
        from admz.api.routes.confirm import _note_resolution_to_chat

        monkeypatch.setattr(sessions_mod, "chat_sessions", store)
        _note_resolution_to_chat(token, session or _FakeSession(),
                                 outcome, confirmed_by)

    def test_success_note(self, store, monkeypatch):
        conv = _conversation(store)
        store.link_action("tok-c", "alice", conv, "confirm")
        self._note(store, monkeypatch, {"success": True})
        text = store.get_messages("alice", conv)[-1]["text"]
        assert text.startswith("[console]")
        assert "delete_device" in text
        assert "E82725315CDF" in text
        assert "executed successfully" in text
        assert "confirmation card" in text  # confirmed_by='chat' surface

    def test_failure_note_carries_truncated_error(self, store, monkeypatch):
        conv = _conversation(store)
        store.link_action("tok-c", "alice", conv, "confirm")
        self._note(store, monkeypatch,
                   {"success": False, "error": "Authentication failed (401)." + "x" * 500},
                   confirmed_by="web",
                   session=_FakeSession("factorydefault.cgi:factory-reset"))
        text = store.get_messages("alice", conv)[-1]["text"]
        assert "FAILED" in text
        assert "Authentication failed (401)" in text
        assert len(text) < 450  # error truncated
        assert "web page" in text  # confirmed_by='web' surface

    def test_unlinked_token_writes_nothing(self, store, monkeypatch):
        conv = _conversation(store)
        self._note(store, monkeypatch, {"success": True}, token="never-linked")
        assert all(m["role"] != "event" for m in store.get_messages("alice", conv))

    def test_note_failure_never_raises(self, store, monkeypatch):
        import admz.chatbot.sessions as sessions_mod
        from admz.api.routes.confirm import _note_resolution_to_chat

        class _Boom:
            def pop_action_link(self, token):
                raise RuntimeError("db down")

        monkeypatch.setattr(sessions_mod, "chat_sessions", _Boom())
        _note_resolution_to_chat("tok", _FakeSession(), {"success": True}, "chat")


# ---------------------------------------------------------------------------
# Capture completion note (routes/capture.py)
# ---------------------------------------------------------------------------


class TestCaptureNote:
    def test_capture_note_no_credentials_in_text(self, store, monkeypatch):
        import admz.chatbot.sessions as sessions_mod
        from admz.api.routes.capture import _note_capture_to_chat

        conv = _conversation(store)
        store.link_action("tok-cap", "alice", conv, "capture")
        monkeypatch.setattr(sessions_mod, "chat_sessions", store)
        _note_capture_to_chat("tok-cap", ["E82725315CDF"])
        text = store.get_messages("alice", conv)[-1]["text"]
        assert text.startswith("[console]")
        assert "E82725315CDF" in text
        assert "stored server-side" in text
        assert "password is not available" in text

    def test_unlinked_capture_is_silent(self, store, monkeypatch):
        import admz.chatbot.sessions as sessions_mod
        from admz.api.routes.capture import _note_capture_to_chat

        conv = _conversation(store)
        monkeypatch.setattr(sessions_mod, "chat_sessions", store)
        _note_capture_to_chat("never-linked", ["dev-1"])
        assert all(m["role"] != "event" for m in store.get_messages("alice", conv))
