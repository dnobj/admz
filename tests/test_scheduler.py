"""Tests for the snapshot scheduler."""

import asyncio
import json
import os

import pytest

from admz.snapshot.scheduler import (
    SnapshotSchedule,
    SnapshotScheduler,
    parse_interval,
)


@pytest.fixture(autouse=True)
def _isolate_tasks_store(tmp_path, monkeypatch):
    """ADR-0037: schedules live in the SQLite tasks store. Point the singleton at
    a per-test DB so each test starts clean (the schedule_path arg is now inert)."""
    import admz.tasks.store as _sm
    from admz.tasks.store import TaskStore
    monkeypatch.setattr(_sm, "tasks_store", TaskStore(str(tmp_path / "tasks.db")))


# ---------------------------------------------------------------------------
# Test parse_interval
# ---------------------------------------------------------------------------

class TestParseInterval:

    def test_seconds(self):
        assert parse_interval("30s") == 30

    def test_minutes(self):
        assert parse_interval("5m") == 300

    def test_hours(self):
        assert parse_interval("2h") == 7200

    def test_days(self):
        assert parse_interval("1d") == 86400

    def test_long_units(self):
        assert parse_interval("30 minutes") == 1800
        assert parse_interval("2 hours") == 7200
        assert parse_interval("1 day") == 86400

    def test_bare_number_is_seconds(self):
        assert parse_interval("3600") == 3600

    def test_fractional(self):
        assert parse_interval("1.5h") == 5400

    def test_whitespace(self):
        assert parse_interval("  2h  ") == 7200

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_interval("never")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_interval("")


# ---------------------------------------------------------------------------
# Test SnapshotSchedule
# ---------------------------------------------------------------------------

class TestSnapshotSchedule:

    def test_to_dict(self):
        s = SnapshotSchedule(
            id="nightly",
            description="Nightly backup",
            interval_seconds=86400,
            tag_filter="experience-center",
        )
        d = s.to_dict()
        assert d["id"] == "nightly"
        assert d["interval_seconds"] == 86400
        assert d["tag_filter"] == "experience-center"
        assert "device_ids" not in d  # None fields stripped

    def test_from_dict(self):
        d = {
            "id": "hourly",
            "description": "Hourly lobby",
            "interval_seconds": 3600,
            "tag_filter": "lobby",
            "enabled": True,
        }
        s = SnapshotSchedule.from_dict(d)
        assert s.id == "hourly"
        assert s.interval_seconds == 3600
        assert s.tag_filter == "lobby"

    def test_from_dict_ignores_unknown_keys(self):
        d = {
            "id": "test",
            "description": "test",
            "interval_seconds": 60,
            "unknown_key": "ignored",
        }
        s = SnapshotSchedule.from_dict(d)
        assert s.id == "test"

    def test_interval_human_seconds(self):
        s = SnapshotSchedule(id="t", description="t", interval_seconds=30)
        assert s.interval_human == "30s"

    def test_interval_human_minutes(self):
        s = SnapshotSchedule(id="t", description="t", interval_seconds=300)
        assert s.interval_human == "5m"

    def test_interval_human_hours(self):
        s = SnapshotSchedule(id="t", description="t", interval_seconds=7200)
        assert s.interval_human == "2h"

    def test_interval_human_days(self):
        s = SnapshotSchedule(id="t", description="t", interval_seconds=172800)
        assert s.interval_human == "2d"

    def test_roundtrip(self):
        s = SnapshotSchedule(
            id="test",
            description="Test schedule",
            interval_seconds=3600,
            tag_filter="lobby",
            enabled=True,
            device_ids=["cam-01", "cam-02"],
        )
        d = s.to_dict()
        s2 = SnapshotSchedule.from_dict(d)
        assert s2.id == s.id
        assert s2.interval_seconds == s.interval_seconds
        assert s2.device_ids == s.device_ids


# ---------------------------------------------------------------------------
# Test SnapshotScheduler (persistence)
# ---------------------------------------------------------------------------

class MockSnapshotEngine:
    def __init__(self):
        self.calls = []

    async def snapshot_fleet(self, **kwargs):
        self.calls.append(kwargs)
        return []


