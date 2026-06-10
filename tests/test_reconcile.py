"""Tests for MAC-based IP reconciliation (admz/discovery/reconcile.py).

The real case: the I8016 (MAC B8A44F0C5B32) was registered at .207 but DHCP
moved it to .208; reconcile should follow the MAC and correct the host.
"""

import pytest

from admz.discovery.reconcile import normalize_mac, reconcile_device_ips


class _Disc:
    """Stand-in for a DiscoveredDevice."""
    def __init__(self, mac, ip):
        self.mac_address = mac
        self.ip_address = ip


class _Registry:
    def __init__(self, devices):
        self._devices = devices
        self.updates = []

    def list_devices(self):
        return self._devices

    def update_device_info(self, device_id, updates):
        self.updates.append((device_id, updates))
        for d in self._devices:
            if d["device_id"] == device_id:
                d.update(updates)


@pytest.mark.parametrize("raw,expected", [
    ("B8:A4:4F:0C:5B:32", "B8A44F0C5B32"),
    ("b8-a4-4f-0c-5b-32", "B8A44F0C5B32"),
    ("B8A44F0C5B32", "B8A44F0C5B32"),
    ("", ""),
    (None, ""),
])
def test_normalize_mac(raw, expected):
    assert normalize_mac(raw) == expected


def test_moved_device_is_corrected():
    """The I8016 scenario: MAC now at a new IP."""
    reg = _Registry([{"device_id": "B8A44F0C5B32", "host": "192.168.1.207"}])
    discovered = [_Disc("B8:A4:4F:0C:5B:32", "192.168.1.208")]
    changes = reconcile_device_ips(reg, discovered)
    assert changes == [{"device_id": "B8A44F0C5B32",
                        "old_host": "192.168.1.207", "new_ip": "192.168.1.208"}]
    assert reg.updates == [("B8A44F0C5B32", {"host": "192.168.1.208"})]


def test_device_at_correct_ip_untouched():
    reg = _Registry([{"device_id": "B8A44F0C5B32", "host": "192.168.1.208"}])
    discovered = [_Disc("B8:A4:4F:0C:5B:32", "192.168.1.208")]
    assert reconcile_device_ips(reg, discovered) == []
    assert reg.updates == []


def test_undiscovered_device_untouched():
    """A device discovery didn't see (e.g. powered off) is left alone."""
    reg = _Registry([{"device_id": "B8A44FFC2B16", "host": "192.168.1.147"}])
    discovered = [_Disc("B8:A4:4F:0C:5B:32", "192.168.1.208")]  # a different device
    assert reconcile_device_ips(reg, discovered) == []
    assert reg.updates == []


def test_match_via_explicit_mac_field():
    """device_id isn't the MAC, but the stored mac_address is."""
    reg = _Registry([{
        "device_id": "custom-name", "mac_address": "B8:A4:4F:0C:5B:32",
        "host": "192.168.1.207",
    }])
    discovered = [_Disc("b8-a4-4f-0c-5b-32", "192.168.1.208")]
    changes = reconcile_device_ips(reg, discovered)
    assert changes == [{"device_id": "custom-name",
                        "old_host": "192.168.1.207", "new_ip": "192.168.1.208"}]


def test_accepts_dict_discovered():
    reg = _Registry([{"device_id": "B8A44F0C5B32", "host": "192.168.1.207"}])
    discovered = [{"mac_address": "B8A44F0C5B32", "ip_address": "192.168.1.208"}]
    changes = reconcile_device_ips(reg, discovered)
    assert changes[0]["new_ip"] == "192.168.1.208"


def test_update_failure_recorded_not_raised():
    class _BadRegistry(_Registry):
        def update_device_info(self, device_id, updates):
            raise NotImplementedError("Vault has no update_device_info")

    reg = _BadRegistry([{"device_id": "B8A44F0C5B32", "host": "192.168.1.207"}])
    changes = reconcile_device_ips(reg, [_Disc("B8A44F0C5B32", "192.168.1.208")])
    assert len(changes) == 1
    assert "error" in changes[0]


def test_mixed_fleet():
    reg = _Registry([
        {"device_id": "AAA1", "host": "10.0.0.1"},   # moved
        {"device_id": "BBB2", "host": "10.0.0.2"},   # same
        {"device_id": "CCC3", "host": "10.0.0.9"},   # not discovered
    ])
    discovered = [
        _Disc("AAA1", "10.0.0.5"),
        _Disc("BBB2", "10.0.0.2"),
    ]
    changes = reconcile_device_ips(reg, discovered)
    assert len(changes) == 1
    assert changes[0]["device_id"] == "AAA1"
    assert changes[0]["new_ip"] == "10.0.0.5"
