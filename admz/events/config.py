"""Event-ingest configuration — the enablement gate + filter defaults.

The whole subsystem is **off by default**: nothing connects to any device until
an operator flips ``event_ingest_enabled`` in fleet settings. Filters have safe
defaults and can be overridden via fleet settings without code changes.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Device-side subscription. "//." = every topic (proven against the fleet). What
# we *store* is decided by the watch gate, not here (ADR-0048); operators can
# later set a tighter device-side filter list once per-model subtree syntax is
# confirmed.
DEFAULT_TOPIC_FILTERS: List[str] = ["//."]

# There is deliberately no category allow-list. ADR-0048 replaced it, for the
# device-WebSocket path, with the watch gate: a device event is persisted only
# if it matches a watched-event or detection spec (`WatchGate.matches`, applied
# at `wsstream.py`), which is strictly narrower than any category filter and,
# unlike one, cannot discard something an operator explicitly asked to watch.
#
# It is NOT a fleet-wide persistence gate: the three ACS writers
# (`events/acs_ingest.py`, `events/acs_firebird_ingest.py`,
# `modules/acs_pro/routes.py`) append their firings unconditionally. Reviving a
# category allow-list would not fix that either — those normalize to
# `action_rule`, which the old default set also excluded, so it would silently
# drop every ACS firing. Source-aware gating is the actual fix; see GH #371.

# Settings this module used to honour and no longer does. Their rows are swept
# at startup by `purge_retired_settings()` — see GH #172.
_RETIRED_SETTING_KEYS = ("event_store_categories",)

# Supervisor knobs.
RECONCILE_INTERVAL_SECONDS = 60.0   # re-read watched scope to add/drop streams
MAX_STREAMS = 64                    # safety cap on concurrent device connections
RECONNECT_BASE_DELAY = 2.0          # exponential backoff base (seconds)
RECONNECT_MAX_DELAY = 120.0
WSSESSION_TIMEOUT = 10.0
WS_OPEN_TIMEOUT = 15.0

# Retention (safety net). The store now holds only watched hits, but a chatty
# watched topic over a long-lived deployment should still never grow unbounded.
EVENTS_MAX_ROWS = 50000             # keep only the newest N stored events
EVENTS_RETENTION_DAYS = 30          # drop stored events older than this

# Transient preview feed (the "pick a new watched event" picker). Streams the
# SELECTED device(s) live to the browser WITHOUT persisting — never the store.
MAX_PREVIEW_STREAMS = 8             # bound concurrent device connections previews open
PREVIEW_MAX_SECONDS = 600.0         # a picker SSE auto-closes after this (abandoned-tab guard)
PREVIEW_RING = 200                  # events buffered per preview (replay to the picker)
PREVIEW_IDLE_TIMEOUT = 120.0        # close a preview this long after its last subscriber leaves
PREVIEW_REAP_INTERVAL = 30.0        # how often PreviewManager sweeps for abandoned sessions

# ACS Pro action-rule poller (ADR-0041 — ACS has NO push API, so we POLL the
# recorded-events log for "Action Rule" firings). Separate flag from the device
# WS ingest; both off by default.
ACS_POLL_INTERVAL_SECONDS = 30.0
ACS_LOOKBACK_HOURS = 0.5            # window fetched each poll (generous vs the interval)
ACS_POLL_MAX_EVENTS = 2000


def acs_event_ingest_enabled() -> bool:
    """True only when the operator enabled the ACS action-rule poller. Also
    requires the ACS Pro module to be connected (checked by the poller).

    Delegates to the advanced-capability registry (GH #132): same env var
    (``ADMZ_ACS_EVENT_INGEST``), same setting (``acs_event_ingest_enabled``),
    same env-beats-setting precedence, and the same never-raise contract — the
    registry swallows a settings-store failure and answers from env alone.
    """
    from admz import capabilities

    return capabilities.is_active("events.acs_poll")


def _settings():
    from admz.fleet_settings import fleet_settings
    return fleet_settings


def event_ingest_enabled() -> bool:
    """True only when the operator has explicitly enabled the subsystem.

    Delegates to the advanced-capability registry (GH #132) — see
    :func:`acs_event_ingest_enabled`. Name, signature, env var and setting key
    are unchanged, so the ~10 callers of this predicate are untouched.
    """
    from admz import capabilities

    return capabilities.is_active("events.device_ingest")


def topic_filters() -> List[str]:
    """The ``events:configure`` topicFilter list (fleet-overridable)."""
    try:
        raw = _settings().get("event_topic_filters")
        if raw:
            val = json.loads(raw)
            if isinstance(val, list) and val:
                return [str(x) for x in val]
    except Exception:  # noqa: BLE001
        pass
    return list(DEFAULT_TOPIC_FILTERS)


def tag_filter() -> Optional[str]:
    """Optional tag to further narrow the watched device set (None = no extra narrowing)."""
    try:
        v = (_settings().get("event_ingest_tag") or "").strip()
        return v or None
    except Exception:  # noqa: BLE001
        return None


def _int_setting(key: str, default: int) -> int:
    try:
        v = _settings().get(key)
        return int(v) if v not in (None, "") else default
    except Exception:  # noqa: BLE001
        return default


def events_max_rows() -> int:
    """Max stored events to retain (fleet-overridable via ``event_store_max_rows``)."""
    return _int_setting("event_store_max_rows", EVENTS_MAX_ROWS)


def events_retention_days() -> int:
    """Days of stored events to keep (fleet-overridable via ``event_store_retention_days``)."""
    return _int_setting("event_store_retention_days", EVENTS_RETENTION_DAYS)


def purge_retired_settings() -> int:
    """Delete fleet-setting rows for event knobs that no longer exist. Returns
    how many were removed.

    `event_store_categories` was superseded by the watch gate in ADR-0048 and
    removed in GH #172. Removing the code does not remove the row: every
    settings surface enumerates `list_all()`, so an install that once set it
    would keep showing an apparently live control that does nothing — which is
    the same trap the removal is meant to close, one layer down.

    Idempotent (nothing to delete on later starts) and never raises: a startup
    cleanup must not be able to stop the process coming up.
    """
    removed = 0
    for key in _RETIRED_SETTING_KEYS:
        try:
            if _settings().delete(key):
                removed += 1
                logger.info("removed the retired fleet setting %r (#172)", key)
        except Exception:  # noqa: BLE001 — never fatal to startup
            logger.warning("could not remove the retired fleet setting %r; "
                           "will retry next start", key, exc_info=True)
    return removed
