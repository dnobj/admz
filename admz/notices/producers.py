"""Who raises and resolves notices (ADR-0071 §2).

Drift raises at one choke point: ``DriftDetector.check_drift`` hands every
check here, so the scheduled audit, the manual **Check drift** button and the
MCP tool all produce the same notices. ``appeared`` and ``changed`` raise;
``cleared`` always resolves, even while raising is switched off; a check that
finds the same drift again confirms the live notice. Accepting a baseline
resolves the notice as ``accepted`` with the person's name.

Provenance rides a context variable: the ``drift_audit`` handler wraps its
sweep in :func:`notice_provenance`, and anything else reads as a manual
``check_drift``. The ``notify`` task action raises an ``event`` notice, keyed
per task and device, so a detection that fires ten times bumps one row.

Rows carry identifiers, counts and class names only (see the store).
"""

from __future__ import annotations

import contextlib
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional

from admz.notices.store import KIND_DRIFT, KIND_EVENT, SEVERITIES, Notice

logger = logging.getLogger(__name__)

SOURCE_CHECK_DRIFT = "check_drift"
SOURCE_DRIFT_AUDIT = "drift_audit"
SOURCE_BACKFILL = "backfill"
SOURCE_NOTIFY = "notify"

#: How a note or the prompt names a source.
SOURCE_LABELS = {
    SOURCE_CHECK_DRIFT: "a drift check",
    SOURCE_DRIFT_AUDIT: "the scheduled drift audit",
    SOURCE_BACKFILL: "the drift cache at startup",
    SOURCE_NOTIFY: "an event detection",
}

TRANSITIONS_THAT_RAISE = ("appeared", "changed")


@dataclass(frozen=True)
class Provenance:
    """Who is checking drift right now, and whether they want notices."""

    source: str = SOURCE_CHECK_DRIFT
    task_id: str = ""
    notify_console: bool = True


_PROVENANCE: ContextVar[Provenance] = ContextVar(
    "admz_notice_provenance", default=Provenance(),
)


def current_provenance() -> Provenance:
    return _PROVENANCE.get()


@contextlib.contextmanager
def notice_provenance(
    source: str, task_id: str = "", notify_console: bool = True,
) -> Iterator[Provenance]:
    """Stamp every notice raised inside the block with this provenance."""
    prov = Provenance(source=source, task_id=task_id or "",
                      notify_console=bool(notify_console))
    token = _PROVENANCE.set(prov)
    try:
        yield prov
    finally:
        _PROVENANCE.reset(token)


def _store():
    from admz.notices import store as store_module
    return store_module.notices_store


def drift_notices_enabled() -> bool:
    """The fleet flag, default on. It switches raising off, never resolving."""
    try:
        from admz.fleet_settings import fleet_settings
        raw = fleet_settings.get("drift_notices_enabled")
    except Exception:  # noqa: BLE001 — an unreadable flag keeps the default
        return True
    if raw is None:
        return True
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def drift_subject(device_id: str) -> str:
    return f"drift:{device_id}"


def event_subject(task_id: str, device_id: str) -> str:
    return f"event:{task_id}:{device_id or 'fleet'}"


def drift_title(device_id: str) -> str:
    return f"Configuration drift on {device_id}"


def _review_counts(report: Any, registry: Any, git_repo: Any) -> Dict[str, Any]:
    """The review's counts and class names — never a value (FR-DRF-018)."""
    counts: Dict[str, Any] = {
        "fields": len(getattr(report, "real_fields", []) or []),
        "facets_absent": len(getattr(report, "facets_absent", []) or []),
    }
    if registry is None:
        return counts
    try:
        from admz.snapshot import review

        summary = review.annotate_review(
            report.to_summary(), registry=registry, git_repo=git_repo,
            device_id=report.device_id,
        )
        counts["by_class"] = {
            cls: int(info.get("count") or 0)
            for cls, info in (summary.get("summary_by_class") or {}).items()
            if cls != "demo_set"
        }
        counts["highest_importance"] = summary.get("highest_importance", "none")
        context = summary.get("triage_context") or {}
        counts["firmware_changed"] = bool(context.get("firmware_changed"))
    except Exception:  # noqa: BLE001 — the counts above still describe it
        logger.debug("notice review counts unavailable for %s",
                     getattr(report, "device_id", "?"), exc_info=True)
    return counts


