"""
SSDP / UPnP device discovery.

Sends M-SEARCH multicast to 239.255.255.250:1900 and parses responses.
Optionally fetches the UPnP XML device description for richer metadata.

Requires: pip install async-upnp-client   (or falls back to raw sockets)
"""

import asyncio
import logging
import re
import socket
import struct
from typing import Dict, List, Optional
from xml.etree import ElementTree

from admz.discovery.base import DiscoveryProtocolBase
from admz.discovery.models import (
    DiscoveredDevice,
    DiscoveryProtocol,
    DeviceType,
    is_axis_mac,
)

logger = logging.getLogger(__name__)

SSDP_MULTICAST = "239.255.255.250"
SSDP_PORT = 1900

M_SEARCH_TEMPLATE = (
    "M-SEARCH * HTTP/1.1\r\n"
    "HOST: 239.255.255.250:1900\r\n"
    "MAN: \"ssdp:discover\"\r\n"
    "MX: {mx}\r\n"
    "ST: {st}\r\n"
    "\r\n"
)

# Search targets: ssdp:all catches everything; the Axis-specific URN
# catches only Axis devices when available.
SEARCH_TARGETS = [
    "ssdp:all",
]


class SSDPDiscovery(DiscoveryProtocolBase):
    """Discover devices via SSDP M-SEARCH multicast."""

    @property
    def name(self) -> str:
        return "SSDP/UPnP"

    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        devices: Dict[str, DiscoveredDevice] = {}

        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0)

        # Join multicast group on all interfaces
        mreq = struct.pack("4sL", socket.inet_aton(SSDP_MULTICAST), socket.INADDR_ANY)
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except OSError:
            logger.debug("Could not join SSDP multicast group")

        # Send M-SEARCH for each target
        mx = max(1, int(timeout) - 1)
        for st in SEARCH_TARGETS:
            msg = M_SEARCH_TEMPLATE.format(mx=mx, st=st).encode()
            try:
                sock.sendto(msg, (SSDP_MULTICAST, SSDP_PORT))
            except OSError as exc:
                logger.debug("SSDP sendto failed: %s", exc)

        # Collect responses
        end = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < end:
            try:
                data, addr = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: sock.recvfrom(4096)),
                    timeout=max(0.1, end - asyncio.get_event_loop().time()),
                )
            except (asyncio.TimeoutError, OSError):
                continue

            ip = addr[0]
            headers = _parse_ssdp_response(data.decode(errors="replace"))
            if not headers:
                continue

            key = ip
            dev = devices.get(key)
            if dev is None:
                dev = DiscoveredDevice(ip_address=ip)
                devices[key] = dev

            dev.ssdp_location = headers.get("LOCATION") or dev.ssdp_location
            dev.ssdp_server = headers.get("SERVER") or dev.ssdp_server
            dev.ssdp_usn = headers.get("USN") or dev.ssdp_usn

            if DiscoveryProtocol.SSDP not in dev.discovered_by:
                dev.discovered_by.append(DiscoveryProtocol.SSDP)

            # Detect Axis from SERVER header
            server = (headers.get("SERVER") or "").lower()
            if "axis" in server:
                dev.is_axis = True
                dev.manufacturer = "Axis Communications"

        sock.close()

        # Optionally fetch UPnP XML descriptions for richer metadata
        await self._enrich_from_descriptions(devices, timeout=min(timeout, 3.0))

        return list(devices.values())

    async def _enrich_from_descriptions(
        self, devices: Dict[str, DiscoveredDevice], timeout: float
    ) -> None:
        """Fetch UPnP device description XML for devices that have a LOCATION."""
        try:
            import httpx
        except ImportError:
            logger.debug("httpx not installed — skipping UPnP XML enrichment")
            return

        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            tasks = []
            for dev in devices.values():
                if dev.ssdp_location:
                    tasks.append(self._fetch_description(client, dev))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_description(self, client, dev: DiscoveredDevice) -> None:
        """Parse a UPnP device description XML."""
        try:
            resp = await client.get(dev.ssdp_location)
            if resp.status_code != 200:
                return
            root = ElementTree.fromstring(resp.text)
        except Exception:
            return

        ns = {"upnp": "urn:schemas-upnp-org:device-1-0"}
        device_el = root.find(".//upnp:device", ns)
        if device_el is None:
            return

        dev.friendly_name = dev.friendly_name or _text(device_el, "upnp:friendlyName", ns)
        dev.manufacturer = dev.manufacturer or _text(device_el, "upnp:manufacturer", ns)
        dev.model = dev.model or _text(device_el, "upnp:modelName", ns)
        dev.serial_number = dev.serial_number or _text(device_el, "upnp:serialNumber", ns)

        if dev.manufacturer and "axis" in dev.manufacturer.lower():
            dev.is_axis = True
            if dev.device_type == DeviceType.UNKNOWN:
                dev.device_type = DeviceType.CAMERA


def _text(el, path: str, ns: dict) -> Optional[str]:
    child = el.find(path, ns)
    return child.text.strip() if child is not None and child.text else None


def _parse_ssdp_response(data: str) -> Optional[Dict[str, str]]:
    """Parse an SSDP/HTTP-like response into a header dict."""
    headers: Dict[str, str] = {}
    for line in data.split("\r\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().upper()] = value.strip()
    return headers if headers else None
