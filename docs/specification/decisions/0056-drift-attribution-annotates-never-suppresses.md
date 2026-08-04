# ADR-0056 — Drift attribution annotates, never suppresses

**Status:** Accepted (2026-08-04). Shipped with #230 (attribution + per-rule grouping).
**Relates to:** ADR-0031 (baseline_sha / drift), ADR-0034 (the confirmation gate),
ADR-0047 (`bucket` / demo attribution), ADR-0055 (`normalize_doc`).

## Context

Drift's job is *"something changed that you did not do."* ADMZ's own gated,
approved, audited writes were being reported as unexplained drift, in a flat
per-parameter shape that buried what changed.

The operator read three drift reports on 2026-08-04 and had to ask what they
were looking at. Two of the three were ADMZ's own writes:

| Device | Reported | Actually |
|---|---|---|
| I8016-LVE `B8A44F0C5B32` | 12 changes | `mcp.create_action_rule`, 2026-07-18 — rule 175 |
| C1710 `E827250959C6` | 36 changes | `mcp.create_action_rule`, 2026-07-18 — rules 194/195 |
| C1110-E | 1 change | a scenario round-trip reordering a condition — fixed in #243 |

#243 removed the *phantom* rows (the wall clock, reordered clauses). What
remained is a different and more tractable problem: **real changes with no
explanation**, rendered one-per-parameter.

Two facts about the C1710's "36 changes" set the shape of the fix. They are
really **3 rules** — one added rule flattens to ~11 rows. And they are all
**read-only**: `ActionRulesFacet.write_ops == []`, so every rule row lands in the
UI's ungrouped read-only block rather than the grouped revertable table.

## Decision

### 1. Attribution is a read-time annotation that can only ADD keys

`snapshot/attribution.py::annotate_attribution` adds an `attribution` key to
drifted-field dicts. It has no path to remove a row: the row set is fixed
upstream in `check_drift`, and the annotator receives an already-built summary.

**It must never touch `bucket`, `real_fields`, or `has_drift`.** This is not
style. `DriftField.bucket` already carries a *suppressing* value — ADR-0047's
`demo_set` is excluded from `DriftReport.real_fields`, which `has_drift` and
every badge count key off. Expressing attribution through `bucket` would
silently change drift state. Hence a separate key.

### 2. A matched row is still drift

> An ADMZ-originated write and a later on-device edit can touch the same rule.
> The audit row records the tool **arguments**, never the resulting config, so
> there is nothing to compare the live value against. A matched row proves ADMZ
> wrote to that rule **once**; it proves nothing about whether the current value
> is what ADMZ wrote. Auto-accepting on a match would hide the second edit, and
> nothing downstream could recover it.

So a matched row keeps its place in the table, its checkbox, and its
accept/revert affordances, and still counts toward `has_drift`. The UI copy is
**provenance, not verdict**, and the hedge is in the operator-facing sentence —
not only in this document.

This mirrors ADR-0055's rule for `normalize_doc` from the other direction: there,
only *provable* equivalences may be collapsed. Here, no amount of audit evidence
collapses anything at all.

### 3. Below `to_summary()`, so both surfaces get it

Applied by the REST route (`/api/snapshot/drift`) *and* the MCP `check_drift`
tool. The chat surface is where an operator most often meets a drift report;
leaving it blind would be the worse default.

Deliberately **not** written into the cached payload
(`drift_alerts.store_report`). A report cached before its audit row landed would
otherwise never gain attribution, and a stale cache would pin a stale
attribution forever. Fleet paths are not annotated, matching the existing
`_annotate_revertable` precedent (one audit query per device is the wrong cost
for a fleet rollup).

### 4. Three strengths of match, each labelled with its own hedge

`audit_log` has no device column — device identity lives in `resource`
(`mcp:create_action_rule/device:<id>`) or in `details_json` (`scenario_*` puts
device ids in `details.applied`). `AuditLog.search(device=, action=)` already
covers both with a LIKE, so **no schema change and no new query were needed**.

| match | key | availability |
|---|---|---|
| `rule_id` (`exact`) | `details.rule_id` / `details.args.rule_id` | deletes today; creates once #230 PR 2 lands |
| `rule_name` (`correlated`) | `details.args.rule_name` ↔ the live `<rid>.name` drift row | **the only retroactive key** |
| `device` (`correlated`) | device + time only | always |

The create path currently **discards the rule id**: `rules/runner.py` extracts
`RuleID`, `operations.py` returns it, and `api/routes/confirm.py` reads only
`success`/`error` off that envelope. Attribution reads the field
opportunistically, so PR 2 upgrades existing matches from `correlated` to
`exact` with no change here.

Two wrinkles are stated in the UI copy rather than papered over:

- `mcp.create_action_rule` rows are recorded with `success=0` **by design** —
  that tool opens a confirmation session, it does not write. The row is an
  *intent*.
- The approver is on a **separate** `confirm.approve` row carrying no rule id or
  name. It is correlated by device and time within a 15-minute window, and
  labelled as correlated.

Name matching is knowingly imprecise: names are neither unique nor stable under
an on-device rename. It ships anyway because it is the only thing that
attributes the operator's *actual* evidence today, and because implying more
precision than the evidence supports is the worse failure. The label says so.

### 5. Grouping is display-layer only — the flatten is not lossy

`flatten()` joins path segments with dots, and `ActionRulesFacet.serialize` keys
the doc by rule id, so the leading segment of `175.actionConfig.actionParameters`
**is** the rule. The id survives verbatim into `DriftField.path` and
`canonical_key`, through `to_summary()`, the SQLite cache and into the DOM. No
backend change, no re-probe, no cache migration.

Grouping is applied in `index.html`'s `catOf` **and in the read-only block**,
because that is where every rule row actually lands.

A group header shows a name only when a `<rid>.name` row exists — true for a
wholesale add or delete, false when only `enabled` changed. Those degrade to a
bare "Rule 175". Always recovering the name means reading the nested doc
(`check_drift` still has `live_by_facet` in scope), which is a backend change and
deliberately out of scope.

## Consequences

- The C1710's report reads *"36 read-only observed changes (not revertable) ·
  across 3 rules"*, expanding to three named rule groups, each row chipped with
  when ADMZ wrote it and who asked.
- Attribution is defensive: a raising audit store logs and leaves the report
  unannotated rather than breaking drift for the device (mirroring how
  `drift.py` calls a facet normaliser).
- **Not done here, deliberately:** rendering a rule's condition in English. The
  vocabulary exists in the atlas YAML (`EventCondition.label`,
  `SoapParam.ui_label`, invertible `ui_to_soap`), and on AXIS OS ≥ 12 the facet
  doc *does* carry the input — `activationConfig.condition[].topicExpression` and
  `actionConfig.template` + `actionParameters`. What does not exist is a
  topic→condition reverse index or a renderer for a rule read back off a device
  (`rules/runner.py::parse_rules` keeps only `{rule_id, name, enabled,
  primary_action}`). `rules/capabilities.py::describe_rule` is forward-only — it
  needs the ids ADMZ chose at create time and ignores `resolved_params`, so it
  cannot say *"display 'Welcome'"*. That is a separate issue, and its coverage is
  per-model (7 surveys), so it needs a stated fallback for unsurveyed models.
- A "hide attributed rows" filter would be acceptable **only** as an
  operator-driven, default-off toggle. An automatic one is the thing this ADR
  exists to prevent.
