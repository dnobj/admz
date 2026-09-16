"""One review annotator for every drift surface (ADR-0070 §2).

The web UI, the chat tools and the notice producer all show an operator the
same drifted rows, so they must all read the same annotations. This module is
that single place: which rows a targeted revert can write back, which rows
ADMZ's own audited writes explain (#230), and what each row most likely is
(``triage``).

Everything here depends only on the registry, the git repo and the drift
cache — never on a request — so the REST route, the MCP server and a
background producer call exactly the same functions.

Like attribution and triage, annotation only ever **adds** keys. Nothing here
removes a row or touches ``bucket`` or ``has_drift``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from admz.snapshot.attribution import annotate_attribution
from admz.snapshot.triage import annotate_triage, report_context

logger = logging.getLogger(__name__)

#: How many applicable ignore rules a review carries. The count is always
#: reported; the list is capped so a fleet with hundreds of rules cannot
#: crowd a chat tool result.
MAX_REVIEW_IGNORE_RULES = 20


def _device_info(registry: Any, device_id: str) -> Dict[str, Any]:
    info = dict(registry.get_device_info(device_id) or {})
    info["device_id"] = device_id
    return info


def annotate_revertable(
    summary: Dict[str, Any], *, registry: Any, device_id: str,
) -> None:
    """Annotate each drifted field with whether a TARGETED revert can write it
    back — the UI uses this to enable/disable the per-row checkbox. Uses the SAME
    facet.revert_param/op_revertable the revert plan builder uses, so the checkbox
    matches exactly what revert would do. Pure (no device probe), so it's applied
    on both the live and the cached path."""
    from admz.snapshot.facets import get_facets_for_device

    device_info = _device_info(registry, device_id)
    facets_by_name = {f.name: f for f in get_facets_for_device(device_info)}
    for fld in summary.get("drifted_fields", []):
        facet = facets_by_name.get(fld.get("facet"))
        if not fld.get("canonical_key") and facet is not None:
            fld["canonical_key"] = facet.canonical_key(fld.get("path"))
        revertable = False
        reason = "read-only"
        if facet is not None and facet.op_revertable(fld.get("path")):
            revertable = True
        elif str(fld.get("expected")) == "<missing>":
            reason = "added"  # appeared live; no baseline value to restore
        elif facet is not None and facet.revert_param(
            fld.get("path"), fld.get("expected")
        ) is not None:
            revertable = True
        if fld.get("bucket") == "demo_set":
            revertable = False
            reason = "demo-owned"
        fld["revertable"] = revertable
        if not revertable:
            fld["revert_skip_reason"] = reason


def cached_drift_report(registry: Any, device_id: str) -> Optional[Dict[str, Any]]:
    """The cached drift report for a device, but ONLY when it is still diffed
    against the device's CURRENT baseline. A stale-baseline cache (the baseline
    moved via accept / re-snapshot) is ignored so it can never drive a wrong
    revert or a misleading inspect — the caller falls back to a live check.
    Returns the cache dict ``{"report", "observed_sha", "signature",
    "computed_at"}`` or None. Best-effort."""
    try:
        from admz.snapshot import drift_alerts as _da
        cached = _da.drift_alerts.get_report(device_id)
    except Exception:  # noqa: BLE001 — a cache miss falls back to a live check
        return None
    if cached is None:
        return None
    try:
        current_baseline = registry.get_device_info(device_id).get("baseline_sha")
    except Exception:  # noqa: BLE001
        return None
    if (cached.get("report") or {}).get("baseline_sha") != current_baseline:
        return None  # baseline moved → cache stale → force a live check
    return cached


async def revert_fields_for(
    registry: Any,
    drift_detector: Any,
    device_id: str,
    *,
    selected: Optional[Iterable[Tuple[str, str]]] = None,
) -> Tuple[List[Any], List[Tuple[str, str]]]:
    """The drifted fields a targeted revert should write, and the selected
    ``(facet, path)`` pairs the diff does not contain.

    Per the drift-cache design, accept and revert act on the CACHED diff, so
    they match exactly what was inspected, without a fresh probe; with nothing
    cached this falls back to a live ``check_drift``. ``demo_set`` rows are
    never returned (ADR-0047: they belong to an active demo, and a revert must
    not kick it off) — but they are part of the diff, so selecting one is not
    "not found": the caller reports it as skipped. ``base_value`` travels with
    each field.

    ``selected`` narrows the result to those pairs, in the diff's order.
    """
    from admz.snapshot.models import DriftField

    cached = cached_drift_report(registry, device_id)
    if cached is not None:
        rows = (cached.get("report") or {}).get("drifted_fields", [])
        every = [
            DriftField(
                facet=r.get("facet", ""), path=r.get("path", ""),
                expected=r.get("expected", ""), actual=r.get("actual", ""),
                canonical_key=r.get("canonical_key"),
                bucket=r.get("bucket", "unclaimed"),
                owner=r.get("owner"), owner_name=r.get("owner_name"),
                candidates=r.get("candidates") or [],
                base_value=r.get("base_value"),
            )
            for r in rows
        ]
    else:
        report = await drift_detector.check_drift(device_id)
        every = list(report.fields)
    fields = [f for f in every if f.bucket != "demo_set"]
    if selected is None:
        return fields, []
    wanted: List[Tuple[str, str]] = []
    for pair in selected:
        pair = (str(pair[0]), str(pair[1]))
        if pair not in wanted:
            wanted.append(pair)
    present = {(f.facet, f.path) for f in every}
    not_found = [p for p in wanted if p not in present]
    chosen = set(wanted)
    return [f for f in fields if (f.facet, f.path) in chosen], not_found


def annotate_review(
    summary: Dict[str, Any],
    *,
    registry: Any,
    git_repo: Any = None,
    device_id: str,
    device_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Everything a reviewer needs on one drift summary. Mutates and returns it.

    In order: ``revertable`` (and the canonical key it fills in), then
    ``attribution`` (#230), then ``triage`` — which reads both — then the
    ignore rules that already apply to this device. Applied at READ time, on
    the cached and the live path alike, and never written into the cache.
    """
    info = device_info if device_info is not None else _device_info(registry, device_id)
    annotate_revertable(summary, registry=registry, device_id=device_id)
    annotate_attribution(summary, device_id=device_id)
    annotate_triage(
        summary,
        context=report_context(summary, git_repo=git_repo, device_info=info),
    )
    try:
        from admz.snapshot.ignore import applicable_rules

        rules = applicable_rules(device_id, info.get("tags"))
    except Exception as e:  # noqa: BLE001 — the rule list is a reading aid
        logger.debug("ignore rules unavailable for %s: %s", device_id, e)
        rules = []
    summary["applicable_ignore_rules"] = rules[:MAX_REVIEW_IGNORE_RULES]
    summary["ignore_rule_count"] = len(rules)
    return summary
