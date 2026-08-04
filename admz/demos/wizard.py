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


def _observed_rule_keys(doc: Any):
    """Identities present in an ``action_rules`` facet, or ``None`` if the facet
    cannot answer the question at all.

    Replaces a substring test (``rid in str(doc)``) that could essentially never
    report a deleted rule: ``doc`` is the whole parsed facet, so the haystack
    contained every rule name, ONVIF topic and profile string, and ``rule_id``
    is a small AXIS integer. ``"2"`` matched ``Camera1Profile2``. See GH #198.

    Both the id **and** the name of every entry are collected, because
    ``snapshot/facets/action_rules.py``'s ``serialize`` keys the facet by
    ``str(rule.get("id") or rule.get("name") or i)`` — so on an entry with no
    id the key, and therefore the only identity available, is the rule's *name*.
    Matching on ids alone would report a real rule as vanished on that shape.

    Parsing is delegated to :func:`~admz.demos.inference.graph.normalize_device_rule`
    rather than reimplemented. It already owns the id-resolution chain
    (``id`` → ``rule_id`` → key) and the AXIS OS <12 firmware asymmetry, and a
    second parser for one facet is the drift that produced #255 and #274.

    Returns ``None`` — never an empty set — for a doc that is not a rule map or
    that contains an entry we cannot parse. That distinction is the point: an
    empty *set* means "readable, and this rule is gone", while ``None`` means
    "cannot tell". Collapsing the two would manufacture the permanent, false
    "your rule vanished" this module's docstring already argues against.
    """
    if not isinstance(doc, dict):
        return None
    from admz.demos.inference.graph import normalize_device_rule

    keys = set()
    for key in doc:
        try:
            r = normalize_device_rule("_", str(key), doc[key])
        except Exception:  # noqa: BLE001 — one bad entry means we cannot claim absence
            return None
        keys.add(str(r.get("rule_id")))
        if r.get("name"):
            keys.add(str(r["name"]))
    return keys


def _rules_status(ctx, demo) -> List[Dict[str, Any]]:
    """Each recorded rule + whether it's still present in the device's last
    audit (``action_rules`` facet). ``observed`` is None when we can't tell.

    **What is actually compared, and where each side comes from.** The left side
    is the demo's own recorded ``rule_id`` (ADMZ's DB). The right side is the
    ``action_rules`` facet read from the **git snapshot repo** at the device's
    ``latest_observed_sha`` — so this is the last *observation* of the device,
    not the device. That is deliberate and load-bearing: this module never
    probes (see the module docstring), because the chat has to answer "is the
    demo set up?" instantly. The consequence to keep in view is that
    ``observed`` can only ever be as fresh as the last snapshot — a rule deleted
    since then still reads ``True`` until the device is re-audited. It reports
    "present as of the last audit", which is weaker than "present now" and is
    the strongest claim a no-probe check can make.

    A membership entry with ``source != "device"`` (#124 slice 3 — an ACS action
    rule an inferred demo links to) is **never** looked for on a device: it does
    not live there. Checking anyway would read ``observed: false`` forever and
    render as a permanent, false "your rule vanished", so those entries report
    ``observed: None`` — unknown by construction, which is the truth.
    """
    out: List[Dict[str, Any]] = []
    for r in demo.rules or []:
        did = r.get("device_id") or ""
        rid = str(r.get("rule_id") or "")
        source = r.get("source") or "device"
        observed: Any = None
        if source == "device":
            try:
                info = ctx.registry.get_device_info(did) or {}
                ref = info.get("latest_observed_sha") or info.get("baseline_sha")
                doc = ctx.git_repo.read_facet(did, "action_rules", ref) if ref else None
                if doc is not None:
                    keys = _observed_rule_keys(doc)
                    if keys is not None:
                        name = str(r.get("rule_name") or "")
                        observed = rid in keys or bool(name and name in keys)
            except Exception:  # noqa: BLE001 — an unreadable facet leaves it "unknown"
                observed = None
        out.append({"device_id": did, "rule_id": rid, "source": source,
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
    # A recorded rule the last audit did not contain. Until #198 this branch
    # could not exist: `observed` was a substring test that essentially never
    # returned False. Note the branch above keys off `rules` being EMPTY, so
    # without this one a demo whose rule has vanished still falls through to
    # the "Demo looks set up" summary — the checklist would carry `observed:
    # false` in its rules table while its headline said the opposite, which is
    # the reading that terminates an operator's investigation.
    # `is False` on purpose: None means "cannot tell" and must not be reported
    # as a missing rule.
    vanished = [r for r in rules if r.get("observed") is False]
    if vanished:
        labels = ", ".join(
            f"'{r.get('rule_name') or r.get('rule_id')}' on {r.get('device_id')}"
            for r in vanished[:3])
        nxt.append(
            f"Re-create {len(vanished)} missing rule(s): {labels} "
            f"{'is' if len(vanished) == 1 else 'are'} recorded for this demo but "
            "absent from the device's last audit. Re-run check_drift to confirm "
            "it is still gone, then create_action_rule to restore it.")
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
