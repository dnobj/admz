# ADR-0047 — Demo-owned config fragments (composition + attribution)

**Status:** Accepted (2026-07-16). Slices 1–2 (capture + attribution) shipped;
activation pushes and later slices staged below.
**Relates to:** ADR-0046 (demos — this replaces its `config_source` idea as the
config model), ADR-0044 (scenarios — become the legacy whole-config case),
ADR-0031 (baseline_sha / drift), ADR-0034 (widget-gated pushes).

## Context

ADR-0046 modelled a demo's config as a *reference*: `baseline` or
`scenario:<name>`. The operator pushed back on both halves of that:

> "Maybe demos involve a certain collection of devices and configs and not some
> universal baseline. And that config is either active or it's not. I guess how
> do we know if a config is drifted or if it is deliberately changed for
> another demo?"

That last question is the crux. Drift today is one bucket: *live ≠ baseline*.
But in an experience center a difference has **four** meanings — an active demo
set it (deliberate), an active demo needs it and it's wrong (the demo is
broken), an inactive demo's config was loaded by hand (recognize it), or nobody
claims it (true drift). A whole-config model can't distinguish them because
config *ownership* is all-or-nothing per device. Also from the operator's
requirements: demos can be **defined but not active**; devices are **fungible
fulfillers** (swap on failure/upgrade); some demo needs are **software**
(ACS Pro, Audio Manager Pro) or **prose** (manual checklist).

## Decision

**A demo owns a sparse config *fragment* — just the keys that make it work —
layered over each device's base. Expected state = base ⊕ every active demo's
owned keys. Every differing key is then *attributable*.**

### The layers

- **Base** (unchanged): per-device `baseline_sha` owns every key no demo claims
  — the housekeeping layer (network, time, users). ADR-0046's "baseline demo"
  survives as the empty-fragment demo.
- **Fragment**: per demo, per **role**, in the config repo —
  `demos/<demo_id>/roles/<role>.yaml`:

  ```yaml
  demo_name: Loitering detection    # breadcrumb; the id is the key
  facets:
    other:
      set:                          # owned: pushed (slice 3) + attributed
        Motion.M0.Enabled: "yes"
      require:                      # asserted at readiness, never pushed
        Audio.A0.Enabled: "yes"
  ```

  Values are the **flattened strings** drift compares (`snapshot/flatten.py`)
  so they round-trip exactly. Fragments are keyed by role, not device —
  that's what makes hardware swap a *rebind* instead of a re-capture.
- **Activation state** (`demos.active`, DB): intent, not fact. **Adopt** marks
  a demo active *without pushing anything* — its keys join expected state on
  the next drift check. Deactivate stops claiming them (the config stays on
  the devices; the keys read as plain drift again, revertable to base).

### Attribution — the answer to "drifted or deliberate?"

Each drift check computes, per device, the owned-key map of active demos and
the fragments of inactive ones (`demos/fragments.py::attribution_maps`), then
buckets every differing key (`DriftField.bucket`, `snapshot/drift.py`):

| bucket | meaning | counted as drift? | action |
|---|---|---|---|
| `demo_set` | matches an active demo's owned value | **no** — deliberate | deactivate the demo to undo |
| `demo_broken` | owned by an active demo, live differs (incl. not-yet-loaded) | yes — *against the demo*; `expected` = the **demo's** value, so revert **repairs** the demo | revert |
| `candidate` | matches ≥1 *inactive* demo's fragment — "looks like demo Y" | yes | adopt Y (no push) or revert |
| `unclaimed` | nobody claims it | yes | revert / accept / **assign-to-demo** |

`DriftReport.fields` keeps ALL rows (annotated, never dropped);
`real_fields`/`has_drift` exclude `demo_set`, and the cached
`drift_signatures.field_count` becomes the **real-drift count** — so a device
fully explained by its active demos reads *in sync* on the roster. The full
per-bucket breakdown (incl. `by_demo` broken counts) rides in a new
`attributed` JSON column, and the signature hash includes bucket+owner so an
adopt/deactivate registers as exactly one deliberate alert transition.

### Capture, not authoring

