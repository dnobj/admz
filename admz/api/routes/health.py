"""Device health REST endpoints — surfaces the cached health table.

Mirrors the MCP ``get_device_health`` / ``get_fleet_health`` tools.
Both endpoints read from the device_health table the background
HealthMonitor maintains — no network calls fire. Devices the
monitor hasn't checked yet show status='unknown'.

POST /api/fleet/health/sweep triggers an on-demand sweep so
operators don't have to wait for the next interval after enabling
the monitor or adding a new device.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from admz.api.context import AppContext, get_context
from admz.device_registry import DeviceRegistry
from admz.exceptions import DeviceNotFoundError
from admz.fleet.health import (
    DeviceHealthStatus,
    device_health_store,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_registry() -> DeviceRegistry:
    """Resolve the registry without forcing the context dependency on
    every endpoint."""
    from admz.api.main import registry
    if registry is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")
    return registry


@router.get("/api/devices/{device_id}/health", tags=["health"])
async def get_device_health(
    device_id: str,
    registry: DeviceRegistry = Depends(_get_registry),
):
    """Return cached health for one device."""
    if not registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    rec = device_health_store.get(device_id)
    if rec is None:
        return {
            "device_id": device_id,
            "status": DeviceHealthStatus.UNKNOWN.value,
            "note": (
                "No health record yet. Enable the monitor via "
                "'health_monitor_enabled' (fleet setting) or call "
                "POST /api/fleet/health/sweep for an on-demand check."
            ),
        }
    return rec.to_dict()


@router.get("/api/fleet/health", tags=["health"])
async def get_fleet_health(
    registry: DeviceRegistry = Depends(_get_registry),
):
    """Return cached health for every registered device + summary counts.

    Devices the monitor hasn't checked yet show status='unknown'.
    """
    records = device_health_store.list_all()
    seen = {r.device_id: r for r in records}
    all_devices = registry.list_devices()

    counts: Dict[str, int] = {
        "online": 0, "unreachable": 0,
        "auth_failed": 0, "unknown": 0,
    }
    entries: List[Dict[str, Any]] = []
    for d in all_devices:
        did = d.get("device_id")
        if not did:
            continue
        rec = seen.get(did)
        if rec is None:
            counts["unknown"] += 1
            entries.append({
                "device_id": did,
                "status": DeviceHealthStatus.UNKNOWN.value,
            })
        else:
            counts[rec.status.value] = counts.get(rec.status.value, 0) + 1
            entries.append(rec.to_dict())

    return {
        "total": len(entries),
        "counts": counts,
        "devices": entries,
    }


@router.post("/api/fleet/health/sweep", tags=["health"])
async def trigger_health_sweep(ctx: AppContext = Depends(get_context)):
    """Run an immediate health sweep, ignoring the polling interval.

    Useful right after enabling the monitor (so operators don't
    wait 60s for the first results) or after adding/changing
    devices.
    """
    n = await ctx.health_monitor.sweep_once()
    return {"checked": n}
