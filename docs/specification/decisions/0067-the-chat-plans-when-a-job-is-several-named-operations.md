# ADR-0067 — The chat plans when a job is several named catalog operations: discover the ids first, then take one approval for the batch

**Status:** Accepted — 2026-09-14
**Closes when shipped:** #438
**Relates to:** [ADR-0034](0034-uniform-widget-gating.md) (the gate a plan takes once, for the whole batch) · [ADR-0062](0062-approve-an-envelope-not-a-step-list.md) / #440 (what an approval authorises when a plan can change — still *Proposed*, and this is the half it says is missing) · [ADR-0005](0005-two-gate-plan-approval.md) / [ADR-0006](0006-multi-level-confirmation.md) (the existing plan gate) · #439 (`condition:`, the adaptivity this deliberately does not need) · #366 (a tool description that disagreed with its handler) · FR-PLN-005/006/012, FR-MCP-013, FR-FW-008

_Plan-first per `process.md`: this document merges before any code. File:line references are against master `456aa31`._

## Context

**The plans subsystem works and the chat essentially never uses it.** Measured on production: `mcp.create_plan` **4**, `mcp.execute_plan` **1**, against **53** `confirm.approve`. All four plan creations were on 2026-06-17 and all were fleet-wide reboot or factory-reset. Nothing since.

On 2026-09-14 an operator asked to upgrade a camera's firmware. The model ran it as a sequence of one-off gated operations — status read, download attempt, import — each with its own approval card, and then (for an unrelated reason, #444) stopped halfway. A firmware upgrade across a fleet is the textbook multi-write job the plan engine exists for, and `FR-FW-008` says so in as many words.

### Two causes, and the second is the larger

**1. The description has no trigger.** `admz/mcp/server.py:1095-1101` reads, verbatim:

> *"Create a multi-step execution plan for review. Submit a list of operations with concrete parameters. The plan is validated against the catalog and risk-classified. Returns a plan summary for the user to approve. Does NOT execute — call execute_plan after approval."*

Five sentences, every one describing *what the tool does*; none describing *the situation that calls for it*. A model selecting on that text reads "create a plan for review" as something to do **when the user asks for a plan**, not as the thing to reach for when a goal needs several writes. This is #366's finding in a second tool: the `description=` string is the artefact the model selects on, and it was written as documentation. The irony is one screen away — `get_device_health` (`:529`) *does* carry a trigger, and it tells the model when to plan.

**2. The stated contract is stricter than the real one.** *"Submit a list of operations with concrete parameters"* demands every step and every parameter up front. For a discover-then-act goal the model cannot supply that, so the tool as described is usable only where the work is already fully known and uniform — exactly the four June uses.

But the engine is **less** restrictive than its own description. `admz/plans/engine.py:97` reads `params` and never validates it: partial or empty params are accepted at creation. What it *does* hard-require is a real `operation_id` (`:99-105`) and a registered `device_id` (`:132-136`), and one failure of either raises `ValueError` that kills the whole plan (`:165-168`).

So the real precondition is **"know the ids"**, not **"know every parameter"** — and the description excludes far more work than the code does. Correcting that is the single highest-leverage change available, and it costs nothing.

### Why the prompt currently teaches the opposite

`admz/chatbot/system_prompt.py` mentions planning three times, all incidental. The strongest is a third "or" in a capability-discovery list at `:60-72` — a paragraph that names *firmware upgrade* and routes it to `execute_operation`. And `# Compound requests` (`:467-484`) actively teaches the opposite behaviour: enumerate the parts of a job and fire them **one gated call at a time, a card per part**. That is precisely the production behaviour. A trigger added to the tool alone would lose to it.

### What is already true, and worth not breaking

`execute_plan` is reachable from **seven** producers, only one of which is `create_plan` (`restore_device`, demo activation, scenario activation, the snapshot routes). That is why production shows `execute_plan` = 1 with `create_plan` = 4: the single execution came through the drift-revert path the prompt already teaches. **The working plan flow in production is the one where ADMZ builds the plan and the model only approves it.** The defect is confined to the model-authored path.

