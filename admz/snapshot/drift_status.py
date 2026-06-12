"""Shared last-known drift status for the roster surfaces (ADR-0031).

Both the Fleet view's drift glance (`GET /api/fleet/drift`) and the
Configuration workbench read the SAME cached answer through
:func:`drift_status_for`, so the two pages can never disagree about a
device. This is a pure cache read — the `baseline_sha` pointer plus the
last-known `drift_signatures` row — never a live device probe (a genuine
"is it drifted right now" check costs a per-device round-trip and runs
on demand via ``GET /api/snapshot/drift``, which warms this same cache).

States (mirrors the four the Configuration page has always shown):
  * ``none``      — no blessed baseline yet; nothing to compare against.
  * ``unchecked`` — baseline set, but no drift check has run since.
  * ``in_sync``   — last check found zero drifted fields.
  * ``drifted``   — last check found ``count`` drifted fields.

``checked_at`` is the signature's ``updated_at`` (unix epoch) or None —
the freshness stamp the UI surfaces so a week-old "In sync" can't be
mistaken for a live one.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# State constants — also the keys used in the fleet-drift count summary.
NONE = "none"
UNCHECKED = "unchecked"
IN_SYNC = "in_sync"
DRIFTED = "drifted"

STATES = (NONE, UNCHECKED, IN_SYNC, DRIFTED)


def drift_status_for(
    device_info: Dict[str, Any],
    signature: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Map a device's baseline pointer + last drift signature to a status.

    Args:
        device_info: a ``get_device_info()`` dict (only ``baseline_sha`` is
            read here).
        signature: the ``drift_alerts.get_last_signature(device_id)`` row
            (``{"signature", "field_count", "updated_at"}``) or None.

    Returns ``{"state", "count", "checked_at"}``:
        state      — one of :data:`STATES`.
        count      — drifted field count (0 unless ``drifted``).
        checked_at — unix epoch of the last drift check, or None.
    """
    if not device_info.get("baseline_sha"):
        return {"state": NONE, "count": 0, "checked_at": None}

    if signature is None:
        return {"state": UNCHECKED, "count": 0, "checked_at": None}

    field_count = signature.get("field_count") or 0
    checked_at = signature.get("updated_at")
    if field_count == 0:
        return {"state": IN_SYNC, "count": 0, "checked_at": checked_at}
    return {"state": DRIFTED, "count": field_count, "checked_at": checked_at}
