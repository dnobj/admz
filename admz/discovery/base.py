"""
Abstract base class for discovery protocol implementations.
"""

import abc
import logging
from typing import List

from admz.discovery.models import DiscoveredDevice

logger = logging.getLogger(__name__)


class DiscoveryProtocolBase(abc.ABC):
    """
    Every protocol scanner subclasses this and implements ``discover``.

    Implementations must be tolerant of missing optional dependencies —
    if a library is not installed the ``discover`` method should return an
    empty list and log a warning rather than raising.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable protocol name (e.g. 'mDNS/Zeroconf')."""

    @abc.abstractmethod
    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        """
        Run discovery and return found devices.

        Args:
            timeout: Maximum seconds to wait for responses.

        Returns:
            List of DiscoveredDevice instances (may be empty).
        """

    async def safe_discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        """Wrapper that catches exceptions so one bad protocol can't crash the orchestrator."""
        try:
            devices = await self.discover(timeout=timeout)
            logger.info("%s found %d device(s)", self.name, len(devices))
            return devices
        except Exception:
            logger.exception("%s discovery failed", self.name)
            return []