class TestSchedulerPersistence:

    def test_add_and_list(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)

        s = SnapshotSchedule(
            id="nightly",
            description="Nightly backup",
            interval_seconds=86400,
        )
        scheduler.add_schedule(s)

        schedules = scheduler.list_schedules()
        assert len(schedules) == 1
        assert schedules[0].id == "nightly"

    def test_persistence_across_instances(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")

        s1 = SnapshotScheduler(engine, path)
        s1.add_schedule(SnapshotSchedule(
            id="hourly",
            description="Hourly",
            interval_seconds=3600,
        ))

        # A second scheduler instance reads the same (shared SQLite) store.
        s2 = SnapshotScheduler(engine, path)
        got = s2.get_schedule("hourly")
        assert got is not None
        assert got.interval_seconds == 3600

    def test_remove_schedule(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)

        scheduler.add_schedule(SnapshotSchedule(
            id="temp", description="Temp", interval_seconds=60,
        ))
        assert scheduler.remove_schedule("temp")
        assert len(scheduler.list_schedules()) == 0

    def test_remove_nonexistent(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)
        assert not scheduler.remove_schedule("nope")

    def test_update_schedule(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)

        scheduler.add_schedule(SnapshotSchedule(
            id="s1", description="Original", interval_seconds=3600,
        ))
        updated = scheduler.update_schedule(
            "s1", description="Updated", interval_seconds=7200,
        )
        assert updated is not None
        assert updated.description == "Updated"
        assert updated.interval_seconds == 7200

    def test_update_nonexistent(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)
        assert scheduler.update_schedule("nope", enabled=False) is None

    def test_get_schedule(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)

        scheduler.add_schedule(SnapshotSchedule(
            id="s1", description="S1", interval_seconds=60,
        ))
        assert scheduler.get_schedule("s1") is not None
        assert scheduler.get_schedule("nope") is None

    def test_added_schedule_is_persisted(self, tmp_path):
        # ADR-0037: persistence is the SQLite tasks store, not a JSON file —
        # a fresh scheduler instance still sees the added schedule.
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)
        scheduler.add_schedule(SnapshotSchedule(
            id="s1", description="S1", interval_seconds=60,
        ))
        assert SnapshotScheduler(engine, path).get_schedule("s1") is not None


# ---------------------------------------------------------------------------
# Test SnapshotScheduler (async execution)
# ---------------------------------------------------------------------------

class TestSchedulerExecution:

    @pytest.mark.asyncio
    async def test_run_now(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)

        scheduler.add_schedule(SnapshotSchedule(
            id="s1",
            description="Test",
            interval_seconds=86400,
            tag_filter="lobby",
        ))

        result = await scheduler.run_now("s1")
        assert result["success"] is True
        assert len(engine.calls) == 1
        assert engine.calls[0]["tag_filter"] == "lobby"

    @pytest.mark.asyncio
    async def test_run_now_nonexistent(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)

        result = await scheduler.run_now("nope")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_run_now_updates_last_run(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)

        scheduler.add_schedule(SnapshotSchedule(
            id="s1", description="Test", interval_seconds=3600,
        ))
        assert scheduler.get_schedule("s1").last_run is None

        await scheduler.run_now("s1")
        assert scheduler.get_schedule("s1").last_run is not None

    @pytest.mark.asyncio
    async def test_start_and_stop(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)

        scheduler.add_schedule(SnapshotSchedule(
            id="s1", description="Fast", interval_seconds=86400,
        ))

        await scheduler.start()
        assert scheduler._running
        assert "s1" in scheduler._tasks

        await scheduler.stop()
        assert not scheduler._running
        assert len(scheduler._tasks) == 0

    @pytest.mark.asyncio
    async def test_disabled_schedule_not_started(self, tmp_path):
        engine = MockSnapshotEngine()
        path = str(tmp_path / "schedules.json")
        scheduler = SnapshotScheduler(engine, path)

        scheduler.add_schedule(SnapshotSchedule(
            id="s1", description="Disabled", interval_seconds=60,
            enabled=False,
        ))

        await scheduler.start()
        assert "s1" not in scheduler._tasks
        await scheduler.stop()
