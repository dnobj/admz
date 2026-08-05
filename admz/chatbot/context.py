"""Preloaded conversational context for the ADMZ chatbot.

Builds a compact, always-current **fleet roster** (and, later, a
catalog-sourced common-operations reference) that the system-prompt builder
injects so the model can resolve a device and pick an operation without
spending a Gemini tool round-trip on inventory/discovery.

Everything here is a *pure local read* — the device registry plus the
**cached** health and drift tables — so it adds no device network calls and
costs ~no latency. Every step degrades to an empty string on any failure, so
a registry/health hiccup can never break a chat turn (the model simply falls
back to calling the tools, as before).
"""

from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

from admz.validators import sanitize_display_text

logger = logging.getLogger(__name__)

# Bound the roster so a huge fleet can't balloon the per-turn token cost.
_MAX_ROSTER_DEVICES = 60

#: Cap on free-text device/demo fields rendered into the roster or the demos
#: section (#167, #191) — long enough for a real label, short enough that a
#: value can't paint several lines' worth of fake prompt structure. Applied
#: on top of admz.validators.sanitize_display_text's control-char stripping,
#: which is what actually closes the "\n breaks out of its line" exploit;
#: the length cap is defense-in-depth against a value that stays on one
#: line but is otherwise enormous.
_MAX_FIELD_LEN = 80

#: Hostnames/IPs are legitimately longer than a label but still bounded —
#: the DNS ceiling, well above any real IP or hostname.
_MAX_HOST_LEN = 253


def _resolve_registry() -> Optional[Any]:
    """The live registry singleton (set at app startup). Lazy-imported to
    avoid an import cycle (admz.api imports admz.chatbot)."""
    try:
        from admz.api.main import registry  # noqa: WPS433 (lazy on purpose)

        return registry
    except Exception:  # noqa: BLE001 - never let context-building break chat
        return None


def build_module_prompt_sections(ctx: Any = None) -> str:
    """Join every platform module's system-prompt fragment (ADR-0039).

    Empty in the device-only deployment (the devices module contributes no
    section), so the assembled prompt is unchanged. A module like ACS Pro (PR2)
    returns its correlation guidance here. Degrades to "" on any failure so it
    can never break a chat turn.
    """
    try:
        from admz.api.context import get_context

        reg = get_context().module_registry
    except Exception:  # noqa: BLE001
        try:
            from admz.modules.registry import ModuleRegistry

            reg = ModuleRegistry().discover()
        except Exception:  # noqa: BLE001
            return ""
    try:
        return "\n\n".join(reg.prompt_sections_all(ctx))
    except Exception:  # noqa: BLE001
        return ""


def _health_by_id() -> dict:
    """device_id -> cached health record (status, SD-card presence, …)."""
    out: dict = {}
    try:
        from admz.fleet.health import device_health_store

        for rec in device_health_store.list_all():
            try:
                out[rec.device_id] = rec
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    return out


def _sd_label(rec: Any) -> str:
    """SD-card presence as a short roster tag, or "" when unknown.

    Health-cadence data from disks-list.cgi — the status attr is the
    authoritative inserted/not signal (slot config params are not)."""
    status = getattr(rec, "sd_status", None)
    if not status:
        return ""
    if status == "no_slot":
        return "sd: no slot"
    if status == "disconnected":
        return "sd: none"
    total_kb = getattr(rec, "sd_total_kb", None)
    size = f" {total_kb / 1048576:.0f}GB" if total_kb else ""
    if status == "OK":
        return f"sd: inserted{size} OK"
    return f"sd: inserted{size} ({status})"


def _drift_label(device: dict) -> str:
    """Cache-only drift state for a device, as a short tag (or "")."""
    try:
        from admz.snapshot.drift_alerts import drift_alerts as _store
        from admz.snapshot.drift_status import (
            DRIFTED,
            IN_SYNC,
            NONE,
            UNCHECKED,
            drift_status_for,
        )

        sig = _store.get_last_signature(device.get("device_id", ""))
        st = drift_status_for(device, sig)
        state = st.get("state")
        if state == DRIFTED:
            return f"drifted({st.get('count')})"
        if state == IN_SYNC:
            return "in-sync"
        if state == UNCHECKED:
            return "baseline-unchecked"
        if state == NONE:
            return "no-baseline"
    except Exception:  # noqa: BLE001
        pass
    return ""


