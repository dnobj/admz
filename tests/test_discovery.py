"""Tests for the discovery module: models, base class, orchestrator merge logic.

These tests use fake protocol implementations rather than touching the
network, so they're hermetic and fast.
"""

from typing import List, Optional

import pytest

from admz.discovery.base import DiscoveryProtocolBase
from admz.discovery.models import (
    AXIS_OUI_PREFIXES,
    DeviceType,
    DiscoveredDevice,
    DiscoveryProtocol,
    is_axis_mac,
)
from admz.discovery.orchestrator import (
    DiscoveryOrchestrator,
    _merge_all,
    _merge_into,
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestIsAxisMac:

    def test_known_axis_oui(self):
        assert is_axis_mac("00:40:8C:11:22:33") is True
        assert is_axis_mac("AC:CC:8E:AA:BB:CC") is True
        assert is_axis_mac("B8:A4:4F:11:22:33") is True

    def test_unknown_oui(self):
        assert is_axis_mac("AA:BB:CC:DD:EE:FF") is False

    def test_case_insensitive(self):
        assert is_axis_mac("00:40:8c:11:22:33") is True

    def test_handles_dashes(self):
        assert is_axis_mac("00-40-8C-11-22-33") is True


class TestDiscoveredDevice:

    def test_default_values(self):
        d = DiscoveredDevice()
        assert d.ip_address is None
        assert d.mac_address is None
        assert d.device_type == DeviceType.UNKNOWN
        assert d.is_axis is False
        assert d.vapix_available is False
        assert d.discovered_by == []

    def test_merge_fills_missing_fields(self):
        a = DiscoveredDevice(ip_address="1.2.3.4", mac_address="aa:bb:cc:11:22:33")
        b = DiscoveredDevice(
            mac_address="aa:bb:cc:11:22:33",
            model="P3245-V",
            hostname="lobby",
        )
        a.merge(b)
        assert a.model == "P3245-V"
        assert a.hostname == "lobby"
        assert a.ip_address == "1.2.3.4"  # was not overwritten

    def test_merge_does_not_overwrite_existing_values(self):
        a = DiscoveredDevice(model="P3245-V")
        b = DiscoveredDevice(model="P1455-LE")
        a.merge(b)
        assert a.model == "P3245-V"

    def test_merge_prefers_concrete_device_type(self):
        a = DiscoveredDevice(device_type=DeviceType.UNKNOWN)
        b = DiscoveredDevice(device_type=DeviceType.CAMERA)
        a.merge(b)
        assert a.device_type == DeviceType.CAMERA

    def test_merge_keeps_concrete_device_type(self):
        a = DiscoveredDevice(device_type=DeviceType.CAMERA)
        b = DiscoveredDevice(device_type=DeviceType.UNKNOWN)
        a.merge(b)
        assert a.device_type == DeviceType.CAMERA

    def test_merge_ors_boolean_flags(self):
        a = DiscoveredDevice(vapix_available=False, is_axis=False)
        b = DiscoveredDevice(vapix_available=True, is_axis=True)
        a.merge(b)
        assert a.vapix_available is True
        assert a.is_axis is True

    def test_merge_deduplicates_lists(self):
        a = DiscoveredDevice(
            discovered_by=[DiscoveryProtocol.MDNS],
            mdns_services=["_axis-video._tcp.local."],
        )
        b = DiscoveredDevice(
            discovered_by=[DiscoveryProtocol.ONVIF, DiscoveryProtocol.MDNS],
            mdns_services=["_axis-video._tcp.local."],
        )
        a.merge(b)
        assert set(a.discovered_by) == {
            DiscoveryProtocol.MDNS, DiscoveryProtocol.ONVIF,
        }
        assert a.mdns_services == ["_axis-video._tcp.local."]

    def test_to_registry_dict_contains_expected_keys(self):
        d = DiscoveredDevice(
            ip_address="1.2.3.4",
            mac_address="aa:bb:cc:11:22:33",
            model="P3245-V",
            hostname="lobby-cam",
            device_type=DeviceType.CAMERA,
            is_axis=True,
        )
        out = d.to_registry_dict()
        assert out["host"] == "1.2.3.4"
        assert out["ip_address"] == "1.2.3.4"
        assert out["mac_address"] == "aa:bb:cc:11:22:33"
        assert out["model"] == "P3245-V"
        assert out["device_type"] == "camera"
        assert "tags" in out
        assert "metadata" in out


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

class TestMergeAll:

    def test_keys_by_mac_when_present(self):
        a = DiscoveredDevice(mac_address="aa:bb:cc:11:22:33", ip_address="1.2.3.4")
        b = DiscoveredDevice(mac_address="aa:bb:cc:11:22:33", model="P3245-V")
        merged = _merge_all([[a], [b]])
        assert len(merged) == 1
        device = next(iter(merged.values()))
        assert device.ip_address == "1.2.3.4"
        assert device.model == "P3245-V"

    def test_keys_by_ip_when_no_mac(self):
        a = DiscoveredDevice(ip_address="1.2.3.4")
        b = DiscoveredDevice(ip_address="1.2.3.4", model="P3245-V")
        merged = _merge_all([[a], [b]])
        assert len(merged) == 1
        assert next(iter(merged.values())).model == "P3245-V"

    def test_skips_devices_with_no_identity(self):
        a = DiscoveredDevice()  # no mac, no ip
        b = DiscoveredDevice(ip_address="1.2.3.4")
        merged = _merge_all([[a, b]])
        assert len(merged) == 1

    def test_different_devices_kept_separate(self):
        a = DiscoveredDevice(mac_address="aa:aa:aa:11:22:33", ip_address="1.2.3.4")
        b = DiscoveredDevice(mac_address="bb:bb:bb:11:22:33", ip_address="1.2.3.5")
        merged = _merge_all([[a, b]])
        assert len(merged) == 2


class TestMergeInto:

    def test_enrichment_matches_by_ip(self):
        merged = {
            "aa:bb:cc:11:22:33": DiscoveredDevice(
                mac_address="aa:bb:cc:11:22:33",
                ip_address="1.2.3.4",
            )
        }
        enrichment = DiscoveredDevice(ip_address="1.2.3.4", model="P3245-V")
        _merge_into(merged, [[enrichment]])
        device = next(iter(merged.values()))
        assert device.model == "P3245-V"

    def test_enrichment_with_new_ip_added(self):
        merged = {
            "aa:bb:cc:11:22:33": DiscoveredDevice(
                mac_address="aa:bb:cc:11:22:33",
                ip_address="1.2.3.4",
            )
        }
        new_device = DiscoveredDevice(ip_address="1.2.3.99", model="Speaker")
        _merge_into(merged, [[new_device]])
        assert len(merged) == 2


# ---------------------------------------------------------------------------
# Orchestrator (with fake protocols)
# ---------------------------------------------------------------------------

class FakeProtocol(DiscoveryProtocolBase):
    def __init__(self, name: str, devices: List[DiscoveredDevice]):
        self._name = name
        self._devices = devices

    @property
    def name(self) -> str:
        return self._name

    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        return list(self._devices)


class CrashingProtocol(DiscoveryProtocolBase):
    @property
    def name(self) -> str:
        return "crashing"

    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        raise RuntimeError("simulated failure")


class TestOrchestrator:

    @pytest.mark.asyncio
    async def test_safe_discover_swallows_exceptions(self):
        proto = CrashingProtocol()
        result = await proto.safe_discover(timeout=0.1)
        assert result == []

    @pytest.mark.asyncio
    async def test_orchestrator_with_no_protocols_returns_empty(self):
        orch = DiscoveryOrchestrator(
            enable_mdns=False,
            enable_ssdp=False,
            enable_onvif=False,
            enable_arp=False,
            enable_ping=False,
            enable_http_probe=False,
            enable_snmp=False,
            timeout=0.1,
        )
        result = await orch.run()
        assert result == []

    @pytest.mark.asyncio
    async def test_orchestrator_merges_results_from_multiple_protos(self):
        """Test the merging logic by injecting fake protocols directly."""
        orch = DiscoveryOrchestrator(
            enable_mdns=False,
            enable_ssdp=False,
            enable_onvif=False,
            enable_arp=False,
            enable_ping=False,
            enable_http_probe=False,
            enable_snmp=False,
            timeout=0.1,
        )
        # Inject fake protocols
        orch._phase1 = [
            FakeProtocol(
                "mdns",
                [DiscoveredDevice(
                    mac_address="aa:bb:cc:11:22:33",
                    ip_address="1.2.3.4",
                    model="P3245-V",
                )],
            ),
            FakeProtocol(
                "onvif",
                [DiscoveredDevice(
                    mac_address="aa:bb:cc:11:22:33",
                    onvif_xaddrs="http://1.2.3.4/onvif/device_service",
                )],
            ),
        ]
        result = await orch.run()
        assert len(result) == 1
        assert result[0].model == "P3245-V"
        assert result[0].onvif_xaddrs == "http://1.2.3.4/onvif/device_service"

    @pytest.mark.asyncio
    async def test_axis_only_filters_out_non_axis(self):
        orch = DiscoveryOrchestrator(
            enable_mdns=False,
            enable_ssdp=False,
            enable_onvif=False,
            enable_arp=False,
            enable_ping=False,
            enable_http_probe=False,
            enable_snmp=False,
            axis_only=True,
            timeout=0.1,
        )
        orch._phase1 = [
            FakeProtocol(
                "fake",
                [
                    DiscoveredDevice(ip_address="1.2.3.4", is_axis=True),
                    DiscoveredDevice(ip_address="1.2.3.5", is_axis=False),
                ],
            ),
        ]
        result = await orch.run()
        assert len(result) == 1
        assert result[0].ip_address == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_axis_devices_sorted_first(self):
        orch = DiscoveryOrchestrator(
            enable_mdns=False,
            enable_ssdp=False,
            enable_onvif=False,
            enable_arp=False,
            enable_ping=False,
            enable_http_probe=False,
            enable_snmp=False,
            timeout=0.1,
        )
        orch._phase1 = [
            FakeProtocol(
                "fake",
                [
                    DiscoveredDevice(ip_address="1.2.3.5", is_axis=False),
                    DiscoveredDevice(ip_address="1.2.3.4", is_axis=True),
                ],
            ),
        ]
        result = await orch.run()
        assert result[0].is_axis is True
        assert result[1].is_axis is False

    @pytest.mark.asyncio
    async def test_one_crashing_protocol_does_not_break_others(self):
        orch = DiscoveryOrchestrator(
            enable_mdns=False,
            enable_ssdp=False,
            enable_onvif=False,
            enable_arp=False,
            enable_ping=False,
            enable_http_probe=False,
            enable_snmp=False,
            timeout=0.1,
        )
        orch._phase1 = [
            CrashingProtocol(),
            FakeProtocol(
                "good",
                [DiscoveredDevice(ip_address="1.2.3.4", model="P3245-V")],
            ),
        ]
        result = await orch.run()
        assert len(result) == 1
        assert result[0].model == "P3245-V"


# ---------------------------------------------------------------------------
# Axis OUI prefixes data
# ---------------------------------------------------------------------------

class TestAxisOUIPrefixes:

    def test_axis_oui_prefixes_are_uppercase_normalized(self):
        for prefix in AXIS_OUI_PREFIXES:
            assert prefix == prefix.upper()
            assert len(prefix) == 8  # XX:XX:XX

    def test_set_not_empty(self):
        assert len(AXIS_OUI_PREFIXES) > 0
