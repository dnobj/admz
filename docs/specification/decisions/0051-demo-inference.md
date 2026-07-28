# ADR-0051 — Infer the demos that already exist: deterministic collection, agent narration

**Status:** Accepted (2026-07-28). Closes issue #124 (PRs #129, #130, #135 and
the narration slice). Implementation plan: `docs/plans/demo-inference.md`.
(Numbering note: 0051 was reserved for this feature while both plans were open;
the advanced-switches work in #132 takes **0052**.)
**Relates to:** ADR-0046 (demos — what a confirmed proposal becomes), ADR-0047
(demo config fragments — the keys a proposal *suggests* but never writes),
ADR-0050 (demo setup wizard — the `next_actions` a fresh demo inherits),
ADR-0040 (ACS Pro module — the read-only rule source), ADR-0041 (event layers;
this supplies Layer 4's per-rule observability report), ADR-0039 (module-gated
prompt sections — the pattern the narration section reuses).

## Context

ADMZ arrives in an experience centre that **already runs demos**. Asking the
operator to re-describe an inventory the environment already encodes is the
wrong first impression, and the encoding really is there: device tags, installed
analytics apps, device-side action rules, and — where ACS Pro is connected — a
server full of action rules naming devices, topics and actions.

Nothing existing infers over that. `modules/acs_pro/correlate.py` joins a device
to its ACS cameras (a primitive, not an inference), and `attach_rule_to_demo`
(`demos/actions.py:290-336`) is bookkeeping over a rule ADMZ *just created*. The
new work is the collection orchestration, the clustering, and the confirmation
experience.

The operator settled the shape on 2026-07-22, and the reason matters for
everything below: *working out how device and ACS configuration flows up into a
"demo" will almost certainly require LLM review.* So the machine must do the
part it can defend — gathering and scoring — and the model the part it is
actually good at: reading the evidence and saying what the thing is.

## Decision

**Collect and score deterministically; let the agent interpret on top; write
nothing until a human confirms.** Every proposal carries the exact edges,
weights, score terms and evidence strings that produced it, so a narrated guess
can always be checked against the machine's reasoning.

### 1. Proposals live in their own table, never in `demos`

`demo_inference_runs` (provenance + the full evidence graph + the constants in
force for that run) and `demo_proposals` (one candidate demo) are separate
SQLite tables. This is not tidiness. Anything in `demos` is enumerated by
`list_demos`, rendered on `/demos`, rolled into readiness and — decisively —
walked by `fragments.attribution_maps` (`demos/fragments.py:213-252`) on **every
drift check**. A half-believed guess must never participate in drift
attribution. A demo comes into existence only through `confirm_demo_proposal`,
which composes the *existing* `create_demo_core` + `attach_rule_to_demo`.

Proposal ids are content-derived — `sha1(run_id + sorted member ids)` for the
row, `sha1(sorted member ids)` for a run-stable `content_key`. Re-running over
an unchanged environment reproduces the same grouping; the previous run's row is
marked `superseded`, and a member set the operator already **confirmed or
dismissed** is not proposed again.

### 2. The scoring contract is published, not implied

```
score = 0.40 · topology_cohesion + 0.25 · rule_density
      + 0.10 · name_cohesion     + 0.10 · tag_cohesion
      + 0.15 · firing_recency
```

Every term is returned with its weight, value, contribution and a human detail
string; every constant is echoed into the run's `params_json` so an old proposal
stays explainable after the weights are tuned. `confidence` is
`high ≥ 0.70 | medium ≥ 0.45 | low`, then **capped**: a cluster with no topology
edge is capped at `low` and flagged `no_topology`. Firing recency is best-effort
and degrades to 0 with a `firing_unknown` flag, so "we did not look" is never
rendered as "it has not fired".

### 3. Two live findings shaped the algorithm

Both came from running against the reference fleet, and neither was in the plan.

- **There is zero rule-expressed device-to-device topology.** Every ACS rule on
  the fleet triggers *and* acts on the same device — the door-station cluster
  calls itself, *Alert on SFH* records the camera that detected. The signal the
  plan assumed would dominate (weight 1.00) produced **nothing**. So
  `include_weak` defaults to **True** and the policy is *surface, flag and cap*
  rather than hide: defaulting it False would return an empty list on exactly
  the flagship "ADMZ already knows your demos" moment. The operator's own
  suggestion — installed ACAPs as an edge, self-calibrated by inverse frequency
  — became the dominant signal (7 of 10 edges).
- **Corroborating evidence does not chain.** Topology is relational: "this rule
  triggers on A and acts on B" is a fact *about the pair*, so A→B→C really is
  one mechanism. Corroboration is not — "A and B both run objectanalytics" and
  "B and C both run AudioManagerPro" say nothing whatsoever about A and C, yet
  connected components chain them happily. Live, six of eleven devices merged
  into one blob through that accident, swallowing the one grouping a human would
  name. Hence `DENSITY_MIN_CORROBORATING = 0.60` (a group with no relational
  evidence must be a group *pairwise*, not a chain) and `OVERLAP_MIN_LINKS = 2`
  (one link back into a part is the coincidence the split just rejected; two
  means genuinely embedded). Both are named constants in `params()`, tunable
  without touching logic.

### 4. Confirmation is chat-driven; the deterministic name is only a fallback

No wizard *page* exists to extend (ADR-0050 is a checklist function, not a
template), and a static form is the wrong host for reasoning that needs
explaining. So review happens in the console, with the agent walking each
proposal's evidence.

The deterministic name — top shared name token plus a role hint — is **always
stored**, so the whole feature works with the model switched off. It is a
serviceable placeholder and no more: the reference fleet's two-speaker demo
(linked by a `#speakers` tag, `AudioManagerPro`, and shared rule-name tokens)
comes back as *"Activation demo"*. `confirm_demo_proposal` therefore takes
optional `name` and `purpose` (plus `device_ids` / `roles` / `tag`), and the
chatbot prompt gains a section — gated off exactly like a module's, absent
unless ACS is connected or a run/open proposal exists — teaching the agent to
narrate from the evidence the proposal already carries: member roles, each
rule's topics, action kinds and firing-observability verdict, the term-by-term
breakdown, the weighted evidence strings, `suggested_owned_keys` with reasons,
the flags and the overlaps. **No second collection pass**: a follow-up question
is answered by re-reading, not by re-running a full site read.

### 5. Suggested keys are evidence; confirm writes no fragments

Auto-capture is not merely undesirable, it is mechanically impossible on the
flagship path: capture only accepts keys that are **currently drifted**
(`demos/actions.py:179` skips `not-drifted`; `fragments.py:177-180` refuses
`not-in-baseline`), and at first run the baseline is snapshotted *from* live
state — live equals baseline, zero drift, nothing capturable. So a proposal
carries `suggested_owned_keys[]` with a reason per entry (and a
`not_capturable` flag where `validate_assignment` would refuse), and confirm
creates the demo with an **empty fragment set**. That is also why confirm stays
ungated: it writes metadata, leaves `active` False, touches no device and issues
no ACS write, so `attribution_maps` sees nothing new on the next drift check.

### 6. The run is operator-invoked, at any time

No first-run concept exists in ADMZ, and restricting inference to first install
would mean *building* an install-state flag purely to disable a capability. An
explicit run (button, endpoint, tool) covers the first-install moment naturally.
Two modes: **fast** (registry + last snapshots + a live ACS read; seconds, works
with the fleet offline) and **deep survey** (discover → onboard → snapshot →
infer) as a background job with progress.

## Consequences

- The flagship moment works on a fleet with no cross-device topology at all —
  but every proposal there is honestly labelled `no_topology` and capped at
  `low`, and the agent is required to explain *that*, not recite a score.
- Proposal quality now has two independent failure modes, deliberately: the
  clustering can group wrongly (visible in the evidence) and the narration can
  name wrongly (visible beside the deterministic name). Neither can silently
  create a demo.
- Inference surfaces registry gaps as a side effect — a device present in ACS
  but absent from ADMZ lands in `unattached_rules[]` with an
  `unregistered_device` flag rather than being dropped.
- Every proposal carries a per-rule firing-observability verdict, including the
  `blind` count. That is the #127 hand-off, and it makes "is this demo running?"
  answerable-or-not *before* the demo exists.
- `demos` is untouched: no schema change, no migration. Rule membership gained a
  JSON `source` field (`device` | `acs`) so `wizard._rules_status` reports an
  ACS rule as `observed: None` rather than as a device rule that vanished.
- Rollback is dropping two tables; nothing else references them.

## Out of scope (named, not hidden)

- **Automatic re-inference.** v1 is operator-invoked. `superseded` and the
  dismissal memory are in the model so the #122 attention-surface use case is
  cheap later.
- **Remediating a `blind` rule.** Instrumenting a rule with an extra alarm or
  HTTP-notify action is a *write* to ACS and belongs to #127. This ADR only
  reports the verdict.
- **Custom console widgets for a proposal card**, and a `/demos` "Proposed
  demos" section beyond the cards slice 3 already renders. The resolved UX is
  chat-driven; richer surfaces are a later refinement.
- **Where demo topology actually lives**, given the rules do not express it.
  Candidates for a future edge type: AudioManagerPro zones/sources, device-side
  rules with HTTP/SIP actions targeting another device, or demos that simply are
  not automated device-to-device at all.

## Rollout

Four merged slices on `master`: the ACS rule-anatomy reader (#129), the evidence
graph + run store (#130), clustering + proposals + confirm (#135), and the agent
narration surface + this ADR. Both tables are created idempotently by their
store's `_ensure_table`; there is no backfill and nothing to migrate. Collection
is read-only throughout — no VAPIX write, no ACS write, and the live Firebird
`.FDB` is never opened.
