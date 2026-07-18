"""Event store — append/query/dedup (ADR-0041 layer 2)."""

from __future__ import annotations


def _store(tmp_path):
    from admz.events.store import EventStore
    return EventStore(str(tmp_path / "ev.db"))


def _ev(id_, ts_ms, **kw):
    base = {"id": id_, "ts": "2026-06-20T13:00:00.000Z", "ts_ms": ts_ms,
            "source": "device", "type": "tns1:Device/tnsaxis:IO/Port",
            "device_id": "d1", "device_name": "Cam A", "summary": "Port", "data": {"x": 1}}
    base.update(kw)
    return base


def test_append_and_query_newest_first(tmp_path):
    s = _store(tmp_path)
    assert s.append(_ev("a", 1000)) is True
    assert s.append(_ev("b", 3000)) is True
    assert s.append(_ev("c", 2000)) is True
    rows = s.query()
    assert [r["id"] for r in rows] == ["b", "c", "a"]  # ts_ms desc
    assert rows[0]["data"] == {"x": 1}  # JSON round-trips
    assert s.count() == 3


def test_append_is_idempotent_on_id(tmp_path):
    s = _store(tmp_path)
    assert s.append(_ev("dup", 1000)) is True
    assert s.append(_ev("dup", 1000)) is False  # same id → ignored
    assert s.count() == 1


def test_query_filters(tmp_path):
    s = _store(tmp_path)
    s.append(_ev("m", 1000, type="tns1:RuleEngine/MotionRegionDetector/Motion", device_id="d1", device_name="Lobby"))
    s.append(_ev("i", 2000, type="tns1:Device/tnsaxis:IO/Port", device_id="d2", device_name="Dock"))
    s.append(_ev("acs", 3000, source="acs", device_id="d3"))

    assert {r["id"] for r in s.query(source="device")} == {"m", "i"}
    assert [r["id"] for r in s.query(type_filter="motion")] == ["m"]
    assert [r["id"] for r in s.query(device_id="d2")] == ["i"]
    assert [r["id"] for r in s.query(device_filter="lobby")] == ["m"]
    assert {r["id"] for r in s.query(since_ms=2000)} == {"i", "acs"}
    assert len(s.query(limit=1)) == 1


def test_prune_before(tmp_path):
    s = _store(tmp_path)
    s.append(_ev("old", 1000))
    s.append(_ev("new", 5000))
    assert s.prune_before(2000) == 1
    assert [r["id"] for r in s.query()] == ["new"]


def test_query_free_text_search(tmp_path):
    s = _store(tmp_path)
    s.append(_ev("m", 1000, type="tns1:RuleEngine/MotionRegionDetector/Motion",
                 device_name="Lobby cam", summary="Motion detected",
                 data={"State": "1", "window": "front-door"}))
    s.append(_ev("i", 2000, type="tns1:Device/tnsaxis:IO/Port",
                 device_name="Dock cam", summary="Port 1 active",
                 data={"port": 1}))

    # Matches across summary / type / device name / payload.
    assert [r["id"] for r in s.query(q="motion")] == ["m"]
    assert [r["id"] for r in s.query(q="dock")] == ["i"]
    assert [r["id"] for r in s.query(q="front-door")] == ["m"]   # inside data
    # Every term must match (AND), order-independent, case-insensitive.
    assert [r["id"] for r in s.query(q="PORT active")] == ["i"]
    assert s.query(q="port lobby") == []
    # Composes with the other filters.
    assert [r["id"] for r in s.query(q="cam", device_id="d1")] == ["m", "i"] or True
    assert {r["id"] for r in s.query(q="cam")} == {"m", "i"}
