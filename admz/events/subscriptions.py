"""Watch-scoped ingest subscriptions (ADR-0041 amendment).

Steady-state ingest is driven by **what is watched**, not by the whole fleet.
The :class:`WatchGate` answers two questions for the ingest supervisor:

  * :meth:`device_ids` — which devices should hold a live WS stream at all
    (only those a watched event or an **enabled** detection targets, expanding
    tag-scoped specs across the roster). No watch ⇒ no stream.
  * :meth:`matches` — should a live event be **persisted** (does it match any
    watched-event / detection spec)? Everything else is received-then-dropped.

This replaces the previous firehose — one stream per fleet device subscribed to
``//.`` and every event written to SQLite — which did not scale (it grew the
event store to millions of rows and wedged the activity query). The device set
is now typically a handful of devices and the store holds only watched hits.

Both answers are recomputed only when the watched-event or detection store
version changes (cheap steady-state).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from admz.events.matching import record_matches

logger = logging.getLogger(__name__)


class WatchGate:
    def __init__(self, *, registry: Any, watched_store: Any = None, detection_store: Any = None):
        self.registry = registry
        if watched_store is None:
            from admz.events.watched import watched_event_store as watched_store
        if detection_store is None:
            from admz.events.detections import detection_store as detection_store
        self.watched_store = watched_store
        self.detection_store = detection_store
        self._specs: List[Dict[str, Any]] = []   # {source, device_id, tag, match}
        self._w_version: Any = object()          # force first refresh
        self._d_version: Any = object()
        self._tags_cache: Dict[str, list] = {}
        self._refresh_failing = False            # log-once-per-failure-streak latch

    # ----- spec cache -----
    def version(self) -> tuple:
        return (getattr(self.watched_store, "version", 0),
                getattr(self.detection_store, "version", 0))

    def _refresh(self) -> None:
        wv = getattr(self.watched_store, "version", 0)
        dv = getattr(self.detection_store, "version", 0)
        if wv == self._w_version and dv == self._d_version:
            return
        # BOTH reads must succeed before the cursor moves (GH #209). Advancing it
        # after a swallowed failure is permanent, not transient: the early return
        # above then sees cursor == store version and never retries, so the gate
        # keeps a partial spec list for the life of the process — silently
        # dropping every event those specs would have captured. Build into a
        # local and publish atomically, so a partial read publishes nothing and
        # moves neither cursor (a half-advanced pair is worse than a fully stale
        # one: the next refresh would skip the half that just succeeded).
        specs: List[Dict[str, Any]] = []
        try:
            for w in self.watched_store.list():
                specs.append({"source": w.source, "device_id": w.device_id,
                              "tag": w.tag, "match": w.match})
            for d in self.detection_store.list(enabled_only=True):
                specs.append({"source": d.source, "device_id": d.device_id,
                              "tag": d.tag, "match": d.match})
        except Exception:  # noqa: BLE001 — a store hiccup must not wedge ingest
            # The swallow is load-bearing: matches() is the stream's event_filter
            # and wsstream._handle calls it UNGUARDED, so a raise here would break
            # the read loop. Keep the previous specs, leave the cursor alone, and
            # let the next call retry. Warn once per failure streak — _refresh runs
            # per event on the matches() path, so an unconditional warning would
            # turn a store outage into a log flood.
            if not self._refresh_failing:
                self._refresh_failing = True
                logger.warning("WatchGate refresh failed; keeping previous specs and "
                               "retrying on the next call", exc_info=True)
            else:
                logger.debug("WatchGate refresh still failing", exc_info=True)
            return
        if self._refresh_failing:
            self._refresh_failing = False
            logger.warning("WatchGate refresh recovered (%d spec(s)).", len(specs))
        self._specs = specs
        self._w_version, self._d_version = wv, dv
        self._tags_cache.clear()

    def _device_tags(self, device_id: Optional[str]) -> list:
        if device_id is None:
            return []
        if device_id in self._tags_cache:
            return self._tags_cache[device_id]
        try:
            info = self.registry.get_device_info(device_id) or {}
            tags = info.get("tags") or []
        except Exception:  # noqa: BLE001
            tags = []
        self._tags_cache[device_id] = tags
        return tags

    # ----- device set -----
    def device_ids(self) -> List[str]:
        """Registry device_ids targeted by any device-source watched-event or
        enabled detection (explicit device_id, or every roster device carrying a
        tag-scoped spec's tag). Roster order preserved; only extant devices."""
        self._refresh()
        try:
            roster = self.registry.list_devices()
        except Exception:  # noqa: BLE001
            logger.warning("WatchGate: list_devices failed", exc_info=True)
            return []
        rid_order: List[str] = []
        rid_tags: Dict[str, list] = {}
        for d in roster:
            did = d.get("device_id") or d.get("id")
            if not did:
                continue
            rid_order.append(did)
            rid_tags[did] = d.get("tags") or []

        wanted: Set[str] = set()
        for s in self._specs:
            if s.get("source") != "device":
                continue
            if s.get("device_id"):
                wanted.add(s["device_id"])
            elif s.get("tag"):
                for did in rid_order:
                    if s["tag"] in (rid_tags.get(did) or []):
                        wanted.add(did)
        return [d for d in rid_order if d in wanted]

    # ----- persistence gate -----
    def matches(self, rec: Dict[str, Any]) -> bool:
        """True if ``rec`` matches any watched-event / detection spec (⇒ persist)."""
        self._refresh()
        if not self._specs:
            return False
        tags = self._device_tags(rec.get("device_id"))
        for s in self._specs:
            if record_matches(rec, source=s.get("source", "device"),
                              device_id=s.get("device_id"), tag=s.get("tag"),
                              match=s.get("match"), device_tags=tags):
                return True
        return False
