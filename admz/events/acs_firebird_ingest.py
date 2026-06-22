"""ACS Firebird firing poller (ADR-0041) — named rule firings, no rule edit.

Polls ``ACS_LOGS.FDB``'s ``LOG`` table (via a read-only copy) for new
``AlarmEntity`` rows — **named** action-rule firings — and feeds them into the
same event store + detection evaluator as device/webhook events
(``source="acs"``, ``via="firebird"``). Unlike the recorded-events poller, this
sees firings the ACS *API* can't and carries the rule name; unlike the webhook,
it needs **no per-rule modification**. The trade-off: it reads ACS's unsupported
internal DB (only alarm-raising firings are logged there).

Off by default (``acs_firebird_enabled``) and additionally requires the ACS
module connected + the Firebird driver/files present. High-water = current max
LOG id on start, so historical firings never fire a detection.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

EventCallback = Callable[[Dict[str, Any]], Awaitable[None]]

POLL_INTERVAL_SECONDS = 30.0


class AcsFirebirdPoller:
    def __init__(self, *, store: Any, on_event: Optional[EventCallback] = None):
        self.store = store
        self.on_event = on_event
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._hw_id = 0          # only fire for LOG rows newer than this
        self.last_poll_at: float = 0.0
        self.last_count = 0
        self.fired_total = 0
        self.last_error = ""

    # ----- gating -----
    @staticmethod
    def _enabled() -> bool:
        from admz.modules.acs_pro.firebird import firebird_available, firebird_enabled
        if not firebird_enabled():
            return False
        try:
            from admz.modules.acs_pro.config import acs_enabled
            if not acs_enabled():
                return False
        except Exception:  # noqa: BLE001
            return False
        ok, _ = firebird_available()
        return ok

    # ----- lifecycle -----
    async def start(self) -> None:
        if self._running:
            return
        if not self._enabled():
            logger.info("ACS Firebird poller not started (disabled or unavailable).")
            return
        try:
            from admz.modules.acs_pro.firebird import max_firing_id
            self._hw_id = await asyncio.to_thread(max_firing_id)
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)[:200]
            logger.warning("ACS Firebird poller: could not read high-water: %s", exc)
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("ACS Firebird poller started (hw=%s, interval=%ss).", self._hw_id, POLL_INTERVAL_SECONDS)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _loop(self) -> None:
        try:
            await self.poll_once()
            while self._running:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                if not self._running:
                    break
                await self.poll_once()
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("ACS Firebird poll loop crashed: %s", exc)

    async def poll_once(self) -> Dict[str, Any]:
        if not self._enabled():
            return {"enabled": False, "count": 0, "fired": 0}
        self.last_poll_at = time.time()
        from admz.modules.acs_pro.firebird import normalize_firing, read_new_firings

        # The copy+connect is blocking → run it off the event loop.
        try:
            rows = await asyncio.to_thread(read_new_firings, self._hw_id)
        except Exception as exc:  # noqa: BLE001 — a bad copy/poll must not kill the loop
            self.last_error = str(exc)[:200]
            logger.warning("ACS Firebird poll failed: %s", exc)
            return {"enabled": True, "count": 0, "fired": 0, "error": self.last_error}
        self.last_error = ""
        self.last_count = len(rows)
        fired = 0
        for row in rows:                    # already oldest-first
            rec = normalize_firing(row)
            self.store.append(rec)
            try:
                rid = int(row.get("id") or 0)
            except (TypeError, ValueError):
                rid = self._hw_id
            if rid > self._hw_id:
                self._hw_id = rid
            if self.on_event is not None:
                try:
                    await self.on_event(rec)
                    fired += 1
                except Exception:  # noqa: BLE001
                    logger.debug("ACS firebird on_event failed for %s", rec.get("id"), exc_info=True)
        self.fired_total += fired
        return {"enabled": True, "count": len(rows), "fired": fired}

    # ----- observability -----
    def status(self) -> Dict[str, Any]:
        from admz.modules.acs_pro.firebird import firebird_available, firebird_enabled
        ok, reason = firebird_available()
        return {
            "enabled": firebird_enabled(),
            "running": self._running,
            "available": ok,
            "reason": reason,
            "high_water": self._hw_id,
            "last_poll_at": self.last_poll_at,
            "last_count": self.last_count,
            "fired_total": self.fired_total,
            "last_error": self.last_error,
        }
