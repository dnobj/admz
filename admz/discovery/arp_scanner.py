"""
ARP-based subnet scanner.

Sends ARP "who-has" requests for every IP in a /24 subnet and collects
responses to build an IP → MAC mapping.  Filters by Axis OUI prefixes.

When scapy is not available (or lacks privileges), falls back to reading
the OS ARP table via ``arp -a``.

Requires (for active scan): pip install scapy  (and root / CAP_NET_RAW)
"""

import asyncio
import ipaddress
import logging
import re
import socket
import subprocess
import sys
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


def _parse_arp_table(output: str, subnet: Optional[str] = None) -> List[DiscoveredDevice]:
    """Parse ``arp -a`` output into DiscoveredDevice list.

    Works with both Windows and Unix formats:
      Windows:  ``  192.168.1.123         e8-27-25-09-59-c6     dynamic``
      Unix:     ``? (192.168.1.123) at e8:27:25:09:59:c6 [ether] on eth0``
    """
    # Build a network object for subnet filtering
    network = None
    if subnet:
        try:
            network = ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            pass

    # Match IP + MAC pairs in either format
    # Windows: dashes, Unix: colons
    pattern = re.compile(
        r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+"
        r"([0-9a-fA-F]{2}[:\-][0-9a-fA-F]{2}[:\-][0-9a-fA-F]{2}[:\-]"
        r"[0-9a-fA-F]{2}[:\-][0-9a-fA-F]{2}[:\-][0-9a-fA-F]{2})"
    )

    devices: List[DiscoveredDevice] = []
    seen_ips = set()

    for match in pattern.finditer(output):
        ip = match.group(1)
        mac = match.group(2).upper().replace("-", ":")

        # Skip broadcast / multicast MACs
        if mac.startswith("FF:FF:FF") or mac.startswith("01:00:5E"):
            continue

        # Skip if outside requested subnet
        if network:
            try:
                if ipaddress.ip_address(ip) not in network:
                    continue
            except ValueError:
                continue

        if ip in seen_ips:
            continue
        seen_ips.add(ip)

        axis = is_axis_mac(mac)
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


def _merge_device_lists(
    primary: List[DiscoveredDevice],
    secondary: List[DiscoveredDevice],
) -> List[DiscoveredDevice]:
    """Merge two device lists, deduplicating by IP address."""
    by_ip = {d.ip_address: d for d in primary if d.ip_address}
    for dev in secondary:
        if dev.ip_address and dev.ip_address not in by_ip:
            by_ip[dev.ip_address] = dev
    return list(by_ip.values())


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
        # Try scapy for active ARP scan
        devices = await self._scapy_scan(timeout)

        # Always merge in the OS ARP table — it catches devices that
        # scapy misses (e.g. WiFi multicast filtering, permissions).
        table_devices = await self._arp_table_fallback()
        devices = _merge_device_lists(devices, table_devices)

        if self._axis_only:
            devices = [d for d in devices if d.is_axis]

        return devices

    async def _scapy_scan(self, timeout: float) -> List[DiscoveredDevice]:
        """Active ARP scan using scapy (requires scapy + raw socket privileges)."""
        try:
            from scapy.all import ARP, Ether, srp
        except ImportError:
            logger.info(
                "scapy not installed — will fall back to OS ARP table"
            )
            return []

        subnet = self._subnet or _get_local_subnet()
        if not subnet:
            logger.warning("Could not detect local subnet for ARP scan")
            return []

        logger.info("ARP scanning subnet %s (scapy)", subnet)
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
                "ARP scan requires root or CAP_NET_RAW — will fall back to OS ARP table"
            )
            return []

        devices: List[DiscoveredDevice] = []
        for _, recv in answered:
            ip = recv.psrc
            mac = recv.hwsrc.upper()
            mac = mac.replace("-", ":")

            axis = is_axis_mac(mac)
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

    async def _arp_table_fallback(self) -> List[DiscoveredDevice]:
        """Read the OS ARP table as a fallback when scapy is unavailable."""
        subnet = self._subnet or _get_local_subnet()
        logger.info("Reading OS ARP table (fallback)%s",
                     f" filtering to {subnet}" if subnet else "")

        loop = asyncio.get_event_loop()

        def _read_arp():
            cmd = ["arp", "-a"]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
            )
            return result.stdout

        try:
            output = await loop.run_in_executor(None, _read_arp)
        except Exception as exc:
            logger.warning("Failed to read ARP table: %s", exc)
            return []

        return _parse_arp_table(output, subnet=subnet)
