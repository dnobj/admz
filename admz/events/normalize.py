"""Normalize VAPIX WebSocket events to the canonical ADMZ event shape.

A ``ws-data-stream`` ``events:notify`` payload looks like::

    {"method": "events:notify",
     "params": {"notification": {
         "topic": "tns1:Device/tnsaxis:IO/Port",
         "message": {"source": {"port": "1"}, "key": {}, "data": {"state": "0"}},
         "timestamp": 1781150388807}}}

We flatten the ``notification`` into the same record shape used by the ACS event
normalizers (:func:`admz.modules.acs_pro.events.normalize_event`) so the store,
the activity feed, and the agent see one uniform schema across sources.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any, Dict, Optional


def topic_leaf(topic: str) -> str:
    """The last meaningful segment of an ONVIF topic, namespace-stripped."""
    if not topic:
        return "event"
    seg = topic.rstrip("/").split("/")[-1] or topic
    # drop a namespace prefix like "tnsaxis:" on the leaf
    return seg.split(":")[-1]


def category_for_topic(topic: str) -> str:
    """Coarse category for filtering/grouping the activity feed."""
    t = topic or ""
    if any(k in t for k in ("Motion", "VMD", "MotionAlarm", "ObjectAnalytics")):
        return "motion"
    if "PTZController" in t:
        return "ptz"
    if any(k in t for k in ("IO/", "Trigger/Relay", "DigitalInput", "OutputPort")):
        return "io"
    if "Storage" in t or "StorageFailure" in t:
        return "storage"
    if "AudioSource" in t:
        return "audio"
    if "Casing" in t:
        return "tamper"
    if "Network" in t:
        return "network"
    if "Light" in t:
        return "light"
    if "Call" in t or "Intercom" in t:
        return "call"
    if any(k in t for k in ("SystemReady", "Temperature", "HardwareFailure", "Status")):
        return "system"
    return "other"


def _ts_from_ms(ts_ms: int) -> str:
    """ISO-8601 UTC string (sortable) from epoch milliseconds."""
    try:
        dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=datetime.timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"
    except (ValueError, OverflowError, OSError):
        return ""


def _summary(leaf: str, data: Dict[str, Any]) -> str:
    if isinstance(data, dict) and data:
        kv = " ".join(f"{k}={v}" for k, v in list(data.items())[:3])
        return f"{leaf} · {kv}"
    return leaf


def event_id(device_id: str, topic: str, ts_ms: int, message: Dict[str, Any]) -> str:
    """Stable content hash for dedup across reconnects."""
    raw = json.dumps([device_id, topic, ts_ms, message], sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def normalize_vapix_event(
    notify: Dict[str, Any],
    *,
    device_id: str,
    device_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Flatten one ``events:notify`` notification into the canonical record.

    Returns None if the payload isn't a recognizable notification.
    """
    note = notify
    if isinstance(notify.get("params"), dict):  # accept the full RPC frame too
        note = notify["params"].get("notification") or notify["params"]
    topic = note.get("topic")
    if not topic:
        return None
    message = note.get("message") or {}
    data = message.get("data") if isinstance(message, dict) else {}
    if not isinstance(data, dict):
        data = {"value": data}
    try:
        ts_ms = int(note.get("timestamp") or 0)
    except (TypeError, ValueError):
        ts_ms = 0
    leaf = topic_leaf(topic)
    category = category_for_topic(topic)
    return {
        "id": event_id(device_id, topic, ts_ms, message if isinstance(message, dict) else {}),
        "ts": _ts_from_ms(ts_ms),
        "ts_ms": ts_ms,
        "source": "device",
        "type": topic,
        "device_id": device_id,
        "device_name": device_name,
        "summary": _summary(leaf, data),
        "data": {
            "topic": topic,
            "category": category,
            "leaf": leaf,
            "source": message.get("source") if isinstance(message, dict) else None,
            "key": message.get("key") if isinstance(message, dict) else None,
            "data": data,
        },
    }
