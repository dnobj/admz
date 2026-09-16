# ADR-0070 — Drift is reviewed in the console chat: deterministic triage, gated tools, one card per decision

**Status:** Accepted — 2026-09-16 (#504 plan) · **Shipped:** PR 1 (#508 — triage, one review annotator, the accept guard on every path, `note`/`ignore_keys` on accept, the seed rule); PR 2 (#509 — `get_drift_review`, `revert_drift`, `ignore_config_keys`, `list_config_ignore_rules`, the `add_ignore_rules` executor, the conditional fenced guidance). `list_notices` / `dismiss_notice` ship with ADR-0071
**Closes when shipped:** the implementation issues filed from [the plan](../plans/drift-review-in-chat.md)
**Relates to:** [ADR-0031](0031-live-observation-baseline.md) (baseline vs observation — what accept blesses) · [ADR-0034](0034-uniform-widget-gating.md) (every write behind one gate; nothing here softens it) · [ADR-0047](0047-demo-config-fragments.md) (attribution buckets; the accept guard this record makes universal) · [ADR-0055](0055-order-insensitive-drift-comparison.md) (what counts as drift — triage never changes that) · [ADR-0056](0056-drift-attribution-annotates-never-suppresses.md) (the annotate-only contract triage adopts) · [ADR-0062](0062-approve-an-envelope-not-a-step-list.md) (where a true one-card composite belongs) · [ADR-0066](0066-an-out-of-band-resolution-resumes-the-promised-turn.md) (the continuation that carries a review from card to card) · [ADR-0069](0069-removing-several-devices-takes-one-approval.md) (one approval for a batch of record operations) · [ADR-0071](0071-a-task-raises-a-notice-the-console-delivers-it.md) (the notice that starts a review)

_Plan-first per `process.md`: this document merges before any code. File:line references are against master `daa4159`._

## Context

Drift tracking and approval work well in the web UI, and the operator says so. The `/devices` roster expands a drifted device into BASELINE vs LIVE columns (`admz/api/templates/index.html:471-756`), each row has an eye-slash that writes a config-ignore rule (`:599-602`, `:824-854`), **Accept drift** takes a note that becomes the device's git changelog entry (`:959-985` → `POST /api/snapshot/accept-baseline`, `admz/api/routes/snapshot.py:194-295`), and **Revert N fields** builds a targeted plan from the rows the operator ticked (`:987-1012` → `POST /api/snapshot/revert`, `snapshot.py:457-560`). Read-only observed changes are grouped and labelled "not revertable" (`:664-674`), from the `revertable` flag `_annotate_revertable` computes with the same facet predicates the revert builder uses (`snapshot.py:1100-1130`).

The operator wants to do that review **in the console chat**, with the assistant nudging what matters and what does not, following reference guidance. Two examples from a live device (AXIS C8110 on 12.11.77): `event_mqtt_bridge publication.topicPrefix default → DEFAULT` and `root.Properties.FirmwareManagement.Version 1.8 → 1.10`, plus two firmware-added read-only keys. All four are noise; none should need thought.

### What the chat has, and lacks

The system prompt tells the model the user has "exactly two moves" — accept via `accept_baseline`, revert via `restore_device` with `ref` omitted (`admz/chatbot/system_prompt.py:191-198`). Measured against the UI, the chat lacks:

| UI can | Chat today |
|---|---|
| revert **chosen** rows | only `restore_device` — the **whole** baseline re-pushed (`admz/mcp/server.py:1372-1409`); no targeted revert tool exists (`admz/mcp/dispatch.py:410-487`) |
| exclude a key from tracking | no ignore-rule tool at all |
| accept with a changelog note | `accept_baseline` has no `note` (`server.py:1410-1442`), although the executor already honours one (`admz/operations.py:666-685`) |
| see which rows are revertable | MCP `_check_drift` live-probes and applies only `annotate_attribution`, never `_annotate_revertable` (`server.py:3826-3854`) |
| know what is noise | nothing: the only volatility knowledge is scattered across `VOLATILE_PREFIXES` (`admz/snapshot/engine.py:79-82`), the seed ignore rules (`admz/snapshot/ignore.py:61-95`) and per-facet `RESTORE_EXCLUDE` lists; the atlas carries no per-parameter metadata |

### A guard that only one door has

Accepting a baseline while an active demo owns config on the device bakes the demo into the baseline. The REST route refuses it with 409 — or 503 when the guard itself cannot run, fail-closed (`snapshot.py:138-191`, #174). That function is referenced from the two REST accept routes and nowhere else. Neither the MCP handler (`server.py:3752-3808`) nor the approved-action executor (`operations.py:659-702`) runs it, so an accept driven from the chat bypasses ADR-0047's guard entirely. This is a defect, and it is fixed here rather than in a separate record because the chat is about to become the primary door.

### The ordering hazard

Accept does not capture; it **blesses a commit that already exists** — the cached report's `observed_sha` on REST (`snapshot.py:225-229`), `latest_observed_sha` on MCP (`server.py:3766`). A revert plan writes the device and records **no** observation. So "revert Y, then accept the rest" only works with a fresh observation between the two; accepting straight after a revert blesses the pre-revert values and every reverted key re-drifts on the next check. The UI never hits this because a human refreshes the panel. The model will hit it unless told.

## Decision

**The chat runs the same review the UI offers — read, decide per field, act — with ADMZ classifying every drifted field deterministically, the model narrating and proposing, and every write behind the existing gate. One card per decision; the accept card can carry the exclusions.**

### 1. Triage is deterministic code that annotates and never suppresses

A new `admz/snapshot/triage.py` classifies each drifted field into a class with an importance, a default recommendation and a one-line `why`, and adds a report-level context. It follows ADR-0056's contract byte for byte: it **adds** keys (`field["triage"]`, `summary["triage_context"]`, `summary["summary_by_class"]`, `summary["highest_importance"]`) and never removes a row or touches `bucket`, `has_drift` or `revertable`. Per ADR-0055 a case-only change is still drift; triage labels it `cosmetic`, it does not hide it.

The classes, first match wins, matching on the canonical key with the same glob / exact-or-child semantics as ignore rules (`ignore.py:102-107`) so an operator reads both the same way:

| Class | Importance | Recommendation | Trigger |
|---|---|---|---|
| `demo_set` | none | none | ADR-0047 bucket, passed through |
| `demo_broken` | high | repair | ADR-0047 bucket |
| `demo_candidate` | medium | adopt or revert | ADR-0047 bucket |
| `security_sensitive` (identity) | high | revert unless explained | `users:*`, `root.Properties.API.HTTP.AdminAccess*`, an ACAP `status` appearing or vanishing |
| `cosmetic` | low | accept | both sides present and equal after case-fold and whitespace collapse, or equal as numbers (KL-DRF-001) |
| `firmware_managed` | low | accept | `root.Properties.*`, `*FirmwareManagement*`, `*.Version`, `*.Build`, `root.Brand.*`; app version/signature, or any key that appeared, when the firmware changed since the baseline |
| `added_key` | low | accept | baseline side is `<missing>` |
| `runtime_state` | low | ignore | any `Volatile*` segment; the seed-ignore family (`eth0.*`, `Routing.*`, `ZeroConf.*`, `DHCP.VendorClass`, `UPnP/Bonjour.FriendlyName`, `dot1x.Status`, `ServerDate/Time`); network's runtime `RESTORE_EXCLUDE` entries (`admz/snapshot/facets/network.py:25-39`) |
| `security_sensitive` (config) | high | revert unless explained | the rest of `root.Network.*`, `root.HTTPS.*`, `root.RemoteService.*`, `root.SNMP.*`, `root.RemoteSyslog.*`, SSH, `root.System.*Access*` |
| `read_only` | low | accept or ignore | `revertable is False` |
| `service_config` | medium | ask | image, stream profiles, audio, events, I/O, time, PTZ, recording, storage, motion, overlay; the `ntp`, `time_api`, `sip`, `event_mqtt_bridge`, `event_schedules`, `action_rules` facets; an app stopped or started |
| `uncategorized` | medium | ask | everything else |

The order carries the judgement: identity sits **above** `added_key` so a new admin account is high even though it "appeared"; `runtime_state` sits **above** network config so a DHCP re-lease is not a security alarm; `read_only` sits **below** the security rules so a non-revertable security change stays high.

The firmware context is read from git, not remembered: the engine writes `firmware_version` into `fleet/<id>/device.yaml` on every capture (`engine.py:638-665`, `:874-891`), so `device.yaml` at `baseline_sha` versus at `observed_sha` says whether the firmware moved. That one fact explains most low rows on a device that was just upgraded, and the model is told to say so.

_As built (PR 1):_ two `service_config` triggers — an action rule, and an application started or stopped — are evaluated **above** `read_only`. Both facets are read-only for restore by design, so in the table's order those triggers could never fire and every rule edit would read "low, accept or ignore". The general service-parameter trigger stays below `read_only`, where a non-writable mirror belongs. Every label also names the `rule` that produced it, and an application's version or signature is firmware-managed only when the firmware moved too.

The table is a Python tuple in `triage.py`, editable without prompt surgery. The atlas has no per-parameter volatility metadata today; when it grows some, the Axis-fact rows move there and this table keeps only ADMZ-policy rows. The four rows from the operator's screenshot classify `cosmetic`, `firmware_managed`, `added_key`, `added_key` — highest importance **low** — so the model proposes one accept with a cause-based note and asks nothing.

### 2. One annotator serves every surface

`_annotate_revertable`, the cached-report read and the revert-field selection move out of the REST module into `admz/snapshot/review.py` (they depend only on the registry — `snapshot.py:1100-1130`, `:407-427`, `:430-454`). `review.annotate_review(summary, *, registry, git_repo, device_id)` runs revertable → attribution (#230) → triage and adds the ignore rules applicable to the device. REST `check_drift`, MCP, and ADR-0071's notice producer all call it, so the chat sees exactly what the UI sees, and a hint chip in the UI later reads the same `triage` key.

### 3. The tools, every write behind the existing gate

| Tool | Gate | What it does |
|---|---|---|
| `get_drift_review(device_id, refresh=false, classes?, include_fields=true, limit)` | read-only | the cached diff, fully annotated, rows ordered highest importance first and capped; `refresh=true` probes the device and **records a fresh observation** |
| `accept_baseline(device_id, commit_sha?, note, ignore_keys?, ignore_scope?)` | url_only action (unchanged class) | gains `note` (the git changelog entry, as the UI) and `accepted_by` (the principal); `ignore_keys` fold "exclude X" into the **same** card; blesses the cached review's `observed_sha` like REST |
| `revert_drift(device_id, fields[{facet,path}], note?)` | url_only plan | a minimal targeted plan from the reviewed diff (`RestoreBuilder.build_targeted_revert_plan`, `admz/snapshot/restore.py:155-289`, every step `service-affecting`) → **one** card; non-revertable rows are skipped and listed with a reason; `demo_set` rows are never in the plan |
| `ignore_config_keys(keys, scope, reason?)` | url_only action `add_ignore_rules` | the eye-slash for chat; already-present keys → no card |
| `list_config_ignore_rules(scope?)` | read-only | what is excluded today |

Ignore rules take a card from the chat although the UI eye-slash is direct. A global rule silently re-labels future drift fleet-wide, permanently — the consequence class `assign_demo_fragment` is gated for (`admz/demos/gated.py:3-8`), and the interactive-console exemption never applies to an LLM caller. No new risk word is invented: the action rides the default class pinned to `url_only` exactly like `gate_task_write` and `gate_demo_write` (`admz/tasks/gated.py:208`, `admz/demos/gated.py:31`); the honesty lives in the card's sentence, which names every key and the scope.

Because every write returns the standard blocked envelope, the in-chat approval card, the `[console]` resolution note, the ADR-0066 continuation and the voice card all work unchanged.

### 4. The accept guard runs on every path, and fails closed at execution

The guard body moves to `admz/snapshot/accept_guard.py::check_accept_allowed`, raising `AcceptRefused(status)` (409 active demo, 503 guard unavailable). Three callers: the REST wrapper (unchanged behaviour, unchanged tests), the MCP handler **before minting a card** (a refused accept produces no card, just the reason), and the approved-action executor **before touching the pointer** — so a demo activated between minting and approval still cannot be baked in. Fail-closed at execution is the property the REST route already had and the chat never did.

### 5. Composite-lite, not a composite — and the order rule

A single "ignore X, revert Y, accept the rest" card was the ideal and is not built. Two facts decide it. First, the ordering hazard above: the accept in such a card must bless an observation taken **after** its own revert step ran, which puts a live device read and an observation commit inside the approval path. Second, an action executor cannot run a plan today (`operations.py:1550` hands it `registry` and `git_repo` only), and the card for an action session shows only its sentence, with no step list (`admz/api/routes/confirm.py:649-659`). Running the un-gated `plan_engine.run_plan` under an action approval with a step-less card is the wrong shape; ADR-0062's envelope is the right home for it, later.

So the common case — the screenshot's, everything low — is **one** card: `accept_baseline(note, ignore_keys)`. A review that reverts something is **two** cards, in a fixed order the prompt and the tool descriptions both state: ignore rules first (they take effect on the next compare, so they can ride the accept), then `revert_drift` (card 1), then — after its `[console]` note reports success — `get_drift_review(refresh=true)`, and only then the accept (card 2). A revert that FAILED stops the review; nothing is accepted on top of it.

### 6. The guidance rides a conditional, fenced prompt section

A `_DRIFT_REVIEW_GUIDANCE` block, in the shape of ADR-0051's inference guidance (`system_prompt.py:593`, wired `:840-846`), renders only when `admz/chatbot/context.py::build_attention_section()` returns something: the open notices (ADR-0071) and the devices the cache says are drifted. Empty → the whole section vanishes and the prompt is byte-identical to today (the ADR-0051/0052 contract, pinned by test). The live block is wrapped in `_fence('ATTENTION DATA', …)` because device model and nickname are device-written text; the builder is registered in `tests/test_prompt_fencing_completeness.py`'s `FENCED_SECTIONS` so forgetting the fence fails CI.

The guidance says, in this order: read with `get_drift_review`; walk highest importance first **with the values**, `demo_broken` first of all; collapse every low row into one line and name the firmware change when the context has one; propose ONE plan in the order ignore → revert → accept and ask once — ask *before* proposing to revert a `security_sensitive` row and never auto-accept one; act in the order §5 fixes; close with one line per part. It states what matters and what does not (the table in §1, in prose), how to write the accept note (short, cause-based, one clause per cause: "fw 12.9.57→12.11.77 upgrade; MQTT prefix case normalised"), and the nudge rule: open notices are mentioned **once, in one line, at the start of a conversation**, never repeated, and answered any time the user asks. The existing "exactly two moves" bullets become three moves per field pointing at the new tools; `snapshot_device` on a drifted device stays forbidden; the `[console]` semantics bullet gains "or opened a notice for review from the Console (nothing has changed yet)".

_As built (PR 2):_ the notice half waits for ADR-0071, which ships the notices. So the attention section lists drifted devices only, and `list_notices` / `dismiss_notice` and the `[console]` clause about an opened notice arrive with the notices themselves. The four review tools follow `delete_devices` in the wire order, and the notice tools go after them. A card not tied to one device — a fleet-wide or tag-scoped exclusion — is held against the literal `fleet`, and its `[console]` note now reads "fleet-wide" (or "for tagged devices") rather than "on device fleet". Other fleet-scoped cards (a fleet-wide task, a survey) now read that way too. The note never repeats a tag name, because a tag can be written through an ungated tool.

### 7. One seed ignore rule

`root.Properties.FirmwareManagement.*` is appended to `_SEED_DEFAULT_RULES` (append-only, `ignore.py:57-60`). It is the same fact as the already-volatile `root.Properties.Firmware.*` (`engine.py:79-82`) one API deeper, and the operator's own example of "internal". Operators can delete it in Settings like every seed.

## What this does not do

- **No single-card composite.** §5; revisit on ADR-0062.
- **No bulk accept.** `accept_baselines(device_ids, …)` in the ADR-0069 shape is planned as a sibling tool (FR-DRF-019), not `device_ids` on the existing tool, so the single-device contract and its tests stay untouched.
- **No UI change** beyond the additive `triage` key on `GET /api/snapshot/drift`; a hint chip is a later slice.
- **No atlas change.** The triage table notes its future home.
- **No post-revert recheck by ADMZ.** The model is told to call `get_drift_review(refresh=true)`; the UI's own revert path is unchanged.
- **No change to what counts as drift.** ADR-0055 stands; triage labels.

## Decisions taken — the owner may override any before it ships

| # | Question | Decision |
|---|---|---|
| 1 | Who classifies? | **Code**, deterministically; the model narrates and proposes (§1) |
| 2 | Where does the knowledge live? | A rule table in `triage.py`; Axis-fact rows move to the atlas when it can hold them |
| 3 | Chat ignore rules gated? | **Yes**, a card, at single-removal's pinned level (§3) |
| 4 | One card per review? | **Composite-lite**: the accept card carries exclusions; a revert is its own card, before the accept, with a refresh between (§5) |
| 5 | Guidance always on? | **Conditional**: only while a device is drifted or a notice is open; byte-identical prompt otherwise (§6) |
| 6 | Seed `FirmwareManagement.*`? | **Yes** (§7) |
| 7 | Bulk accept? | Planned as a sibling tool, later |

## Slices

**PR 1 — backend.** `triage.py`, `review.py`, `accept_guard.py`; REST and MCP `check_drift` call `annotate_review`; `accept_baseline` gains `note` / `accepted_by` / `ignore_keys` and the guard on both chat paths; `OUTCOME_IDENTITY_KEYS` gains `ignore_added_keys`; the seed rule; tests.

**PR 2 — tools and prompt.** `admz/mcp/tools/drift_review.py` (`get_drift_review`, `revert_drift`, `ignore_config_keys`, `list_config_ignore_rules`, plus ADR-0071's `list_notices` / `dismiss_notice`), handlers, dispatch, the `add_ignore_rules` executor, tool order; `_DRIFT_REVIEW_GUIDANCE`, `build_attention_section`, the three prompt-assembly sites, the fencing registry, the rewritten drift block; `docs/MCP_TOOLS_REFERENCE.md`; a live e2e.

## Verification

| Claim | Test | Control / mutation |
|---|---|---|
| Triage annotates, never suppresses | row count, buckets, `has_drift`, `revertable` identical before and after; a raising rule leaves the report untouched | make it drop `demo_set` rows → fails |
| The screenshot's four rows are low; identity beats `added_key`; runtime beats network config | table-driven classification | swap two rule rows → the `users:… <missing>→admin` case fails |
| Firmware context comes from git | two committed `device.yaml` versions → `firmware_changed` | registry-only read → fails |
| One annotator serves REST, MCP and the cache path | both surfaces carry `triage`, `revertable`, `attribution`; cached and live paths have the same keys | remove one call site → fails (replaces the literal-text assertions at `tests/test_drift_attribution.py:455-461`) |
| The chat accept refuses an active-demo device before minting, and the executor refuses at execution | handler → no session; demo activated after minting → approval `success: false`, pointer unchanged; a `sqlite3.OperationalError` in `owning_demos` → 503-class on both | remove the executor call → the second case fails; the REST test stays green as the control |
| A chat accept writes the changelog with the principal | `BASELINE.yaml@HEAD` has the note and `accepted_by` | drop `accepted_by` from the payload → fails |
| `ignore_keys` land only on approval | rules absent after minting, present after `_approve`; the next compare excludes the key | add them at mint time → fails |
| `revert_drift` builds one gated plan from the reviewed diff | one revertable + one read-only + one `demo_set` row → one `param.cgi:update` step, `skipped` names the other two, `demo_set` never in the plan; the card approves in a fresh `PlanEngine` | include `demo_set` → fails |
| `ignore_config_keys` is gated at the pinned level and dedupes | session is `service-affecting` / `url_only`; a fleet override does not soften it; already-present keys → no card | `operator_configurable=True` → fails |
| Tool order and dispatch stay frozen | the new names are appended at the end; `TOOL_HANDLERS` equals the frozen set | insert mid-list → the prefix assertion fails |
| The guidance is conditional and fenced | one drifted device → heading + `ATTENTION DATA` fence; none → byte-identical prompt | classify the builder as trusted → the behavioural fence test fails |
| The descriptions carry the order rule | `accept_baseline` / `revert_drift` contain "refresh=true" and "before"; `get_drift_review` says the hint is never a verdict | delete the sentence → fails |
| Live | `tests/e2e/test_24_drift_review_chat.py`: a drifted lab device → the reply names the firmware context and proposes an accept with a note; any card is real | — |

Then per the playbook: adversarial review in its own worktree, a mutation harness on a quiet tree, the full suite, green CI.

## Consequences

- The chat can do what the UI does, per field, with the same annotations the UI will show — and one thing the UI does not: explain each row.
- A real guard bypass closes on the surface that is about to carry most accepts.
- Two new modules the UI and the chat share, four tools, one executor, one prompt section that costs roughly 700 tokens per turn only while something is drifted.
- The "two moves" prompt bullets, which pointed revert at a whole-baseline re-push, are corrected.

## What would falsify this

If reviews routinely need the model to overrule a class — a `service_config` row that is always noise on this fleet, a `runtime_state` key that once mattered — the table is wrong for the site and needs operator-editable overrides, not a smarter prompt. If operators keep answering the accept card with a revert, the proposal order is wrong. If the two-card revert path is what people actually run, §5's deferral was the wrong call and the composite should move ahead of ADR-0062 rather than wait for it.
