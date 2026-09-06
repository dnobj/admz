"""ADR-0064 slice A — a device ADMZ cannot authenticate to is never `online`.

#443: an A1210 registered without credentials read `online` on every surface
for seven hours. The sweep's missing-credentials lookup fell back to a TCP
connect, which filed `online`. Now it is `no_credentials`: settled, amber, in
the attention bucket, stamping the reachability clock, never firing
`on_online` — and every consumer of the enum knows it.

The predicate's three edges, decided in the ADR and pinned here: absence is
what the registry *says*, never what a lookup *fails* to say; only the
`default` account counts; a factory-default unit is `needs_setup`, because the
credential-less tier asks `systemready` unauthenticated first.
"""

import re
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import admz.api as api_pkg
from admz.exceptions import AccountNotFoundError, DeviceNotFoundError
from admz.fleet.health import (
    _STABLE_STATUSES,
    DeviceHealthRecord,
    DeviceHealthStatus,
    DeviceHealthStore,
    HealthMonitor,
    probe_device,
)

TEMPLATES = Path(api_pkg.__file__).parent / "templates"
SYSTEMREADY_OP = "systemready.cgi:systemReady"


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setattr("admz.fleet.health._tcp_probe", AsyncMock(return_value=3))
    return tmp_path


def _catalog_and_executor(systemready_result):
    """A catalog that resolves systemready and an executor answering it,
    recording (op id, credentials) for every call."""
    catalog = MagicMock()

    def _get_operation(family, op_id):
        op = MagicMock()
        op.to_executor_dict.return_value = {"id": op_id}
        return op

    catalog.get_operation.side_effect = _get_operation
    calls = []

    async def _execute(op_dict, device_info, credentials, params):
        calls.append((op_dict["id"], dict(credentials or {})))
        return systemready_result

    executor = MagicMock()
    executor.execute = AsyncMock(side_effect=_execute)
    return catalog, executor, calls


def _systemready(needsetup):
    return MagicMock(
        success=True, status_code=200, error=None,
        parsed_data={"data": {"systemready": "yes",
                              "needsetup": "yes" if needsetup else "no",
                              "uptime": "120", "bootid": "b7"}},
    )


async def _probe(credentials, catalog=None, executor=None):
    return await probe_device(
        device_id="a1210", device_info={"host": "192.0.2.10"},
        credentials=credentials, catalog=catalog, executor=executor,
    )


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------

class TestTheVerdict:
    @pytest.mark.asyncio
    async def test_no_credentials_and_host_up_is_no_credentials(self, isolated):
        rec = await _probe(None)
        assert rec.status == DeviceHealthStatus.NO_CREDENTIALS
        assert rec.consecutive_failures == 0
        assert rec.last_seen_online is not None
        assert rec.latency_ms == 3

    @pytest.mark.parametrize("creds", [
        {"username": "root", "password": ""},
        {"username": "root"},
        {},
    ])
    @pytest.mark.asyncio
    async def test_an_empty_password_is_no_usable_credential(self, isolated, creds):
        rec = await _probe(creds)
        assert rec.status == DeviceHealthStatus.NO_CREDENTIALS

    @pytest.mark.asyncio
    async def test_credentials_present_and_no_catalog_stays_online(self, isolated):
        """Control: the value keys on credential absence, not on which tier
        answered."""
        rec = await _probe({"username": "root", "password": "pw"}, catalog=None)
        assert rec.status == DeviceHealthStatus.ONLINE

    @pytest.mark.asyncio
    async def test_host_down_is_unreachable_regardless(self, isolated, monkeypatch):
        monkeypatch.setattr("admz.fleet.health._tcp_probe", AsyncMock(return_value=None))
        rec = await _probe(None)
        assert rec.status == DeviceHealthStatus.UNREACHABLE

    @pytest.mark.asyncio
    async def test_a_factory_default_unit_is_needs_setup_not_no_credentials(self, isolated):
        """The credential-less tier asks systemready UNAUTHENTICATED — the op
        needs no credential by design — so a fresh camera keeps its existing
        CTA and deferred-recovery trigger instead of a password form for a
        password it does not have."""
        catalog, executor, calls = _catalog_and_executor(_systemready(needsetup=True))
        rec = await _probe(None, catalog=catalog, executor=executor)
        assert rec.status == DeviceHealthStatus.NEEDS_SETUP
        assert rec.uptime_seconds == 120 and rec.bootid == "b7"
        assert calls == [(SYSTEMREADY_OP, {"username": "", "password": ""})]

    @pytest.mark.asyncio
    async def test_a_provisioned_unit_answering_systemready_is_no_credentials(self, isolated):
        catalog, executor, calls = _catalog_and_executor(_systemready(needsetup=False))
        rec = await _probe(None, catalog=catalog, executor=executor)
        assert rec.status == DeviceHealthStatus.NO_CREDENTIALS
        assert calls == [(SYSTEMREADY_OP, {"username": "", "password": ""})]

    @pytest.mark.asyncio
    async def test_a_systemready_that_cannot_be_read_is_still_no_credentials(self, isolated):
        """A T85-class device (no JSON surface) without credentials: the
        unauthenticated read fails, the host answered → no_credentials."""
        catalog, executor, calls = _catalog_and_executor(
            MagicMock(success=False, status_code=None, error="Transport error: ")
        )
        rec = await _probe(None, catalog=catalog, executor=executor)
        assert rec.status == DeviceHealthStatus.NO_CREDENTIALS


