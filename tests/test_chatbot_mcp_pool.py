"""Tests for admz.chatbot.mcp_pool — pooling, reuse, idle eviction.

Mocks open_mcp_session so subprocess spawning never happens.
Verifies:
  - acquire() reuses the same session across calls for the same principal
  - different principals get different sessions
  - eviction drops idle entries
  - stop() drains everything
  - bridge failures degrade to None (no entry created)
"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest

from admz.chatbot import mcp_bridge
from admz.chatbot import mcp_pool as pool_module
from admz.chatbot.mcp_pool import McpSessionPool


# ---------------------------------------------------------------------------
# A fake "open_mcp_session" that returns a unique session per call.
# ---------------------------------------------------------------------------


class _FakeSession:
    _counter = 0

    def __init__(self, label):
        self.label = label
        self.closed = False

    def __repr__(self):
        return f"_FakeSession({self.label})"


def _fake_open_factory():
    """Returns a (cm_factory, close_callback) tuple.

    cm_factory() is what we monkeypatch open_mcp_session to.
    close_callback receives session labels when their context
    exits — so tests can assert eviction-driven closures.
    """
    closures: list = []

    @asynccontextmanager
    async def cm():
        _FakeSession._counter += 1
        sess = _FakeSession(f"s-{_FakeSession._counter}")
        try:
            yield sess
        finally:
            sess.closed = True
            closures.append(sess.label)

    return cm, closures


@pytest.fixture
def fake_bridge(monkeypatch):
    """Replace open_mcp_session in the pool's import with our fake."""
    factory, closures = _fake_open_factory()
    monkeypatch.setattr(pool_module, "open_mcp_session", factory)
    return closures


# ---------------------------------------------------------------------------
# Acquire semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_returns_session_for_principal(fake_bridge):
    pool = McpSessionPool(idle_seconds=60)
    try:
        async with pool.acquire("alice") as session:
            assert session is not None
            assert session.label.startswith("s-")
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_two_acquires_same_principal_reuse_session(fake_bridge):
    """The whole point of the pool: same principal → same subprocess."""
    pool = McpSessionPool(idle_seconds=60)
    try:
        async with pool.acquire("alice") as s1:
            label_first = s1.label
        async with pool.acquire("alice") as s2:
            label_second = s2.label
        assert label_first == label_second
        assert pool.size() == 1
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_different_principals_get_different_sessions(fake_bridge):
    pool = McpSessionPool(idle_seconds=60)
    try:
        async with pool.acquire("alice") as alice:
            async with pool.acquire("bob") as bob:
                assert alice.label != bob.label
        assert pool.size() == 2
        assert set(pool.known_principals()) == {"alice", "bob"}
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_acquire_yields_none_on_bridge_missing(monkeypatch):
    @asynccontextmanager
    async def boom():
        raise mcp_bridge.McpBridgeMissing("simulated missing mcp")
        yield  # unreachable

    monkeypatch.setattr(pool_module, "open_mcp_session", boom)

    pool = McpSessionPool(idle_seconds=60)
    try:
        async with pool.acquire("alice") as session:
            assert session is None
        # No entry created.
        assert pool.size() == 0
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_acquire_yields_none_on_bridge_error(monkeypatch):
    @asynccontextmanager
    async def boom():
        raise mcp_bridge.McpBridgeError("simulated spawn failure")
        yield  # unreachable

    monkeypatch.setattr(pool_module, "open_mcp_session", boom)

    pool = McpSessionPool(idle_seconds=60)
    try:
        async with pool.acquire("alice") as session:
            assert session is None
        assert pool.size() == 0
    finally:
        await pool.stop()


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evict_idle_drops_stale_entries(fake_bridge):
    """Manually invoke the idle-eviction logic to verify it removes
    entries whose last_used is too old."""
    pool = McpSessionPool(idle_seconds=0.001)  # essentially immediate

    try:
        async with pool.acquire("alice"):
            pass
        assert pool.size() == 1

        # Wait long enough that the entry is now stale relative to the
        # idle threshold.
        await asyncio.sleep(0.01)
        await pool._evict_idle()

        assert pool.size() == 0
        # The fake's close path should have been hit when the
        # AsyncExitStack ran.
        assert "s-" in fake_bridge[0]  # at least one closure recorded
    finally:
        await pool.stop()


@pytest.mark.asyncio
async def test_stop_evicts_all_entries(fake_bridge):
    pool = McpSessionPool(idle_seconds=600)
    async with pool.acquire("alice"):
        pass
    async with pool.acquire("bob"):
        pass
    assert pool.size() == 2

    await pool.stop()
    assert pool.size() == 0
    # Both sessions should have been closed.
    assert len(fake_bridge) == 2


