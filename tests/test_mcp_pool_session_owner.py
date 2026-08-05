"""The pool opens and closes a session in ONE task, and never serves a corpse (#302).

Two defects, both visible in production on 2026-08-04:

```
21:53:10  Gemini generateContent -> 200 OK          <- the FIRST turn succeeds
          RuntimeError: Attempted to exit a cancel scope that isn't
                        the current task's current cancel scope
21:53:26  MCPError: Connection closed               <- second turn
21:53:38  MCPError: Connection closed               <- third
21:54:30  MCPError: Connection closed               <- fourth
```

**1. The cancel-scope violation.** `stdio_client` and `ClientSession` are anyio
context managers; anyio requires a cancel scope to be exited by the task that
entered it. The pool entered them on an `AsyncExitStack` inside a chat turn's
ASGI task and unwound that stack from a *different* task — the reaper, the
lifespan, `evict()`, or `asyncio.create_task(stack.aclose())`. mcp 1.26
tolerated it; mcp 2.0 does not, which is why this appeared the morning
production moved to 2.0.0.

**2. The pool served the dead session for four turns.** Independent of (1) and
arguably worse. `client._is_session_dead_error` only recognises
`BrokenPipeError` and `anyio.ClosedResourceError`; the error production
actually saw is `mcp.shared.exceptions.MCPError`, which is a bare `Exception`
— so nothing evicted, and the entry survived until the 300 s idle sweep.

**Vacuity note.** "a dead entry is replaced" is trivially green if *every*
entry is replaced — that would silently undo the whole point of pooling and
reintroduce the 1–2 s per-turn spawn the pool exists to remove. So
`TestAHealthySessionIsStillPooled` runs first and pins reuse. Likewise "close
did not raise" is worthless on its own, because the old code *swallowed* the
error in `PoolEntry.close`: the assertions below check that teardown actually
**ran**, not that it stayed quiet.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import anyio
import pytest

from admz.chatbot import mcp_pool as M


class FakeSession:
    def __init__(self, ident: int):
        self.ident = ident
        self.closed = False
        self.opened_in: str = ""
        self.closed_in: str = ""
        #: Set to make the stand-in "subprocess" die, exactly as a real one
        #: does: a child task inside the SDK's task group raises. Deliberately
        #: NOT a pool API — these tests must run unchanged against the old
        #: code, or they prove nothing about it.
        self.die = asyncio.Event()

    async def call(self):
        if self.die.is_set():
            from mcp.shared.exceptions import MCPError
            raise MCPError(-32000, "Connection closed")
        return "ok"

    def kill(self):
        self.die.set()


def _task_name() -> str:
    t = asyncio.current_task()
    return t.get_name() if t is not None else "<none>"


class Spawner:
    """A stand-in for `mcp_bridge.open_mcp_session` with the SAME anyio
    structure — nested task groups, exactly like `stdio_client` +
    `ClientSession`. Without the real scopes the bug is unreproducible."""

    def __init__(self):
        self.count = 0
        self.sessions: list = []
        self.fail_next = False

    @asynccontextmanager
    async def open(self, **kwargs):
        if self.fail_next:
            self.fail_next = False
            raise M.McpBridgeError("spawn failed")
        self.count += 1
        sess = FakeSession(self.count)
        self.sessions.append(sess)

        async def reader():
            """Stands in for stdio_client's stream-reader child task. When the
            subprocess dies this raises, unwinding the task group — which is
            exactly how a real dead child is noticed."""
            await sess.die.wait()
            raise ConnectionResetError("subprocess exited")

        async with anyio.create_task_group() as outer:     # stdio_client
            async with anyio.create_task_group() as inner:  # ClientSession
                inner.start_soon(reader)
                sess.opened_in = _task_name()
                try:
                    yield sess
                finally:
                    sess.closed = True
                    sess.closed_in = _task_name()
                    inner.cancel_scope.cancel()
            outer.cancel_scope.cancel()


@pytest.fixture
def spawner(monkeypatch):
    s = Spawner()
    monkeypatch.setattr(M, "open_mcp_session", s.open)
    return s


@pytest.fixture
def pool():
    return M.McpSessionPool(idle_seconds=999)


async def _turn(pool, principal="alice"):
    """One chat turn — deliberately its own task, as an ASGI request is."""
    async def body():
        async with pool.acquire(principal) as sess:
            return sess
    return await asyncio.create_task(body())


# ── the anti-vacuity guard ───────────────────────────────────────────────────
class TestAHealthySessionIsStillPooled:
    @pytest.mark.asyncio
    async def test_two_turns_reuse_one_subprocess(self, pool, spawner):
        """FIRST. If the fix replaced entries eagerly, every assertion below
        would pass for free while silently restoring the per-turn spawn cost
        the pool exists to avoid."""
        a = await _turn(pool)
        b = await _turn(pool)
        assert a is b, "the pooled session was not reused"
        assert spawner.count == 1, f"spawned {spawner.count} subprocesses for 2 turns"
        assert not a.closed
        await pool.stop()

    @pytest.mark.asyncio
    async def test_the_second_turn_gets_a_working_session(self, pool, spawner):
        """The operator-visible symptom, stated directly: *the first message
        worked, the next didn't*."""
        await _turn(pool)
        second = await _turn(pool)
        assert second is not None and not second.closed
        await pool.stop()


