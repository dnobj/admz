"""Shared ``systemready.cgi`` reader.

The one place that knows how to ask an Axis device "are you ready, and are you
factory-defaulted (``needsetup``)?". ``systemready.cgi`` answers without
authentication, so it works on a device that's been wiped and has no account
yet — which is exactly when we need to tell "factory-defaulted / needs setup"
apart from "wrong credentials".

Reused by the health monitor's credential-less tier (classify ``needs_setup``),
drift's readability probe (precise unreadable reason), and onboarding's
factory-default check (#479). All three ask it with no credential at all: the
reader takes none, so no caller can send one.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _to_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def unauthenticated(device_info: Dict[str, Any]) -> Dict[str, Any]:
    """``device_info`` with authentication switched off on both schemes.

    Both, because the executor falls back to the other scheme when the
    configured one refuses the connection, and takes that scheme's method from
    the same profile. Other profile keys (``scheme``) are kept."""
    return {
        **device_info,
        "auth": {**(device_info.get("auth") or {}), "http": "none", "https": "none"},
        "auth_method": "none",
    }


async def read_systemready(
    catalog: Any,
    executor: Any,
    device_info: Dict[str, Any],
    *,
    family: str = "vapix",
) -> Optional[Dict[str, Any]]:
    """Call ``systemready.cgi`` and return
    ``{systemready: bool, needsetup: bool, bootid: str|None, uptime: int|None}``,
    or ``None`` if it couldn't be read (no op / executor / device unreachable).
    Never raises.

    Always asked with no credential (#479). The op is auth-free by design, and
    each caller asks it when ADMZ has no credential that works: none is
    stored, or the device has just refused the stored one. Presenting a pair
    then is a credentialed request for nothing. Both halves are needed:

    - auth switched off, or a ``basic`` profile sends a Basic header on the
      first request;
    - an empty pair, because on a 401 whose challenge names Digest (or Basic,
      over HTTPS) the executor retries with that method using whatever pair it
      was handed (``VapixExecutor._send_self_healing``). Handed the stored
      password, that retry would put it on the wire.

    ``family`` is keyword-only so a stray positional credential fails loudly
    rather than being taken for a family name, which the ``except`` below would
    turn into a silent ``None``."""
    try:
        op = catalog.get_operation(family, "systemready.cgi:systemReady")
        if not op:
            return None
        result = await executor.execute(
            op.to_executor_dict(), unauthenticated(device_info),
            {"username": "", "password": ""}, {},
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
