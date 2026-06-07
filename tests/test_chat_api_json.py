"""Tests for POST /api/chat — the JSON endpoint for programmatic testing.

Covers:
  - Happy path returns full response JSON shape
  - Tool calls captured in tool_calls[]
  - Budget gate rejects with success=false and rejected_by_budget=true
  - Invalid model falls back to default
  - Unconfigured (no API key) returns success=false with friendly error
  - SDK error wraps as success=false with the error string
  - Audit + usage records still emitted (same as the SSE path)
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


def _seed_api_key():
    from admz.chatbot.config import set_api_key
    set_api_key("AIza-test")


def _fake_stream(
    *,
    text="hello world",
    input_tokens=10,
    output_tokens=5,
    interaction_id="int-1",
    tool_calls=None,
):
    """Build a fake stream_turn that yields a representative event sequence."""
    from admz.chatbot.events import event_done, event_text, event_tool_call

    async def stream(**kwargs):
        for tc in tool_calls or []:
            yield event_tool_call(tc, f"{tc}()")
        yield event_text(text)
        yield event_done(
            interaction_id=interaction_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    return stream


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestJsonChatHappyPath:
    def test_basic_round_trip(self, client):
        _seed_api_key()
        with patch(
            "admz.api.routes.chat.stream_turn",
            side_effect=_fake_stream(
                text="Here are your devices.",
                input_tokens=42,
                output_tokens=87,
                interaction_id="int-abc",
            ),
        ):
            r = client.post(
                "/api/chat",
                json={"message": "list my devices"},
            )

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["response"] == "Here are your devices."
        assert body["error"] is None
        assert body["model"] in {"gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"}
        assert body["interaction_id"] == "int-abc"
        assert body["input_tokens"] == 42
        assert body["output_tokens"] == 87
        assert body["cost_usd"] is not None
        assert body["cost_usd"] > 0  # tokens × non-zero rate
        assert body["tool_calls"] == []
        assert body["rejected_by_budget"] is False

    def test_tool_calls_captured(self, client):
        _seed_api_key()
        with patch(
            "admz.api.routes.chat.stream_turn",
            side_effect=_fake_stream(
                text="OK, listed.",
                tool_calls=["list_devices", "get_device"],
            ),
        ):
            r = client.post(
                "/api/chat",
                json={"message": "tell me everything"},
            )

        assert r.status_code == 200
        body = r.json()
        assert body["tool_calls"] == ["list_devices", "get_device"]

    def test_model_selection_honored(self, client):
        _seed_api_key()
        captured = {}

        async def fake(**kwargs):
            from admz.chatbot.events import event_done, event_text
            captured["model"] = kwargs["model"]
            yield event_text("hi")
            yield event_done(input_tokens=1, output_tokens=1, interaction_id="x")

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake):
            r = client.post(
                "/api/chat",
                json={"message": "hi", "model": "gemini-2.5-pro"},
            )

        assert r.status_code == 200
        assert r.json()["model"] == "gemini-2.5-pro"
        assert captured["model"] == "gemini-2.5-pro"

    def test_invalid_model_falls_back_to_default(self, client):
        _seed_api_key()
        captured = {}

        async def fake(**kwargs):
            from admz.chatbot.events import event_done, event_text
            captured["model"] = kwargs["model"]
            yield event_text("hi")
            yield event_done(input_tokens=1, output_tokens=1, interaction_id="x")

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake):
            r = client.post(
                "/api/chat",
                json={"message": "hi", "model": "gemini-totally-fake"},
            )

        assert r.status_code == 200
        # DEFAULT_MODEL is gemini-2.5-flash.
        assert r.json()["model"] == "gemini-2.5-flash"
        assert captured["model"] == "gemini-2.5-flash"

    def test_use_tools_false_passes_through(self, client):
        _seed_api_key()
        captured = {}

        async def fake(**kwargs):
            from admz.chatbot.events import event_done, event_text
            captured["use_tools"] = kwargs.get("use_tools")
            yield event_text("hi")
            yield event_done(input_tokens=1, output_tokens=1, interaction_id="x")

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake):
            r = client.post(
                "/api/chat",
                json={"message": "hi", "use_tools": False},
            )

        assert r.status_code == 200
        assert captured["use_tools"] is False


# ---------------------------------------------------------------------------
# Unhappy paths
# ---------------------------------------------------------------------------


class TestJsonChatUnconfigured:
    def test_no_api_key_returns_friendly_json(self, client):
        # Don't seed the key.
        r = client.post("/api/chat", json={"message": "hi"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert "not configured" in body["error"].lower()
        assert body["response"] == ""
        # Still report model (so callers can log it).
        assert body["model"]


class TestJsonChatBudgetGate:
    def test_over_budget_rejected_with_flag(self, client):
        _seed_api_key()
        from admz.chatbot.usage import set_daily_budget, token_usage
        set_daily_budget(100)
        token_usage.record_turn(
            principal="anonymous",
            model="gemini-2.5-flash",
            input_tokens=200,
            output_tokens=0,
        )

        called = {"count": 0}

        async def fake(**kwargs):
            called["count"] += 1
            if False:
                yield  # pragma: no cover

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake):
            r = client.post("/api/chat", json={"message": "hi"})

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert body["rejected_by_budget"] is True
        assert "budget" in body["error"].lower()
        # stream_turn must not have been called — the gate fires first.
        assert called["count"] == 0


class TestJsonChatEmptyResponseBackstop:
    """Bug 5: Flash-Lite occasionally returns 200 OK with zero text
    chunks. We surface that as a friendly error rather than letting
    the user see an empty bot bubble."""

    def test_zero_output_surfaced_as_helpful_error(self, client):
        """Case A: output_tokens=0, no text — thinking-only or content filter."""
        _seed_api_key()
        from admz.chatbot.events import event_done

        async def empty_stream(**kwargs):
            yield event_done(interaction_id="x", input_tokens=42, output_tokens=0)

        with patch("admz.api.routes.chat.stream_turn", side_effect=empty_stream):
            r = client.post(
                "/api/chat",
                json={"message": "hi", "model": "gemini-2.5-flash"},
            )

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert "no text" in body["error"].lower()
        assert "gemini-2.5-flash" in body["error"]
        # Case A is a neutral thinking-only/safety-filter message: rephrase.
        assert "rephras" in body["error"].lower()
        assert body["response"] == ""

    def test_3x_zero_output_neutral_message(self, client):
        """Case A on 3.x — neutral message (the 3.x tool quirk is fixed by the
        manual loop, so no model-switch nudge)."""
        _seed_api_key()
        from admz.chatbot.events import event_done

        async def empty_stream(**kwargs):
            yield event_done(interaction_id="x", input_tokens=100, output_tokens=0)

        with patch("admz.api.routes.chat.stream_turn", side_effect=empty_stream):
            r = client.post(
                "/api/chat",
                json={"message": "hi", "model": "gemini-3.5-flash"},
            )

        body = r.json()
        assert body["success"] is False
        assert "gemini-3.5-flash" in body["error"]
        assert "no text" in body["error"].lower()
        assert "rephras" in body["error"].lower()

    def test_nonzero_tokens_empty_text_neutral_backstop(self, client):
        """Case B: tokens > 0 but no visible text. The gemini-3.x AFC bug that
        used to cause this is now handled by the in-ADMZ manual function-calling
        loop, so this is just a neutral backstop for other causes (mid-stream
        content filter, malformed final turn) — no AFC/model-switch messaging."""
        _seed_api_key()
        from admz.chatbot.events import event_done

        async def empty_with_tokens(**kwargs):
            yield event_done(
                interaction_id="x", input_tokens=7000, output_tokens=10
            )

        with patch(
            "admz.api.routes.chat.stream_turn", side_effect=empty_with_tokens
        ):
            r = client.post(
                "/api/chat",
                json={"message": "what cameras do i have?", "model": "gemini-3.5-flash"},
            )

        body = r.json()
        assert body["success"] is False
        assert "gemini-3.5-flash" in body["error"]
        assert "10" in body["error"]  # the output token count
        assert "retry" in body["error"].lower() or "rephras" in body["error"].lower()
        # neutral — no stale AFC-bug claim
        assert "AFC" not in body["error"]
        assert body["input_tokens"] == 7000
        assert body["output_tokens"] == 10

    def test_2x_nonzero_tokens_empty_text_does_not_falsely_blame_3x(self, client):
        """If the same shape (tokens > 0, empty text) happens on 2.5,
        the error should still fire but shouldn't reference the 3.x
        bug specifically."""
        _seed_api_key()
        from admz.chatbot.events import event_done

        async def afc_broken_stream(**kwargs):
            yield event_done(
                interaction_id="x", input_tokens=7000, output_tokens=10
            )

        with patch(
            "admz.api.routes.chat.stream_turn", side_effect=afc_broken_stream
        ):
            r = client.post(
                "/api/chat",
                json={"message": "hi", "model": "gemini-2.5-flash"},
            )

        body = r.json()
        assert body["success"] is False
        assert "gemini-2.5-flash" in body["error"]
        # Should NOT claim this is the 3.x bug.
        assert "3.x" not in body["error"]
        assert "gemini-3" not in body["error"]

    def test_nonzero_output_with_text_is_normal(self, client):
        """Sanity: a turn with actual text is NOT flagged."""
        _seed_api_key()
        from admz.chatbot.events import event_done, event_text

        async def normal_stream(**kwargs):
            yield event_text("hello")
            yield event_done(interaction_id="x", input_tokens=10, output_tokens=5)

        with patch("admz.api.routes.chat.stream_turn", side_effect=normal_stream):
            r = client.post("/api/chat", json={"message": "hi"})

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["response"] == "hello"
        assert body["error"] is None


class TestJsonChatSdkError:
    def test_stream_error_surfaced_as_json(self, client):
        _seed_api_key()
        from admz.chatbot.events import event_error

        async def fake(**kwargs):
            yield event_error("Gemini stream error: 503 unavailable")

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake):
            r = client.post("/api/chat", json={"message": "hi"})

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert "503" in body["error"]


# ---------------------------------------------------------------------------
# Audit log integration (same channel as the SSE route)
# ---------------------------------------------------------------------------


class TestJsonChatHistory:
    """Phase 5E: conversation history threading across turns."""

    def test_first_turn_sends_empty_history(self, client):
        _seed_api_key()
        captured = {}

        async def fake(**kwargs):
            from admz.chatbot.events import event_done, event_text
            captured["history"] = kwargs.get("history")
            yield event_text("first answer")
            yield event_done(input_tokens=1, output_tokens=1, interaction_id="x")

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake):
            r = client.post("/api/chat", json={"message": "first question"})

        assert r.status_code == 200
        # First turn: history is empty.
        assert captured["history"] == []

    def test_second_turn_includes_first_turn_in_history(self, client):
        """The chronological [user, model, user, model, ...] shape
        is what gets fed to stream_turn on subsequent turns."""
        _seed_api_key()

        async def first_stream(**kwargs):
            from admz.chatbot.events import event_done, event_text
            yield event_text("8 devices")
            yield event_done(input_tokens=1, output_tokens=1, interaction_id="x")

        with patch("admz.api.routes.chat.stream_turn", side_effect=first_stream):
            client.post(
                "/api/chat",
                json={"message": "list my devices"},
            )

        captured_history = {}

        async def second_stream(**kwargs):
            from admz.chatbot.events import event_done, event_text
            captured_history["history"] = kwargs.get("history")
            yield event_text("done")
            yield event_done(input_tokens=1, output_tokens=1, interaction_id="y")

        with patch("admz.api.routes.chat.stream_turn", side_effect=second_stream):
            client.post(
                "/api/chat",
                json={"message": "restart device A"},
            )

        history = captured_history["history"]
        assert len(history) == 2
        assert history[0] == {"role": "user", "text": "list my devices"}
        assert history[1] == {"role": "model", "text": "8 devices"}

    def test_empty_response_not_persisted(self, client):
        """Budget rejections / SDK errors shouldn't pollute history."""
        _seed_api_key()
        from admz.chatbot.events import event_error

        async def err_stream(**kwargs):
            yield event_error("503 unavailable")

        with patch("admz.api.routes.chat.stream_turn", side_effect=err_stream):
            client.post("/api/chat", json={"message": "failing message"})

        # Next turn should still see an empty history.
        captured = {}

        async def ok_stream(**kwargs):
            from admz.chatbot.events import event_done, event_text
            captured["history"] = kwargs.get("history")
            yield event_text("ok")
            yield event_done(input_tokens=1, output_tokens=1, interaction_id="x")

        with patch("admz.api.routes.chat.stream_turn", side_effect=ok_stream):
            client.post("/api/chat", json={"message": "second"})

        assert captured["history"] == []

    def test_chat_clear_drops_history(self, client):
        _seed_api_key()

        async def fake(**kwargs):
            from admz.chatbot.events import event_done, event_text
            yield event_text("answer")
            yield event_done(input_tokens=1, output_tokens=1, interaction_id="x")

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake):
            client.post("/api/chat", json={"message": "first"})
            client.post("/api/chat", json={"message": "second"})

        # Two turns happened — verify by direct DB inspection.
        import admz.chatbot.sessions as sess_module
        assert len(sess_module.chat_sessions.get_history("anonymous")) == 4

        # /chat/clear is a form POST that redirects.
        r = client.post("/chat/clear")
        assert r.status_code == 303

        assert sess_module.chat_sessions.get_history("anonymous") == []


