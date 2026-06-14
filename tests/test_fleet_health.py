"""Tests for the device health monitor: store + per-device probe + monitor loop.

The monitor is opt-in via the ``health_monitor_enabled`` fleet
setting. Tests below isolate the store (SQLite tmp), mock the
network probe, and exercise both the storage round-trip and the
monitor's per-device dispatch.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from admz.fleet.health import (
    DeviceHealthRecord,
    DeviceHealthStatus,
    DeviceHealthStore,
    HealthMonitor,
    probe_device,
)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return DeviceHealthStore(str(tmp_path / "admz.db"))


class TestStore:
    def test_unknown_device_returns_none(self, store):
        assert store.get("missing") is None

    def test_upsert_round_trip(self, store):
        rec = DeviceHealthRecord(
            device_id="cam-01",
            status=DeviceHealthStatus.ONLINE,
            last_check=1234567890.0,
            last_seen_online=1234567890.0,
            latency_ms=42,
            uptime_seconds=3600,
            bootid="boot-abc",
        )
        store.upsert(rec)
        out = store.get("cam-01")
        assert out is not None
        assert out.status == DeviceHealthStatus.ONLINE
        assert out.latency_ms == 42
        assert out.uptime_seconds == 3600
        assert out.bootid == "boot-abc"

    def test_upsert_overwrites(self, store):
        store.upsert(DeviceHealthRecord(
            device_id="cam-01",
            status=DeviceHealthStatus.ONLINE,
            latency_ms=10,
        ))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01",
            status=DeviceHealthStatus.UNREACHABLE,
            last_error="timed out",
            consecutive_failures=3,
        ))
        out = store.get("cam-01")
        assert out.status == DeviceHealthStatus.UNREACHABLE
        assert out.last_error == "timed out"
        assert out.consecutive_failures == 3
        # latency_ms reset to None on the new record.
        assert out.latency_ms is None

    def test_list_all_sorted(self, store):
        for did in ("c", "a", "b"):
            store.upsert(DeviceHealthRecord(
                device_id=did, status=DeviceHealthStatus.ONLINE
            ))
        result = [r.device_id for r in store.list_all()]
        assert result == ["a", "b", "c"]

    def test_delete(self, store):
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.ONLINE
        ))
        assert store.delete("cam-01") is True
        assert store.delete("cam-01") is False
        assert store.get("cam-01") is None


# ---------------------------------------------------------------------------
# Per-device probe — tier 2 (TCP fallback)
# ---------------------------------------------------------------------------


class TestProbeTcpFallback:
    @pytest.mark.asyncio
    async def test_tcp_connect_success_marks_online(self, monkeypatch):
        """No creds → TCP probe. Mock open_connection to succeed instantly."""
        from admz.fleet import health as h

        async def fake_open(host, port):
            class _W:
                def close(self): pass
                async def wait_closed(self): pass
            class _R: pass
            return _R(), _W()

        monkeypatch.setattr(asyncio, "open_connection", fake_open)

        rec = await probe_device(
            device_id="cam-01",
            device_info={"host": "192.0.2.1"},
            credentials=None,
        )
        assert rec.status == DeviceHealthStatus.ONLINE
        assert rec.latency_ms is not None
        assert rec.consecutive_failures == 0
        assert rec.last_seen_online is not None

    @pytest.mark.asyncio
    async def test_tcp_connect_timeout_marks_unreachable(self, monkeypatch):
        async def fake_open(host, port):
            raise asyncio.TimeoutError()
        monkeypatch.setattr(asyncio, "open_connection", fake_open)
        # Make wait_for surface the timeout immediately.
        rec = await probe_device(
            device_id="cam-01",
            device_info={"host": "192.0.2.1"},
            credentials=None,
            timeout_seconds=0.1,
        )
        assert rec.status == DeviceHealthStatus.UNREACHABLE
        assert "TCP connect" in rec.last_error
        assert rec.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_tcp_connect_refused_marks_unreachable(self, monkeypatch):
        async def fake_open(host, port):
            raise OSError("Connection refused")
        monkeypatch.setattr(asyncio, "open_connection", fake_open)
        rec = await probe_device(
            device_id="cam-01",
            device_info={"host": "192.0.2.1"},
            credentials=None,
            timeout_seconds=0.1,
        )
        assert rec.status == DeviceHealthStatus.UNREACHABLE

    @pytest.mark.asyncio
    async def test_no_host_marks_unreachable(self):
        rec = await probe_device(
            device_id="cam-01",
            device_info={},
            credentials=None,
        )
        assert rec.status == DeviceHealthStatus.UNREACHABLE
        assert "no host" in rec.last_error.lower()


# ---------------------------------------------------------------------------
# Per-device probe — tier 1 (authenticated systemReady)
# ---------------------------------------------------------------------------


class TestProbeAuthenticated:
    @pytest.mark.asyncio
    async def test_401_marks_auth_failed(self):
        catalog = MagicMock()
        op = MagicMock()
        op.to_executor_dict.return_value = {"id": "systemready.cgi:systemReady"}
        catalog.get_operation.return_value = op

        executor = MagicMock()
        result = MagicMock(success=False, status_code=401, error="HTTP 401")
        executor.execute = AsyncMock(return_value=result)

        rec = await probe_device(
            device_id="cam-01",
            device_info={"host": "192.0.2.1"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog,
            executor=executor,
        )
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert rec.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_systemready_success_populates_uptime_bootid(self):
        catalog = MagicMock()
        op = MagicMock()
        op.to_executor_dict.return_value = {"id": "systemready.cgi:systemReady"}
        catalog.get_operation.return_value = op

        executor = MagicMock()
        result = MagicMock(
            success=True,
            status_code=200,
            error=None,
            parsed_data={
                "data": {
                    "systemready": "yes",
                    "uptime": 3600,
                    "bootid": "boot-xyz",
                }
            },
        )
        executor.execute = AsyncMock(return_value=result)

        rec = await probe_device(
            device_id="cam-01",
            device_info={"host": "192.0.2.1"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog,
            executor=executor,
        )
        assert rec.status == DeviceHealthStatus.ONLINE
        assert rec.uptime_seconds == 3600
        assert rec.bootid == "boot-xyz"
        assert rec.consecutive_failures == 0
        assert rec.last_seen_online is not None

    @pytest.mark.asyncio
    async def test_probe_captures_firmware_facts(self):
        """The credential check fetches basicdeviceinfo; probe_device lifts
        model/serial/firmware off that response into observed_facts."""
        catalog = MagicMock()
        op = MagicMock()
        op.to_executor_dict.return_value = {"id": "x"}
        catalog.get_operation.return_value = op
        executor = MagicMock()
        result = MagicMock(
            success=True, status_code=200, error=None,
            parsed_data={"data": {"propertyList": {
                "ProdNbr": "AXIS P3245-V",
                "SerialNumber": "ACCC8E000001",
                "Version": "11.9.65",
            }}},
        )
        executor.execute = AsyncMock(return_value=result)
        with patch("admz.fleet.health._verify_credentials_enabled", return_value=True):
            rec = await probe_device(
                device_id="cam-01",
                device_info={"host": "192.0.2.1"},
                credentials={"username": "root", "password": "x"},
                catalog=catalog, executor=executor,
            )
        assert rec.status == DeviceHealthStatus.ONLINE
        assert rec.observed_facts is not None
        assert rec.observed_facts["firmware_version"] == "11.9.65"
        assert rec.observed_facts["model"] == "AXIS P3245-V"
        assert rec.observed_facts["serial_number"] == "ACCC8E000001"

    @pytest.mark.asyncio
    async def test_connect_timeout_in_systemready_marks_unreachable(self):
        catalog = MagicMock()
        op = MagicMock()
        op.to_executor_dict.return_value = {"id": "systemready.cgi:systemReady"}
        catalog.get_operation.return_value = op

        executor = MagicMock()
        result = MagicMock(
            success=False, status_code=None, error="Connection timeout to 192.0.2.1"
        )
        executor.execute = AsyncMock(return_value=result)

        rec = await probe_device(
            device_id="cam-01",
            device_info={"host": "192.0.2.1"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog,
            executor=executor,
        )
        assert rec.status == DeviceHealthStatus.UNREACHABLE
        assert "timeout" in rec.last_error.lower()


# ---------------------------------------------------------------------------
# Monitor: sweep_once iterates the registry
# ---------------------------------------------------------------------------


class TestMonitorSweep:
    @pytest.mark.asyncio
    async def test_sweep_visits_every_device(self, tmp_path):
        registry = MagicMock()
        registry.list_devices.return_value = [
            {"device_id": "a", "host": "192.0.2.1"},
            {"device_id": "b", "host": "192.0.2.2"},
            {"device_id": "c", "host": "192.0.2.3"},
        ]
        registry.get_credentials.side_effect = Exception("no creds")

        store = DeviceHealthStore(str(tmp_path / "admz.db"))
        monitor = HealthMonitor(
            registry=registry,
            catalog=None,
            executors={},
            store=store,
        )

        async def fake_probe(*, device_id, **kwargs):
            return DeviceHealthRecord(
                device_id=device_id,
                status=DeviceHealthStatus.ONLINE,
                last_check=time.time(),
                last_seen_online=time.time(),
                latency_ms=5,
            )

        with patch("admz.fleet.health.probe_device", side_effect=fake_probe):
            n = await monitor.sweep_once()

        assert n == 3
        for did in ("a", "b", "c"):
            rec = store.get(did)
            assert rec is not None
            assert rec.status == DeviceHealthStatus.ONLINE

    @pytest.mark.asyncio
    async def test_sweep_flushes_changed_facts_to_registry(self, tmp_path):
        """When a probe surfaces new firmware/model, the sweep writes the
        changed subset back to the device registry (no extra probe)."""
        registry = MagicMock()
        registry.list_devices.return_value = [
            {"device_id": "cam-01", "host": "192.0.2.1",
             "firmware_version": "11.0.0"},  # stale; no model yet
        ]
        registry.get_credentials.return_value = {"username": "root", "password": "x"}
        store = DeviceHealthStore(str(tmp_path / "admz.db"))
        monitor = HealthMonitor(
            registry=registry, catalog=MagicMock(),
            executors={"vapix": MagicMock()}, store=store,
        )

        async def fake_probe(*, device_id, **kwargs):
            return DeviceHealthRecord(
                device_id=device_id, status=DeviceHealthStatus.ONLINE,
                last_check=time.time(), last_seen_online=time.time(),
                observed_facts={"firmware_version": "11.9.65",
                                "model": "AXIS P3245-V"},
            )

        with patch("admz.fleet.health.probe_device", side_effect=fake_probe):
            await monitor.sweep_once()

        registry.update_device_info.assert_called_once()
        did_arg, facts_arg = registry.update_device_info.call_args.args
        assert did_arg == "cam-01"
        assert facts_arg["firmware_version"] == "11.9.65"  # changed
        assert facts_arg["model"] == "AXIS P3245-V"        # was missing

    @pytest.mark.asyncio
    async def test_sweep_skips_unchanged_facts(self, tmp_path):
        """No registry write when the probed facts already match the record."""
        registry = MagicMock()
        registry.list_devices.return_value = [
            {"device_id": "cam-01", "host": "192.0.2.1",
             "firmware_version": "11.9.65", "model": "AXIS P3245-V"},
        ]
        registry.get_credentials.return_value = {"username": "root", "password": "x"}
        store = DeviceHealthStore(str(tmp_path / "admz.db"))
        monitor = HealthMonitor(
            registry=registry, catalog=MagicMock(),
            executors={"vapix": MagicMock()}, store=store,
        )

        async def fake_probe(*, device_id, **kwargs):
            return DeviceHealthRecord(
                device_id=device_id, status=DeviceHealthStatus.ONLINE,
                last_check=time.time(), last_seen_online=time.time(),
                observed_facts={"firmware_version": "11.9.65",
                                "model": "AXIS P3245-V"},
            )

        with patch("admz.fleet.health.probe_device", side_effect=fake_probe):
            await monitor.sweep_once()

        registry.update_device_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_sweep_preserves_last_seen_online_after_failure(self, tmp_path):
        """A device that was online before and is now unreachable should
        keep last_seen_online intact + bump consecutive_failures."""
        registry = MagicMock()
        registry.list_devices.return_value = [
            {"device_id": "a", "host": "192.0.2.1"},
        ]
        registry.get_credentials.side_effect = Exception("no creds")

        store = DeviceHealthStore(str(tmp_path / "admz.db"))
        # Seed with a successful prior check
        earlier = time.time() - 300
        store.upsert(DeviceHealthRecord(
            device_id="a",
            status=DeviceHealthStatus.ONLINE,
            last_check=earlier,
            last_seen_online=earlier,
            latency_ms=10,
            consecutive_failures=0,
        ))

        monitor = HealthMonitor(
            registry=registry, catalog=None, executors={}, store=store
        )

        async def fake_probe(*, device_id, **kwargs):
            return DeviceHealthRecord(
                device_id=device_id,
                status=DeviceHealthStatus.UNREACHABLE,
                last_check=time.time(),
                last_error="timed out",
                consecutive_failures=1,
            )

        with patch("admz.fleet.health.probe_device", side_effect=fake_probe):
            await monitor.sweep_once()

        rec = store.get("a")
        assert rec.status == DeviceHealthStatus.UNREACHABLE
        # last_seen_online preserved from the prior successful check.
        assert rec.last_seen_online == pytest.approx(earlier)
        # consecutive_failures incremented from 0 to 1.
        assert rec.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_sweep_empty_fleet_returns_zero(self, tmp_path):
        registry = MagicMock()
        registry.list_devices.return_value = []
        store = DeviceHealthStore(str(tmp_path / "admz.db"))
        monitor = HealthMonitor(
            registry=registry, catalog=None, executors={}, store=store
        )
        n = await monitor.sweep_once()
        assert n == 0


# ---------------------------------------------------------------------------
# Opt-in via fleet flag
# ---------------------------------------------------------------------------


class TestMonitorOptIn:
    @pytest.mark.asyncio
    async def test_start_noop_when_flag_off(self, tmp_path, monkeypatch):
        from admz import fleet_settings as fs_module
        from admz.fleet import health as h_module
        fresh_fs = fs_module.FleetSettings(str(tmp_path / "admz.db"))
        monkeypatch.setattr(fs_module, "fleet_settings", fresh_fs)
        monkeypatch.setattr(h_module, "_fs_module", fs_module)

        registry = MagicMock()
        monitor = HealthMonitor(
            registry=registry,
            catalog=None,
            executors={},
            store=DeviceHealthStore(str(tmp_path / "h.db")),
        )

        await monitor.start()
        assert monitor._task is None
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_start_spins_task_when_flag_on(self, tmp_path, monkeypatch):
        from admz import fleet_settings as fs_module
        from admz.fleet import health as h_module
        fresh_fs = fs_module.FleetSettings(str(tmp_path / "admz.db"))
        fresh_fs.set("health_monitor_enabled", "true")
        # Also set a long interval so the loop doesn't churn during the test.
        fresh_fs.set("health_check_interval_seconds", "300")
        monkeypatch.setattr(fs_module, "fleet_settings", fresh_fs)
        monkeypatch.setattr(h_module, "_fs_module", fs_module)

        registry = MagicMock()
        registry.list_devices.return_value = []

        monitor = HealthMonitor(
            registry=registry,
            catalog=None,
            executors={},
            store=DeviceHealthStore(str(tmp_path / "h.db")),
        )
        await monitor.start()
        try:
            assert monitor._running is True
            assert monitor._task is not None
        finally:
            await monitor.stop()
        assert monitor._running is False


# ---------------------------------------------------------------------------
# Protected fleet keys
# ---------------------------------------------------------------------------


class TestProtectedKeys:
    def test_health_keys_protected(self):
        from admz.api.confirm_store import PROTECTED_SETTING_KEYS
        for k in (
            "health_monitor_enabled",
            "health_check_interval_seconds",
            "health_check_timeout_seconds",
        ):
            assert k in PROTECTED_SETTING_KEYS, f"{k} should be protected"
