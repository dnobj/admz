"""Consume the axis-api-atlas rule-builder pillar.

ADMZ selects a ``(condition, action, param_choices)`` triple; the atlas
(``Atlas.build_rule`` / ``event_conditions`` / ``event_actions``) renders the
SOAP and owns all device quirks. This module is the thin ADMZ-side wrapper: it
lists what a model can do (for the model to ground its choices), detects which
action params are recipient **secrets** (routed to the credential-capture
widget, never chat), and turns a build result into one human sentence for the
approval card.

A model with no survey yields ``available: False`` with a plain reason — the
honest "not surveyed yet" signal, surfaced to the user rather than guessed
around. See ADR-0043.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional

# Param-name hints. ``password``-family values must never reach chat/logs;
# ``login``-family values are usernames but are collected together with the
# password via the widget so the whole recipient credential is entered at once.
_SECRET_HINTS = ("password", "passwd")
_LOGIN_HINTS = ("login",)


@lru_cache(maxsize=1)
def _atlas() -> Any:
    from axis_api_atlas import Atlas
    return Atlas()


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------

def is_surveyed(model: str) -> bool:
    """True if the model has an events/rules survey (rules are buildable)."""
    return bool(model) and _atlas().events_survey(model) is not None


def _condition_dict(c: Any) -> Dict[str, Any]:
    return {
        "id": c.id,
        "label": c.label or c.id,
        "group": c.group,
        "topic": c.topic,
        "stateful": c.stateful,
        "params": sorted((c.params or {}).keys()),
        "verified": c.verified,
    }


def _param_dict(p: Any) -> Dict[str, Any]:
    choices = list((p.ui_to_soap or {}).keys()) or list(p.values or [])
    return {
        "name": p.name,
        "label": p.ui_label or p.name,
        "choices": choices,
        "example": p.example,
        "secret": param_is_secret(p),
    }


def _action_dict(a: Any) -> Dict[str, Any]:
    return {
        "token": a.template_token,
        "label": a.label or a.template_token,
        "group": a.group,
        "recurrence": a.recurrence,
        "verified": a.verified,
        "params": [_param_dict(p) for p in (a.soap_params or [])],
        "needs_capture": bool(capture_param_names(a)),
    }


def list_capabilities(model: str) -> Dict[str, Any]:
    """Structured view of a model's rule vocabulary for the model to pick from.

    ``{available: False, reason}`` when the model isn't surveyed; otherwise
    ``{available: True, model, conditions[], actions[]}``. (Current rules on a
    specific device are added by the caller, which has the device handle.)"""
    survey = _atlas().events_survey(model)
    if survey is None:
        return {
            "available": False,
            "model": model,
            "reason": (
                f"No events/rules survey exists for {model or 'this model'} yet, "
                "so ADMZ can't build rules for it. Rules are available on surveyed "
                "models (e.g. the speakers/intercoms and cameras already in the fleet)."
            ),
        }
    return {
        "available": True,
        "model": model,
        "conditions": [_condition_dict(c) for c in survey.conditions],
        "actions": [_action_dict(a) for a in survey.actions],
    }


def build(
    model: str,
    condition_id: str,
    action_token: str,
    param_choices: Optional[Dict[str, Any]] = None,
    rule_name: str = "AtlasRule",
) -> Any:
    """Render the rule via the atlas. Returns a ``RuleBuildResult`` (``.available``
    is False with ``.error`` when unbuildable)."""
    return _atlas().build_rule(
        model, condition_id, action_token,
        param_choices=param_choices, rule_name=rule_name,
    )


def condition_for(model: str, condition_id: str) -> Any:
    survey = _atlas().events_survey(model)
    return survey.condition(condition_id) if survey else None


def action_for(model: str, action_token: str) -> Any:
    survey = _atlas().events_survey(model)
    return survey.action(action_token) if survey else None


# --------------------------------------------------------------------------
# Secret / capture classification
# --------------------------------------------------------------------------

def param_is_secret(p: Any) -> bool:
    """True if a param's VALUE must never appear in chat/logs — the survey flags
    it for secure capture (``capture_note``) or its name is password-family."""
    if getattr(p, "capture_note", ""):
        return True
    name = (getattr(p, "name", "") or "").lower()
    return any(h in name for h in _SECRET_HINTS)


def capture_param_names(action: Any) -> List[str]:
    """Param names that must be collected via the credential-capture widget
    rather than passed through chat — the recipient login + password pair (plus
    any survey-flagged capture params)."""
    names: List[str] = []
    for p in getattr(action, "soap_params", []) or []:
        name = (getattr(p, "name", "") or "")
        low = name.lower()
        if param_is_secret(p) or any(h in low for h in _LOGIN_HINTS):
            names.append(name)
    return names


def primary_recipient_secret_fields(action: Any) -> List[Dict[str, Any]]:
    """The PRIMARY (username, password) recipient params to collect via the
    secure form — ``[{name, label, kind}]``.

    v1 collects only the primary login + password pair; secondary credentials
    (proxy_*, pop_*) are not captured (rare; build_rule warns if a rule needs
    them). ``kind`` is ``password`` for the secret field, ``text`` for the
    username, so the form can mask appropriately."""
    login = pwd = None
    for p in getattr(action, "soap_params", []) or []:
        low = (getattr(p, "name", "") or "").lower()
        if login is None and low in ("login", "username", "user"):
            login = p
        if pwd is None and low == "password":
            pwd = p
    fields: List[Dict[str, Any]] = []
    if login is not None:
        fields.append({"name": login.name,
                       "label": login.ui_label or "Recipient username",
                       "kind": "text"})
    if pwd is not None:
        fields.append({"name": pwd.name,
                       "label": pwd.ui_label or "Recipient password",
                       "kind": "password"})
    return fields


# --------------------------------------------------------------------------
# Human summary for the approval card
# --------------------------------------------------------------------------

def describe_rule(
    result: Any,
    *,
    device_label: str,
    device_id: str,
    rule_name: str,
    condition: Any = None,
    action: Any = None,
) -> str:
    """One-sentence plain-language description of the rule for the url_only card.

    Uses the survey's human labels for the trigger and action, states the
    always-on nature, and appends any atlas prerequisites/warnings so the
    approver sees caveats (unverified entries, feature gates) before approving."""
    trigger = (getattr(condition, "label", "") or "").strip() or "the trigger fires"
    act = (getattr(action, "label", "") or "").strip() or "run the action"
    recurrence = getattr(result, "action_recurrence", "") or ""
    tail = (
        "It runs while the trigger condition holds"
        if recurrence == "continuous"
        else "It runs each time the trigger fires"
    )
    sentence = (
        f"Create rule '{rule_name}' on {device_label} ({device_id}): "
        f"when {trigger} → {act}. {tail}, until the rule is removed."
    )
    caveats: List[str] = list(getattr(result, "prerequisites", []) or [])
    caveats += list(getattr(result, "warnings", []) or [])
    if caveats:
        sentence += " Note: " + " ".join(caveats)
    return sentence
