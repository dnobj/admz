"""Is the device at this address still the one the scan saw? (ADR-0072 §4)

An approved add writes to a device at an address a scan recorded. Between the
scan and the click, DHCP can hand that address to another box, and the
executor's host-moved refusal cannot notice: the registry host was just
written from the same scan. Without a check here, the fleet root password and
a new root account would land on whatever answers there now.

So before anything is written, the device is asked who it is, **without
credentials**: ``basicdeviceinfo.cgi:getAllUnrestrictedProperties`` answers
unauthenticated (catalog ``auth_level: none``). Its ``SerialNumber`` must be
the id the scan recorded — an Axis serial is its MAC.

**Fail-closed.** No answer, no serial, or a different serial all mean "not
confirmed", and the caller skips the device. Nothing is sent that could carry
a credential: the request goes out with the no-auth profile and empty
credentials, so a device that demands a password simply fails the check.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping, Optional, Tuple

from admz.device_registry import canonical_mac
from admz.discovery.candidates import device_identity

logger = logging.getLogger(__name__)

OPERATION_ID = "basicdeviceinfo.cgi:getAllUnrestrictedProperties"
#: Per-port TCP preflight, as onboarding's.
PREFLIGHT_SECONDS = 1.5
#: The whole identity read, once the device has accepted a connection.
READ_TIMEOUT_SECONDS = 10.0

_NO_AUTH = {"http": "none", "https": "none", "scheme": "http"}
_NO_CREDENTIALS = {"username": "", "password": ""}


def _serial_from(parsed: Any) -> str:
    """``SerialNumber`` wherever the parsed body put it."""
    node = parsed
    for _ in range(3):
        if not isinstance(node, Mapping):
            return ""
        serial = node.get("SerialNumber")
        if serial:
            return str(serial)
        node = node.get("propertyList") or node.get("data")
    return ""


async def read_unrestricted_serial(
    catalog: Any, executor: Any, host: str, *, family: str = "vapix",
) -> Optional[str]:
    """The serial the device at ``host`` reports without credentials, or
    ``None`` when it cannot be read. Never raises."""
    if not host or catalog is None or executor is None:
        return None
    # The operator is waiting on the approval request, so an address that no
    # longer answers must fail in seconds, not after the executor's timeout on
    # each scheme. Same preflight onboarding runs before its first probe.
    from admz.fleet.health import _tcp_probe

    if await _tcp_probe(host, 80, PREFLIGHT_SECONDS) is None and \
            await _tcp_probe(host, 443, PREFLIGHT_SECONDS) is None:
        return None
    try:
        op = catalog.get_operation(family, OPERATION_ID)
        if not op:
            return None
        device = {
            "host": host,
            "device_id": f"_identity_{host}",
            "auth_method": "none",
            "auth": dict(_NO_AUTH),
        }
        result = await asyncio.wait_for(
            executor.execute(op.to_executor_dict(), device,
                             dict(_NO_CREDENTIALS), {}),
            timeout=READ_TIMEOUT_SECONDS,
        )
    except Exception:  # noqa: BLE001 — unreachable / timeout / executor error
        logger.debug("identity read failed for %s", host, exc_info=True)
        return None
    if not getattr(result, "success", False):
        return None
    serial = _serial_from(getattr(result, "parsed_data", None))
    return serial or None


async def confirm_identity(
    catalog: Any, executor: Any, host: str, device_id: str,
) -> Tuple[bool, str]:
    """``(True, "")`` when the device at ``host`` reports ``device_id`` as its
    serial; otherwise ``(False, reason)``."""
    expected = canonical_mac(device_id)
    if not expected:
        return False, "no device id to confirm"
    serial = await read_unrestricted_serial(catalog, executor, host)
    if serial is None:
        return False, (
            f"could not confirm the device at {host} is {expected}: it did not "
            "report a serial number without credentials"
        )
    if canonical_mac(serial) != expected:
        # The reported serial is the device's own text and this reason reaches
        # the model through the console note, so it is quoted only when it has
        # the shape of a serial.
        reported = device_identity(serial) or "a different serial"
        return False, (
            f"the device at {host} now reports {reported}, not {expected} — "
            "the address has changed hands since the scan"
        )
    return True, ""
