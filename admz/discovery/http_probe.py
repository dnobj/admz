"""
HTTP / VAPIX device probing.

For each IP discovered by other protocols, makes a lightweight HTTP
request and checks for Axis-specific response headers and endpoints:

- ``Server`` header containing 'Boa' or 'AXIS'
- ``AXIS-Setup: vapix`` header on factory-default devices
- ``/axis-cgi/basicdeviceinfo.cgi`` (requires auth on configured devices)
"""

import asyncio
import logging
from typing import Dict, List, Optional

from admz.ssl_config import verify_ssl_default

from admz.discovery.base import DiscoveryProtocolBase
from admz.discovery.models import (
    DiscoveredDevice,
    DiscoveryProtocol,
    DeviceType,
)

logger = logging.getLogger(__name__)


class HTTPProbe(DiscoveryProtocolBase):
    """Probe known IPs over HTTP for VAPIX / Axis identification."""

    def __init__(self, targets: Optional[List[str]] = None):
        """
        Args:
            targets: List of IP addresses to probe.  Normally populated
                     by the orchestrator from other protocols' results.
        """
        self._targets = targets or []

    @property
    def name(self) -> str:
        return "HTTP/VAPIX Probe"

    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        if not self._targets:
            return []

        try:
            import httpx
        except ImportError:
            logger.warning(
                "httpx library not installed — skipping HTTP probing. "
                "Install with: pip install httpx"
            )
            return []

        devices: List[DiscoveredDevice] = []
        sem = asyncio.Semaphore(20)

        async def _probe(ip: str) -> Optional[DiscoveredDevice]:
            async with sem:
                return await self._probe_host(ip, timeout)

        results = await asyncio.gather(
            *[_probe(ip) for ip in self._targets],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, DiscoveredDevice):
                devices.append(r)

        return devices

    async def _probe_host(
        self, ip: str, timeout: float
    ) -> Optional[DiscoveredDevice]:
        import httpx

        dev = DiscoveredDevice(ip_address=ip)
        dev.discovered_by.append(DiscoveryProtocol.HTTP_PROBE)

        async with httpx.AsyncClient(
            timeout=timeout, verify=verify_ssl_default(), follow_redirects=True
        ) as client:
            # 1. Basic HTTP GET on port 80
            try:
                resp = await client.get(f"http://{ip}/")
                server = resp.headers.get("server", "")
                dev.http_server_header = server

                # Check for Axis signatures
                if "axis" in server.lower() or "boa" in server.lower():
                    dev.is_axis = True
                    dev.manufacturer = "Axis Communications"
                    dev.vapix_available = True

                # Factory-default devices return this header
                axis_setup = resp.headers.get("axis-setup", "")
                if axis_setup.lower() == "vapix":
                    dev.is_axis = True
                    dev.vapix_available = True
                    dev.factory_default = True
                    dev.manufacturer = "Axis Communications"

                # Newer Axis firmware (AXIS OS 12+) uses Apache and
                # references *.axis.com in the Content-Security-Policy.
                if not dev.is_axis:
                    csp = resp.headers.get("content-security-policy", "")
                    if ".axis.com" in csp:
                        dev.is_axis = True
                        dev.manufacturer = "Axis Communications"
                        dev.vapix_available = True

            except Exception:
                pass

            # 2. Try VAPIX basicdeviceinfo (may fail without auth)
            #    AXIS OS 12+ requires POST; older firmware uses GET.
            if dev.is_axis:
                try:
                    import json as _json
                    post_body = _json.dumps(
                        {"apiVersion": "1.0", "method": "getAllProperties"}
                    )
                    resp = await client.post(
                        f"http://{ip}/axis-cgi/basicdeviceinfo.cgi",
                        content=post_body,
                        headers={"Content-Type": "application/json"},
                    )
                    # Fall back to GET for older firmware
                    if resp.status_code in (405, 404):
                        resp = await client.get(
                            f"http://{ip}/axis-cgi/basicdeviceinfo.cgi"
                        )

                    if resp.status_code == 200:
                        # Verify response is real device info, not an
                        # API error (e.g. method-not-supported).
                        body = resp.text
                        is_error = False
                        try:
                            data = _json.loads(body)
                            if "error" in data and "data" not in data:
                                is_error = True
                        except (ValueError, TypeError):
                            pass

                        if not is_error:
                            await self._parse_basic_device_info(dev, body)
                            # Only mark factory_default if param.cgi is
                            # also open (it always requires auth when a
                            # password is configured).
                            if not dev.factory_default:
                                try:
                                    pr = await client.get(
                                        f"http://{ip}/axis-cgi/param.cgi"
                                        "?action=list&group=root.Brand"
                                    )
                                    if pr.status_code == 200:
                                        dev.factory_default = True
                                    elif pr.status_code == 401:
                                        # On AXIS OS 12+, factory-default
                                        # devices return 401 with
                                        # Axis-Setup: vapix on all endpoints.
                                        ax = pr.headers.get("axis-setup", "")
                                        if ax.lower() == "vapix":
                                            dev.factory_default = True
                                except Exception:
                                    pass
                    elif resp.status_code == 401:
                        # Auth required — device is configured, but still Axis
                        dev.vapix_available = True
                        # Factory-default devices return Axis-Setup: vapix
                        # on 401 responses (POST requires auth even when
                        # no password is set on AXIS OS 12+).
                        axis_setup = resp.headers.get("axis-setup", "")
                        if axis_setup.lower() == "vapix":
                            dev.factory_default = True
                            # GET may still work without auth for device info
                            try:
                                get_resp = await client.get(
                                    f"http://{ip}/axis-cgi/basicdeviceinfo.cgi"
                                )
                                if get_resp.status_code == 200:
                                    body = get_resp.text
                                    is_api_error = False
                                    try:
                                        data = _json.loads(body)
                                        if "error" in data and "data" not in data:
                                            is_api_error = True
                                    except (ValueError, TypeError):
                                        pass
                                    if not is_api_error:
                                        await self._parse_basic_device_info(
                                            dev, body
                                        )
                            except Exception:
                                pass
                except Exception:
                    pass

        if dev.is_axis or dev.http_server_header:
            return dev
        return None

    async def _parse_basic_device_info(
        self, dev: DiscoveredDevice, body: str
    ) -> None:
        """Parse VAPIX basicdeviceinfo response (JSON or key=value)."""
        import json

        try:
            data = json.loads(body)
            props = data.get("data", {}).get("properties", data)
        except (json.JSONDecodeError, AttributeError):
            # Fall back to key=value parsing
            props = {}
            for line in body.splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    props[k.strip()] = v.strip()

        dev.model = dev.model or props.get("ProdNbr") or props.get("model")
        dev.serial_number = dev.serial_number or props.get("SerialNumber") or props.get("serialnumber")
        dev.firmware_version = dev.firmware_version or props.get("Version") or props.get("firmware")
        dev.friendly_name = dev.friendly_name or props.get("ProdFullName")

        if dev.device_type == DeviceType.UNKNOWN:
            prod_type = (props.get("ProdType") or "").lower()
            if "camera" in prod_type or "video" in prod_type:
                dev.device_type = DeviceType.CAMERA
            elif "speaker" in prod_type or "audio" in prod_type:
                dev.device_type = DeviceType.SPEAKER
            elif "encoder" in prod_type:
                dev.device_type = DeviceType.ENCODER
            elif "radar" in prod_type:
                dev.device_type = DeviceType.RADAR
            elif "intercom" in prod_type or "station" in prod_type:
                dev.device_type = DeviceType.INTERCOM