Fragments are built from observed reality: set the device up for the demo, run
a drift check, tick rows in the diff, **"Assign to a demo"** (a fourth
disposition beside Accept / Revert / Exclude). The server re-checks drift and
records the **actual live values** — the operator configured the device the way
the demo needs it, so the live side *is* the demo's config. Capturing from a
device implicitly binds it (records its role, pulls it into scope).

### Guards (each closes a hole found in adversarial design review)

1. **Accept-baseline guard (non-negotiable).** Observations contain live state
   = demo-set values included. Accepting while an active demo owns keys would
   silently bake the demo's config into base — after which deactivation pushes
   nothing and the demo config survives forever, labelled "baseline". Single
   accept → 409 naming the demos; bulk accept → skip-and-report.
2. **No same-key overlap between active demos, even equal values** (409 at
   adopt, naming the holder). Makes future deactivation trivially "push base";
   key-level exclusivity still beats ADR-0046's whole-device "on loan".
3. **`set` only for param-writable keys already present in the baseline *and*
   still present on the device** — `param.cgi` cannot create or delete keys, so
   a fragment overrides, never invents and never removes. API whole-object
   facets (NTP/SIP) and snapshot-only facets are `require`-only. Enforced at
   capture, **both directions**: `expected == "<missing>"` → refused
   `not-in-baseline` (would create), `actual == "<missing>"` → refused
   `vanished-from-device` (would remove — and, once adopted, would suppress
   that key's drift forever, since attribution then matches `want ==
   "<missing>"` exactly while the key stays deleted). Only the first half was
   implemented until #208; the rationale here always covered both.
4. **Ignored keys can't be assigned**, and an ignore rule added *after* capture
   makes the key invisible to attribution too (never a false "demo broken").
5. **Device-local values warn**: fragment values embedding the device's own
   IP/hostname/MAC/serial are flagged at capture — unsafe to carry to a
   swapped-in device. No templating in v1.
6. **Legacy partition**: a device with `active_scenario` set keeps ADR-0044
   semantics untouched — no overlay, no adopt (409) — until its scenario ends.
   The two models coexist, partitioned by device, until migration.
7. **Whole-device revert excludes `demo_set` rows** — reverting "everything"
   must not silently kick an active demo off its keys.

## Consequences

- The drifted-vs-deliberate question has a mechanical answer: intent is
  recorded *before* the difference exists (capture + adopt), so the drift
  report can attribute rather than guess. Even out-of-band demo setups get
  recognized ("looks like demo Y") because inactive fragments are matched too.
- Demo configs get git history, diffs, and review like device snapshots — the
  operator's "track configurations built on git just like what we have now".
- Multiple demos coexist on a device up to key conflicts, not whole devices.
- A demo delete removes its fragments from the working tree; history keeps them.

## Staged follow-ons (not yet built)

- **Slice 3 — activation pushes**: Prepare = synthetic DriftFields
  (expected=fragment value) → `build_targeted_revert_plan` → the existing
  gated plan; deactivate-with-restore pushes base values for owned keys only.
  Activation state must transition on plan *completion* (also fixes the
  pre-existing scenario marker-timing bug, chip task_7f8c285b).
- **Slice 4 — readiness v2**: per-demo verdicts from the attributed cache;
  `require` checked against the latest observation (not base — a live-broken
  requirement must not read ready); software requirements
  (`{kind: software, module: acs_pro}` → reuse `/api/acs/test` + MAC
  correlation); manual checklist with ack (advisory amber).
- **Slice 5 — scenario migration**: per-(device, scenario) reviewable
  converter (writable diff → `set`, non-writable → `require`/dropped with
  notice); retire `in_scenario`/on-loan only when nothing legacy remains.
- **Slice 6 — swap ergonomics**: rebind = validate fragment keys against the
  new device's observation + device-local review + gated push.

## Deferred (named)

- Key creation/deletion in fragments (no `param.cgi:add` op exists); "must be
  absent" assertions; whole-object fragments for NTP/SIP.
- Templating / per-device value substitution (warn instead).
- Fragment sha pinning at activation (read HEAD; surface "fragment changed
  since activation" later).
- Ranked adopt suggestions (the per-key candidate annotation is kept; adopt is
  a manual demo-level action).
