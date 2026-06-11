"""Shared Jinja2 configuration for the ADMZ web UI.

Centralizes the "Axis Signal" chrome data so individual route handlers
don't each have to assemble org/site/group navigation. ``configure(templates)``
registers a small set of Jinja globals/filters on a ``Jinja2Templates``
instance; ``build_nav(request)`` does the actual hierarchy lookups.

The nav is intentionally defensive: the hierarchy backend (orgs/sites/
groups) is optional on some registries (e.g. Vault), so every lookup is
wrapped and falls back to a sensible single-site default. The web UI must
render even before any real Org is created.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# Health → semantic colour key (mirrors tokens.jsx HEALTH map).
HEALTH_SEM = {
    "online": "green",
    "unreachable": "red",
    "auth-failed": "amber",
    "authfail": "amber",
    "unknown": "grey",
    None: "grey",
}
HEALTH_LABEL = {
    "online": "Online",
    "unreachable": "Unreachable",
    "auth-failed": "Auth failed",
    "authfail": "Auth failed",
    "unknown": "Unknown",
}

# Risk → semantic key + short code (mirrors tokens.jsx RISK map).
RISK_SEM = {
    "read-only": ("green", "READ"),
    "readonly": ("green", "READ"),
    "normal": ("blue", "NORMAL"),
    "service-affecting": ("amber", "SERVICE"),
    "service": ("amber", "SERVICE"),
    "dangerous": ("red", "DANGER"),
}

DRIFT_SEM = {
    "clean": ("green", "In sync"),
    "in-sync": ("green", "In sync"),
    "drifted": ("red", "Drifted"),
    "none": ("grey", "No baseline"),
    "no-baseline": ("grey", "No baseline"),
}


def _registry():
    try:
        from admz.api.main import registry

        return registry
    except Exception:
        return None


def _initials(name: str) -> str:
    if not name:
        return "AD"
    name = name.split("\\")[-1].split("@")[0]
    parts = [p for p in name.replace(".", " ").replace("_", " ").split() if p]
    if not parts:
        return name[:2].upper()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def _device_health(device: Dict[str, Any]) -> str:
    """Best-effort health string from a device dict."""
    h = device.get("health") or device.get("health_status") or device.get("status")
    if isinstance(h, dict):
        h = h.get("status")
    return h or "unknown"


def build_nav(request) -> Dict[str, Any]:
    """Assemble the chrome navigation context for the active request.

    Returns a dict with: org_name, sites[], active_site, tags[],
    active_tag, principal{name,initials}.
    """
    reg = _registry()
    nav: Dict[str, Any] = {
        "org_name": "ADMZ",
        "sites": [],
        "active_site": None,
        "tags": [],
        "active_tag": request.query_params.get("tag"),
        "principal": {"name": "", "initials": "AD"},
        "hierarchy_enabled": False,
    }

    # Principal (set by auth middleware on request.state when available).
    principal = getattr(getattr(request, "state", None), "principal", None)
    if principal is not None:
        pname = getattr(principal, "display_name", None) or getattr(principal, "name", "")
        nav["principal"] = {"name": pname, "initials": _initials(pname)}

    if reg is None:
        return nav

    try:
        orgs = reg.list_organizations()
    except Exception:
        return nav  # hierarchy not supported on this backend

    nav["hierarchy_enabled"] = True

    # Active org = first non-default org if any exists, else default.
    org = None
    non_default = [o for o in orgs if o.get("org_id") != "default"]
    if non_default:
        org = non_default[0]
    elif orgs:
        org = orgs[0]
    if org:
        nav["org_name"] = org.get("name") or "ADMZ"
    org_id = org.get("org_id") if org else None

    try:
        all_devices = reg.list_devices()
    except Exception:
        all_devices = []

    # Map device_id -> site_id (separate columns, not in info_json).
    dev_site: Dict[str, Optional[str]] = {}
    for d in all_devices:
        did = d.get("device_id")
        try:
            os_ = reg.get_device_org_site(did)
            dev_site[did] = (os_ or {}).get("site_id")
        except Exception:
            dev_site[did] = None

    def _site_devices(site_id: str) -> List[Dict[str, Any]]:
        return [d for d in all_devices if dev_site.get(d.get("device_id")) == site_id]

    try:
        sites = reg.list_sites(org_id) if org_id else reg.list_sites()
    except Exception:
        sites = []

    site_entries = []
    for s in sites:
        sid = s.get("site_id")
        devs = _site_devices(sid)
        issues = sum(1 for d in devs if _device_health(d) not in ("online", "unknown"))
        short = (s.get("metadata", {}) or {}).get("short") if isinstance(s.get("metadata"), dict) else None
        site_entries.append(
            {
                "id": sid,
                "name": s.get("name") or sid,
                "count": len(devs),
                "issues": issues,
                "short": short or sid,
            }
        )
    nav["sites"] = site_entries

    # Active site: cookie, falling back to first site / "default".
    cookie_site = request.cookies.get("admz_site")
    active_id = None
    if cookie_site and any(e["id"] == cookie_site for e in site_entries):
        active_id = cookie_site
    elif site_entries:
        active_id = site_entries[0]["id"]
    nav["active_site"] = next((e for e in site_entries if e["id"] == active_id), None)

    # Tags for the active site's devices (ADR-0032: tags are the
    # device-grouping primitive — there is no Group level). Counts are
    # exact-membership, matching tag_filter semantics everywhere else.
    # An "Untagged" pseudo-row appears only when untagged devices exist.
    if active_id:
        site_devs = _site_devices(active_id)
        tag_counts: Dict[str, int] = {}
        untagged = 0
        for d in site_devs:
            tags = d.get("tags") or []
            if not tags:
                untagged += 1
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        nav["tags"] = [
            {"id": t, "name": t, "count": c}
            for t, c in sorted(tag_counts.items())
        ]
        if untagged:
            nav["tags"].append(
                {"id": "untagged", "name": "Untagged", "count": untagged}
            )

    return nav


# ── Jinja filters ─────────────────────────────────────────────────────────

def health_sem(health: Optional[str]) -> str:
    return HEALTH_SEM.get(health, "grey")


def health_label(health: Optional[str]) -> str:
    return HEALTH_LABEL.get(health, "Unknown")


def risk_sem(risk: Optional[str]) -> str:
    return RISK_SEM.get((risk or "").lower(), ("grey", "—"))[0]


def risk_short(risk: Optional[str]) -> str:
    return RISK_SEM.get((risk or "").lower(), ("grey", (risk or "—").upper()))[1]


def drift_sem(drift: Optional[str]) -> str:
    return DRIFT_SEM.get((drift or "").lower(), ("grey", "No baseline"))[0]


def drift_label(drift: Optional[str]) -> str:
    return DRIFT_SEM.get((drift or "").lower(), ("grey", "No baseline"))[1]


def initials(name: str) -> str:
    return _initials(name)


def configure(templates) -> None:
    """Register ADMZ globals + filters on a Jinja2Templates instance."""
    env = templates.env
    env.globals["admz_nav"] = build_nav
    env.filters["health_sem"] = health_sem
    env.filters["health_label"] = health_label
    env.filters["risk_sem"] = risk_sem
    env.filters["risk_short"] = risk_short
    env.filters["drift_sem"] = drift_sem
    env.filters["drift_label"] = drift_label
    env.filters["initials"] = initials
