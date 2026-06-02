"""Tests for the per-event SSE timeout in the chat route (Hotfix #36).

Background: when the pooled MCP subprocess dies in a way the
self-heal path can't recover from, the chat stream silently stops
emitting events and the browser hangs forever. The wrapper added in
admz/api/routes/chat.py `_with_per_event_timeout` surfaces the
stall as an `error` ChatEvent after a configurable timeout
(`ADMZ_CHAT_EVENT_TIMEOUT_SECONDS`, default 120s) so the UI shows
"stream stalled, please retry" instead of an infinite spinner.

This file pins:
  * Timeout fires when the upstream iterator stalls past the budget.
  * On timeout, exactly one error event is yielded then the wrapper
    stops cleanly (no extra events).
  * Normal traffic (events arriving faster than timeout) passes
    through unchanged.
  * Setting ADMZ_CHAT_EVENT_TIMEOUT_SECONDS=0 disables the wrapper
    entirely (legacy behavior).
  * Env-var parsing tolerates garbage (falls back to 120s).
"""

from __future__ import annotations

import asyncio

import pytest

from admz.chatbot.events import ChatEventType
from admz.api.routes.chat import (
    _chat_event_timeout_seconds,
    _with_per_event_timeout,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeEvent:
    """Tiny stand-in for ChatEvent — only `.type` is read by the wrapper."""

    def __init__(self, type_, **payload):
        self.type = type_
        self.payload = payload


async def _stalling_stream(events_then_pause, pause_seconds):
    """Async generator that yields `events_then_pause` quickly, then
    sleeps `pause_seconds` before yielding a final event. Mimics the
    'snapshot kicked off, then subprocess died' shape."""
    for ev in events_then_pause:
        yield ev
        await asyncio.sleep(0)  # yield control so events flush
    await asyncio.sleep(pause_seconds)
    yield _FakeEvent(ChatEventType.DONE)  # should never reach consumer


async def _fast_stream(events):
    """Yields all events with no delay — should pass through unchanged."""
    for ev in events:
        yield ev


async def _collect(aiter, limit=20):
    """Drain up to `limit` events from an async iterator."""
    out = []
    async for ev in aiter:
        out.append(ev)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# Env-var parsing
# ---------------------------------------------------------------------------


class TestTimeoutEnvParsing:
    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("ADMZ_CHAT_EVENT_TIMEOUT_SECONDS", raising=False)
        assert _chat_event_timeout_seconds() == 120.0

    def test_explicit_value(self, monkeypatch):
        monkeypatch.setenv("ADMZ_CHAT_EVENT_TIMEOUT_SECONDS", "30")
        assert _chat_event_timeout_seconds() == 30.0

    def test_zero_disables(self, monkeypatch):
        monkeypatch.setenv("ADMZ_CHAT_EVENT_TIMEOUT_SECONDS", "0")
        assert _chat_event_timeout_seconds() == 0.0

    def test_garbage_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("ADMZ_CHAT_EVENT_TIMEOUT_SECONDS", "abc")
        assert _chat_event_timeout_seconds() == 120.0

    def test_empty_string_falls_back(self, monkeypatch):
        monkeypatch.setenv("ADMZ_CHAT_EVENT_TIMEOUT_SECONDS", "")
        assert _chat_event_timeout_seconds() == 120.0


# ---------------------------------------------------------------------------
# Wrapper behavior
# ---------------------------------------------------------------------------


class TestPerEventTimeout:
    @pytest.mark.asyncio
    async def test_fast_stream_passes_through(self):
        events = [
            _FakeEvent(ChatEventType.START),
            _FakeEvent(ChatEventType.TEXT, chunk="hello"),
            _FakeEvent(ChatEventType.DONE),
        ]
        collected = await _collect(
            _with_per_event_timeout(_fast_stream(events), 5.0)
        )
        assert len(collected) == 3
        assert collected[0].type == ChatEventType.START
        assert collected[2].type == ChatEventType.DONE

    @pytest.mark.asyncio
    async def test_stall_yields_error_event(self):
        # Upstream yields one event then stalls 10s. Timeout is 0.2s
        # so the wrapper should bail with an error before 10s elapses.
        upstream = _stalling_stream(
            [_FakeEvent(ChatEventType.START)],
            pause_seconds=10.0,
        )
        collected = await _collect(
            _with_per_event_timeout(upstream, 0.2)
        )
        # Exactly: 1 start + 1 error, no DONE.
        assert len(collected) == 2
        assert collected[0].type == ChatEventType.START
        assert collected[1].type == ChatEventType.ERROR
        assert "stalled" in collected[1].payload.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_zero_timeout_disables_wrapper(self):
        # With timeout=0, the wrapper is bypassed. A stall would
        # block forever, so we don't test that — but we can verify
        # fast traffic passes through cleanly.
        events = [
            _FakeEvent(ChatEventType.START),
            _FakeEvent(ChatEventType.DONE),
        ]
        collected = await _collect(
            _with_per_event_timeout(_fast_stream(events), 0)
        )
        assert len(collected) == 2

    @pytest.mark.asyncio
    async def test_negative_timeout_also_disables(self):
        events = [_FakeEvent(ChatEventType.START)]
        collected = await _collect(
            _with_per_event_timeout(_fast_stream(events), -1.0)
        )
        assert len(collected) == 1

    @pytest.mark.asyncio
    async def test_completes_normally_within_timeout(self):
        # Slow but within budget: events ~0.1s apart, timeout 1s.
        async def slow_stream():
            yield _FakeEvent(ChatEventType.START)
            await asyncio.sleep(0.1)
            yield _FakeEvent(ChatEventType.TEXT, chunk="a")
            await asyncio.sleep(0.1)
            yield _FakeEvent(ChatEventType.DONE)

        collected = await _collect(
            _with_per_event_timeout(slow_stream(), 1.0)
        )
        assert len(collected) == 3
        assert collected[-1].type == ChatEventType.DONE

    @pytest.mark.asyncio
    async def test_no_double_error_after_timeout(self):
        # After yielding the error event, the wrapper must STOP —
        # no further events should leak through even if the upstream
        # eventually wakes up.
        upstream = _stalling_stream(
            [_FakeEvent(ChatEventType.START)],
            pause_seconds=0.5,
        )
        collected = await _collect(
            _with_per_event_timeout(upstream, 0.1)
        )
        # Should be exactly start + error, NOT start + error + done.
        assert len(collected) == 2
        types = [ev.type for ev in collected]
        assert ChatEventType.DONE not in types
