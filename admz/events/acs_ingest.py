"""ACS Pro action-rule poller (ADR-0041 — the ACS event SOURCE seam).

ACS Pro has **no outbound/push event API** (the MQTT broker is ACS-owned, and the
Facade API exposes no subscription), so — unlike the device WebSocket streams —
we **poll** the recorded-events log for ``"Action Rule"`` firings and feed them
into the *same* :class:`EventStore` + :class:`DetectionEvaluator` as device
events, tagged ``source="acs"``. That lets an operator build "when an ACS action
rule fires → notify / record / snapshot" detections alongside device rules.

Important live finding (2026-06-21): an ACS action-rule recorded-event is
**anonymous** — it carries ``{Start, End, Id, CameraId, Type:"Action Rule"}`` but
**no rule name or definition id**. So a firing tells us *an* action rule fired, on
*which camera*, *when* — not *which named rule*. Awareness is therefore
camera-scoped, not rule-scoped (a named inventory needs the ACS Firebird DB,
which is a separate, opt-in capability).

The poller is **off by default** (``acs_event_ingest_enabled``) and additionally
requires the ACS Pro module to be connected. On start it sets a high-water mark to
"now", so historical firings seed the store/feed but never fire a detection — only
firings observed *after* enablement do.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from admz.events import config as cfg
from admz.events.store import EventStore, event_store

logger = logging.getLogger(__name__)

EventCallback = Callable[[Dict[str, Any]], Awaitable[None]]

# The recorded-event Type value ACS uses for action-rule firings (confirmed live
# via GetRecordedEventTypes: Name="Action Rule").
ACS_ACTION_RULE_TYPE = "Action Rule"
# Canonical topic/category we normalize ACS action-rule firings onto.
ACS_RULE_TOPIC = "ACS/ActionRule"
ACS_RULE_CATEGORY = "action_rule"


def _parse_ms(ts: Optional[str]) -> int:
    """Epoch ms from an ACS timestamp like ``2026-06-11T18:57:35.5861971Z``.

    ACS uses up to 7 fractional digits + a ``Z`` suffix; both trip
    ``datetime.fromisoformat`` on some versions, so normalize first.
    """
    if not ts:
        return 0
    s = ts.strip().replace("Z", "+00:00")
    if "." in s:  # clamp fractional seconds to 6 digits
        head, frac = s.split(".", 1)
        tz = ""
        for marker in ("+", "-"):
            idx = frac.find(marker)
            if idx != -1:
                frac, tz = frac[:idx], frac[idx:]
                break
        s = f"{head}.{frac[:6]}{tz}"
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return int(dt.timestamp() * 1000)
    except (ValueError, OverflowError):
        return 0


def normalize_acs_action_rule(
    detection: Dict[str, Any]
) -> Dict[str, Any]:
    """Map one ``search_detections`` "Action Rule" row onto the canonical
    EventStore record (``source="acs"``).

    ``detection`` is the already-normalized detection shape
    (``{ts, end, type, camera_id, device_name, data:{Id}}``). The result matches
    the device-event record shape so the store, the Activity feed, and the
    detection evaluator treat ACS and device events uniformly.
    """
    cam_id = detection.get("camera_id")
    cam_name = detection.get("device_name")
    start = detection.get("ts")
    end = detection.get("end")
    event_id = (detection.get("data") or {}).get("Id")
    ts_ms = _parse_ms(start)
    raw = f"{cam_id}|{ACS_RULE_TOPIC}|{start}|{event_id}"
    eid = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    summary = "Action rule fired"
    if cam_name:
        summary = f"{summary} · {cam_name}"
    return {
        "id": eid,
        "ts": start,
        "ts_ms": ts_ms,
        "source": "acs",
        "type": ACS_RULE_TOPIC,
        "device_id": cam_id,            # the ACS camera id (ADMZ-device correlation deferred)
        "device_name": cam_name,
        "summary": summary,
        "data": {
            "topic": ACS_RULE_TOPIC,
            "category": ACS_RULE_CATEGORY,
            "camera_id": cam_id,
            "camera_name": cam_name,
            "event_id": event_id,
            "start": start,
            "end": end,
            # anonymous: ACS does not expose the rule name/id on the firing
            "rule_name": None,
        },
    }


class AcsActionRulePoller:
    """Polls ACS recorded-events for action-rule firings → store + evaluator."""

    def __init__(
        self,
        *,
        catalog: Any,
        executors: Dict[str, Any],
        store: Optional[EventStore] = None,
        on_event: Optional[EventCallback] = None,
    ):
        self.catalog = catalog
        self.executors = executors
        self.store = store or event_store
        self.on_event = on_event
        self._task: Optional[asyncio.Task] = None
        self._running = False
        # high-water: only fire detections for events newer than this. Set to
        # "now" on start so historical firings seed the store but don't fire.
        self._hw_ms = 0
        self.last_poll_at: float = 0.0
        self.last_count = 0          # action-rule events seen in the last poll
        self.last_fired = 0          # detections fired in the last poll
        self.fired_total = 0
        self.last_error = ""

    # ----- lifecycle -----
    async def start(self) -> None:
        if self._running:
            return
        if not cfg.acs_event_ingest_enabled():
            logger.info("ACS action-rule poller disabled (acs_event_ingest_enabled).")
            return
        try:
            from admz.modules.acs_pro.config import acs_enabled
            if not acs_enabled():
                logger.info("ACS action-rule poller: ACS Pro not connected; not starting.")
                return
        except Exception:  # noqa: BLE001
            return
        self._hw_ms = int(time.time() * 1000)   # ignore everything before enablement
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("ACS action-rule poller started (interval=%ss).", cfg.ACS_POLL_INTERVAL_SECONDS)

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
                await asyncio.sleep(cfg.ACS_POLL_INTERVAL_SECONDS)
                if not self._running:
                    break
                await self.poll_once()
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("ACS action-rule poll loop crashed: %s", exc)

    async def poll_once(self) -> Dict[str, Any]:
        """One poll: fetch recent action-rule firings, store them, and fire the
        evaluator for any newer than the high-water mark. Returns a small summary."""
        if not cfg.acs_event_ingest_enabled():
            return {"enabled": False, "count": 0, "fired": 0}
        self.last_poll_at = time.time()
        from admz.modules.acs_pro.events import search_detections

        try:
            res = await search_detections(
                self.catalog, self.executors,
                hours_back=cfg.ACS_LOOKBACK_HOURS,
                type_filter=ACS_ACTION_RULE_TYPE,
                count=cfg.ACS_POLL_MAX_EVENTS,
            )
        except Exception as exc:  # noqa: BLE001 — a poll error must not kill the loop
            self.last_error = str(exc)[:200]
            logger.warning("ACS action-rule poll failed: %s", exc)
            return {"enabled": True, "count": 0, "fired": 0, "error": self.last_error}

        if not res.get("success"):
            self.last_error = res.get("message") or "poll failed"
            return {"enabled": True, "count": 0, "fired": 0, "error": self.last_error}
        self.last_error = ""

        events: List[Dict[str, Any]] = res.get("events") or []
        self.last_count = len(events)
        fired = 0
        max_ms = self._hw_ms
        # oldest-first so multi-event polls fire in order
        for det in sorted(events, key=lambda e: _parse_ms(e.get("ts"))):
            rec = normalize_acs_action_rule(det)
            self.store.append(rec)                       # seed feed (dedup on id)
            ts_ms = rec["ts_ms"]
            if ts_ms > self._hw_ms and self.on_event is not None:
                try:
                    await self.on_event(rec)
                    fired += 1
                except Exception:  # noqa: BLE001 — one bad rule must not stop the poll
                    logger.debug("ACS on_event failed for %s", rec.get("id"), exc_info=True)
            max_ms = max(max_ms, ts_ms)
        self._hw_ms = max_ms
        self.last_fired = fired
        self.fired_total += fired
        return {"enabled": True, "count": len(events), "fired": fired}

    # ----- observability -----
    def status(self) -> Dict[str, Any]:
        return {
            "enabled": cfg.acs_event_ingest_enabled(),
            "running": self._running,
            "last_poll_at": self.last_poll_at,
            "last_count": self.last_count,
            "last_fired": self.last_fired,
            "fired_total": self.fired_total,
            "last_error": self.last_error,
        }