class TestJsonChatAudit:
    def test_successful_turn_audited_with_via_chatbot(self, client):
        _seed_api_key()
        with patch(
            "admz.api.routes.chat.stream_turn",
            side_effect=_fake_stream(),
        ):
            client.post("/api/chat", json={"message": "hi"})

        from admz.audit import AuditLog
        import os
        log = AuditLog(os.environ["ADMZ_DB_PATH"])
        entries = log.list_recent(limit=10)
        turns = [e for e in entries if e.action == "chat_turn"]
        assert len(turns) == 1
        assert turns[0].details.get("via_chatbot") is True
        assert turns[0].success is True

    def test_budget_rejection_audited(self, client):
        _seed_api_key()
        from admz.chatbot.usage import set_daily_budget, token_usage
        set_daily_budget(50)
        token_usage.record_turn(
            principal="anonymous",
            model="gemini-2.5-flash",
            input_tokens=100,
            output_tokens=0,
        )

        client.post("/api/chat", json={"message": "hi"})

        from admz.audit import AuditLog
        import os
        log = AuditLog(os.environ["ADMZ_DB_PATH"])
        entries = log.list_recent(limit=10)
        rejects = [e for e in entries if e.action == "chat_budget_exceeded"]
        assert len(rejects) == 1
        assert rejects[0].success is False