## Decision

### 1. The trigger lives in the description, because that is what the model selects on

`create_plan`'s description is rewritten to lead with the *situation*: a goal needing several device writes the model can already name — the same change across several devices, or an ordered sequence on one. It states the payoff explicitly — **one approval for the whole job, versus a confirmation card per step** — because without that clause the new trigger still loses to `# Compound requests`, which currently defines "finished" as a card per part.

It names the precondition as a **consequence, not an instruction**: every step needs a real catalog `operation_id` and a registered `device_id`, and **one unknown id rejects the whole plan and creates nothing**. A bare "look them up first" is the kind of instruction models skip; the consequence is what makes the ordering non-optional.

And it states the **anti-trigger**, because `PlanStep.condition` exists in the model and could otherwise be inferred to work: steps run in `depends_on` order but **no data passes between them**, and params are frozen at creation.

**No schema change.** `required: ["operation_id", "device_id", "params"]` stays — `params: {}` already satisfies it, so the shape the new description invites ("ids concrete, params possibly thin") is already legal.

### 2. Discover first, then plan — the boundary is mechanical, not a matter of taste

A "when to plan" rule joins the system prompt, and it is reconciled with `# Compound requests` rather than left to compete with it, by a fact about the schema:

> **A plan step is a catalog operation on a registered device, and nothing else.** ADMZ's own record tools — `create_demo`, `create_action_rule`, `assign_demo_fragment`, `queue_device_recovery`, `snapshot_device` — can never be plan steps.

That is derivable from the step schema (`additionalProperties: False`, `server.py:1165`), so the two sets are disjoint and neither rule can ever be the wrong answer for work the other covers. "Reboot eleven devices" is one plan; "create demo X that flashes the LED on motion" stays a compound request, because two of its three parts are not catalog operations.

The rule is inserted **between the end of `# Compound requests` and `# House style`** — verified as the only free seam: `tests/test_chatbot_system_prompt.py:264` and `:343` assert exact section adjacency, and `:264` is precisely the tripwire that catches the tempting-but-wrong placement immediately *before* `# Compound requests`. Both assertions stay armed and unedited; they are the control.

### 3. `execute_plan`'s description documents a branch that does not exist — fix it in the same breath

It currently promises a blocked-reason `plan_contains_dangerous_steps`. **That string exists nowhere in `admz/`.** The real reason is `plan_requires_confirmation` (`admz/operations.py:1629`), and only on the `llm_confirm` tier; the default `url_*` tier returns a `confirm_url` envelope (`:1636-1663`) the description never mentions. A model that starts planning, then reads that text, expects `confirm_dangerous=true` to carry a dangerous plan. It never will.

The replacement is keyed on **`confirmation_level`**, which both branches carry — not on `reason`, which is a slug on one branch and a sentence on the other.

**One coupled code fix comes with it.** `blocked_envelope` (`admz/operations.py:131-151`) already takes `is_plan` and branches on it for `reason` (`:137`) and `message` (`:149`), but sets `"confirm_tool": "confirm_dangerous_operation"` **unconditionally** (`:145`). So a `url_*` plan's envelope hands the model the exact tool the corrected description tells it will not work. Shipping a description that contradicts a field in its own payload would recreate #366 in miniature, so `confirm_tool` becomes conditional on `is_plan`.

### 4. The in-chat plan card must show the plan

This is the judgement call, and it goes in.

The whole purpose of this ADR is to make plans start appearing. The first artefact an operator meets when one does is `populateApprovalForm` (`admz/api/static/chat.js:547-599`), which renders `operation_id` and `device_id` only. For a plan those are `plan:plan-ab12…` and the literal string `"multiple"` (`operations.py:1641-1643`), with an empty `danger_description`. **`chat.js` contains zero occurrences of the string "plan".**

