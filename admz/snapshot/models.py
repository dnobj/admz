from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SnapshotStatus(Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class FacetResult:
    name: str
    success: bool
    normalized: Optional[Dict[str, Any]] = None
    raw: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class DeviceSnapshot:
    device_id: str
    device_info: Dict[str, Any]
    facets: List[FacetResult] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: SnapshotStatus = SnapshotStatus.IN_PROGRESS
    git_sha: Optional[str] = None

    @property
    def succeeded_facets(self) -> List[FacetResult]:
        return [f for f in self.facets if f.success]

    @property
    def failed_facets(self) -> List[FacetResult]:
        return [f for f in self.facets if not f.success]

    def to_summary(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "git_sha": self.git_sha,
            "facets_succeeded": len(self.succeeded_facets),
            "facets_failed": len(self.failed_facets),
            "succeeded": [f.name for f in self.succeeded_facets],
            "failed": [
                {"name": f.name, "error": f.error} for f in self.failed_facets
            ],
        }


@dataclass
class DriftField:
    facet: str
    path: str
    expected: str
    actual: str
    # Cross-facet identifier for the ignore list (full root.* key for param
    # facets, else "<facet>:<path>"). For the UI's "exclude from tracking"
    # action; NOT used in drift comparison (which joins on facet+path).
    canonical_key: Optional[str] = None


@dataclass
class DriftReport:
    device_id: str
    has_drift: bool
    fields: List[DriftField] = field(default_factory=list)
    facets_checked: int = 0
    facets_drifted: int = 0
    # True when the device has no blessed baseline to compare against, so
    # ``has_drift=False`` means "nothing to compare", NOT "in sync".
    no_baseline: bool = False
    # Git commit holding what this audit observed (ADR-0031 slice 2).
    # Commit-on-change: an unchanged device points at the existing commit.
    # None when observation recording failed/was unavailable.
    observed_sha: Optional[str] = None
    # The drift-alert transition this check produced ("appeared"/"changed"/
    # "cleared"), or None when the drift state didn't change.
    alert_transition: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_summary(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "has_drift": self.has_drift,
            "no_baseline": self.no_baseline,
            "observed_sha": self.observed_sha,
            "facets_checked": self.facets_checked,
            "facets_drifted": self.facets_drifted,
            "timestamp": self.timestamp,
            "drifted_fields": [
                {
                    "facet": f.facet,
                    "path": f.path,
                    "expected": f.expected,
                    "actual": f.actual,
                    "canonical_key": f.canonical_key,
                }
                for f in self.fields
            ],
        }
