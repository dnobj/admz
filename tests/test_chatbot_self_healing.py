"""Self-healing MCP pool: evict dead sessions and retry once.

When the pooled subprocess crashes or its stdio streams close
between turns, the next chat turn hits anyio.ClosedResourceError
inside the Gemini SDK's MCP session-introspection call. We detect
this error, evict the stale pool entry, and retry the turn once
with a fresh subprocess — invisible to the user.
"""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest

from admz.chatbot import client as client_mod


# ---------------------------------------------------------------------------
# Error detection
# ---------------------------------------------------------------------------


class TestSessionDeadDetection:
    def test_anyio_closed_resource_error_is_dead(self):
        import anyio
        exc = anyio.ClosedResourceError()
        assert client_mod._is_session_dead_error(exc) is True

    def test_broken_pipe_is_dead(self):
        exc = BrokenPipeError("pipe closed")
        assert client_mod._is_session_dead_error(exc) is True

    def test_generic_runtime_error_is_not_dead(self):
        assert client_mod._is_session_dead_error(RuntimeError("hi")) is False

    def test_503_error_is_not_session_dead(self):
        """503 from Gemini is a retryable transient — handled separately by
        the rate-limit/transient retry, not the session-dead path."""
        exc = MagicMock(spec=["code"])
        exc.code = 503
        assert client_mod._is_session_dead_error(exc) is False

    def test_wrapped_closed_resource_error_is_dead(self):
        """SDK wraps the underlying anyio error — chain walking should still
        recognize it."""
        import anyio
        inner = anyio.ClosedResourceError()
        outer = RuntimeError("operation failed")
        outer.__cause__ = inner
        assert client_mod._is_session_dead_error(outer) is True


# ---------------------------------------------------------------------------
# Pool eviction
# ---------------------------------------------------------------------------


class TestPoolEvict:
    @pytest.mark.asyncio
    async def test_evict_known_principal_returns_true(self):
        from admz.chatbot.mcp_pool import (McpSessionPool, PoolEntry,
                                           _SessionOwner)

        pool = McpSessionPool()
        # #302: an entry now holds a _SessionOwner, not an AsyncExitStack, so
        # the session's context is entered and exited by ONE task. A
        # never-started owner closes to a no-op, which is all these
        # key-bookkeeping assertions need.
        entry = PoolEntry(
            principal="alice",
            session=MagicMock(),
            owner=_SessionOwner("alice", {}),
        )
        pool._entries["alice"] = entry

        result = await pool.evict("alice")
        assert result is True
        assert "alice" not in pool._entries

    @pytest.mark.asyncio
    async def test_evict_unknown_principal_returns_false(self):
        from admz.chatbot.mcp_pool import McpSessionPool

        pool = McpSessionPool()
        result = await pool.evict("ghost")
        assert result is False

    @pytest.mark.asyncio
    async def test_evict_only_affects_target_principal(self):
        from admz.chatbot.mcp_pool import (McpSessionPool, PoolEntry,
                                           _SessionOwner)

        pool = McpSessionPool()
        pool._entries["alice"] = PoolEntry(
            principal="alice", session=MagicMock(),
            owner=_SessionOwner("alice", {}),
        )
        pool._entries["bob"] = PoolEntry(
            principal="bob", session=MagicMock(),
            owner=_SessionOwner("bob", {}),
        )

        await pool.evict("alice")
        assert "alice" not in pool._entries
        assert "bob" in pool._entries


