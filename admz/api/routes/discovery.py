"""
REST API routes for network device discovery.
"""

from typing import Optional

from fastapi import APIRouter, Query

from admz.discovery import discover_devices

router = APIRouter()


@router.post("/discover")
async def api_discover_devices(
    timeout: float = Query(5.0, description="Per-protocol timeout in seconds"),
    axis_only: bool = Query(False, description="Only return Axis devices"),
    subnet: Optional[str] = Query(None, description="Subnet for ARP scan (CIDR)"),
    enable_mdns: bool = Query(True, description="Enable mDNS discovery"),
    enable_ssdp: bool = Query(True, description="Enable SSDP discovery"),
    enable_onvif: bool = Query(True, description="Enable ONVIF discovery"),
    enable_arp: bool = Query(True, description="Enable ARP scanning"),
    enable_ping: bool = Query(False, description="Enable ping sweep"),
    enable_http_probe: bool = Query(True, description="Enable HTTP/VAPIX probing"),
    enable_snmp: bool = Query(True, description="Enable SNMP enrichment"),
    snmp_community: str = Query("public", description="SNMP community string"),
):
    """Discover devices on the local network."""
    devices = await discover_devices(
        timeout=timeout,
        axis_only=axis_only,
        subnet=subnet,
        enable_mdns=enable_mdns,
        enable_ssdp=enable_ssdp,
        enable_onvif=enable_onvif,
        enable_arp=enable_arp,
        enable_ping=enable_ping,
        enable_http_probe=enable_http_probe,
        enable_snmp=enable_snmp,
        snmp_community=snmp_community,
    )
    return {
        "count": len(devices),
        "devices": [d.to_registry_dict() for d in devices],
    }
