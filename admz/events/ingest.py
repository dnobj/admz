"""Event-ingest supervisor (ADR-0041 layer 2).

Mirrors :class:`HealthMonitor`'s lifecycle (start/stop, fleet-setting gate,
``asyncio`` task) but instead of a periodic sweep it maintains **one persistent
:class:`DeviceEventStream` per subscribed device**. A reconcile loop re-reads the
tag-scoped device roster and adds/drops streams as devices come and go. The whole
thing is off until ``event_ingest_enabled`` is set, and tolerates per-device
failures (a device that 401s on ``wssession.cgi`` just keeps retrying with backoff
and never blocks the others).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from admz.events import config as cfg
from admz.events.store import EventStore, event_store
from admz.events.wsstream import DeviceEventStream, EventCallback

logger = logging.getLogger(__name__)


def _scoped_device_ids(registry: Any, tag: Optional[str]) -> List[str]:
    try:
        devices = registry.list_devices()
    except Exception as exc:  # noqa: BLE001
        logger.warning("event ingest: list_devices failed: %s", exc)
        return []
    out: List[str] = []
    for d in devices:
        did = d.get("device_id") or d.get("id")
        if not did:
            continue
        if tag and tag not in (d.get("tags") or []):
            continue
        out.append(did)
    return out


class EventIngestSupervisor:
    """Maintains the set of per-device WS event streams."""

    def __init__(
        self,
        *,
        registry: Any,
        store: Optional[EventStore] = None,
        on_event: Optional[EventCallback] = None,
    ):
        self.registry = registry
        self.store = store or event_store
        self.on_event = on_event
        self._streams: Dict[str, DeviceEventStream] = {}
        self._task: Optional[asyncio.Task] = None
        self._running = False

    # ----- lifecycle -----
    async def start(self) -> None:
        """Start the reconcile loop if enabled. No-op when disabled."""
        if self._running:
            return
        if not cfg.event_ingest_enabled():
            logger.info("Event ingest disabled (event_ingest_enabled fleet flag).")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Event ingest supervisor started.")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        await self._stop_all()

    async def _stop_all(self) -> None:
        streams = list(self._streams.values())
        self._streams.clear()
        for s in streams:
            try:
                await s.stop()
            except Exception:  # noqa: BLE001
                pass

    # ----- loop -----
    async def _loop(self) -> None:
        try:
            await self.reconcile()
            while self._running:
                await asyncio.sleep(cfg.RECONCILE_INTERVAL_SECONDS)
                if not self._running:
                    break
                await self.reconcile()
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("Event ingest loop crashed: %s", exc)

    async def reconcile(self) -> Dict[str, int]:
        """Add streams for newly-in-scope devices, drop removed ones.

        If the subsystem was disabled at runtime, tears everything down.
        Returns ``{added, removed, active}`` for observability/tests.
        """
        if not cfg.event_ingest_enabled():
            await self._stop_all()
            return {"added": 0, "removed": 0, "active": 0}

        want = _scoped_device_ids(self.registry, cfg.tag_filter())
        want = want[: cfg.MAX_STREAMS]
        want_set = set(want)
        have = set(self._streams)

        added = 0
        for did in want:
            if did not in self._streams:
                stream = DeviceEventStream(
                    did, registry=self.registry, store=self.store, on_event=self.on_event,
                )
                self._streams[did] = stream
                await stream.start()
                added += 1

        removed = 0
        for did in have - want_set:
            stream = self._streams.pop(did, None)
            if stream is not None:
                await stream.stop()
                removed += 1

        if added or removed:
            logger.info("event ingest reconcile: +%d -%d (active=%d)", added, removed, len(self._streams))
        return {"added": added, "removed": removed, "active": len(self._streams)}

    # ----- observability -----
    def status(self) -> Dict[str, Any]:
        streams = self._streams
        return {
            "enabled": cfg.event_ingest_enabled(),
            "running": self._running,
            "streams": len(streams),
            "connected": sum(1 for s in streams.values() if s.connected),
            "devices": [
                {"device_id": did, "connected": s.connected,
                 "last_event_at": s.last_event_at, "last_error": s.last_error}
                for did, s in streams.items()
            ],
        }


Reconcile = Callable[[], Awaitable[Dict[str, int]]]
