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
  - Eviction: ``AsyncExitStack.aclose()`` unwinds the
    ``stdio_client`` + ``ClientSession`` contexts cleanly,
    terminating the subprocess.

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
from contextlib import AsyncExitStack, asynccontextmanager
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


@dataclass
class PoolEntry:
    """One principal's pooled subprocess + session."""

    principal: str
    session: Any
    stack: AsyncExitStack
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_used: float = field(default_factory=time.monotonic)

    async def close(self) -> None:
        """Tear down the underlying stdio subprocess + session."""
        try:
            await self.stack.aclose()
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "PoolEntry.close: aclose raised for %s: %s",
                self.principal,
                exc,
            )


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
    async def acquire(self, principal: str) -> AsyncIterator[Any]:
        """Yield a live MCP session for ``principal``.

        Reuses an existing pooled subprocess when possible; opens a
        fresh one otherwise. Yields ``None`` (and logs a warning)
        when the bridge is unavailable (mcp SDK not installed,
        subprocess spawn failed). Callers should match the
        existing chatbot-client semantics: ``None`` means "no
        tools available, degrade gracefully".
        """
        entry: Optional[PoolEntry] = None
        try:
            entry = await self._get_or_create(principal)
        except (McpBridgeMissing, McpBridgeError) as exc:
            logger.warning(
                "MCP pool: bridge unavailable for %s, yielding None: %s",
                principal,
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

    async def _get_or_create(self, principal: str) -> Optional[PoolEntry]:
        # First, fast path: existing entry.
        async with self._entries_lock:
            existing = self._entries.get(principal)
            if existing is not None:
                return existing

        # Open a fresh session outside the entries lock so two
        # different principals can spin up concurrently. Re-enter
        # the lock to register — handle the race where another
        # task created the entry while we were spawning.
        stack = AsyncExitStack()
        try:
            session = await stack.enter_async_context(open_mcp_session())
        except (McpBridgeMissing, McpBridgeError):
            await stack.aclose()
            raise
        except Exception as exc:
            await stack.aclose()
            raise McpBridgeError(
                f"Failed to open pooled MCP session: {exc}"
            ) from exc

        async with self._entries_lock:
            # Race: another task created an entry while we were
            # opening ours. Discard ours, use theirs.
            existing = self._entries.get(principal)
            if existing is not None:
                # Close the duplicate quietly.
                asyncio.create_task(stack.aclose())
                return existing

            entry = PoolEntry(
                principal=principal,
                session=session,
                stack=stack,
            )
            self._entries[principal] = entry
            logger.debug(
                "MCP pool: created entry for %s (pool size=%d)",
                principal,
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
