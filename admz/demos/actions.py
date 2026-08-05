"""Shared demo write cores — one implementation for REST, MCP, and the
confirm-widget action executors.

The REST routes owned this logic inline until the chat console needed the same
moves. Same shape as the codebase's other shared cores (``tasks/gated.py``,
``snapshot/scenarios.py``): plain functions taking the app context + already-
resolved inputs, raising :class:`DemoActionError` (with an HTTP-ish ``status``)
so each surface maps errors its own way — REST to HTTPException, MCP to result
dicts. Audit rows are written HERE so every surface gets them for free.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from admz.demos import service
from admz.demos.store import Demo

logger = logging.getLogger(__name__)

# The only demo fields a caller may set/patch — everything else is computed.
DEMO_FIELDS = ("name", "narrative", "tag", "device_ids", "roles",
               "config_source", "signals", "enabled")

# #191: a demo name is written by an ungated MCP tool (create_demo,
# confirm_demo_proposal) and rendered into EVERY future chat/voice system
# prompt via admz/chatbot/context.py:build_demos_section — no confirmation
# gate stands between a caller and every future principal's prompt. Reject
# the shapes that let a name masquerade as prompt structure rather than a
# label: control characters/newlines (the concrete #167/#191 exploit — a
# newline lets a name split into extra lines once rendered) and unbounded
# length (an unbounded name is also a per-turn token amplifier). This is a
# reject-at-the-door check, not the render-time sanitizer in
# admz/chatbot/context.py: a caller naming a demo gets a clear error rather
# than a silently mangled name, and the render-time sanitizer stays as a
# backstop for any name that reached storage before this existed.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_MAX_NAME_LENGTH = 80


def _validate_demo_name(name: str) -> None:
    if _CONTROL_CHARS_RE.search(name):
        raise DemoActionError(
            "name cannot contain control characters or newlines — a "
            "newline would let the name masquerade as extra lines once "
            "it's rendered into every future chat's system prompt (#191)"
        )
    if len(name) > _MAX_NAME_LENGTH:
        raise DemoActionError(
            f"name is too long ({len(name)} chars, max {_MAX_NAME_LENGTH}) "
            "— it is rendered into every future chat's system prompt (#191)"
        )


class DemoActionError(ValueError):
    """A demo action refused. ``status`` mirrors the HTTP class the REST layer
    should answer with (400 invalid, 404 missing, 409 conflict)."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ── Lookup ───────────────────────────────────────────────────────────────────


