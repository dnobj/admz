"""Tests for the streaming chat path (Phase 5B).

Covers:
  - stream_turn() async generator behavior (mocked SDK chunks)
  - _translate_stream_chunk() shape probing
  - POST /chat/stream SSE response (mocked stream_turn)
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from admz.chatbot import client as client_mod
from admz.chatbot.events import ChatEventType


# ---------------------------------------------------------------------------
# stream_turn() async generator
# ---------------------------------------------------------------------------


class _FakeChunk:
    """Lightweight SDK chunk stand-in. The translator probes attributes."""

    def __init__(
        self,
        *,
        text=None,
        step_type=None,
        name=None,
        usage=None,
        id=None,
    ):
        if text is not None:
            self.text = text
        if step_type is not None:
            self.step_type = step_type
        if name is not None:
            self.name = name
        if usage is not None:
            self.usage = usage
        if id is not None:
            self.id = id


@pytest.mark.asyncio
async def test_stream_turn_emits_start_text_done_sequence(monkeypatch):
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    async def fake_invoke_stream(client, kwargs):
        yield _FakeChunk(text="Hello, ")
        yield _FakeChunk(text="world.")
        yield _FakeChunk(
            id="int-final", usage={"input_tokens": 8, "output_tokens": 4}
        )

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke_stream)

    events = []
    async for ev in client_mod.stream_turn(
        user_message="hi",
        api_key="AIza-x",
        model="gemini-3.1-pro",
        system_prompt="sys",
    ):
        events.append(ev)

    types = [e.type for e in events]
    # First event must be START, last must be DONE.
    assert types[0] == ChatEventType.START
    assert types[-1] == ChatEventType.DONE
    # Two text chunks in between.
    text_events = [e for e in events if e.type == ChatEventType.TEXT]
    assert len(text_events) == 2
    assert text_events[0].payload["chunk"] == "Hello, "
    assert text_events[1].payload["chunk"] == "world."

    done = events[-1]
    assert done.payload["interaction_id"] == "int-final"
    assert done.payload["input_tokens"] == 8
    assert done.payload["output_tokens"] == 4


@pytest.mark.asyncio
async def test_stream_turn_emits_tool_call_events(monkeypatch):
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    async def fake_invoke_stream(client, kwargs):
        yield _FakeChunk(text="Let me check. ")
        yield _FakeChunk(step_type="function_call", name="list_devices")
        yield _FakeChunk(text="Done.")
        yield _FakeChunk(usage={"input_tokens": 3, "output_tokens": 2})

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke_stream)

    events = []
    async for ev in client_mod.stream_turn(
        user_message="hi",
        api_key="AIza-x",
        model="gemini-3.1-pro",
        system_prompt="sys",
    ):
        events.append(ev)

    tool_calls = [e for e in events if e.type == ChatEventType.TOOL_CALL]
    assert len(tool_calls) == 1
    assert tool_calls[0].payload["name"] == "list_devices"


@pytest.mark.asyncio
async def test_stream_turn_unconfigured_yields_error(monkeypatch):
    monkeypatch.setattr(client_mod, "_import_genai", lambda: MagicMock())

    events = []
    async for ev in client_mod.stream_turn(
        user_message="hi",
        api_key="",
        model="gemini-3.1-pro",
        system_prompt="sys",
    ):
        events.append(ev)

    # Only one event — the error.
    assert len(events) == 1
    assert events[0].type == ChatEventType.ERROR
    assert "not configured" in events[0].payload["message"].lower()


@pytest.mark.asyncio
async def test_stream_turn_sdk_failure_yields_error(monkeypatch):
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    async def boom(client, kwargs):
        # Generators raise during iteration; emulate with one yield then raise.
        yield _FakeChunk(text="partial ")
        raise RuntimeError("rate limited")

    monkeypatch.setattr(client_mod, "_invoke_stream", boom)

    events = []
    async for ev in client_mod.stream_turn(
        user_message="hi",
        api_key="AIza-x",
        model="gemini-3.1-pro",
        system_prompt="sys",
    ):
        events.append(ev)

    # We should have at least the start + the partial text + the error.
    types = [e.type for e in events]
    assert ChatEventType.START in types
    assert ChatEventType.ERROR in types
    error_event = next(e for e in events if e.type == ChatEventType.ERROR)
    assert "rate limited" in error_event.payload["message"]


# ---------------------------------------------------------------------------
# _translate_stream_chunk shape probing
# ---------------------------------------------------------------------------


class TestTranslateChunk:
    def test_text_chunk(self):
        ev = client_mod._translate_stream_chunk(_FakeChunk(text="hi"))
        assert ev.type == ChatEventType.TEXT
        assert ev.payload["chunk"] == "hi"

    def test_empty_text_returns_none(self):
        ev = client_mod._translate_stream_chunk(_FakeChunk(text=""))
        assert ev is None

    def test_function_call_step(self):
        chunk = _FakeChunk(step_type="function_call", name="my_tool")
        ev = client_mod._translate_stream_chunk(chunk)
        assert ev.type == ChatEventType.TOOL_CALL
        assert ev.payload["name"] == "my_tool"

    def test_tool_call_step_alias(self):
        # The SDK may use 'tool_call' or 'function_call' interchangeably.
        chunk = _FakeChunk(step_type="tool_call", name="my_tool")
        ev = client_mod._translate_stream_chunk(chunk)
        assert ev.type == ChatEventType.TOOL_CALL

    def test_terminal_chunk_with_usage(self):
        chunk = _FakeChunk(
            id="int-x", usage={"input_tokens": 5, "output_tokens": 2}
        )
        ev = client_mod._translate_stream_chunk(chunk)
        assert ev.type == ChatEventType.DONE
        assert ev.payload["interaction_id"] == "int-x"
        assert ev.payload["input_tokens"] == 5

    def test_completely_unknown_chunk_returns_none(self):
        class Random:
            pass
        assert client_mod._translate_stream_chunk(Random()) is None


# ---------------------------------------------------------------------------
# POST /chat/stream — end-to-end via TestClient
# ---------------------------------------------------------------------------


@pytest.fixture
def stream_client(tmp_path, monkeypatch):
    """A TestClient configured the same way test_chatbot_routes.py uses,
    with singletons swapped to a tmp DB and restored on teardown."""
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

    db_path = str(tmp_path / "admz.db")
    orig_fs = fs_module.fleet_settings
    orig_sess = sess_module.chat_sessions
    orig_boot = cfg_module._bootstrapped

    fs_module.fleet_settings = fs_module.FleetSettings(db_path)
    sess_module.chat_sessions = sess_module.ChatSessionStore(db_path)
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
        cfg_module._bootstrapped = orig_boot


class TestChatStreamRoute:
    def test_stream_endpoint_returns_event_stream_content_type(self, stream_client):
        from admz.chatbot.config import set_api_key
        from admz.chatbot.events import event_done, event_text

        set_api_key("AIza-x")

        async def fake_stream(**kwargs):
            yield event_text("hello ")
            yield event_text("world")
            yield event_done(interaction_id="int-stream", input_tokens=1, output_tokens=1)

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake_stream):
            r = stream_client.post(
                "/chat/stream",
                data={"message": "hi", "model": "gemini-3.1-pro"},
            )
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = r.text
        # SSE format markers
        assert "event: text" in body
        assert "event: done" in body
        # Content
        assert "hello " in body
        assert "world" in body

    def test_stream_endpoint_persists_interaction_id(self, stream_client):
        from admz.chatbot.config import set_api_key
        from admz.chatbot.events import event_done

        set_api_key("AIza-x")

        async def fake_stream(**kwargs):
            yield event_done(interaction_id="int-persist", input_tokens=0, output_tokens=0)

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake_stream):
            stream_client.post(
                "/chat/stream",
                data={"message": "hi", "model": "gemini-3.1-pro"},
            )

        from admz.chatbot.sessions import chat_sessions
        assert chat_sessions.get_interaction_id("anonymous") == "int-persist"

    def test_stream_endpoint_emits_error_when_unconfigured(self, stream_client):
        # No API key set — the route's first event should be an error.
        r = stream_client.post(
            "/chat/stream", data={"message": "hi", "model": "gemini-3.1-pro"}
        )
        # Endpoint returns 200 with an error event (rather than 503)
        # because SSE consumers don't read the body of a non-200 response
        # — the error has to be inside the stream itself.
        assert r.status_code == 200
        assert "event: error" in r.text
        assert "not configured" in r.text.lower()

    def test_stream_endpoint_falls_back_to_default_model(self, stream_client):
        from admz.chatbot.config import set_api_key
        from admz.chatbot.events import event_done

        set_api_key("AIza-x")

        captured = {}

        async def fake_stream(**kwargs):
            captured["model"] = kwargs["model"]
            yield event_done()

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake_stream):
            stream_client.post(
                "/chat/stream",
                data={"message": "hi", "model": "gemini-not-real"},
            )
        assert captured["model"] == "gemini-3.1-pro"
