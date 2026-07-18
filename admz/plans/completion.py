"""Declarative plan-completion dispatch (ADR-0048 wizard foundation).

A plan may carry an ``on_complete`` payload ``{"handler": name, ...args}``. At
the tail of :meth:`PlanEngine.run_plan` — once the plan has reached COMPLETED or
FAILED — :func:`run_completion` looks the handler up and runs it. ``run_plan`` is
the single choke point for all four execution paths, and a *JSON* payload (not a
Python callback) so the hook survives the MCP-subprocess → web-process round-trip
through ``plan_summary_json``.

Contract: **``run_completion`` NEVER raises.** An unknown handler, an
unimportable module, or a handler exception is caught, logged, and recorded as
the plan's ``completion_note`` — a piece of bookkeeping that rode on a plan must
never fail the plan itself. Handlers run on BOTH COMPLETED and FAILED; each
decides its own partial-failure semantics from ``plan.status`` / ``plan.results``.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# handler name -> (module path, function name) lazily imported to avoid cycles
# (the demo/scenario handlers reach into plan/demo/snapshot internals), OR a
# direct callable. An entry may point at a function that doesn't exist yet —
# run_completion degrades to a note — so the foundation lands before its
# handlers (Phase A).
_REGISTRY: Dict[str, Any] = {
    "demo_activation": ("admz.demos.activation", "on_activation_complete"),
    "demo_deactivation": ("admz.demos.activation", "on_deactivation_complete"),
    "scenario_markers": ("admz.snapshot.scenarios", "on_markers_complete"),
}


def register_handler(name: str, module_path: str, fn_name: str) -> None:
    """Register or override a lazily-imported completion handler."""
    _REGISTRY[name] = (module_path, fn_name)


def register_callable(name: str, fn: Callable[..., Any]) -> None:
    """Register a completion handler as a direct callable (used by tests)."""
    _REGISTRY[name] = fn


def _resolve(name: str) -> Optional[Callable[..., Any]]:
    entry = _REGISTRY.get(name)
    if entry is None:
        return None
    if callable(entry):
        return entry
    module_path, fn_name = entry
    mod = importlib.import_module(module_path)  # may raise ImportError → caught
    return getattr(mod, fn_name)  # may raise AttributeError → caught


def run_completion(plan: Any, registry: Any = None) -> None:
    """Dispatch ``plan.on_complete``. NEVER raises.

    Calls ``handler(plan, args, registry=registry)`` where ``args`` is the
    ``on_complete`` payload minus its ``handler`` key. Any failure is written to
    ``plan.completion_note`` and swallowed.
    """
    spec = getattr(plan, "on_complete", None)
    if not spec or not isinstance(spec, dict):
        return
    name = spec.get("handler")
    if not name:
        return
    args = {k: v for k, v in spec.items() if k != "handler"}
    try:
        fn = _resolve(name)
        if fn is None:
            plan.completion_note = f"completion handler '{name}' is not registered"
            logger.warning("plan %s: %s", getattr(plan, "plan_id", "?"), plan.completion_note)
            return
        fn(plan, args, registry=registry)
    except Exception as exc:  # noqa: BLE001 — a completion hook must never fail its plan
        plan.completion_note = f"completion handler '{name}' failed: {exc}"
        logger.warning(
            "plan %s completion handler '%s' failed",
            getattr(plan, "plan_id", "?"), name, exc_info=True,
        )
