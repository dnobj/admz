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
requires the ACS Pro module to be connected. **The first successful poll after
start seeds the store/feed and fires nothing**, so historical firings become
visible without triggering a detection — only firings observed *after* enablement
fire. Every poll after that fires for each firing the event store had never seen
(ADR-0057: identity, not a clock — see :meth:`AcsActionRulePoller.poll_once`).
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
    detection: Dict[str, Any], *, now_ms: Optional[int] = None
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
    ts_parsed = ts_ms > 0
    if not ts_parsed:
        # ADR-0057: a parse failure must not leave ts_ms at 0. Such a row sorts
        # last under ``ORDER BY ts_ms DESC`` and the first retention sweep reaps
        # it (``DELETE FROM events WHERE ts_ms < cutoff``), so the firing would
        # vanish from the feed entirely. Fall back to poll time and flag it.
        # Safe because the id below hashes the RAW ``start`` string, never
        # ``ts_ms`` — dedup stays stable across polls even if ts never parses.
        ts_ms = int(now_ms if now_ms is not None else time.time() * 1000)
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
            # False ⇒ ``ts_ms`` above is a poll-time fallback, not ACS's time.
            "ts_parsed": ts_parsed,
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
        # ADR-0057: firing is gated on store identity, not on a clock. `_seeded`
        # is the whole of the startup contract — the first SUCCESSFUL poll after
        # start() appends everything and fires nothing, so pre-enablement history
        # seeds the feed without triggering detections. Without it, identity
        # firing alone would fire the entire lookback window on first enablement,
        # including pre-authorized service-affecting actions.
        self._seeded = False
        self.last_poll_at: float = 0.0
        self.last_count = 0          # action-rule events seen in the last poll
        self.last_fired = 0          # detections fired in the last poll
        self.fired_total = 0
        # ADR-0058: on the current wiring this is structurally pinned at zero —
        # DetectionEvaluator.evaluate no longer has a raise path. A non-zero
        # reading therefore means an INJECTED on_event is failing, and those
        # firings are not retried (the row is appended before the callback runs).
        self.fire_failed_total = 0
        self.last_error = ""
        # Observability (ADR-0057). Skew between the ADMZ host clock and the ACS
        # server clock is unmeasurable directly — ACS exposes no server-time op —
        # so it is inferred from the newest event ACS reported and surfaced
        # rather than corrected.
        self.newest_event_ts_ms = 0  # newest SUCCESSFULLY PARSED ACS timestamp
        self.last_truncated = False
        self.truncated_polls = 0
        self.unparsed_ts = 0
        self.store_error_polls = 0
        self._warned_truncated = False   # log-once-per-streak latches (cf. #249)
        self._warned_unparsed = False
        self._warned_fire_failed = False

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
        # No clock read: the next successful poll seeds and fires nothing, which
        # is what "ignore everything before enablement" now means (ADR-0057).
        self._seeded = False
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
        evaluator for every firing **the store had never seen**. Returns a summary.

        ADR-0057: firing is gated on identity, never on a timestamp. ``append`` is
        ``INSERT OR IGNORE`` on a content-hash id and returns True only for a
        genuinely new row, so no clock is consulted anywhere on this path — which
        matters because the mark this replaced was seeded from the ADMZ host clock
        and compared against ACS server timestamps.

        A consequence worth knowing: because every poll re-fetches the whole
        ``ACS_LOOKBACK_HOURS`` window, a firing whose *append* failed is retried on
        the next poll for up to that window. So a swallowed store error must NOT be
        disambiguated with an in-process seen-set — that would defeat the retry and
        reintroduce the defect class #209 fixed. It is counted instead.
        """
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

        # Truncation (ADR-0057 D2). Paging is newest-first from StartIndex 0 and
        # the window slides forward every poll, so a row pushed off a truncated
        # page is never returned again — lost from the feed AND the fire path.
        # Real paging is deferred; surface it so the condition is diagnosable
        # instead of invisible, and name the two levers that already exist.
        self.last_truncated = bool(res.get("more"))
        if self.last_truncated:
            self.truncated_polls += 1
            if not self._warned_truncated:
                self._warned_truncated = True
                logger.warning(
                    "ACS action-rule poll hit the %d-event page cap: older firings in "
                    "the %sh window were not returned and cannot be recovered. Raise "
                    "ACS_POLL_MAX_EVENTS or lower ACS_LOOKBACK_HOURS.",
                    cfg.ACS_POLL_MAX_EVENTS, cfg.ACS_LOOKBACK_HOURS)
        elif self._warned_truncated:
            self._warned_truncated = False
            logger.warning("ACS action-rule poll is no longer truncated.")

        events: List[Dict[str, Any]] = res.get("events") or []
        self.last_count = len(events)
        now_ms = int(self.last_poll_at * 1000)
        errors_before = getattr(self.store, "append_errors", 0)
        fired = 0
        # oldest-first so a multi-event poll fires in chronological order. This
        # orders events WITHIN one poll; it is not a correctness gate.
        for det in sorted(events, key=lambda e: _parse_ms(e.get("ts"))):
            rec = normalize_acs_action_rule(det, now_ms=now_ms)
            if rec["data"].get("ts_parsed"):
                self.newest_event_ts_ms = max(self.newest_event_ts_ms, rec["ts_ms"])
            else:
                # Fire it anyway: the ACS query interval already bounds what came
                # back, so an unparseable timestamp is a FORMAT problem, not an
                # age one — and the realistic failure is wholesale (an ACS version
                # changing its format), where failing closed would silently
                # disable all ACS automation. Loud, not silent.
                self.unparsed_ts += 1
                if not self._warned_unparsed:
                    self._warned_unparsed = True
                    logger.warning(
                        "ACS firing has an unparseable timestamp %r; firing it anyway "
                        "with a poll-time fallback and data.ts_parsed=False (ADR-0057).",
                        str(det.get("ts"))[:64])
            inserted = self.store.append(rec)
            # THE gate: new to the store, and past the seeding poll.
            if inserted and self._seeded and self.on_event is not None:
                try:
                    await self.on_event(rec)
                    fired += 1
                    self._warned_fire_failed = False
                except Exception:  # noqa: BLE001 — one bad rule must not stop the poll
                    # NOTE: the row is already appended, so `inserted` is False on
                    # every later poll and this firing will NOT be retried. The
                    # window's retry buffer covers a failed *append*, not a failed
                    # *fire*. ADR-0058 removes the wired evaluator's only raise
                    # path, so this is now reachable only via an injected on_event
                    # — which is exactly what `fire_failed_total` reports.
                    self.fire_failed_total += 1
                    if not self._warned_fire_failed:
                        self._warned_fire_failed = True
                        logger.warning("ACS on_event failed for %s; this firing will not "
                                       "be retried", rec.get("id"), exc_info=True)
                    else:
                        logger.debug("ACS on_event failed for %s", rec.get("id"), exc_info=True)
        if getattr(self.store, "append_errors", 0) > errors_before:
            # Appends were lost to a DB error, so those firings did not fire. They
            # retry on the next poll while they remain inside the lookback window;
            # an outage longer than that window loses them, which is the one
            # genuine loss path left and must not be silent.
            self.store_error_polls += 1
        self._seeded = True          # any successful poll ends the seeding window
        self.last_fired = fired
        self.fired_total += fired
        return {"enabled": True, "count": len(events), "fired": fired}

    # ----- observability -----
    def status(self) -> Dict[str, Any]:
        # `apparent_skew_ms` is local-now minus the newest ACS timestamp SEEN, so
        # it reads "since the last event", not "current clock offset" — on a quiet
        # install it grows without meaning anything. It exists because the query
        # interval is still built from the local clock (`utc_anchor`), so skew
        # shrinks the effective window even though it no longer gates firing: ACS
        # behind by more than the lookback returns nothing at all, forever, which
        # otherwise looks exactly like "ACS is quiet" (ADR-0057).
        skew = (int(time.time() * 1000) - self.newest_event_ts_ms
                if self.newest_event_ts_ms else None)
        return {
            "enabled": cfg.acs_event_ingest_enabled(),
            "running": self._running,
            "seeded": self._seeded,
            "last_poll_at": self.last_poll_at,
            "last_count": self.last_count,
            "last_fired": self.last_fired,
            "fired_total": self.fired_total,
            "fire_failed_total": self.fire_failed_total,
            "last_error": self.last_error,
            "newest_event_ts_ms": self.newest_event_ts_ms,
            "apparent_skew_ms": skew,
            "last_truncated": self.last_truncated,
            "truncated_polls": self.truncated_polls,
            "unparsed_ts": self.unparsed_ts,
            "store_error_polls": self.store_error_polls,
        }