# ---------------------------------------------------------------------------
# Settled, attention, never on_online
# ---------------------------------------------------------------------------

class TestSettledAndAttention:
    def test_it_is_settled(self):
        assert DeviceHealthStatus.NO_CREDENTIALS in _STABLE_STATUSES

    def test_it_never_fires_on_online(self):
        from admz.tasks.store import EVENT_ONLINE, event_for_status

        assert event_for_status("no_credentials") is None
        assert event_for_status("online") == EVENT_ONLINE  # control

    def test_it_is_not_demo_ready(self):
        """ADR-0046 readiness: a device ADMZ cannot authenticate to is not
        ready — and until the status existed it counted as ready."""
        from admz.demos.readiness import _HEALTHY

        assert "no_credentials" not in _HEALTHY
        assert "online" in _HEALTHY

    def test_it_is_an_attention_state_in_the_roster(self):
        index = (TEMPLATES / "index.html").read_text(encoding="utf-8", errors="replace")
        entry = re.search(r"no_credentials:\s*\{[^}]*\}", index)
        assert entry, "no_credentials missing from the dashboard HEALTH map"
        assert "bucket: 'attention'" in entry.group(0)
        assert "'amber'" in entry.group(0)

    def test_it_is_amber_and_labelled(self):
        from admz.api.templating import health_label, health_sem

        assert health_sem("no_credentials") == "amber"
        assert health_label("no_credentials") == "No credentials"

    def test_it_counts_as_a_site_issue(self, monkeypatch):
        import admz.api.templating as templating
        from tests.test_nav_sections import _FakeReq, _FakeRegistry

        devices = [
            {"device_id": "cam-1", "tags": [], "health": "online"},
            {"device_id": "cam-2", "tags": [], "health": "no_credentials"},
            {"device_id": "cam-3", "tags": [], "health": "limited_api"},
        ]
        monkeypatch.setattr(templating, "_registry", lambda: _FakeRegistry(devices))
        nav = templating.build_nav(_FakeReq())
        site = next(s for s in nav["sites"] if s["id"] == "default")
        assert site["issues"] == 1

    @pytest.mark.asyncio
    async def test_the_sweep_resets_the_counter_and_stamps_the_clock(self, isolated):
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "a1210", "host": "192.0.2.10"}]
        registry.get_credentials.side_effect = AccountNotFoundError("no account")
        store = DeviceHealthStore(str(isolated / "health.db"))
        earlier = time.time() - 3600
        store.upsert(DeviceHealthRecord(
            device_id="a1210", status=DeviceHealthStatus.UNREACHABLE,
            last_check=earlier, last_seen_online=earlier, consecutive_failures=3,
        ))
        monitor = HealthMonitor(registry=registry, catalog=None, executors={}, store=store)
        await monitor.sweep_once()
        rec = store.get("a1210")
        assert rec.status == DeviceHealthStatus.NO_CREDENTIALS
        assert rec.consecutive_failures == 0
        assert rec.last_seen_online > earlier

    @pytest.mark.asyncio
    async def test_the_sweep_does_not_claim_on_online_tasks(self, isolated):
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "a1210", "host": "192.0.2.10"}]
        registry.get_credentials.side_effect = AccountNotFoundError("no account")
        store = DeviceHealthStore(str(isolated / "health.db"))
        monitor = HealthMonitor(registry=registry, catalog=None, executors={}, store=store)
        with patch("admz.tasks.store.tasks_store.claim_for_event") as claim:
            await monitor.sweep_once()
        claim.assert_not_called()


