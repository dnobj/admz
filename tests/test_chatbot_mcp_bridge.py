"""Tests for the MCP bridge + tool-handoff to the SDK.

The bridge spawns ``python -m admz mcp`` as a subprocess in
production. These tests mock the mcp.client.stdio surface so we
don't actually fork processes, and they verify:

  - Missing ``mcp`` package raises McpBridgeMissing
  - bridge errors are wrapped in McpBridgeError
  - stream_turn passes tools=[session] to the SDK when MCP is
    available
  - stream_turn proceeds without tools when the bridge fails,
    emitting a notice text event
  - _stream_via_models_api builds a config with tools=[session]
"""

import sys
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest

from admz.chatbot import client as client_mod
from admz.chatbot import mcp_bridge


# ---------------------------------------------------------------------------
# Bridge error surface
# ---------------------------------------------------------------------------


class TestBridgeImportFailure:
    @pytest.mark.asyncio
    async def test_missing_mcp_raises_missing(self, monkeypatch):
        # Force import inside open_mcp_session to fail.
        monkeypatch.setitem(sys.modules, "mcp", None)

        with pytest.raises(mcp_bridge.McpBridgeMissing):
            async with mcp_bridge.open_mcp_session():
                pass  # pragma: no cover — never reached


# ---------------------------------------------------------------------------
# stream_turn: tool handoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_turn_threads_session_into_invoke_stream(monkeypatch):
    """When the bridge yields a session, _invoke_stream sees it."""
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    fake_session = object()  # sentinel — the test checks identity

    @asynccontextmanager
    async def fake_open(use_tools, *, principal=None):
        assert use_tools is True
        yield fake_session

    monkeypatch.setattr(client_mod, "_open_mcp_or_none", fake_open)

    captured = {}

    async def fake_invoke_stream(client, kwargs, *, mcp_session=None):
        captured["session"] = mcp_session
        # Emit a done chunk to terminate cleanly.
        yield _FakeChunk(id="int-1", usage={"input_tokens": 1, "output_tokens": 1})

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke_stream)

    events = []
    async for ev in client_mod.stream_turn(
        user_message="hi",
        api_key="AIza-x",
        model="gemini-3.1-pro",
        system_prompt="sys",
        use_tools=True,
    ):
        events.append(ev)

    assert captured["session"] is fake_session


@pytest.mark.asyncio
async def test_stream_turn_proceeds_without_tools_when_bridge_fails(monkeypatch):
    """If the bridge raises Missing/Error, the turn keeps going with
    no tools and emits a friendly notice."""
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    @asynccontextmanager
    async def fake_open(use_tools, *, principal=None):
        # Simulate bridge open succeeding but yielding None (degraded mode).
        yield None

    monkeypatch.setattr(client_mod, "_open_mcp_or_none", fake_open)

    async def fake_invoke_stream(client, kwargs, *, mcp_session=None):
        assert mcp_session is None
        yield _FakeChunk(text="ok")
        yield _FakeChunk(id="int-1", usage={"input_tokens": 1, "output_tokens": 1})

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke_stream)

    events = []
    async for ev in client_mod.stream_turn(
        user_message="hi",
        api_key="AIza-x",
        model="gemini-3.1-pro",
        system_prompt="sys",
        use_tools=True,
    ):
        events.append(ev)

    text_events = [e for e in events if e.type.value == "text"]
    # The degradation notice + the actual answer.
    assert any("MCP tools unavailable" in e.payload["chunk"] for e in text_events)


@pytest.mark.asyncio
async def test_open_mcp_or_none_yields_none_on_missing(monkeypatch):
    @asynccontextmanager
    async def fake_open():
        raise mcp_bridge.McpBridgeMissing("simulated")
        yield  # unreachable; satisfies asyncgen syntax

    monkeypatch.setattr(client_mod, "open_mcp_session", fake_open)

    async with client_mod._open_mcp_or_none(True) as session:
        assert session is None


@pytest.mark.asyncio
async def test_open_mcp_or_none_yields_none_on_error(monkeypatch):
    @asynccontextmanager
    async def fake_open():
        raise mcp_bridge.McpBridgeError("simulated spawn failure")
        yield

    monkeypatch.setattr(client_mod, "open_mcp_session", fake_open)

    async with client_mod._open_mcp_or_none(True) as session:
        assert session is None


@pytest.mark.asyncio
async def test_open_mcp_or_none_short_circuits_when_use_tools_false():
    """use_tools=False must not even attempt the import — needed so
    the no-tools tests don't drag mcp.client.stdio into the import
    graph at test time."""
    async with client_mod._open_mcp_or_none(False) as session:
        assert session is None


# ---------------------------------------------------------------------------
# _stream_via_models_api: builds config with tools=[session]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_models_api_path_passes_tools_in_config(monkeypatch):
    """When mcp_session is provided, the config dict contains
    ``tools=[session]`` and the SDK is called via aio.models."""
    captured = {}

    async def fake_stream(**kwargs):
        captured.update(kwargs)
        # Async generator that yields nothing.
        if False:
            yield  # pragma: no cover

    fake_client = MagicMock()
    fake_client.aio.models.generate_content_stream = fake_stream

    fake_session = object()
    request_kwargs = {
        "model": "gemini-3.1-pro",
        "system_instruction": "sys",
        "contents": "hi",
    }

    # Bypass GenerateContentConfig coupling: force the dict fallback.
    monkeypatch.setattr(
        client_mod, "_build_generate_config", lambda d: d
    )

    async for _ in client_mod._stream_via_models_api(
        fake_client, request_kwargs, mcp_session=fake_session
    ):
        pass

    assert captured["model"] == "gemini-3.1-pro"
    assert captured["contents"] == "hi"
    config = captured["config"]
    assert config["tools"] == [fake_session]
    assert config["system_instruction"] == "sys"


@pytest.mark.asyncio
async def test_invoke_stream_routes_to_models_api_when_session_present(monkeypatch):
    """_invoke_stream with mcp_session=non-None must go to the
    models-API streaming path, not the Interactions API."""
    interactions_called = False
    models_called = False

    async def interactions_stream(**kwargs):
        nonlocal interactions_called
        interactions_called = True
        if False:
            yield  # pragma: no cover

    async def models_stream(**kwargs):
        nonlocal models_called
        models_called = True
        if False:
            yield  # pragma: no cover

    fake_client = MagicMock()
    fake_client.interactions.astream = interactions_stream
    fake_client.aio.models.generate_content_stream = models_stream

    monkeypatch.setattr(client_mod, "_build_generate_config", lambda d: d)

    fake_session = object()
    request_kwargs = {
        "model": "gemini-3.1-pro",
        "system_instruction": "sys",
        "contents": "hi",
    }

    async for _ in client_mod._invoke_stream(
        fake_client, request_kwargs, mcp_session=fake_session
    ):
        pass

    assert models_called is True
    assert interactions_called is False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeChunk:
    """Match the shape test_chatbot_streaming.py uses."""

    def __init__(self, *, text=None, step_type=None, name=None, usage=None, id=None):
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