# ---------------------------------------------------------------------------
# stream_turn: dead session triggers eviction + retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dead_session_evicted_and_retried(monkeypatch):
    """First attempt yields ClosedResourceError before any chunks;
    stream_turn evicts the pool entry and retries with a fresh
    session that succeeds. The user sees a clean response."""
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    eviction_calls = []

    async def fake_evict(principal):
        eviction_calls.append(principal)

    # Patch the helper directly so we don't need a real pool.
    monkeypatch.setattr(client_mod, "_evict_stale_session", fake_evict)

    fake_session = object()

    @asynccontextmanager
    async def fake_open(use_tools, *, principal=None):
        yield fake_session

    monkeypatch.setattr(client_mod, "_open_mcp_or_none", fake_open)

    attempt_count = {"n": 0}

    async def fake_invoke_stream(client, kwargs, *, mcp_session=None):
        attempt_count["n"] += 1
        if attempt_count["n"] == 1:
            import anyio
            raise anyio.ClosedResourceError()
        # Second attempt yields a clean chunk and a done.
        chunk = MagicMock(spec=["text", "candidates", "usage_metadata"])
        chunk.text = "fresh session worked"
        chunk.usage_metadata = None
        yield chunk

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke_stream)

    events = []
    async for ev in client_mod.stream_turn(
        user_message="hi",
        api_key="AIza-x",
        model="gemini-2.5-flash",
        system_prompt="sys",
        principal="alice",
        use_tools=True,
    ):
        events.append(ev)

    # Eviction happened once.
    assert eviction_calls == ["alice"]
    # Two attempts: first failed with ClosedResourceError, second succeeded.
    assert attempt_count["n"] == 2
    # Final text event made it through.
    text_events = [e for e in events if e.type.value == "text"]
    assert any("fresh session worked" in e.payload.get("chunk", "") for e in text_events)
    # Final done event present.
    assert any(e.type.value == "done" for e in events)


@pytest.mark.asyncio
async def test_dead_session_no_retry_after_chunks_yielded(monkeypatch):
    """If chunks have already been yielded to the user, we can't
    safely retry — surface the error."""
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    eviction_calls = []

    async def fake_evict(principal):
        eviction_calls.append(principal)

    monkeypatch.setattr(client_mod, "_evict_stale_session", fake_evict)

    @asynccontextmanager
    async def fake_open(use_tools, *, principal=None):
        yield object()

    monkeypatch.setattr(client_mod, "_open_mcp_or_none", fake_open)

    async def fake_invoke_stream(client, kwargs, *, mcp_session=None):
        # Yield ONE chunk first, then die.
        chunk = MagicMock(spec=["text", "candidates", "usage_metadata"])
        chunk.text = "partial output"
        chunk.usage_metadata = None
        yield chunk
        import anyio
        raise anyio.ClosedResourceError()

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke_stream)

    events = []
    async for ev in client_mod.stream_turn(
        user_message="hi",
        api_key="AIza-x",
        model="gemini-2.5-flash",
        system_prompt="sys",
        principal="alice",
    ):
        events.append(ev)

    # No eviction attempted — chunk was already yielded.
    assert eviction_calls == []
    # Error surfaced.
    error_events = [e for e in events if e.type.value == "error"]
    assert len(error_events) == 1


@pytest.mark.asyncio
async def test_non_session_dead_error_not_retried(monkeypatch):
    """Generic RuntimeError shouldn't trigger a session-evict-and-retry."""
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    eviction_calls = []

    async def fake_evict(principal):
        eviction_calls.append(principal)

    monkeypatch.setattr(client_mod, "_evict_stale_session", fake_evict)

    @asynccontextmanager
    async def fake_open(use_tools, *, principal=None):
        yield object()

    monkeypatch.setattr(client_mod, "_open_mcp_or_none", fake_open)

    async def fake_invoke_stream(client, kwargs, *, mcp_session=None):
        raise RuntimeError("not a session error")
        yield  # pragma: no cover

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke_stream)

    events = []
    async for ev in client_mod.stream_turn(
        user_message="hi",
        api_key="AIza-x",
        model="gemini-2.5-flash",
        system_prompt="sys",
        principal="alice",
    ):
        events.append(ev)

    assert eviction_calls == []
    assert any(e.type.value == "error" for e in events)


@pytest.mark.asyncio
async def test_dead_session_with_no_principal_no_retry(monkeypatch):
    """principal=None means the per-turn-spawn path, not the pool —
    there's no entry to evict, so we just surface the error."""
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    @asynccontextmanager
    async def fake_open(use_tools, *, principal=None):
        yield object()

    monkeypatch.setattr(client_mod, "_open_mcp_or_none", fake_open)

    async def fake_invoke_stream(client, kwargs, *, mcp_session=None):
        import anyio
        raise anyio.ClosedResourceError()
        yield  # pragma: no cover

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke_stream)

    events = []
    async for ev in client_mod.stream_turn(
        user_message="hi",
        api_key="AIza-x",
        model="gemini-2.5-flash",
        system_prompt="sys",
        principal=None,  # no pool
    ):
        events.append(ev)

    error_events = [e for e in events if e.type.value == "error"]
    assert len(error_events) == 1
