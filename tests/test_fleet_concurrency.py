"""Tests for the Phase 3D bounded-fleet-snapshot concurrency cap.

The semaphore in SnapshotEngine.snapshot_fleet must (a) be honored at
runtime, (b) be configurable per-instance and via env var, and (c)
fall back sanely on invalid env values.
"""

import asyncio

import pytest

from admz.snapshot.engine import (
    SnapshotEngine,
    _DEFAULT_FLEET_CONCURRENCY,
    _resolve_fleet_concurrency,
)
from admz.snapshot.models import DeviceSnapshot, SnapshotStatus


# ---------------------------------------------------------------------------
# Env-var resolution
# ---------------------------------------------------------------------------


class TestResolveFleetConcurrency:
    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("ADMZ_SNAPSHOT_FLEET_CONCURRENCY", raising=False)
        assert _resolve_fleet_concurrency() == _DEFAULT_FLEET_CONCURRENCY

    def test_valid_integer(self, monkeypatch):
        monkeypatch.setenv("ADMZ_SNAPSHOT_FLEET_CONCURRENCY", "8")
        assert _resolve_fleet_concurrency() == 8

    def test_one_is_valid(self, monkeypatch):
        # Lowest meaningful concurrency
        monkeypatch.setenv("ADMZ_SNAPSHOT_FLEET_CONCURRENCY", "1")
        assert _resolve_fleet_concurrency() == 1

    def test_zero_falls_back(self, monkeypatch, caplog):
        import logging
        monkeypatch.setenv("ADMZ_SNAPSHOT_FLEET_CONCURRENCY", "0")
        with caplog.at_level(logging.WARNING):
            result = _resolve_fleet_concurrency()
        assert result == _DEFAULT_FLEET_CONCURRENCY
        assert any("not positive" in r.message for r in caplog.records)

    def test_negative_falls_back(self, monkeypatch):
        monkeypatch.setenv("ADMZ_SNAPSHOT_FLEET_CONCURRENCY", "-3")
        assert _resolve_fleet_concurrency() == _DEFAULT_FLEET_CONCURRENCY

    def test_non_integer_falls_back(self, monkeypatch, caplog):
        import logging
        monkeypatch.setenv("ADMZ_SNAPSHOT_FLEET_CONCURRENCY", "fifty")
        with caplog.at_level(logging.WARNING):
            result = _resolve_fleet_concurrency()
        assert result == _DEFAULT_FLEET_CONCURRENCY
        assert any("not an integer" in r.message for r in caplog.records)

    def test_empty_string_falls_back(self, monkeypatch):
        monkeypatch.setenv("ADMZ_SNAPSHOT_FLEET_CONCURRENCY", "")
        assert _resolve_fleet_concurrency() == _DEFAULT_FLEET_CONCURRENCY


# ---------------------------------------------------------------------------
# Engine ctor honors the limit
# ---------------------------------------------------------------------------


class TestEngineConstructorCap:
    def _make_engine(self, **kwargs):
        # SnapshotEngine wants catalog / registry / executors / git_repo
        # but we only test that it surfaces the concurrency limit.
        from unittest.mock import MagicMock
        return SnapshotEngine(
            catalog=MagicMock(),
            registry=MagicMock(),
            executors={},
            git_repo=MagicMock(),
            **kwargs,
        )

    def test_default_from_env(self, monkeypatch):
        monkeypatch.delenv("ADMZ_SNAPSHOT_FLEET_CONCURRENCY", raising=False)
        engine = self._make_engine()
        assert engine.fleet_concurrency == _DEFAULT_FLEET_CONCURRENCY

    def test_explicit_overrides_env(self, monkeypatch):
        monkeypatch.setenv("ADMZ_SNAPSHOT_FLEET_CONCURRENCY", "8")
        engine = self._make_engine(fleet_concurrency=2)
        assert engine.fleet_concurrency == 2

    def test_env_picked_up_when_no_explicit(self, monkeypatch):
        monkeypatch.setenv("ADMZ_SNAPSHOT_FLEET_CONCURRENCY", "8")
        engine = self._make_engine()
        assert engine.fleet_concurrency == 8


# ---------------------------------------------------------------------------
# Runtime: the semaphore actually limits in-flight work
# ---------------------------------------------------------------------------


class TestFleetSemaphoreLimitsConcurrency:
    @pytest.mark.asyncio
    async def test_concurrency_capped_at_configured_limit(self):
        """Track the high-water mark of concurrent in-flight snapshots
        and verify it never exceeds the configured cap."""
        from unittest.mock import MagicMock

        engine = SnapshotEngine(
            catalog=MagicMock(),
            registry=MagicMock(),
            executors={},
            git_repo=MagicMock(),
            fleet_concurrency=3,
        )

        # Registry returns a synthetic device list — _snapshot_device_no_commit
        # is replaced below so we never touch real network calls.
        engine.registry.list_devices.return_value = [
            {"device_id": f"cam-{i:02d}", "tags": []} for i in range(20)
        ]
        engine.git.commit_fleet_snapshot.return_value = "deadbeef"

        # Track concurrency via a mutable counter + max watermark
        in_flight = 0
        max_in_flight = 0
        gate = asyncio.Event()

        async def fake_snapshot_no_commit(device_id, family):
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            # Hold long enough that the semaphore matters
            await asyncio.sleep(0.05)
            in_flight -= 1
            return DeviceSnapshot(
                device_id=device_id,
                device_info={"device_id": device_id},
                status=SnapshotStatus.COMPLETED,
            )

        engine._snapshot_device_no_commit = fake_snapshot_no_commit

        results = await engine.snapshot_fleet()
        assert len(results) == 20
        # The cap is 3, so at no point should more than 3 be in flight
        assert max_in_flight <= 3, (
            f"semaphore breached: max_in_flight={max_in_flight}"
        )
        # And the cap should actually have been *reached* — otherwise the
        # test would pass trivially with cap=1000 too.
        assert max_in_flight == 3, (
            f"expected concurrency to saturate at 3; got {max_in_flight}"
        )

    @pytest.mark.asyncio
    async def test_higher_cap_allows_more_parallelism(self):
        """Sanity check: with a higher cap, more snapshots run in parallel."""
        from unittest.mock import MagicMock

        engine = SnapshotEngine(
            catalog=MagicMock(),
            registry=MagicMock(),
            executors={},
            git_repo=MagicMock(),
            fleet_concurrency=10,
        )
        engine.registry.list_devices.return_value = [
            {"device_id": f"cam-{i:02d}", "tags": []} for i in range(20)
        ]
        engine.git.commit_fleet_snapshot.return_value = "deadbeef"

        in_flight = 0
        max_in_flight = 0

        async def fake_snapshot_no_commit(device_id, family):
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.05)
            in_flight -= 1
            return DeviceSnapshot(
                device_id=device_id,
                device_info={"device_id": device_id},
                status=SnapshotStatus.COMPLETED,
            )

        engine._snapshot_device_no_commit = fake_snapshot_no_commit

        await engine.snapshot_fleet()
        # With cap=10 and 20 devices, we should saturate at 10
        assert max_in_flight == 10
