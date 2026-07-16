"""Demos phase 1 — the readiness "green light" (ADR-0046).

The readiness matrix IS the feature, so every (config_source × drift state) cell
is pinned. Drift inputs are built with the REAL producer (``drift_status_for``)
rather than hand-made dicts, so these tests break if the two ever disagree.
"""

from __future__ import annotations

import pytest

from admz.demos import readiness as rd
from admz.demos.store import Demo, DemoStore
from admz.events.store import EventStore
from admz.snapshot.drift_status import drift_status_for


def _drift(state: str, *, scenario: str = None, count: int = 0):
    """A real drift_status_for result in the requested state."""
    if state == "in_scenario":
        return drift_status_for(
            {"baseline_sha": "b", "active_scenario": scenario},
            {"field_count": 0, "updated_at": 1.0})
    if state == "none":
        return drift_status_for({}, None)
    if state == "unchecked":
        return drift_status_for({"baseline_sha": "b"}, None)
    if state == "in_sync":
        return drift_status_for({"baseline_sha": "b"},
                                {"field_count": 0, "updated_at": 1.0})
    if state == "drifted":
        return drift_status_for({"baseline_sha": "b"},
                                {"field_count": count, "updated_at": 1.0})
    raise AssertionError(f"unknown state {state}")


# ---------------------------------------------------------------------------
# The matrix — baseline demos (the norm: the baseline IS the demo config)
# ---------------------------------------------------------------------------


class TestBaselineDemoConfigVerdict:
    def test_in_sync_is_ready(self):
        v = rd.config_verdict_for("baseline", _drift("in_sync"))
        assert v["state"] == rd.READY

    def test_drifted_carries_count(self):
        v = rd.config_verdict_for("baseline", _drift("drifted", count=3))
        assert v["state"] == rd.DRIFTED and v["count"] == 3

    def test_other_scenario_is_on_loan(self):
        # The exclusivity signal: a sidelined demo has taken the device.
        v = rd.config_verdict_for("baseline", _drift("in_scenario", scenario="loiter"))
        assert v["state"] == rd.ON_LOAN and v["scenario_name"] == "loiter"

    def test_no_baseline(self):
        assert rd.config_verdict_for("baseline", _drift("none"))["state"] == rd.NO_BASELINE

    def test_unchecked(self):
        assert rd.config_verdict_for("baseline", _drift("unchecked"))["state"] == rd.UNCHECKED

    def test_none_config_source_defaults_to_baseline(self):
        assert rd.config_verdict_for(None, _drift("in_sync"))["state"] == rd.READY


# ---------------------------------------------------------------------------
# The matrix — sidelined demos (config_source = scenario:<name>)
# ---------------------------------------------------------------------------


class TestSidelinedDemoConfigVerdict:
    def test_its_own_scenario_is_ready(self):
        v = rd.config_verdict_for("scenario:loiter",
                                  _drift("in_scenario", scenario="loiter"))
        assert v["state"] == rd.READY and v["scenario_name"] == "loiter"

    def test_someone_elses_scenario_is_conflict(self):
        v = rd.config_verdict_for("scenario:loiter",
                                  _drift("in_scenario", scenario="audio"))
        assert v["state"] == rd.CONFLICT and v["scenario_name"] == "audio"

    def test_on_baseline_is_not_loaded(self):
        assert rd.config_verdict_for(
            "scenario:loiter", _drift("in_sync"))["state"] == rd.NOT_LOADED

    def test_drifted_is_still_just_not_loaded(self):
        # Drift vs baseline is a separate concern; the demo simply isn't loaded.
        assert rd.config_verdict_for(
            "scenario:loiter", _drift("drifted", count=2))["state"] == rd.NOT_LOADED

    def test_no_baseline(self):
        assert rd.config_verdict_for(
            "scenario:loiter", _drift("none"))["state"] == rd.NO_BASELINE

    def test_unchecked(self):
        assert rd.config_verdict_for(
            "scenario:loiter", _drift("unchecked"))["state"] == rd.UNCHECKED


class TestScenarioOf:
    def test_parses(self):
        assert rd.scenario_of("scenario:demo-a") == "demo-a"
        assert rd.scenario_of("baseline") is None
        assert rd.scenario_of(None) is None
        assert rd.scenario_of("scenario:") is None  # empty name → baseline-ish


# ---------------------------------------------------------------------------
# Demo-level rollup — worst wins
# ---------------------------------------------------------------------------


def _row(device_id, state, *, role="detector", health="online", **kw):
    return rd.device_readiness(
        kw.pop("config_source", "baseline"), device_id, role,
        _drift(state, **kw), health)