def build_device_roster(registry: Optional[Any] = None) -> str:
    """A compact one-line-per-device roster for the system prompt, or "".

    Each line: ``MODEL (DEVICE_ID) · IP · health · fw X · drift · tags: …`` —
    enough for the model to resolve "my C1710 / the lab speaker / 192.168.1.x"
    to a ``device_id`` and answer inventory questions with no tool call.
    """
    try:
        registry = registry or _resolve_registry()
        if registry is None:
            return ""
        devices = registry.list_devices()
    except Exception:  # noqa: BLE001
        logger.debug("[chat] device roster unavailable", exc_info=True)
        return ""
    if not devices:
        return ""

    health = _health_by_id()
    devices.sort(key=lambda d: ((d.get("model") or "").lower(), d.get("device_id") or ""))

    lines: List[str] = []
    for d in devices[:_MAX_ROSTER_DEVICES]:
        did = d.get("device_id") or "?"
        # model, like nickname/friendly_name below, is copied straight from
        # the device's own probe response during auto-registration
        # (admz/mcp/server.py's provision_device path: "model": (probe.
        # device_info or {}).get("model", "")) — same exploit surface as
        # nickname, so it gets the same sanitizer.
        model = sanitize_display_text(d.get("model") or "?", max_length=_MAX_FIELD_LEN)
        parts: List[str] = [f"{model} ({did})"]

        # A real operator-set nickname is worth showing; the stock
        # "AXIS <model>" friendly_name is not (it just repeats the model,
        # so skip any friendly_name that merely contains the model string).
        # Both fields are device- or model-supplied and reach here unvetted
        # (#167: nickname is writable via the ungated update_device MCP tool,
        # and friendly_name is copied from the device's own probe response
        # during auto-registration) — sanitize before they're rendered into
        # the roster line.
        nick = sanitize_display_text(d.get("nickname"), max_length=_MAX_FIELD_LEN)
        fn = sanitize_display_text(d.get("friendly_name"), max_length=_MAX_FIELD_LEN)
        if not nick and fn and model != "?" and model.lower() not in fn.lower():
            nick = fn
        if nick:
            parts.append(f'"{nick}"')

        if d.get("host"):
            parts.append(sanitize_display_text(d["host"], max_length=_MAX_HOST_LEN))
        rec = health.get(did)
        try:
            parts.append(rec.status.value if rec is not None else "unknown")
        except Exception:  # noqa: BLE001
            parts.append("unknown")
        if d.get("firmware_version"):
            # Also device-probe-supplied (basicdeviceinfo.cgi), same reasoning.
            fw = sanitize_display_text(d["firmware_version"], max_length=_MAX_FIELD_LEN)
            parts.append(f"fw {fw}")
        if rec is not None:
            sd = _sd_label(rec)
            if sd:
                parts.append(sd)
        drift = _drift_label(d)
        if drift:
            parts.append(drift)
        tags = d.get("tags") or []
        if tags:
            clean_tags = [
                sanitize_display_text(t, max_length=_MAX_FIELD_LEN) for t in tags
            ]
            parts.append("tags: " + ", ".join(clean_tags))

        lines.append("- " + " · ".join(parts))

    if len(devices) > _MAX_ROSTER_DEVICES:
        lines.append(f"- …and {len(devices) - _MAX_ROSTER_DEVICES} more (call list_devices)")

    return "\n".join(lines)


# Fixed set of the most common operator intents → a short label, resolved
# through the live catalog (so the operation_id is real, never hand-typed)
# against a representative fleet device.
#
# Deliberately limited to UNIVERSAL, NO-PARAM operations that the resolver
# returns unambiguously: these can safely skip the query_catalog discovery
# call (there are no parameter ranges to verify). Parameter reads/writes
# (volume, image, …) are intentionally NOT here — they resolve less reliably
# and the model must call query_catalog for the exact param/range regardless
# (the prompt's param rules + the param.cgi:list group= rule cover those).
_COMMON_INTENTS = (
    ("reboot the device", "Reboot / restart the device"),
    ("factory reset the device to defaults", "Factory reset (dangerous, gated)"),
    ("get device information model firmware serial number", "Device info / firmware / serial"),
    ("list installed acap applications", "List installed ACAP apps + run state"),
)

