"""Run the SOAP rule sequence that ``axis_api_atlas.Atlas.build_rule`` composes.

The atlas renders two device-proven SOAP bodies — ``AddActionConfiguration``
(returns a ``ConfigurationID``) and ``AddActionRule`` (links a trigger to that
config, returns a ``RuleID``). This module executes them against a device
through the shared VAPIX executor and parses the ids the device returns. It
reuses the catalog's ``action-service`` SOAP ops (``generation: soap``) and only
overrides the rendered body — so scheme/auth self-healing, content-type, and the
POST to ``/vapix/services`` all come from the existing execution path
(``admz/executor/vapix.py``). Auth is taken from the registry ``device`` profile,
never from the op.

Create is a two-call choreography with orphan cleanup; delete reads the rule to
find its linked config and removes both. Nothing here composes XML — the atlas
owns rule shape and device quirks (ONVIF filter dialect, Conditions-vs-StartEvent,
0-indexed physical ports). See ADR-0043.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Mapping, Optional

from admz.redact import is_sensitive_key

_FAMILY = "vapix"
_OP_ADD_CONFIG = "action-service:AddActionConfiguration"
_OP_ADD_RULE = "action-service:AddActionRule"
_OP_GET_RULES = "action-service:GetActionRules"
_OP_RM_RULE = "action-service:RemoveActionRule"
_OP_RM_CONFIG = "action-service:RemoveActionConfiguration"

# The atlas leaves this literal in the rule body's <PrimaryAction>; we fill it
# with the ConfigurationID the device returns from AddActionConfiguration.
_ACTION_CONFIG_ID_PLACEHOLDER = "{action_configuration_id}"


class RuleRunnerError(RuntimeError):
    """A SOAP rule step failed — the device rejected it, the catalog is missing
    the op, or an expected id was absent from the response. Carries the per-step
    outcomes collected before the failure so callers can surface them."""

    def __init__(self, message: str, steps: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.steps = steps or []


# --------------------------------------------------------------------------
# Response parsing (tolerant of any namespace prefix)
# --------------------------------------------------------------------------

def _extract(tag: str, xml: Optional[str]) -> Optional[str]:
    """Text of the first ``<[ns:]tag ...>value</[ns:]tag>`` element, or None."""
    if not xml:
        return None
    m = re.search(rf"<(?:\w+:)?{tag}\b[^>]*>([^<]*)</(?:\w+:)?{tag}\s*>", xml)
    return m.group(1).strip() if m else None


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_rules(xml: Optional[str]) -> List[Dict[str, Any]]:
    """Parse a ``GetActionRules`` response into
    ``[{rule_id, name, enabled, primary_action}]``.

    Walks the tree by element *local* name so it is namespace-agnostic (the
    device echoes rules under the ``action1`` namespace with assorted prefixes),
    and pairs each ``RuleID`` with its siblings' ``Name`` / ``Enabled`` /
    ``PrimaryAction``. Best-effort: a rule whose ``PrimaryAction`` can't be read
    still lists (its linked config just won't be auto-removed on delete)."""
    if not xml:
        return []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return _parse_rules_regex(xml)

    parents = {child: parent for parent in root.iter() for child in parent}
    rules: List[Dict[str, Any]] = []
    for el in root.iter():
        if _localname(el.tag) != "RuleID":
            continue
        container = parents.get(el)
        if container is None:
            continue
        fields: Dict[str, str] = {}
        for child in container:
            fields[_localname(child.tag)] = (child.text or "").strip()
        rid = fields.get("RuleID")
        if not rid:
            continue
        enabled = fields.get("Enabled")
        rules.append({
            "rule_id": rid,
            "name": fields.get("Name"),
            "enabled": (enabled.lower() == "true") if enabled else None,
            "primary_action": fields.get("PrimaryAction"),
        })
    return rules


def _parse_rules_regex(xml: str) -> List[Dict[str, Any]]:
    """Fallback parse when the response isn't well-formed XML — slice on rule
    containers and pull each field with the tolerant ``_extract``."""
    rules: List[Dict[str, Any]] = []
    for block in re.findall(
        r"<(?:\w+:)?ActionRule\b.*?</(?:\w+:)?ActionRule\s*>", xml, re.DOTALL
    ):
        rid = _extract("RuleID", block)
        if not rid:
            continue
        enabled = _extract("Enabled", block)
        rules.append({
            "rule_id": rid,
            "name": _extract("Name", block),
            "enabled": (enabled.lower() == "true") if enabled else None,
            "primary_action": _extract("PrimaryAction", block),
        })
    return rules


def redact_soap_body(xml: Optional[str]) -> Optional[str]:
    """Mask ``Value="..."`` on any ``<[ns:]Parameter Name="<sensitive>" .../>``
    row so a rendered notification config (which inlines login/password) is safe
    to audit or return. Non-secret rows pass through unchanged."""
    if not xml:
        return xml

    def _mask(m: "re.Match[str]") -> str:
        if is_sensitive_key(m.group("name")):
            return f'{m.group("pre")}Value="***"'
        return m.group(0)

    return re.sub(
        r'(?P<pre><\w*:?Parameter\s+Name="(?P<name>[^"]+)"\s+)Value="[^"]*"',
        _mask,
        xml,
    )


# --------------------------------------------------------------------------
# SOAP execution
# --------------------------------------------------------------------------

def _step(op: str, result: Any) -> Dict[str, Any]:
    return {
        "op": op,
        "success": bool(getattr(result, "success", False)),
        "status_code": getattr(result, "status_code", None),
        "error": getattr(result, "error", None),
    }


async def _run_soap(
    *,
    catalog: Any,
    executor: Any,
    device: Mapping[str, Any],
    creds: Mapping[str, Any],
    op_id: str,
    body_override: Optional[str] = None,
    params: Optional[Mapping[str, str]] = None,
) -> Any:
    """Execute one action-service SOAP op via the shared executor.

    Reuses the catalog op's ``to_executor_dict`` (correct ``generation: soap``
    and content-type); when ``body_override`` is given (a fully-rendered atlas
    body) it replaces ``request.body_xml`` and forces ``params={}`` so the
    executor's ``{placeholder}`` pass is skipped. For the parameterized
    delete/get ops, ``params`` (e.g. ``{"rule_id": ...}``) drives that pass."""
    op = catalog.get_operation(_FAMILY, op_id)
    if not op:
        raise RuleRunnerError(
            f"Catalog is missing SOAP op {op_id!r} — is axis-api-atlas current?"
        )
    op_dict = op.to_executor_dict()
    if body_override is not None:
        req = dict(op_dict.get("request") or {})
        req["body_xml"] = body_override
        op_dict["request"] = req
        params = {}
    return await executor.execute(op_dict, dict(device), dict(creds), dict(params or {}))


async def create_rule(
    *,
    catalog: Any,
    executor: Any,
    device: Mapping[str, Any],
    creds: Mapping[str, Any],
    config_body: str,
    rule_body: str,
) -> Dict[str, Any]:
    """Create a rule from the atlas's two rendered bodies.

    AddActionConfiguration → parse ConfigurationID → fill the rule body's
    ``{action_configuration_id}`` → AddActionRule → parse RuleID. If the rule
    step fails, the just-created configuration is removed so no orphan is left.
    Raises :class:`RuleRunnerError` on any failure (with the steps so far)."""
    steps: List[Dict[str, Any]] = []

    r1 = await _run_soap(
        catalog=catalog, executor=executor, device=device, creds=creds,
        op_id=_OP_ADD_CONFIG, body_override=config_body,
    )
    steps.append(_step("AddActionConfiguration", r1))
    if not getattr(r1, "success", False):
        raise RuleRunnerError(
            "Creating the action configuration failed: "
            f"{getattr(r1, 'error', None) or 'the device rejected it'}.",
            steps,
        )
    config_id = _extract("ConfigurationID", getattr(r1, "response_body", None))
    if not config_id:
        raise RuleRunnerError(
            "The device accepted the action configuration but returned no "
            "ConfigurationID — cannot link a rule to it.",
            steps,
        )

    filled_rule = rule_body.replace(_ACTION_CONFIG_ID_PLACEHOLDER, config_id)
    r2 = await _run_soap(
        catalog=catalog, executor=executor, device=device, creds=creds,
        op_id=_OP_ADD_RULE, body_override=filled_rule,
    )
    steps.append(_step("AddActionRule", r2))
    if not getattr(r2, "success", False):
        # Never leave an orphan configuration behind.
        try:
            rc = await _run_soap(
                catalog=catalog, executor=executor, device=device, creds=creds,
                op_id=_OP_RM_CONFIG, params={"configuration_id": config_id},
            )
            steps.append(_step("RemoveActionConfiguration (cleanup)", rc))
        except Exception:  # noqa: BLE001 — cleanup is best-effort
            pass
        raise RuleRunnerError(
            "Creating the rule failed (the orphaned configuration was cleaned "
            f"up): {getattr(r2, 'error', None) or 'the device rejected it'}.",
            steps,
        )

    rule_id = _extract("RuleID", getattr(r2, "response_body", None))
    return {"config_id": config_id, "rule_id": rule_id, "steps": steps}


async def list_rules(
    *, catalog: Any, executor: Any, device: Mapping[str, Any], creds: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Return the device's current action rules (GetActionRules)."""
    r = await _run_soap(
        catalog=catalog, executor=executor, device=device, creds=creds,
        op_id=_OP_GET_RULES,
    )
    if not getattr(r, "success", False):
        raise RuleRunnerError(
            "Could not read the device's action rules: "
            f"{getattr(r, 'error', None) or 'the device rejected it'}."
        )
    return parse_rules(getattr(r, "response_body", None))


async def delete_rule(
    *,
    catalog: Any,
    executor: Any,
    device: Mapping[str, Any],
    creds: Mapping[str, Any],
    rule_id: str,
) -> Dict[str, Any]:
    """Remove a rule by id and its linked action configuration.

    Reads GetActionRules first to find the rule's ``PrimaryAction`` (config id),
    removes the rule, then removes the now-unreferenced config (best-effort).
    Raises :class:`RuleRunnerError` if the rule removal itself fails."""
    steps: List[Dict[str, Any]] = []

    config_id: Optional[str] = None
    try:
        for rule in await list_rules(
            catalog=catalog, executor=executor, device=device, creds=creds
        ):
            if str(rule.get("rule_id")) == str(rule_id):
                config_id = rule.get("primary_action")
                break
    except RuleRunnerError:
        pass  # proceed with the rule id alone if the listing failed

    r1 = await _run_soap(
        catalog=catalog, executor=executor, device=device, creds=creds,
        op_id=_OP_RM_RULE, params={"rule_id": str(rule_id)},
    )
    steps.append(_step("RemoveActionRule", r1))
    if not getattr(r1, "success", False):
        raise RuleRunnerError(
            f"Removing rule {rule_id} failed: "
            f"{getattr(r1, 'error', None) or 'the device rejected it'}.",
            steps,
        )

    removed_config: Optional[str] = None
    if config_id:
        r2 = await _run_soap(
            catalog=catalog, executor=executor, device=device, creds=creds,
            op_id=_OP_RM_CONFIG, params={"configuration_id": str(config_id)},
        )
        steps.append(_step("RemoveActionConfiguration", r2))
        if getattr(r2, "success", False):
            removed_config = str(config_id)

    return {
        "removed_rule": str(rule_id),
        "removed_config": removed_config,
        "steps": steps,
    }
