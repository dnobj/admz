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
    CORROBORATION_OP,
    DeviceHealthRecord,
    DeviceHealthStatus,
    DeviceHealthStore,
    HealthMonitor,
    SYSTEMREADY_OP,
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
            # `error` MUST be set: an unset attribute on a MagicMock is a child
            # mock whose str() embeds `id='<address>'`, and probe_device reads
            # this field. That is what made this test flaky (#291). None is what
            # a real StepResult carries here (executor/models.py:38).
            error=None,
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
    async def test_parse_failure_with_tcp_up_and_no_legacy_read_is_reachable_no_api(
        self, monkeypatch
    ):
        """Unparsable body, host answers TCP, and the legacy CGI read ALSO
        fails — the genuine "cannot manage it" case.

        This used to be labelled "the T8516 case" and was not: on the real
        T8516 `param.cgi` answers, which is why #357 reclassified it. The
        shared harness here returns the same failure for every op, so both
        surfaces fail and `reachable_no_api` remains correct — that is what
        this test now pins.
        """
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


def _per_op_catalog_and_executor(results_by_op):
    """Catalog + executor that returns a DIFFERENT result per operation id.

    The shared harness above answers every op identically, which cannot
    express the shape #357 is about: one surface failing while another
    answers. That uniformity is precisely why the T8516 misclassification had
    no failing test.
    """
    catalog = MagicMock()

    def _get_operation(family, op_id):
        op = MagicMock()
        op.to_executor_dict.return_value = {"id": op_id}
        op._op_id = op_id
        return op

    catalog.get_operation.side_effect = _get_operation

    async def _execute(op_dict, device_info, credentials, params):
        return results_by_op[op_dict["id"]]

    executor = MagicMock()
    executor.execute = AsyncMock(side_effect=_execute)
    return catalog, executor