# Cache the rendered block keyed on the fleet's set of models — rebuilt only
# when a model is added/removed, so it costs nothing on a normal turn.
_common_ops_cache: dict = {}

#: Bound the demos section the same way the roster is bounded (#191 — this
#: loop had no cap at all while both its siblings, _MAX_ROSTER_DEVICES and
#: _MAX_INFERENCE_PROPOSALS below, do; the absence was an inconsistency,
#: not house style, and an unbounded per-turn token amplifier besides).
_MAX_DEMOS_SECTION = 60


def build_demos_section() -> str:
    """A compact one-line-per-demo readiness list for the system prompt, or "".

    Lets the model answer "is the <X> demo ready?" / "what demos exist?" with
    no tool call. Entirely cache-backed: readiness comes from the drift/health
    caches; ``event_store=None`` skips the per-signal event queries (the model
    calls ``get_demo`` when it needs signal last-seen). Same degrade-to-""
    contract as the device roster.
    """
    try:
        from admz.api.context import get_context
        from admz.demos import service as demo_service

        ctx = get_context()
        views = demo_service.demo_views(
            ctx.demo_store.list(), ctx.registry, None)
    except Exception:  # noqa: BLE001 - never let context-building break chat
        logger.debug("[chat] demos section unavailable", exc_info=True)
        return ""
    if not views:
        return ""

    lines: List[str] = []
    # Demo names are free text the model itself can write, ungated, via
    # create_demo / confirm_demo_proposal (#191) — sanitize the same way
    # the roster's device-supplied fields are (#167).
    for v in views[:_MAX_DEMOS_SECTION]:
        r = v.get("readiness") or {}
        name = sanitize_display_text(v.get("name"), max_length=_MAX_FIELD_LEN)
        parts = [f"{name} — {r.get('state', '?')}"]
        n = len(r.get("devices") or [])
        parts.append(f"{n} device{'s' if n != 1 else ''}")
        if v.get("active"):
            parts.append("ACTIVE")
        if v.get("scenario_name"):
            scenario = sanitize_display_text(v["scenario_name"], max_length=_MAX_FIELD_LEN)
            parts.append(f"scenario:{scenario}")
        blockers = r.get("blockers") or []
        if blockers:
            parts.append("blockers: " + "; ".join(str(b) for b in blockers[:3])
                         + ("; …" if len(blockers) > 3 else ""))
        lines.append(" · ".join(parts))
    if len(views) > _MAX_DEMOS_SECTION:
        lines.append(f"…and {len(views) - _MAX_DEMOS_SECTION} more (call list_demos)")
    return "\n".join(lines)


#: Bound the proposal list the same way the roster is bounded — a noisy site
#: must not balloon the per-turn token cost. Unlike the demos section before
#: #191, this already bounds what's RENDERED, not just what's queried (#320
#: checked): the query at :func:`build_inference_section` fetches
#: ``_MAX_INFERENCE_PROPOSALS + 1`` rows (one extra, to detect "more" without
#: a second count query), and the render loop re-slices to exactly
#: ``rows[:_MAX_INFERENCE_PROPOSALS]`` before iterating — so no second cap
#: is needed here.
_MAX_INFERENCE_PROPOSALS = 8


def _age(started_at: float) -> str:
    """"12m ago" / "3h ago" / "2d ago", or "" when the timestamp is unusable."""
    try:
        secs = time.time() - float(started_at or 0)
    except (TypeError, ValueError):
        return ""
    if started_at and secs >= 0:
        if secs < 3600:
            return f"{int(secs // 60)}m ago"
        if secs < 86400:
            return f"{int(secs // 3600)}h ago"
        return f"{int(secs // 86400)}d ago"
    return ""