class TestDemoRollup:
    def test_all_ready_online_is_ready(self):
        rows = [_row("a", "in_sync"), _row("b", "in_sync")]
        out = rd.demo_readiness("baseline", rows)
        assert out["state"] == rd.DEMO_READY and out["blockers"] == []

    def test_offline_device_blocks_ready(self):
        rows = [_row("a", "in_sync"), _row("b", "in_sync", health="unreachable")]
        out = rd.demo_readiness("baseline", rows)
        assert out["state"] == rd.DEMO_NOT_READY
        assert out["offline"] == 1
        assert any("unreachable" in b for b in out["blockers"])

    def test_on_loan_blocks(self):
        rows = [_row("a", "in_sync"),
                _row("b", "in_scenario", scenario="loiter")]
        out = rd.demo_readiness("baseline", rows)
        assert out["state"] == rd.DEMO_BLOCKED
        assert any("on loan" in b and "loiter" in b for b in out["blockers"])

    def test_drifted_is_not_ready(self):
        rows = [_row("a", "drifted", count=4)]
        out = rd.demo_readiness("baseline", rows)
        assert out["state"] == rd.DEMO_NOT_READY
        assert any("drifted (4 field" in b for b in out["blockers"])

    def test_sidelined_all_not_loaded_is_actionable(self):
        rows = [_row("a", "in_sync", config_source="scenario:x"),
                _row("b", "in_sync", config_source="scenario:x")]
        out = rd.demo_readiness("scenario:x", rows)
        assert out["state"] == rd.DEMO_NOT_LOADED  # → hit Prepare, not broken

    def test_sidelined_loaded_is_ready(self):
        rows = [_row("a", "in_scenario", scenario="x", config_source="scenario:x")]
        assert rd.demo_readiness("scenario:x", rows)["state"] == rd.DEMO_READY

    def test_worst_wins_over_ready(self):
        rows = [_row("a", "in_sync"), _row("b", "in_sync"),
                _row("c", "in_scenario", scenario="other")]
        assert rd.demo_readiness("baseline", rows)["state"] == rd.DEMO_BLOCKED

    def test_conflict_outranks_drift(self):
        rows = [_row("a", "drifted", count=1, config_source="scenario:x"),
                _row("b", "in_scenario", scenario="y", config_source="scenario:x")]
        out = rd.demo_readiness("scenario:x", rows)
        assert out["state"] == rd.DEMO_BLOCKED

    def test_empty(self):
        out = rd.demo_readiness("baseline", [])
        assert out["state"] == rd.DEMO_EMPTY


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return DemoStore(str(tmp_path / "admz.db"))


class TestDemoStore:
    def test_create_get_roundtrip_json_fields(self, store):
        d = store.create(Demo(
            id="", name="Loitering", narrative="Walk into the zone…",
            tag="speakers", device_ids=["A", "B"],
            roles={"A": "detector", "B": "responder"},
            config_source="scenario:loiter",
            signals=[{"role": "detector", "category": "motion"}],
        ))
        assert d.id  # generated
        got = store.get(d.id)
        assert got.name == "Loitering"
        assert got.narrative.startswith("Walk into")
        assert got.device_ids == ["A", "B"]
        assert got.roles == {"A": "detector", "B": "responder"}
        assert got.config_source == "scenario:loiter"
        assert got.signals == [{"role": "detector", "category": "motion"}]
        assert got.enabled is True and got.created_at > 0

    def test_defaults_to_baseline(self, store):
        d = store.create(Demo(id="", name="Simple"))
        assert store.get(d.id).config_source == "baseline"

    def test_list_and_update_and_delete(self, store):
        a = store.create(Demo(id="", name="Bravo"))
        b = store.create(Demo(id="", name="Alpha"))
        assert [x.name for x in store.list()] == ["Alpha", "Bravo"]  # sorted
        b.name = "Alpha2"
        b.config_source = "scenario:z"
        store.update(b)
        assert store.get(b.id).name == "Alpha2"
        assert store.get(b.id).config_source == "scenario:z"
        assert store.delete(a.id) is True
        assert store.get(a.id) is None
        assert store.delete("nope") is False

    def test_get_missing(self, store):
        assert store.get("nothing") is None


# ---------------------------------------------------------------------------
# EventStore.activity_since / count_since — "did this signal fire, and when?"
# ---------------------------------------------------------------------------


@pytest.fixture
def events(tmp_path):
    return EventStore(str(tmp_path / "events.db"))


def _ev(eid, ts_ms, device_id, type_):
    return {"id": eid, "ts": "x", "ts_ms": ts_ms, "source": "device",
            "type": type_, "device_id": device_id, "device_name": device_id,
            "summary": "", "data": {}}


class TestActivitySince:
    def test_counts_and_last_ms(self, events):
        events.append(_ev("1", 1000, "A", "tns1:VideoSource/MotionAlarm"))
        events.append(_ev("2", 2000, "A", "tns1:VideoSource/MotionAlarm"))
        events.append(_ev("3", 3000, "B", "tns1:Device/IO/Port"))
        out = events.activity_since(since_ms=0, device_id="A")
        assert out["count"] == 2 and out["last_ms"] == 2000

    def test_since_bounds(self, events):
        events.append(_ev("1", 1000, "A", "motion"))
        events.append(_ev("2", 5000, "A", "motion"))
        assert events.activity_since(since_ms=2000, device_id="A")["count"] == 1
        assert events.count_since(since_ms=2000, device_id="A") == 1

    def test_type_filter_is_substring_insensitive(self, events):
        events.append(_ev("1", 1000, "A", "tns1:VideoSource/MotionAlarm"))
        out = events.activity_since(since_ms=0, type_filter="motionalarm")
        assert out["count"] == 1

    def test_no_match_is_zero_and_none(self, events):
        events.append(_ev("1", 1000, "A", "motion"))
        out = events.activity_since(since_ms=0, device_id="ZZZ")
        assert out["count"] == 0 and out["last_ms"] is None
