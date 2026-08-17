# ADR-0062 — A plan approval is an envelope, not a step list

**Status:** Proposed (2026-08-17). Closes the decision half of #440.
**Relates to:** ADR-0034 (confirmation gates — the level this reuses), FR-PLN-005
(mechanical gate by aggregate risk — the existing implementation), FR-PLN-007
(multi-level confirmation), NFR-PLN-002 (approvals are single-use), #439
(`condition:` — the cheap adaptivity this deliberately keeps separate), #438 (the
chat never plans, which is the same problem from the other side).

## Context

The operator asked for a console mode where the chat model plans a multi-step
goal, gets approval **once at the start for everything it will do**, then
executes — with the plan able to change if reality differs.

The first two are already built. The third is in tension with the second, and
that tension is the whole subject of this ADR.

### What already exists

`admz/plans/` is not a sketch. Twelve requirements are implemented, `run_plan`
executes steps through `operations.run_execution_tail` — the same tail a single
operation takes — and `operations.execute_gated_plan` computes the strictest
confirmation level across all steps and gates once. `NFR-PLN-002` makes that
approval single-use.

So ADMZ already implements the strong form of plan-then-execute, including the
up-front aggregate approval.

### Why replanning breaks it

The security property that makes plan-then-execute worth having is
**control-flow integrity**: untrusted content may influence data flow, but it
cannot hijack the *sequence*, because the sequence is fixed before untrusted
input is touched. An operator approving a plan is approving that fixed sequence.

Replanning removes precisely that. A plan that can change after approval means
the operator approved a plan that no longer exists — and the thing most likely
to *cause* a replan is a device response, which is exactly the untrusted input
the property is supposed to contain.

This is not a hypothetical concern in this codebase. `#160` was ADMZ relaying a
service account's Windows credentials to a caller-chosen host; `#162` was option
injection through a git ref. Device and caller input steering behaviour is the
recurring shape here, not an abstract risk.

### Why "just re-approve each change" is not the answer

It is correct and it is unusable. A discover-then-act plan across eleven devices
will replan whenever a read comes back differently from one of them. An operator
prompted eleven times stops reading the prompts, which is the failure ADR-0034
already names: a gate that fires constantly trains people to clear it.

## Decision

**An approval authorises an envelope, not a list of steps.**

The envelope is:

| Field | Meaning |
|---|---|
| **device set** | the exact device ids the plan may touch |
| **risk ceiling** | the strictest `risk_level` any step may carry — the value `execute_gated_plan` already computes |
| **operation set** | the catalog operation ids the plan may call |

Execution inside the envelope needs no further approval. **Any step outside it
stops the plan and re-gates** — it does not silently drop the step, and it does
not proceed with the rest.

**An envelope may only ever narrow.** A replan may drop devices, drop
operations, or lower risk. It may never widen any of the three without a new
approval. Narrow-only is the property that makes the envelope reviewable: an
operator who approved it knows the true blast radius is *at most* what they saw.

### Why ADMZ can do this honestly

Most systems proposing "approve the capability, not the steps" cannot say
precisely what was approved. ADMZ can: the atlas carries `risk_level` per
operation, `_DEFAULT_CONFIRMATION_LEVELS` maps risk to gate level, and the
aggregate is already computed today. The envelope is **derived from data the
system already has**, not a new abstraction someone has to maintain.

### What the operator sees

The approval widget shows the envelope **as an envelope**, never as a step list
that happens to be current:

> *This plan may run **firmware upgrade** and **reboot** on **11 devices**.
> Highest risk: **service-affecting**. Steps may change as it learns what each
> device needs; it can only do less than this, never more.*

That last clause is the load-bearing one. Approving "up to X on these devices" is
a different act from approving eleven named operations, and the widget must not
let the first look like the second. If an operator reads a step list and the
steps then change, the interface lied — even if the envelope held.

## What this does not change

- **`condition:` (#439) stays outside this.** A conditional step is already *in*
  the approved plan; evaluating it narrows what runs. That needs no envelope
  machinery and should ship independently — it is the cheap case and conflating
  the two would delay it behind this decision.
- **Single-operation gating is untouched.** ADR-0034 continues to govern one-off
  operations; nothing here creates a second path to an ungated write.
- **Approvals stay single-use.** An envelope is consumed by one plan run, not
  held open as a standing permission. A standing envelope is a different and much
  larger decision, and this ADR does not make it.

## Consequences

**The audit record must show both.** Today one `confirm.approve` row covers a
plan. With replanning, the log has to carry what was *approved* and what actually
*ran* — otherwise it answers the wrong question, and the 2026-08-16 audit read
showed how much weight that log carries when something goes wrong.

**A replan is an event, not a detail.** Every replan is recorded with what
changed and why. A plan that quietly rewrote itself four times and stayed inside
its envelope is technically compliant and operationally alarming; the record
should make that visible rather than merely permissible.

**Narrow-only has a cost, and it is the right cost.** A plan that discovers it
needs one operation nobody anticipated will stop and ask, even though continuing
would have been fine. That is the trade being made deliberately: the alternative
is an approval whose meaning depends on what the fleet said afterwards.

**This does not make the chat plan.** #438 is a separate defect — the tool's
description gives no trigger, and its contract demands fully-parameterised steps
up front, which most multi-step goals cannot supply. An envelope makes
*replanning* legitimate; it does not make the model reach for planning in the
first place. Shipping this without #438 changes nothing an operator would notice.

## What would falsify this

If envelopes turn out to be either always-exact (every plan runs precisely the
steps first proposed) or always-violated (nearly every plan re-gates), the
abstraction is not earning its keep. The signal is the **replan-that-stayed-inside
rate**: if it is near zero, a step list was sufficient and this is ceremony; if
re-gating is constant, the envelope is drawn too tight and operators are being
prompted as much as before, with more machinery. Worth measuring after twenty
plans rather than assuming.
