"""
ONVIF / WS-Discovery device discovery.

Sends a WS-Discovery Probe multicast for ONVIF-compliant network video
devices (type ``tdn:NetworkVideoTransmitter``).

Requires: pip install WSDiscovery
"""

import asyncio
import logging
import re
from typing import List, Optional

from admz.discovery.base import DiscoveryProtocolBase
from admz.discovery.models import (
    DiscoveredDevice,
    DiscoveryProtocol,
    DeviceType,
)

logger = logging.getLogger(__name__)

# ONVIF scope prefixes that reveal device metadata.
_SCOPE_RE = {
    "name": re.compile(r"onvif://www\.onvif\.org/name/(.+)", re.I),
    "hardware": re.compile(r"onvif://www\.onvif\.org/hardware/(.+)", re.I),
    "location": re.compile(r"onvif://www\.onvif\.org/location/(.+)", re.I),
    "type": re.compile(r"onvif://www\.onvif\.org/type/(.+)", re.I),
    "profile": re.compile(r"onvif://www\.onvif\.org/Profile/(.+)", re.I),
}

# XAddrs URL pattern to extract IP.
_IP_RE = re.compile(r"https?://(\d+\.\d+\.\d+\.\d+)[:/]")


class ONVIFDiscovery(DiscoveryProtocolBase):
    """Discover ONVIF cameras via WS-Discovery Probe."""

    @property
    def name(self) -> str:
        return "ONVIF/WS-Discovery"

    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        try:
            from WSDiscovery import WSDiscovery as _WSDiscovery
        except ImportError:
            logger.warning(
                "WSDiscovery library not installed — skipping ONVIF discovery. "
                "Install with: pip install WSDiscovery"
            )
            return []

        loop = asyncio.get_event_loop()

        # WSDiscovery is synchronous — run in a thread executor.
        def _probe() -> list:
            wsd = _WSDiscovery()
            wsd.start()
            # Search for ONVIF NetworkVideoTransmitter devices.
            services = wsd.searchServices(
                types=[
                    "{http://www.onvif.org/ver10/network/wsdl}NetworkVideoTransmitter"
                ],
                timeout=int(timeout),
            )
            wsd.stop()
            return services

        try:
            services = await asyncio.wait_for(
                loop.run_in_executor(None, _probe),
                timeout=timeout + 5,
            )
        except asyncio.TimeoutError:
            logger.warning("ONVIF WS-Discovery timed out")
            return []

        devices: List[DiscoveredDevice] = []
        for svc in services:
            dev = self._service_to_device(svc)
            if dev:
                devices.append(dev)

        return devices

    def _service_to_device(self, svc) -> Optional[DiscoveredDevice]:
        """Convert a WSDiscovery service object to a DiscoveredDevice."""
        xaddrs = " ".join(svc.getXAddrs()) if svc.getXAddrs() else ""
        scopes = [str(s) for s in (svc.getScopes() or [])]

        # Extract IP from XAddrs
        ip_match = _IP_RE.search(xaddrs)
        ip = ip_match.group(1) if ip_match else None
        if not ip:
            return None

        dev = DiscoveredDevice(ip_address=ip)
        dev.onvif_xaddrs = xaddrs
        dev.onvif_scopes = scopes
        dev.discovered_by.append(DiscoveryProtocol.ONVIF)
        dev.device_type = DeviceType.CAMERA

        # Parse scopes for metadata
        for scope in scopes:
            for field_name, pattern in _SCOPE_RE.items():
                m = pattern.match(scope)
                if not m:
                    continue
                value = m.group(1).replace("%20", " ")
                if field_name == "name":
                    dev.friendly_name = dev.friendly_name or value
                elif field_name == "hardware":
                    dev.model = dev.model or value
                elif field_name == "location":
                    pass  # location is free-form; not mapping to device fields
                elif field_name == "type":
                    if "video" in value.lower() or "transmitter" in value.lower():
                        dev.device_type = DeviceType.CAMERA

        # If manufacturer not set, check scopes for axis mentions
        scope_str = " ".join(scopes).lower()
        if "axis" in scope_str:
            dev.is_axis = True
            dev.manufacturer = "Axis Communications"

        return dev
