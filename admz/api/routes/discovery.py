"""REST routes for network discovery."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.discovery import discover_devices as run_network_discovery

router = APIRouter()


class DiscoverRequest(BaseModel):
    timeout: float = 5.0
    axis_only: bool = False
    subnet: Optional[str] = None
    enable_mdns: bool = True
    enable_ssdp: bool = True
    enable_onvif: bool = True
    enable_arp: bool = True
    enable_ping: bool = False
    enable_http_probe: bool = True
    enable_snmp: bool = True
    snmp_community: str = "public"


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
    request: Request,
    req: DiscoverRequest,
    ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    devices = await run_network_discovery(
        timeout=req.timeout,
        axis_only=req.axis_only,
        subnet=req.subnet,
        enable_mdns=req.enable_mdns,
        enable_ssdp=req.enable_ssdp,
        enable_onvif=req.enable_onvif,
        enable_arp=req.enable_arp,
        enable_ping=req.enable_ping,
        enable_http_probe=req.enable_http_probe,
        enable_snmp=req.enable_snmp,
        snmp_community=req.snmp_community,
    )
    record_event(principal, "discovery.scan",
                 details={"subnet": req.subnet, "axis_only": req.axis_only,
                          "count": len(devices)})
    return {
        "count": len(devices),
        "devices": [d.to_registry_dict() for d in devices],
    }


@router.post("/discovery/register")
async def register_discovered(
    request: Request,
    req: RegisterDiscoveredRequest,
    ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"device:{req.device_id}"
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
        record_event(principal, "discovery.register", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    record_event(principal, "discovery.register", resource=resource,
                 details={"ip": req.ip_address, "model": req.model})
    return {
        "message": (
            f"Device '{req.device_id}' registered. Use the capture flow "
            "to set credentials."
        ),
        "device_id": req.device_id,
    }
