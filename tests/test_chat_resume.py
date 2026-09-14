"""The continuation turn after an out-of-band resolution (#444 / ADR-0066).

The passive half already worked: resolving a capture or approval writes a
``role='event'`` console note into the conversation that spawned it, and
``_build_contents`` hands that note to the model on its next turn. Nothing made
the model RUN — so an operator who was told "once approved, I will proceed"
came back to nothing done.

These cover the trigger: that a continuation is owed exactly when a console
note is unanswered, that it happens at most once, that it is seed-free, and —
the one most likely to be got wrong — that it never moves the operator's
active-conversation cursor.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("ADMZ_GEMINI_API_KEY", raising=False)

    from admz import fleet_settings as fs_module
    from admz.chatbot import config as cfg_module
    from admz.chatbot import sessions as sess_module
    from admz.chatbot import usage as usage_module

    db_path = str(tmp_path / "admz.db")
    orig_fs = fs_module.fleet_settings
    orig_sess = sess_module.chat_sessions
    orig_usage = usage_module.token_usage
    orig_boot = cfg_module._bootstrapped

    fs_module.fleet_settings = fs_module.FleetSettings(db_path)
    sess_module.chat_sessions = sess_module.ChatSessionStore(db_path)
    usage_module.token_usage = usage_module.TokenUsageStore(db_path)
    cfg_module._bootstrapped = False

    from admz.api.main import app

    try:
        with TestClient(app, follow_redirects=False) as c:
            import subprocess
            repo_path = str(tmp_path / "config-repo")
            for key, val in [
                ("user.email", "test@test.com"),
                ("user.name", "Test"),
                ("commit.gpgsign", "false"),
            ]:
                subprocess.run(
                    ["git", "config", key, val], cwd=repo_path, check=True
                )
            yield c
    finally:
        fs_module.fleet_settings = orig_fs
        sess_module.chat_sessions = orig_sess
        usage_module.token_usage = orig_usage
        cfg_module._bootstrapped = orig_boot


PRINCIPAL = "anonymous"  # the synthetic principal under the no-auth default


def _store():
    from admz.chatbot import sessions as sess_module
    return sess_module.chat_sessions


def _seed_api_key():
    from admz.chatbot.config import set_api_key
    set_api_key("AIza-test")


def _capturing_stream(captured, text="Captured the baseline."):
    """A fake stream_turn that records the kwargs it was handed."""
    from admz.chatbot.events import event_done, event_text

    async def stream(**kwargs):
        captured.update(kwargs)
        yield event_text(text)
        yield event_done(
            interaction_id="int-1", input_tokens=10, output_tokens=5
        )

    return stream


def _resolved_conversation(store, principal=PRINCIPAL):
    """A conversation whose last row is an unanswered console note — i.e. the
    exact state an approval or capture resolution leaves behind."""
    store.append_turn(principal, "upgrade the firmware", "Approve the card.")
    conv = store.get_active_conversation(principal)
    store.append_event(principal, conv, "[console] approved; executed.")
    return conv


class TestResumeDue:
    def test_due_after_a_resolution(self, client):
        conv = _resolved_conversation(_store())
        r = client.get("/api/chat/resume-due")
        assert r.status_code == 200
        assert r.json() == {"due": True, "conversation_id": conv}

    def test_not_due_after_an_ordinary_turn(self, client):
        _store().append_turn(PRINCIPAL, "hi", "hello")
        assert client.get("/api/chat/resume-due").json()["due"] is False

    def test_no_conversation_at_all_is_not_due(self, client):
        body = client.get("/api/chat/resume-due").json()
        assert body == {"due": False, "conversation_id": None}

    def test_unknown_conversation_is_404(self, client):
        _resolved_conversation(_store())
        r = client.get(
            "/api/chat/resume-due", params={"conversation_id": "ghost-conv"}
        )
        assert r.status_code == 404


class TestResume:
    def test_persists_a_model_row_and_invents_no_user_message(self, client):
        store = _store()
        conv = _resolved_conversation(store)
        _seed_api_key()
        captured = {}
        with patch(
            "admz.api.routes.chat.stream_turn", _capturing_stream(captured)
        ):
            r = client.post("/api/chat/resume", json={"conversation_id": conv})
        assert r.status_code == 200
        roles = [m["role"] for m in store.get_messages(PRINCIPAL, conv)]
        assert roles == ["user", "model", "event", "model"]
        # The continuation answered the note without inventing a message the
        # operator never typed.
        assert roles.count("user") == 1

    def test_is_seed_free(self, client):
        """The model is handed history alone. A text seed would be a second,
        unmarked channel of ADMZ-authored instruction — the ambiguity the
        [console] marker exists to close."""
        store = _store()
        conv = _resolved_conversation(store)
        _seed_api_key()
        captured = {}
        with patch(
            "admz.api.routes.chat.stream_turn", _capturing_stream(captured)
        ):
            client.post("/api/chat/resume", json={"conversation_id": conv})
        assert captured["user_message"] == ""
        # ...and the history it got still ends in the console note, which is
        # what makes a seed-free contents array well-formed.
        assert captured["history"][-1]["role"] == "event"

    def test_once_answered_a_second_attempt_is_refused(self, client):
        store = _store()
        conv = _resolved_conversation(store)
        _seed_api_key()
        with patch("admz.api.routes.chat.stream_turn", _capturing_stream({})):
            first = client.post(
                "/api/chat/resume", json={"conversation_id": conv}
            )
            second = client.post(
                "/api/chat/resume", json={"conversation_id": conv}
            )
        assert first.status_code == 200
        assert second.status_code == 409
        # exactly one continuation was written
        roles = [m["role"] for m in store.get_messages(PRINCIPAL, conv)]
        assert roles.count("model") == 2  # the original turn + one continuation

    def test_a_second_tab_cannot_double_fire(self, client):
        """Capture opens its form in a second tab and the done page links back
        to /chat, so two live chat tabs are the normal end state — both would
        otherwise answer the same note."""
        store = _store()
        conv = _resolved_conversation(store)
        _seed_api_key()
        note = store.resume_due(PRINCIPAL, conv)
        assert store.try_claim_resume(PRINCIPAL, conv, note) is True  # tab one
        with patch("admz.api.routes.chat.stream_turn", _capturing_stream({})):
            r = client.post("/api/chat/resume", json={"conversation_id": conv})
        assert r.status_code == 409

    def test_unknown_conversation_is_404(self, client):
        _seed_api_key()
        r = client.post(
            "/api/chat/resume", json={"conversation_id": "ghost-conv"}
        )
        assert r.status_code == 404

    def test_budget_gate_refuses_before_the_model_is_called(self, client):
        """A continuation is an ordinary turn and must not be a way around the
        budget. This pins that the endpoint reuses _run_chat_turn rather than
        reaching for stream_turn directly — which would bypass the gate, the
        usage accounting and the audit row in one step."""
        store = _store()
        conv = _resolved_conversation(store)
        _seed_api_key()
        from admz.chatbot.usage import set_daily_budget, token_usage

        set_daily_budget(100)
        token_usage.record_turn(
            principal=PRINCIPAL,
            model="gemini-2.5-flash",
            input_tokens=200,
            output_tokens=0,
        )
        called = {"n": 0}

        async def fake(**kwargs):
            called["n"] += 1
            if False:
                yield  # pragma: no cover

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake):
            client.post("/api/chat/resume", json={"conversation_id": conv})

        assert called["n"] == 0
        # Nothing was persisted, so the note is still unanswered and will be
        # retried once the claim lease lapses — not stranded.
        assert [m["role"] for m in store.get_messages(PRINCIPAL, conv)][-1] == "event"
        assert store.resume_due(PRINCIPAL, conv) is not None

    def test_audit_row_records_that_it_was_a_continuation(self, client):
        """chat_turn rows now answer 'typed, or continued?' — the question
        this feature exists to make answerable in production."""
        conv = _resolved_conversation(_store())
        _seed_api_key()
        with patch("admz.api.routes.chat.stream_turn", _capturing_stream({})):
            client.post("/api/chat/resume", json={"conversation_id": conv})

        import os
        from admz.audit import AuditLog

        entries = AuditLog(os.environ["ADMZ_DB_PATH"]).list_recent(limit=10)
        turns = [e for e in entries if e.action == "chat_turn"]
        assert len(turns) == 1
        assert turns[0].details.get("resume") is True
        assert turns[0].details.get("via_chatbot") is True

    def test_a_typed_turn_is_not_marked_as_a_continuation(self, client):
        """Control for the above — otherwise the flag would be meaningless."""
        _seed_api_key()
        with patch("admz.api.routes.chat.stream_turn", _capturing_stream({})):
            client.post("/api/chat", json={"message": "hi"})

        import os
        from admz.audit import AuditLog

        entries = AuditLog(os.environ["ADMZ_DB_PATH"]).list_recent(limit=10)
        turns = [e for e in entries if e.action == "chat_turn"]
        assert turns[0].details.get("resume") is False

    def test_a_first_turns_action_token_still_links(self, client):
        """Regression pin. Threading an explicit conversation through the turn
        runner must not break the FIRST turn, where append_turn lazily creates
        the conversation — resolving the id only at the start of the turn
        leaves it None there.

        Nothing covered this, and it is the expensive kind of silent: no link
        means the next resolution writes no console note, which means nothing
        is ever due, which kills the very chain #444 exists to fix — one step
        later, in a different file, with no error anywhere.
        """
        from admz.chatbot.events import (
            ChatEvent, ChatEventType, event_done, event_text,
        )

        store = _store()
        _seed_api_key()
        token = "A" * 24

        async def stream(**kwargs):
            yield ChatEvent(
                ChatEventType.TOOL_RESULT,
                {
                    "name": "execute_operation",
                    "result": {
                        "blocked": True,
                        "confirm_url": f"/confirm/{token}",
                    },
                },
            )
            yield event_text("Approve the card.")
            yield event_done(
                interaction_id="int-1", input_tokens=5, output_tokens=5
            )

        with patch("admz.api.routes.chat.stream_turn", stream):
            r = client.post("/api/chat", json={"message": "reboot it"})
        assert r.status_code == 200

        conv = store.get_active_conversation(PRINCIPAL)
        link = store.pop_action_link(token)
        assert link is not None, "a first turn's card was never linked"
        assert link["conversation_id"] == conv

    def test_does_not_move_the_active_conversation_cursor(self, client):
        """The highest-value case, and the one a simpler design gets wrong.

        The firmware incident is exactly this shape: an import runs for
        minutes, and while waiting the operator opens a second chat. The active
        pointer decides where their NEXT TYPED message lands, so answering the
        first conversation must not drag the cursor back to it. A build that
        called set_active_conversation() first would fail here.
        """
        store = _store()
        conv_a = _resolved_conversation(store)
        conv_b = client.post("/api/chat/conversations").json()["id"]
        store.set_active_conversation(PRINCIPAL, conv_b)
        assert store.get_active_conversation(PRINCIPAL) == conv_b
        _seed_api_key()

        with patch("admz.api.routes.chat.stream_turn", _capturing_stream({})):
            r = client.post(
                "/api/chat/resume", json={"conversation_id": conv_a}
            )
        assert r.status_code == 200

        # the answer landed in the conversation that resolved...
        assert [m["role"] for m in store.get_messages(PRINCIPAL, conv_a)][-1] == "model"
        # ...and the operator's cursor never moved.
        assert store.get_active_conversation(PRINCIPAL) == conv_b
