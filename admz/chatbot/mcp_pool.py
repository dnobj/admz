"""Per-principal MCP subprocess pool with idle timeout.

Closes KL-CB-006. The original :func:`admz.chatbot.mcp_bridge.open_mcp_session`
spawns ``python -m admz mcp`` once per chat turn, paying ~1–2 s
of Python+import+handshake overhead on every message. With this
pool, a principal's MCP subprocess is held open between turns
and reused.

Design:

  - Per-principal entry: ``{principal: PoolEntry}``. Each entry
    owns its own subprocess, a per-entry asyncio Lock (chat is
    naturally sequential per user, but the lock makes it safe
    against accidental concurrent use), and a ``last_used``
    timestamp.
  - Acquire: :meth:`McpSessionPool.acquire` is an async context
    manager. It serializes on the entry's lock, refreshes
    ``last_used``, and yields the live ``ClientSession``. On
    exit it releases the lock — the subprocess stays alive.
  - Reaper: a background task scans every minute and evicts
    entries idle past the configured timeout (default 300 s,
    configurable via ``ADMZ_MCP_POOL_IDLE_SECONDS``).
  - Eviction: the entry's owner task unwinds its own
    ``stdio_client`` + ``ClientSession`` contexts, terminating the
    subprocess. Entry and exit happen in the **same task** by
    construction — see :class:`_SessionOwner` and #302.
  - Liveness: an entry whose session has ended is detected and
    **replaced** on the next acquire, rather than handed out. A
    subprocess can die for reasons the pool did not cause.

Falls back gracefully:

  - If ``mcp_bridge`` raises ``McpBridgeMissing`` / ``McpBridgeError``
    on first open, the pool entry isn't created and acquire
    yields ``None`` (matching the no-bridge degradation path the
    chatbot client already handles).

Lifecycle:

  - :meth:`start` is called once at app startup (FastAPI
    lifespan).
  - :meth:`stop` is called on shutdown — evicts all entries and
    cancels the reaper task.

Concurrency notes:

  - Two chat turns for the same principal in flight at once will
    serialize on the entry lock. The UI already enforces
    sequential turns per session, but this defends against
    duplicate-tab scenarios.
  - Two different principals chatting at the same time → two
    different entries → two subprocesses, no contention.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Optional

from admz.chatbot.mcp_bridge import (
    McpBridgeError,
    McpBridgeMissing,
    open_mcp_session,
)

logger = logging.getLogger(__name__)


_DEFAULT_IDLE_SECONDS = 300.0  # 5 minutes
_REAPER_INTERVAL_SECONDS = 60.0


def _principal_to_env(principal: Any) -> Dict[str, str]:
    """Build the env-var dict the MCP subprocess reads at startup.

    CR-4: the spawned ``python -m admz mcp`` process needs to know
    *who* it's serving so it can stamp every audit row with the
    correct ``requester``. Pass the principal's fields as env vars;
    the MCP server reconstructs a :class:`Principal` on the other
    side and uses it in ``call_tool``'s audit wrapper.

    Accepts either a :class:`Principal` (full info passed) or a bare
    string (legacy callers that only know the name). Returns the
    empty dict if neither is usable — the subprocess will fall back
    to a synthetic ``mcp-standalone`` identity in that case.
    """
    if principal is None:
        return {}
    # Avoid an import-time cycle by accepting any object that has
    # the Principal shape.
    name = getattr(principal, "name", None)
    if name is None:
        # Bare string fallback.
        if isinstance(principal, str):
            return {"ADMZ_PRINCIPAL_NAME": principal}
        return {}
    env = {"ADMZ_PRINCIPAL_NAME": str(name)}
    display = getattr(principal, "display_name", None)
    if display:
        env["ADMZ_PRINCIPAL_DISPLAY_NAME"] = str(display)
    domain = getattr(principal, "domain", None)
    if domain:
        env["ADMZ_PRINCIPAL_DOMAIN"] = str(domain)
    source = getattr(principal, "source", None)
    if source:
        env["ADMZ_PRINCIPAL_SOURCE"] = str(source)
    groups = getattr(principal, "groups", None)
    if groups:
        # Comma-separated; matches the shape ReverseProxyAuth produces
        # via LDAP enrichment.
        env["ADMZ_PRINCIPAL_GROUPS"] = ",".join(str(g) for g in groups)
    # H-1: the uvicorn process already runs the SnapshotScheduler.  Suppress
    # it in every pool subprocess to prevent N+1 schedulers writing duplicate
    # snapshot/drift jobs and contending on the git lock.
    env["ADMZ_MCP_NO_SCHEDULER"] = "1"
    return env


def _principal_key(principal: Any) -> str:
    """Extract the pool key from either a Principal or a bare string."""
    if principal is None:
        return "anonymous"
    name = getattr(principal, "name", None)
    if name is not None:
        return str(name)
    return str(principal)


def _resolve_idle_seconds() -> float:
    """Resolve the idle-timeout from env, with a sane default + log on
    bad input."""
    raw = os.getenv("ADMZ_MCP_POOL_IDLE_SECONDS")
    if not raw:
        return _DEFAULT_IDLE_SECONDS
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "ADMZ_MCP_POOL_IDLE_SECONDS=%r is not a number; using default %s",
            raw,
            _DEFAULT_IDLE_SECONDS,
        )
        return _DEFAULT_IDLE_SECONDS
    if value <= 0:
        logger.warning(
            "ADMZ_MCP_POOL_IDLE_SECONDS=%s is not positive; using default %s",
            value,
            _DEFAULT_IDLE_SECONDS,
        )
        return _DEFAULT_IDLE_SECONDS
    return value


_CLOSE_TIMEOUT_SECONDS = 10.0


class _SessionOwner:
    """Owns one pooled session's context for its whole life, in ONE task.

    **This is the fix for the cancel-scope violation (#302).** ``stdio_client``
    and ``ClientSession`` are anyio context managers, and anyio requires a
    cancel scope to be exited by the task that entered it. The pool previously
    entered them on an ``AsyncExitStack`` inside whichever **chat turn's ASGI
    task** happened to open the session, and unwound that stack later from a
    different task — the reaper, the lifespan shutdown, an explicit ``evict``,
    or ``asyncio.create_task(stack.aclose())`` on the duplicate-discard path.
    Every one of those is a different task by construction.

    ``mcp`` 1.26 tolerated it; ``mcp`` 2.x does not, which is why this appeared
    the morning production moved to 2.0.0 and never before.

    Worse than the error itself: the scopes were entered in a task that then
    **ended while they were still open**, leaving a suspended async generator
    holding live scopes. The first turn succeeded, its teardown raised
    ``RuntimeError: Attempted to exit a cancel scope …``, and every later turn
    was handed a session whose transport was already gone — the operator-visible
    *"the first message worked, the next didn't"*.

    The shape here removes the possibility rather than the occurrence: a
    dedicated task opens the session, parks on an event, and closes it on
    request. Entry and exit are the same task **by construction**, so no caller
    can get it wrong and no future call site can reintroduce it.

    It also gives a **type-free liveness signal**. If the subprocess dies, the
    SDK's task group unwinds and :meth:`_run` completes — so ``alive`` goes
    False with no need to recognise any particular exception. Measured: a child
    that exits immediately makes the owning context raise ``ExceptionGroup``
    and the task finish, without the parked owner doing anything.
    """

    __slots__ = ("_spawn_kwargs", "_task", "_ready", "_close_requested",
                 "_principal", "session")

    def __init__(self, principal: str, spawn_kwargs: Dict[str, Any]):
        self._principal = principal
        self._spawn_kwargs = spawn_kwargs
        self._ready: asyncio.Future = asyncio.get_running_loop().create_future()
        self._close_requested = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self.session: Any = None

    async def _run(self) -> None:
        try:
            async with open_mcp_session(**self._spawn_kwargs) as session:
                self.session = session
                if not self._ready.done():
                    self._ready.set_result(session)
                # Park. The session stays open across turns; this task — and
                # only this task — will unwind it.
                await self._close_requested.wait()
        except BaseException as exc:  # noqa: BLE001 — reported, never swallowed
            if not self._ready.done():
                self._ready.set_exception(exc)
            elif not self._close_requested.is_set():
                # It died on its own (subprocess exit, broken pipe). Not an
                # error path anyone is awaiting — but the reason is exactly
                # what #290's stderr capture exists to preserve.
                logger.warning(
                    "MCP pool: session for %s ended unexpectedly: %s",
                    self._principal, exc,
                )

    async def start(self) -> Any:
        """Launch the owner task and return the live session.

        Raises whatever ``open_mcp_session`` raised, in the *caller's* task, so
        existing ``McpBridgeMissing`` / ``McpBridgeError`` handling is unchanged.
        """
        self._task = asyncio.create_task(
            self._run(), name=f"mcp-session-owner:{self._principal}")
        try:
            return await self._ready
        except BaseException:
            # Never leak the task if the spawn failed or we were cancelled
            # while waiting for the handshake.
            await self.aclose()
            raise

    @property
    def alive(self) -> bool:
        """False once the owning task has finished for any reason.

        Deliberately structural. A predicate over exception types would have to
        recognise ``mcp.shared.exceptions.MCPError`` — which is a bare
        ``Exception`` (verified), so the existing
        ``client._is_session_dead_error`` check for ``BrokenPipeError`` /
        ``anyio.ClosedResourceError`` misses it, which is why production served
        a dead session for four consecutive turns.
        """
        return self._task is not None and not self._task.done()

    async def aclose(self) -> None:
        """Ask the owner task to unwind, and wait for it. Never raises."""
        self._close_requested.set()
        task = self._task
        if task is None:
            return
        try:
            await asyncio.wait_for(asyncio.shield(task), _CLOSE_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning(
                "MCP pool: owner task for %s did not exit within %.0fs; "
                "cancelling", self._principal, _CLOSE_TIMEOUT_SECONDS)
            task.cancel()
        except Exception as exc:  # noqa: BLE001 — teardown never propagates
            logger.warning(
                "MCP pool: owner task for %s ended with %s: %s",
                self._principal, type(exc).__name__, exc)


@dataclass
class PoolEntry:
    """One principal's pooled subprocess + session."""

    principal: str
    session: Any
    owner: _SessionOwner
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_used: float = field(default_factory=time.monotonic)

    @property
    def usable(self) -> bool:
        """Whether this entry may be handed to another turn (#302 part 2).

        ONE mechanism, checked on every acquire. An earlier draft also flagged
        the entry from inside ``acquire`` when a turn saw the session fail;
        measured against the tests, that branch changed nothing — the liveness
        check here already catches it, because it runs before every yield. Two
        overlapping mechanisms for one predicate is how #255 happened, so the
        redundant one is gone rather than kept "just in case".
        """
        return self.owner.alive

    async def close(self) -> None:
        """Tear down the underlying stdio subprocess + session."""
        await self.owner.aclose()


class McpSessionPool:
    """Process-local pool of MCP subprocesses keyed by principal."""

    def __init__(self, idle_seconds: Optional[float] = None):
        self._entries: Dict[str, PoolEntry] = {}
        self._entries_lock = asyncio.Lock()
        self._idle_seconds = (
            idle_seconds if idle_seconds is not None else _resolve_idle_seconds()
        )
        self._reaper_task: Optional[asyncio.Task] = None
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Spin up the background reaper."""
        if self._started:
            return
        self._started = True
        self._reaper_task = asyncio.create_task(self._reaper_loop())
        logger.info(
            "MCP session pool started (idle_timeout=%.0fs)", self._idle_seconds
        )

    async def stop(self) -> None:
        """Cancel the reaper and evict every entry."""
        self._started = False
        if self._reaper_task is not None:
            self._reaper_task.cancel()
            try:
                await self._reaper_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reaper_task = None
        await self._evict_all()
        logger.info("MCP session pool stopped")

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def acquire(self, principal: Any) -> AsyncIterator[Any]:
        """Yield a live MCP session for ``principal``.

        ``principal`` may be either a bare string (legacy / test
        callers — name only, no env vars passed to the subprocess)
        or a :class:`admz.auth.Principal` (full info — passed to
        the subprocess via ``ADMZ_PRINCIPAL_*`` env vars so the MCP
        server can audit-log every tool call with the correct
        requester).

        Reuses an existing pooled subprocess when possible; opens a
        fresh one otherwise. Yields ``None`` (and logs a warning)
        when the bridge is unavailable (mcp SDK not installed,
        subprocess spawn failed).
        """
        key = _principal_key(principal)
        entry: Optional[PoolEntry] = None
        try:
            entry = await self._get_or_create(key, principal)
        except (McpBridgeMissing, McpBridgeError) as exc:
            logger.warning(
                "MCP pool: bridge unavailable for %s, yielding None: %s",
                key,
                exc,
            )
            yield None
            return

        if entry is None:
            yield None
            return

        async with entry.lock:
            entry.last_used = time.monotonic()
            try:
                yield entry.session
            finally:
                entry.last_used = time.monotonic()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _get_or_create(
        self, key: str, principal: Any = None
    ) -> Optional[PoolEntry]:
        # Fast path: an existing entry, but only if it is still usable. A dead
        # one is dropped here rather than handed out — before #302 the pool
        # returned it unconditionally and kept serving a session whose
        # transport was gone, for four consecutive turns in production, until
        # the 300 s idle sweep.
        stale: Optional[PoolEntry] = None
        async with self._entries_lock:
            existing = self._entries.get(key)
            if existing is not None:
                if existing.usable:
                    return existing
                stale = self._entries.pop(key)
                logger.info(
                    "MCP pool: entry for %s is dead (its session ended); "
                    "replacing it", key,
                )
        if stale is not None:
            await stale.close()

        # Build env vars from the full Principal (CR-4) so the
        # spawned MCP subprocess knows who it's serving. When the
        # caller passed just a string (legacy/test path) we only
        # have a name — skip the kwarg entirely so test doubles
        # that mock open_mcp_session with a narrower signature
        # still work.
        extra_env = _principal_to_env(principal)
        spawn_kwargs: Dict[str, Any] = {}
        if extra_env:
            spawn_kwargs["extra_env"] = extra_env

        # Open a fresh session outside the entries lock so two
        # different principals can spin up concurrently. Re-enter
        # the lock to register — handle the race where another
        # task created the entry while we were spawning.
        owner = _SessionOwner(key, spawn_kwargs)
        try:
            session = await owner.start()
        except (McpBridgeMissing, McpBridgeError):
            raise
        except Exception as exc:
            raise McpBridgeError(
                f"Failed to open pooled MCP session: {exc}"
            ) from exc

        async with self._entries_lock:
            # Race: another task created an entry while we were
            # opening ours. Discard ours, use theirs.
            existing = self._entries.get(key)
            if existing is not None and existing.usable:
                # Close the duplicate. This is now a plain `await`: the owner
                # unwinds itself in its own task, so there is nothing to hand
                # to `asyncio.create_task`. That fire-and-forget call was the
                # same cancel-scope violation as the rest, just on a rarer
                # trigger — and it discarded the result, so a failure to
                # terminate the duplicate subprocess was silent.
                await owner.aclose()
                return existing

            entry = PoolEntry(
                principal=key,
                session=session,
                owner=owner,
            )
            self._entries[key] = entry
            logger.debug(
                "MCP pool: created entry for %s (pool size=%d)",
                key,
                len(self._entries),
            )
            return entry

    async def _reaper_loop(self) -> None:
        """Background task: evict entries idle past the timeout."""
        try:
            while True:
                await asyncio.sleep(_REAPER_INTERVAL_SECONDS)
                await self._evict_idle()
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("MCP pool reaper crashed: %s", exc)

    async def evict(self, principal: Any) -> bool:
        """Drop ``principal``'s pool entry and close its subprocess.

        Accepts either a string name or a :class:`Principal`.

        Used when the caller detects the session is dead (typically
        anyio.ClosedResourceError raised by the SDK trying to use a
        subprocess whose stdio streams are gone). Returns True if
        an entry was actually evicted, False if there was nothing
        to evict.

        Safe to call concurrently — the entries-lock serializes
        the lookup, and closing the subprocess happens outside the
        lock so other principals' acquires aren't blocked.
        """
        key = _principal_key(principal)
        async with self._entries_lock:
            entry = self._entries.pop(key, None)
        if entry is None:
            return False
        logger.info(
            "MCP pool: explicitly evicting %s (pool size now=%d)",
            key,
            len(self._entries),
        )
        await entry.close()
        return True

    async def _evict_idle(self) -> None:
        """Evict any entry whose ``last_used`` is older than the timeout."""
        cutoff = time.monotonic() - self._idle_seconds
        to_close: list = []
        async with self._entries_lock:
            stale = [
                p for p, e in self._entries.items() if e.last_used < cutoff
            ]
            for principal in stale:
                entry = self._entries.pop(principal)
                to_close.append(entry)
                logger.info(
                    "MCP pool: evicting idle entry for %s "
                    "(pool size now=%d)",
                    principal,
                    len(self._entries),
                )

        # Close subprocesses outside the lock so closing doesn't
        # block other acquires.
        for entry in to_close:
            await entry.close()

    async def _evict_all(self) -> None:
        to_close: list = []
        async with self._entries_lock:
            to_close = list(self._entries.values())
            self._entries.clear()
        for entry in to_close:
            await entry.close()

    # ------------------------------------------------------------------
    # Introspection (handy for tests + future status endpoint)
    # ------------------------------------------------------------------

    def size(self) -> int:
        return len(self._entries)

    def known_principals(self) -> list:
        return list(self._entries.keys())


# Module-level singleton — wired into the FastAPI lifespan in main.py.
mcp_pool = McpSessionPool()
