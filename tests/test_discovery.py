"""Tests for the discovery module: models, base class, orchestrator merge logic.

These tests use fake protocol implementations rather than touching the
network, so they're hermetic and fast.
"""

import copy
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

    # -- a record with no MAC joins its device (ADR-0016's IP fallback) -----
    #
    # The console's discovery widget listed every Axis camera twice on
    # 2026-09-17: SSDP reports a serial and a model but never a MAC, so its
    # record sat under the IP beside the mDNS/ARP record under the MAC.

    def test_a_serial_joins_the_record_whose_mac_it_is(self):
        ssdp = DiscoveredDevice(
            ip_address="192.0.2.24", serial_number="ACCC8E000024",
            model="AXIS T8516", is_axis=True,
            discovered_by=[DiscoveryProtocol.SSDP])
        arp = DiscoveredDevice(
            ip_address="192.0.2.24", mac_address="AC:CC:8E:00:00:24",
            is_axis=True, discovered_by=[DiscoveryProtocol.ARP])
        for order in ([[ssdp], [arp]], [[arp], [ssdp]]):
            merged = _merge_all(copy.deepcopy(order))
            assert len(merged) == 1, order
            device = next(iter(merged.values()))
            assert (device.mac_address, device.serial_number, device.model) == (
                "AC:CC:8E:00:00:24", "ACCC8E000024", "AXIS T8516")
            assert set(device.discovered_by) == {
                DiscoveryProtocol.SSDP, DiscoveryProtocol.ARP}

    def test_a_serial_joins_its_mac_record_at_another_address(self):
        arp = DiscoveredDevice(ip_address="192.0.2.30", mac_address="B8:A4:4F:00:00:30")
        ssdp = DiscoveredDevice(ip_address="192.0.2.31", serial_number="b8a44f000030",
                                model="AXIS P3748-PLVE", is_axis=True)
        merged = _merge_all([[arp], [ssdp]])
        assert len(merged) == 1
        assert next(iter(merged.values())).ip_address == "192.0.2.30"

    def test_a_record_without_identity_joins_the_one_mac_at_its_address(self):
        """The router: SSDP gives a model and a serial that is not a MAC, ARP
        the MAC. One device."""
        router_ssdp = DiscoveredDevice(ip_address="192.0.2.1", manufacturer="ISP",
                                       serial_number="1J72450M0", model="GR6EXX0C")
        router_arp = DiscoveredDevice(ip_address="192.0.2.1",
                                      mac_address="5C:35:FC:00:00:01")
        merged = _merge_all([[router_ssdp], [router_arp]])
        assert len(merged) == 1
        router = merged["5C35FC000001"]
        assert (router.model, router.serial_number, router.manufacturer) == (
            "GR6EXX0C", "1J72450M0", "ISP")

    def test_an_axis_claim_joined_by_address_does_not_make_a_pc_an_axis_device(self):
        """The PC running ADMZ answered SSDP with a SERVER header naming Axis
        software (2026-09-17). Joined to its own MAC it is one row — and not
        an Axis device to add, because nothing tied the claim to Axis
        hardware."""
        pc_ssdp = DiscoveredDevice(
            ip_address="192.0.2.95", is_axis=True,
            manufacturer="Axis Communications", device_type=DeviceType.CAMERA,
            discovered_by=[DiscoveryProtocol.SSDP])
        pc_arp = DiscoveredDevice(
            ip_address="192.0.2.95", mac_address="98:59:7A:00:00:95",
            discovered_by=[DiscoveryProtocol.ARP])
        merged = _merge_all([[pc_ssdp], [pc_arp]])
        assert len(merged) == 1
        pc = merged["98597A000095"]
        assert (pc.is_axis, pc.manufacturer, pc.device_type) == (
            False, None, DeviceType.UNKNOWN)
        assert set(pc.discovered_by) == {DiscoveryProtocol.SSDP, DiscoveryProtocol.ARP}

    def test_an_axis_claim_joined_by_address_stands_on_an_axis_mac(self):
        """No serial, but the MAC is Axis hardware, so the claim agrees."""
        ssdp = DiscoveredDevice(ip_address="192.0.2.96", is_axis=True,
                                manufacturer="Axis Communications")
        arp = DiscoveredDevice(ip_address="192.0.2.96",
                               mac_address="B8:A4:4F:00:00:96", is_axis=True)
        mdns = DiscoveredDevice(ip_address="192.0.2.97", is_axis=True)
        holder = DiscoveredDevice(ip_address="192.0.2.97",
                                  mac_address="E8:27:25:00:00:97")
        merged = _merge_all([[ssdp, mdns], [arp, holder]])
        assert len(merged) == 2
        assert merged["B8A44F000096"].manufacturer == "Axis Communications"
        assert merged["E82725000097"].is_axis is True

    def test_an_address_two_macs_hold_is_not_guessed(self):
        a = DiscoveredDevice(ip_address="192.0.2.7", mac_address="AC:CC:8E:00:00:07")
        b = DiscoveredDevice(ip_address="192.0.2.7", mac_address="AC:CC:8E:00:00:08")
        ssdp = DiscoveredDevice(ip_address="192.0.2.7", model="AXIS M3106")
        merged = _merge_all([[a, b], [ssdp]])
        assert len(merged) == 3
        assert a.model is None and b.model is None

    def test_a_different_axis_serial_at_the_same_address_stays_separate(self):
        """An Axis serial is a MAC, so one naming another MAC is another
        device (a stale ARP entry, a reassigned lease)."""
        arp = DiscoveredDevice(ip_address="192.0.2.9", mac_address="AC:CC:8E:00:00:09",
                               is_axis=True)
        ssdp = DiscoveredDevice(ip_address="192.0.2.9", serial_number="B8A44F000009",
                                is_axis=True)
        merged = _merge_all([[arp], [ssdp]])
        assert len(merged) == 2
        assert arp.serial_number is None

    def test_another_vendors_mac_shaped_serial_is_not_a_conflict(self):
        """Only an Axis serial is its MAC."""
        arp = DiscoveredDevice(ip_address="192.0.2.10", mac_address="5C:35:FC:00:00:10")
        ssdp = DiscoveredDevice(ip_address="192.0.2.10", serial_number="0123456789AB",
                                model="NAS")
        merged = _merge_all([[arp], [ssdp]])
        assert len(merged) == 1
        assert arp.model == "NAS"

    def test_two_different_serials_at_the_same_address_stay_separate(self):
        mdns = DiscoveredDevice(ip_address="192.0.2.11", mac_address="5C:35:FC:00:00:11",
                                serial_number="SN-ONE")
        ssdp = DiscoveredDevice(ip_address="192.0.2.11", serial_number="SN-TWO")
        merged = _merge_all([[mdns], [ssdp]])
        assert len(merged) == 2

    def test_records_without_a_mac_still_merge_with_each_other(self):
        ssdp = DiscoveredDevice(ip_address="192.0.2.12", model="Speaker")
        onvif = DiscoveredDevice(ip_address="192.0.2.12", onvif_xaddrs="http://192.0.2.12/x")
        merged = _merge_all([[ssdp], [onvif]])
        assert len(merged) == 1
        assert merged["192.0.2.12"].onvif_xaddrs == "http://192.0.2.12/x"

    def test_mac_spellings_are_one_device(self):
        a = DiscoveredDevice(mac_address="ac:cc:8e:00:00:13", ip_address="192.0.2.13")
        b = DiscoveredDevice(mac_address="AC-CC-8E-00-00-13", model="AXIS P1455")
        merged = _merge_all([[a], [b]])
        assert len(merged) == 1
        assert a.model == "AXIS P1455"


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
    async def test_a_scan_lists_each_device_once(self):
        """The 2026-09-17 widget scan in miniature: mDNS and ARP know the MAC,
        SSDP the serial and model. One scan record, and one id, per device."""
        from admz.discovery.candidates import scan_record

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
        cam = "E8:27:25:00:00:41"
        orch._phase1 = [
            FakeProtocol("mdns", [DiscoveredDevice(
                ip_address="192.0.2.41", mac_address=cam, is_axis=True,
                hostname="axis-e82725000041.local",
                discovered_by=[DiscoveryProtocol.MDNS])]),
            FakeProtocol("ssdp", [
                DiscoveredDevice(
                    ip_address="192.0.2.41", serial_number="E82725000041",
                    model="AXIS P3408-VE", is_axis=True,
                    discovered_by=[DiscoveryProtocol.SSDP]),
                DiscoveredDevice(
                    ip_address="192.0.2.1", serial_number="1J72450M0",
                    model="GR6EXX0C", discovered_by=[DiscoveryProtocol.SSDP]),
            ]),
            FakeProtocol("arp", [
                DiscoveredDevice(ip_address="192.0.2.41", mac_address=cam,
                                 is_axis=True, discovered_by=[DiscoveryProtocol.ARP]),
                DiscoveredDevice(ip_address="192.0.2.1", mac_address="5C:35:FC:00:00:01",
                                 discovered_by=[DiscoveryProtocol.ARP]),
            ]),
        ]
        records = [scan_record(d) for d in await orch.run()]
        assert [r["device_id"] for r in records] == ["E82725000041", "5C35FC000001"]
        assert (records[0]["model"], records[0]["hostname"]) == (
            "AXIS P3408-VE", "axis-e82725000041.local")
        assert records[0]["discovered_by"] == ["mdns", "arp", "ssdp"]

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
