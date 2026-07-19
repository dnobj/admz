"""Guided demo setup status (ADR-0050 Phase C).

``setup_status`` is a **deterministic, read-only** checklist for getting a demo
running end-to-end: devices/roles, owned config (fragments) + activation, rules
(recorded vs observed on the device), signals + last-seen, and event-capture
state — ending in ordered ``next_actions`` that name the exact remaining tool
calls. Cache/DB/git reads only; never probes a device (so the chat can answer
"is the demo set up?" instantly).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _rules_status(ctx, demo) -> List[Dict[str, Any]]:
    """Each recorded rule + whether it's still observed on the device's last
    audit (``action_rules`` facet). ``observed`` is None when we can't tell."""
    out: List[Dict[str, Any]] = []
    for r in demo.rules or []:
        did = r.get("device_id") or ""
        rid = str(r.get("rule_id") or "")
        observed: Any = None
        try:
            info = ctx.registry.get_device_info(did) or {}
            ref = info.get("latest_observed_sha") or info.get("baseline_sha")
            doc = ctx.git_repo.read_facet(did, "action_rules", ref) if ref else None
            if doc is not None:
                observed = rid in str(doc)  # rule id present anywhere in the facet doc
        except Exception:  # noqa: BLE001 — an unreadable facet leaves it "unknown"
            observed = None
        out.append({"device_id": did, "rule_id": rid,
                    "rule_name": r.get("rule_name"),
                    "condition_topic": r.get("condition_topic"), "observed": observed})
    return out


def _ingest_status(ctx, device_ids: List[str]) -> Dict[str, Any]:
    from admz.events import config as ev_cfg

    enabled = False
    try:
        enabled = ev_cfg.event_ingest_enabled()
    except Exception:  # noqa: BLE001
        pass
    tag = None
    try:
        tag = ev_cfg.tag_filter()
    except Exception:  # noqa: BLE001
        pass
    any_events = False
    store = getattr(ctx, "event_store", None)
    if store is not None and device_ids:
        for did in device_ids:
            try:
                if store.query(device_id=did, limit=1):
                    any_events = True
                    break
            except Exception:  # noqa: BLE001
                continue
    return {"enabled": enabled, "any_events": any_events,
            "tag_scope": tag,
            "tag_scope_warning": (
                f"Capture is scoped to tag '{tag}' — this demo's devices may not "
                "be captured unless they carry it." if tag else None)}


def setup_status(ctx, demo) -> Dict[str, Any]:
    """The deterministic setup checklist for ``demo`` (read-only)."""
    from admz.demos import fragments as fr
    from admz.demos import service

    view = service.demo_view(demo, ctx.registry, getattr(ctx, "event_store", None))
    device_ids = [d.get("device_id", "") for d in service.resolve_devices(demo, ctx.registry)]

    # Fragments the demo owns.
    set_keys = req_keys = 0
    roles = fr.load_all_fragments(ctx.git_repo, demo.id)
    for facets in roles.values():
        c = fr.fragment_entry_count(facets)
        set_keys += c.get(fr.MODE_SET, 0)
        req_keys += c.get(fr.MODE_REQUIRE, 0)

    rules = _rules_status(ctx, demo)
    signals = view.get("signal_status", [])
    ingest = _ingest_status(ctx, device_ids)

    status = {
        "demo_id": demo.id, "demo_name": demo.name,
        "active": bool(demo.active), "config_source": demo.config_source,
        "scenario_name": view.get("scenario_name"),
        "devices": [
            {"device_id": r.get("device_id"), "name": r.get("name"),
             "role": r.get("role"), "ready": r.get("ready"), "state": r.get("state")}
            for r in view.get("readiness", {}).get("rows", [])
        ] if isinstance(view.get("readiness"), dict) else [],
        "fragments": {"roles": len(roles), "set_keys": set_keys, "require_keys": req_keys},
        "rules": rules, "signals": signals, "ingest": ingest,
    }

    # ── Ordered next actions (the exact remaining tool calls) ────────────────
    nxt: List[str] = []
    if not device_ids:
        nxt.append("Add devices: update_demo with device_ids (or a tag) so the "
                   "demo has something to run on.")
    if set_keys == 0 and not view.get("scenario_name"):
        nxt.append("Capture config: run check_drift on each device, then "
                   "assign_demo_fragment to record the keys this demo owns.")
    elif (set_keys or view.get("scenario_name")) and not demo.active:
        nxt.append("Load the demo: prepare_demo (pushes its config + activates on "
                   "completion), or adopt_demo if the devices already match.")
    if not rules:
        nxt.append("Create the demo's rules: create_action_rule with "
                   f"demo='{demo.name}' — the trigger topic becomes its signal.")
    missing_signal = [s for s in signals if not s.get("seen")]
    if signals and missing_signal:
        labels = ", ".join(s.get("label") or "signal" for s in missing_signal[:3])
        nxt.append(f"Confirm signals fire: trigger {labels} and re-check "
                   "(demo_setup_status shows seen: true once captured).")
    if signals and not ingest["enabled"]:
        nxt.append("Turn on capture: set_event_ingest(enabled=true) so the demo's "
                   "signals are recorded and can be verified.")
    if not nxt:
        seen = sum(1 for s in signals if s.get("seen"))
        nxt.append(f"Demo looks set up — active, {len(rules)} rule(s), "
                   f"{seen}/{len(signals)} signal(s) seen recently.")
    status["next_actions"] = nxt
    return status
