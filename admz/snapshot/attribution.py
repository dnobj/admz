"""Drift attribution — mark the drift rows ADMZ's own audited writes explain.

**ANNOTATE, NEVER SUPPRESS** (#230). This module only ever *adds* an
``attribution`` key to a drifted-field dict. It must never remove a row, never
touch ``bucket`` / ``real_fields`` / ``has_drift``, and never change a device's
drift state. That is not a style preference — it is the correctness boundary:

    An ADMZ-originated write and a later on-device edit can touch the same
    rule. The audit row records the tool *arguments*, never the resulting
    config, so there is nothing to compare the live value against. A matched
    row therefore proves ADMZ wrote to that rule ONCE; it proves nothing about
    whether the current value is what ADMZ wrote. Auto-accepting on a match
    would hide the second edit, and nothing downstream could recover it.

``DriftField.bucket`` already carries a *suppressing* value (``demo_set`` is
excluded from ``DriftReport.real_fields``), which is exactly the trap: express
attribution through ``bucket`` and it silently changes drift state. Hence a
separate key, applied at READ time by a function that has no path to drop a row.

Read-time, not capture-time
---------------------------
This runs below ``DriftReport.to_summary()``, on both the live and the cached
path, and its result is deliberately NOT written into the cached payload
(``drift_alerts.store_report``). A report cached before its audit row landed
would otherwise never gain attribution.

What the join actually supports
-------------------------------
``audit_log`` has no device column — device identity lives inside ``resource``
(``mcp:create_action_rule/device:<id>``) or inside ``details_json``
(``snapshot.scenario_*`` puts device ids in ``details.applied``).
``AuditLog.search(device=..., action=...)`` already covers both with a LIKE.

Three strengths of match, weakest last, all annotated with their own hedge:

``rule_id``   The audit row records the rule id outright. Read from
              ``details.rule_id`` or ``details.args.rule_id``. Available today
              for *deletes* (the id is an inbound tool argument); available for
              *creates* only once the create path records it (#230 PR 2 —
              ``runner.py`` extracts ``RuleID`` and ``operations.py`` returns
              it, but ``confirm.py`` currently discards it). This code reads the
              field opportunistically, so PR 2 upgrades matches with no change
              here.
``rule_name`` The only retroactive per-rule key. ``mcp.create_action_rule``
              records the requested ``rule_name`` in ``details.args``; the live
              rule contributes a ``<rid>.name`` drift row. Names are neither
              unique nor stable under an on-device rename, so this is stated as
              a correlation in the UI copy rather than implied to be exact.
``device``    "ADMZ changed action rules on this device around then." No
              per-rule claim at all. The weakest version, and still most of the
              value: it turns "36 unexplained changes" into "36 changes on a
              device ADMZ wrote rules to on 2026-07-18".

Two further wrinkles the copy states plainly rather than papering over:

* ``mcp.create_action_rule`` / ``mcp.delete_action_rule`` rows are recorded with
  ``success=0`` **by design** — those tools do not write anything, they open a
  confirmation session (``mcp/server.py`` ``_create_action_rule``). The row is
  an *intent*, not a creation.
* The approver is on a **separate** ``confirm.approve`` row keyed
  ``device:<id>/op:<op>``, which carries no rule name or id. We correlate it by
  device + time proximity only, and label it as correlated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

ACTION_RULES_FACET = "action_rules"

# Audit actions meaning "ADMZ wrote to this device's action rules".
RULE_WRITE_ACTIONS = ("mcp.create_action_rule", "mcp.delete_action_rule")
# scenario_save only records a snapshot; it pushes nothing to a device.
SCENARIO_WRITE_ACTIONS = ("snapshot.scenario_activate", "snapshot.scenario_return")
APPROVE_ACTION = "confirm.approve"

# How near (seconds) a confirm.approve row must sit to an intent row before we
# will *correlate* them. The two rows share only a device and a rough time, so
# this is a heuristic and is labelled as one. Generous enough to cover a human
# reading an approval card, tight enough that two unrelated approvals on the
# same device in the same quarter-hour is the only way to mis-pair.
APPROVE_WINDOW_S = 15 * 60

_MISSING = "<missing>"

# Appended to every note. The single most important sentence in this feature.
_HEDGE = (
    "This shows ADMZ wrote to it once — it is NOT proof the current value is "
    "what ADMZ wrote. The audit row records the tool arguments, never the "
    "resulting config, so a later on-device edit would look identical. This "
    "row is still drift and still needs review."
)

_INTENT_NOTE = (
    "The {action} row records the request that opened the confirmation gate "
    "(stored as success=0 by design — that tool opens a gate, it does not "
    "write)."
)


def _fmt_when(ts: Any) -> Tuple[Optional[str], str]:
    """(iso, human) for a unix timestamp; ('', 'an unknown time') if unusable."""
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None, "an unknown time"
    return dt.isoformat(), dt.strftime("%Y-%m-%d %H:%M UTC")


def _rule_id_of(path: str) -> str:
    """Leading segment of a flattened action_rules key.

    ``flatten()`` joins path segments with dots and ``ActionRulesFacet.serialize``
    keys the facet doc by rule id, so ``175.actionConfig.actionParameters`` ->
    ``175``. The id is never joined into an opaque blob — it survives verbatim
    into ``DriftField.path`` and ``canonical_key``.
    """
    return str(path or "").partition(".")[0]


def live_rule_names(fields: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    """{rule id -> name} recovered from the drift rows themselves.

    Only rules whose ``name`` actually drifted contribute — a wholesale add or
    delete emits ``<rid>.name``, but a rule where only ``enabled`` changed does
    not. That is the accepted degrade: such a rule groups as "Rule 175" with no
    name and can only ever match by rule id or device, never by name. Reading
    the nested doc to always recover the name is a backend change, deliberately
    out of scope here.
    """
    names: Dict[str, str] = {}
    for fld in fields:
        if fld.get("facet") != ACTION_RULES_FACET:
            continue
        rid, _, rest = str(fld.get("path") or "").partition(".")
        if rest != "name" or not rid:
            continue
        # A deleted rule has actual="<missing>"; its name is on the baseline side.
        for candidate in (fld.get("actual"), fld.get("expected")):
            text = str(candidate) if candidate is not None else ""
            if text and text != _MISSING:
                names[rid] = text
                break
    return names


def _entry_rule_ids(entry: Any) -> List[str]:
    """Rule ids recorded on an audit row, if any.

    Looks in ``details`` and ``details.args`` so it picks up both the delete
    path's inbound ``rule_id`` argument today and the create path's recorded
    ``rule_id`` once #230 PR 2 lands, with no change here.
    """
    details = getattr(entry, "details", None)
    if not isinstance(details, dict):
        return []
    args = details.get("args")
    sources = [details, args if isinstance(args, dict) else {}]
    out: List[str] = []
    for src in sources:
        for key in ("rule_id", "ruleId"):
            value = src.get(key)
            if value not in (None, "") and str(value) not in out:
                out.append(str(value))
    return out


def _entry_rule_name(entry: Any) -> str:
    details = getattr(entry, "details", None)
    if not isinstance(details, dict):
        return ""
    args = details.get("args")
    for src in (details, args if isinstance(args, dict) else {}):
        value = src.get("rule_name")
        if value not in (None, ""):
            return str(value)
    return ""


def _nearest_approval(entry: Any, approvals: Sequence[Any]) -> Optional[Any]:
    """The confirm.approve row nearest in time, within APPROVE_WINDOW_S."""
    best: Optional[Tuple[float, Any]] = None
    try:
        origin = float(getattr(entry, "timestamp", None))
    except (TypeError, ValueError):
        return None
    for row in approvals:
        try:
            delta = abs(float(getattr(row, "timestamp", None)) - origin)
        except (TypeError, ValueError):
            continue
        if delta <= APPROVE_WINDOW_S and (best is None or delta < best[0]):
            best = (delta, row)
    return best[1] if best else None


def _build_attribution(
    entry: Any,
    *,
    match: str,
    rule_id: str,
    rule_name: str,
    approver: Optional[Any],
) -> Dict[str, Any]:
    iso, human = _fmt_when(getattr(entry, "timestamp", None))
    action = str(getattr(entry, "action", "") or "")
    requester = str(getattr(entry, "requester", "") or "") or "an unknown principal"

    if match == "rule_id":
        label = "ADMZ wrote this rule"
        head = (
            f"ADMZ wrote to rule {rule_id} on {human} ({action}, requested by "
            f"{requester}). Matched on the rule id recorded in the audit row."
        )
    elif match == "rule_name":
        label = "ADMZ wrote this rule (name match)"
        head = (
            f"ADMZ wrote a rule named “{rule_name}” on {human} "
            f"({action}, requested by {requester}). Matched by rule NAME and "
            f"time, not by rule id — the audit row records the requested "
            f"name, which is not unique and not stable if the rule was renamed "
            f"on the device. Treat as a correlation."
        )
    else:
        label = "ADMZ changed rules on this device"
        head = (
            f"ADMZ changed action rules on this device on {human} ({action}, "
            f"requested by {requester}). NOT matched to this specific rule "
            f"— device- and time-level correlation only."
        )

    parts = [head]
    if action in RULE_WRITE_ACTIONS and getattr(entry, "success", True) is False:
        parts.append(_INTENT_NOTE.format(action=action))
    if approver is not None:
        who = str(getattr(approver, "requester", "") or "") or "an unknown principal"
        parts.append(
            f"Approved by {who} (correlated by device and time from a separate "
            f"confirm.approve row, which carries no rule id or name)."
        )
    parts.append(_HEDGE)

    return {
        "source": "admz",
        "match": match,
        "confidence": "exact" if match == "rule_id" else "correlated",
        "action": action,
        "when": iso,
        "when_human": human,
        "requested_by": str(getattr(entry, "requester", "") or ""),
        "approved_by": (
            str(getattr(approver, "requester", "") or "")
            if approver is not None
            else None
        ),
        "approved_by_correlated": approver is not None,
        "rule_id": rule_id or None,
        "rule_name": rule_name or None,
        "label": label,
        "note": " ".join(parts),
    }


def annotate_attribution(
    summary: Dict[str, Any],
    *,
    device_id: str,
    audit: Any = None,
) -> Dict[str, Any]:
    """Add an ``attribution`` key to the drift rows ADMZ's own writes explain.

    Mutates ``summary`` in place and returns it. Adds keys only: no row is
    removed, no existing key is rewritten, ``has_drift`` and every ``bucket``
    are left exactly as found. Applied below ``to_summary()`` so the REST route
    and the MCP tool both get it.

    Defensive by construction — attribution is a nicety and drift is not, so any
    failure logs and leaves the report untouched rather than breaking the report
    for the device (mirroring how ``drift.py`` calls a facet normaliser).
    """
    try:
        fields = summary.get("drifted_fields") or []
        rule_fields = [f for f in fields if f.get("facet") == ACTION_RULES_FACET]
        if not rule_fields:
            return summary

        if audit is None:
            from admz.audit import audit_log as audit  # noqa: PLC0415

        # `action` is a LIKE substring: "action_rule" catches create+delete,
        # "scenario_" catches activate/return/save (save is filtered out below).
        writes = [
            e for e in audit.search(device=device_id, action="action_rule", limit=200)
            if getattr(e, "action", None) in RULE_WRITE_ACTIONS
        ]
        scenarios = [
            e for e in audit.search(device=device_id, action="scenario_", limit=200)
            if getattr(e, "action", None) in SCENARIO_WRITE_ACTIONS
        ]
        approvals = list(
            audit.search(device=device_id, action=APPROVE_ACTION, limit=200)
        )

        if not writes and not scenarios:
            return summary

        # search() returns newest first, so the first entry seen for a key wins.
        by_id: Dict[str, Any] = {}
        by_name: Dict[str, Any] = {}
        for entry in writes:
            for rid in _entry_rule_ids(entry):
                by_id.setdefault(rid, entry)
            name = _entry_rule_name(entry)
            if name:
                by_name.setdefault(name, entry)

        device_latest = None
        for entry in (writes + scenarios):
            try:
                stamp = float(getattr(entry, "timestamp", None))
            except (TypeError, ValueError):
                continue
            if device_latest is None or stamp > device_latest[0]:
                device_latest = (stamp, entry)

        names = live_rule_names(fields)
        approver_cache: Dict[int, Optional[Any]] = {}

        for fld in rule_fields:
            rid = _rule_id_of(fld.get("path"))
            name = names.get(rid, "")
            if rid and rid in by_id:
                entry, match = by_id[rid], "rule_id"
            elif name and name in by_name:
                entry, match = by_name[name], "rule_name"
            elif device_latest is not None:
                entry, match = device_latest[1], "device"
            else:
                continue
            key = id(entry)
            if key not in approver_cache:
                approver_cache[key] = _nearest_approval(entry, approvals)
            fld["attribution"] = _build_attribution(
                entry,
                match=match,
                rule_id=rid,
                rule_name=name or _entry_rule_name(entry),
                approver=approver_cache[key],
            )
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(
            "drift attribution failed for %s (report left unannotated): %s",
            device_id,
            e,
        )
    return summary
