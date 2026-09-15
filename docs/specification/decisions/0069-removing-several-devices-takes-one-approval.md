# ADR-0069 — Removing several devices from the registry takes one approval

**Status:** Accepted — 2026-09-15 · **Shipped:** 2026-09-15 (#495 plan, #496 code)
**Relates to:** [ADR-0034](0034-uniform-widget-gating.md) (registry actions gate at a pinned `url_only`; this keeps that gate and changes only how many devices one approval covers) · [ADR-0067](0067-the-chat-plans-when-a-job-is-several-named-operations.md) (one approval for a batch — of catalog operations only, so it cannot reach registry removal) · [ADR-0066](0066-an-out-of-band-resolution-resumes-the-promised-turn.md) (the continuation that carried the 2026-09-15 job from card to card) · #493 / #494 (the two failures that stopped that job)

_Plan-first per `process.md`: this document merges before any code. File:line references are against master `b83f5b5`._

## Context

On 2026-09-15 an operator asked the chat to "remove all devices from the registry". Eleven were registered. The model listed them and raised an approval card for the first, and the operator approved it. The continuation then ran on a different model (fixed in #493), and that model wrote an approval link for the second device instead of calling the tool (fixed in #494). The job stopped after one device.

Those fixes make the chain work. They do not make it reasonable. Done correctly, "remove all eleven" is **eleven approval cards**, each a separate decision about one part of a single intent. That is the gate fatigue ADR-0034 exists to prevent, and it is the shape ADR-0067 fixed for device writes: one approval for the batch.

ADR-0067 cannot reach it. A plan step is a **catalog operation on a registered device, and nothing else** (ADR-0067 §2). Removing a device from ADMZ's registry is one of ADMZ's own record operations, so under that rule the job is a compound request — one gated call, and one card, per device. Nothing in the tool set offers otherwise: `delete_device` takes exactly one `device_id` (`admz/mcp/server.py:819-839`).

### What single removal does today, and what a batch must reuse

- **The gate.** `_delete_device` (`server.py:2436-2459`) opens an action session through `operations.create_action_session` (`admz/operations.py:1387-1437`). The risk class is `service-affecting`; the confirmation level is **pinned** at `url_only` (`operator_configurable=False`, `:1432-1433`); the token lives 300 seconds (`:45`). The session stores `operation_id="action:delete_device"` and `action_json={"action": "delete_device", "device_id": …}`, and the card's sentence is its `danger_description`.
- **The removal.** On approval, `_approve_session` (`admz/api/routes/confirm.py:189-371`) calls `execute_approved_session`, which dispatches to `_action_delete_device` (`operations.py:705-724`). That tombstones the device's config history (`tombstone_device`, `:594-625`) and then calls `registry.remove_device`, which purges the device's state tables and cascades to its accounts and baselines in one SQLite transaction (`admz/backends/sqlite_backend.py:713-727`).
- **The trail.** One `confirm.approve` audit row, attributed to the approving principal, and one `[console]` note back into the conversation (`confirm.py:374-414`), which reads `on device {session.device_id}`.

There is precedent for one approval covering items on several devices: `assign_demo_fragment` stores a per-device list in one action session and executes it in one call (`admz/demos/gated.py:31-46`, `operations.py:794-823`). There is none for a list of device ids that all receive the same registry change.

## Decision

### 1. `delete_devices` — one tool call, one session, one card

A new MCP tool, `delete_devices(device_ids)`, requests removal of every listed device and returns **one** blocked envelope with one `confirm_url`. It sits beside `delete_device` rather than replacing it, so the single-device contract, its tests and its callers are unchanged.

- **Every id is checked before anything is created.** One unknown `device_id` rejects the whole request and opens no session. That is the consequence ADR-0067 states for a plan, for the same reason: the model must list devices before naming them, and an approval for "most of" the batch is worse than none. Duplicate ids collapse.
- **The gate is single removal's gate, unchanged.** `create_action_session(action="delete_devices", …)` uses the same risk class, the same pinned `url_only` level and the same token lifetime. A batch is never cheaper to approve than any one of its members, and ADR-0034's pin is kept rather than re-derived.
- **The card names every device.** Both approval surfaces already render `danger_description` — the chat card and `confirm_form.html` — while neither renders `action_json`. So the sentence lists each device by label and id: *"Remove 10 devices from the registry: AXIS P8815-2 (ACCC8EE6E7EE), …, including their stored accounts and credentials. The devices themselves are not touched; their git config history is retained."* No renderer changes. The list is as faithful as single removal's sentence, and a richer card can come with ADR-0062's envelope work rather than ahead of it.
- **The session's `device_id` is `"multiple"`** when more than one device is listed — the convention plans already use (`operations.py:1646-1650`).

### 2. Execution reuses single removal, device by device

A new executor, registered in `_ACTION_EXECUTORS`, calls `_action_delete_device` for each id in the order given. It does not reimplement removal, so the tombstone, the cascade and the deliberately kept tables (`sqlite_backend.py:671-685`) are exactly those of single removal.

- **One failure does not stop the rest.** Each device's removal is independent, and stopping partway would leave an arbitrary subset removed. The executor attempts every id and reports which were removed and which failed, each failure with its error.
- **Success means every listed device was removed.** A partial result is reported as a failure that names what did and did not happen. The console note and the model then say "removed 9 of 10; ACCC8EE6E7EE: Device not found", not "executed successfully".
- **There is no cross-device atomicity, and none is claimed.** Each device is its own SQLite transaction and its own config-repo commit, as it is today.

### 3. The trail names the devices

- **Audit.** The `confirm.approve` row records payload key names, never values (`_approved_work_fields`, `confirm.py:117-179`), so on its own it would say only that *some* devices were removed. The executor's outcome carries the removed and failed ids, and `OUTCOME_IDENTITY_KEYS` (`admz/audit.py:339`) gains keys for them. Device ids are short, non-secret identifiers — the bar that list's own comment sets. `outcome_identity_fields` records scalars only, so each list is recorded as one comma-separated string. The row stays attributed to the principal who approved.
- **Console note.** For a batch session, `_note_resolution_to_chat` says *"on 10 devices"* rather than *"on device multiple"*, and so does the denial note (`_note_denial_to_chat`), which had the same sentence.

### 4. The model is told when to reach for it

- **`delete_devices` description.** It leads with the situation: the user wants more than one device removed. Then the payoff: **one approval card for the whole batch instead of a card per device** — the clause ADR-0067 found a trigger loses without. It states the precondition as a consequence: one unknown id rejects the whole request.
- **`delete_device` description.** It gains one line pointing to `delete_devices` for several devices.
- **System prompt.** Its registry-action bullet and `# When to plan` gain the same rule. ADR-0067's boundary stays intact: registry removal is still never a plan step; it has its own batch tool.

## What this does not do

- **Make registry removal a plan step.** ADR-0067's mechanical boundary stands, so a job mixing removal with catalog writes is still a compound request.
- **Add a REST batch endpoint.** REST `DELETE /api/devices/{id}` is ungated by design (ADR-0034's REST parity), and a script can loop over it.
- **Record who removed a device in its tombstone.** On the approval path `removed_by` is already empty for single removal, because the executor never receives the approving principal: `confirm.py:227` reads the session before it is completed. The batch inherits that gap. Closing it for every executor is its own change.
- **Batch other registry actions.** Only removal, the one with an incident behind it.

## Decisions taken — the owner may override any before it ships

| # | Question | Decision |
|---|---|---|
| 1 | Extend `delete_device` to take a list, or add a tool? | **Add `delete_devices`** — the single contract, its tests and its audit resource stay as they are |
| 2 | What happens to an unknown id in the list? | **The whole request is rejected and nothing is created**, as for a plan (ADR-0067) |
| 3 | How is the batch gated? | **Exactly like single removal** — service-affecting, pinned `url_only`, the same token lifetime |
| 4 | How does the card show the devices? | **In `danger_description`**, which both surfaces already render — no renderer change |
| 5 | What if one device fails? | **The rest are still attempted; success only when all were removed**, and the result names each failure |

## Slices

One implementation PR, after this merges: `admz/mcp/server.py` (the tool, its handler and the `delete_device` pointer) · `admz/mcp/dispatch.py` · `admz/operations.py` (the executor and its registration) · `admz/audit.py` (`OUTCOME_IDENTITY_KEYS`) · `admz/api/routes/confirm.py` (the console note) · `admz/chatbot/system_prompt.py` · docs: `docs/MCP_TOOLS_REFERENCE.md`, `docs/specification/requirements/mcp-server.md`.

## Verification

| Claim | Test | Control / mutation |
|---|---|---|
| One call opens exactly one session covering every device | `delete_devices` with three ids → one confirm session whose action lists all three | open a session per id → fails |
| An unknown id rejects the whole request | two real ids plus one unknown → an error, **no** session, no card | gate only the known ids → fails |
| The gate is single removal's | the session's risk class and level equal `delete_device`'s; a `confirm_level_service-affecting` override does not soften it | make the action operator-configurable → fails |
| The card names every device | the chat JSON endpoint's `danger_description` contains each label and id | control: single removal's sentence is unchanged |
| Approval removes every device through the single-removal executor | after approval all three are gone, and each is tombstoned | reimplement removal inline → the tombstone assertion fails |
| One failure does not stop the rest | one id removed out-of-band before approval → the other two are removed, `success` is false, and the failure names that id | stop at the first failure → fails |
| The trail names the devices | the `confirm.approve` row carries the removed and failed ids, and the console note says "on 3 devices" | drop the keys → fails |
| The model is told | the tool description carries the trigger, the ONE-approval payoff and the whole-request rejection, and the prompt names `delete_devices` | remove any of them → fails |

## Consequences

- Removing *n* devices takes one approval instead of *n*, and the operator reviews the whole list once, on one card.
- The model has a batch tool for a job it demonstrably attempts, so it no longer has to carry a card-per-device chain across continuations — the chain that broke on 2026-09-15.
- A batch is exactly as gated as any one of its members; nothing about the pinned `url_only` level changes.
