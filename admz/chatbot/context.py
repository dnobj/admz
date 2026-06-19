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
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Bound the roster so a huge fleet can't balloon the per-turn token cost.
_MAX_ROSTER_DEVICES = 60


def _resolve_registry() -> Optional[Any]:
    """The live registry singleton (set at app startup). Lazy-imported to
    avoid an import cycle (admz.api imports admz.chatbot)."""
    try:
        from admz.api.main import registry  # noqa: WPS433 (lazy on purpose)

        return registry
    except Exception:  # noqa: BLE001 - never let context-building break chat
        return None


def build_module_prompt_sections(ctx: Any = None) -> str:
    """Join every platform module's system-prompt fragment (ADR-0038).

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
    """device_id -> cached health status string (online/unreachable/…)."""
    out: dict = {}
    try:
        from admz.fleet.health import device_health_store

        for rec in device_health_store.list_all():
            try:
                out[rec.device_id] = rec.status.value
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    return out


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
        model = d.get("model") or "?"
        parts: List[str] = [f"{model} ({did})"]

        # A real operator-set nickname is worth showing; the stock
        # "AXIS <model>" friendly_name is not (it just repeats the model,
        # so skip any friendly_name that merely contains the model string).
        nick = (d.get("nickname") or "").strip()
        fn = (d.get("friendly_name") or "").strip()
        if not nick and fn and model != "?" and model.lower() not in fn.lower():
            nick = fn
        if nick:
            parts.append(f'"{nick}"')

        if d.get("host"):
            parts.append(str(d["host"]))
        parts.append(health.get(did, "unknown"))
        if d.get("firmware_version"):
            parts.append(f"fw {d['firmware_version']}")
        drift = _drift_label(d)
        if drift:
            parts.append(drift)
        tags = d.get("tags") or []
        if tags:
            parts.append("tags: " + ", ".join(str(t) for t in tags))

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
