"""
mDNS / Zeroconf / Bonjour device discovery.

Browses for Axis-specific service types on the local network:
  - _axis-video._tcp.local.
  - _http._tcp.local.

Requires: pip install zeroconf
"""

import asyncio
import logging
import sys
from typing import Dict, List, Optional

from admz.discovery.base import DiscoveryProtocolBase
from admz.discovery.models import (
    DiscoveredDevice,
    DiscoveryProtocol,
    DeviceType,
    is_axis_mac,
)

logger = logging.getLogger(__name__)

# Service types to browse.  The first is Axis-specific; the second is
# generic HTTP which sometimes catches Axis devices too.
AXIS_SERVICE_TYPES = [
    "_axis-video._tcp.local.",
]

GENERAL_SERVICE_TYPES = [
    "_http._tcp.local.",
]


class MDNSDiscovery(DiscoveryProtocolBase):
    """Discover devices via mDNS/Zeroconf multicast."""

    @property
    def name(self) -> str:
        return "mDNS/Zeroconf"

    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        try:
            from zeroconf import IPVersion, ServiceStateChange, Zeroconf
            from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf
        except ImportError:
            logger.warning(
                "zeroconf library not installed — skipping mDNS discovery. "
                "Install with: pip install zeroconf"
            )
            return []

        devices: Dict[str, DiscoveredDevice] = {}

        class _Listener:
            def __init__(self, azc: AsyncZeroconf):
                self.azc = azc

            def _handle(
                self,
                zeroconf: Zeroconf = None,
                service_type: str = "",
                name: str = "",
                state_change: ServiceStateChange = None,
                **kwargs,
            ) -> None:
                if state_change != ServiceStateChange.Added:
                    return
                asyncio.ensure_future(self._resolve(zeroconf, service_type, name))

            async def _resolve(
                self, zc: Zeroconf, service_type: str, name: str
            ) -> None:
                info = await self.azc.async_get_service_info(service_type, name)
                if info is None:
                    return

                addresses = info.parsed_addresses(IPVersion.V4Only)
                if not addresses:
                    return

                ip = addresses[0]
                mac: Optional[str] = None

                # Try to extract MAC from TXT records
                props = {
                    k.decode() if isinstance(k, bytes) else k: (
                        v.decode() if isinstance(v, bytes) else v
                    )
                    for k, v in (info.properties or {}).items()
                }
                mac = props.get("macaddress") or props.get("mac")
                if mac:
                    # Normalise to colon-separated uppercase
                    mac = _normalise_mac(mac)

                key = mac or ip
                dev = devices.get(key)
                if dev is None:
                    dev = DiscoveredDevice(ip_address=ip, mac_address=mac)
                    devices[key] = dev

                dev.ip_address = dev.ip_address or ip
                dev.mac_address = dev.mac_address or mac
                dev.mdns_name = info.server
                dev.hostname = (info.server or "").rstrip(".")

                if service_type not in dev.mdns_services:
                    dev.mdns_services.append(service_type)
                if DiscoveryProtocol.MDNS not in dev.discovered_by:
                    dev.discovered_by.append(DiscoveryProtocol.MDNS)

                # Populate metadata from TXT records
                dev.model = dev.model or props.get("model")
                dev.serial_number = dev.serial_number or props.get("serialnumber")
                dev.firmware_version = dev.firmware_version or props.get("firmware")
                dev.friendly_name = dev.friendly_name or props.get("friendlyname") or info.name.split(".")[0]

                # Detect Axis
                if mac and is_axis_mac(mac):
                    dev.is_axis = True
                    dev.manufacturer = "Axis Communications"
                if "_axis-video" in service_type:
                    dev.is_axis = True
                    dev.manufacturer = "Axis Communications"
                    if dev.device_type == DeviceType.UNKNOWN:
                        dev.device_type = DeviceType.CAMERA

        # On Windows, zeroconf requires SelectorEventLoop for UDP multicast.
        # ProactorEventLoop (the default) silently fails to receive datagrams.
        if sys.platform == "win32":
            return await self._discover_via_selector(
                devices, _Listener, IPVersion, AsyncZeroconf,
                AsyncServiceBrowser, timeout,
            )

        azc = AsyncZeroconf(ip_version=IPVersion.V4Only)
        listener = _Listener(azc)

        all_types = AXIS_SERVICE_TYPES + GENERAL_SERVICE_TYPES
        browsers = []
        for stype in all_types:
            browser = AsyncServiceBrowser(
                azc.zeroconf,
                stype,
                handlers=[listener._handle],
            )
            browsers.append(browser)

        # Wait for responses
        await asyncio.sleep(timeout)

        # Clean up
        for browser in browsers:
            await browser.async_cancel()
        await azc.async_close()

        return list(devices.values())

    async def _discover_via_selector(
        self, devices, _Listener, IPVersion, AsyncZeroconf,
        AsyncServiceBrowser, timeout,
    ):
        """Run mDNS discovery in a SelectorEventLoop thread on Windows."""
        loop = asyncio.get_event_loop()

        def _run_in_selector():
            """Run zeroconf browse inside a dedicated SelectorEventLoop."""
            sel_loop = asyncio.SelectorEventLoop()
            return sel_loop.run_until_complete(
                self._browse(devices, _Listener, IPVersion, AsyncZeroconf,
                             AsyncServiceBrowser, timeout)
            )

        return await loop.run_in_executor(None, _run_in_selector)

    async def _browse(
        self, devices, _Listener, IPVersion, AsyncZeroconf,
        AsyncServiceBrowser, timeout,
    ):
        """Core browse logic that runs inside any event loop."""
        azc = AsyncZeroconf(ip_version=IPVersion.V4Only)
        listener = _Listener(azc)

        all_types = AXIS_SERVICE_TYPES + GENERAL_SERVICE_TYPES
        browsers = []
        for stype in all_types:
            browser = AsyncServiceBrowser(
                azc.zeroconf,
                stype,
                handlers=[listener._handle],
            )
            browsers.append(browser)

        await asyncio.sleep(timeout)

        for browser in browsers:
            await browser.async_cancel()
        await azc.async_close()

        return list(devices.values())


def _normalise_mac(mac: str) -> str:
    """Normalise a MAC address to ``AA:BB:CC:DD:EE:FF`` format."""
    clean = mac.upper().replace("-", ":").replace(".", "")
    if ":" not in clean and len(clean) == 12:
        clean = ":".join(clean[i : i + 2] for i in range(0, 12, 2))
    return clean