def drift_transition(
    transition: Optional[str], report: Any, *,
    registry: Any = None, git_repo: Any = None,
) -> Optional[Notice]:
    """Hand one drift check's result to the attention queue.

    No transition but still drifted — the same drift seen again — confirms
    the live notice (:meth:`NoticeStore.touch`), so "last confirmed" stays
    true and an unreviewed notice does not expire while checks keep finding
    its drift. It never raises one: a dismissed notice stays dismissed until
    the drift changes.
    """
    device_id = report.device_id
    subject = drift_subject(device_id)
    prov = current_provenance()
    if not transition:
        if getattr(report, "real_fields", None) or getattr(report, "facets_absent", None):
            _store().touch(subject, source=prov.source, task_id=prov.task_id)
        return None
    if transition == "cleared":
        return _store().resolve(subject, "cleared", by=prov.source)
    if transition not in TRANSITIONS_THAT_RAISE:
        return None
    if not prov.notify_console or not drift_notices_enabled():
        return None
    counts = _review_counts(report, registry, git_repo)
    counts["transition"] = transition
    importance = counts.get("highest_importance")
    return _store().raise_notice(
        kind=KIND_DRIFT,
        subject_key=subject,
        title=drift_title(device_id),
        summary=counts,
        device_id=device_id,
        severity=importance if importance in SEVERITIES else "medium",
        source=prov.source,
        task_id=prov.task_id,
    )


def resolve_drift_accepted(device_id: str, accepted_by: str = "") -> Optional[Notice]:
    """Close the device's drift notice as ``accepted``, naming the person."""
    return _store().resolve(drift_subject(device_id), "accepted", by=accepted_by or "")


def event_notice(task: Any, message: str) -> Notice:
    """Raise (or bump) the notice a ``notify`` task action stands for."""
    from admz.validators import sanitize_display_text

    task_id = str(getattr(task, "id", "") or "")
    device_id = str(getattr(task, "device_id", "") or "")
    return _store().raise_notice(
        kind=KIND_EVENT,
        subject_key=event_subject(task_id, device_id),
        title=sanitize_display_text(message, max_length=120) or "Event detected",
        summary={"action": "notify"},
        device_id=device_id,
        severity="medium",
        source=SOURCE_NOTIFY,
        task_id=task_id,
    )


def backfill_drift_notices(registry: Any) -> int:
    """Raise a notice for drift that predates notices.

    ``process_report`` emits nothing for an unchanged signature, so a device
    that was already drifted when this feature arrived would never surface.
    A subject that already has any notice row — open, dismissed or resolved —
    is left to its transitions: a dismissed notice is not re-raised on every
    restart. Idempotent; nothing when the flag is off.
    """
    if not drift_notices_enabled():
        return 0
    from admz.snapshot.drift_alerts import drift_alerts
    from admz.snapshot.drift_status import DRIFTED, drift_status_for

    store = _store()
    raised = 0
    for device in registry.list_devices() or []:
        device_id = device.get("device_id")
        if not device_id:
            continue
        try:
            status = drift_status_for(device, drift_alerts.get_last_signature(device_id))
        except Exception:  # noqa: BLE001 — one unreadable row skips one device
            continue
        if status.get("state") != DRIFTED:
            continue
        subject = drift_subject(device_id)
        if store.has_any(subject):
            continue
        store.raise_notice(
            kind=KIND_DRIFT,
            subject_key=subject,
            title=drift_title(device_id),
            summary={"fields": int(status.get("count") or 0),
                     "transition": SOURCE_BACKFILL},
            device_id=device_id,
            source=SOURCE_BACKFILL,
            now=status.get("checked_at") or None,
        )
        raised += 1
    return raised