The data is already fetched and thrown away: `GET /api/chat/confirm/{token}` returns `is_plan` and `plan_summary` (`admz/api/routes/confirm.py:640-641`). So this is one branch mirroring the Jinja renderer that already exists at `admz/api/templates/confirm_form.html:81-153` — step count, risk badges, a collapsed step table. No server work, no new endpoint, no new state.

Without it, the observable effect of this ADR is an unreviewable approval prompt for the most consequential action in the system. A gate reading *"approve `plan:plan-ab12` on multiple"* is a gate that trains operators to click — the failure ADR-0034 exists to prevent. Keep the card **minimal and faithful**: ADR-0062 will revise it toward an envelope, and building a rich version now would be work thrown away.

### 5. Expect more failed `create_plan` calls, and accept them

Today the model attempts almost none, so any trigger increases attempts — including attempts that fail validation. That trade is deliberate, and it rests on the *shape* of the failure:

- The failure is **safe and informative**: `_create_plan` catches `ValueError` and returns `{"success": False, "error": …}` listing every accumulated validation error (`server.py:3438-3442`). Nothing is gated, nothing reaches a device, no approval is consumed, and the model gets exactly which ids were wrong and can retry.
- The failure that would be **dangerous** is the other one — a plan that *validates* and then does the wrong thing, because params are never checked. That is why "never plan what you cannot yet parameterise" appears in both the description and the prompt, and why it earns its own test.

A tool whose worst failure mode is a free, detailed, zero-side-effect rejection is one it is responsible to make the model reach for.

## What this does not do

- **Make the firmware LTS stair plannable.** `admz/plans/engine.py` contains no reboot, recovery or wait handling, and `await_device_recovery` is an **MCP tool, not a catalog operation**, so it can never be a plan step. Any plan whose step N reboots a device and step N+1 touches it is unsound. A *single-hop* fleet upgrade becomes plannable; the multi-hop stair does not — and the corrected FR-FW-008 must say so rather than replace one fiction with another.
- **Give steps data flow.** `PlanStep.condition` is declared (`admz/plans/models.py:45`) and never read by the engine. Needs #439.
- **Add templates.** `admz/plans/templates.py` does not exist; `template` is not in the schema and `additionalProperties: False` makes passing one a hard rejection. FR-PLN-012 stays planned; the corrected FR-FW-008 cross-references it as the reason its fiction was written.
- **Let a plan adapt after approval.** Approval is over a fixed step list and is single-use. That is #440 / ADR-0062, still *Proposed*. This ADR is the half ADR-0062 names as missing: *"Shipping this without #438 changes nothing an operator would notice."*
- **Change the gate, the risk classification, or who may approve.** Risk still comes from the catalog per step (FR-PLN-006); a caller can neither set nor soften it.

## Decisions taken — the owner may override any before it ships

| # | Question | Decision |
|---|---|---|
| 1 | May a plan be created with steps not yet fully parameterised? | **Yes — the engine already allows it.** The real precondition is knowing the ids. This is the issue's own open question, answered from the code rather than by preference (§1) |
| 2 | Description-only, or wider? | **Wider**: descriptions + prompt + the chat plan card + the false docs. A trigger alone produces plans nobody can review (§4) |
| 3 | How is the plan/compound-request boundary drawn? | **Mechanically** — a plan step is a catalog operation on a registered device; ADMZ's own record tools never are (§2) |
| 4 | Fix `execute_plan`'s description here too? | **Yes**, plus the coupled `confirm_tool` fix — a model that plans reads it next (§3) |
| 5 | Ship the rich envelope-style card? | **No** — minimal and faithful; #440 will revise it |

## Slices

One PR. The description and prompt changes are worthless without each other (the prompt would otherwise override the trigger), and the card is what makes the result reviewable.

