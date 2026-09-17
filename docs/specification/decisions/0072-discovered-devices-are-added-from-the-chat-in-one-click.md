# ADR-0072 — Discovered devices are added from the chat in one click

**Status:** Accepted — 2026-09-16 · **Shipped:** 2026-09-16 (#512 plan, #514 code — see [As built](#as-built))
**Relates to:** [ADR-0059](0059-gate-provisioning-at-the-decision-point.md) (account creation is gated where it is decided; this keeps that gate and changes how many devices one approval covers) · [ADR-0069](0069-removing-several-devices-takes-one-approval.md) (one approval for a batch, for removal) · [ADR-0034](0034-uniform-widget-gating.md) (every destructive action goes through the approval widget) · [ADR-0066](0066-an-out-of-band-resolution-resumes-the-promised-turn.md) (the continuation that answers a `[console]` note) · [ADR-0016](0016-merge-discovery-by-mac.md) (a device is its MAC) · #404 (discovery reports; adding a new device is a manual, batched click)

_Plan-first per `process.md`: this document merges before any code. File:line references are against master `eaeec9d`._

## Context

"Discover devices on my network" is one of the most common console requests. On 2026-09-16 it found 31 devices on the lab's /24. The model received the whole result and re-typed it as a markdown table. That cost about 70k input tokens and 1k output tokens, and it produced a table nobody can act on.

Acting on it is the expensive part. To add the four new cameras, the operator has to ask again. Each add then reaches `onboarding.onboard_device_credentials`, which raises **its own** approval card before it creates an account (ADR-0059, `admz/onboarding.py:394`, `:559`). With a fleet root password configured, that is almost every new camera. So adding four devices means four cards: the gate fatigue ADR-0069 removed for removal.

The owner's direction on #404 is that searching for and adding a new MAC is a manual effort, reduced to a click, with the approval batched. There is no surface for that click today.

### What exists, and what a widget must reuse

- **The tool result reaches the browser, but capped.**
  - The manual tool loop emits every result as an SSE `tool_result` event carrying `_redact_for_display(payload)` (`admz/chatbot/client.py:1535-1539`). That copy is capped at **50 list items and 300-character strings** (`:1295-1332`).
  - The model gets a separate copy capped at 6000 characters (`:1549`).
  - Tool results are **not persisted**. `chat_history` stores text only (`admz/chatbot/sessions.py:36-50`), so a reload replays prose and event chips, never tool cards.
- **Widgets are built only from structured results.**
  - The approval and capture cards are found by scanning `tool_result` JSON for `/confirm/` and `/capture/` URLs (`admz/api/static/chat.js:149-156`, `:257-268`).
  - A link that appears only in the model's prose is flagged, not rendered (`:283-304`).
- **The discovery result carries no registration state.**
  - `discover_network_devices` (`admz/mcp/server.py:4522-4559`) returns `{success, count, devices}`, and no field says whether a device is already managed.
  - The deep survey is the only caller that checks: it matches `canonical_mac` against the registry and uses the MAC as the device id (`admz/demos/inference/collect.py:459-509`).
- **The approval gate is one function.**
  - `_approve_session` (`admz/api/routes/confirm.py:189-371`) runs, in order: the rate limit, the pending check, the per-token password lockout (`:36-63`), the approver-group check (#178, `:263-283`), the password when the level is `url_and_password`, execution, the `confirm.approve` audit row, and the `[console]` note (`:369`).
  - The JSON twin `POST /api/chat/confirm/{token}` is how the chat card approves.
- **The approval list decides provisioning authority.**
  - An approved action carries it only if it is in `operations._PROVISIONING_APPROVAL_ACTIONS` (`admz/operations.py:1539-1545`), which sets the ambient marker.
  - Onboarding honours the marker only for the actions in `onboarding._APPROVAL_ACTIONS` (`admz/onboarding.py:145`).
- **There is no interactive exemption for provisioning** (`admz/discovery/gated.py:60-66`). A signed-in operator is gated like the model.

## Decision

### 1. A scan is kept, server-side, for a day

`discover_network_devices` saves each scan to a new store, `admz/discovery/scan_store.py` (`discovery_scans`).

- **What a row holds:** principal, subnet, `axis_only`, creation time, and every device with its display fields and `to_registry_dict()`.
- **What the result gains:**
  - top level: `scan_id`, `scan_url` (`/api/discovery/scans/<id>`), `axis_count`, `new_axis_count`, `factory_default_count`;
  - per device: `registered_device_id`.
  - The counts survive the model-side cap.
  - None of these names trips the display redactor.
- **Why a store rather than the display copy:**
  - the display copy drops devices past 50;
  - what gets registered must come from the scan, not from the browser;
  - the MCP handler runs in a per-principal subprocess, and the API process has to read what it saw.
- **When a scan is not saved:** under the `mcp-standalone` fallback principal (`server.py:412-444`), which has no console to show it.
- **Binding to the conversation.** The chat route binds the scan to the conversation at the end of the turn, beside the existing action-link loop (`admz/api/routes/chat.py:915-931`). The client never supplies a conversation id.

This does not close KL-DISC-002. A scan row is a record of one run, not a cache that accumulates findings.

### 2. The console renders the scan as a widget

When a `tool_result` from `discover_network_devices` carries a `scan_url` matching `^/api/discovery/scans/[A-Za-z0-9_-]{20,}$`, `chat.js` inserts a widget after that tool card. The widget fills itself from `GET /api/discovery/scans/{scan_id}`.

- **Columns:** model or friendly name, device id (canonical MAC), IP, firmware, and badges for VAPIX, factory default and registered. A registered row links to its device page.
- **Default view:** Axis only, with an Axis/All toggle. The toggle is disabled when the scan itself was `axis_only`.
- **Which rows can be added:** a row is selectable when the device is Axis, has an IP, has an identity and is not registered.
  - Identity is the canonical MAC, or failing that a 12-hex serial, because an Axis serial is its MAC.
  - Every other row states why it cannot be added.
- **Selection:** nothing is pre-checked; **Select all new** is one click.
- **Consequence sentence:** it sits above the button and names what Add does.
- **Password field:** shown only when the approval needs one.
- **When Add is disabled:**
  - until the turn's `done` event;
  - when the operator may not approve;
  - when the scan is stale;
  - when the selection is empty or larger than the cap.
- **Escaping:** every device-supplied string is written through `textContent` or `escapeHtml`, because hostnames and friendly names are claims the device makes about itself.

The GET is scoped to the scan's principal. It returns live registration state (so rows flip after an add) and an `add_policy`:
- `confirmation_level` and `needs_password`, with the same no-hash fallback as `confirm.py:653-658`;
- `may_approve`;
- the consequence sentence;
- the scan's age and the limits.

`may_approve` and `_approve_session` use **one** helper for the approver decision, including the anonymous-no-identity fallback (`confirm.py:263-271`), so the widget and the gate cannot disagree.

### 3. The widget is the approval: one click, two requests

**Add** does two things in sequence.

1. **`POST /api/discovery/scans/{scan_id}/add {device_ids}`** creates the session and returns its token. It never approves. In order:
   1. **`check_same_origin`, before any side effect.** The scan id has been in the model's context and the SSE stream, so it is not a secret. Without this check, a cross-site POST under Negotiate could start a root-account write.
   2. **The scan's principal must be the caller's.**
   3. **Stale scans are refused.** A scan more than 60 minutes old gets 409 with "scan again".
   4. **Validation is all-or-nothing, as for a batch removal.** Every id must be in the scan and selectable, duplicates collapse, and at most 20 devices may be listed. One bad id rejects the request and creates nothing.
   5. **The session is built from the scan row, never the request body.** It is created through `discovery/gated.gate_scan_write("add_discovered_devices", target, payload, reason)`.
      - `target` is the device's own id for one device, and `"multiple"` for several.
      - The payload is `{device_ids, scan_id, devices: [{device_id, host, registry_info}]}`.
   6. **The token is linked to the scan's conversation** with the existing `confirm` kind, so the resolution writes a `[console]` note and a reload re-pins a still-pending card.
2. **`POST /api/chat/confirm/{token}`**, the existing route: the widget sends the token straight to it with `confirm_password` when needed.

Everything that makes this an approval is `_approve_session`, unchanged: the rate limit, the approver group, the password, the lockout, the audit row, `strip_payload` and the note.

- **Why two requests.** The lockout counts failures per token, so a retry has to reuse the token. A single request that created a fresh session on every attempt would reset that count each time, leaving only the per-address rate limit against password guessing.
- **A failed approval leaves the session pending.** It is never denied, because a denial writes a note saying the user said no.

**Why this is not an interactive exemption.**
- The gate still runs, in full, on the request of the principal who clicked.
- The level still comes from `gate_scan_write`, which is operator-configurable like every other provisioning gate. The operator can raise it to `url_and_password` on `/confirm-settings`, and the widget then asks for the password.
- The approver is still checked.
- The operator still reads what is approved: the sentence above the button is the session's `danger_description`.

What the owner removed is only the second surface: the card that would repeat what the widget already shows.

**The card names every device** (ADR-0069 §1).
- `danger_description` lists each device by canonical id and IP, plus its model passed through `sanitize_display_text`. It then names the writes, in the wording `survey_reason` already uses (`admz/discovery/gated.py:104-127`).
- Any surface that renders the session (a re-pinned card after a reload, or `/confirm/{token}`) shows the same list.

### 4. Execution registers, checks identity, and onboards under the one approval

A new executor, `_action_add_discovered_devices`, is registered in `_ACTION_EXECUTORS`. The action is added to **both** approval lists: `operations._PROVISIONING_APPROVAL_ACTIONS` and `onboarding._APPROVAL_ACTIONS`. With only the first, every factory-defaulted device would raise a nested `provision_device_credentials` card: *n* cards inside an approval already given, the failure `discovery/gated.py:43-47` describes.

For each listed device:

1. **Identity is re-checked before anything is written, fail-closed.**
   - The executor reads `basicdeviceinfo.cgi:getAllUnrestrictedProperties` (catalog `auth_level: none`) at the scanned host and compares `SerialNumber` with the device id.
   - A mismatch, or no answer, skips the device with a reason.
   - Without this, an address that DHCP has handed to another box since the scan would receive the fleet root password and a new root account. The host-moved refusal in `_action_provision_device_credentials` (`operations.py:1427-1450`) cannot catch this, because the registry host was just written from the same scan.
2. **A device registered since the scan is skipped and reported.**
3. **The device is registered:** `registry.add_device(device_id, registry_info)`.
4. **It is onboarded:** `onboard_device_credentials`, run for all devices through `asyncio.gather` with at most four at once.
   - Awaited children copy the approved context.
   - The executor spawns no detached task, which keeps the hazard `approval_context.py:49-62` names out of it.
5. **A device left needing credentials gets a capture session,** as `_action_provision_device_credentials` does (`operations.py:1458-1469`).

**The outcome.**
- It lists `added` and `failed`, and per device: `registered`, the onboarding `status`, a `capture_url` where one was opened, and any error.
- **Success means every listed device was registered and ended with working credentials** (`provisioned`, `admz_account_created` or `already_credentialed`). Anything less is a failure whose error names each device and what it lacks, so the console note never says "executed successfully" about a device ADMZ cannot reach.
- There is no cross-device atomicity, and none is claimed.

**The trail.**
- `audit.OUTCOME_IDENTITY_KEYS` gains `added_devices` and `provisioned_devices`, each a comma-separated string. `provisioned_devices` counts both statuses that created an account on the device.
- `failed_devices` is reused.
- `_note_target` already says "on N devices", because the payload's key is `device_ids`.

### 5. After the click

- **The widget writes each row's outcome in place:** added, needs credentials (with the standard capture card), or failed with its reason.
- **It refetches the scan,** so added rows show as registered.
- **It calls the existing continuation.** The model then answers the `[console]` note once, summarising what was added and what still needs attention (ADR-0066).

### 6. The model stops re-typing the table

The system prompt says:
- the console shows discovery results as an interactive table with an Add button;
- after a scan, the assistant summarises counts, new Axis devices and anything notable, and does not reprint the list;
- a scan is never a reason to register devices on its own initiative.

The voice session shares `build_system_prompt` (`admz/chatbot/voice.py:207`), and voice renders no widget, so the sentence is scoped to the text console.

## What this does not do

- **Everything else #404 asks for.** No periodic scan, no "not mine" dismissals, no discovery page. #404 stays open for those.
- **Restore the widget on reload.** The console does not persist tool results. A pending approval still re-pins as a standard card because its token is linked, but the table itself is gone until the next scan.
- **Add a chat batch-add tool.** Asking the model to add several devices still takes one card per device. The widget is the batched path.
- **Rescan from the widget.** A scan outside a chat turn has no conversation to bind to.
- **Render a widget in voice.**
- **Change the gating of `register_device` or `register_discovered_device`.** Whether a registry addition should be gated on its own is #404's question.
- **Restrict who may approve to human principals.** An API-key principal in an approver group can already approve any session. Making approval human-only would be a change to `_approve_session` for every session, not to this path.

## Decisions taken — the owner may override any before it ships

| # | Question | Decision |
|---|---|---|
| 1 | Does Add raise a separate approval card? | **No.** The widget is the approval surface: one click, two requests, both through the existing gate |
| 2 | Are API-key principals kept off this path? | **No.** Same approver rule as every other session |
| 3 | What if the address now belongs to another box? | **Fail-closed identity check** (serial against the MAC) per device, before any write |
| 4 | How old may a scan be? | **60 minutes**, then Add is refused with "scan again" |
| 5 | How large a batch, how fast? | **At most 20 devices**; onboarding **four at a time** |
| 6 | What happens to a bad id in the batch? | **The whole request is rejected** and nothing is created, as for a batch removal |
| 7 | When is an add a success? | **Every device registered and credentialed**; otherwise the error names each gap |
| 8 | What does the widget show first? | **Axis only**, with an All toggle; **nothing pre-checked** |
| 9 | Does the widget survive a reload? | **No**, in this version |

## Slices

One implementation PR, after this merges:

- `admz/discovery/scan_store.py` (new) and the discovery helpers: identity, registration annotation, selectability, and the card sentence in `discovery/gated.py`.
- `admz/mcp/server.py`: the handler's new fields and description.
- `admz/api/routes/chat.py`: bind the scan to the conversation.
- `admz/api/routes/confirm.py`: one approver helper.
- `admz/api/routes/discovery.py`: the scan GET and the add POST.
- `admz/operations.py`, `admz/onboarding.py`, `admz/audit.py`, `admz/approval_context.py`: the executor, both approval lists, the identity keys, the docstrings.
- `admz/api/static/chat.js` and `admz/api/static/css/admz.css`: the widget.
- `admz/chatbot/system_prompt.py`.
- Docs: `docs/MCP_TOOLS_REFERENCE.md`, and the 📋 → ✅ flips in `requirements/discovery.md`, `requirements/web-chatbot.md` and `user-stories/network-discovery.md`.

## Verification

| Claim | Test | Control / mutation |
|---|---|---|
| A scan is stored and the result names it | the handler writes one row and returns `scan_id`, `scan_url`, the counts and `registered_device_id` | control: the `mcp-standalone` principal writes nothing |
| The GET is the caller's own and live | another principal gets 404; a device registered after the scan reads as registered | compute registration at scan time only → the second assertion fails |
| One bad id rejects the batch | two selectable ids plus one registered id → 4xx, **no** session | gate only the valid ids → fails |
| A cross-site POST creates nothing | a POST with a foreign `Origin` is refused and no session exists | move the check after `gate_scan_write` → fails |
| The session comes from the scan | a body carrying extra device fields changes nothing in the session payload | read metadata from the body → fails |
| A stale scan is refused | a 61-minute-old scan → 409 | drop the age check → fails |
| One approval covers every device, with no nested card | a factory-defaulted and an adoptable device → one session; after approval both are credentialed and no `provision_device_credentials` session exists | leave the action out of `onboarding._APPROVAL_ACTIONS` → a nested session appears |
| The two approval lists agree | `_PROVISIONING_APPROVAL_ACTIONS == set(onboarding._APPROVAL_ACTIONS)` | add to one only → fails |
| The approval reaches every onboarding child | each gathered onboarding sees `is_approved_for("add_discovered_devices")` | run onboarding in a detached task → the static no-`create_task` test fails |
| Identity is checked before any write | a serial that does not match → that device is not registered and nothing is sent to it; the rest proceed | skip the check → the mismatched device is registered |
| One failure does not stop the rest, and success means all | one device already registered out-of-band → the others are added, `success` is false, the error names it | stop at the first failure → fails |
| A retry keeps the lockout | wrong password five times on one token → locked; the widget's retry uses the same token | create a session per attempt → the lockout never trips |
| The trail names the devices | the `confirm.approve` row carries `added_devices`; the console note says "on 2 devices" | drop the keys → fails |
| The widget renders only from the structured result | `chat.js` gates the widget on the tool name and the strict `scan_url` pattern, and writes device strings through `textContent`/`escapeHtml` | source-pinning test, as for the approval card |
| The model is told | the prompt names the widget, the summarise-don't-reprint rule and the no-initiative rule, only for the text console | remove any → fails |

## Consequences

- Adding *n* discovered devices takes one click and one audited approval instead of *n* requests and *n* cards.
- A scan turn is cheaper: the model summarises instead of re-typing the table, and the widget shows every device, past the 50-item display cap.
- The console gains its first data widget. It is built only from a structured tool result, as the approval and capture cards are.
- The provisioning-authority list grows by one entry. The two lists that grant that authority are now held equal by a test.

## As built

Shipped as decided, in #514 after #512. Where the code settled a detail this document left open:

- **Where things live.**
  - `admz/discovery/scan_store.py` (`discovery_scans`, store #22).
  - `admz/discovery/candidates.py`: identity, registration index, add blockers, counts and the batch, age and concurrency constants.
  - `admz/discovery/identity.py`: the unauthenticated serial read.
  - `admz/discovery/gated.py`: `add_reason` / `add_consequence`, plus the survey wording moved into a shared constant; the survey card reads exactly as before.
- **One consequence sentence.** The widget shows `add_consequence()` above the button before anything is ticked, and the session's `danger_description` is the device list followed by that same sentence.
- **One approver decision.** `confirm.approval_decision` is what `_approve_session` enforces and what the scan GET reports as `may_approve`.
- **One capture-form choice.** `api/capture.open_onboarding_capture` picks the account or root-adopt form by `reason_code`. The REST add/onboard routes and the executor both use it, so the REST behaviour is unchanged.
- **Only console turns get the prompt section.** `_run_chat_turn(console=…)` renders the section for `/chat/stream` and the continuation, and passes `False` for the JSON `/api/chat`. The no-JS form and voice never render it.
- **When Add is enabled.** Add enables when the turn's response *closes*, not at its `done` event. The server binds the scan after `done` is written.
- **Retries and lockout — enforced on the server.** The scan row remembers the pending session opened for a selection, and the add route hands that same session back while it is pending. So re-clicking Add, or re-posting the add, cannot reset the per-token password lockout. A different selection opens a new session, and the superseded one is unlinked from the conversation (no re-pinned card, no note) and left to expire. Across different selections the per-address `confirm` rate limit remains the bound, as it is for every other session-creating route. A `locked` answer disables Add for the lockout's five minutes.
- **The console note names every device.** The executor returns a `console_summary` that groups every device by outcome in fixed wording, with device ids only. `_note_resolution_to_chat` uses it in place of the 200-character error, so the model sees every outcome and never a device's own text. It still reaches no audit row.
- **Captures the add opens are linked** to the scan's conversation, so submitting the form writes its note and a reload re-pins the card.
- **A 410 is checked before it is reported.** The widget asks `/api/confirm/{token}/status`, so a session that already ran (a lost response, or approval from a re-pinned card) reads as done, not "expired".
- **A raised level is picked up.** If the add answers `url_and_password` while the widget showed no password field, or the approval answers `wrong_password`, the widget refreshes its policy.
- **Voice is not told about the table.** The tool description names only the new fields; how the console shows `scan_url` lives in the console-only prompt section.
- **Audit.** Creating the session writes a `discovery.add_requested` row (count and device ids), beside the `confirm.approve` row the approval writes.
- **Untrusted text in the executor's reasons.** A device's reported serial is quoted only when it has a serial's shape. Onboarding error text is flattened and bounded before it reaches the console note.
- **Not yet verified against live devices.** The identity check assumes configured devices still report `SerialNumber` without credentials (the catalog says they return "a subset" of the unrestricted properties). If one does not, it is skipped with "could not confirm", which is the fail-closed direction; the owner's lab check decides whether that needs revisiting.