class TestLimitedApi:
    """GH #357 — a device ADMZ can actually read is not 'no API'.

    The T8516 answered `param.cgi` on every audit cycle (four config facets,
    245 tracked drift alerts) while being reported as unmanageable, because
    one JSON-RPC probe's parse failure stood in for "any API". Worse, the
    status is in ``_STABLE_STATUSES`` — by design it never escalates — and it
    never cleared either, so the device sat in *needs attention* permanently
    with `consecutive_failures = 0`. A device parked there can no longer
    signal a real fault.
    """

    def _t8516_ops(self):
        return {
            SYSTEMREADY_OP: MagicMock(
                success=False, status_code=200,
                error=("Failed to parse JSON response: Expecting value: "
                       "line 1 column 1 (char 0)"),
            ),
            # `parsed_data`, not `data` — the field production actually reads.
            # The first draft of this test set `data`, which meant it passed
            # only because the code trusted the 2xx; the review caught that the
            # mock did not match the type it stands in for.
            CORROBORATION_OP: MagicMock(
                success=True, status_code=200, error=None,
                parsed_data="root.Brand.Brand=AXIS\nroot.Brand.ProdNbr=T8516",
            ),
        }

    @pytest.mark.asyncio
    async def test_json_probe_fails_but_legacy_read_answers(self, monkeypatch):
        """The real T8516 shape, end to end."""
        catalog, executor = _per_op_catalog_and_executor(self._t8516_ops())
        monkeypatch.setattr(
            "admz.fleet.health._tcp_probe", AsyncMock(return_value=3)
        )

        rec = await probe_device(
            device_id="t8516",
            device_info={"host": "192.0.2.124"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog, executor=executor,
        )

        assert rec.status == DeviceHealthStatus.LIMITED_API
        assert rec.status != DeviceHealthStatus.REACHABLE_NO_API
        assert rec.last_seen_online is not None
        assert rec.consecutive_failures == 0
        # The error field still says what could not be read — the operator
        # asking "can I push config to this?" deserves the honest answer.
        assert CORROBORATION_OP in rec.last_error

    @pytest.mark.asyncio
    async def test_html_body_at_200_does_not_count_as_a_managed_read(
        self, monkeypatch
    ):
        """A 2xx is not evidence — this is the original bug, inverted.

        For text-format ops the executor sets ``success=True`` on any non-error
        2xx and passes the raw body through, so a device serving an HTML login
        page from ``param.cgi`` produces a "successful" result with no
        parameters in it. Promoting that to ``limited_api`` would be the same
        trust-the-shape error that classified the T8516 wrongly to begin with.
        """
        catalog, executor = _per_op_catalog_and_executor({
            SYSTEMREADY_OP: MagicMock(
                success=False, status_code=200,
                error="Failed to parse JSON response: Expecting value",
            ),
            CORROBORATION_OP: MagicMock(
                success=True, status_code=200, error=None,
                parsed_data="<html><body>Please log in</body></html>",
            ),
        })
        monkeypatch.setattr(
            "admz.fleet.health._tcp_probe", AsyncMock(return_value=4)
        )

        rec = await probe_device(
            device_id="html-switch",
            device_info={"host": "192.0.2.200"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog, executor=executor,
        )
        assert rec.status == DeviceHealthStatus.REACHABLE_NO_API

    @pytest.mark.asyncio
    async def test_empty_body_at_200_does_not_count_either(self, monkeypatch):
        catalog, executor = _per_op_catalog_and_executor({
            SYSTEMREADY_OP: MagicMock(
                success=False, status_code=200, error="parse failure",
            ),
            CORROBORATION_OP: MagicMock(
                success=True, status_code=200, error=None, parsed_data="",
            ),
        })
        monkeypatch.setattr(
            "admz.fleet.health._tcp_probe", AsyncMock(return_value=4)
        )
        rec = await probe_device(
            device_id="empty", device_info={"host": "192.0.2.201"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog, executor=executor,
        )
        assert rec.status == DeviceHealthStatus.REACHABLE_NO_API

    def test_param_data_predicate(self):
        """The predicate itself, since it is what stands between a real read
        and a login page."""
        from admz.fleet.health import _looks_like_param_data

        # `error=None` on every one of these: the repo's mock-faithfulness
        # lint (#291) requires it wherever a result-shaped mock is built, and
        # it is right to be unconditional — `StepResult.error` is always
        # present, and a MagicMock without it hands back a child mock.
        def _r(parsed):
            return MagicMock(parsed_data=parsed, error=None)

        assert _looks_like_param_data(
            _r("root.Brand.Brand=AXIS\nroot.Brand.ProdNbr=T8516")
        )
        assert _looks_like_param_data(_r({"root.Brand": "AXIS"}))
        assert not _looks_like_param_data(_r("<html>hi</html>"))
        assert not _looks_like_param_data(_r("   "))
        assert not _looks_like_param_data(_r(None))
        assert not _looks_like_param_data(_r({}))
        # Prose that happens to contain '=' is not parameter data.
        assert not _looks_like_param_data(_r("Error: session = expired"))

    def test_consumers_treat_limited_api_as_reachable(self):
        """A new enum member leaks past its own tests unless the things that
        *branch* on it are updated too — found in review, so pinned here.

        Each of these compared against the literal ``"online"``, so a
        `limited_api` device would have counted as offline in a demo checklist,
        never satisfied an `on_online` task trigger, and shown as a permanent
        site issue.
        """
        from admz.demos.readiness import _HEALTHY
        from admz.tasks.store import EVENT_ONLINE, event_for_status

        assert "limited_api" in _HEALTHY
        assert event_for_status("limited_api") == EVENT_ONLINE

    @pytest.mark.asyncio
    async def test_limited_api_is_a_settled_answer(self):
        """It must not accumulate failures — the #138 lesson still applies."""
        from admz.fleet.health import _STABLE_STATUSES
        assert DeviceHealthStatus.LIMITED_API in _STABLE_STATUSES

    def test_limited_api_is_not_an_attention_state(self):
        """The half that actually clears the T8516 from the operator's queue.

        `_STABLE_STATUSES` and the UI bucket are two different questions asked
        of this enum (#357's follow-up), and both were individually right while
        the device stayed parked. This pins the *second* one.
        """
        import re
        from pathlib import Path

        index = Path("admz/api/templates/index.html").read_text(
            encoding="utf-8", errors="replace")
        entry = re.search(r"limited_api:\s*\{[^}]*\}", index)
        assert entry, "limited_api missing from the dashboard HEALTH map"
        assert "bucket: 'online'" in entry.group(0)
        assert "attention" not in entry.group(0)

    def test_reachable_no_api_remains_an_attention_state(self):
        """The fix must not sweep the genuine case under the rug too."""
        import re
        from pathlib import Path

        index = Path("admz/api/templates/index.html").read_text(
            encoding="utf-8", errors="replace")
        entry = re.search(r"reachable_no_api:\s*\{[^}]*\}", index)
        assert entry and "bucket: 'attention'" in entry.group(0)

    def test_every_status_has_a_label_and_a_colour(self):
        """Adding an enum member without teaching the renderers is how a
        status ends up rendering as a raw string in the UI."""
        from admz.api.templating import HEALTH_LABEL, HEALTH_SEM

        for status in DeviceHealthStatus:
            assert status.value in HEALTH_SEM, f"{status.value} has no colour"
            assert status.value in HEALTH_LABEL, f"{status.value} has no label"

    @pytest.mark.asyncio
    async def test_legacy_read_is_only_attempted_after_a_failure(self, monkeypatch):
        """No extra request on a healthy sweep — the probe runs only on a path
        that has already failed."""
        catalog, executor = _per_op_catalog_and_executor({
            SYSTEMREADY_OP: MagicMock(
                success=True, status_code=200, error=None,
                data={"uptime": 1234, "bootid": "abc"},
            ),
        })
        monkeypatch.setattr(
            "admz.fleet.health._tcp_probe", AsyncMock(return_value=1)
        )

        rec = await probe_device(
            device_id="healthy",
            device_info={"host": "192.0.2.10"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog, executor=executor,
        )

        assert rec.status == DeviceHealthStatus.ONLINE
        called = [c.args[0]["id"] for c in executor.execute.call_args_list]
        assert CORROBORATION_OP not in called, (
            f"healthy sweep made an extra call: {called}"
        )


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
        """Exactly these ``health_*`` keys are protected — no more, no fewer.

        Was a loop over a literal tuple asserting membership, the same shape
        that let GH #152 through: growth in the real key set could only ever be
        missed. Recast as an equality lock over the ``health_*`` namespace so
        adding or dropping a protected health key fails here and forces a
        conscious update.

        The residual gap this used to record is **closed** (ADR-0053, #212). A
        new health setting added to ``admz/fleet/health.py`` as an inline
        literal now fails ``tests/test_setting_policy.py`` until it is
        declared, and it is protected by default in the meantime. That is also
        how ``health_verify_credentials`` — #168, absent from this lock until
        now, and the key whose whole purpose is to stop the credential check
        being enforced — joined the set.
        """
        from admz.api.confirm_store import PROTECTED_SETTING_KEYS

        protected_health_keys = {
            k for k in PROTECTED_SETTING_KEYS if k.startswith("health_")
        }
        # Exact equality on purpose. Adding or dropping a protected health key
        # must fail here and force a conscious update; loosening this to a
        # superset check would make it pass forever, which is the defect #176
        # found in the test that was supposed to catch #152.
        assert protected_health_keys == {
            "health_monitor_enabled",
            "health_check_interval_seconds",
            "health_check_timeout_seconds",
            "health_verify_credentials",
        }


class TestDeferredActionAuditRecordsPasswordSource:
    """GH #326. A fired reprovision creates an admin credential on a device,
    and the audit row could not say which mode produced it — `_run_reprovision`
    received `password_source` from `provision_factory_default` and dropped it,
    and `_run_pending` discarded the handler's return dict entirely.

    That matters because of #326's phantom-provision gap: when an on-path
    responder answers instead of the real device, ADMZ's registry believes it
    holds a working credential it never set. An operator looking at a suspect
    provision needs to know what was actually set; the alternative is inferring
    it from whichever code path happened to be live at the time.
    """

    def test_the_handler_carries_the_source_forward(self, monkeypatch):
        import asyncio
        from types import SimpleNamespace

        from admz.tasks import handlers as h

        async def fake_provision(*a, **kw):
            return {"success": True, "password_source": "generated"}

        import admz.provisioning as prov
        monkeypatch.setattr(prov, "provision_factory_default", fake_provision)

        task = SimpleNamespace(device_id="cam-01", device_ids=None,
                               action_params={}, action_type="reprovision")
        ctx = SimpleNamespace(
            registry=SimpleNamespace(
                get_device_info=lambda d: {"host": "192.0.2.1"}),
            catalog=None, executors={})
        out = asyncio.new_event_loop().run_until_complete(
            h.get_task_handler("reprovision")(task, ctx))
        assert out["password_source"] == "generated"

    def test_the_audit_row_carries_it(self):
        """The other half — the handler's return used to be thrown away."""
        import inspect
        from admz.fleet import health

        src = inspect.getsource(health.HealthMonitor)
        assert "outcome = await execute_task_action(task)" in src

    def test_only_allow_listed_keys_reach_the_row(self):
        """An allow-list, not a filter. A handler that starts returning
        something sensitive must not have it copied into an audit row by
        default — the row records attribution, never a second copy of a
        secret."""
        from admz.fleet.health import _AUDITABLE_OUTCOME_KEYS

        assert _AUDITABLE_OUTCOME_KEYS == ("password_source",)
        # Substring matching is the wrong test here and my first attempt used
        # it: "password" is a substring of "password_source", so it failed on
        # a key that is perfectly safe. The real property is that no key IS a
        # secret — `password_source` names a mode, `password` would be one.
        assert not ({"password", "secret", "token", "credential", "pwd"}
                    & set(_AUDITABLE_OUTCOME_KEYS))

    def test_the_source_values_are_modes_not_secrets(self):
        """`password_source` is one of three mode names. Pinned so a future
        change that puts the password itself in this field fails here."""
        import inspect

        from admz import provisioning
        src = inspect.getsource(provisioning)
        for mode in ('"provided"', '"fleet_default"', '"generated"'):
            assert mode in src