def resolve_demo(store, ref: str) -> Demo:
    """A demo by id OR (unique, case-insensitive) name.

    The chat model says "the speaker demo", not a hex id — so every tool-facing
    surface resolves through here. Ambiguity is an error that lists the
    candidates rather than a guess.
    """
    ref = (ref or "").strip()
    if not ref:
        raise DemoActionError("demo id or name is required")
    demo = store.get(ref)
    if demo is not None:
        return demo
    matches = [d for d in store.list() if (d.name or "").lower() == ref.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        ids = ", ".join(f"{d.name} ({d.id})" for d in matches)
        raise DemoActionError(
            f"Demo name {ref!r} is ambiguous — use an id: {ids}")
    raise DemoActionError(f"Demo not found: {ref}", status=404)


def fragments_view(ctx, demo: Demo) -> Dict[str, Any]:
    """``{role: {facets, counts}}`` for the demo's owned config, or {}."""
    from admz.demos import fragments as fr

    out: Dict[str, Any] = {}
    for role, facets in fr.load_all_fragments(ctx.git_repo, demo.id).items():
        out[role] = {"facets": facets, "counts": fr.fragment_entry_count(facets)}
    return out


# ── Metadata CRUD (inert — authenticated principal, no gate) ─────────────────


def create_demo_core(ctx, spec: Dict[str, Any], principal) -> Demo:
    from admz.audit import record_event

    name = (spec.get("name") or "").strip()
    if not name:
        raise DemoActionError("name is required")
    _validate_demo_name(name)
    demo = ctx.demo_store.create(Demo(
        id="", name=name, narrative=spec.get("narrative") or "",
        tag=spec.get("tag") or None, device_ids=spec.get("device_ids") or [],
        roles=spec.get("roles") or {},
        config_source=spec.get("config_source") or "baseline",
        signals=spec.get("signals") or [],
        enabled=bool(spec.get("enabled", True)),
        created_by=str(principal),
    ))
    record_event(principal, "demo.create", resource=f"demo:{demo.id}",
                 details={"name": demo.name,
                          "scope": demo.tag or f"{len(demo.device_ids)} device(s)",
                          "config_source": demo.config_source})
    return demo


def update_demo_core(ctx, demo: Demo, body: Dict[str, Any], principal) -> Demo:
    from admz.audit import record_event

    touched = [f for f in DEMO_FIELDS if f in body]
    if not touched:
        raise DemoActionError(
            f"nothing to update — settable fields: {', '.join(DEMO_FIELDS)}")
    for f in touched:
        setattr(demo, f, body[f])
    if not (demo.name or "").strip():
        raise DemoActionError("name cannot be empty")
    if "name" in touched:
        _validate_demo_name(demo.name)
    ctx.demo_store.update(demo)
    record_event(principal, "demo.update", resource=f"demo:{demo.id}",
                 details={"fields": touched})
    return demo


def delete_demo_core(ctx, demo: Demo, principal) -> None:
    from admz.audit import record_event

    ctx.demo_store.delete(demo.id)
    # The proposal this demo was confirmed from goes back to `proposed` (#201).
    # `demo_proposals.demo_id` is the only persisted back-reference to a demo,
    # and nothing else reconciled it: the row stayed `confirmed`, so
    # `decided_content_keys` skipped that member set on every later inference
    # run and the operator could neither re-propose it nor dismiss it. This is
    # what makes inference/confirm.py's "a wrong confirm is trivially
    # reversible" — the premise for leaving confirm ungated — actually true.
    reopened: List[str] = []
    try:
        reopened = ctx.proposal_store.reopen_for_demo(demo.id)
    except Exception:  # noqa: BLE001 — the demo row is already gone; failing to
        # tidy the proposal must not turn a completed delete into an error
        logger.warning("demo %s: proposal re-open failed", demo.id, exc_info=True)
    try:
        from admz.demos import fragments as fr

        fr.delete_demo_fragments(ctx.git_repo, demo.id, demo.name)
    except Exception:  # noqa: BLE001 — orphan fragments are harmless; history keeps them
        logger.warning("demo %s: fragment cleanup failed", demo.id, exc_info=True)
    record_event(principal, "demo.delete", resource=f"demo:{demo.id}",
                 details={"name": demo.name, "proposals_reopened": reopened})


# ── Fragment capture (drift-affecting — callers gate per ADR-0047) ───────────


async def assign_fragment_core(
    ctx,
    demo: Demo,
    fields: List[Dict[str, str]],
    role: Optional[str],
    mode: str,
    principal,
) -> Dict[str, Any]:
    """Assign drift-diff rows to the demo's fragment (capture).

    Re-checks drift per device so values come from the REAL diff — the captured
    value is the device's actual live value. Also implicitly binds captured
    devices (records the role; pulls them into scope when not tag-scoped).
    Writes only; no device is touched.
    """
    from admz.audit import record_event
    from admz.demos import fragments as fr
    from admz.snapshot.facets import get_facets_for_device

    if not fields:
        raise DemoActionError("no fields selected")
    if mode not in fr.MODES:
        raise DemoActionError(f"mode must be one of {fr.MODES}")

    selected: Dict[str, set] = {}
    for f in fields:
        if not (f.get("device_id") and f.get("path")):
            raise DemoActionError(
                "each field needs device_id, facet, and path")
        selected.setdefault(f["device_id"], set()).add(
            (f.get("facet") or "", f["path"]))

    added: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    warnings: List[str] = []
    entries_by_role: Dict[str, List[Dict[str, str]]] = {}
    roles_learned: Dict[str, str] = {}

    for did, chosen in selected.items():
        if not ctx.registry.device_exists(did):
            skipped.append({"device_id": did, "facet": "", "path": "",
                            "reason": "device not found"})
            continue
        device_info = ctx.registry.get_device_info(did)
        device_info["device_id"] = did
        facets_by_name = {f.name: f for f in get_facets_for_device(device_info)}
        dev_role = fr.normalize_role(role or (demo.roles or {}).get(did))

        report = await ctx.drift_detector.check_drift(did)
        by_key = {(f.facet, f.path): f for f in report.fields}
        for facet_name, path in sorted(chosen):
            field = by_key.get((facet_name, path))
            if field is None:
                skipped.append({"device_id": did, "facet": facet_name,
                                "path": path, "reason": "not-drifted"})
                continue
            ok, reason, warns = fr.validate_assignment(
                field, facets_by_name.get(facet_name), mode, device_info)
            warnings.extend(warns)
            if not ok:
                skipped.append({"device_id": did, "facet": facet_name,
                                "path": path, "reason": reason})
                continue
            entries_by_role.setdefault(dev_role, []).append(
                {"facet": facet_name, "path": path, "value": field.actual})
            added.append({"device_id": did, "role": dev_role,
                          "facet": facet_name, "path": path,
                          "value": field.actual,
                          "canonical_key": field.canonical_key})
            roles_learned[did] = dev_role

    commit_sha = None
    for dev_role, entries in entries_by_role.items():
        sha = fr.add_entries(ctx.git_repo, demo, dev_role, entries, mode=mode)
        commit_sha = sha or commit_sha

    # Capturing from a device implicitly binds it: record the role, and put the
    # device in scope when the demo isn't tag-scoped.
    if roles_learned:
        demo.roles = {**(demo.roles or {}), **roles_learned}
        if not demo.tag:
            missing = [d for d in roles_learned if d not in (demo.device_ids or [])]
            demo.device_ids = list(demo.device_ids or []) + missing
        ctx.demo_store.update(demo)

    record_event(principal, "demo.fragment_assign", resource=f"demo:{demo.id}",
                 details={"added": len(added), "skipped": len(skipped),
                          "mode": mode, "commit": commit_sha})
    return {"success": True, "added": added, "skipped": skipped,
            "warnings": warnings, "commit_sha": commit_sha,
            "fragments": fragments_view(ctx, demo)}


# ── Activation state (adopt is drift-affecting — callers gate) ───────────────


def adopt_demo_core(ctx, demo: Demo, principal) -> Dict[str, Any]:
    """Mark a demo ACTIVE without pushing anything (its owned keys join each
    device's expected state on the next drift check). Guards — re-run at
    APPLY time when reached via the confirm widget, since the world may have
    changed since approval:
      * devices held by a legacy ADR-0044 scenario → 409
      * same-key overlap with another active demo → 409
    """
    from admz.audit import record_event
    from admz.demos import fragments as fr

    if demo.active:
        return {"success": True, "demo": demo.to_dict(),
                "message": "Already active."}

    devices = service.resolve_devices(demo, ctx.registry)
    held = sorted({
        f"{d.get('device_id')} (scenario '{d.get('active_scenario')}')"
        for d in devices if d.get("active_scenario")
    })
    if held:
        raise DemoActionError(
            "Held by a legacy scenario — end it before adopting: "
            + ", ".join(held), status=409)

    others = [d for d in ctx.demo_store.list() if d.active and d.id != demo.id]
    conflicts = fr.overlap_conflicts(ctx.git_repo, demo, others, ctx.registry)
    if conflicts:
        lines = sorted({
            f"{c['facet']}/{c['path']} on {c['device_id']} "
            f"(claimed by '{c['other_demo']}')" for c in conflicts})
        raise DemoActionError(
            "Key conflict with another active demo: " + "; ".join(lines),
            status=409)

    demo.active = True
    ctx.demo_store.update(demo)
    record_event(principal, "demo.adopt", resource=f"demo:{demo.id}",
                 details={"name": demo.name,
                          "devices": [d.get("device_id") for d in devices]})
    return {"success": True, "demo": demo.to_dict(),
            "message": ("Marked active. The next drift check attributes its "
                        "keys — nothing was pushed.")}


def deactivate_demo_core(ctx, demo: Demo, principal) -> Dict[str, Any]:
    """Stop claiming the demo's keys (no push; only reveals drift again)."""
    from admz.audit import record_event

    if demo.active:
        demo.active = False
        ctx.demo_store.update(demo)
    record_event(principal, "demo.deactivate", resource=f"demo:{demo.id}",
                 details={"name": demo.name})
    return {"success": True, "demo": demo.to_dict(),
            "message": ("Deactivated. Its keys return to unclaimed drift on "
                        "the next check; revert them to restore the base "
                        "values.")}


# ── Rule ↔ demo correlation (ADR-0050 Phase B) ───────────────────────────────


def attach_rule_to_demo(ctx, demo: Demo, rule: Dict[str, Any]) -> None:
    """Record a created rule's membership on a demo, and auto-attach its condition
    topic as a demo signal (the device publishes that topic independently of the
    rule — it IS the correlated watched event). Implicitly binds the device.

    Called best-effort from the rule executor: a bookkeeping failure must NEVER
    falsify the rule creation itself.

    ``source`` (#124 slice 3) records where the rule lives: ``"device"`` (an
    ADMZ-created device rule, the default and everything before this) or
    ``"acs"`` (an ACS action rule an inferred demo links to). It is a JSON field
    inside the existing ``rules_json`` — ``_row_to_demo`` tolerates missing keys,
    so this is **not** a schema migration. ``wizard._rules_status`` needs it:
    an ACS rule has no ADMZ device to look for the rule id on, and without the
    field it would read ``observed: false`` forever — a permanent, false "your
    rule vanished".
    """
    import time
    from types import SimpleNamespace

    from admz.audit import record_event

    did = rule.get("device_id") or ""
    rid = str(rule.get("rule_id") or "")
    if not (did and rid):
        return
    entry = {
        "device_id": did, "rule_id": rid, "rule_name": rule.get("rule_name"),
        "condition_id": rule.get("condition_id"),
        "condition_topic": rule.get("condition_topic"),
        "source": rule.get("source") or "device", "created_at": time.time(),
    }
    # membership deduped on (device_id, rule_id)
    demo.rules = [r for r in (demo.rules or [])
                  if not (r.get("device_id") == did and str(r.get("rule_id")) == rid)]
    demo.rules.append(entry)

    # auto-signal from the condition topic, deduped on (topic, device_id)
    topic = entry.get("condition_topic")
    if topic:
        sigs = list(demo.signals or [])
        if not any(s.get("topic") == topic and s.get("device_id") == did for s in sigs):
            sigs.append({"label": entry.get("rule_name") or "rule",
                         "topic": topic, "device_id": did})
            demo.signals = sigs

    # implicit device bind (device-scoped demos): pull the device into scope
    if not demo.tag and did not in (demo.device_ids or []):
        demo.device_ids = list(demo.device_ids or []) + [did]

    ctx.demo_store.update(demo)
    try:
        record_event(SimpleNamespace(name=f"demo:{demo.name}", source="rule-attach"),
                     "demo.rule_attach", resource=f"demo:{demo.id}",
                     details={"rule_id": rid, "device_id": did, "topic": topic})
    except Exception:  # noqa: BLE001 — audit best-effort
        logger.debug("rule_attach audit failed", exc_info=True)


def detach_rule_from_demo(ctx, rule_id: str, device_id: str) -> None:
    """Reverse-scan on rule delete: drop the membership entry (and its auto-signal
    when no remaining rule shares that topic on the device) from whichever demo
    owns it. Best-effort."""
    from types import SimpleNamespace

    from admz.audit import record_event

    rid = str(rule_id or "")
    for demo in ctx.demo_store.list():
        match = next((r for r in (demo.rules or [])
                      if str(r.get("rule_id")) == rid and r.get("device_id") == device_id),
                     None)
        if match is None:
            continue
        demo.rules = [r for r in demo.rules if r is not match]
        topic = match.get("condition_topic")
        if topic and not any(
                r.get("condition_topic") == topic and r.get("device_id") == device_id
                for r in demo.rules):
            demo.signals = [s for s in (demo.signals or [])
                            if not (s.get("topic") == topic and s.get("device_id") == device_id)]
        ctx.demo_store.update(demo)
        try:
            record_event(SimpleNamespace(name=f"demo:{demo.name}", source="rule-detach"),
                         "demo.rule_detach", resource=f"demo:{demo.id}",
                         details={"rule_id": rid, "device_id": device_id})
        except Exception:  # noqa: BLE001
            logger.debug("rule_detach audit failed", exc_info=True)
        return


# ── Prepare / End (device-touching — the scenario cores gate the push) ───────


async def prepare_demo_core(ctx, demo: Demo, principal) -> Dict[str, Any]:
    """Load a demo in one gated plan. Three-way: a legacy ADR-0044 *scenario*
    demo pushes its saved config; a fragment demo (ADR-0047) pushes its owned
    keys via the fragment core; a demo that owns nothing yet is steered to
    capture."""
    from admz.demos import activation as act
    from admz.demos import readiness as rd
    from admz.snapshot.scenarios import activate_scenario_core

    name = rd.scenario_of(demo.config_source)
    if name:
        targets = service.resolve_devices(demo, ctx.registry)
        if not targets:
            raise DemoActionError("This demo has no devices.")
        held = [
            d.get("device_id") for d in targets
            if d.get("active_scenario") and d.get("active_scenario") != name
        ]
        if held:
            holders = sorted({
                d.get("active_scenario") for d in targets
                if d.get("active_scenario") and d.get("active_scenario") != name})
            raise DemoActionError(
                f"{', '.join(held)} currently held by another scenario "
                f"({', '.join(holders)}). End that demo first.", status=409)
        try:
            result = await activate_scenario_core(
                ctx, name, targets, principal,
                description=f"Prepare demo '{demo.name}' (scenario '{name}')")
        except ValueError as e:
            raise DemoActionError(str(e))
        result["demo_id"] = demo.id
        return result

    # Fragment demo (ADR-0047 slice 3): push its owned set-keys.
    if act.demo_has_fragments(ctx, demo):
        return await act.prepare_fragment_demo_core(ctx, demo, principal)

    raise DemoActionError(
        "This demo owns no config to load yet. Capture some first — run "
        "check_drift on its devices, then assign_demo_fragment — or it runs on "
        "the baseline (its devices are ready when they're in sync and online).")


async def end_demo_core(ctx, demo: Demo, principal) -> Dict[str, Any]:
    """End a demo (gated plan). Mirror of prepare: scenario demos snap back to
    baseline; fragment demos push base values back for their owned keys and
    deactivate; a demo that owns nothing is steered off."""
    from admz.demos import activation as act
    from admz.demos import readiness as rd
    from admz.snapshot.scenarios import return_to_baseline_core

    if rd.scenario_of(demo.config_source):
        targets = service.resolve_devices(demo, ctx.registry)
        if not targets:
            raise DemoActionError("This demo has no devices.")
        try:
            result = await return_to_baseline_core(
                ctx, targets, principal,
                description=f"End demo '{demo.name}' — return to baseline")
        except ValueError as e:
            raise DemoActionError(str(e))
        result["demo_id"] = demo.id
        return result

    if act.demo_has_fragments(ctx, demo):
        return await act.end_fragment_demo_core(ctx, demo, principal)

    raise DemoActionError(
        "This demo owns no config — there's nothing to end. Its devices were "
        "never taken out of their normal state.")
