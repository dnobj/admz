"""
Data models for network device discovery.
"""

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set


class DiscoveryProtocol(enum.Enum):
    """Protocols that can discover a device."""

    ARP = "arp"
    MDNS = "mdns"
    SSDP = "ssdp"
    ONVIF = "onvif"
    PING = "ping"
    HTTP_PROBE = "http_probe"
    SNMP = "snmp"


class DeviceType(enum.Enum):
    """High-level device classification."""

    CAMERA = "camera"
    ENCODER = "encoder"
    SPEAKER = "speaker"
    IO_MODULE = "io_module"
    RADAR = "radar"
    INTERCOM = "intercom"
    ACCESS_CONTROL = "access_control"
    NETWORK_SWITCH = "network_switch"
    UNKNOWN = "unknown"


# Known Axis Communications OUI prefixes (uppercase, colon-separated).
AXIS_OUI_PREFIXES: Set[str] = {
    "00:40:8C",
    "AC:CC:8E",
    "B8:A4:4F",
    "E8:27:25",
}


def is_axis_mac(mac: str) -> bool:
    """Return True if *mac* matches a known Axis Communications OUI."""
    normalized = mac.upper().replace("-", ":")
    prefix = normalized[:8]
    return prefix in AXIS_OUI_PREFIXES


@dataclass
class DiscoveredDevice:
    """
    A device found on the local network.

    Instances are keyed by *mac_address* so that results from multiple
    discovery protocols can be merged into a single record.
    """

    # Identity (at least one of ip/mac must be set)
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None

    # Metadata populated by various protocols
    hostname: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    manufacturer: Optional[str] = None
    friendly_name: Optional[str] = None
    device_type: DeviceType = DeviceType.UNKNOWN

    # ONVIF-specific
    onvif_xaddrs: Optional[str] = None
    onvif_scopes: List[str] = field(default_factory=list)

    # mDNS-specific
    mdns_name: Optional[str] = None
    mdns_services: List[str] = field(default_factory=list)

    # SSDP/UPnP-specific
    ssdp_location: Optional[str] = None
    ssdp_server: Optional[str] = None
    ssdp_usn: Optional[str] = None

    # HTTP probe
    http_server_header: Optional[str] = None
    vapix_available: bool = False

    # SNMP
    snmp_sys_descr: Optional[str] = None
    snmp_sys_name: Optional[str] = None

    # Tracking
    discovered_by: List[DiscoveryProtocol] = field(default_factory=list)
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    is_axis: bool = False

    # Raw per-protocol payloads (for debugging / extension)
    raw: Dict[str, dict] = field(default_factory=dict)

    def merge(self, other: "DiscoveredDevice") -> None:
        """
        Merge *other* into this device, filling in any ``None`` fields and
        appending to list fields.  The merge is additive — it never
        overwrites a non-``None`` value with ``None``.
        """
        for fld in (
            "ip_address",
            "mac_address",
            "hostname",
            "model",
            "serial_number",
            "firmware_version",
            "manufacturer",
            "friendly_name",
            "onvif_xaddrs",
            "mdns_name",
            "ssdp_location",
            "ssdp_server",
            "ssdp_usn",
            "http_server_header",
            "snmp_sys_descr",
            "snmp_sys_name",
        ):
            other_val = getattr(other, fld)
            if other_val is not None and getattr(self, fld) is None:
                setattr(self, fld, other_val)

        # Prefer a concrete device type over UNKNOWN
        if self.device_type == DeviceType.UNKNOWN and other.device_type != DeviceType.UNKNOWN:
            self.device_type = other.device_type

        # Merge boolean flags
        self.vapix_available = self.vapix_available or other.vapix_available
        self.is_axis = self.is_axis or other.is_axis

        # Merge lists (deduplicate)
        for list_fld in ("onvif_scopes", "mdns_services", "discovered_by"):
            existing = getattr(self, list_fld)
            for item in getattr(other, list_fld):
                if item not in existing:
                    existing.append(item)

        # Update timestamps
        if other.first_seen < self.first_seen:
            self.first_seen = other.first_seen
        if other.last_seen > self.last_seen:
            self.last_seen = other.last_seen

        # Merge raw payloads
        self.raw.update(other.raw)

    def to_registry_dict(self) -> Dict:
        """Convert to a dict compatible with ``DeviceRegistry.add_device``."""
        return {
            "host": self.ip_address or "",
            "ip_address": self.ip_address or "",
            "mac_address": self.mac_address or "",
            "serial_number": self.serial_number or "",
            "model": self.model or "",
            "firmware_version": self.firmware_version or "",
            "nickname": self.friendly_name or self.hostname or "",
            "manufacturer": self.manufacturer or "",
            "device_type": self.device_type.value,
            "tags": self._auto_tags(),
            "metadata": {
                "discovered_by": [p.value for p in self.discovered_by],
                "first_seen": self.first_seen.isoformat(),
                "last_seen": self.last_seen.isoformat(),
                "is_axis": self.is_axis,
                "onvif_xaddrs": self.onvif_xaddrs,
                "vapix_available": self.vapix_available,
            },
        }

    def _auto_tags(self) -> List[str]:
        tags: List[str] = []
        if self.is_axis:
            tags.append("axis")
        if self.device_type != DeviceType.UNKNOWN:
            tags.append(self.device_type.value)
        if self.vapix_available:
            tags.append("vapix")
        if self.onvif_xaddrs:
            tags.append("onvif")
        return tags
