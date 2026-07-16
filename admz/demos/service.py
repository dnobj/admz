"""Demo → readiness assembly (ADR-0046).

The join layer: resolve a demo's devices, read the caches ADMZ already keeps
(drift signature + health record + event log), hand them to the pure matrix in
:mod:`admz.demos.readiness`. Every read here is cache-only — the same contract as
``snapshot/drift_status.py``, so the Demos page and the Devices page can never
disagree, and rendering a demo never costs a device round-trip.

Scope resolution mirrors the rest of ADMZ (ADR-0032): a ``tag`` is the grouping
primitive; an explicit ``device_ids`` list is the escape hatch. Tag wins when both
are set, so a tag-scoped demo picks up a newly-tagged device for free.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from admz.demos import readiness as rd
from admz.demos.store import Demo
from admz.snapshot.drift_status import drift_status_for

logger = logging.getLogger(__name__)

# How far back "has this signal fired?" looks by default. A demo is a session,
# not a history — an hour is "since we started setting up".
SIGNAL_WINDOW_SECONDS = 3600


def resolve_devices(demo: Demo, registry) -> List[Dict[str, Any]]:
    """The demo's devices, as registry dicts. Tag scope wins over the id list."""
    try:
        devices = registry.list_devices()
    except Exception as exc:  # noqa: BLE001 — readiness must render regardless
        logger.warning("demo %s: device list failed: %s", demo.id, exc)
        return []

    if demo.tag:
        return [d for d in devices if demo.tag in (d.get("tags") or [])]
    by_id = {d.get("device_id"): d for d in devices}
    # Preserve the demo's own ordering, and drop ids that no longer exist.
    return [by_id[i] for i in demo.device_ids if i in by_id]


def _drift_for(device: Dict[str, Any]) -> Dict[str, Any]:
    from admz.snapshot.drift_alerts import drift_alerts as _drift_store

    try:
        sig = _drift_store.get_last_signature(device.get("device_id", ""))
    except Exception:  # noqa: BLE001
        sig = None
    return drift_status_for(device, sig)


def _health_map(device_ids: List[str]) -> Dict[str, str]:
    from admz.fleet.health import device_health_store

    try:
        return {
            r.device_id: r.status.value
            for r in device_health_store.list_all()
            if r.device_id in set(device_ids)
        }
    except Exception:  # noqa: BLE001
        return {}


def signal_activity(
    demo: Demo,
    rows: List[Dict[str, Any]],
    event_store,
    window_seconds: int = SIGNAL_WINDOW_SECONDS,
) -> List[Dict[str, Any]]:
    """Per-signal "last seen", from the event log.

    Phase 1 only: each expected signal is matched **in isolation** (the same
    limit detections have — ``events/evaluator.py``). The ordered sequence +
    window that would prove the demo actually *ran* is ADR-0041 Layer 4 proper,
    deferred. A signal targets a ``device_id`` or a ``role`` (which fans out to
    every device holding that role).
    """
    since_ms = int((time.time() - window_seconds) * 1000)
    out: List[Dict[str, Any]] = []
    for sig in demo.signals or []:
        device_ids = []
        if sig.get("device_id"):
            device_ids = [sig["device_id"]]
        elif sig.get("role"):
            device_ids = [r["device_id"] for r in rows if r["role"] == sig["role"]]

        count, last_ms = 0, None
        type_filter = sig.get("topic") or sig.get("category") or None
        for did in device_ids or [None]:
            try:
                got = event_store.activity_since(
                    since_ms=since_ms, device_id=did, type_filter=type_filter)
            except Exception:  # noqa: BLE001
                continue
            count += got["count"]
            if got["last_ms"] and (last_ms is None or got["last_ms"] > last_ms):
                last_ms = got["last_ms"]

        out.append({
            "label": sig.get("label") or type_filter or "any event",
            "role": sig.get("role") or "",
            "device_id": sig.get("device_id") or "",
            "type_filter": type_filter or "",
            "count": count,
            "last_ms": last_ms,
            "seen": count > 0,
        })
    return out


def demo_view(
    demo: Demo,
    registry,
    event_store=None,
    window_seconds: int = SIGNAL_WINDOW_SECONDS,
) -> Dict[str, Any]:
    """A demo + its computed readiness, ready to render or return as JSON."""
    devices = resolve_devices(demo, registry)
    health = _health_map([d.get("device_id", "") for d in devices])

    rows: List[Dict[str, Any]] = []
    for d in devices:
        did = d.get("device_id", "")
        row = rd.device_readiness(
            demo.config_source, did, (demo.roles or {}).get(did, ""),
            _drift_for(d), health.get(did))
        # Display-only extras the matrix has no business knowing about.
        row["name"] = d.get("nickname") or did
        row["model"] = d.get("model") or ""
        rows.append(row)

    out = demo.to_dict()
    out["readiness"] = rd.demo_readiness(demo.config_source, rows)
    out["scenario_name"] = rd.scenario_of(demo.config_source)
    out["signal_status"] = (
        signal_activity(demo, rows, event_store, window_seconds)
        if event_store is not None else []
    )
    return out


def demo_views(demos: List[Demo], registry, event_store=None) -> List[Dict[str, Any]]:
    return [demo_view(d, registry, event_store) for d in demos]


def holders_of(device_id: str, demos: List[Demo], registry) -> List[Demo]:
    """Which sidelined demos claim the scenario currently loaded on a device.

    The "on loan" banner's other half: the device tells us *which scenario* holds
    it (``active_scenario``), and this names the demo(s) that scenario belongs to
    — so the operator gets "the Loitering demo has it", not "scenario loiter-v2".
    """
    try:
        info = registry.get_device_info(device_id) or {}
    except Exception:  # noqa: BLE001
        return []
    active = info.get("active_scenario")
    if not active:
        return []
    return [d for d in demos if rd.scenario_of(d.config_source) == active]


def find_demo(demo_id: str, store) -> Optional[Demo]:
    return store.get(demo_id)
