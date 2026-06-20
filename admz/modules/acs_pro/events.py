"""ACS Pro event-log read + normalization (ADR-0041, layer 1).

``EventLogFacade:GetEventLogList`` takes ``{range:{StartIndex,NumberOfElements},
time}`` where ``time`` is a UTC anchor ``"YYYY-MM-DD hh:mm:ss"``; events return
**newest-first** from that anchor, paged by ``range``. We normalize each
``{Timestamp, EventLogType, Data}`` into a flat record so the UI + the agent get
a uniform shape (and so layer 2 can later merge ACS + device events on one
timeline). Live shape (ACS Pro 6.16): ``RecordingStarted``/``RecordingStopped``
carry ``Data:{Name, CameraId}``.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional


def utc_anchor(hours_back: float) -> str:
    """The ``time`` anchor string ``hours_back`` hours before now (UTC)."""
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        hours=float(hours_back)
    )
    return t.strftime("%Y-%m-%d %H:%M:%S")


def normalize_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten one ACS ``EventLogEntryDto`` into the normalized shape."""
    data = raw.get("Data") or {}
    name = data.get("Name")
    etype = raw.get("EventLogType")
    cam = data.get("CameraId")
    if isinstance(cam, dict):
        cam = cam.get("Id")
    summary = etype or "event"
    if name:
        summary = f"{summary} · {name}"
    return {
        "ts": raw.get("Timestamp"),  # "YYYY-MM-DD HH:MM:SS.fffffff" UTC (sortable)
        "source": "acs",
        "type": etype,
        "camera_id": cam,
        "device_name": name,
        "summary": summary,
        "data": data,
    }


async def search_events(
    catalog: Any,
    executors: Dict[str, Any],
    *,
    hours_back: float = 24.0,
    start_index: int = 0,
    count: int = 200,
    type_filter: Optional[str] = None,
    device_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Search the ACS event log over the last ``hours_back`` hours.

    Returns ``{success, count, more, window_hours, events[]}`` or the executor's
    error envelope. ``type_filter`` / ``device_filter`` are case-insensitive
    substring matches applied client-side (the API has no field filter).
    """
    from admz.modules.acs_pro.client import run_acs_op

    req = {
        "range": {"StartIndex": int(start_index), "NumberOfElements": int(count)},
        "time": utc_anchor(hours_back),
    }
    res = await run_acs_op(catalog, executors, "EventLogFacade:GetEventLogList", req)
    if not res.get("success"):
        return res

    data = res.get("data") or {}
    events: List[Dict[str, Any]] = [normalize_event(e) for e in (data.get("Events") or [])]

    if type_filter:
        tl = type_filter.lower()
        events = [e for e in events if tl in (e["type"] or "").lower()]
    if device_filter:
        dl = device_filter.lower()
        events = [e for e in events if dl in (e["device_name"] or "").lower()]

    return {
        "success": True,
        "count": len(events),
        # ContainsLastResult=True means we reached the end of the log.
        "more": not data.get("ContainsLastResult", True),
        "window_hours": hours_back,
        "events": events,
    }
