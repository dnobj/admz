"""Drift-alert history REST endpoint (FR-DRF-010).

Read-only surface over the ``drift_alerts`` SQLite table that
``DriftAlertStore`` already maintains as a side effect of every
``check_drift`` run. Closes the "no drift-history surface" gap
called out in the spec — previously the audit trail was only
queryable by hitting the DB directly.

Anonymous-allowed (consistent with other read endpoints like
``/api/fleet/health``) and audit-logged on every call so we
have a record of who read which device's history.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from admz.snapshot.drift_alerts import drift_alerts as _alert_store_singleton
from admz.validators import validate_identifier


logger = logging.getLogger(__name__)

router = APIRouter()


# The transitions the store records — kept here so the validator can
# reject typos at the boundary rather than silently returning empty.
_VALID_TRANSITIONS = frozenset({"appeared", "changed", "cleared"})

# Cap to keep a runaway client from pulling the whole table.
_MAX_LIMIT = 1000


def _parse_since(raw: Optional[str]) -> Optional[float]:
    """Accept either an ISO-8601 timestamp (``2026-06-03T04:14:43Z``)
    or a raw unix timestamp (``1717387783``). Empty / None passes
    through as None (no lower bound)."""
    if raw is None or raw == "":
        return None
    # Try unix timestamp first — short numeric strings are common
    # in tests and scripts.
    try:
        return float(raw)
    except ValueError:
        pass
    # ISO-8601 — accept trailing 'Z' (Python <3.11 didn't).
    iso = raw.rstrip()
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not parse 'since={raw!r}'. Use ISO-8601 "
                "(e.g. '2026-06-03T04:14:43Z') or a unix timestamp."
            ),
        ) from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


@router.get("/drift/alerts", tags=["drift"])
async def list_drift_alerts(
    request: Request,
    device_id: Optional[str] = Query(
        None, description="Filter to a single device",
    ),
    transition: Optional[List[str]] = Query(
        None,
        description=(
            "Filter by transition type. Repeat to allow multiple "
            "(e.g. ?transition=appeared&transition=cleared). "
            "Valid: appeared, changed, cleared."
        ),
    ),
    since: Optional[str] = Query(
        None,
        description=(
            "Lower bound on alert timestamp. ISO-8601 "
            "(2026-06-03T04:14:43Z) or unix timestamp."
        ),
    ),
    limit: int = Query(
        100, ge=1, le=_MAX_LIMIT,
        description=f"Max alerts to return (1..{_MAX_LIMIT}).",
    ),
):
    """FR-DRF-010 — read-only drift-alert history.

    Returns alerts in newest-first order. Every successful query is
    audited; the caller's principal is recorded for traceability.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal

    # Use the latest singleton — repointed in tests, so do not capture
    # the import-time reference.
    from admz.snapshot import drift_alerts as _da_mod

    principal = await get_current_principal(request)
    resource = "drift_alerts"

    # CR-5 — reject path-traversal-shaped device IDs at the boundary.
    if device_id is not None and device_id != "":
        try:
            validate_identifier(device_id, "device_id")
        except ValueError as e:
            record_event(
                principal, "drift.list_alerts",
                resource=resource, success=False,
                error_message=f"InvalidInput: {e}",
            )
            raise HTTPException(status_code=400, detail=str(e))

    # Validate transition values up front so a typo doesn't silently
    # return empty.
    if transition:
        bad = [t for t in transition if t not in _VALID_TRANSITIONS]
        if bad:
            record_event(
                principal, "drift.list_alerts",
                resource=resource, success=False,
                error_message=f"InvalidTransition: {bad}",
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown transition(s): {bad}. "
                    f"Valid values: {sorted(_VALID_TRANSITIONS)}."
                ),
            )

    since_ts = _parse_since(since)

    alerts = _da_mod.drift_alerts.list_alerts(
        since=since_ts,
        device_id=device_id or None,
        transitions=list(transition) if transition else None,
        limit=limit,
    )

    record_event(
        principal, "drift.list_alerts",
        resource=resource,
        details={
            "device_id": device_id,
            "transition": list(transition) if transition else None,
            "since": since,
            "limit": limit,
            "returned_count": len(alerts),
        },
    )

    return {
        "count": len(alerts),
        "alerts": [a.to_dict() for a in alerts],
    }