# ---------------------------------------------------------------------------
# The predicate's edges in the sweep
# ---------------------------------------------------------------------------

class TestTheSweepsLookup:
    @pytest.mark.parametrize("exc", [
        AccountNotFoundError("no account row"),
        DeviceNotFoundError("gone"),
    ])
    @pytest.mark.asyncio
    async def test_absence_the_registry_says_is_no_credentials(self, isolated, exc):
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "a1210", "host": "192.0.2.10"}]
        registry.get_credentials.side_effect = exc
        store = DeviceHealthStore(str(isolated / "health.db"))
        monitor = HealthMonitor(registry=registry, catalog=None, executors={}, store=store)
        await monitor.sweep_once()
        assert store.get("a1210").status == DeviceHealthStatus.NO_CREDENTIALS

    @pytest.mark.parametrize("exc", [
        sqlite3.OperationalError("database is locked"),
        RuntimeError("Fernet: invalid token"),
        ConnectionError("vault: connection refused"),
    ])
    @pytest.mark.asyncio
    async def test_a_lookup_that_fails_keeps_the_previous_record(self, isolated, exc):
        """A locked database is not a fleet of devices without passwords."""
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "a1210", "host": "192.0.2.10"}]
        registry.get_credentials.side_effect = exc
        store = DeviceHealthStore(str(isolated / "health.db"))
        earlier = time.time() - 300
        store.upsert(DeviceHealthRecord(
            device_id="a1210", status=DeviceHealthStatus.ONLINE,
            last_check=earlier, last_seen_online=earlier, latency_ms=12,
            consecutive_failures=0,
        ))
        monitor = HealthMonitor(registry=registry, catalog=None, executors={}, store=store)
        with patch("admz.fleet.health.probe_device") as probe:
            await monitor.sweep_once()
        probe.assert_not_called()
        rec = store.get("a1210")
        assert rec.status == DeviceHealthStatus.ONLINE
        assert rec.consecutive_failures == 0
        assert rec.last_seen_online == pytest.approx(earlier)
        assert rec.last_check > earlier
        assert rec.last_error.startswith("credential lookup failed:")

    @pytest.mark.asyncio
    async def test_a_lookup_that_fails_with_no_history_is_unknown(self, isolated):
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "a1210", "host": "192.0.2.10"}]
        registry.get_credentials.side_effect = sqlite3.OperationalError("database is locked")
        store = DeviceHealthStore(str(isolated / "health.db"))
        monitor = HealthMonitor(registry=registry, catalog=None, executors={}, store=store)
        await monitor.sweep_once()
        rec = store.get("a1210")
        assert rec.status == DeviceHealthStatus.UNKNOWN
        assert rec.last_error.startswith("credential lookup failed:")

    @pytest.mark.asyncio
    async def test_the_sweep_never_resolves(self, isolated):
        """Rule 2: the sweep classifies. It sends nothing credentialed beyond
        the unauthenticated systemready read, and writes no account."""
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "a1210", "host": "192.0.2.10"}]
        registry.get_credentials.side_effect = AccountNotFoundError("no account")
        catalog, executor, calls = _catalog_and_executor(_systemready(needsetup=False))
        store = DeviceHealthStore(str(isolated / "health.db"))
        monitor = HealthMonitor(
            registry=registry, catalog=catalog, executors={"vapix": executor}, store=store,
        )
        with patch("admz.onboarding.onboard_device_credentials", new=AsyncMock()) as onboard:
            await monitor.sweep_once()
        assert store.get("a1210").status == DeviceHealthStatus.NO_CREDENTIALS
        assert calls == [(SYSTEMREADY_OP, {"username": "", "password": ""})]
        onboard.assert_not_called()
        registry.add_account.assert_not_called()
        registry.update_account.assert_not_called()


