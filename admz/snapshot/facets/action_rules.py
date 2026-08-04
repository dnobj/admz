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

# --------------------------------------------------------------------------- #
# Condition-clause normalisation (#228)
#
# An activation condition's ``messageContent`` is an XPath boolean expression.
# When its top-level clauses are joined by ``and`` their ORDER carries no
# meaning, but the doc is compared as a string — so the same rule serialized
# the other way round reports as drift the operator cannot clear (the facet is
# read-only, so "accept baseline" is the only offered action, and the next
# reorder drifts again).
#
# Observed live on the C1110-E (B8A44FB0BDA1) and I8016-LVE (B8A44F0C5B32).
# The reorder is self-inflicted: a scenario round-trip (scenario_activate ->
# scenario_return) rewrites the rule and ADMZ's own writer emits the clauses in
# its order rather than the device's, so it recurs on every activation.
#
# SCOPE — deliberately narrow. We recognise exactly one shape: two or more
# top-level ``and``-joined, individually balanced ``boolean(...)`` calls.
# Everything else is returned VERBATIM so it is byte-compared and still reports
# as drift. Not recognised, and intentionally so:
#   * ``or`` anywhere at top level, and mixed ``and``/``or`` precedence,
#   * ``not(...)``, ``|`` unions, parenthesised top-level grouping,
#   * mixed-case ``AND`` (XPath keywords are lowercase; anything else is not a
#     keyword we're willing to assume about),
#   * unbalanced quotes/brackets.
# Reordering across ``or`` may well be equivalent too, but proving it needs an
# expression evaluator, and every bug in one is a FALSE NEGATIVE that hides a
# real change. Noise is the cheaper failure.
#
# Clauses are compared as a sorted MULTISET, never a set: under set semantics
# ``A and A and B`` equals ``A and B``, so dropping a duplicated clause would
# become invisible. Duplicates are preserved.
# --------------------------------------------------------------------------- #

_AND = "and"
_BOOL = "boolean("


def _split_top_level_and(expr: str):
    """Split ``expr`` on ``and`` at bracket/paren depth 0 and outside quotes.

    Depth tracking is the whole point: an XPath predicate legitimately contains
    ``and`` — ``[@Name="CallState" and @Value="Ringing"]`` — so a naive
    ``split(" and ")`` shreds a single clause into fragments and could compare
    two genuinely different rules equal.

    Returns the raw (unstripped) parts, or None if quotes/brackets don't
    balance."""
    parts: List[str] = []
    depth = 0
    quote = None
    start = 0
    i = 0
    n = len(expr)
    while i < n:
        ch = expr[i]
        if quote is not None:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            continue
        if ch in "([":
            depth += 1
            i += 1
            continue
        if ch in ")]":
            depth -= 1
            if depth < 0:
                return None                       # unbalanced — bail
            i += 1
            continue
        if (depth == 0
                and expr.startswith(_AND, i)
                and i > 0 and expr[i - 1].isspace()
                and (i + len(_AND) >= n or expr[i + len(_AND)].isspace())):
            parts.append(expr[start:i])
            i += len(_AND)
            start = i
            continue
        i += 1
    if quote is not None or depth != 0:
        return None                               # unbalanced — bail
    parts.append(expr[start:])
    return parts


def _is_single_boolean_call(clause: str) -> bool:
    """True only when ``clause`` is exactly ONE balanced ``boolean(...)`` call.

    Rejects ``boolean(a) | boolean(b)``, ``not(boolean(a))`` and
    ``(boolean(a) and boolean(b))`` — the trailing-paren check is what catches
    a clause whose ``boolean(`` closes before the end."""
    if not clause.startswith(_BOOL) or not clause.endswith(")"):
        return False
    depth = 0
    quote = None
    for i in range(len(_BOOL) - 1, len(clause)):
        ch = clause[i]
        if quote is not None:
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
            if depth == 0:
                return i == len(clause) - 1       # must close at the very end
            if depth < 0:
                return False
    return False


def normalize_condition_expression(expr: Any) -> Any:
    """Canonical form of one ``messageContent`` for order-insensitive compare.

    Returns ``expr`` UNCHANGED unless it is confidently a set of top-level
    ``and``-joined ``boolean(...)`` clauses; then it returns those clauses
    sorted (as a multiset) and rejoined with a single ``" and "``.

    Only whitespace SURROUNDING a clause is trimmed — never internal
    whitespace, and never case: both are significant inside an XPath value."""
    if not isinstance(expr, str):
        return expr
    parts = _split_top_level_and(expr)
    if parts is None or len(parts) < 2:
        return expr                               # malformed, or nothing to reorder
    clauses = [p.strip() for p in parts]
    if not all(_is_single_boolean_call(c) for c in clauses):
        return expr                               # unrecognised shape → byte compare
    return f" {_AND} ".join(sorted(clauses))      # sorted MULTISET (dupes kept)


def _normalize_rule(rule: Any) -> Any:
    """Rewrite a rule's condition ``messageContent`` fields to canonical form,
    leaving every other field — and the condition LIST order — untouched.
    Copy-on-write: returns the input object when nothing changed."""
    if not isinstance(rule, dict):
        return rule
    act = rule.get("activationConfig")
    if not isinstance(act, dict):
        return rule
    conds = act.get("condition")
    if not isinstance(conds, list):
        return rule
    out: List[Any] = []
    changed = False
    for cond in conds:
        if isinstance(cond, dict) and isinstance(cond.get("messageContent"), str):
            norm = normalize_condition_expression(cond["messageContent"])
            if norm != cond["messageContent"]:
                cond = {**cond, "messageContent": norm}
                changed = True
        out.append(cond)
    if not changed:
        return rule
    return {**rule, "activationConfig": {**act, "condition": out}}


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
            # Normalise on the way in too, so new baselines and the git config
            # repo are written already-canonical and stop churning. Comparison
            # does NOT rely on this — normalize_doc handles baselines captured
            # before this shipped (see normalize_doc / drift.py).
            result[rid] = _normalize_rule({
                k: v for k, v in rule.items()
                if k not in _VOLATILE_RULE_FIELDS
            })
        return result

    def normalize_doc(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Canonicalise every rule's condition clauses (#228). Applied to both
        the live doc and the git-stored baseline, so a baseline captured before
        this shipped clears on the next drift computation with NO re-capture."""
        if not isinstance(doc, dict):
            return doc
        return {rid: _normalize_rule(rule) for rid, rule in doc.items()}

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Read-only: rule restore is deferred (multi-step, recipient-linked).
        return []
