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


class TestTheContinuationKeepsTheModel:
    """2026-09-15: a job typed on one model was continued on the org default,
    because the console sent no model and the endpoint fell straight back to
    it. The other model wrote an approval link instead of calling the tool.
    A continuation answers the turn before it, so it runs on that turn's model.

    Each test reads the model back from ``last_model``, which the turn records
    as the model it actually ran on.
    """

    @staticmethod
    def _default_and_other():
        from admz.chatbot.config import SELECTABLE_MODELS, get_chatbot_config

        default = get_chatbot_config().default_model
        return default, next(m for m in SELECTABLE_MODELS if m != default)

    def test_it_runs_on_the_model_the_page_sends(self, client):
        store = _store()
        conv = _resolved_conversation(store)
        _seed_api_key()
        _, other = self._default_and_other()
        with patch("admz.api.routes.chat.stream_turn", _capturing_stream({})):
            r = client.post(
                "/api/chat/resume", json={"conversation_id": conv, "model": other}
            )
        assert r.status_code == 200
        assert store.last_model(PRINCIPAL) == other

    def test_without_one_it_runs_on_the_model_this_principal_last_used(self, client):
        """The incident's shape: the page sent no model at all."""
        store = _store()
        conv = _resolved_conversation(store)
        _seed_api_key()
        _, other = self._default_and_other()
        store.set_interaction_id(PRINCIPAL, "int-0", other)
        with patch("admz.api.routes.chat.stream_turn", _capturing_stream({})):
            r = client.post("/api/chat/resume", json={"conversation_id": conv})
        assert r.status_code == 200
        assert store.last_model(PRINCIPAL) == other, (
            "the continuation switched off the model the operator was using")

    def test_an_unselectable_last_model_falls_back_to_the_default(self, client):
        """Control for the test above: the fallback still exists, it is only
        no longer the first resort."""
        store = _store()
        conv = _resolved_conversation(store)
        _seed_api_key()
        default, _ = self._default_and_other()
        store.set_interaction_id(PRINCIPAL, "int-0", "not-a-real-model")
        with patch("admz.api.routes.chat.stream_turn", _capturing_stream({})):
            client.post("/api/chat/resume", json={"conversation_id": conv})
        assert store.last_model(PRINCIPAL) == default

    def test_the_console_sends_its_model_with_the_continuation(self):
        """This repo has no JavaScript test tooling, so the request is pinned by
        its source: the continuation's body must carry the picked model."""
        import re
        from pathlib import Path

        import admz.api as api_pkg

        src = (Path(api_pkg.__file__).parent / "static" / "chat.js").read_text(
            encoding="utf-8")
        call = re.search(r'fetch\("/api/chat/resume",\s*\{.*?\}\)', src, re.S)
        assert call, "the continuation request moved — re-pin this test"
        assert "model:" in call.group(0)


# ---------------------------------------------------------------------------
# A note that lands while a turn is running (2026-09-23)
#
# Three cards were approved within six seconds. The first approval's
# continuation read the conversation, then the other two approvals wrote their
# notes, then the continuation saved its reply — after them. The trailing row
# was a model row, so nothing was due, and the reply told the operator two
# accepts were still awaiting approval although both had run.
# ---------------------------------------------------------------------------


def _mid_turn_stream(store, conv, notes, captured=None, text="Reverted SSH."):
    """A fake stream_turn that, while the turn is running, has approvals land:
    it appends console notes AFTER the turn read its history."""
    from admz.chatbot.events import event_done, event_text

    async def stream(**kwargs):
        if captured is not None:
            captured.update(kwargs)
        for note in notes:
            store.append_event(PRINCIPAL, conv, note)
        yield event_text(text)
        yield event_done(interaction_id="int-9", input_tokens=10, output_tokens=5)

    return stream


