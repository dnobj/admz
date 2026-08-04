# ADR-0055 — Order-insensitive drift comparison (`normalize_doc`)

**Status:** Accepted (2026-08-04). Shipped with #215/#228.
**Relates to:** ADR-0031 (baseline_sha / drift), ADR-0043 (device event action
rules), the config-tracking ignore list (`admz/snapshot/ignore.py`).

## Context

Drift compares a facet's git-stored baseline against its live doc by
**flattening both to dotted keys and comparing the values as strings**
(`snapshot/flatten.py`, `snapshot/drift.py`). That is the right default: it is
cheap, total, and makes no assumptions about any facet's value semantics.

It reports a false positive whenever a value is *serialized* differently while
meaning the same thing. Observed live on the operator's fleet (#228): an action
rule's activation condition is an XPath expression whose top-level clauses are
joined by `and`. `and` is commutative, so

```
boolean(//SimpleItem[@Name="CallState" and @Value="Ringing"])
  and boolean(//SimpleItem[@Name="Source" and @Value="NetworkSpeaker"])
```

and the same two clauses the other way round are the same rule — but they are
different strings, so drift reports them as a change.

Two properties made this actively harmful rather than merely noisy:

- **It is unclearable.** The `action_rules` facet is read-only (no
  `build_revert_ops`, `write_ops == []`), so the only offered action is *accept
  baseline* — and the next reorder drifts again. On the C1110-E it was that
  device's *entire* drift.
- **It is self-inflicted and recurring.** A scenario round-trip
  (`scenario_activate` → `scenario_return`) rewrites the rule, and ADMZ's own
  writer emits the clauses in its order rather than the device's. So it
  reappears on every activation.

Noise of this kind buries real change — the same report contained a genuinely
new rule — and it is what trains an operator to stop reading drift reports.

## Decision

**1. Facets may declare a canonical form via `FacetAdapter.normalize_doc(doc)`.**
Default identity, so no existing facet changes. It must be pure, idempotent,
and must not add or drop fields.

**2. The drift detector applies it to BOTH sides** — the live doc *and* the
git-stored baseline — before flattening.

This second half is the whole point, and it mirrors what the ignore list
already does for the same reason (`drift.py`: applied to both sides "so an
excluded field vanishes from drift immediately, even if an older baseline still
holds it — no forced re-baseline"). Normalising only on capture would leave
every baseline already on disk drifting until an operator re-captured it: a
silent no-op dressed as a fix, and indistinguishable from the fix working.

Facets also call their own normaliser from `serialize`, so newly captured
baselines and the git config repo are written already-canonical and stop
churning. Comparison does not depend on that.

**3. Only provable equivalences may be collapsed.** A normaliser exists to
remove noise, never to interpret. The rule for what belongs here:

> If it is not *certainly* the same configuration, it must still report as
> drift. A false positive costs an operator one glance. A false negative hides
> a real change, and nothing downstream can recover it.

## Consequences

`ActionRulesFacet` is the first implementation. It recognises exactly one
shape — two or more top-level `and`-joined, individually balanced `boolean(...)`
calls — and returns everything else **verbatim** so it is still byte-compared.
Deliberately not recognised: `or` and mixed precedence, `not(...)`, `|` unions,
top-level parenthesised grouping, mixed-case `AND`, unbalanced quotes/brackets.

Two specific traps, both regression-tested:

- **Clauses sort as a multiset, never a set.** Under set semantics
  `A and A and B` equals `A and B`, so *dropping a duplicated clause* would
  become invisible.
- **Splitting is bracket- and quote-aware.** An XPath predicate legitimately
  contains `and` (`[@Name="CallState" and @Value="Ringing"]`). A naive
  `split(" and ")` shatters both sides into the same fragment multiset when
  values are swapped *across* clauses — turning a genuine change into "no
  drift".

Because a normaliser sits on the drift path, `drift.py` calls it defensively:
a raising normaliser logs and falls back to raw comparison rather than breaking
drift detection for the device.

### Known-exposed, deliberately not normalised

`flatten()` does not recurse into lists — it stringifies them — so **any**
list-valued facet field is order-sensitive by construction. Known cases:
`actionConfig.recipientParameters` and `actionConfig.actionParameters` (lists of
`{name, value}`), and the `activationConfig.condition` list itself. These are
left reporting as drift: no reorder has been observed, the transform is
different (sorting a name/value bag is not splitting a boolean expression), and
per the rule above an unproven equivalence stays visible. `normalize_doc` is the
seam to use if evidence appears — tracked as **#242**, which also records what
evidence would justify acting.

Tests pin the current behaviour for these, so relaxing it later is a deliberate
act rather than an accident.
