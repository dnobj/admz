"""ACS Pro detection/analytics log (RecordedEventFacade) — ADR-0041."""

from __future__ import annotations

import asyncio


def _run(coro):
    return asyncio.run(coro)


def test_normalize_detection():
    from admz.modules.acs_pro.events import normalize_detection

    e = normalize_detection(
        {"Start": "2026-06-13T02:10:30.79Z", "End": "2026-06-13T02:10:34.65Z",
         "Id": 1551, "CameraId": {"Id": "cam-7"}, "Type": "Motion"},
        {"cam-7": "AXIS P3748 - Camera 2"},
    )
    assert e["ts"] == "2026-06-13T02:10:30.79Z"
    assert e["end"] == "2026-06-13T02:10:34.65Z"
    assert e["source"] == "acs-detection"
    assert e["type"] == "Motion"
    assert e["camera_id"] == "cam-7"
    assert e["device_name"] == "AXIS P3748 - Camera 2"
    assert "Motion" in e["summary"] and "P3748" in e["summary"]


def test_normalize_detection_bare_cameraid_and_no_name():
    from admz.modules.acs_pro.events import normalize_detection

    e = normalize_detection({"Start": "t", "CameraId": "x", "Type": "Object detection"})
    assert e["camera_id"] == "x" and e["device_name"] is None
    assert e["summary"] == "Object detection"


def test_recorded_event_types_bare_list(monkeypatch):
    import admz.modules.acs_pro.client as client

    async def fake_run(catalog, executors, op_id, params):
        assert op_id == "RecordedEventFacade:GetRecordedEventTypes"
        return {"success": True, "data": [
            {"Name": "Motion", "Title": "Motion"},
            {"Name": "Object detection", "Title": "Object detection"},
        ]}

    monkeypatch.setattr(client, "run_acs_op", fake_run)
    from admz.modules.acs_pro.events import recorded_event_types

    out = _run(recorded_event_types(None, {}))
    assert out["success"] and out["count"] == 2
    assert out["types"][0]["Name"] == "Motion"


def test_recorded_event_types_passes_error(monkeypatch):
    import admz.modules.acs_pro.client as client

    async def fake_run(*a, **k):
        return {"success": False, "error": "AcsError", "message": "boom"}

    monkeypatch.setattr(client, "run_acs_op", fake_run)
    from admz.modules.acs_pro.events import recorded_event_types

    out = _run(recorded_event_types(None, {}))
    assert out["success"] is False and out["message"] == "boom"


def test_search_detections_with_explicit_cameras(monkeypatch):
    import admz.modules.acs_pro.client as client

    async def fake_run(catalog, executors, op_id, params):
        # explicit camera_ids → no camera-list call, straight to detections.
        assert op_id == "RecordedEventFacade:GetRecordedEvents"
        assert params["cameraIds"] == [{"Id": "a"}, {"Id": "b"}]
        assert "interval" in params and "StartTime" in params["interval"]
        return {"success": True, "data": {"RecordedEvents": [
            {"Start": "t1", "CameraId": {"Id": "a"}, "Type": "Motion"},
            {"Start": "t3", "CameraId": {"Id": "b"}, "Type": "Object detection"},
            {"Start": "t2", "CameraId": {"Id": "a"}, "Type": "Motion"},
        ]}}

    monkeypatch.setattr(client, "run_acs_op", fake_run)
    from admz.modules.acs_pro.events import search_detections

    out = _run(search_detections(None, {}, hours_back=6, camera_ids=["a", "b"], count=50))
    assert out["success"] and out["count"] == 3 and out["more"] is False
    # newest-first by ts
    assert [e["ts"] for e in out["events"]] == ["t3", "t2", "t1"]

    only_obj = _run(search_detections(None, {}, camera_ids=["a", "b"], type_filter="object"))
    assert only_obj["count"] == 1 and only_obj["events"][0]["type"] == "Object detection"


def test_search_detections_resolves_camera_list(monkeypatch):
    import admz.modules.acs_pro.client as client

    calls = []

    async def fake_run(catalog, executors, op_id, params):
        calls.append(op_id)
        if op_id == "CameraListFacade:GetCameraList":
            return {"success": True, "data": {"Cameras": [
                {"CameraId": {"Id": "cam-1"}, "Name": "Lobby"},
                {"CameraId": "cam-2", "Name": "Dock"},
            ]}}
        assert op_id == "RecordedEventFacade:GetRecordedEvents"
        # camera ids resolved from the list, both forms handled
        assert {c["Id"] for c in params["cameraIds"]} == {"cam-1", "cam-2"}
        return {"success": True, "data": {"RecordedEvents": [
            {"Start": "t1", "CameraId": {"Id": "cam-1"}, "Type": "Motion"},
        ]}}

    monkeypatch.setattr(client, "run_acs_op", fake_run)
    from admz.modules.acs_pro.events import search_detections

    out = _run(search_detections(None, {}))
    assert out["success"] and out["count"] == 1
    # device_name enriched from the camera list
    assert out["events"][0]["device_name"] == "Lobby"
    assert calls == ["CameraListFacade:GetCameraList", "RecordedEventFacade:GetRecordedEvents"]


def test_search_detections_more_flag_at_cap(monkeypatch):
    import admz.modules.acs_pro.client as client

    async def fake_run(catalog, executors, op_id, params):
        return {"success": True, "data": {"RecordedEvents": [
            {"Start": "t1", "CameraId": {"Id": "a"}, "Type": "Motion"},
            {"Start": "t2", "CameraId": {"Id": "a"}, "Type": "Motion"},
        ]}}

    monkeypatch.setattr(client, "run_acs_op", fake_run)
    from admz.modules.acs_pro.events import search_detections

    out = _run(search_detections(None, {}, camera_ids=["a"], count=2))
    assert out["more"] is True  # hit the page cap


def test_search_detections_passes_camera_list_error(monkeypatch):
    import admz.modules.acs_pro.client as client

    async def fake_run(catalog, executors, op_id, params):
        return {"success": False, "error": "AcsError", "message": "no cams"}

    monkeypatch.setattr(client, "run_acs_op", fake_run)
    from admz.modules.acs_pro.events import search_detections

    out = _run(search_detections(None, {}))
    assert out["success"] is False and out["message"] == "no cams"


def test_recorded_event_tools_present_when_enabled(monkeypatch):
    import admz.modules.acs_pro.config as cfg
    monkeypatch.setattr(cfg, "acs_enabled", lambda: True)
    from admz.modules.acs_pro.tools import tool_specs

    names = {s.tool.name for s in tool_specs()}
    assert {"acs_get_recorded_events", "acs_get_recorded_event_types"} <= names
