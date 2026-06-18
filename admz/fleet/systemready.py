"""Shared ``systemready.cgi`` reader.

The one place that knows how to ask an Axis device "are you ready, and are you
factory-defaulted (``needsetup``)?". ``systemready.cgi`` answers without
authentication, so it works on a device that's been wiped and has no account
yet — which is exactly when we need to tell "factory-defaulted / needs setup"
apart from "wrong credentials".

Reused by the health monitor (classify ``needs_setup``), drift's readability
probe (precise unreadable reason), and the deferred-action trigger evaluator
("device came back in needsetup state").
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _to_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


async def read_systemready(
    catalog: Any,
    executor: Any,
    device_info: Dict[str, Any],
    credentials: Any,
    family: str = "vapix",
) -> Optional[Dict[str, Any]]:
    """Call ``systemready.cgi`` and return
    ``{systemready: bool, needsetup: bool, bootid: str|None, uptime: int|None}``,
    or ``None`` if it couldn't be read (no op / executor / device unreachable).
    Never raises."""
    try:
        op = catalog.get_operation(family, "systemready.cgi:systemReady")
        if not op:
            return None
        result = await executor.execute(
            op.to_executor_dict(), device_info, credentials, {}
        )
    except Exception:  # noqa: BLE001 - unreachable / executor error
        return None
    if not getattr(result, "success", False):
        return None
    data = getattr(result, "parsed_data", None) or {}
    inner = data.get("data") if isinstance(data, dict) and "data" in data else data
    if not isinstance(inner, dict):
        return None
    return {
        "systemready": str(inner.get("systemready", "")).lower() == "yes",
        "needsetup": str(inner.get("needsetup", "")).lower() == "yes",
        "bootid": str(inner.get("bootid") or "") or None,
        "uptime": _to_int(inner.get("uptime")),
    }