def build_inference_section() -> str:
    """Live demo-inference state for the system prompt, or "" (ADR-0051).

    The narration guidance rides on this block, so returning "" switches the
    whole section off. It is off unless inference can do real work here:

    * **ACS Pro is connected** — its action rules are the strongest evidence
      class, and an experience centre with ACS is the flagship case; or
    * **a run or an open proposal already exists** — the operator has used the
      feature and may be coming back to finish reviewing it.

    On a device-only deployment that has never run inference, this returns ""
    and the prompt is byte-identical to before the slot existed — the same
    conditional contract the ACS Pro module's own section keeps (ADR-0039).

    Reads two small SQLite tables; degrades to "" on any failure, so a store
    hiccup can never break a chat turn.
    """
    try:
        from admz.api.context import get_context
        from admz.demos.inference.proposals import STATUS_PROPOSED

        ctx = get_context()
        rows = ctx.proposal_store.list(status=STATUS_PROPOSED,
                                       limit=_MAX_INFERENCE_PROPOSALS + 1)
        latest = ctx.inference_run_store.latest()
    except Exception:  # noqa: BLE001 - never let context-building break chat
        logger.debug("[chat] inference section unavailable", exc_info=True)
        return ""

    try:
        from admz.modules.acs_pro.config import acs_enabled

        acs = bool(acs_enabled())
    except Exception:  # noqa: BLE001
        acs = False

    if not (acs or rows or latest is not None):
        return ""

    lines: List[str] = [
        "ACS Pro is connected — its action rules are readable as evidence."
        if acs else
        "ACS Pro is NOT connected, so no ACS action rule is readable: inference "
        "runs on device rules, tags and installed apps alone, and every "
        "proposal carries `acs_absent`."
    ]

    if latest is None:
        lines.append("No inference run has happened yet — offer `infer_demos`.")
    else:
        age = _age(latest.started_at)
        lines.append(
            f"Last run `{latest.id}` ({latest.mode}, {latest.status}"
            + (f", {age}" if age else "") + f"): {latest.device_count} device(s), "
            f"{latest.rule_count} rule(s), {latest.edge_count} edge(s)."
            + (f" {latest.error}" if latest.error else ""))

    if not rows:
        lines.append("No proposal is open — either none was produced, or every "
                     "one has been confirmed or dismissed.")
    else:
        shown = rows[:_MAX_INFERENCE_PROPOSALS]
        more = len(rows) > len(shown)
        lines.append(
            f"{len(shown)}{'+' if more else ''} proposal(s) awaiting a decision. "
            "Read them with `list_demo_proposals` — do NOT re-run inference to "
            "see them. Each name below is the DETERMINISTIC placeholder, not a "
            "good name:")
        for p in shown:
            # p.name derives from device tags and rule names — partially
            # device/operator-influenceable, the same class of field as the
            # roster's nickname and the demos section's name (#320). Less
            # direct than either (an attacker shapes it via tags/rule names,
            # not by setting it outright), but the render is identical.
            name = sanitize_display_text(p.name, max_length=_MAX_FIELD_LEN)
            parts = [f"{name} ({p.id}) — {p.confidence}",
                     f"{len(p.device_ids)} device(s)"]
            if p.flags:
                parts.append("flags: " + ", ".join(str(f) for f in p.flags[:4]))
            lines.append("- " + " · ".join(parts))
        if more:
            lines.append("- …and more (call `list_demo_proposals`)")

    return "\n".join(lines)


#: Per-capability narration notes — what an ACTIVE capability changes about
#: how the model should *talk*, not about what ADMZ does.
#:
#: Only the capabilities whose activity would otherwise make the model say
#: something false get an entry; every other active capability falls back to
#: its registry ``description``, which is already one operator-readable
#: sentence. Keeping these here rather than in ``capabilities.py`` keeps the
#: registry a declaration of *what is on* and this a statement of *what to say
#: about it* — and keeps chat-prompt wording out of a module the MCP
#: subprocess imports.
_NARRATION_NOTES = {
    "dev.test_auth": (
        "the caller may be a SCRIPT, not the person you are addressing: an "
        "unauthenticated request resolves to a fixed synthetic principal. Do "
        "not describe a pending action as \"waiting for your approval\" or "
        "\"waiting for you to click\" — say the gate is open and who or what "
        "may satisfy it, because an unattended agent may be approving it. The "
        "synthetic principal has no group membership by default, so "
        "reveal-gated surfaces (plaintext credentials, the advanced page's "
        "toggles) refuse it; report that refusal as authorization working, "
        "not as a bug."
    ),
    "dev.auto_approve": (
        "an unattended approver may complete `url_*` confirmation gates "
        "without a human. The gate still fires and still has to be satisfied "
        "— what changed is WHO may satisfy it. Never tell the operator an "
        "approval is waiting on them as though nothing else could complete "
        "it; say the card is open and that the dev approver may take it."
    ),
    "test.no_onboarding_probes": (
        "adding a device never probes it, so every add comes back "
        "`credentials_needed`. Say that is the suppressor, not a device fault "
        "— do not send the operator hunting for a network problem."
    ),
    "test.no_github_push": (
        "config-repo pushes never reach GitHub. Snapshots still commit "
        "locally; do not report a backup as offsite."
    ),
}


