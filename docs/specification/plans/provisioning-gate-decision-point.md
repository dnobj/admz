# Plan: move the provisioning gate to the decision point (ADR-0059)

Status: **implemented** (2026-08-09; slices #361, #363, #364) — the decision is made
([ADR-0059](../decisions/0059-gate-provisioning-at-the-decision-point.md),
adopted by the owner 2026-08-07 via `q_f66d6e50`); this is how to build it.
Anchors: [#199](https://github.com/dnobj/admz/issues/199) item 3,
[#193](https://github.com/dnobj/admz/issues/193)'s gate half.

The ADR argues *why* and names its own costs honestly. This plan settles the
things it deliberately left to implementation, corrects its caller table against
current master, and slices the work so the fail-open hazard is landed with its
tests rather than after them.

## What the ADR left open, and what this plan answers

| ADR left open | Answer here |
|---|---|
| Does the blocked envelope carry the device id alone, or discovered metadata? | **Device id + host only.** §4 |
| Should `_register_device` / `onboard_device` surface the approval link themselves, or pass the envelope up? | **Pass it up unchanged**, one shape for all callers. §4 |
| What the audit row names | Device, host, and password **source** — never the password (#199 item 2 precedent). §5 |

## 1. The caller inventory is not what the ADR says

The ADR's table lists five rows and was written 2026-08-05. Verified against
`origin/master` today, `onboard_device_credentials` has **four call sites**:

| # | call site | reachable by | approved already? |
|---|---|---|---|
| 1 | `api/routes/devices.py:167` `_run_onboarding` ← `POST /api/devices`, `POST /api/devices/{id}/onboard` | operator (REST) | no |
| 2 | `mcp/server.py:2164` `_onboard_device` ← MCP `onboard_device`, and `register_device` routes through the same handler | **model** | no |
| 3 | `demos/inference/collect.py:498` — the deep survey | operator/model | **yes** (gated at the route, #299) |
| 4 | `operations.py:890` `_action_register_discovered_device` — the approval executor | post-approval | **yes** (it *is* the approval) |

The ADR counted `register_device` and `onboard_device` as separate rows; they
reach the same handler, so there are three functions to update, not four. Rows 3
and 4 are the ones that must **not** re-gate — the reason the context token
exists.

Also worth stating because it is the fact the whole decision rests on, and it
should be re-verified before writing code rather than trusted from here:
**`tasks/handlers.py::_run_reprovision` calls `provision_factory_default`
directly and never routes through `onboard_device_credentials`.** If that ever
stops being true, this design gates the scheduler, which cannot approve
anything, and the plan is wrong. Re-check it as step 0.

## 2. Where the gate goes

Inside `onboard_device_credentials`, in the `if ready and ready.get("needsetup")`
branch at `admz/onboarding.py:133`, **immediately before**
`provision_factory_default` — not at function entry.

This is forced, not stylistic: whether provisioning will happen is not knowable
without contacting the device (`read_systemready` decides it). A gate at entry
would fire on every device add. By the branch, four things have happened and all
four are **reads** — TCP probe, registry lookup, `_confirm_credentials`,
`read_systemready` — so nothing has been written when the widget is raised.

Paths that must keep never gating, each of which returns earlier:
`ALREADY_CREDENTIALED`, the unreachable `CREDENTIALS_NEEDED`, and the
fleet-pair / capture branches.

## 3. The approved-context module

New `admz/approval_context.py`: a `ContextVar`, a `@contextmanager
approved(action, token)` that sets and **resets in `finally`**, and
**`is_approved_for(*actions)`** as the gating predicate.

> **Amended after slice 1's review (#361).** The ADR specified a bare
> `is_approved()`, and that is not safe: the marker would be established for
> every approved action, so approving a task creation or a rule delete would
> have been sufficient authority to provision. **Approval for X is not approval
> for Y.** Two changes followed — only `operations._PROVISIONING_APPROVAL_ACTIONS`
> (`start_demo_survey`, `register_discovered_device`) establishes the marker at
> all, and the gate must ask `is_approved_for(...)` naming those actions.
> `is_approved()` still exists for audit and debugging and is documented as
> not-for-gating.
>
> Also recorded there: a task spawned inside an approval keeps it for the task's
> whole life, because `create_task` copies the context and the parent cannot
> revoke the copy. The survey needs exactly that; it is a hazard for any other
> detached task, bounded by the two-action list above.

> **The fail-open hazard is the whole risk of this change.** A token set and
> never reset marks every later call on that task approved: the gate stops
> existing, and nothing raises or logs. Two structural rules, both testable:
>
> 1. `_APPROVED.set()` appears **nowhere** outside the context manager. A test
>    greps the tree for it, in the spirit of the existing mock-faithfulness and
>    setting-policy lints — a static check because the dynamic one cannot see a
>    leak that only happens on a path no test takes.
> 2. The marker is cleared after `execute_approved_session` returns,
>    **including when it raises**. Both directions get a test.

`operations.execute_approved_session` wraps its dispatch in
`with approved(action, token):` — but only for the two actions listed above. `asyncio.create_task` copies the current context, so
the survey's background task inherits it for its whole life — which is the
correct semantics: the operator approved *that survey*, including the devices it
provisions.

## 4. The new terminal status

`onboard_device_credentials` gains `APPROVAL_REQUIRED` and returns the standard
blocked envelope from `discovery/gated.py::gate_scan_write` — the same shape a
gated VAPIX op returns, so the UI and chat already know how to render it.

**Envelope contents: device id and host, nothing else.** The ADR wondered about
including discovered metadata; the answer is no. The operator is approving "may
ADMZ create a root account on this device", and the device's own advertised
metadata is attacker-supplied on precisely the factory-default unit in question
(#193 is the sibling issue about trusting an unauthenticated device claim).
Extra fields would add nothing to the decision and would put unverified strings
on the approval card.

**All three callers pass the envelope up unchanged.** No caller re-wraps or
re-words it. The reason is the failure this ADR exists to fix: three callers
each formatting their own approval message is three places to drift.

Each caller's obligation is therefore only to *not swallow it*:

- `_run_onboarding` (REST) already returns the status dict to the route; it must
  stop treating unknown statuses as failure and pass `capture_url`-style
  approval fields through, the way it already does for `CREDENTIALS_NEEDED`.
- `_onboard_device` (MCP) returns the dict to the model; the blocked envelope is
  already the shape the model is trained on for gated ops.
- The survey and the approval executor never see it — `is_approved_for(...)`
  is true for both.

**Fail-closed if a caller is missed**: an unhandled status reads as "not
provisioned", which is safe and merely confusing. That is the ADR's stated cost
and it does not change.

## 5. Audit

One row when the gate fires and one when an approved provisioning proceeds. The
approved row names **device, host, and password *source*** (`fleet_default` vs
`generated`) — never the password. That is the #199 item-2 precedent, and it is
the same rule that #351 and #355 have since reinforced: an audit row records
attribution, never a second copy of a secret.

## 6. Slices

Deliberately three PRs, because slice 1 carries the hazard and should not land
buried in caller churn.

**Slice 1 — the mechanism, unused.** `admz/approval_context.py`, plus the
`with approved(action):` wrap in `execute_approved_session`, plus both hazard
tests (reset on return, reset on raise) and the static no-bare-`set()` lint.
Nothing consults the marker yet, so behaviour is unchanged and the risky
part is reviewable on its own.

**Slice 2 — the gate.** The `APPROVAL_REQUIRED` status and the
`gate_scan_write` call at the `needsetup` branch, plus the caller updates and
the audit rows. This is the behaviour change.

**Slice 3 — reconcile the entry-point gates and flip the ADR.**

> **Corrected during slice 3 (PR #364).** This slice originally said "remove the
> #299 gate from `discovery/gated.py`'s two call sites now that the chokepoint
> covers them". **That was wrong.** The chokepoint covers *provisioning*; those
> two gates approve a **scan blast radius** and a **registry write**, neither of
> which the chokepoint can express. And removing the survey gate would have been
> actively harmful: approving it is what establishes the approved context the
> background survey inherits, so ungating it would make the chokepoint fire once
> **per device**, from a background task, with nobody watching — the exact
> failure §3 exists to prevent. The instruction generalised from the ADR's
> argument without re-checking it against the approved-context section.

What slice 3 actually does: **keep both gates**, rewrite the superseded
*"Why the gate is here and not on `provision_factory_default`"* section to
describe the two-layer arrangement honestly, and flip ADR-0059
`Proposed → Accepted` — here, not in slice 1, because it is not accepted until
it is true.

Slices 2 and 3 could merge together; keep them apart if slice 2's review raises
anything, because deleting the old gate is the irreversible half.

## 7. Tests

Beyond the two hazard tests in §3:

- `needsetup=yes` + unapproved → `APPROVAL_REQUIRED`, and
  **`provision_factory_default` is never called** (spy on it; a status assertion
  alone would pass if the gate returned the right envelope *after* provisioning).
- `needsetup=yes` + `is_approved_for(...)` → provisions, no widget.
- `needsetup=yes` inside an approval for an UNRELATED action → still gates.
  (The authority-widening case slice 1's review caught.)
- Each non-provisioning path (`ALREADY_CREDENTIALED`, unreachable, fleet-pair,
  capture) → unchanged, no gate. One test each; this is the "operators do not
  notice" claim and it is the claim most likely to be wrong.
- The survey provisions N devices under **one** approval, not N widgets.
- `_run_reprovision` still reaches `provision_factory_default` with no gate —
  the scheduler regression test that makes step 0's fact permanent.

## 8. Out of scope, stated so it is not assumed

- **#313 is not closed.** `_create_temp_credentials` creates a device account
  without routing through `onboard_device_credentials`, so it is untouched.
- **`provision_factory_default` stays ungated**, for the reasons
  `discovery/gated.py` gives and the ADR preserves.
- **#199 item 3's other half** — decoupling registration from onboarding — is
  not this. `operations.py:872` says so in writing and deliberately keeps them
  together; changing that is its own decision.
