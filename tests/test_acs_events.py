"""ACS Pro event-log read + normalization (ADR-0041 layer 1)."""

from __future__ import annotations

import asyncio


def _run(coro):
    return asyncio.run(coro)


def test_normalize_event():
    from admz.modules.acs_pro.events import normalize_event

    e = normalize_event({
        "Timestamp": "2026-06-19 16:30:39.1942000",
        "EventLogType": "RecordingStarted",
        "Data": {"Name": "AXIS P3748-PLVE - Camera 2", "CameraId": "14238_x"},
    })
    assert e["ts"] == "2026-06-19 16:30:39.1942000"
    assert e["source"] == "acs"
    assert e["type"] == "RecordingStarted"
    assert e["camera_id"] == "14238_x"
    assert e["device_name"] == "AXIS P3748-PLVE - Camera 2"
    assert "RecordingStarted" in e["summary"] and "P3748" in e["summary"]


def test_normalize_handles_nested_cameraid_and_missing_data():
    from admz.modules.acs_pro.events import normalize_event

    e = normalize_event({"Timestamp": "t", "EventLogType": "Motion",
                         "Data": {"CameraId": {"Id": "cam-9"}}})
    assert e["camera_id"] == "cam-9" and e["device_name"] is None
    bare = normalize_event({"EventLogType": "Failover"})
    assert bare["type"] == "Failover" and bare["camera_id"] is None


def test_utc_anchor_format():
    from admz.modules.acs_pro.events import utc_anchor

    s = utc_anchor(24)
    # "YYYY-MM-DD HH:MM:SS"
    assert len(s) == 19 and s[4] == "-" and s[10] == " " and s[13] == ":"


def test_search_events_normalizes_and_filters(monkeypatch):
    import admz.modules.acs_pro.client as client

    payload = {"success": True, "data": {"Events": [
        {"Timestamp": "t1", "EventLogType": "RecordingStarted", "Data": {"Name": "Cam A", "CameraId": "a"}},
        {"Timestamp": "t2", "EventLogType": "Motion", "Data": {"Name": "Cam B", "CameraId": "b"}},
    ], "ContainsLastResult": True}}

    async def fake_run(catalog, executors, op_id, params):
        assert op_id == "EventLogFacade:GetEventLogList"
        assert "time" in params and "range" in params
        return payload

    monkeypatch.setattr(client, "run_acs_op", fake_run)
    from admz.modules.acs_pro.events import search_events

    out = _run(search_events(None, {}, hours_back=6, count=50))
    assert out["success"] and out["count"] == 2 and out["more"] is False
    assert out["events"][0]["type"] == "RecordingStarted"

    only_motion = _run(search_events(None, {}, type_filter="motion"))
    assert only_motion["count"] == 1 and only_motion["events"][0]["type"] == "Motion"

    only_a = _run(search_events(None, {}, device_filter="cam a"))
    assert only_a["count"] == 1 and only_a["events"][0]["device_name"] == "Cam A"


def test_search_events_more_flag_when_not_last(monkeypatch):
    import admz.modules.acs_pro.client as client

    async def fake_run(*a, **k):
        return {"success": True, "data": {"Events": [], "ContainsLastResult": False}}

    monkeypatch.setattr(client, "run_acs_op", fake_run)
    from admz.modules.acs_pro.events import search_events

    out = _run(search_events(None, {}))
    assert out["success"] and out["more"] is True


def test_search_events_passes_error_through(monkeypatch):
    import admz.modules.acs_pro.client as client

    async def fake_run(*a, **k):
        return {"success": False, "error": "AcsError", "message": "boom"}

    monkeypatch.setattr(client, "run_acs_op", fake_run)
    from admz.modules.acs_pro.events import search_events

    out = _run(search_events(None, {}))
    assert out["success"] is False and out["message"] == "boom"