# ---------------------------------------------------------------------------
# Every consumer knows every member — by iteration, not by literal
# ---------------------------------------------------------------------------

class TestEveryConsumerKnowsEveryMember:
    @pytest.mark.parametrize("name", ["index.html", "device_detail.html"])
    def test_every_status_is_in_the_client_side_health_map(self, name):
        """The template tests before ADR-0064 were keyed on literal strings,
        so a member missing from `index.html` rendered grey "Unknown" in bucket
        `unknown` — #357's parking, again — and no test noticed."""
        text = (TEMPLATES / name).read_text(encoding="utf-8", errors="replace")
        block = re.search(r"const HEALTH = \{(.*?)\n\};", text, re.S)
        assert block, f"{name}: HEALTH map not found"
        for status in DeviceHealthStatus:
            assert re.search(rf"\b{status.value}\s*:\s*\{{", block.group(1)), (
                f"{name}: {status.value} missing from the HEALTH map"
            )

    def test_every_status_has_a_colour_and_a_label(self):
        from admz.api.templating import HEALTH_LABEL, HEALTH_SEM

        for status in DeviceHealthStatus:
            assert status.value in HEALTH_SEM and status.value in HEALTH_LABEL

    @pytest.mark.asyncio
    async def test_both_count_dicts_carry_every_member(self, isolated, monkeypatch):
        from admz.api.routes import health as health_routes
        from admz.fleet import health as health_mod
        from admz.mcp.server import ADMZMCPServer

        store = DeviceHealthStore(str(isolated / "health.db"))
        store.upsert(DeviceHealthRecord(device_id="a1210", status=DeviceHealthStatus.NO_CREDENTIALS))
        monkeypatch.setattr(health_routes, "device_health_store", store)
        monkeypatch.setattr(health_mod, "device_health_store", store)
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "a1210"}]
        registry.device_exists.return_value = True

        rest = await health_routes.get_fleet_health(registry=registry)
        mcp = await ADMZMCPServer._get_fleet_health(SimpleNamespace(registry=registry))
        expected = {s.value for s in DeviceHealthStatus}
        assert set(rest["counts"]) == expected
        assert set(mcp["counts"]) == expected
        assert rest["counts"]["no_credentials"] == 1 and mcp["counts"]["no_credentials"] == 1

    @pytest.mark.asyncio
    async def test_the_count_dicts_are_zero_initialised_for_every_member(self, isolated, monkeypatch):
        """The increment (`counts.get(status, 0) + 1`) would re-create a missing
        key whenever such a device exists — so the shape is checked with NO
        device in the new status: a literal dict missing the member fails
        here, not only when the fleet happens to contain one."""
        from admz.api.routes import health as health_routes
        from admz.fleet import health as health_mod
        from admz.mcp.server import ADMZMCPServer

        store = DeviceHealthStore(str(isolated / "health.db"))
        store.upsert(DeviceHealthRecord(device_id="cam", status=DeviceHealthStatus.ONLINE))
        monkeypatch.setattr(health_routes, "device_health_store", store)
        monkeypatch.setattr(health_mod, "device_health_store", store)
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "cam"}]
        registry.device_exists.return_value = True

        rest = await health_routes.get_fleet_health(registry=registry)
        mcp = await ADMZMCPServer._get_fleet_health(SimpleNamespace(registry=registry))
        for status in DeviceHealthStatus:
            assert rest["counts"][status.value] == (1 if status is DeviceHealthStatus.ONLINE else 0)
            assert mcp["counts"][status.value] == (1 if status is DeviceHealthStatus.ONLINE else 0)

    def test_the_chat_model_is_told_what_it_means(self):
        from admz.chatbot import system_prompt

        text = " ".join(Path(system_prompt.__file__).read_text(encoding="utf-8").split())
        assert "`no_credentials` means ADMZ never had a way in" in text
        assert 'never say "unreachable"' in text
        assert 'never "wrong password"' in text
        assert "`capture_credentials`" in text
