"""
Data models for the device API capabilities registry.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FirmwareSnapshot:
    """API capabilities snapshot for a specific firmware version."""

    firmware: str                                # e.g. "12.8.54"
    discovered: str                              # ISO date
    device_id: str = ""                          # which device was probed
    api_count: int = 0
    apis: Dict[str, str] = field(default_factory=dict)  # device-reported id -> version


@dataclass
class ModelCapabilities:
    """All known API capability snapshots for a model."""

    model: str                                   # canonical name, e.g. "Q3538-SLVE"
    series: Optional[str] = None                 # e.g. "q35"
    snapshots: List[FirmwareSnapshot] = field(default_factory=list)

    def get_snapshot(self, firmware: str) -> Optional[FirmwareSnapshot]:
        """Get snapshot for an exact firmware version."""
        for snap in self.snapshots:
            if snap.firmware == firmware:
                return snap
        return None

    def get_latest_snapshot(self) -> Optional[FirmwareSnapshot]:
        """Get the most recently discovered snapshot."""
        if not self.snapshots:
            return None
        return max(self.snapshots, key=lambda s: s.discovered)

    def supports_api(self, api_id: str, firmware: Optional[str] = None) -> Optional[str]:
        """Check if a specific API is supported.

        Returns the version string if supported, None otherwise.
        Uses the exact firmware match if provided, otherwise the latest snapshot.
        """
        snap = self.get_snapshot(firmware) if firmware else self.get_latest_snapshot()
        if not snap:
            return None
        return snap.apis.get(api_id)


@dataclass
class CapabilityLookupResult:
    """Result of a capability check for a specific device + API."""

    device_id: str
    model: Optional[str] = None
    firmware: Optional[str] = None
    snapshot: Optional[FirmwareSnapshot] = None
    supported: Optional[bool] = None
    api_version: Optional[str] = None
    notes: List[str] = field(default_factory=list)
