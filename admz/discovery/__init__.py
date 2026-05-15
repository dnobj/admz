"""
Network device discovery for ADMZ.

Discovers Axis cameras and other devices on the local network using
multiple protocols run concurrently:

- mDNS / Zeroconf / Bonjour  (``_axis-video._tcp``)
- SSDP / UPnP
- ONVIF / WS-Discovery
- ARP subnet scanning
- ICMP ping sweep
- HTTP / VAPIX header probing
- SNMP sysDescr enrichment

Usage::

    import asyncio
    from admz.discovery import discover_devices

    devices = asyncio.run(discover_devices(timeout=5.0))
    for dev in devices:
        print(f"{dev.ip_address}  {dev.model}  axis={dev.is_axis}")
"""

from admz.discovery.models import (
    DiscoveredDevice,
    DiscoveryProtocol,
    DeviceType,
    AXIS_OUI_PREFIXES,
    is_axis_mac,
)
from admz.discovery.orchestrator import (
    DiscoveryOrchestrator,
    discover_devices,
)
from admz.discovery.credential_probe import (
    probe_credentials,
    ProbeResult,
    ProbeStatus,
)

__all__ = [
    "discover_devices",
    "DiscoveryOrchestrator",
    "DiscoveredDevice",
    "DiscoveryProtocol",
    "DeviceType",
    "AXIS_OUI_PREFIXES",
    "is_axis_mac",
    "probe_credentials",
    "ProbeResult",
    "ProbeStatus",
]
