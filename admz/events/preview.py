"""Transient event preview for the watched-event picker (ADR-0041 amendment).

When an operator wants to pick a NEW watched event, they need to *see* what a
device is emitting right now — but we must not turn the firehose back on to do
it. A :class:`PreviewSession` opens an **ephemeral** WS stream to only the
selected device(s), with ``store=None`` so **nothing is persisted**, and fans
the live events out to the browser (SSE). It lives exactly as long as the picker
is open: the stream tears down when the SSE client disconnects, after an idle
period with no subscriber, or at a hard max-duration cap (abandoned-tab guard).
A global cap bounds how many device connections previews may open at once.

Contrast with steady-state ingest (:mod:`admz.events.ingest`): that persists, is
watch-scoped, and runs continuously; this persists nothing, is device-scoped to
the picker's selection, and is momentary.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, AsyncIterator, Deque, Dict, List, Optional

from admz.events import config as cfg
from admz.events.wsstream import DeviceEventStream

logger = logging.getLogger(__name__)

# Sentinel yielded to the SSE layer as an SSE comment so proxies don't time the
# idle connection out and disconnects are noticed promptly.
KEEPALIVE: Dict[str, Any] = {"_keepalive": True}


class PreviewCapacityError(RuntimeError):
    """Raised when opening a preview would exceed the global device-stream cap."""


class PreviewSession:
    """One picker's live look at selected device(s) — never persisted."""

    def __init__(self, device_ids: List[str], *, registry: Any, manager: "PreviewManager"):
        self.device_ids = [d for d in dict.fromkeys(device_ids) if d]  # dedup, order
        self.registry = registry
        self._manager = manager
        self._streams: List[DeviceEventStream] = []
        self._ring: Deque[Dict[str, Any]] = deque(maxlen=int(cfg.PREVIEW_RING))
        self._queues: List[asyncio.Queue] = []          # one per live subscriber
        # Seeded at construction, not at start(): `PreviewManager.open` registers
        # the session before the route calls `start()`, and a reaper sweeping in
        # that window would see 0.0, judge it idle since the epoch, and stop a
        # session about to be used. `start()` resets both to the real start.
        self._started_at = self._last_subscriber_at = time.time()
        self._stopped = False

    # ----- lifecycle -----
    async def start(self) -> None:
        if self._streams or self._stopped:
            return
        for did in self.device_ids:
            # store=None → no persistence; event_filter=None → see everything live.
            s = DeviceEventStream(did, registry=self.registry, store=None,
                                  on_event=self._push, event_filter=None)
            self._streams.append(s)
            await s.start()
            if self._stopped:
                # The reaper stopped and released us mid-start (each device is
                # awaited in turn, so a slow or hung connect can outlast the
                # idle/duration threshold). Without this check the loop would
                # carry on opening streams onto a session no longer in
                # `_sessions` — untracked, unreapable, and holding device
                # connections for the life of the process.
                await self._stop_streams()
                return
        self._started_at = self._last_subscriber_at = time.time()

    async def _stop_streams(self) -> None:
        streams, self._streams = self._streams, []
        for s in streams:
            try:
                await s.stop()
            except Exception:  # noqa: BLE001
                pass

    async def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        try:
            await self._stop_streams()
            # wake any subscribers so their generators can exit
            for q in list(self._queues):
                try:
                    q.put_nowait(None)
                except asyncio.QueueFull:
                    pass
        finally:
            # In `finally` so a CancelledError escaping mid-stop still
            # deregisters. The `_stopped` guard means a second caller returns
            # immediately, so if the first one were cancelled before this line
            # the session would stay in `_sessions` forever, holding part of
            # MAX_PREVIEW_STREAMS — the leak this whole change removes, arriving
            # through the cancellation path.
            self._manager._release(self)

    async def _push(self, rec: Dict[str, Any]) -> None:
        self._ring.append(rec)
        for q in list(self._queues):
            try:
                q.put_nowait(rec)
            except asyncio.QueueFull:  # slow subscriber: drop oldest, keep live
                try:
                    q.get_nowait()
                    q.put_nowait(rec)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    def ring_snapshot(self) -> List[Dict[str, Any]]:
        return list(self._ring)

    # ----- subscription (drives one SSE client) -----
    async def subscribe(self) -> AsyncIterator[Dict[str, Any]]:
        """Replay the ring, then yield live events until the client disconnects
        (caller stops iterating), the session stops, or the max-duration guard
        trips. Yields :data:`KEEPALIVE` on idle so the caller can poll for
        disconnect and keep the connection warm."""
        q: asyncio.Queue = asyncio.Queue(maxsize=int(cfg.PREVIEW_RING))
        self._queues.append(q)
        self._last_subscriber_at = time.time()
        try:
            for rec in self.ring_snapshot():
                yield rec
            while not self._stopped:
                if time.time() - self._started_at > float(cfg.PREVIEW_MAX_SECONDS):
                    break
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield KEEPALIVE
                    continue
                if item is None:  # stop sentinel
                    break
                yield item
        finally:
            try:
                self._queues.remove(q)
            except ValueError:
                pass
            self._last_subscriber_at = time.time()

    # ----- observability / reaping -----
    @property
    def stream_count(self) -> int:
        return len(self.device_ids)

    @property
    def subscribers(self) -> int:
        return len(self._queues)

    def idle_expired(self) -> bool:
        return (not self._queues
                and time.time() - self._last_subscriber_at > float(cfg.PREVIEW_IDLE_TIMEOUT))

    def duration_expired(self) -> bool:
        """Past the hard cap. ``subscribe()`` checks this too, but only between
        yields — so it bounds a session whose subscriber is still iterating, which
        is the case that was never at risk. This is the check for the other one.
        """
        return time.time() - self._started_at > float(cfg.PREVIEW_MAX_SECONDS)

    def expired(self) -> bool:
        """Either abandonment condition. What the reaper asks."""
        return self.idle_expired() or self.duration_expired()

    def status(self) -> Dict[str, Any]:
        return {
            "device_ids": self.device_ids,
            "subscribers": self.subscribers,
            "connected": sum(1 for s in self._streams if s.connected),
            "buffered": len(self._ring),
            "started_at": self._started_at,
        }


