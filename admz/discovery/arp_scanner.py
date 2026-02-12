"""
ARP-based subnet scanner.

Sends ARP "who-has" requests for every IP in a /24 subnet and collects
responses to build an IP → MAC mapping.  Filters by Axis OUI prefixes.

Requires: pip install scapy   (and root / CAP_NET_RAW privileges)
"""

import asyncio
import logging
import socket
from typing import List, Optional

from admz.discovery.base import DiscoveryProtocolBase
from admz.discovery.models import (
    DiscoveredDevice,
    DiscoveryProtocol,
    is_axis_mac,
)

logger = logging.getLogger(__name__)


def _get_local_subnet() -> Optional[str]:
    """Best-effort detection of the local /24 subnet in CIDR notation."""
    try:
        # Connect to a non-routable address to discover the default interface IP.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        # Assume /24
        parts = ip.split(".")
        parts[3] = "0"
        return ".".join(parts) + "/24"
    except Exception:
        return None


class ARPScanner(DiscoveryProtocolBase):
    """Discover devices via ARP broadcast on the local subnet."""

    def __init__(self, subnet: Optional[str] = None, axis_only: bool = False):
        """
        Args:
            subnet: CIDR subnet to scan (e.g. '192.168.1.0/24').
                    Auto-detected if not provided.
            axis_only: If True, only return devices with Axis OUI prefixes.
        """
        self._subnet = subnet
        self._axis_only = axis_only

    @property
    def name(self) -> str:
        return "ARP Scanner"

    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        try:
            from scapy.all import ARP, Ether, srp
        except ImportError:
            logger.warning(
                "scapy library not installed — skipping ARP scan. "
                "Install with: pip install scapy"
            )
            return []

        subnet = self._subnet or _get_local_subnet()
        if not subnet:
            logger.warning("Could not detect local subnet for ARP scan")
            return []

        logger.info("ARP scanning subnet %s", subnet)
        loop = asyncio.get_event_loop()

        def _scan():
            arp = ARP(pdst=subnet)
            ether = Ether(dst="ff:ff:ff:ff:ff:ff")
            packet = ether / arp
            answered, _ = srp(packet, timeout=timeout, verbose=False)
            return answered

        try:
            answered = await loop.run_in_executor(None, _scan)
        except PermissionError:
            logger.warning(
                "ARP scan requires root or CAP_NET_RAW — skipping"
            )
            return []

        devices: List[DiscoveredDevice] = []
        for _, recv in answered:
            ip = recv.psrc
            mac = recv.hwsrc.upper()
            mac = mac.replace("-", ":")

            axis = is_axis_mac(mac)
            if self._axis_only and not axis:
                continue

            dev = DiscoveredDevice(
                ip_address=ip,
                mac_address=mac,
                is_axis=axis,
            )
            if axis:
                dev.manufacturer = "Axis Communications"
            dev.discovered_by.append(DiscoveryProtocol.ARP)
            devices.append(dev)

        return devices
