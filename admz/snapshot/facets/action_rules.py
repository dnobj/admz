"""Action rules facet — the 'then do X' side of events (send email, record,
play audio, activate output), read via the beta Action Rules REST API.

Unlike the param facets this reads a non-param.cgi source through the
``extra_read_ops`` seam. Read-only for now: drift detects rule changes, but
restore is deferred (creating a rule is multi-step and recipient-linked).
Firmware-gated to AXIS OS >= 12 (the v2beta API); on older firmware the call
just fails and the engine yields an empty facet (graceful — no harm).
"""

from typing import Any, Dict, List

from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
    ReadSpec,
    register_facet,
)

# Server-assigned / runtime fields that flap between reads and aren't real
# config drift. Curated as we see live responses.
_VOLATILE_RULE_FIELDS = {"lastModified", "modified", "created", "etag", "revision"}


def _extract_rules(payload: Any) -> List[Dict[str, Any]]:
    """Pull the rules list out of whatever shape listRules returns — a bare
    list, ``{"rules": [...]}``, or ``{"data": {"rules": [...]}}``. Defensive
    because the op is auto-drafted from OpenAPI (shape unverified live)."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("rules", "items", "data"):
            v = payload.get(key)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
            if isinstance(v, dict) and isinstance(v.get("rules"), list):
                return [r for r in v["rules"] if isinstance(r, dict)]
    return []


@register_facet
class ActionRulesFacet(FacetAdapter):
    NAME = "action_rules"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        return [DeviceCriteria(families=["vapix"], min_firmware="12")]

    @property
    def extra_read_ops(self) -> List[ReadSpec]:
        return [
            ReadSpec(
                operation_id="action-rules:listRules",
                result_key="action_rules",
            )
        ]

    @property
    def write_ops(self) -> List[str]:
        return []

    @property
    def restore_order(self) -> int:
        return 70

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        rules = _extract_rules(raw_responses.get("action_rules"))
        result: Dict[str, Any] = {}
        for i, rule in enumerate(rules):
            rid = str(rule.get("id") or rule.get("name") or i)
            result[rid] = {
                k: v for k, v in rule.items()
                if k not in _VOLATILE_RULE_FIELDS
            }
        return result

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Read-only: rule restore is deferred (multi-step, recipient-linked).
        return []