# ── defect 1: one task owns the whole lifetime ───────────────────────────────
class TestEntryAndExitShareOneTask:
    @pytest.mark.asyncio
    async def test_the_session_is_opened_and_closed_in_the_same_task(
            self, pool, spawner):
        """THE structural fix. Before this the session was opened in whichever
        chat turn's task happened to be first and closed in the reaper's."""
        await _turn(pool)
        sess = spawner.sessions[0]
        await asyncio.create_task(pool.evict("alice"))
        assert sess.closed, "the session context never unwound"
        assert sess.opened_in == sess.closed_in, (
            f"opened in {sess.opened_in!r} but closed in {sess.closed_in!r} — "
            "that is the cancel-scope violation")

    @pytest.mark.asyncio
    async def test_evicting_from_another_task_really_tears_down(
            self, pool, spawner):
        """The assertion that fails on the old code. `PoolEntry.close` used to
        swallow the RuntimeError with a warning, so eviction *reported*
        success while the subprocess kept running — a zombie per evicted
        principal. Assert the teardown RAN, not that it was quiet."""
        await _turn(pool)
        sess = spawner.sessions[0]
        assert not sess.closed
        await asyncio.create_task(pool.evict("alice"))
        assert sess.closed, (
            "evict() returned but the session was never closed — the "
            "subprocess is still running")
        assert pool.size() == 0

    @pytest.mark.asyncio
    async def test_shutdown_closes_every_entry(self, pool, spawner):
        await _turn(pool, "alice")
        await _turn(pool, "bob")
        assert spawner.count == 2
        await pool.stop()
        assert all(s.closed for s in spawner.sessions)
        assert pool.size() == 0

    @pytest.mark.asyncio
    async def test_the_reaper_can_evict_without_a_scope_error(
            self, pool, spawner):
        """The idle sweep runs in the reaper's task — a third task, different
        from both the opener and any request."""
        await _turn(pool)
        pool._idle_seconds = -1.0          # everything is stale
        await asyncio.create_task(pool._evict_idle())
        assert spawner.sessions[0].closed and pool.size() == 0

    @pytest.mark.asyncio
    async def test_the_duplicate_discard_closes_before_returning(
            self, pool, spawner):
        """`mcp_pool.py:308` used to do `asyncio.create_task(stack.aclose())`
        — the same violation on a rarer trigger, fire-and-forget, so a failure
        to terminate the duplicate subprocess was silent. Now it is awaited."""
        first = await _turn(pool)
        # Force the race arm: an entry already exists when _get_or_create
        # finishes spawning its own.
        entry = await pool._get_or_create("alice", "alice")
        assert entry.session is first
        # Exactly one session is still open; any duplicate was closed.
        assert sum(1 for s in spawner.sessions if not s.closed) == 1
        await pool.stop()