`admz/mcp/server.py` (both descriptions + two schema field descriptions) · `admz/operations.py` (`confirm_tool` conditional on `is_plan`) · `admz/chatbot/system_prompt.py` (the forward bullet inside `# Compound requests`, the new `# When to plan` section, the amended `:68` bullet) · `admz/api/static/chat.js` (the `is_plan` branch) · docs: **FR-FW-008**, **FR-MCP-013**, **FR-MCP-003**, `user-stories/llm-driven-configuration.md:42` (the origin of the phantom reason string — leave it and the next person restores the falsehood), `docs/MCP_TOOLS_REFERENCE.md`.

## Verification

| Claim | Test | Control / mutation |
|---|---|---|
| The description states a trigger, not behaviour | `"Use this when"` present; **anti-vacuity:** the exact sentence #438 quotes is *gone* | restore the old string → fails |
| It orders discovery before planning, with the consequence | `"rejects the WHOLE plan"` present | trim to a bare instruction → fails; this is the clause a later "tighten the prose" edit removes first |
| It names the payoff that competes with card-per-step | `"ONE approval"` / `"card per step"` | remove → fails; without it the description and `# Compound requests` disagree on which is preferable |
| It promises nothing the schema forbids | `template=` / `condition` / `risk_level` absent from the text | add one → fails (schema side already pinned by `test_risk_vocabulary.py:185-210`) |
| The anti-trigger is tied to **code**, not just prose | `condition` absent from `PlanStep.to_dict()` **and** from the engine source | when #439 lands this fails, forcing the description to be corrected in the same PR — the anti-drift mechanism #438 asks for |
| `execute_plan` documents no nonexistent reason | `plan_contains_dangerous_steps` absent from the description **and** from `inspect.getsource(admz.operations)` | fails if someone later introduces the reason for real without updating the description |
| It documents the real gate | build a dangerous plan, call `execute_gated_plan`, assert the envelope's keys match the tokens the description names | ties description to a live envelope, so drift in **either** direction fails |
| A plan envelope does not advertise the wrong tool | `confirm_tool != "confirm_dangerous_operation"` for a `url_*` plan | control: the **single-op** envelope still carries it (`test_gate_parity.py:33-52` unchanged), proving the fix is scoped |
| The prompt carries the rule, and the two sections cross-reference | both directions asserted | ship the section without touching `# Compound requests` → the forward assertion fails |
| Placement broke neither pinned seam | **do not edit** `test_chatbot_system_prompt.py:264` / `:343` | they are the control; inserting before `# Compound requests` fails `:264` |
| The card's JSON carries what the card needs | extend `test_chat_confirm_json.py` with a plan session → `is_plan` true, `plan_summary["steps"]` non-empty | control: the existing single-op `is_plan is False` assertions still pass |

Assert on the **live** `Tool` object via `tests/mcp_harness.py:107-112`, not on sliced source. The renderer itself is **not unit-testable** — this repo has no JS test tooling — so it is covered by the JSON contract test plus manual verification on a local dev instance (staging is unusable, #238).

## Consequences

- Multi-write jobs take one approval instead of a card per device; the operator's click count on an eleven-device change goes from eleven to one, and each of those clicks stops being a separate decision made in isolation.
- Three descriptions stop lying: two that never said when to use the tool, and one that documented a branch the code does not have.
- The in-chat approval card shows a plan as a plan. FR-CB-004's ✅ becomes true for the plan case it already claims to cover.
- More `create_plan` attempts will fail validation than today. That is the intended trade (§5).
- The model-authored plan path becomes usable; the ADMZ-authored one (`restore_device`, demos, scenarios) is unchanged.

## What would falsify this

If the model starts planning and its plans routinely fail validation on ids it could have looked up, the discovery clause is not carrying its weight and the answer is a `list_devices`-style precondition in the tool itself, not more prose. If operators approve plans without opening the step table, the card is ceremony and ADR-0062's envelope framing is the better target. And if plans remain rare after this ships, the cause was never the description — it is `# Compound requests`, and that section needs rewriting rather than annotating.
