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


def normalize_detection(
    raw: Dict[str, Any], name_by_id: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Flatten one ACS ``RecordedEventDto`` into the normalized event shape.

    Recorded (analytics) events are duration events: ``{Start, End, Id,
    CameraId, Type}`` where ``Type`` is e.g. ``Motion`` / ``Object detection``.
    We map them onto the same shape as :func:`normalize_event` so the UI table
    and the agent see a uniform record; ``name_by_id`` enriches ``device_name``
    from the camera list.
    """
    name_by_id = name_by_id or {}
    cam = raw.get("CameraId")
    if isinstance(cam, dict):
        cam = cam.get("Id")
    etype = raw.get("Type")
    dev = name_by_id.get(cam)
    summary = etype or "detection"
    if dev:
        summary = f"{summary} · {dev}"
    return {
        "ts": raw.get("Start"),  # duration start (UTC, sortable)
        "end": raw.get("End"),
        "source": "acs-detection",
        "type": etype,
        "camera_id": cam,
        "device_name": dev,
        "summary": summary,
        "data": {"Id": raw.get("Id")},
    }


async def recorded_event_types(
    catalog: Any, executors: Dict[str, Any]
) -> Dict[str, Any]:
    """The catalog of recorded-event categories (Motion, Object detection, …).

    Returns ``{success, count, types[]}`` where each type carries Name/Title/
    Description/Colors, or the executor's error envelope.
    """
    from admz.modules.acs_pro.client import run_acs_op

    res = await run_acs_op(
        catalog, executors, "RecordedEventFacade:GetRecordedEventTypes", {}
    )
    if not res.get("success"):
        return res
    data = res.get("data")
    # The op returns a bare list of type dicts; tolerate a wrapped form too.
    if isinstance(data, dict):
        types = data.get("EventTypes") or data.get("RecordedEventTypes") or []
    else:
        types = data or []
    return {"success": True, "count": len(types), "types": types}


async def search_detections(
    catalog: Any,
    executors: Dict[str, Any],
    *,
    hours_back: float = 24.0,
    camera_ids: Optional[List[str]] = None,
    type_filter: Optional[str] = None,
    device_filter: Optional[str] = None,
    count: int = 2000,
) -> Dict[str, Any]:
    """Search the ACS detection/analytics log (``GetRecordedEvents``).

    When ``camera_ids`` is omitted, lists cameras first (also building an
    id→name map for ``device_name``). Returns the same ``{success, count, more,
    window_hours, events[]}`` envelope as :func:`search_events`, newest-first.
    """
    from admz.modules.acs_pro.client import run_acs_op

    name_by_id: Dict[str, Any] = {}
    if camera_ids is None:
        cams = await run_acs_op(
            catalog, executors, "CameraListFacade:GetCameraList",
            {"range": {"StartIndex": 0, "NumberOfElements": 10000}},
        )
        if not cams.get("success"):
            return cams
        camera_ids = []
        for c in (cams.get("data") or {}).get("Cameras") or []:
            cid = c.get("CameraId")
            cid = cid.get("Id") if isinstance(cid, dict) else cid
            if cid:
                camera_ids.append(cid)
                name_by_id[cid] = c.get("Name")

    req = {
        "cameraIds": [{"Id": i} for i in camera_ids],
        "interval": {"StartTime": utc_anchor(hours_back), "StopTime": utc_anchor(0)},
        "range": {"StartIndex": 0, "NumberOfElements": int(count)},
    }
    res = await run_acs_op(catalog, executors, "RecordedEventFacade:GetRecordedEvents", req)
    if not res.get("success"):
        return res

    raw = (res.get("data") or {}).get("RecordedEvents") or []
    events: List[Dict[str, Any]] = [normalize_detection(e, name_by_id) for e in raw]
    events.sort(key=lambda e: e.get("ts") or "", reverse=True)

    if type_filter:
        tl = type_filter.lower()
        events = [e for e in events if tl in (e["type"] or "").lower()]
    if device_filter:
        dl = device_filter.lower()
        events = [e for e in events if dl in (e["device_name"] or "").lower()]

    return {
        "success": True,
        "count": len(events),
        # No ContainsLastResult on this op; flag when we hit the page cap.
        "more": len(raw) >= int(count),
        "window_hours": hours_back,
        "events": events,
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
