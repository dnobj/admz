"""Shared extraction of device identity facts from a basicdeviceinfo response.

``model`` / ``serial_number`` / ``firmware_version`` describe what a unit *is*.
They are read from ``basicdeviceinfo.cgi:getAllProperties`` and used by the
refresh-info endpoint, the replace-hardware rebind, and (opportunistically) the
health monitor — which already fetches that response to verify credentials, so
it can self-populate firmware on the health cadence with no extra probe.
"""

from __future__ import annotations

import json as _json
from typing import Any, Dict


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
