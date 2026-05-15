"""REST routes for network discovery."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.discovery import discover_devices as run_network_discovery

router = APIRouter()


class DiscoverRequest(BaseModel):
    timeout: float = 5.0
    axis_only: bool = False
    subnet: Optional[str] = None
    enable_ping: bool = False


class RegisterDiscoveredRequest(BaseModel):
    device_id: str
    ip_address: str
    mac_address: Optional[str] = None
    model: Optional[str] = None
    hostname: Optional[str] = None
    device_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


@router.post("/discovery/scan")
async def scan_network(
    req: DiscoverRequest, ctx: AppContext = Depends(get_context)
):
    devices = await run_network_discovery(
        timeout=req.timeout,
        axis_only=req.axis_only,
        subnet=req.subnet,
        enable_ping=req.enable_ping,
    )
    return {
        "count": len(devices),
        "devices": [d.to_registry_dict() for d in devices],
    }


@router.post("/discovery/register")
async def register_discovered(
    req: RegisterDiscoveredRequest, ctx: AppContext = Depends(get_context)
):
    device_info = {
        "host": req.ip_address,
        "ip_address": req.ip_address,
        "mac_address": req.mac_address or "",
        "model": req.model or "",
        "hostname": req.hostname or "",
        "nickname": req.hostname or "",
        "device_type": req.device_type or "unknown",
        "tags": req.tags,
    }
    try:
        ctx.registry.add_device(req.device_id, device_info)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "message": (
            f"Device '{req.device_id}' registered. Use the capture flow "
            "to set credentials."
        ),
        "device_id": req.device_id,
    }
