"""What the console may add from a discovery scan (ADR-0072 §2).

A scan records every device it found. This module answers three questions
about each record, the same way for the MCP result, the widget's GET and the
add route, so the three cannot disagree:

* **Who is it?** :func:`device_identity` — the canonical MAC, or failing that
  a 12-hex serial, because an Axis serial *is* its MAC. The deep survey uses
  the MAC as the device id (``demos/inference/collect.py``); so does this.
* **Is it already managed?** :func:`registered_index` + :func:`annotate`,
  matched by canonical MAC against the live registry — computed when read, so
  a device added after the scan shows as registered.
* **Can the operator add it?** :func:`add_blocker` — an Axis device with an
  address and an identity that is not registered. Anything else says why not.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

from admz.device_registry import canonical_mac

#: At most this many devices per add (ADR-0072 decision 5).
MAX_ADD_BATCH = 20
#: A scan older than this cannot be added from (ADR-0072 decision 4).
MAX_SCAN_AGE_SECONDS = 3600
#: Onboarding runs at most this many devices at once.
ADD_CONCURRENCY = 4

BLOCK_REGISTERED = "already registered"
BLOCK_NOT_AXIS = "not an Axis device"
BLOCK_NO_IDENTITY = "no MAC or serial number to identify it"
BLOCK_NO_ADDRESS = "no IP address"

_HEX12 = re.compile(r"^[0-9A-F]{12}$")

#: The fields a scan record shows. The same keys the tool returned before
#: ADR-0072, so a caller that read them is unaffected.
DISPLAY_FIELDS = (
    "ip_address", "mac_address", "hostname", "model", "serial_number",
    "firmware_version", "manufacturer", "friendly_name", "device_type",
    "is_axis", "vapix_available", "factory_default", "discovered_by",
)


def device_identity(mac: Any, serial: Any = None) -> str:
    """The id a discovered device would be registered under, or ``""``."""
    for value in (mac, serial):
        candidate = canonical_mac(str(value) if value else "")
        if _HEX12.match(candidate):
            return candidate
    return ""


def scan_record(device: Any) -> Dict[str, Any]:
    """One stored scan entry for a :class:`~admz.discovery.models.DiscoveredDevice`."""
    record: Dict[str, Any] = {
        "ip_address": device.ip_address,
        "mac_address": device.mac_address,
        "hostname": device.hostname,
        "model": device.model,
        "serial_number": device.serial_number,
        "firmware_version": device.firmware_version,
        "manufacturer": device.manufacturer,
        "friendly_name": device.friendly_name,
        "device_type": device.device_type.value,
        "is_axis": device.is_axis,
        "vapix_available": device.vapix_available,
        "factory_default": device.factory_default,
        "discovered_by": [p.value for p in device.discovered_by],
    }
    record["device_id"] = device_identity(device.mac_address, device.serial_number)
    record["registry_info"] = device.to_registry_dict()
    return record


def display_view(record: Mapping[str, Any]) -> Dict[str, Any]:
    """The record without its registry payload — what a result shows."""
    return {k: record.get(k) for k in DISPLAY_FIELDS}


def registered_index(registry: Any) -> Dict[str, str]:
    """Canonical MAC → registered ``device_id``, for every managed device.

    Both the stored MAC and the device id are indexed: a device registered by
    hand may carry its MAC only in its id. An unreadable registry yields an
    empty index, which reads as "nothing registered" — the add path re-checks
    the registry itself before writing, so this never admits a duplicate.
    """
    index: Dict[str, str] = {}
    try:
        devices = registry.list_devices() or []
    except Exception:  # noqa: BLE001 — a view must degrade, not raise
        return index
    for device in devices:
        device_id = str(device.get("device_id") or "")
        for value in (device.get("mac_address"), device_id):
            key = canonical_mac(str(value) if value else "")
            if _HEX12.match(key):
                index.setdefault(key, device_id)
    return index


def add_blocker(record: Mapping[str, Any], registered_device_id: str = "") -> str:
    """Why this record cannot be added, or ``""`` when it can."""
    if registered_device_id:
        return BLOCK_REGISTERED
    if not record.get("is_axis"):
        return BLOCK_NOT_AXIS
    if not record.get("device_id"):
        return BLOCK_NO_IDENTITY
    if not record.get("ip_address"):
        return BLOCK_NO_ADDRESS
    return ""


def annotate(
    records: Iterable[Mapping[str, Any]], index: Mapping[str, str],
) -> List[Dict[str, Any]]:
    """Display views with live ``registered_device_id`` and ``add_blocker``."""
    out: List[Dict[str, Any]] = []
    for record in records:
        view = display_view(record)
        view["device_id"] = record.get("device_id") or ""
        registered = index.get(view["device_id"], "") if view["device_id"] else ""
        view["registered_device_id"] = registered or None
        view["add_blocker"] = add_blocker(record, registered)
        out.append(view)
    return out


def summary_counts(views: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    """Counts a model can quote even when the device list is truncated."""
    views = list(views)
    axis = [v for v in views if v.get("is_axis")]
    return {
        "axis_count": len(axis),
        "new_axis_count": sum(1 for v in axis if not v.get("registered_device_id")),
        "factory_default_count": sum(1 for v in views if v.get("factory_default")),
    }


def find_record(
    records: Iterable[Mapping[str, Any]], device_id: str,
) -> Optional[Mapping[str, Any]]:
    for record in records:
        if record.get("device_id") and record.get("device_id") == device_id:
            return record
    return None
