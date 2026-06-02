"""Backfill the Org/Site/Group hierarchy on devices created before Slice 1.

Pre-Slice-1, devices had no `org_id` or `site_id` and no group
memberships. This migration:

1. Finds every device whose org_id IS NULL OR site_id IS NULL.
2. Assigns each such device to (org="default", site="default").
3. Adds each to the "ungrouped" device group as their primary.

Assumes the default Org/Site/Group rows already exist (the
`_bootstrap_default_hierarchy` in `admz/components.py` is called
before this migration in the CLI flow).

The function is idempotent: a device that already has org_id +
site_id set AND a primary group is left alone.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict


logger = logging.getLogger(__name__)


_DEFAULT_ORG = "default"
_DEFAULT_SITE = "default"
_DEFAULT_GROUP = "ungrouped"


def migrate_hierarchy_backfill(
    registry,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Backfill org_id/site_id + primary-group on every legacy device.

    Args:
        registry: the SQLiteDeviceRegistry (or any backend that
            implements set_device_org_site + set_device_primary_group).
        dry_run: if True, don't write anything — just count what
            would change. The numbers in the return value still
            reflect the intended action.

    Returns:
        dict with keys:
          - devices_total: total device count
          - already_migrated: devices that already have both
            org_id + site_id AND a primary group (no work needed)
          - backfilled: devices that received an org_id/site_id assignment
          - primary_assigned: devices that received a primary-group assignment
          - errors: list of (device_id, error_message) tuples for
            per-device failures (the migration continues past errors)
    """
    devices = registry.list_devices()
    total = len(devices)
    already_migrated = 0
    backfilled = 0
    primary_assigned = 0
    errors = []

    for d in devices:
        device_id = d.get("device_id")
        if not device_id:
            continue

        # Where is the device today?
        os_pair = registry.get_device_org_site(device_id)
        has_org_site = os_pair is not None
        primary = registry.get_device_primary_group(device_id)
        has_primary = primary is not None

        if has_org_site and has_primary:
            already_migrated += 1
            continue

        try:
            if not has_org_site:
                if not dry_run:
                    registry.set_device_org_site(
                        device_id, _DEFAULT_ORG, _DEFAULT_SITE,
                    )
                backfilled += 1

            if not has_primary:
                if not dry_run:
                    registry.set_device_primary_group(
                        device_id, _DEFAULT_GROUP,
                    )
                primary_assigned += 1
        except Exception as exc:
            errors.append({
                "device_id": device_id,
                "error": f"{type(exc).__name__}: {exc}",
            })
            logger.warning(
                "hierarchy_backfill: %s failed: %s", device_id, exc,
            )

    result: Dict[str, Any] = {
        "devices_total": total,
        "already_migrated": already_migrated,
        "backfilled": backfilled,
        "primary_assigned": primary_assigned,
        "dry_run": dry_run,
    }
    if errors:
        result["errors"] = errors
    return result