# ── defect 2: a dead entry is replaced, not served ───────────────────────────
class TestADeadEntryIsReplaced:
    """Every test here kills the session via `sess.kill()` — a child task
    inside the stand-in SDK's task group raising, exactly as a real dying
    subprocess does. No pool internals are touched, so these run unchanged
    against the old code and fail there BEHAVIOURALLY rather than on a missing
    attribute."""

    @pytest.mark.asyncio
    async def test_a_session_that_ended_is_not_handed_out_again(
            self, pool, spawner):
        """THE four-turns defect, in four lines. The subprocess dies between
        turns; the next acquire must produce a NEW session, not the corpse."""
        first = await _turn(pool)
        first.kill()
        await asyncio.sleep(0.05)          # let the task group unwind

        second = await _turn(pool)
        assert second is not first, "the pool served a dead session"
        assert await second.call() == "ok"
        assert spawner.count == 2
        await pool.stop()

    @pytest.mark.asyncio
    async def test_four_consecutive_turns_survive_a_death(self, pool, spawner):
        """Production's exact shape: turn 1 works, the session dies, and turns
        2-4 were all handed the same corpse. Every turn must work."""
        s1 = await _turn(pool)
        assert await s1.call() == "ok"
        s1.kill()
        await asyncio.sleep(0.05)
        for n in (2, 3, 4):
            sess = await _turn(pool)
            assert await sess.call() == "ok", f"turn {n} got a dead session"
        assert spawner.count == 2, "it should respawn once, not once per turn"
        await pool.stop()

    @pytest.mark.asyncio
    async def test_death_is_detected_without_naming_an_exception_type(self):
        """Why the pool's check is structural rather than a type allow-list.
        The error production saw is `mcp.shared.exceptions.MCPError`, a bare
        `Exception` — so `client._is_session_dead_error`, which recognises
        only `BrokenPipeError` and `anyio.ClosedResourceError`, cannot see it.
        That is why nothing evicted for four turns."""
        from mcp.shared.exceptions import MCPError

        from admz.chatbot.client import _is_session_dead_error
        assert not issubclass(MCPError, (BrokenPipeError, anyio.ClosedResourceError))
        assert _is_session_dead_error(MCPError(-32000, "Connection closed")) is False

    @pytest.mark.asyncio
    async def test_a_turn_that_raises_over_a_dead_session_still_recovers(
            self, pool, spawner):
        """The caller propagates. The pool must not need it to."""
        first = await _turn(pool)

        async def bad_turn():
            async with pool.acquire("alice") as sess:
                sess.kill()
                await asyncio.sleep(0.05)
                await sess.call()          # raises MCPError
        with pytest.raises(Exception):
            await asyncio.create_task(bad_turn())

        assert (await _turn(pool)) is not first
        await pool.stop()

    @pytest.mark.asyncio
    async def test_a_swallowed_failure_still_replaces_the_entry(
            self, pool, spawner):
        """The path that actually happened. The chat client degrades to "no
        tools" rather than propagating, so the turn returns CLEANLY over a dead
        session. If replacement were conditional on an exception reaching the
        pool, the corpse would be served again — which is precisely what
        production did."""
        first = await _turn(pool)

        async def quiet_turn():
            async with pool.acquire("alice") as sess:
                sess.kill()
                await asyncio.sleep(0.05)
                try:
                    await sess.call()
                except Exception:
                    pass               # the client swallows it
        await asyncio.create_task(quiet_turn())

        second = await _turn(pool)
        assert second is not first, (
            "a turn that swallowed its tool error left the corpse pooled")
        assert await second.call() == "ok"
        await pool.stop()


# ── failures still degrade the way callers expect ────────────────────────────
class TestFailureModesAreUnchanged:
    @pytest.mark.asyncio
    async def test_a_failed_spawn_still_yields_none(self, pool, spawner):
        """The no-bridge degradation the chat client already handles."""
        spawner.fail_next = True
        async with pool.acquire("alice") as sess:
            assert sess is None
        assert pool.size() == 0

    @pytest.mark.asyncio
    async def test_a_failed_spawn_leaves_no_owner_task_behind(
            self, pool, spawner):
        before = len(asyncio.all_tasks())
        spawner.fail_next = True
        async with pool.acquire("alice"):
            pass
        await asyncio.sleep(0)
        assert len(asyncio.all_tasks()) <= before, "an owner task leaked"

    @pytest.mark.asyncio
    async def test_a_recovered_spawn_works_after_a_failure(self, pool, spawner):
        spawner.fail_next = True
        async with pool.acquire("alice") as sess:
            assert sess is None
        second = await _turn(pool)
        assert second is not None and second.ident == 1
        await pool.stop()
