"""
Discovery orchestrator — runs all available protocols concurrently,
merges results by MAC address, and produces a unified device list.
"""

import asyncio
import logging
from typing import Dict, List, Optional

from admz.discovery.base import DiscoveryProtocolBase
from admz.discovery.models import DiscoveredDevice, DiscoveryProtocol
from admz.discovery.mdns_discovery import MDNSDiscovery
from admz.discovery.ssdp_discovery import SSDPDiscovery
from admz.discovery.onvif_discovery import ONVIFDiscovery
from admz.discovery.arp_scanner import ARPScanner
from admz.discovery.ping_sweep import PingSweep
from admz.discovery.http_probe import HTTPProbe
from admz.discovery.snmp_query import SNMPQuery

from admz.validators import validate_scan_subnet

logger = logging.getLogger(__name__)


class DiscoveryOrchestrator:
    """
    Runs multiple discovery protocols in parallel, then optionally runs
    enrichment passes (HTTP probe, SNMP) against the collected IPs.

    Usage::

        orch = DiscoveryOrchestrator()
        devices = await orch.run()
        for dev in devices:
            print(dev.ip_address, dev.model, dev.is_axis)
    """

    def __init__(
        self,
        *,
        enable_mdns: bool = True,
        enable_ssdp: bool = True,
        enable_onvif: bool = True,
        enable_arp: bool = True,
        enable_ping: bool = False,
        enable_http_probe: bool = True,
        enable_snmp: bool = True,
        subnet: Optional[str] = None,
        axis_only: bool = False,
        snmp_community: str = "public",
        timeout: float = 5.0,
    ):
        self.timeout = timeout
        self._axis_only = axis_only

        # Phase 1 — primary discovery protocols (run concurrently)
        self._phase1: List[DiscoveryProtocolBase] = []
        if enable_mdns:
            self._phase1.append(MDNSDiscovery())
        if enable_ssdp:
            self._phase1.append(SSDPDiscovery())
        if enable_onvif:
            self._phase1.append(ONVIFDiscovery())
        if enable_arp:
            self._phase1.append(ARPScanner(subnet=subnet, axis_only=axis_only))
        if enable_ping:
            self._phase1.append(PingSweep())

        # Phase 2 — enrichment (run after phase 1 to get target IPs)
        self._enable_http_probe = enable_http_probe
        self._enable_snmp = enable_snmp
        self._snmp_community = snmp_community

    async def run(self) -> List[DiscoveredDevice]:
        """Execute all discovery phases and return merged results."""

        # --- Phase 1: parallel primary discovery --------------------------
        logger.info(
            "Phase 1: running %d primary discovery protocol(s)…",
            len(self._phase1),
        )
        phase1_results = await asyncio.gather(
            *[p.safe_discover(timeout=self.timeout) for p in self._phase1]
        )

        merged = _merge_all(phase1_results)
        logger.info("Phase 1 complete: %d unique device(s) found", len(merged))

        # --- Phase 2: enrichment ------------------------------------------
        ips = [d.ip_address for d in merged.values() if d.ip_address]

        enrichment: List[DiscoveryProtocolBase] = []
        if self._enable_http_probe and ips:
            enrichment.append(HTTPProbe(targets=ips))
        if self._enable_snmp and ips:
            enrichment.append(SNMPQuery(targets=ips, community=self._snmp_community))

        if enrichment:
            logger.info(
                "Phase 2: running %d enrichment protocol(s) against %d IP(s)…",
                len(enrichment),
                len(ips),
            )
            phase2_results = await asyncio.gather(
                *[p.safe_discover(timeout=self.timeout) for p in enrichment]
            )
            _merge_into(merged, phase2_results)
            logger.info("Phase 2 complete")

        # --- Final filtering ----------------------------------------------
        devices = list(merged.values())
        if self._axis_only:
            devices = [d for d in devices if d.is_axis]

        # Sort: Axis first, then by IP
        devices.sort(key=lambda d: (not d.is_axis, d.ip_address or ""))
        return devices


def _merge_all(
    protocol_results: List[List[DiscoveredDevice]],
) -> Dict[str, DiscoveredDevice]:
    """Merge device lists from multiple protocols, keyed by MAC or IP."""
    merged: Dict[str, DiscoveredDevice] = {}
    for dev_list in protocol_results:
        for dev in dev_list:
            key = dev.mac_address or dev.ip_address
            if not key:
                continue
            if key in merged:
                merged[key].merge(dev)
            else:
                merged[key] = dev
    return merged


def _merge_into(
    merged: Dict[str, DiscoveredDevice],
    protocol_results: List[List[DiscoveredDevice]],
) -> None:
    """Merge enrichment results into an existing merged dict."""
    for dev_list in protocol_results:
        for dev in dev_list:
            # Try to find matching device by IP
            matched = False
            for key, existing in merged.items():
                if existing.ip_address and existing.ip_address == dev.ip_address:
                    existing.merge(dev)
                    matched = True
                    break
            if not matched:
                new_key = dev.mac_address or dev.ip_address
                if new_key:
                    if new_key in merged:
                        merged[new_key].merge(dev)
                    else:
                        merged[new_key] = dev


async def discover_devices(
    *,
    timeout: float = 5.0,
    axis_only: bool = False,
    subnet: Optional[str] = None,
    enable_mdns: bool = True,
    enable_ssdp: bool = True,
    enable_onvif: bool = True,
    enable_arp: bool = True,
    enable_ping: bool = False,
    enable_http_probe: bool = True,
    enable_snmp: bool = True,
    snmp_community: str = "public",
) -> List[DiscoveredDevice]:
    """
    High-level convenience function: discover devices on the local network.

    Runs all enabled protocols concurrently, merges results, and returns
    a deduplicated list of ``DiscoveredDevice`` objects.

    Args:
        timeout: Per-protocol timeout in seconds.
        axis_only: If True, filter to Axis devices only.
        subnet: Override subnet for ARP scan (e.g. '192.168.1.0/24').
        enable_mdns: Enable mDNS/Zeroconf/Bonjour discovery.
        enable_ssdp: Enable SSDP/UPnP discovery.
        enable_onvif: Enable ONVIF/WS-Discovery.
        enable_arp: Enable ARP subnet scanning (requires root).
        enable_ping: Enable ICMP ping sweep.
        enable_http_probe: Enable HTTP/VAPIX probing of discovered IPs.
        enable_snmp: Enable SNMP enrichment of discovered IPs.
        snmp_community: SNMP v2c community string.

    Returns:
        List of DiscoveredDevice, sorted with Axis devices first.

    Raises:
        ValueError: ``subnet`` is not IPv4 CIDR, or is wider than
            ``validators.MIN_SCAN_PREFIXLEN``.
    """
    # #199: the subnet is model-supplied free text and reaches scapy's
    # `ARP(pdst=...)` untouched. Validated HERE rather than at the five call
    # sites (REST scan, the demo-inference survey, two MCP tools, the CLI)
    # because per-entry-point enforcement is how the sixth caller gets missed —
    # which is exactly what happened to #299's gate. Every present and future
    # caller inherits this.
    subnet = validate_scan_subnet(subnet)

    orch = DiscoveryOrchestrator(
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
    return await orch.run()
