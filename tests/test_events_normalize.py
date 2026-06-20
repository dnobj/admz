"""VAPIX event normalization (ADR-0041 layer 2)."""

from __future__ import annotations

from admz.events.normalize import (
    normalize_vapix_event, category_for_topic, topic_leaf, event_id,
)

IO = {"topic": "tns1:Device/tnsaxis:IO/Port",
      "message": {"source": {"port": "1"}, "key": {}, "data": {"state": "0"}},
      "timestamp": 1781150388807}
MOTION = {"topic": "tns1:RuleEngine/MotionRegionDetector/Motion",
          "message": {"source": {"RuleName": "ACS Profile 1"}, "key": {}, "data": {"State": "1"}},
          "timestamp": 1781966492434}
PTZ = {"topic": "tns1:PTZController/tnsaxis:Move/Channel_1",
       "message": {"source": {"PTZConfigurationToken": "1"}, "key": {}, "data": {"is_moving": "1"}},
       "timestamp": 1781966492500}


def test_category_mapping():
    assert category_for_topic(IO["topic"]) == "io"
    assert category_for_topic(MOTION["topic"]) == "motion"
    assert category_for_topic(PTZ["topic"]) == "ptz"
    assert category_for_topic("tns1:Device/tnsaxis:IO/OutputPort") == "io"
    assert category_for_topic("tns1:VideoSource/MotionAlarm") == "motion"
    assert category_for_topic("tnsaxis:Storage/Alert") == "storage"
    assert category_for_topic("tns1:Device/tnsaxis:Casing/Open") == "tamper"
    assert category_for_topic("tns1:Whatever/Unknown") == "other"


def test_topic_leaf():
    assert topic_leaf(IO["topic"]) == "Port"
    assert topic_leaf(PTZ["topic"]) == "Move/Channel_1".split("/")[-1] or "Channel_1"
    assert topic_leaf("") == "event"


def test_normalize_io_event():
    e = normalize_vapix_event(IO, device_id="d1", device_name="I8016")
    assert e["source"] == "device"
    assert e["type"] == "tns1:Device/tnsaxis:IO/Port"
    assert e["device_id"] == "d1" and e["device_name"] == "I8016"
    assert e["ts_ms"] == 1781150388807
    assert e["ts"].startswith("2026-") and e["ts"].endswith("Z")
    assert e["data"]["category"] == "io"
    assert e["data"]["source"] == {"port": "1"}
    assert e["data"]["data"] == {"state": "0"}
    assert "Port" in e["summary"] and "state=0" in e["summary"]
    assert len(e["id"]) == 40  # sha1 hex


def test_normalize_accepts_full_rpc_frame():
    frame = {"method": "events:notify", "params": {"notification": MOTION}}
    e = normalize_vapix_event(frame, device_id="d2")
    assert e["type"] == MOTION["topic"] and e["data"]["category"] == "motion"
    assert e["data"]["data"] == {"State": "1"}


def test_event_id_stable_and_distinct():
    a = normalize_vapix_event(IO, device_id="d1")
    b = normalize_vapix_event(IO, device_id="d1")
    c = normalize_vapix_event(IO, device_id="d2")
    assert a["id"] == b["id"]            # same input → same id (dedup)
    assert a["id"] != c["id"]            # different device → different id
    assert event_id("d", "t", 1, {}) == event_id("d", "t", 1, {})


def test_normalize_missing_topic_returns_none():
    assert normalize_vapix_event({"message": {}}, device_id="d") is None
    assert normalize_vapix_event({"topic": "", "timestamp": 0}, device_id="d") is None