def build_capabilities_section() -> str:
    """Active non-production-appropriate advanced capabilities, or "" (#132).

    Off — and therefore absent from the prompt entirely — unless a capability
    whose ``production_appropriate`` is False is actually active. An ordinary
    installation sees **no prompt change at all**, the same conditional
    contract :func:`build_inference_section` and the ACS Pro module section
    keep (ADR-0039/0051), and a test pins the rendered prompt byte-identical
    in that case.

    ``privileged`` and ``internal`` capabilities are deliberately not in scope:
    survey mode and event ingest are legitimate deployment profiles, and a
    subprocess role marker is noise. Narrating them every turn on a normal
    privileged install is exactly the alarm fatigue the registry's chip rules
    avoid — the model can still read the whole table with
    `get_advanced_capabilities` when a question actually turns on it.

    Pure registry read (env + one settings lookup); degrades to "" on any
    failure, so a settings hiccup can never break a chat turn.
    """
    try:
        from admz import capabilities

        loud = [
            a for a in capabilities.active_capabilities()
            if not a.capability.production_appropriate
        ]
    except Exception:  # noqa: BLE001 - never let context-building break chat
        logger.debug("[chat] capabilities section unavailable", exc_info=True)
        return ""

    if not loud:
        return ""

    lines: List[str] = []
    for a in loud:
        cap = a.capability
        knob = cap.env_var if a.source == "env" else cap.setting_key
        lines.append(
            f"- `{cap.id}` [{cap.danger}] — ON via {a.source} ({knob}). "
            f"{cap.description}"
        )
        note = _NARRATION_NOTES.get(cap.id)
        if note:
            lines.append(f"  What this changes for you: {note}")
    return "\n".join(lines)


def _resolve_top_op(resolver: Any, device_id: str, device_info: dict, intent: str) -> str:
    """The top catalog operation_id for an intent, or "" (never raises)."""
    try:
        res = resolver.resolve(
            device_id=device_id,
            intent=intent,
            family="vapix",
            device_info=device_info,
        )
        ops = getattr(res, "operations", None) or []
        if ops and isinstance(ops[0], dict):
            return ops[0].get("id") or ops[0].get("operation_id") or ""
    except Exception:  # noqa: BLE001
        pass
    return ""


def build_common_ops_reference(resolver: Any = None, registry: Optional[Any] = None) -> str:
    """Catalog-sourced "common operations" reference for the system prompt, or "".

    Resolves :data:`_COMMON_INTENTS` through the live catalog resolver to real
    ``operation_id``s, deduped, and caches per fleet-model-set. Degrades to ""
    on any failure (prompt unchanged; model falls back to query_catalog).
    """
    try:
        if resolver is None or registry is None:
            from admz.api.context import _ctx  # lazy: avoid an import cycle

            if _ctx is None:
                return ""
            resolver = resolver or _ctx.resolver
            registry = registry or _ctx.registry
        devices = registry.list_devices()
    except Exception:  # noqa: BLE001
        logger.debug("[chat] common-ops reference unavailable", exc_info=True)
        return ""
    if not devices:
        return ""

    models = tuple(sorted({(d.get("model") or "") for d in devices}))
    cached = _common_ops_cache.get(models)
    if cached is not None:
        return cached

    rep = devices[0]
    rep_id = rep.get("device_id") or ""
    seen: set = set()
    lines: List[str] = []
    for intent, label in _COMMON_INTENTS:
        op_id = _resolve_top_op(resolver, rep_id, rep, intent)
        if op_id and op_id not in seen:
            seen.add(op_id)
            lines.append(f"- {label}: `{op_id}`")

    out = "\n".join(lines)
    _common_ops_cache[models] = out
    return out