class PreviewManager:
    """Tracks live preview sessions and enforces the global device-stream cap."""

    def __init__(self, *, registry: Any):
        self.registry = registry
        self._sessions: List[PreviewSession] = []
        self._reaper: Optional[asyncio.Task] = None

    def _active_streams(self) -> int:
        return sum(s.stream_count for s in self._sessions)

    async def open(self, device_ids: List[str]) -> PreviewSession:
        ids = [d for d in dict.fromkeys(device_ids) if d]
        if not ids:
            raise ValueError("no device_ids for preview")
        # Reap before measuring: an abandoned session must not be able to refuse
        # a legitimate preview for up to a whole sweep interval.
        await self.reap()
        if self._active_streams() + len(ids) > int(cfg.MAX_PREVIEW_STREAMS):
            raise PreviewCapacityError(
                f"preview cap reached ({cfg.MAX_PREVIEW_STREAMS} device streams)")
        session = PreviewSession(ids, registry=self.registry, manager=self)
        self._sessions.append(session)
        self._ensure_reaper()
        return session

    # ----- reaping (GH #172) -----
    async def reap(self) -> int:
        """Stop every abandoned session. Returns how many were stopped.

        The advertised idle teardown (``preview.py`` module docstring, the
        ``/api/events/preview`` route docstring, and ``PREVIEW_IDLE_TIMEOUT``)
        had no implementation: ``PreviewSession.idle_expired`` existed and
        nothing called it. Sessions left ``_sessions`` only via ``_release``,
        reached from ``stop()``, reached from the SSE generator's ``finally`` —
        so a subscriber generator that is never finalised (a killed browser, a
        proxy dropping the connection without closing it) held its per-device
        WebSocket streams open indefinitely and permanently consumed part of
        ``MAX_PREVIEW_STREAMS``. The abandoned-tab guard the docstrings name was
        precisely the unguarded case.

        ``stop()`` calls ``_release``, which mutates ``_sessions`` — hence the
        snapshot.
        """
        reaped = 0
        for session in list(self._sessions):
            if not session.expired():
                continue
            try:
                await session.stop()
            except Exception:  # noqa: BLE001 — one bad session must not stop the sweep
                logger.warning("preview reap: could not stop %s",
                               session.device_ids, exc_info=True)
                self._release(session)   # drop it anyway; the alternative is a
                                         # session that can never be reclaimed
            # Count releases, not calls: two sweeps can overlap (one from
            # `open()`, one from the loop) and `stop()`'s re-entry guard returns
            # immediately for the second, whose session is still mid-teardown.
            if session not in self._sessions:
                reaped += 1
        if reaped:
            logger.info("preview reap: stopped %d abandoned session(s)", reaped)
        return reaped

    def _ensure_reaper(self) -> None:
        """Start the sweep loop if it is not already running.

        Lazy and self-terminating rather than a lifespan-managed service: with
        no previews open there is nothing to sweep, and the subsystem should
        cost nothing when unused. It also cannot hang off the ingest
        supervisor's reconcile loop, which is the obvious host — that loop
        no-ops unless ``event_ingest_enabled``, while preview is deliberately
        independent of that flag (picking must work with the firehose off), so
        the reaper would be absent in exactly the common case.
        """
        if self._reaper is not None and not self._reaper.done():
            return
        coro = self._reap_loop()
        try:
            self._reaper = asyncio.create_task(coro)
        except RuntimeError:
            # No running loop. Unreachable from production — `open()` is async
            # and awaits before this — so it only guards direct construction in
            # a sync context. Close the coroutine explicitly: an un-awaited one
            # would warn, and reaping is genuinely off in that case.
            coro.close()
            self._reaper = None

    async def aclose(self) -> None:
        """Cancel the reaper and stop every live session. Called at shutdown.

        Without this the sweep task outlives the loop that owns it — harmless in
        a long-lived process, but it leaves each session's device WebSockets to
        be torn down by process exit rather than closed, and it surfaces as
        "Task was destroyed but it is pending" wherever the loop is short-lived.
        """
        task, self._reaper = self._reaper, None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        for session in list(self._sessions):
            try:
                await session.stop()
            except Exception:  # noqa: BLE001
                self._release(session)

    async def _reap_loop(self) -> None:
        try:
            while self._sessions:
                await asyncio.sleep(float(cfg.PREVIEW_REAP_INTERVAL))
                await self.reap()
        except asyncio.CancelledError:
            pass
        except Exception:  # pragma: no cover — defensive; must never kill the app
            logger.warning("preview reaper loop failed", exc_info=True)
        finally:
            self._reaper = None

    def _release(self, session: PreviewSession) -> None:
        try:
            self._sessions.remove(session)
        except ValueError:
            pass

    def status(self) -> Dict[str, Any]:
        return {
            "sessions": len(self._sessions),
            "device_streams": self._active_streams(),
            "cap": int(cfg.MAX_PREVIEW_STREAMS),
            "detail": [s.status() for s in self._sessions],
        }
