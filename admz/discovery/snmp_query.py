"""
SNMP device enrichment.

Queries ``sysDescr.0`` and ``sysName.0`` for devices already found by
other protocols, to add model/firmware/hostname information.

Requires: pip install pysnmp
"""

import asyncio
import logging
from typing import Dict, List, Optional

from admz.discovery.base import DiscoveryProtocolBase
from admz.discovery.models import (
    DiscoveredDevice,
    DiscoveryProtocol,
    DeviceType,
)

logger = logging.getLogger(__name__)

# Standard OIDs
SYS_DESCR = "1.3.6.1.2.1.1.1.0"
SYS_NAME = "1.3.6.1.2.1.1.5.0"


class SNMPQuery(DiscoveryProtocolBase):
    """Enrich device information via SNMP GET queries."""

    def __init__(
        self,
        targets: Optional[List[str]] = None,
        community: str = "public",
    ):
        """
        Args:
            targets: IP addresses to query.
            community: SNMPv2c community string.
        """
        self._targets = targets or []
        self._community = community

    @property
    def name(self) -> str:
        return "SNMP Query"

    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        if not self._targets:
            return []

        try:
            from pysnmp.hlapi.v3arch.asyncio import (
                CommunityData,
                ContextData,
                ObjectIdentity,
                ObjectType,
                SnmpEngine,
                UdpTransportTarget,
                get_cmd,
            )
        except ImportError:
            logger.warning(
                "pysnmp library not installed — skipping SNMP enrichment. "
                "Install with: pip install pysnmp"
            )
            return []

        devices: List[DiscoveredDevice] = []
        sem = asyncio.Semaphore(20)

        async def _query(ip: str) -> Optional[DiscoveredDevice]:
            async with sem:
                try:
                    engine = SnmpEngine()
                    result = await get_cmd(
                        engine,
                        CommunityData(self._community),
                        await UdpTransportTarget.create((ip, 161), timeout=timeout, retries=0),
                        ContextData(),
                        ObjectType(ObjectIdentity(SYS_DESCR)),
                        ObjectType(ObjectIdentity(SYS_NAME)),
                    )

                    error_indication, error_status, _, var_binds = result
                    if error_indication or error_status:
                        return None

                    dev = DiscoveredDevice(ip_address=ip)
                    dev.discovered_by.append(DiscoveryProtocol.SNMP)

                    for oid, val in var_binds:
                        oid_str = str(oid)
                        val_str = str(val)
                        if SYS_DESCR in oid_str:
                            dev.snmp_sys_descr = val_str
                            if "axis" in val_str.lower():
                                dev.is_axis = True
                                dev.manufacturer = "Axis Communications"
                        elif SYS_NAME in oid_str:
                            dev.snmp_sys_name = val_str
                            dev.hostname = dev.hostname or val_str

                    return dev
                except Exception:
                    return None

        results = await asyncio.gather(
            *[_query(ip) for ip in self._targets],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, DiscoveredDevice):
                devices.append(r)

        return devices
