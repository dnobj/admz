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
from typing import Any, AsyncIterator, Deque, Dict, List

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
        self._started_at = 0.0
        self._last_subscriber_at = 0.0
        self._stopped = False

    # ----- lifecycle -----
    async def start(self) -> None:
        if self._streams:
            return
        for did in self.device_ids:
            # store=None → no persistence; event_filter=None → see everything live.
            s = DeviceEventStream(did, registry=self.registry, store=None,
                                  on_event=self._push, event_filter=None)
            self._streams.append(s)
            await s.start()
        self._started_at = self._last_subscriber_at = time.time()

    async def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        for s in self._streams:
            try:
                await s.stop()
            except Exception:  # noqa: BLE001
                pass
        self._streams = []
        # wake any subscribers so their generators can exit
        for q in list(self._queues):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
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

    def _active_streams(self) -> int:
        return sum(s.stream_count for s in self._sessions)

    async def open(self, device_ids: List[str]) -> PreviewSession:
        ids = [d for d in dict.fromkeys(device_ids) if d]
        if not ids:
            raise ValueError("no device_ids for preview")
        if self._active_streams() + len(ids) > int(cfg.MAX_PREVIEW_STREAMS):
            raise PreviewCapacityError(
                f"preview cap reached ({cfg.MAX_PREVIEW_STREAMS} device streams)")
        session = PreviewSession(ids, registry=self.registry, manager=self)
        self._sessions.append(session)
        return session

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
