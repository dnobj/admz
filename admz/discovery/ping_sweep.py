"""
ICMP ping sweep for host liveness detection.

Pings a range of IPs concurrently and returns those that respond.
Uses the system ``ping`` command so no special privileges are needed
beyond what the OS normally grants.
"""

import asyncio
import logging
import platform
import socket
from typing import List, Optional

from admz.discovery.base import DiscoveryProtocolBase
from admz.discovery.models import DiscoveredDevice, DiscoveryProtocol

logger = logging.getLogger(__name__)


def _get_local_prefix() -> Optional[str]:
    """Return the first three octets of the default interface IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ".".join(ip.split(".")[:3])
    except Exception:
        return None


class PingSweep(DiscoveryProtocolBase):
    """Discover live hosts via ICMP echo (system ping)."""

    def __init__(
        self,
        subnet_prefix: Optional[str] = None,
        start: int = 1,
        end: int = 254,
    ):
        """
        Args:
            subnet_prefix: First three octets (e.g. '192.168.1').
                           Auto-detected if not provided.
            start: First host octet to scan (inclusive).
            end: Last host octet to scan (inclusive).
        """
        self._prefix = subnet_prefix
        self._start = start
        self._end = end

    @property
    def name(self) -> str:
        return "ICMP Ping Sweep"

    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        prefix = self._prefix or _get_local_prefix()
        if not prefix:
            logger.warning("Could not detect local subnet for ping sweep")
            return []

        logger.info("Ping sweeping %s.%d-%d", prefix, self._start, self._end)

        is_windows = platform.system().lower() == "windows"
        ping_count_flag = "-n" if is_windows else "-c"
        ping_timeout_flag = "-w" if is_windows else "-W"
        # Use a short per-host timeout (1 second)
        per_host_timeout = "1"

        sem = asyncio.Semaphore(50)  # limit concurrency

        async def _ping(ip: str) -> Optional[str]:
            async with sem:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "ping",
                        ping_count_flag, "1",
                        ping_timeout_flag, per_host_timeout,
                        ip,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await asyncio.wait_for(proc.wait(), timeout=3)
                    return ip if proc.returncode == 0 else None
                except Exception:
                    return None

        targets = [f"{prefix}.{i}" for i in range(self._start, self._end + 1)]
        results = await asyncio.gather(*[_ping(ip) for ip in targets])

        devices: List[DiscoveredDevice] = []
        for ip in results:
            if ip is not None:
                dev = DiscoveredDevice(ip_address=ip)
                dev.discovered_by.append(DiscoveryProtocol.PING)
                devices.append(dev)

        return devices