# ---------------------------------------------------------------------------
# Concurrency: lock serializes same-principal use
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_principal_serializes_on_lock(fake_bridge):
    """Two simultaneous acquires for the same principal must not
    interleave — one waits while the other holds the lock."""
    pool = McpSessionPool(idle_seconds=600)

    events: list = []

    async def turn(label: str, hold: float):
        async with pool.acquire("alice"):
            events.append(("enter", label))
            await asyncio.sleep(hold)
            events.append(("exit", label))

    try:
        # Fire two turns in parallel; expect strict enter/exit
        # interleaving (no enter-enter pair).
        await asyncio.gather(turn("A", 0.02), turn("B", 0.02))

        # The order is non-deterministic, but each enter must be
        # followed by its own exit before the other enter.
        first_enter = events[0]
        assert first_enter[0] == "enter"
        first_label = first_enter[1]
        assert events[1] == ("exit", first_label)
    finally:
        await pool.stop()


# ---------------------------------------------------------------------------
# Lifecycle + idle-seconds env override
# ---------------------------------------------------------------------------


def test_resolve_idle_seconds_default(monkeypatch):
    monkeypatch.delenv("ADMZ_MCP_POOL_IDLE_SECONDS", raising=False)
    from admz.chatbot.mcp_pool import _resolve_idle_seconds, _DEFAULT_IDLE_SECONDS
    assert _resolve_idle_seconds() == _DEFAULT_IDLE_SECONDS


def test_resolve_idle_seconds_env_override(monkeypatch):
    monkeypatch.setenv("ADMZ_MCP_POOL_IDLE_SECONDS", "30")
    from admz.chatbot.mcp_pool import _resolve_idle_seconds
    assert _resolve_idle_seconds() == 30.0


def test_resolve_idle_seconds_invalid_falls_back(monkeypatch, caplog):
    import logging
    monkeypatch.setenv("ADMZ_MCP_POOL_IDLE_SECONDS", "not-a-number")
    with caplog.at_level(logging.WARNING):
        from admz.chatbot.mcp_pool import _resolve_idle_seconds, _DEFAULT_IDLE_SECONDS
        assert _resolve_idle_seconds() == _DEFAULT_IDLE_SECONDS
    assert any("not a number" in rec.message for rec in caplog.records)


def test_resolve_idle_seconds_zero_falls_back(monkeypatch, caplog):
    import logging
    monkeypatch.setenv("ADMZ_MCP_POOL_IDLE_SECONDS", "0")
    with caplog.at_level(logging.WARNING):
        from admz.chatbot.mcp_pool import _resolve_idle_seconds, _DEFAULT_IDLE_SECONDS
        assert _resolve_idle_seconds() == _DEFAULT_IDLE_SECONDS


# ---------------------------------------------------------------------------
# _open_mcp_or_none integration: principal-supplied path uses the pool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_mcp_or_none_uses_pool_when_principal_given(monkeypatch):
    from admz.chatbot import client as client_mod

    fake_session = object()
    calls = []

    @asynccontextmanager
    async def fake_pool_acquire(principal):
        calls.append(principal)
        yield fake_session

    # Stub the module-level mcp_pool.acquire so we don't need real
    # subprocess plumbing.
    fake_pool = MagicMock()
    fake_pool.acquire = fake_pool_acquire
    monkeypatch.setattr(pool_module, "mcp_pool", fake_pool)

    async with client_mod._open_mcp_or_none(True, principal="alice") as session:
        assert session is fake_session
    assert calls == ["alice"]


@pytest.mark.asyncio
async def test_open_mcp_or_none_falls_through_when_no_principal(monkeypatch):
    """principal=None must use the per-turn path, not the pool."""
    from admz.chatbot import client as client_mod

    pool_called = []

    @asynccontextmanager
    async def pool_acquire(principal):
        pool_called.append(principal)
        yield object()

    fake_pool = MagicMock()
    fake_pool.acquire = pool_acquire
    monkeypatch.setattr(pool_module, "mcp_pool", fake_pool)

    # Per-turn path: open_mcp_session should be called instead.
    per_turn_called = []

    @asynccontextmanager
    async def fake_open():
        per_turn_called.append(True)
        yield object()

    monkeypatch.setattr(client_mod, "open_mcp_session", fake_open)

    async with client_mod._open_mcp_or_none(True, principal=None) as session:
        assert session is not None
    # Per-turn path used.
    assert per_turn_called == [True]
    # Pool path not used.
    assert pool_called == []
