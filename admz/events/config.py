"""Event-ingest configuration — the enablement gate + filter defaults.

The whole subsystem is **off by default**: nothing connects to any device until
an operator flips ``event_ingest_enabled`` in fleet settings. Filters have safe
defaults and can be overridden via fleet settings without code changes.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

# Device-side subscription. "//." = every topic (proven against the fleet). We
# narrow what we *store* via STORE categories below; operators can later set a
# tighter device-side filter list once per-model subtree syntax is confirmed.
DEFAULT_TOPIC_FILTERS: List[str] = ["//."]

# Ingest-side allow-list: which normalized categories get persisted (drops the
# chattiest non-actionable "other" topics). None elsewhere would mean "store all".
DEFAULT_STORE_CATEGORIES: Set[str] = {
    "motion", "io", "ptz", "storage", "tamper", "audio", "call", "network", "light", "system",
}

# Supervisor knobs.
RECONCILE_INTERVAL_SECONDS = 60.0   # re-read the device roster to add/drop streams
MAX_STREAMS = 64                    # safety cap on concurrent device connections
RECONNECT_BASE_DELAY = 2.0          # exponential backoff base (seconds)
RECONNECT_MAX_DELAY = 120.0
WSSESSION_TIMEOUT = 10.0
WS_OPEN_TIMEOUT = 15.0


def _settings():
    from admz.fleet_settings import fleet_settings
    return fleet_settings


def event_ingest_enabled() -> bool:
    """True only when the operator has explicitly enabled the subsystem."""
    if os.getenv("ADMZ_EVENT_INGEST") == "1":
        return True
    try:
        return str(_settings().get("event_ingest_enabled") or "").lower() in ("1", "true", "yes", "on")
    except Exception:  # noqa: BLE001 — config must never break startup
        return False


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


def store_categories() -> Optional[Set[str]]:
    """Categories to persist; None means store everything."""
    try:
        raw = _settings().get("event_store_categories")
        if raw:
            val = json.loads(raw)
            if isinstance(val, list):
                return {str(x).lower() for x in val} or None
    except Exception:  # noqa: BLE001
        pass
    return set(DEFAULT_STORE_CATEGORIES)


def tag_filter() -> Optional[str]:
    """Optional tag to scope which devices we subscribe to (None = all)."""
    try:
        v = (_settings().get("event_ingest_tag") or "").strip()
        return v or None
    except Exception:  # noqa: BLE001
        return None
