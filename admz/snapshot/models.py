from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SnapshotStatus(Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


#: A facet read's honest outcome (ADR-0063, FR-DRF-012). ``ok``: every read
#: the facet needed succeeded. ``skipped``: the local capability record says
#: the device lacks the API, so nothing was asked — a *settled* state, never
#: PARTIAL. ``failed``: a read was attempted and did not succeed — the facet's
#: live state is unknown, which is NOT the same as empty.
FACET_OK = "ok"
FACET_SKIPPED = "skipped"
FACET_FAILED = "failed"


@dataclass
class FacetResult:
    name: str
    success: bool
    normalized: Optional[Dict[str, Any]] = None
    raw: Optional[Any] = None
    error: Optional[str] = None
    # ``success`` ≡ ``status == "ok"``; the two are kept consistent below so
    # every existing constructor (``success=False``) and every existing
    # reader (``.success``) keeps meaning what it meant.
    status: str = FACET_OK
    skipped_reason: Optional[str] = None
    # What the capability record says about this facet's APIs after this
    # cycle's learning (ADR-0063): "absent" — every API the facet reads has a
    # hard-absent row (a clean 404-class answer), the ONLY state strong
    # enough to report a baselined facet as facets_absent; "unconfirmed" —
    # failures observed but not proof of absence (a blip must never read as
    # "known to lack"); None — no capability claim (ok facets, dump failure,
    # stub engines).
    capability: Optional[str] = None

    def __post_init__(self):
        if self.status == FACET_OK and not self.success:
            self.status = FACET_FAILED
        elif self.status != FACET_OK:
            self.success = False


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
        return [f for f in self.facets if f.status == FACET_OK]

    @property
    def failed_facets(self) -> List[FacetResult]:
        """Attempted and did not succeed. A ``skipped`` facet is NOT here —
        it is settled, and must never make a snapshot PARTIAL."""
        return [f for f in self.facets if f.status == FACET_FAILED]

    @property
    def skipped_facets(self) -> List[FacetResult]:
        return [f for f in self.facets if f.status == FACET_SKIPPED]

    def to_summary(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "git_sha": self.git_sha,
            "facets_succeeded": len(self.succeeded_facets),
            "facets_failed": len(self.failed_facets),
            "facets_skipped": len(self.skipped_facets),
            "succeeded": [f.name for f in self.succeeded_facets],
            "failed": [
                {"name": f.name, "error": f.error} for f in self.failed_facets
            ],
            "skipped": [
                {"name": f.name, "reason": f.skipped_reason}
                for f in self.skipped_facets
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
    # ADR-0047 attribution — which demo (if any) explains this difference:
    #   "unclaimed"   true drift (nothing claims it)
    #   "demo_set"    matches an ACTIVE demo's owned value — deliberate, not
    #                 drift; ``expected`` holds the BASE value for display
    #   "demo_broken" owned by an active demo but live differs — drift AGAINST
    #                 the demo; ``expected`` holds the DEMO's value, so a
    #                 targeted revert re-pushes the demo's config (repair)
    #   "candidate"   matches ≥1 INACTIVE demo's fragment — adopt or revert
    bucket: str = "unclaimed"
    owner: Optional[str] = None        # demo id (demo_set / demo_broken)
    owner_name: Optional[str] = None
    candidates: List[Dict[str, str]] = field(default_factory=list)  # [{id,name}]
    # ADR-0050: the BASELINE value for a demo-owned key, captured at the
    # demo_set/demo_broken sites. For demo_broken, ``expected`` holds the DEMO's
    # value (so a targeted revert repairs the demo); ``base_value`` is what a
    # deactivate-with-restore pushes to return the device to baseline.
    base_value: Optional[str] = None


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
    # True when the live device couldn't be read at all (auth failure /
    # unreachable). ``has_drift=False`` here means "unknown" — NOT "in sync".
    # Without this, an unreadable device makes every baselined field look
    # "removed" (false drift).
    unreadable: bool = False
    unreadable_reason: str = ""  # "auth_failed" | "unreachable" | ""
    # Git commit holding what this audit observed (ADR-0031 slice 2).
    # Commit-on-change: an unchanged device points at the existing commit.
    # None when observation recording failed/was unavailable.
    observed_sha: Optional[str] = None
    # The blessed baseline this report was diffed against. Stored in the drift
    # cache so a cached report can be invalidated the moment the baseline moves
    # (accept / re-snapshot) — a stale-baseline cache must never drive a revert.
    baseline_sha: Optional[str] = None
    # The drift-alert transition this check produced ("appeared"/"changed"/
    # "cleared"), or None when the drift state didn't change.
    alert_transition: Optional[str] = None
    # ADR-0063 (FR-DRF-013): the compare visits every facet in the BASELINE,
    # not only those present in the live read.
    #   facets_absent     baseline facets the device is now known to lack
    #                     (live read ``skipped``). This IS drift, reported
    #                     honestly — but it carries no DriftField, because the
    #                     revert builder must never write to an API the device
    #                     does not have.
    #   facets_unverified baseline facets whose live read FAILED. NOT drift:
    #                     the live state is unknown, not different.
    #   facet_status      every live facet's read status (ok/skipped/failed).
    facets_absent: List[str] = field(default_factory=list)
    facets_unverified: List[str] = field(default_factory=list)
    facet_status: Dict[str, str] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def real_fields(self) -> List[DriftField]:
        """The fields that are actually DRIFT — everything except ``demo_set``
        rows, which record a deliberate difference an active demo owns
        (ADR-0047). ``has_drift``/counts key off this, so a device fully
        explained by its active demos reads in-sync."""
        return [f for f in self.fields if f.bucket != "demo_set"]

    def to_summary(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "has_drift": self.has_drift,
            "no_baseline": self.no_baseline,
            "unreadable": self.unreadable,
            "unreadable_reason": self.unreadable_reason,
            "observed_sha": self.observed_sha,
            "baseline_sha": self.baseline_sha,
            "facets_checked": self.facets_checked,
            "facets_drifted": self.facets_drifted,
            "facets_absent": list(self.facets_absent),
            "facets_unverified": list(self.facets_unverified),
            "facet_status": dict(self.facet_status),
            "timestamp": self.timestamp,
            "drifted_fields": [
                {
                    "facet": f.facet,
                    "path": f.path,
                    "expected": f.expected,
                    "actual": f.actual,
                    "canonical_key": f.canonical_key,
                    "bucket": f.bucket,
                    "owner": f.owner,
                    "owner_name": f.owner_name,
                    "candidates": f.candidates,
                    "base_value": f.base_value,
                }
                for f in self.fields
            ],
        }
