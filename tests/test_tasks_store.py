"""Tests for the unified TaskStore (ADR-0037)."""

from __future__ import annotations

import time

import pytest

from admz.tasks.store import (
    EVENT_NEEDS_SETUP,
    TRIGGER_DETECTION,
    TRIGGER_SCHEDULE,
    Task,
    TaskStore,
    event_for_status,
)


@pytest.fixture
def store(tmp_path):
    return TaskStore(str(tmp_path / "admz.db"))


class TestScheduleTasks:
    def test_create_get_list(self, store):
        t = store.create_schedule(
            description="Nightly snapshot", interval_seconds=3600,
            action_type="snapshot", tag_filter="lab",
        )
        assert t.trigger_kind == TRIGGER_SCHEDULE
        assert t.next_run  # defaulted to now+interval
        got = store.get(t.id)
        assert got.description == "Nightly snapshot"
        assert got.interval_seconds == 3600
        assert got.tag_filter == "lab"
        assert got.enabled is True
        scheds = store.schedule_tasks()
        assert [s.id for s in scheds] == [t.id]

    def test_enabled_only_filter(self, store):
        a = store.create_schedule(description="on", interval_seconds=60)
        b = store.create_schedule(description="off", interval_seconds=60, enabled=False)
        ids = {s.id for s in store.schedule_tasks(enabled_only=True)}
        assert a.id in ids and b.id not in ids

    def test_update_and_run_result(self, store):
        t = store.create_schedule(description="x", interval_seconds=60)
        store.update(t.id, enabled=False, interval_seconds=120)
        assert store.get(t.id).enabled is False
        assert store.get(t.id).interval_seconds == 120
        store.set_run_result(t.id, last_run="2026-06-18T00:00:00+00:00",
                             last_result="3 succeeded", next_run="2026-06-18T01:00:00+00:00")
        g = store.get(t.id)
        assert g.last_result == "3 succeeded"
        assert g.next_run == "2026-06-18T01:00:00+00:00"

    def test_delete(self, store):
        t = store.create_schedule(description="x", interval_seconds=60)
        assert store.delete(t.id) is True
        assert store.get(t.id) is None
        assert store.delete(t.id) is False

    def test_device_ids_roundtrip(self, store):
        t = store.create_schedule(
            description="x", interval_seconds=60, device_ids=["AA", "BB"],
        )
        assert store.get(t.id).device_ids == ["AA", "BB"]


class TestDetectionTasks:
    def test_create_and_list_active_for(self, store):
        pid = store.create_detection(
            device_id="cam-1", event=EVENT_NEEDS_SETUP, action_type="reprovision",
            action_params={"username": "root"}, approved_by="tester",
            description="recover cam-1",
        )
        active = store.list_active_for("cam-1")
        assert len(active) == 1
        t = active[0]
        assert t.id == pid
        assert t.trigger_kind == TRIGGER_DETECTION
        assert t.action_type == "reprovision"
        assert t.action == {"action": "reprovision", "username": "root"}
        assert t.approved_by == "tester"
        # not visible for another device
        assert store.list_active_for("other") == []

    def test_unknown_event_rejected(self, store):
        with pytest.raises(ValueError):
            store.create_detection(device_id="x", event="on_whatever",
                                   action_type="reprovision")

    def test_claim_fires_once(self, store):
        store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                               action_type="reprovision")
        first = store.claim_for_event("cam-1", EVENT_NEEDS_SETUP)
        assert len(first) == 1
        # a second concurrent claim gets nothing (already fired)
        second = store.claim_for_event("cam-1", EVENT_NEEDS_SETUP)
        assert second == []
        # it's no longer in the active list
        assert store.list_active_for("cam-1") == []

    def test_claim_event_mismatch(self, store):
        store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                               action_type="reprovision")
        assert store.claim_for_event("cam-1", "on_online") == []

    def test_cancel(self, store):
        pid = store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                                     action_type="reprovision")
        assert store.cancel(pid) is True
        assert store.list_active_for("cam-1") == []
        # cancel is a no-op once it's not pending
        assert store.cancel(pid) is False

    def test_expire_stale(self, store):
        pid = store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                                     action_type="reprovision", ttl_seconds=-1)
        # already expired -> expire_stale flips it
        assert store.expire_stale() == 1
        assert store.list_active_for("cam-1") == []
        assert store.get(pid).status == "expired"

    def test_schedule_tasks_excludes_detections(self, store):
        store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                               action_type="reprovision")
        store.create_schedule(description="s", interval_seconds=60)
        assert len(store.schedule_tasks()) == 1


class TestListFilters:
    def test_list_by_kind_and_device(self, store):
        store.create_schedule(description="s", interval_seconds=60, device_ids=["cam-1"])
        store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                               action_type="reprovision")
        store.create_detection(device_id="cam-2", event=EVENT_NEEDS_SETUP,
                               action_type="reprovision")
        assert len(store.list(trigger_kind=TRIGGER_DETECTION)) == 2
        assert len(store.list(trigger_kind=TRIGGER_SCHEDULE)) == 1
        # device filter spans schedule scope (device_ids) + detection target
        for_cam1 = store.list(device_id="cam-1")
        assert {t.trigger_kind for t in for_cam1} == {TRIGGER_SCHEDULE, TRIGGER_DETECTION}
        assert len(for_cam1) == 2

    def test_active_only_drops_cancelled_detection(self, store):
        pid = store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                                     action_type="reprovision")
        store.cancel(pid)
        assert store.list(trigger_kind=TRIGGER_DETECTION, active_only=True) == []
        assert len(store.list(trigger_kind=TRIGGER_DETECTION)) == 1  # still on record


def test_event_for_status():
    assert event_for_status("needs_setup") == EVENT_NEEDS_SETUP
    assert event_for_status("online") == "on_online"
    assert event_for_status("auth_failed") is None


def test_task_to_dict_shape():
    t = Task(id="x", description="hi", interval_seconds=3600, action_type="snapshot")
    d = t.to_dict()
    assert d["name"] == "hi" and d["interval_human"] == "1h"
    assert d["trigger_kind"] == "schedule"
