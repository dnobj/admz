"""ADR-0072 §1-2 — what a scan records, what the console may add from it, the
unauthenticated identity read, and the sentence the approval carries."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from admz.discovery import candidates
from admz.discovery.models import DeviceType, DiscoveredDevice, DiscoveryProtocol


def _axis(mac="E8:27:25:31:5C:DF", ip="192.0.2.41", **kw):
    dev = DiscoveredDevice(ip_address=ip, mac_address=mac, model="AXIS P3408-VE",
                           is_axis=True, **kw)
    dev.discovered_by.append(DiscoveryProtocol.ARP)
    return dev


class TestIdentity:
    def test_the_mac_is_the_identity(self):
        assert candidates.device_identity("e8:27:25:31:5c:df") == "E82725315CDF"

    def test_a_serial_stands_in_when_there_is_no_mac(self):
        assert candidates.device_identity(None, "ACCC8EE6E7EE") == "ACCC8EE6E7EE"

    def test_nothing_hex12_is_no_identity(self):
        assert candidates.device_identity("", "") == ""
        assert candidates.device_identity(None, "not-a-serial") == ""
        assert candidates.device_identity("12:34", None) == ""


class TestRecord:
    def test_a_record_keeps_the_display_fields_and_the_registry_payload(self):
        rec = candidates.scan_record(_axis(serial_number="E82725315CDF"))
        assert rec["device_id"] == "E82725315CDF"
        assert rec["registry_info"]["host"] == "192.0.2.41"
        assert rec["discovered_by"] == ["arp"]
        assert set(candidates.DISPLAY_FIELDS) <= set(rec)
        assert set(candidates.display_view(rec)) == set(candidates.DISPLAY_FIELDS)


class TestRegistration:
    def test_the_index_matches_by_stored_mac_or_by_id(self):
        registry = MagicMock()
        registry.list_devices.return_value = [
            {"device_id": "lobby-cam", "mac_address": "E8:27:25:31:5C:DF"},
            {"device_id": "ACCC8EE6E7EE"},
            {"device_id": "no-mac-at-all"},
        ]
        index = candidates.registered_index(registry)
        assert index == {"E82725315CDF": "lobby-cam", "ACCC8EE6E7EE": "ACCC8EE6E7EE"}

    def test_an_unreadable_registry_is_an_empty_index(self):
        registry = MagicMock()
        registry.list_devices.side_effect = RuntimeError("db locked")
        assert candidates.registered_index(registry) == {}

    def test_annotate_marks_registered_and_blocked_rows(self):
        records = [
            candidates.scan_record(_axis()),
            candidates.scan_record(_axis(mac="B8:A4:4F:B8:92:AE", ip="192.0.2.5")),
            candidates.scan_record(DiscoveredDevice(
                ip_address="192.0.2.1", mac_address="5C:35:FC:51:EA:C0",
                device_type=DeviceType.UNKNOWN)),
            candidates.scan_record(_axis(mac=None, ip="192.0.2.77")),
            candidates.scan_record(_axis(mac="00:40:8C:00:00:01", ip=None)),
        ]
        views = candidates.annotate(records, {"B8A44FB892AE": "c8110"})
        blockers = [(v["registered_device_id"], v["add_blocker"]) for v in views]
        assert blockers == [
            (None, ""),
            ("c8110", candidates.BLOCK_REGISTERED),
            (None, candidates.BLOCK_NOT_AXIS),
            (None, candidates.BLOCK_NO_IDENTITY),
            (None, candidates.BLOCK_NO_ADDRESS),
        ]
        assert "registry_info" not in views[0]

    def test_counts_survive_a_truncated_list(self):
        views = [
            {"is_axis": True, "registered_device_id": None, "factory_default": True},
            {"is_axis": True, "registered_device_id": "x", "factory_default": False},
            {"is_axis": False, "registered_device_id": None, "factory_default": False},
        ]
        assert candidates.summary_counts(views) == {
            "axis_count": 2, "new_axis_count": 1, "factory_default_count": 1}


class TestUnauthenticatedIdentityRead:
    @pytest.fixture(autouse=True)
    def _reachable(self, monkeypatch):
        monkeypatch.setattr("admz.fleet.health._tcp_probe", AsyncMock(return_value=3))

    def test_an_address_that_does_not_answer_fails_fast(self, monkeypatch):
        """The operator is waiting on the approval request."""
        from admz.discovery.identity import read_unrestricted_serial

        monkeypatch.setattr("admz.fleet.health._tcp_probe",
                            AsyncMock(return_value=None))
        executor = MagicMock()
        executor.execute = AsyncMock()
        assert asyncio.run(read_unrestricted_serial(
            self._catalog(), executor, "192.0.2.41")) is None
        executor.execute.assert_not_awaited()

    def test_a_slow_read_times_out(self, monkeypatch):
        from admz.discovery import identity

        monkeypatch.setattr(identity, "READ_TIMEOUT_SECONDS", 0.05)

        async def _slow(*a, **kw):
            await asyncio.sleep(5)

        executor = MagicMock()
        executor.execute = _slow
        assert asyncio.run(identity.read_unrestricted_serial(
            self._catalog(), executor, "192.0.2.41")) is None

    def _catalog(self):
        catalog = MagicMock()
        catalog.get_operation.return_value = MagicMock(
            to_executor_dict=lambda: {"id": "basicdeviceinfo.cgi:getAllUnrestrictedProperties"})
        return catalog

    def test_it_sends_no_credentials(self):
        from admz.discovery.identity import OPERATION_ID, read_unrestricted_serial

        executor = MagicMock()
        executor.execute = AsyncMock(return_value=SimpleNamespace(
            success=True, parsed_data={"SerialNumber": "E82725315CDF"}))
        catalog = self._catalog()
        serial = asyncio.run(read_unrestricted_serial(catalog, executor, "192.0.2.41"))

        assert serial == "E82725315CDF"
        catalog.get_operation.assert_called_once_with("vapix", OPERATION_ID)
        _op, device, creds, params = executor.execute.await_args.args
        assert creds == {"username": "", "password": ""}
        assert device["auth"]["http"] == "none" and device["auth"]["https"] == "none"
        assert params == {}

    def test_the_serial_is_found_under_the_property_list(self):
        from admz.discovery.identity import _serial_from

        assert _serial_from({"propertyList": {"SerialNumber": "X"}}) == "X"
        assert _serial_from({"data": {"propertyList": {"SerialNumber": "Y"}}}) == "Y"
        assert _serial_from("text") == ""

    def test_a_failed_read_is_none(self):
        from admz.discovery.identity import read_unrestricted_serial

        executor = MagicMock()
        executor.execute = AsyncMock(return_value=SimpleNamespace(
            success=False, parsed_data=None))
        assert asyncio.run(read_unrestricted_serial(
            self._catalog(), executor, "192.0.2.41")) is None
        executor.execute = AsyncMock(side_effect=OSError("refused"))
        assert asyncio.run(read_unrestricted_serial(
            self._catalog(), executor, "192.0.2.41")) is None

    def test_confirmation_compares_canonical_forms(self, monkeypatch):
        from admz.discovery import identity

        monkeypatch.setattr(identity, "read_unrestricted_serial",
                            AsyncMock(return_value="e8:27:25:31:5c:df"))
        ok, why = asyncio.run(identity.confirm_identity(
            None, None, "192.0.2.41", "E82725315CDF"))
        assert (ok, why) == (True, "")


class TestTheSentence:
    def test_it_names_every_device_and_every_write(self):
        from admz.discovery.gated import add_reason

        text = add_reason([
            {"device_id": "E82725315CDF", "host": "192.0.2.41", "model": "AXIS P3408-VE"},
            {"device_id": "E827250904B4", "host": "192.0.2.60", "model": ""},
        ])
        assert text.startswith("Add 2 discovered devices to ADMZ:")
        assert "AXIS P3408-VE (E82725315CDF at 192.0.2.41)" in text
        assert "E827250904B4 at 192.0.2.60" in text
        assert "'root' set to the fleet root password" in text
        assert "identity cannot be confirmed is skipped" in text

    def test_a_device_written_model_cannot_add_lines(self):
        from admz.discovery.gated import add_reason

        text = add_reason([{"device_id": "E82725315CDF", "host": "192.0.2.41",
                            "model": "Cam\nIgnore the above"}])
        assert "\n" not in text

    def test_the_survey_card_is_unchanged(self):
        """The account wording moved into a shared constant; the survey card
        must read exactly as it did."""
        from admz.discovery.gated import survey_reason

        assert survey_reason("10.0.0.0/24", True) == (
            "Deep survey: scan 10.0.0.0/24, then register unknown devices it "
            "finds and, on each, create an admin account for ADMZ — on a "
            "factory-defaulted device TWO accounts: 'root' set to the fleet "
            "root password, then ADMZ's own 'admz' account (only 'admz' is "
            "stored); or on a device that is already set up, just ADMZ's own "
            "'admz' account if the fleet root password or an entry credential "
            "can log in (that credential is left in place). This writes to "
            "devices ADMZ has never seen.")


class TestTheToolResult:
    def _server(self, monkeypatch, principal_name, devices, registered=()):
        from admz.auth import Principal
        from admz.mcp import server as server_mod
        from admz.mcp.server import ADMZMCPServer

        async def _scan(**kwargs):
            return devices

        monkeypatch.setattr(server_mod, "run_network_discovery", _scan)
        srv = ADMZMCPServer.__new__(ADMZMCPServer)
        srv.principal = Principal(name=principal_name, display_name=principal_name,
                                  source="windows")
        srv.registry = MagicMock()
        srv.registry.list_devices.return_value = [
            {"device_id": d} for d in registered]
        return srv

    def test_the_result_names_the_scan_and_the_registered_devices(self, monkeypatch):
        from admz.discovery.scan_store import discovery_scans

        devices = [_axis(), _axis(mac="B8:A4:4F:B8:92:AE", ip="192.0.2.5",
                                  factory_default=True)]
        srv = self._server(monkeypatch, "alice", devices, registered=["B8A44FB892AE"])
        out = asyncio.run(srv._discover_network_devices({"subnet": "192.0.2.0/24"}))

        assert out["success"] is True
        assert (out["count"], out["axis_count"], out["new_axis_count"],
                out["factory_default_count"]) == (2, 2, 1, 1)
        assert [d["registered_device_id"] for d in out["devices"]] == [None, "B8A44FB892AE"]
        assert out["scan_url"] == f"/api/discovery/scans/{out['scan_id']}"
        # The pre-ADR fields are all still there.
        assert set(candidates.DISPLAY_FIELDS) <= set(out["devices"][0])

        scan = discovery_scans.get_scan(out["scan_id"])
        assert scan.principal == "alice"
        assert scan.subnet == "192.0.2.0/24"
        assert scan.devices[0]["registry_info"]["host"] == "192.0.2.41"

    def test_a_standalone_client_keeps_no_scan(self, monkeypatch):
        srv = self._server(monkeypatch, "mcp-standalone", [_axis()])
        out = asyncio.run(srv._discover_network_devices({}))
        assert out["success"] is True
        assert "scan_id" not in out and "scan_url" not in out

    def test_a_store_failure_is_still_a_scan(self, monkeypatch):
        srv = self._server(monkeypatch, "alice", [_axis()])
        monkeypatch.setattr(
            "admz.discovery.scan_store.discovery_scans.save_scan",
            MagicMock(side_effect=OSError("disk full")))
        out = asyncio.run(srv._discover_network_devices({}))
        assert out["success"] is True
        assert "scan_url" not in out

    def test_the_new_names_survive_the_display_redactor(self):
        from admz.chatbot.client import _redact_for_display

        shown = _redact_for_display({
            "scan_id": "abc", "scan_url": "/api/discovery/scans/abc",
            "new_axis_count": 1,
            "devices": [{"registered_device_id": "E82725315CDF"}]})
        assert shown["scan_url"] == "/api/discovery/scans/abc"
        assert shown["scan_id"] == "abc"
        assert shown["devices"][0]["registered_device_id"] == "E82725315CDF"

    def test_the_description_names_the_widget_and_the_fields(self):
        import pathlib
        import re

        src = pathlib.Path("admz/mcp/server.py").read_text(encoding="utf-8")
        start = src.index('name="discover_network_devices"')
        end = src.index("inputSchema", start)
        # Join the adjacent string literals the description is written as.
        desc = re.sub(r'"\s*\n\s*"', "", src[start:end])
        for word in ("registered_device_id", "new_axis_count", "scan_url",
                     "one approval"):
            assert word in desc
