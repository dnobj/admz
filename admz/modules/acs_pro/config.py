"""ACS Pro connection config — the single enablement switch (ADR-0040).

The entire ACS Pro module footprint (nav item, MCP tools, prompt section) is
gated on ``acs_enabled()``: until the operator connects a server from the
Settings → Modules card, ACS Pro adds **zero** UI/tool surface.

Config is one JSON blob in the existing ``fleet_settings`` key/value store under
key ``acs_pro``. There is deliberately **no password field** — ACS authenticates
with the ADMZ process's own Windows identity via Negotiate (ADR-0035/0039), so
the only stored values are where to reach the server and whether it's on.
"""

from __future__ import annotations

import json
from typing import Any, Dict

FLEET_KEY = "acs_pro"
DEFAULT_PORT = 29204  # ACS Pro HTTPS "mobile API" port

_DEFAULT: Dict[str, Any] = {
    "enabled": False,
    "server_url": "",      # host or IP of the ACS Pro server
    "port": DEFAULT_PORT,
    "verify_tls": False,    # ACS ships a self-signed cert by default
}


def _settings():
    # Lazy import keeps this module importable in the leaf/MCP context.
    from admz.fleet_settings import fleet_settings

    return fleet_settings


def acs_config() -> Dict[str, Any]:
    """Current ACS Pro config, merged over defaults. Never raises."""
    cfg = dict(_DEFAULT)
    try:
        raw = _settings().get(FLEET_KEY)
        if raw:
            stored = json.loads(raw)
            if isinstance(stored, dict):
                cfg.update({k: stored[k] for k in _DEFAULT if k in stored})
    except Exception:  # noqa: BLE001 — config must never break a request
        pass
    cfg["enabled"] = bool(cfg.get("enabled")) and bool(cfg.get("server_url"))
    try:
        cfg["port"] = int(cfg.get("port") or DEFAULT_PORT)
    except (TypeError, ValueError):
        cfg["port"] = DEFAULT_PORT
    cfg["verify_tls"] = bool(cfg.get("verify_tls"))
    return cfg


def acs_enabled() -> bool:
    """True only when ACS Pro is enabled AND a server is configured.

    Every module factory (nav/tools/prompt) checks this so the module is
    invisible until connected.
    """
    return acs_config()["enabled"]


def base_url() -> str:
    """``https://<server>:<port>`` with no trailing slash, or '' if unset."""
    cfg = acs_config()
    host = (cfg.get("server_url") or "").strip()
    if not host:
        return ""
    # Allow the operator to paste a full URL; otherwise build one.
    if host.startswith(("http://", "https://")):
        return host.rstrip("/")
    return f"https://{host}:{cfg['port']}".rstrip("/")


def save_acs_config(
    *,
    enabled: bool,
    server_url: str,
    port: int = DEFAULT_PORT,
    verify_tls: bool = False,
) -> Dict[str, Any]:
    """Persist the ACS Pro config; returns the normalized stored config."""
    cfg = {
        "enabled": bool(enabled),
        "server_url": (server_url or "").strip(),
        "port": int(port or DEFAULT_PORT),
        "verify_tls": bool(verify_tls),
    }
    _settings().set(FLEET_KEY, json.dumps(cfg))
    return acs_config()
