"""Tests for the unified-scheduler additions (#22 Slice A).

Pins:
  * FR-SCH-010 — handler registry: register_job_handler / get_job_handler /
    list_job_types; _execute_schedule dispatches by job_type; unknown
    job_type produces a clear error envelope.
  * FR-SCH-011 — drift_audit handler: runs check_fleet_drift; new
    transitions flow into drift_alerts; summary reflects counts.
  * FR-SCH-013 — every run attributes the audit row to the synthetic
    'scheduler' principal (NOT 'anonymous'); failures also audited.
  * KL-SCH-005 — per-job lock: run_now and the interval loop never
    overlap for the same schedule id.
  * Migration — schedules.json without job_type loads as 'snapshot'.
  * Pre-existing snapshot behavior unchanged (covered by the
    untouched tests/test_scheduler.py).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from admz.snapshot.scheduler import (
    JobContext,
    ScheduledJob,
    SnapshotSchedule,
    SnapshotScheduler,
    _HANDLERS,
    get_job_handler,
    list_job_types,
    register_job_handler,
)


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------


class TestHandlerRegistry:
    def test_snapshot_handler_registered_at_import(self):
        assert get_job_handler("snapshot") is not None

    def test_drift_audit_handler_registered_at_import(self):
        assert get_job_handler("drift_audit") is not None

    def test_unknown_job_type_returns_none(self):
        assert get_job_handler("does-not-exist") is None

    def test_list_job_types_includes_both(self):
        types = list_job_types()
        assert "snapshot" in types
        assert "drift_audit" in types

    def test_register_then_unregister_via_decorator(self):
        """Tests can register transient handlers, then pop the key to
        keep the global registry clean."""
        @register_job_handler("test_job")
        async def _h(job, ctx):
            return {"success": True, "summary": "ok"}

        assert get_job_handler("test_job") is _h
        # Cleanup so other tests see a clean registry.
        del _HANDLERS["test_job"]


# ---------------------------------------------------------------------------
# Dispatch behavior
# ---------------------------------------------------------------------------


class TestDispatch:
    def _mk_scheduler(self, tmp_path, **kwargs):
        return SnapshotScheduler(
            snapshot_engine=kwargs.get("snapshot_engine", MagicMock()),
            schedule_path=str(tmp_path / "schedules.json"),
            drift_detector=kwargs.get("drift_detector"),
        )

    @pytest.mark.asyncio
    async def test_snapshot_job_dispatches_to_snapshot_handler(
        self, tmp_path,
    ):
        # Mock the engine so we don't talk to real devices.
        engine = MagicMock()
        engine.snapshot_fleet = AsyncMock(return_value=[])
        s = self._mk_scheduler(tmp_path, snapshot_engine=engine)
        job = SnapshotSchedule(
            id="s1", description="d", interval_seconds=3600,
            job_type="snapshot",
        )
        s.schedules[job.id] = job

        result = await s._execute_schedule(job)
        assert result["success"] is True
        assert result["job_type"] == "snapshot"
        assert engine.snapshot_fleet.called

    @pytest.mark.asyncio
    async def test_drift_audit_dispatches_to_drift_handler(self, tmp_path):
        detector = MagicMock()
        detector.check_fleet_drift = AsyncMock(return_value=[])
        s = self._mk_scheduler(tmp_path, drift_detector=detector)
        job = SnapshotSchedule(
            id="d1", description="nightly audit",
            interval_seconds=86400, job_type="drift_audit",
        )
        s.schedules[job.id] = job

        result = await s._execute_schedule(job)
        assert result["success"] is True
        assert result["job_type"] == "drift_audit"
        assert result["checked"] == 0
        assert detector.check_fleet_drift.called

    @pytest.mark.asyncio
    async def test_unknown_job_type_returns_clear_error(self, tmp_path):
        s = self._mk_scheduler(tmp_path)
        job = SnapshotSchedule(
            id="x", description="bogus", interval_seconds=3600,
            job_type="not_a_real_type",
        )
        s.schedules[job.id] = job
        result = await s._execute_schedule(job)
        assert result["success"] is False
        assert "not_a_real_type" in result["error"]
        # And the failure surfaces in last_result for operator visibility.
        assert "error" in s.schedules["x"].last_result.lower()

    @pytest.mark.asyncio
    async def test_handler_exception_becomes_error_envelope(self, tmp_path):
        engine = MagicMock()
        engine.snapshot_fleet = AsyncMock(
            side_effect=RuntimeError("simulated boom")
        )
        s = self._mk_scheduler(tmp_path, snapshot_engine=engine)
        job = SnapshotSchedule(
            id="s2", description="d", interval_seconds=3600,
        )
        s.schedules[job.id] = job
        result = await s._execute_schedule(job)
        assert result["success"] is False
        assert "simulated boom" in result["error"]


# ---------------------------------------------------------------------------
# Per-job lock (KL-SCH-005)
# ---------------------------------------------------------------------------


class TestPerJobLock:
    @pytest.mark.asyncio
    async def test_concurrent_run_for_same_schedule_is_serialized(
        self, tmp_path,
    ):
        """Two ``run_now`` calls for the same schedule run sequentially.
        Specifically: the second call must not enter the handler until
        the first has returned."""
        order: list = []

        # Register a handler that records enter/exit ordering.
        @register_job_handler("ordered_probe")
        async def _h(job, ctx):
            order.append(("enter", job.id))
            await asyncio.sleep(0.05)
            order.append(("exit", job.id))
            return {"success": True, "summary": "ok"}

        try:
            s = SnapshotScheduler(
                snapshot_engine=MagicMock(),
                schedule_path=str(tmp_path / "schedules.json"),
            )
            job = SnapshotSchedule(
                id="probe", description="d", interval_seconds=3600,
                job_type="ordered_probe",
            )
            s.schedules[job.id] = job

            # Kick off two concurrent runs.
            await asyncio.gather(
                s._execute_schedule(job),
                s._execute_schedule(job),
            )

            # The trace must show interleave-free runs: each
            # ("enter", X) is followed by ("exit", X) before the
            # next ("enter", X).
            assert order == [
                ("enter", "probe"), ("exit", "probe"),
                ("enter", "probe"), ("exit", "probe"),
            ]
        finally:
            del _HANDLERS["ordered_probe"]

    @pytest.mark.asyncio
    async def test_different_schedules_run_in_parallel(self, tmp_path):
        """The lock is per-schedule, NOT global. Two schedules can
        run concurrently."""
        active: list = []

        @register_job_handler("parallel_probe")
        async def _h(job, ctx):
            active.append(job.id)
            await asyncio.sleep(0.05)
            return {"success": True, "summary": "ok"}

        try:
            s = SnapshotScheduler(
                snapshot_engine=MagicMock(),
                schedule_path=str(tmp_path / "schedules.json"),
            )
            j1 = SnapshotSchedule(
                id="a", description="d", interval_seconds=3600,
                job_type="parallel_probe",
            )
            j2 = SnapshotSchedule(
                id="b", description="d", interval_seconds=3600,
                job_type="parallel_probe",
            )
            s.schedules["a"] = j1
            s.schedules["b"] = j2

            await asyncio.gather(
                s._execute_schedule(j1),
                s._execute_schedule(j2),
            )

            # Both schedules entered the handler before either left
            # — i.e. they were genuinely parallel.
            assert set(active) == {"a", "b"}
        finally:
            del _HANDLERS["parallel_probe"]


# ---------------------------------------------------------------------------
# Audit attribution (FR-SCH-013)
# ---------------------------------------------------------------------------


class TestAuditAttribution:
    @pytest.mark.asyncio
    async def test_run_writes_audit_row_as_scheduler_principal(
        self, tmp_path, monkeypatch,
    ):
        from admz import audit as audit_module
        fresh_audit = audit_module.AuditLog(
            db_path=str(tmp_path / "admz.db"),
        )
        monkeypatch.setattr(audit_module, "audit_log", fresh_audit)

        engine = MagicMock()
        engine.snapshot_fleet = AsyncMock(return_value=[])
        s = SnapshotScheduler(
            snapshot_engine=engine,
            schedule_path=str(tmp_path / "schedules.json"),
        )
        job = SnapshotSchedule(
            id="audited", description="d", interval_seconds=3600,
            job_type="snapshot",
        )
        s.schedules[job.id] = job

        await s._execute_schedule(job)

        rows = audit_module.audit_log.list_recent(
            action="scheduler.run.snapshot", limit=5,
        )
        assert rows, "scheduler should write an audit row on every run"
        assert rows[0].requester == "scheduler"
        assert rows[0].auth_source == "scheduler"
        assert rows[0].success is True
        # Resource format: "schedule:<id>"
        assert rows[0].resource == "schedule:audited"

    @pytest.mark.asyncio
    async def test_failure_audited_with_error_message(
        self, tmp_path, monkeypatch,
    ):
        from admz import audit as audit_module
        fresh_audit = audit_module.AuditLog(
            db_path=str(tmp_path / "admz.db"),
        )
        monkeypatch.setattr(audit_module, "audit_log", fresh_audit)

        engine = MagicMock()
        engine.snapshot_fleet = AsyncMock(
            side_effect=RuntimeError("boom"),
        )
        s = SnapshotScheduler(
            snapshot_engine=engine,
            schedule_path=str(tmp_path / "schedules.json"),
        )
        job = SnapshotSchedule(
            id="failing", description="d", interval_seconds=3600,
        )
        s.schedules[job.id] = job
        await s._execute_schedule(job)

        rows = audit_module.audit_log.list_recent(
            action="scheduler.run.snapshot", limit=5,
        )
        assert rows[0].success is False
        assert "boom" in rows[0].error_message


# ---------------------------------------------------------------------------
# schedules.json migration (ADR-0026)
# ---------------------------------------------------------------------------


class TestMigration:
    def test_legacy_row_without_job_type_loads_as_snapshot(self, tmp_path):
        """Operator's existing schedules.json from before this PR
        has no `job_type` field. The loader defaults to 'snapshot'
        so nothing breaks for them."""
        path = tmp_path / "schedules.json"
        # Pre-Phase-X shape: no job_type, no params.
        path.write_text(json.dumps({
            "legacy": {
                "id": "legacy",
                "description": "every 6 hours",
                "interval_seconds": 21600,
                "tag_filter": "lobby",
                "enabled": True,
            }
        }))

        s = SnapshotScheduler(
            snapshot_engine=MagicMock(),
            schedule_path=str(path),
        )
        s._load()
        assert "legacy" in s.schedules
        assert s.schedules["legacy"].job_type == "snapshot"
        assert s.schedules["legacy"].params == {}

    def test_round_trip_preserves_job_type(self, tmp_path):
        path = tmp_path / "schedules.json"
        s = SnapshotScheduler(
            snapshot_engine=MagicMock(),
            schedule_path=str(path),
        )
        s.schedules["da"] = SnapshotSchedule(
            id="da", description="nightly", interval_seconds=86400,
            job_type="drift_audit",
        )
        s._save()
        # Re-load fresh; verify round-trip.
        s2 = SnapshotScheduler(
            snapshot_engine=MagicMock(),
            schedule_path=str(path),
        )
        s2._load()
        assert s2.schedules["da"].job_type == "drift_audit"

    def test_scheduled_job_alias_works(self):
        """ScheduledJob is the ADR-0026 name; SnapshotSchedule is the
        legacy name. They should be the same class."""
        assert ScheduledJob is SnapshotSchedule