class TestANoteThatLandsMidTurn:
    def test_a_note_written_during_a_continuation_stays_due(self, client):
        store = _store()
        conv = _resolved_conversation(store)
        _, seen = store.get_history_and_watermark(PRINCIPAL, conversation_id=conv)
        store.append_event(PRINCIPAL, conv, "[console] second card approved")
        store.append_model_turn(PRINCIPAL, conv, "The first one is done.",
                                seen_upto=seen)

        rows = store.get_messages(PRINCIPAL, conv)
        assert [m["role"] for m in rows] == [
            "user", "model", "event", "model", "event"]
        assert rows[-1]["text"] == "[console] second card approved"
        assert store.resume_due(PRINCIPAL, conv) is not None

    def test_a_note_the_turn_saw_is_left_where_it_is(self, client):
        """Control: only notes newer than the watermark move."""
        store = _store()
        conv = _resolved_conversation(store)
        _, seen = store.get_history_and_watermark(PRINCIPAL, conversation_id=conv)
        store.append_model_turn(PRINCIPAL, conv, "Done.", seen_upto=seen)

        assert [m["role"] for m in store.get_messages(PRINCIPAL, conv)] == [
            "user", "model", "event", "model"]
        assert store.resume_due(PRINCIPAL, conv) is None

    def test_refiled_notes_keep_their_text_time_and_order(self, client):
        store = _store()
        conv = _resolved_conversation(store)
        _, seen = store.get_history_and_watermark(PRINCIPAL, conversation_id=conv)
        store.append_event(PRINCIPAL, conv, "[console] second")
        store.append_event(PRINCIPAL, conv, "[console] third")
        before = {m["text"]: m["created_at"] for m in store.get_messages(PRINCIPAL, conv)}

        store.append_model_turn(PRINCIPAL, conv, "First done.", seen_upto=seen)

        rows = store.get_messages(PRINCIPAL, conv)
        assert [m["text"] for m in rows[-3:]] == [
            "First done.", "[console] second", "[console] third"]
        for m in rows[-2:]:
            assert m["created_at"] == before[m["text"]]

    def test_a_typed_turn_refiles_them_too(self, client):
        """An approval that lands while a typed message is being answered."""
        store = _store()
        store.append_turn(PRINCIPAL, "hi", "hello")
        conv = store.get_active_conversation(PRINCIPAL)
        _, seen = store.get_history_and_watermark(PRINCIPAL, conversation_id=conv)
        store.append_event(PRINCIPAL, conv, "[console] approved mid-reply")
        store.append_turn(PRINCIPAL, "status?", "All good.", seen=(conv, seen))

        assert [m["role"] for m in store.get_messages(PRINCIPAL, conv)] == [
            "user", "model", "user", "model", "event"]
        assert store.resume_due(PRINCIPAL, conv) is not None

    def test_nothing_moves_when_the_reply_lands_in_another_conversation(self, client):
        """The active conversation can change mid-turn; the watermark belongs
        to the conversation it was read in."""
        store = _store()
        store.append_turn(PRINCIPAL, "hi", "hello")
        conv = store.get_active_conversation(PRINCIPAL)
        store.append_event(PRINCIPAL, conv, "[console] a note")
        store.append_turn(PRINCIPAL, "status?", "All good.", seen=("other-conv", 0))

        assert [m["role"] for m in store.get_messages(PRINCIPAL, conv)] == [
            "user", "model", "event", "user", "model"]

    def test_a_claim_follows_its_note(self, client):
        """A tab already answering a note keeps its claim after the note moves,
        so the same note is not answered twice."""
        store = _store()
        conv = _resolved_conversation(store)
        _, seen = store.get_history_and_watermark(PRINCIPAL, conversation_id=conv)
        store.append_event(PRINCIPAL, conv, "[console] second")
        note = store.resume_due(PRINCIPAL, conv)
        assert store.try_claim_resume(PRINCIPAL, conv, note) is True

        store.append_model_turn(PRINCIPAL, conv, "First done.", seen_upto=seen)

        moved = store.resume_due(PRINCIPAL, conv)
        assert moved is not None and moved != note
        assert store.try_claim_resume(PRINCIPAL, conv, moved) is False

    def test_the_watermark(self, client):
        store = _store()
        assert store.get_history_and_watermark(PRINCIPAL) == ([], None)
        conv = store.create_conversation(PRINCIPAL)
        assert store.get_history_and_watermark(
            PRINCIPAL, conversation_id=conv) == ([], 0)
        store.append_event(PRINCIPAL, conv, "[console] x")
        newest = store.resume_due(PRINCIPAL, conv)
        _, seen = store.get_history_and_watermark(PRINCIPAL, conversation_id=conv)
        assert seen == newest
        _, seen0 = store.get_history_and_watermark(
            PRINCIPAL, max_turns=0, conversation_id=conv)
        assert seen0 == newest

    def test_the_2026_09_23_sequence(self, client):
        """End to end: the first approval's continuation runs while two more
        approvals land. The next continuation is still owed, and it sees both
        notes last, as the thing to answer."""
        store = _store()
        conv = _resolved_conversation(store)
        _seed_api_key()
        with patch("admz.api.routes.chat.stream_turn", _mid_turn_stream(
                store, conv, ["[console] accept on cam-2 executed",
                              "[console] accept on cam-3 executed"])):
            r = client.post("/api/chat/resume", json={"conversation_id": conv})
        assert r.status_code == 200
        assert client.get("/api/chat/resume-due").json()["due"] is True

        captured = {}
        with patch("admz.api.routes.chat.stream_turn",
                   _capturing_stream(captured, text="All three are done.")):
            r = client.post("/api/chat/resume", json={"conversation_id": conv})
        assert r.status_code == 200
        assert [h["text"] for h in captured["history"][-3:]] == [
            "Reverted SSH.",
            "[console] accept on cam-2 executed",
            "[console] accept on cam-3 executed",
        ]
        assert client.get("/api/chat/resume-due").json()["due"] is False

    def test_a_typed_turn_end_to_end(self, client):
        store = _store()
        store.append_turn(PRINCIPAL, "hi", "hello")
        conv = store.get_active_conversation(PRINCIPAL)
        _seed_api_key()
        with patch("admz.api.routes.chat.stream_turn", _mid_turn_stream(
                store, conv, ["[console] approved mid-reply"], text="Status ok.")):
            r = client.post("/api/chat", json={"message": "status?"})
        assert r.status_code == 200
        assert [m["role"] for m in store.get_messages(PRINCIPAL, conv)] == [
            "user", "model", "user", "model", "event"]
        assert client.get("/api/chat/resume-due").json()["due"] is True

    def test_the_console_answers_a_note_after_the_reply_instead_of_dropping_it(self):
        """No JS test tooling here, so the browser half is pinned by source: a
        continuation asked for while any reply streams is remembered, and both
        kinds of reply look again when they finish."""
        import re
        from pathlib import Path

        import admz.api as api_pkg

        src = (Path(api_pkg.__file__).parent / "static" / "chat.js").read_text(
            encoding="utf-8")
        body = re.search(
            r"function maybeResumeConversation\(\) \{\s*(.*?)\n    return fetch",
            src, re.S)
        assert body, "maybeResumeConversation moved — re-pin this test"
        assert "resumeWanted = true" in body.group(1)
        assert "if (resumeInFlight) return;" not in src, (
            "a note that lands mid-reply is dropped again")
        typed = re.search(r'fetch\("/chat/stream".*?\.finally\(function \(\) \{(.*?)\}\);',
                          src, re.S)
        assert typed and "answerDeferredNotes()" in typed.group(1)
        resumed = re.search(r'fetch\("/api/chat/resume".*?\.finally\(function \(\) \{(.*?)\}\);',
                            src, re.S)
        assert resumed and "answerDeferredNotes()" in resumed.group(1)
