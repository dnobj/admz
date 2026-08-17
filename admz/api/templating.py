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

from admz.hierarchy import device_is_in_site
from admz import build_info


# Health → semantic colour key (mirrors tokens.jsx HEALTH map).
# Keys are the raw ``DeviceHealthStatus`` values (underscored) plus the
# hyphenated spellings older callers pass. ``reachable_no_api`` is amber, not
# red (GH #138): the device is demonstrably up — ADMZ just can't speak its
# API — so it belongs with the other "needs attention" states, never with a
# network outage.
HEALTH_SEM = {
    "online": "green",
    "unreachable": "red",
    # GH #357: up AND a managed read works — it is not an attention state, so
    # it is not amber. The caveat lives in the label, not the colour.
    "limited_api": "green",
    "reachable_no_api": "amber",
    "auth_failed": "amber",
    "auth-failed": "amber",
    "authfail": "amber",
    "needs_setup": "amber",
    "unknown": "grey",
    None: "grey",
}
HEALTH_LABEL = {
    "online": "Online",
    "unreachable": "Unreachable",
    "limited_api": "Online, limited API",
    "reachable_no_api": "Reachable, no API",
    "auth_failed": "Auth failed",
    "auth-failed": "Auth failed",
    "authfail": "Auth failed",
    "needs_setup": "Needs setup",
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

# Demo readiness → semantic key + label (ADR-0046). "Not loaded" is amber, not
# red: it's the expected resting state of a sidelined demo, and the fix is one
# button (Prepare), not an investigation.
DEMO_SEM = {
    "ready": ("green", "Ready"),
    "not_loaded": ("amber", "Not loaded"),
    "blocked": ("red", "Blocked"),
    "not_ready": ("red", "Not ready"),
    "empty": ("grey", "No devices"),
}

# Per-device config verdict → semantic key + label.
DEMO_CONFIG_SEM = {
    "ready": ("green", "Config OK"),
    "not_loaded": ("amber", "Not loaded"),
    "drifted": ("red", "Drifted"),
    "on_loan": ("red", "On loan"),
    "conflict": ("red", "Conflict"),
    "no_baseline": ("grey", "No baseline"),
    "unchecked": ("grey", "Not checked"),
}


def _registry():
    try:
        from admz.api.main import registry

        return registry
    except Exception:
        return None


def _module_registry():
    """The discovered platform-module set (ADR-0039), for module nav sections.

    Prefers the app context's registry; falls back to an on-demand discovery so
    the nav renders in tests / before the context is initialized. Discovery is
    pure and cheap (it imports + lists modules; it does not build executors).
    """
    try:
        from admz.api.context import get_context

        return get_context().module_registry
    except Exception:
        try:
            from admz.modules.registry import ModuleRegistry

            return ModuleRegistry().discover()
        except Exception:
            return None


def _demo_count() -> Optional[int]:
    """How many demos are defined — the Demos nav badge (ADR-0046).

    Cheap (one indexed read) and defensive: the nav must render on a backend that
    has never seen a demo. None hides the badge rather than showing a bare 0.
    """
    try:
        from admz.demos.store import get_store

        n = len(get_store().list())
        return n or None
    except Exception:
        return None


def _advanced_chip() -> Optional[Dict[str, Any]]:
    """The topbar advanced-capability chip, or None when there is nothing to say.

    This is loudness channel 3 of GH #132: because it lives in ``base.html`` it
    appears on **every** page and behind the console dock, so a production
    install running with the dev auto-approver on is impossible to miss.

    Two rules, both deliberate:

    * **Absent when clean.** A normal install never sees it, which is what
      makes it mean something when it does appear.
    * ``internal``-class capabilities never chip. ``runtime.no_scheduler`` is a
      role marker ADMZ sets for its own subprocesses; chipping it would put a
      permanent badge on boxes where nothing is wrong and train operators to
      ignore the badge — the exact failure this channel exists to avoid.

    Red when any active capability is not production-appropriate, amber for a
    purely privileged install profile. Defensive throughout: the nav must
    render even if the settings store is unreachable.
    """
    try:
        from admz import capabilities

        active = [
            a for a in capabilities.active_capabilities()
            if a.capability.danger != "internal"
        ]
        if not active:
            return None
        loud = [a for a in active if not a.capability.production_appropriate]
        return {
            "count": len(active),
            "severity": "red" if loud else "amber",
            "ids": [a.id for a in active],
            "label": ", ".join(f"{a.id} (via {a.source})" for a in active),
        }
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

    Returns the hierarchy data (org_name, sites[], active_site, tags[],
    active_tag, principal) plus a data-driven ``sections`` list (ADR-0039)
    that the sidebar renders without hardcoding items.
    """
    nav = _build_nav_data(request)
    nav["sections"] = _assemble_nav_sections(nav)
    return nav


def _build_nav_data(request) -> Dict[str, Any]:
    """The hierarchy lookups: org/site/tags/principal (no presentation)."""
    reg = _registry()
    nav: Dict[str, Any] = {
        "org_name": "ADMZ",
        "sites": [],
        "active_site": None,
        "tags": [],
        "active_tag": request.query_params.get("tag"),
        "principal": {"name": "", "initials": "AD"},
        "hierarchy_enabled": False,
        # GH #132 — None on a normal install, so base.html renders nothing.
        "advanced": _advanced_chip(),
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
        # Shared with the roster's own scoping (GH #427). This used to be a
        # strict `== site_id`, which dropped every device whose site was NULL,
        # while `routes/web.py` kept them — same registry, 5 in the nav and 11
        # on the page.
        return [
            d for d in all_devices
            if device_is_in_site(dev_site.get(d.get("device_id")), site_id)
        ]

    try:
        sites = reg.list_sites(org_id) if org_id else reg.list_sites()
    except Exception:
        sites = []

    site_entries = []
    for s in sites:
        sid = s.get("site_id")
        devs = _site_devices(sid)
        # `limited_api` is not an issue (GH #357) — the device is up and ADMZ
        # reads it; counting it here would put a permanent badge on any site
        # holding a T85-class switch, which is the site-level version of the
        # attention-bucket parking this issue fixed.
        issues = sum(
            1 for d in devs
            if _device_health(d) not in ("online", "limited_api", "unknown")
        )
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


def _assemble_nav_sections(nav: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build the data-driven sidebar (ADR-0039, user nav decision 2026-06-19).

    The sidebar is a list of sections:
      * **Core** — pinned at the top, no header/divider: Console, Devices,
        Tasks, Audit log, Settings (fixed order). The **tags move UNDER
        Devices** as a child sub-nav (``children[]``) — no longer a standalone
        "Tags" section below the divider.
      * **Module sections** — each platform module contributes its own
        divider-separated section (optional header + 1..N items). Empty in PR1
        (the devices module folds into Core); ACS Pro adds one in PR2.

    Every child carries a ``tag`` key (None for non-tag children) so a single
    template rule — active iff ``active == key and nav.active_tag == tag`` —
    works for both the device tag sub-nav and future module sub-navs.
    """
    active_site = nav.get("active_site")
    site_count = active_site["count"] if active_site else None

    # Devices' tag sub-nav (only when a site is active). No "All devices" row —
    # the Devices item itself is "all" (active when no ?tag is selected). The
    # sub-nav is rendered by base.html only while Devices is the active page.
    device_children: List[Dict[str, Any]] = []
    if active_site:
        for t in nav.get("tags", []):
            device_children.append(
                {
                    "key": "fleet", "label": t["name"],
                    "href": f"/devices?tag={t['id']}",
                    "icon": "tag", "count": t["count"], "tag": t["id"],
                }
            )

    core = {
        "id": "core",
        "title": "",
        "items": [
            {"key": "console", "label": "Console", "href": "/chat",
             "icon": "sparkles", "accent": True, "badge": "⌘K"},
            # ADR-0046: the job view sits above the inventory view — in an
            # experience center the unit of work is the demo, not the device.
            {"key": "demos", "label": "Demos", "href": "/demos",
             "icon": "presentation", "badge": _demo_count()},
            {"key": "fleet", "label": "Devices", "href": "/devices",
             "icon": "layout-grid", "badge": site_count, "children": device_children},
            {"key": "tasks", "label": "Tasks", "href": "/tasks", "icon": "list-checks", "badge": None},
            {"key": "activity", "label": "Activity", "href": "/activity", "icon": "activity", "badge": None},
            {"key": "auditlog", "label": "Audit log", "href": "/audit-log", "icon": "shield", "badge": None},
            {"key": "settings", "label": "Settings", "href": "/settings", "icon": "settings", "badge": None},
        ],
    }

    sections: List[Dict[str, Any]] = [core]

    # Module sections (PR2+). Each NavSection → a divider-separated group.
    reg = _module_registry()
    if reg is not None:
        try:
            for sec in reg.nav_sections_all(nav):
                sections.append(
                    {
                        "id": sec.id,
                        "title": sec.title,
                        "items": [
                            {
                                "key": it.key, "label": it.label, "href": it.href,
                                "icon": it.icon,
                                "children": [
                                    {"key": c.key, "label": c.label, "href": c.href,
                                     "icon": c.icon, "tag": None, "count": None}
                                    for c in it.children
                                ],
                            }
                            for it in sec.items
                        ],
                    }
                )
        except Exception:
            pass  # nav must render even if a module's nav_section raises

    return sections


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


def demo_sem(state: Optional[str]) -> str:
    return DEMO_SEM.get((state or "").lower(), ("grey", "Unknown"))[0]


def demo_label(state: Optional[str]) -> str:
    return DEMO_SEM.get((state or "").lower(), ("grey", "Unknown"))[1]


def demo_config_sem(state: Optional[str]) -> str:
    return DEMO_CONFIG_SEM.get((state or "").lower(), ("grey", "Unknown"))[0]


def demo_config_label(state: Optional[str]) -> str:
    return DEMO_CONFIG_SEM.get((state or "").lower(), ("grey", "Unknown"))[1]


def initials(name: str) -> str:
    return _initials(name)


def configure(templates) -> None:
    """Register ADMZ globals + filters on a Jinja2Templates instance."""
    env = templates.env
    env.globals["admz_nav"] = build_nav
    # A Jinja global, not a per-route context key (GH #432). The question it
    # answers — "am I looking at the latest build?" — is asked from whatever
    # page the operator happens to be on, and a route that forgot to pass it
    # would answer by showing nothing, which reads as "no build info" rather
    # than "this route forgot". Resolved once and cached in build_info.
    env.globals["build_id"] = build_info.build_id()
    env.filters["health_sem"] = health_sem
    env.filters["health_label"] = health_label
    env.filters["risk_sem"] = risk_sem
    env.filters["risk_short"] = risk_short
    env.filters["drift_sem"] = drift_sem
    env.filters["drift_label"] = drift_label
    env.filters["demo_sem"] = demo_sem
    env.filters["demo_label"] = demo_label
    env.filters["demo_config_sem"] = demo_config_sem
    env.filters["demo_config_label"] = demo_config_label
    env.filters["initials"] = initials
