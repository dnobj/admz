"""Shared extraction of device identity facts from a basicdeviceinfo response.

``model`` / ``serial_number`` / ``firmware_version`` describe what a unit *is*.
They are read from ``basicdeviceinfo.cgi:getAllProperties`` and used by the
refresh-info endpoint, the replace-hardware rebind, and (opportunistically) the
health monitor — which already fetches that response to verify credentials, so
it can self-populate firmware on the health cadence with no extra probe.

``extract_sd_card`` reads SD-card *presence* out of a ``disks-list.cgi``
response: the per-disk ``status`` attribute is the authoritative signal
(``disconnected`` = empty slot; ``OK`` = card inserted and working). The
root.Storage params can't answer this — their Enabled=yes only means the
slot is configured, which is why presence has to come from this API.
"""

from __future__ import annotations

import json as _json
from typing import Any, Dict, Optional, Tuple


def extract_device_facts(parsed: Any) -> Dict[str, str]:
    """Pull model / serial / firmware out of a basicdeviceinfo response.

    Robust to shape: the props can sit under ``data.propertyList``,
    ``data.properties``, or at the top level, and the payload may arrive as a
    dict (json-rpc) or a ``key=value`` string (legacy). Keys are matched
    case-insensitively (ProdNbr / SerialNumber / Version)."""
    props: Dict[str, str] = {}

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    _walk(v)
                else:
                    props.setdefault(str(k).lower(), v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    if isinstance(parsed, str):
        try:
            _walk(_json.loads(parsed))
        except Exception:
            for line in parsed.splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    props.setdefault(k.strip().lower(), v.strip())
    else:
        _walk(parsed)

    facts: Dict[str, str] = {}
    if props.get("prodnbr"):
        facts["model"] = str(props["prodnbr"])
    if props.get("serialnumber"):
        facts["serial_number"] = str(props["serialnumber"])
    if props.get("version"):
        facts["firmware_version"] = str(props["version"])
    return facts


def extract_sd_card(parsed: Any) -> "Tuple[Optional[str], Optional[int]]":
    """``(status, total_kb)`` for the SD_DISK entry of a disks-list response.

    ``status`` is the device's own word (``disconnected`` / ``connected`` /
    ``OK`` / ``failed`` / encryption states), or ``"no_slot"`` when the
    response parsed fine but carries no SD_DISK entry (e.g. a P8815-2 that
    only has NetworkShare). ``(None, None)`` when the shape is unrecognized —
    callers must treat that as *unknown*, not as absent.

    Robust to the XML-to-dict shapes the executor produces: attributes may be
    ``@``-prefixed, and a single-disk device yields ``disk`` as a dict rather
    than a list.
    """
    def _attr(d: Dict[str, Any], key: str) -> Any:
        return d.get("@" + key, d.get(key))

    disks: Any = None

    def _find_disks(obj: Any) -> None:
        nonlocal disks
        if disks is not None:
            return
        if isinstance(obj, dict):
            if "disk" in obj:
                disks = obj["disk"]
                return
            for v in obj.values():
                _find_disks(v)
        elif isinstance(obj, list):
            for item in obj:
                _find_disks(item)

    _find_disks(parsed)
    if disks is None:
        return None, None
    if isinstance(disks, dict):
        disks = [disks]
    if not isinstance(disks, list):
        return None, None

    for disk in disks:
        if not isinstance(disk, dict):
            continue
        if str(_attr(disk, "diskid") or "") != "SD_DISK":
            continue
        status = str(_attr(disk, "status") or "") or None
        total_kb: Optional[int] = None
        raw_total = _attr(disk, "totalsize")
        try:
            total_kb = int(raw_total)
        except (TypeError, ValueError):
            total_kb = None
        return status, total_kb
    return "no_slot", None
