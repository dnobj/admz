"""Tests for the Task-native scheduler (ADR-0037, was the unified-scheduler PR).

Schedule tasks now live in the SQLite ``tasks`` store, not ``schedules.json`` —
so the old on-disk merge/reconcile tests are gone (replaced by
``test_tasks_store.py`` + ``test_tasks_migrate.py``). What still matters and is
pinned here:
  * handler registry: register/get/list (delegating to admz.tasks.handlers).
  * dispatch by action_type; unknown action → clear error envelope.
  * the drift_audit handler runs check_fleet_drift.
  * per-job lock (KL-SCH-005): run_now never overlaps itself for one task.
  * audit attribution (FR-SCH-013): the synthetic 'scheduler' principal.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from admz.snapshot.scheduler import (
    ScheduledJob,
    SnapshotSchedule,
    SnapshotScheduler,
    get_job_handler,
    list_job_types,
    register_job_handler,
)
from admz.tasks.handlers import _HANDLERS
from admz.tasks.store import TaskStore


def _scheduler(tmp_path, **kwargs):
    return SnapshotScheduler(
        snapshot_engine=kwargs.get("snapshot_engine", MagicMock()),
        drift_detector=kwargs.get("drift_detector"),
        store=TaskStore(str(tmp_path / "admz.db")),
    )


class TestHandlerRegistry:
    def test_builtin_handlers_registered_at_import(self):
        assert get_job_handler("snapshot") is not None
        assert get_job_handler("drift_audit") is not None
        assert get_job_handler("survey") is not None
        assert get_job_handler("reprovision") is not None

    def test_unknown_job_type_returns_none(self):
        assert get_job_handler("does-not-exist") is None

    def test_list_job_types_includes_builtins(self):
        types = list_job_types()
        assert {"snapshot", "drift_audit", "survey"} <= set(types)

    def test_register_then_unregister_via_decorator(self):
        @register_job_handler("test_job")
        async def _h(task, ctx):
            return {"success": True, "summary": "ok"}

        assert get_job_handler("test_job") is _h
        del _HANDLERS["test_job"]


class TestDispatch:
    @pytest.mark.asyncio
    async def test_snapshot_job_dispatches(self, tmp_path):
        engine = MagicMock()
        engine.snapshot_fleet = AsyncMock(return_value=[])
        s = _scheduler(tmp_path, snapshot_engine=engine)
        s.add_schedule(SnapshotSchedule(id="s1", description="d",
                                        interval_seconds=3600, job_type="snapshot"))
        result = await s.run_now("s1")
        assert result["success"] is True
        assert result["job_type"] == "snapshot"
        assert engine.snapshot_fleet.called

    @pytest.mark.asyncio
    async def test_drift_audit_dispatches(self, tmp_path):
        detector = MagicMock()
        detector.check_fleet_drift = AsyncMock(return_value=[])
        s = _scheduler(tmp_path, drift_detector=detector)
        s.add_schedule(SnapshotSchedule(id="d1", description="audit",
                                        interval_seconds=86400, job_type="drift_audit"))
        result = await s.run_now("d1")
        assert result["success"] is True
        assert result["job_type"] == "drift_audit"
        assert result["checked"] == 0
        assert detector.check_fleet_drift.called

    @pytest.mark.asyncio
    async def test_unknown_job_type_returns_clear_error(self, tmp_path):
        s = _scheduler(tmp_path)
        s.add_schedule(SnapshotSchedule(id="x", description="bogus",
                                        interval_seconds=3600, job_type="not_a_real_type"))
        result = await s.run_now("x")
        assert result["success"] is False
        assert "not_a_real_type" in result["error"]
        assert "error" in s.get_schedule("x").last_result.lower()

    @pytest.mark.asyncio
    async def test_handler_exception_becomes_error_envelope(self, tmp_path):
        engine = MagicMock()
        engine.snapshot_fleet = AsyncMock(side_effect=RuntimeError("simulated boom"))
        s = _scheduler(tmp_path, snapshot_engine=engine)
        s.add_schedule(SnapshotSchedule(id="s2", description="d", interval_seconds=3600))
        result = await s.run_now("s2")
        assert result["success"] is False
        assert "simulated boom" in result["error"]

    @pytest.mark.asyncio
    async def test_run_now_unknown_schedule(self, tmp_path):
        s = _scheduler(tmp_path)
        result = await s.run_now("ghost")
        assert result["success"] is False


class TestPerJobLock:
    @pytest.mark.asyncio
    async def test_concurrent_run_for_same_schedule_is_serialized(self, tmp_path):
        order: list = []

        @register_job_handler("ordered_probe")
        async def _h(task, ctx):
            order.append(("enter", task.id))
            await asyncio.sleep(0.05)
            order.append(("exit", task.id))
            return {"success": True, "summary": "ok"}

        try:
            s = _scheduler(tmp_path)
            s.add_schedule(SnapshotSchedule(id="probe", description="d",
                                            interval_seconds=3600, job_type="ordered_probe"))
            await asyncio.gather(s.run_now("probe"), s.run_now("probe"))
            assert order == [
                ("enter", "probe"), ("exit", "probe"),
                ("enter", "probe"), ("exit", "probe"),
            ]
        finally:
            del _HANDLERS["ordered_probe"]

    @pytest.mark.asyncio
    async def test_different_schedules_run_in_parallel(self, tmp_path):
        active: list = []

        @register_job_handler("parallel_probe")
        async def _h(task, ctx):
            active.append(task.id)
            await asyncio.sleep(0.05)
            return {"success": True, "summary": "ok"}

        try:
            s = _scheduler(tmp_path)
            s.add_schedule(SnapshotSchedule(id="a", description="d",
                                            interval_seconds=3600, job_type="parallel_probe"))
            s.add_schedule(SnapshotSchedule(id="b", description="d",
                                            interval_seconds=3600, job_type="parallel_probe"))
            await asyncio.gather(s.run_now("a"), s.run_now("b"))
            assert set(active) == {"a", "b"}
        finally:
            del _HANDLERS["parallel_probe"]


class TestAuditAttribution:
    @pytest.mark.asyncio
    async def test_run_writes_audit_row_as_scheduler_principal(self, tmp_path, monkeypatch):
        from admz import audit as audit_module
        fresh = audit_module.AuditLog(db_path=str(tmp_path / "audit.db"))
        monkeypatch.setattr(audit_module, "audit_log", fresh)

        engine = MagicMock()
        engine.snapshot_fleet = AsyncMock(return_value=[])
        s = _scheduler(tmp_path, snapshot_engine=engine)
        s.add_schedule(SnapshotSchedule(id="audited", description="d",
                                        interval_seconds=3600, job_type="snapshot"))
        await s.run_now("audited")

        rows = audit_module.audit_log.list_recent(action="scheduler.run.snapshot", limit=5)
        assert rows and rows[0].requester == "scheduler"
        assert rows[0].auth_source == "scheduler"
        assert rows[0].success is True
        assert rows[0].resource == "schedule:audited"

    @pytest.mark.asyncio
    async def test_failure_audited_with_error_message(self, tmp_path, monkeypatch):
        from admz import audit as audit_module
        fresh = audit_module.AuditLog(db_path=str(tmp_path / "audit.db"))
        monkeypatch.setattr(audit_module, "audit_log", fresh)

        engine = MagicMock()
        engine.snapshot_fleet = AsyncMock(side_effect=RuntimeError("boom"))
        s = _scheduler(tmp_path, snapshot_engine=engine)
        s.add_schedule(SnapshotSchedule(id="failing", description="d", interval_seconds=3600))
        await s.run_now("failing")

        rows = audit_module.audit_log.list_recent(action="scheduler.run.snapshot", limit=5)
        assert rows[0].success is False
        assert "boom" in rows[0].error_message


class TestStoreBackedCrud:
    def test_add_list_update_remove(self, tmp_path):
        s = _scheduler(tmp_path)
        s.add_schedule(SnapshotSchedule(id="a", description="a", interval_seconds=60))
        s.add_schedule(SnapshotSchedule(id="b", description="b", interval_seconds=60,
                                        job_type="drift_audit"))
        assert {x.id for x in s.list_schedules()} == {"a", "b"}
        assert s.get_schedule("b").job_type == "drift_audit"
        s.update_schedule("a", enabled=False)
        assert s.get_schedule("a").enabled is False
        assert s.remove_schedule("a") is True
        assert {x.id for x in s.list_schedules()} == {"b"}
        assert s.remove_schedule("ghost") is False

    def test_scheduled_job_alias_works(self):
        assert ScheduledJob is SnapshotSchedule
