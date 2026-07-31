"""Tests for the device health monitor: store + per-device probe + monitor loop.

The monitor is opt-in via the ``health_monitor_enabled`` fleet
setting. Tests below isolate the store (SQLite tmp), mock the
network probe, and exercise both the storage round-trip and the
monitor's per-device dispatch.
"""

import asyncio
import time
from types import SimpleNamespace
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
    async def test_needsetup_marks_needs_setup_not_auth_failed(self):
        """A factory-defaulted device answers systemready (200) with
        needsetup=yes — that's NEEDS_SETUP (recoverable), not AUTH_FAILED."""
        catalog = MagicMock()
        op = MagicMock()
        op.to_executor_dict.return_value = {"id": "systemready.cgi:systemReady"}
        catalog.get_operation.return_value = op

        executor = MagicMock()
        result = MagicMock(
            success=True, status_code=200,
            parsed_data={"systemready": "yes", "needsetup": "yes",
                         "uptime": 100, "bootid": "boot-abc"},
        )
        executor.execute = AsyncMock(return_value=result)

        rec = await probe_device(
            device_id="cam-01",
            device_info={"host": "192.0.2.1"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog,
            executor=executor,
        )
        assert rec.status == DeviceHealthStatus.NEEDS_SETUP
        assert rec.last_seen_online is not None          # reachable
        assert "needsetup" in rec.last_error.lower()
        assert rec.bootid == "boot-abc"

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
# GH #138 — reachability vs. API capability
# ---------------------------------------------------------------------------


def _vapix_catalog_and_executor(result):
    """A catalog + executor whose every op returns ``result``."""
    catalog = MagicMock()
    op = MagicMock()
    op.to_executor_dict.return_value = {"id": "systemready.cgi:systemReady"}
    catalog.get_operation.return_value = op
    executor = MagicMock()
    executor.execute = AsyncMock(return_value=result)
    return catalog, executor


class TestProbePort:
    """The reachability probe knocks on the port ADMZ actually talks to."""

    def test_defaults_to_80(self):
        from admz.fleet.health import _probe_port
        assert _probe_port({"host": "192.0.2.1"}) == 80

    def test_https_scheme_uses_443(self):
        from admz.fleet.health import _probe_port
        assert _probe_port({"auth_info": {"scheme": "https"}}) == 443

    def test_explicit_port_wins(self):
        from admz.fleet.health import _probe_port
        assert _probe_port({"port": 8443, "auth_info": {"scheme": "https"}}) == 8443

    def test_junk_port_falls_back(self):
        from admz.fleet.health import _probe_port
        assert _probe_port({"port": "not-a-port"}) == 80


class TestReachableNoApi:
    """A device that answers but doesn't speak VAPIX is UP, not unreachable.

    The AXIS T8516 PoE switch answers HTTP in ~80 ms with an HTML login page.
    The old code recorded that as ``unreachable`` *with a measured latency* —
    a self-contradicting verdict that logged 10,795 false failures.
    """

    @pytest.mark.asyncio
    async def test_parse_failure_with_tcp_up_is_reachable_no_api(self, monkeypatch):
        """The T8516 case: unparsable body + host answers TCP."""
        catalog, executor = _vapix_catalog_and_executor(
            MagicMock(
                success=False, status_code=200,
                error="Failed to parse JSON response: Expecting value: line 1 column 1 (char 0)",
            )
        )
        monkeypatch.setattr(
            "admz.fleet.health._tcp_probe", AsyncMock(return_value=3)
        )

        rec = await probe_device(
            device_id="t8516",
            device_info={"host": "192.0.2.124"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog,
            executor=executor,
        )
        assert rec.status == DeviceHealthStatus.REACHABLE_NO_API
        assert rec.status != DeviceHealthStatus.UNREACHABLE
        # It is up: the reachability clock advances and nothing is counted
        # as a failure.
        assert rec.last_seen_online is not None
        assert rec.consecutive_failures == 0
        assert rec.latency_ms is not None
        assert "parse" in rec.last_error.lower()

    @pytest.mark.asyncio
    async def test_unexpected_status_with_tcp_up_is_reachable_no_api(self, monkeypatch):
        """An unexpected-but-valid HTTP status also proves the host is up."""
        catalog, executor = _vapix_catalog_and_executor(
            MagicMock(success=False, status_code=404, error="HTTP 404 Not Found")
        )
        monkeypatch.setattr(
            "admz.fleet.health._tcp_probe", AsyncMock(return_value=7)
        )
        rec = await probe_device(
            device_id="switch",
            device_info={"host": "192.0.2.124"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog, executor=executor,
        )
        assert rec.status == DeviceHealthStatus.REACHABLE_NO_API

    @pytest.mark.asyncio
    async def test_parse_failure_with_tcp_down_is_unreachable(self, monkeypatch):
        """Classification is evidence-based: no TCP connect → genuinely down."""
        catalog, executor = _vapix_catalog_and_executor(
            MagicMock(success=False, status_code=None,
                      error="Failed to parse JSON response")
        )
        monkeypatch.setattr(
            "admz.fleet.health._tcp_probe", AsyncMock(return_value=None)
        )
        rec = await probe_device(
            device_id="ghost",
            device_info={"host": "192.0.2.9"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog, executor=executor,
        )
        assert rec.status == DeviceHealthStatus.UNREACHABLE
        assert rec.consecutive_failures == 1
        assert rec.last_seen_online is None

    @pytest.mark.asyncio
    async def test_connect_failure_still_unreachable_without_probing(self, monkeypatch):
        """A connect-class error is already conclusive — don't spend a probe."""
        catalog, executor = _vapix_catalog_and_executor(
            MagicMock(success=False, status_code=None,
                      error="Connection refused by 192.0.2.9")
        )
        tcp = AsyncMock(return_value=5)
        monkeypatch.setattr("admz.fleet.health._tcp_probe", tcp)
        rec = await probe_device(
            device_id="dead",
            device_info={"host": "192.0.2.9"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog, executor=executor,
        )
        assert rec.status == DeviceHealthStatus.UNREACHABLE
        assert rec.latency_ms is None
        tcp.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_401_still_auth_failed(self, monkeypatch):
        """Regression: the auth verdict is decided before reachability."""
        catalog, executor = _vapix_catalog_and_executor(
            MagicMock(success=False, status_code=401, error="HTTP 401")
        )
        tcp = AsyncMock(return_value=5)
        monkeypatch.setattr("admz.fleet.health._tcp_probe", tcp)
        rec = await probe_device(
            device_id="cam-01",
            device_info={"host": "192.0.2.1"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog, executor=executor,
        )
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        tcp.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_probe_uses_the_devices_effective_port(self, monkeypatch):
        """An HTTPS-only device is confirmed on 443, not 80."""
        catalog, executor = _vapix_catalog_and_executor(
            MagicMock(success=False, status_code=200, error="unexpected content type")
        )
        tcp = AsyncMock(return_value=4)
        monkeypatch.setattr("admz.fleet.health._tcp_probe", tcp)
        await probe_device(
            device_id="cam-01",
            device_info={"host": "192.0.2.1", "auth_info": {"scheme": "https"}},
            credentials={"username": "root", "password": "x"},
            catalog=catalog, executor=executor,
        )
        assert tcp.await_args.args[1] == 443

    def test_store_round_trip(self, store):
        """The new status survives the SQLite round-trip."""
        store.upsert(DeviceHealthRecord(
            device_id="t8516",
            status=DeviceHealthStatus.REACHABLE_NO_API,
            last_check=1234567890.0,
            last_seen_online=1234567890.0,
            latency_ms=77,
            last_error="Failed to parse JSON response",
        ))
        out = store.get("t8516")
        assert out.status == DeviceHealthStatus.REACHABLE_NO_API
        assert out.latency_ms == 77
        assert out.to_dict()["status"] == "reachable_no_api"
        assert [r.status for r in store.list_all()] == [
            DeviceHealthStatus.REACHABLE_NO_API
        ]

    def test_does_not_fire_detection_tasks(self):
        """A device ADMZ can't speak to has NOT proven itself online, so it
        must not satisfy the ``on_online`` trigger — while ``needs_setup``
        deferred recovery keeps working exactly as before."""
        from admz.tasks.store import EVENT_NEEDS_SETUP, EVENT_ONLINE, event_for_status

        assert event_for_status("reachable_no_api") is None
        assert event_for_status("needs_setup") == EVENT_NEEDS_SETUP
        assert event_for_status("online") == EVENT_ONLINE

    @pytest.mark.asyncio
    async def test_sweep_does_not_accumulate_failures(self, tmp_path):
        """A stable "can't speak VAPIX" state must not grow a failure counter
        (the 10,795-strong counter of GH #138) and must advance the
        reachability clock."""
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "t8516", "host": "192.0.2.124"}]
        registry.get_credentials.return_value = {"username": "root", "password": "x"}
        store = DeviceHealthStore(str(tmp_path / "admz.db"))
        earlier = time.time() - 3600
        store.upsert(DeviceHealthRecord(
            device_id="t8516", status=DeviceHealthStatus.REACHABLE_NO_API,
            last_check=earlier, last_seen_online=earlier, consecutive_failures=42,
        ))
        monitor = HealthMonitor(
            registry=registry, catalog=MagicMock(),
            executors={"vapix": MagicMock()}, store=store,
        )

        async def fake_probe(*, device_id, **kwargs):
            return DeviceHealthRecord(
                device_id=device_id, status=DeviceHealthStatus.REACHABLE_NO_API,
                last_check=time.time(), last_seen_online=time.time(),
                latency_ms=77, consecutive_failures=0,
            )

        with patch("admz.fleet.health.probe_device", side_effect=fake_probe):
            await monitor.sweep_once()

        rec = store.get("t8516")
        assert rec.status == DeviceHealthStatus.REACHABLE_NO_API
        assert rec.consecutive_failures == 0        # reset, not 43
        assert rec.last_seen_online > earlier       # clock advanced

    @pytest.mark.asyncio
    async def test_sweep_keeps_prior_clock_when_probe_proves_nothing(self, tmp_path):
        """A fresh stamp is never overwritten by a stale one — and a probe
        that establishes nothing still inherits the previous value."""
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "a", "host": "192.0.2.1"}]
        registry.get_credentials.side_effect = Exception("no creds")
        store = DeviceHealthStore(str(tmp_path / "admz.db"))
        earlier = time.time() - 300
        store.upsert(DeviceHealthRecord(
            device_id="a", status=DeviceHealthStatus.ONLINE,
            last_check=earlier, last_seen_online=earlier,
        ))
        monitor = HealthMonitor(
            registry=registry, catalog=None, executors={}, store=store
        )

        async def fake_probe(*, device_id, **kwargs):
            return DeviceHealthRecord(
                device_id=device_id, status=DeviceHealthStatus.UNREACHABLE,
                last_check=time.time(), last_error="down", consecutive_failures=1,
            )

        with patch("admz.fleet.health.probe_device", side_effect=fake_probe):
            await monitor.sweep_once()

        assert store.get("a").last_seen_online == pytest.approx(earlier)


class TestReachableNoApiSurfaces:
    """The new status has to be legible everywhere health is read."""

    @pytest.mark.asyncio
    async def test_rest_fleet_health_counts_and_entry(self, store, monkeypatch):
        from admz.api.routes import health as health_routes

        store.upsert(DeviceHealthRecord(
            device_id="t8516", status=DeviceHealthStatus.REACHABLE_NO_API,
            latency_ms=77,
        ))
        monkeypatch.setattr(health_routes, "device_health_store", store)
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "t8516"}]

        body = await health_routes.get_fleet_health(registry=registry)
        assert body["counts"]["reachable_no_api"] == 1
        assert body["counts"]["unreachable"] == 0
        assert body["devices"][0]["status"] == "reachable_no_api"

    @pytest.mark.asyncio
    async def test_rest_device_health(self, store, monkeypatch):
        from admz.api.routes import health as health_routes

        store.upsert(DeviceHealthRecord(
            device_id="t8516", status=DeviceHealthStatus.REACHABLE_NO_API,
        ))
        monkeypatch.setattr(health_routes, "device_health_store", store)
        registry = MagicMock()
        registry.device_exists.return_value = True

        body = await health_routes.get_device_health("t8516", registry=registry)
        assert body["status"] == "reachable_no_api"

    @pytest.mark.asyncio
    async def test_mcp_fleet_health_counts(self, store, monkeypatch):
        from admz.fleet import health as health_mod
        from admz.mcp.server import ADMZMCPServer

        store.upsert(DeviceHealthRecord(
            device_id="t8516", status=DeviceHealthStatus.REACHABLE_NO_API,
        ))
        monkeypatch.setattr(health_mod, "device_health_store", store)
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "t8516"}]
        registry.device_exists.return_value = True

        srv = SimpleNamespace(registry=registry)
        fleet = await ADMZMCPServer._get_fleet_health(srv)
        assert fleet["counts"]["reachable_no_api"] == 1
        one = await ADMZMCPServer._get_device_health(srv, "t8516")
        assert one["status"] == "reachable_no_api"

    def test_ui_renders_it_amber_and_labelled(self):
        """Not green (it isn't manageable), not red (it isn't an outage)."""
        from admz.api.templating import health_label, health_sem

        assert health_sem("reachable_no_api") == "amber"
        assert health_sem("unreachable") == "red"
        assert health_sem("online") == "green"
        assert health_label("reachable_no_api") == "Reachable, no API"
        # The raw (underscored) store values must all resolve — these reach the
        # filters straight from DeviceHealthStatus.
        for value in ("auth_failed", "needs_setup"):
            assert health_sem(value) == "amber"
            assert health_label(value) != "Unknown"

    def test_client_side_health_maps_know_it(self):
        """The roster + device page colour health in JS, from their own maps —
        a status missing there renders as a bogus "Unknown"."""
        from pathlib import Path

        import admz.api as api_pkg

        templates = Path(api_pkg.__file__).parent / "templates"
        for name in ("index.html", "device_detail.html"):
            text = (templates / name).read_text(encoding="utf-8")
            assert "reachable_no_api" in text, f"{name} can't render the status"
            assert "Reachable, no API" in text


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
