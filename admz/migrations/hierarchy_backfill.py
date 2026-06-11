"""Backfill the Org/Site hierarchy on devices created before Slice 1.

Pre-Slice-1, devices had no `org_id` or `site_id`. This migration finds
every device whose org_id IS NULL OR site_id IS NULL and assigns it to
(org="default", site="default").

(ADR-0032: the former Group level — and this migration's old
"assign to the ungrouped group" step — was removed. Operational
grouping is done with device tags.)

Assumes the default Org/Site rows already exist (the
`_bootstrap_default_hierarchy` in `admz/components.py` is called
before this migration in the CLI flow).

The function is idempotent: a device that already has org_id +
site_id set is left alone.
"""

from __future__ import annotations

import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)


_DEFAULT_ORG = "default"
_DEFAULT_SITE = "default"


def migrate_hierarchy_backfill(
    registry,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Backfill org_id/site_id on every legacy device.

    Args:
        registry: the SQLiteDeviceRegistry (or any backend that
            implements set_device_org_site).
        dry_run: if True, don't write anything — just count what
            would change. The numbers in the return value still
            reflect the intended action.

    Returns:
        dict with keys:
          - devices_total: total device count
          - already_migrated: devices that already have org_id + site_id
          - backfilled: devices that received an org_id/site_id assignment
          - errors: list of (device_id, error_message) tuples for
            per-device failures (the migration continues past errors)
    """
    devices = registry.list_devices()
    total = len(devices)
    already_migrated = 0
    backfilled = 0
    errors = []

    for d in devices:
        device_id = d.get("device_id")
        if not device_id:
            continue

        # Where is the device today?
        os_pair = registry.get_device_org_site(device_id)
        if os_pair is not None:
            already_migrated += 1
            continue

        try:
            if not dry_run:
                registry.set_device_org_site(
                    device_id, _DEFAULT_ORG, _DEFAULT_SITE,
                )
            backfilled += 1
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
        "dry_run": dry_run,
    }
    if errors:
        result["errors"] = errors
    return result
