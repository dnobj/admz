"""MAC-based IP reconciliation.

Devices move IP when DHCP leases change. ADMZ keys a device by its MAC
(the ``device_id`` is the normalized MAC), so when a device's MAC turns up at
a new IP during discovery, its registered ``host`` can be corrected
automatically — following the MAC, not the stale IP. This prevents the
"looks online but ADMZ says unreachable" class of failures where the address
moved out from under the registry.

Leaf module: takes ``registry`` + the discovered devices as parameters; the
MCP/REST/CLI surfaces run discovery and call in here.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def normalize_mac(mac: Any) -> str:
    """Strip separators and upper-case a MAC so it matches a ``device_id``.

    ``"B8:A4:4F:0C:5B:32"`` and ``"b8-a4-4f-0c-5b-32"`` both → ``"B8A44F0C5B32"``.
    """
    if not mac:
        return ""
    return "".join(c for c in str(mac) if c.isalnum()).upper()


def _discovered_mac(d: Any) -> str:
    raw = d.get("mac_address") if isinstance(d, dict) else getattr(d, "mac_address", None)
    return normalize_mac(raw)


def _discovered_ip(d: Any) -> str:
    ip = d.get("ip_address") if isinstance(d, dict) else getattr(d, "ip_address", None)
    return str(ip) if ip else ""


def reconcile_device_ips(registry: Any, discovered: Any) -> List[Dict[str, Any]]:
    """Update registered devices whose MAC now answers at a different IP.

    ``discovered`` is an iterable of DiscoveredDevice objects (or dicts) with
    ``mac_address`` + ``ip_address``. A device is matched by its stored
    ``mac_address`` if present, else by its ``device_id`` (the MAC).

    Returns one entry per *change applied*: ``{device_id, old_host, new_ip}``
    (with an ``error`` key if the registry write failed). Devices already at
    the right IP, or not seen by discovery, are left untouched.
    """
    by_mac: Dict[str, str] = {}
    for d in discovered or []:
        mac, ip = _discovered_mac(d), _discovered_ip(d)
        if mac and ip:
            by_mac.setdefault(mac, ip)  # first responder for a MAC wins

    changes: List[Dict[str, Any]] = []
    try:
        devices = registry.list_devices()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("reconcile: list_devices failed: %s", exc)
        return changes

    for dev in devices:
        device_id = dev.get("device_id")
        if not device_id:
            continue
        mac = normalize_mac(dev.get("mac_address") or device_id)
        new_ip = by_mac.get(mac)
        cur_host = dev.get("host")
        if not new_ip or new_ip == cur_host:
            continue
        try:
            registry.update_device_info(device_id, {"host": new_ip})
            logger.info(
                "reconcile: %s host %s -> %s (MAC %s)",
                device_id, cur_host, new_ip, mac,
            )
            changes.append({"device_id": device_id, "old_host": cur_host, "new_ip": new_ip})
        except Exception as exc:
            logger.warning("reconcile: could not update %s: %s", device_id, exc)
            changes.append({
                "device_id": device_id, "old_host": cur_host,
                "new_ip": new_ip, "error": str(exc),
            })
    return changes
