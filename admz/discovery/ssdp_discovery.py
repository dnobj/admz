"""
SSDP / UPnP device discovery.

Sends M-SEARCH multicast to 239.255.255.250:1900 and parses responses.
Optionally fetches the UPnP XML device description for richer metadata.

The socket receive loop uses a blocking socket with a short timeout
(``settimeout(0.5)``) running inside ``loop.run_in_executor``.  This
is critical on Windows where the previous approach of ``settimeout(0)``
(non-blocking) caused the executor thread to immediately raise
``BlockingIOError`` on every ``recvfrom``, creating a busy-loop that
almost never caught real responses.
"""

import asyncio
import logging
import socket
import struct
import time
from typing import Dict, List, Optional
from xml.etree import ElementTree

from admz.discovery.base import DiscoveryProtocolBase
from admz.ssl_config import verify_ssl_default
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
    'MAN: "ssdp:discover"\r\n'
    "MX: {mx}\r\n"
    "ST: {st}\r\n"
    "\r\n"
)

# Search targets: ssdp:all catches everything; the Axis-specific URN
# catches only Axis devices when available.
SEARCH_TARGETS = [
    "ssdp:all",
]


def _get_local_ip() -> str:
    """Return the local IP used for the default route.

    We connect to a public unicast address (not a multicast address)
    because on Windows with Hyper-V/WSL virtual NICs, connecting to a
    multicast address may route through the wrong interface.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 53))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


class SSDPDiscovery(DiscoveryProtocolBase):
    """Discover devices via SSDP M-SEARCH multicast."""

    @property
    def name(self) -> str:
        return "SSDP/UPnP"

    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        devices: Dict[str, DiscoveredDevice] = {}
        loop = asyncio.get_event_loop()

        local_ip = _get_local_ip()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to the specific local interface so responses return here.
        # Using port 0 lets the OS pick an ephemeral port (we do not need
        # to listen on port 1900; M-SEARCH responses are unicast back to
        # the sender's source port).
        if local_ip:
            sock.bind((local_ip, 0))
        else:
            sock.bind(("", 0))

        # Use a SHORT BLOCKING timeout -- NOT 0 (non-blocking).
        #
        # The old code used ``sock.settimeout(0)`` which made recvfrom()
        # immediately raise ``BlockingIOError`` every time it was called
        # in the executor thread, producing a busy-loop that almost never
        # caught actual UDP responses.  A 0.5-second blocking timeout lets
        # the kernel wake the thread when data arrives while still allowing
        # periodic checks for the overall deadline.
        sock.settimeout(0.5)

        # Send M-SEARCH for each target
        mx = max(1, int(timeout) - 1)
        for st in SEARCH_TARGETS:
            msg = M_SEARCH_TEMPLATE.format(mx=mx, st=st).encode()
            try:
                sock.sendto(msg, (SSDP_MULTICAST, SSDP_PORT))
            except OSError as exc:
                logger.debug("SSDP sendto failed: %s", exc)

        # Collect responses in a blocking thread with short recv timeout
        stop_time = time.monotonic() + timeout

        def _recv_loop():
            results = []
            while time.monotonic() < stop_time:
                try:
                    data, addr = sock.recvfrom(4096)
                    text = data.decode(errors="replace")
                    headers = _parse_ssdp_response(text)
                    if headers:
                        results.append((addr[0], headers))
                except socket.timeout:
                    # No data within the 0.5s window -- loop back and
                    # check the deadline.
                    continue
                except OSError:
                    continue
            return results

        responses = await loop.run_in_executor(None, _recv_loop)
        sock.close()

        # Build DiscoveredDevice objects from responses
        for ip, headers in responses:
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
            logger.debug("httpx not installed -- skipping UPnP XML enrichment")
            return

        async with httpx.AsyncClient(timeout=timeout, verify=verify_ssl_default()) as client:
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
