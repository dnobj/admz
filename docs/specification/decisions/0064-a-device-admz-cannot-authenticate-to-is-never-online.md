# ADR-0064 — A device ADMZ cannot authenticate to is never `online`: credential state is resolved once at registration, projected by health, and re-opened by the operator

**Status:** Accepted — 2026-09-06 · **Shipped:** slices A, B, C, D, E (2026-09-06) — #443 closed
**Closes when shipped:** #443 (slices A–B) · the remainder of #411 (slices C–F; F waits for the lockout measurement)
**Amends:** [ADR-0061](0061-entry-credentials-and-the-admz-account.md) (records what shipped; re-plans what did not) · supersedes the reclassification refusal in KL-HLT-004
**Relates to:** ADR-0034 (no flat refusals; one gate), ADR-0059 (gate at the decision point), FR-HLT-002/003/007, FR-CRED-007/011/012/013, #149/#150 (corroborated rejection), #357 (settled ≠ needs attention)

_Plan-first per `process.md`: this document merges before any code. All file:line references are against master `b89af46`._

## Context

### Seven hours of `online` for a device ADMZ could not talk to

Reconstructed from production's chat history and audit log (#443):

| time | what happened |
|---|---|
| 13:07 | An A1210 is registered via `register_discovered_device` (approved). No account row, no capture session. |
| 13:07 → 19:59 | Health reports `online`. Every surface — roster, device page, chat roster line, fleet counts — says the device is fine. |
| 19:59 | The operator asks a different question ("which devices have no baseline?") and finds it sideways. |
| 20:01 | A baseline capture needs credentials; only now does resolution fail and a capture card appear. |
| 20:02 | Credentials submitted; 11 facets captured. |

Two defects, and they are separate:

1. **There is no health state for "no credentials".** The vocabulary has `auth_failed` — *wrong* credentials — and nothing for *absent* ones. The sweep asks the registry for credentials (`admz/fleet/health.py:1730-1735`) inside a bare `except Exception` — the comment says *"missing creds is fine"*, but the catch also swallows a locked database file, a decrypt failure and Vault being down — and `probe_device`'s Tier-1 guard (`:1181-1186`, `credentials and credentials.get("password")`) falls through to Tier 2 (`:1580-1592`): TCP connect OK → `ONLINE`, `consecutive_failures=0`, `last_error=""`. FR-HLT-003 documents it (*"a device with no stored creds still yields an 'the IP is up' signal"*), and KL-HLT-004 explicitly declined to change it: *"'no credentials stored yet' is a different situation from 'this device doesn't speak VAPIX', and reclassifying it would relabel every device awaiting credential capture."* That sentence assumed "awaiting capture" is a short, visible interval. It was seven hours with no capture pending.
2. **Registration does not always leave a way back in.** Four paths add a device. Three resolve credentials eagerly at registration through `onboard_device_credentials`; the MCP `register_discovered_device` path (`admz/mcp/server.py:3905-3918`) calls it **directly** and, on `credentials_needed`, returns *"Device 'X' registered."* with no capture session — unlike `register_device` (`:2181-2198` → `_onboard_device` `:2259-2272`, which opens one). The REST discovery route (`admz/api/routes/discovery.py:78-125`) is registry-add only by design. And nothing re-resolves later: `onboard_device_credentials` has six callers, none scheduled and none in the sweep. When the chat's capture card auto-removes after five minutes (`chat.js:773`) and the session expires at ten, the device page has no "enter credentials" action for a device without an account (`web.py:402` requires one; `device_detail.html:788-806` only handles `needs_setup`). The operator has to trip over it.

### What every consumer of a health status does with a value it does not know

A new status touches every reader of `DeviceHealthStatus`, and the codebase's own history says what happens when one is missed (#357: `reachable_no_api` was *settled* and *needs attention* at once, both predicates individually right, and the T8516 was parked in the attention bucket with a counter that never moved). The readers:

| Consumer | Where | Today |
|---|---|---|
| the enum | `admz/fleet/health.py:170-209` | seven members |
| settled set | `_STABLE_STATUSES` `:222-228`, used at `:1761` | resets vs increments `consecutive_failures` |
| detection trigger | `admz/tasks/store.py:41-56` `event_for_status` | `online`/`limited_api` → `on_online`; `_fire_pending` (`health.py:1827-1841`) fires pre-authorised tasks |
| colour / label | `admz/api/templating.py:28-52` | guard test `tests/test_fleet_health.py:789` iterates the enum |
| site issue count | `templating.py:291-294` | anything not `online`/`limited_api`/`unknown` is an issue |
| roster bucket | `admz/api/templates/index.html:295-307`, `:326-328` | unknown value → grey, bucket `unknown` |
| device page | `admz/api/templates/device_detail.html:323-331`, `:788-806` | the only per-status CTA is `needs_setup`'s |
| REST / MCP counts | `admz/api/routes/health.py:76-78`, `admz/mcp/server.py:2065-2068` | two literal seven-key dicts — a drift pair |
| chat roster line | `admz/chatbot/context.py:190-194` | the model was told "online" for seven hours |
| demo readiness | `admz/demos/readiness.py:58` | `{"online","limited_api"}` counted as ready |
| spec | FR-HLT-002/003/007, KL-HLT-004, `user-stories/fleet-monitoring.md:15` | |

### Where ADR-0061 actually stands

ADR-0061 is listed as *Proposed*; it is three-fifths shipped. `#446` (slice 1: entry credentials become a list), `#447` (slice 2: try the list, create ADMZ's own account — gated) and `#449` (an unplanned slice 3: adopt an already-credentialed device onto the `admz` account in place) merged on 2026-08-17 (#449 in the small hours of the 18th). `credential-storage.md` FR-CRED-011 records it and states what is left: the promote checkbox (FR-CRED-012) and most-recently-successful ordering. FR-CRED-007's ordering change (issue slice 4) was also unshipped when this was written — `admz/provisioning.py` still preferred `fleet_settings.default_password` over a generated one; slice E shipped it on 2026-09-06, together with the MCP `provision_device` tool's own copy of the ordering. #405 (encrypt at rest) is closed and the list is store-encrypted (`admz/setting_policy.py:210-215`) with read-time migration; **no "single pair → list" migration remains** — slice 1 chose to read the legacy pair as entry #1 (`admz/entry_credentials.py:141-147`).

Two facts the issue bodies do not say:

- **There is no operator-facing writer for the entry list.** `add_entry_credential` and `describe` (`entry_credentials.py:168-231`) have no callers outside tests; the Fleet Settings page lists keys generically with no edit form. The only ways to populate the list today are `python -m admz settings set entry_credentials '<json>'` and the unbuilt promote checkbox. Production's effective list is therefore the legacy pair `[operator/<pw>]`, which ADR-0061 already measured resolves nothing on this fleet.
- **The lockout measurement ADR-0061 required has not happened,** and the atlas holds no lockout knowledge (a repository-wide search for lockout/brute-force terms finds one unrelated ACS log enum). FR-CRED-013's cap of three is, in its own words, *"a conservative guess … not a measurement"*.

### Why the two issues are one design

#443's new state is the health-side projection of every onboarding exit that leaves no account row — every `credentials_needed` exit (`onboarding.py:164-191`, `:369-374`, `:477`), `approval_required` (`:304-324`, `:423-441`) and `provision_failed` (`:353-354`). It is reached *after* the entry list was tried once at registration, and it persists until an account row exists. #411's remaining slices change how a device *leaves* that state (promotion widens what the next registration tries; ordering and the bound change what one pass costs). Designed apart, #443's "resolve at registration" half would be written against a loop #411 is about to reorder, and #411 would have no visible state for "every entry failed". One state machine; serial PRs.

## Decision

### 1. `no_credentials` is a health status — not a separate field

**Semantics:** *registered, the host answers TCP, and ADMZ holds no usable stored credential* — "usable" being the existing Tier-1 predicate (`credentials.get("password")`, so an empty password counts as none). It is **settled** (in `_STABLE_STATUSES`: the counter does not climb — #138), it stamps `last_seen_online` (the host answered — FR-HLT-002's reachability clock), it is **amber** and in the **attention** bucket, and `event_for_status` maps it to `None` (no `on_online` task may fire for a device ADMZ cannot authenticate to). Tier 2 is also reached with credentials present when the catalog or executor is unavailable (`health.py:1183-1191`); the new value keys on credential absence, not on "Tier 2 was reached", so those cases stay `online`.

Three edges of the predicate, decided here so slice A does not decide them by accident:

- **Absence is something the registry *says*, not something a lookup *fails* to say.** `AccountNotFoundError` / `DeviceNotFoundError` mean no credential; any other exception from `get_credentials` (a locked database, a Fernet decrypt error, Vault down) is a lookup failure, and the sweep keeps the device's previous record with `last_error="credential lookup failed: …"` — or files `unknown` when there is none. Today's bare `except Exception` would otherwise turn every backend hiccup into a fleet of false amber, which is #357's shape with a new colour.
- **Only the `default` account counts.** In-place adoption keeps the pre-adoption credential under `recovery` (#449) and temporary users live under `at_*`; both are invisible to the predicate, exactly as they are to the Tier-1 guard today, and the device-page action targets `default`. "Usable" means a non-empty password: the executor's bearer method falls back to `password` and no registry writer stores a `token`, so for this registry there is no other kind of usable credential.
- **A factory-default unit is `needs_setup`, not `no_credentials`.** Today `needs_setup` is produced only inside Tier 1, which a device without a password never enters — so a fresh camera with no account row would read `no_credentials` and be offered a capture form for a password it does not have. Onboarding already reads `systemready` *unauthenticated* to detect factory-default (`onboarding.py:283-286`), and the op needs no credential by design (FR-HLT-003). Tier 2 therefore asks it the same way when there is no usable credential and a catalog and executor are available: `needsetup=yes` → `needs_setup`, whose CTA and `on_needs_setup` deferred-recovery trigger already exist and could otherwise never fire for a device without an account row; anything else → `no_credentials` (the host answered) or `unreachable`. One unauthenticated request per sweep for a device in S1 — the request Tier 1 would have made.

**Why a status, not a field.** A separate `credential_state` column would leave every consumer in the table above still needing a change, and would give each a *two-variable* rule — exactly the shape #357 showed fails. The enum already carries credential facts (`auth_failed`, `needs_setup`); #443 asks for a value that is *never* `online`. **Name:** `no_credentials`, mirroring `auth_failed`; `credentials_needed` is rejected because it is onboarding's wire status (`onboarding.py:91`) and the two would be read as the same thing by different callers.

### 2. The credential state machine

States are per device on the credential axis; the health status is the projection after the next sweep.

| # | State | Invariant | Health | Operator sees | Leaves it by |
|---|---|---|---|---|---|
| S0 | Unregistered | no device row | — | — | any of the four register paths → S1; on three of them onboarding runs synchronously |
| S1 | **Unresolved** | device row, no usable `default` account | **`no_credentials`** | roster label "No credentials", attention count, device-page **Enter credentials** action, chat roster line | onboarding at registration → S2/S3/S4/S5; capture submit → S4; operator `onboard_device` / `POST …/onboard` re-run → same fan-out |
| S1a | Unresolved, capture offered | S1 + a pending capture session (TTL 600 s) | `no_credentials` | chat card / add-device redirect | submit → S4; expiry → S1 (the device-page action re-opens it) |
| S1b | Unresolved, approval pending | S1 + a `provision_device_credentials` confirm session | `no_credentials` | approval card in chat / `/confirm` | approve → the executor (`operations.py:1231`) re-runs onboarding in the approved context → S2 (an entry credential worked and `admz` was created), S3 (a factory-default unit was provisioned), or S1a when capture is still needed; session expiry → S1 (re-running `onboard_device` re-gates) |
| S2 | Managed on ADMZ's account | `default` = `admz`, generated password; the pre-adoption credential kept under `recovery` for in-place adoption | `online` / `limited_api` | normal | device password rotated → S5; delete → the orphan question (ADR-0061) |
| S3 | Managed on a borrowed credential | `default` = an entry credential (`ENTRY_CREDENTIALS_SAVED`), or the `root` account written by factory-default provisioning (`PROVISIONED`; its password source is slice E's business, not this table's) | `online` / `limited_api` | normal; purpose text says the `admz` account was not created | `onboard_device adopt=true` (gated) → S2 |
| S4 | Managed on a captured credential | `default` = what the human typed | `online` / `limited_api`; wrong → `auth_failed` | normal | promote (FR-CRED-012; the list grows, the device does not move); adopt → S2 |
| S5 | Credential rejected | account exists; two ops refuse (FR-HLT-008/010, #463) | `auth_failed` (unchanged) | "Auth failed", attention, **Enter credentials** action | capture (rotate) → S4; `onboard_device` re-run may repair a stale stored password → S2/S3 |

A factory-default unit sits beside this table, not in it: from S1's sweep the unauthenticated `systemready` read files it `needs_setup`, whose exits (gated provisioning, the deferred-recovery trigger) are unchanged.

Four rules the machine enforces:

1. **The only automatic device-touching transition is at registration, once.**
2. **The sweep classifies and never resolves** — with one existing, deliberate exception: a *pre-authorised* detection task (ADR-0037's `reprovision` handler on `on_needs_setup`, which calls `provision_factory_default`) is an approval deferred to a trigger, not a sweep decision, and stays. Re-running onboarding from a sweep would spray every entry credential at every S1 device every 60 s (NFR-HLT-002: the probe *never changes device state*; the lockout exposure of §6 multiplied by the fleet), would reach the account-write gate unattended (the ADR-0059 amendment's *"one approval becomes N widgets nobody sees"*), and would contradict ADR-0034's one-gate rule. Detection events stay as they are.
3. **Every S1 exit that writes an account passes ADR-0059's gate** (`onboarding.py:304`, `:423`) — unchanged.
4. **Promotion is a human form action**, audited as its own event, and never re-runs onboarding on other devices by itself (`entry_credentials.py:174-178`: *"Nothing here should be called as a side effect of a successful capture."*).

### 3. Registration always leaves a visible, re-openable capture path

- `register_discovered_device` routes through `_onboard_device` exactly as `register_device` does (`server.py:3911` → the one-line change), so a `credentials_needed` outcome opens a capture session and the response carries `capture_url`, `capture_token` and a message that says so.
- The device page gains **Enter credentials** for `no_credentials` and `auth_failed`: a `POST /device/{id}/credentials` route shaped like the existing rotate route (`web.py:372-435`) minus its account-must-exist requirement, binding the session to `account_id="default"` with `account_type="admin"` (the session default is `service`, which the rotate route avoids only by copying an existing account's type), performing the same-origin check `capture_submit` performs, and redirecting to `/capture/{token}`. Beside it, **Run onboarding** re-runs the gated `onboard_device` — for the device whose password the operator does not know but the entry list might. This is the durable affordance the five-minute card and the ten-minute session lack.
- The legacy approval executor `_action_register_discovered_device` (`operations.py:872-919`, kept for pre-2026-08-09 sessions) is left alone and noted.

### 4. Promotion (FR-CRED-012), as designed in ADR-0061, with the mechanics fixed

The capture session carries a `propose_promote` flag (default `False`); the form renders an **unchecked** checkbox whose label says what promotion does; a proposal renders as a hint and never pre-checks. On submit with the box ticked, `add_entry_credential` is called **after** the device credential is stored; `entry_credential.promoted` or `entry_credential.promotion_refused` (cap, posture) is audited with the username and device ids only — never the password — and a refusal never loses the capture. The Fleet Settings page renders `entry_credentials.describe()`: usernames, labels, the posture flag and the cap — the first operator view of the list. MCP `capture_credentials` may propose the flag; the flag reaching the store requires the form submission, never the tool argument.

### 5. The attempt bound now, the ordering after the measurement (FR-CRED-013)

The entry loop makes at most **3 entries × 2 ops = 6 credentialed operations** — a wrong entry costs two, the primary op and its corroborator (#149/#150). At the wire that is **up to 12 credentialed sends**: the executor re-sends an op once when the 401 challenge names a different auth method than the device profile (`vapix.py:693-696`), and onboarding hands every entry the same profile. Each Digest op also costs one *unauthenticated* challenge round-trip — whether Axis counts that as a failed login is exactly what decision 7 measures. The pass stops on first success and breaks on a `None` (unreachable) answer. The loop is not the whole pass: step 1 (`onboarding.py:199-204`) corroborates a *stored* credential before the loop, and a stale one costs the same two operations, so the honest per-pass maximum is **8 operations / 16 sends**. Nothing dedupes the two — an entry pair stored as the device's `default` account (the `ENTRY_CREDENTIALS_SAVED` fallback) is tried in step 1 and again in the loop once the device's password has changed; that pre-existing double count is #475.

The bound is enforced **where the attempt list is built, not only at storage**: `attempt_order()` returns at most `MAX_ATTEMPTS_PER_PASS`, the onboarding loop iterates it, and `describe()` reports it as *in use*, so what is tried and what the settings page says is tried cannot drift. FR-CRED-013 chose a storage-time cap so the settings page could never show six credentials while ADMZ tried three; that argument survives — but the CLI writer (`python -m admz settings set entry_credentials`) bypasses the cap because `_parse` never truncates, so without this the loop was unbounded by what one command can store. The bound is the cheap safety half and shipped first (slice C, no measurement needed). `attempt_order` sorting by most-recently-successful — with no history the legacy pair first, today's behaviour kept as the control — is the ceremony half: **slice F does not merge until the lockout behaviour has been measured on a spare Axis unit**, the measurement ADR-0061 asked for and nobody ran; FR-CRED-013 records the result, or its absence, in words.

### 6. FR-CRED-007: the generated password wins

`allow_fleet_default` defaults to `False`; an explicit `password=` is still honoured. The username stays `root`: ADR-0061's table says a factory-defaulted device gets `admz`, but whether an Axis unit accepts a non-`root` first account varies by OS version and is unmeasured — the password source changes, the username question waits for a measurement. _As shipped: the MCP `provision_device` tool has its own inline copy of the ordering (it does not call `provision_factory_default`) and generates too, on its factory-default path and its `force_change` rotation — the requirement is about the value written, not one function. The trade ADR-0061 accepted is now stated in FR-CRED-007: a device provisioned from factory default holds only its generated password, so after a database loss it is factory-reset and provisioned again._

### 7. One enum, one place

The two literal count dictionaries (REST `health.py:76-78`, MCP `server.py:2065-2068`) become `{s.value: 0 for s in DeviceHealthStatus}`, and the templates' `HEALTH` maps and both count dicts gain an **enum-iterating** test beside `test_fleet_health.py:789`'s for the colour map. Today only that one test walks the enum; the template and count tests are keyed on literal strings, so a member missing from `index.html` would pass every cited test and render grey "Unknown" in bucket `unknown` — #357's parking, again. A future status cannot be omitted from any of them.

### 8. What the chat model is told

`admz/chatbot/system_prompt.py:357-366` is where the model learns what `auth_failed` and `reachable_no_api` mean. It gains `no_credentials`: ADMZ never had a way in — offer `onboard_device` (which may gate) or `capture_credentials`; never "unreachable", never "wrong password". Without the rule the roster line would read as offline or as a rotated password, and the model would route to the wrong fix.

## What this does not do

- **Retire `default_username`/`default_password` into the list.** The legacy pair stays entry #1 (`entry_credentials.py`); since slice E it is no longer written to a factory-defaulted device, and folding it into the JSON list is a separate decision.
- **Back off the sweep on `auth_failed`.** Today an `auth_failed` device is re-probed with its bad credential every 60 s — systemready, the auth op and its corroborator: up to three failed authentications a minute, indefinitely, with no backoff. That is the larger standing lockout exposure, it predates both issues, and it gets its own issue rather than a paragraph here.
- **Fix drift's view of a credential-less device.** `snapshot/engine.py:684-692` reports it as `"unreachable"` — the same defect class in a different enum; its own issue.
- **Retry automatically after a promotion.** Each retry sprays and can raise a gate per device; the done page shows how many devices sit at `no_credentials`, and the operator re-runs `onboard_device` per device.
- **Give approval-pending (S1b) its own status.** The confirm session is already visible in chat and on `/confirm`; `probe_device` has no confirm-store handle; `no_credentials` covers it.
- **Migrate existing devices.** ADR-0061's rule stands: creating accounts on live devices as a deploy side effect is a decision, not a consequence.

## Decisions taken by default — the owner may override any before the slice that depends on it

| # | Question | Default taken | Depends on it |
|---|---|---|---|
| 1 | Eager or lazy resolution? | Eager at registration (three of four paths already do); the sweep never resolves; the outcome is made visible and re-openable | A, B |
| 2 | Admit a device with no credentials at all? | Admit; it is `no_credentials` from its first sweep. Capture does not need the device up, and the REST discovery route is add-only by design | A |
| 3 | Status name, colour, bucket | `no_credentials`, amber, attention, settled | A |
| 4 | Approval-pending as its own status? | No | A |
| 5 | Auto-retry the `no_credentials` devices after a promotion? | No; show the count | C |
| 6 | Entry-list cap and per-pass bound | Keep `MAX_STORED=3`; bound the loop at 3 entries × 2 ops (up to 12 sends) now, measured or not | C |
| 7 | **The lockout measurement** | **Needs the owner**: a spare Axis unit, `test_device_credentials` with four wrong passwords then the right one over Digest; record whether the right one is refused or delayed, and whether the anonymous Digest challenge counts as a failure. Slice F waits for it | F |
| 7a | Does the promote checkbox wait for the measurement too? | No: the per-pass bound (slice C) ships before it, the cap is three, and a human ticks the box knowing what it does — the exposure promotion adds is bounded and chosen | D |
| 8 | Sweep backoff on `auth_failed` | Separate issue (see above) | — |
| 9 | FR-CRED-007 username | `root` stays; the `admz`-on-factory-default question waits for a measurement | E |
| 10 | Fold `default_*` into the list? | No | — |

## Slices, in PR order

Serial, one worktree per PR (`orchestration.md`). None need to be open concurrently; shared files are listed so a rebase is mechanical.

**PR A — #443 defect 1: the `no_credentials` status.**
`admz/fleet/health.py` (enum; `_STABLE_STATUSES`; the sweep's credential lookup narrowed to `AccountNotFoundError`/`DeviceNotFoundError` → none, any other exception → previous record kept with `last_error="credential lookup failed: …"`; one `has_usable_credential` computed once and used at the Tier-1 guard and in Tier 2; Tier 2 asks `systemready` unauthenticated when there is no usable credential and files `NEEDS_SETUP` on `needsetup=yes`, else `NO_CREDENTIALS` with `last_seen_online=now`, `consecutive_failures=0` and a `last_error` naming the state; the docstring), `admz/tasks/store.py` (explicit `None` with a comment), `admz/api/templating.py` (amber, "No credentials"), `admz/api/templates/index.html` (bucket `attention`) and `device_detail.html` (map entry), `admz/api/routes/health.py` + `admz/mcp/server.py` (the comprehension), `admz/chatbot/system_prompt.py:357-366` (the rule in §8), `admz/demos/readiness.py` (the set is unchanged — a `no_credentials` demo device is now *not ready*, which is right and is a visible change under ADR-0046). Docs: FR-HLT-002/003/007/011, KL-HLT-004, `user-stories/fleet-monitoring.md`, `docs/MCP_TOOLS_REFERENCE.md:129-134` (the status values). Tests: `tests/test_fleet_health.py` (`:102` rewritten; a `TestNoCredentials` class on the `:741-800` and `:826-905` patterns; enum-iterating tests for both templates' `HEALTH` maps and both count dicts), `tests/test_tasks_store.py`, a demo-readiness row.

**PR B — #443 defect 2: registration always leaves a re-openable capture path.** _After A: the CTA keys on the `no_credentials` string A introduces._
`admz/mcp/server.py:3907-3918`, `admz/api/routes/web.py` (the new route: `account_type="admin"`, the same-origin check, 303 to the capture form; the **Run onboarding** action beside it), `admz/api/templates/device_detail.html` (the CTA; `NOTES` gains `credentials_needed`, `admz_account_created`, `approval_required`). Docs: `docs/MCP_TOOLS_REFERENCE.md` (`register_discovered_device` returns `capture_url`), `user-stories/device-onboarding.md`. Tests: `tests/test_survey_provisioning_gate.py:124-146` extended (assert `capture_url`; spy `capture_store.create_session`; control: `already_credentialed` opens none), a new web-route test (303 to `/capture/<token>`; session bound to `default`; 404 for an unknown device). Shares `mcp/server.py` and `device_detail.html` with A, in different regions.

**PR C — #411 FR-CRED-013, the safety half: the per-pass attempt bound.**
_As shipped (#473):_ `admz/entry_credentials.py` (`MAX_ATTEMPTS_PER_PASS = MAX_STORED`; `attempt_order()` slices to it and warns — once per pass, counts only — when the stored list is longer; `describe()` reports `in_use` and `max_attempts_per_pass` without warning), `admz/onboarding.py` iterates `attempt_order()` (the `None` break kept), the stale module docstring. Docs: FR-CRED-013 (the bound, stated at wire level: 6 operations / 12 sends in the loop, 8 / 16 per pass). Tests: the bound is pinned where it is built (`tests/test_entry_credentials.py`: a raw list of five → three tried, the legacy pair counts, `describe()` reports what is tried, an install at exactly the bound is not warned about, the warning carries no credential) and where it is consumed (`tests/test_onboarding.py`: one pass confirms at most the bound, stops at first success, stops when the device stops answering); `:133` keeps its meaning. The request-counting test row 17 first asked for was decomposed rather than written: "two ops per entry" is pinned by `tests/test_health_auth_aware.py` (a corroborator called twice fails three tests) and "one confirm per entry" by the onboarding tests; the executor's one re-send per op is `vapix.py`'s existing behaviour and **no test counts it** — row 17 says so.

**PR D — #411 FR-CRED-012: the promote checkbox, and seeing the list.**
`admz/api/capture.py` (`propose_promote` on the session and its column, with the ALTER guard pattern), `capture_form.html`, `capture_done.html`, `admz/api/routes/capture.py:179-262` (`promote: bool = Form(False)`; `add_entry_credential` after the device credential is stored; the two audit events; refusal keeps the capture), `admz/mcp/server.py` (`capture_credentials` schema + handler), `admz/api/routes/web.py` + `fleet_settings.html` (`describe()`). Docs: FR-CRED-012 📋 → ✅, `MCP_TOOLS_REFERENCE.md`. Tests: `tests/test_capture.py`, new `tests/test_entry_promotion.py`, `tests/test_doc_inventories.py`.

**PR E — #411 FR-CRED-007: the generated password wins.**
`admz/provisioning.py:180` (`allow_fleet_default=False`). Docs: FR-CRED-007. Tests: `tests/test_provisioning.py` — the fleet-default test inverted; the #185 `allow_fleet_default=False` handler test and the end-to-end unattended test unchanged. The `reprovision` detection handler already passes `allow_fleet_default=False`, so deferred reprovision does not change. _As shipped:_ also `admz/mcp/server.py` `_provision_device` (its own copy of the ordering — it does not call `provision_factory_default`), the `provision_device` tool description, the two reprovision UI strings that still said "from the fleet default password" (already untrue since #185), the chat system prompt, and the comments in `entry_credentials.py`, `setting_policy.py`, `onboarding.py` and `tasks/handlers.py` that described the old ordering. Tests: `tests/test_provisioning.py` — a configured fleet default is not written, the opt-in is the only way it is, an explicit password is honoured, no caller in the tree opts in; new `tests/test_provisioning_mcp_tool.py` — the tool generates with a fleet default configured, honours an explicit password, its `force_change` rotation generates too, and its description says so.

**PR F — #411 FR-CRED-013, the ceremony half: most-recently-successful ordering.** _Waits for decision 7._
`admz/entry_credentials.py` (`attempt_order` — it must sort **before** the slice to the bound, or success history can never pull a tail entry into the tried set; `note_success`; the timestamp lives inside the encrypted JSON for list entries and in a plain non-secret key for the legacy pair, with the `setting_policy.py` mask exemption and inventory entry), `admz/onboarding.py` (`note_success` after a success). Docs: FR-CRED-013 (the measurement or its absence, in words). Tests: `tests/test_entry_credentials.py:133` changes, `:53` stays as the control; `tests/test_setting_policy.py`.

Issue hygiene: #443 carries A and B; #411's body is updated to record slices 1–3 as shipped and to list C–F.

## Verification matrix

| # | Claim | Test | Control / mutation |
|---|---|---|---|
| 1 | No usable credential + TCP up → `no_credentials`, never `online` | `test_fleet_health.py::TestProbeTcpFallback` (`:102` rewritten) | mutation: Tier-2 verdict back to `ONLINE` → fails. Controls: credentials present + `catalog=None` → still `ONLINE`; the registry *raising* a backend error → the previous record kept, never `no_credentials` |
| 1a | A factory-default unit with no account row is `needs_setup`, not `no_credentials` | sweep test: no credential, `systemready` answers `needsetup=yes` unauthenticated → `NEEDS_SETUP`; the `on_needs_setup` trigger fires | mutation: skip the unauthenticated read → `no_credentials` → fails |
| 2 | An empty password is no usable credential | same class, `password=""` | mutation: key on `credentials is None` only → fails |
| 3 | `no_credentials` is settled and stamps reachability | `_STABLE_STATUSES` membership; sweep test seeded `consecutive_failures=3` → 0, fresh `last_seen_online` | mutation: drop from the set → fails (pattern `:757`) |
| 4 | It never fires `on_online` | `test_tasks_store.py::test_event_for_status`; sweep test with a pending `on_online` task, `claim_for_event` not called | mutation: add it to the `on_online` tuple → fails. Control: `limited_api` still fires |
| 5 | It is an attention state in the roster | regex on `index.html` asserting `bucket: 'attention'` (pattern `:779-787`) | mutation: `bucket: 'online'` → fails. Control: `limited_api` stays `online` |
| 6 | Every renderer and both count dicts know it | `:789` (walks the enum today) plus new enum-iterating tests for both templates' `HEALTH` maps and both count dicts | mutation: drop the member from `index.html`'s map → fails (today's `:893` is literal-keyed and would not notice) |
| 7 | The site issue count includes it | `build_nav` with a fake registry (fixtures in `tests/test_nav_sections.py`, `tests/test_web_tags.py`) | mutation: add it to the excluded tuple → fails |
| 8 | `register_discovered_device` on `credentials_needed` opens a session and returns `capture_url` | `test_survey_provisioning_gate.py:124` extended | mutation: restore the direct call → fails. Control: `already_credentialed` → no session |
| 9 | The device-page action opens a session for `default` with no existing account | new web-route test: 303; `get_session(token).account_id == "default"` | control: unknown device → 404; the rotate route still 404s without an account |
| 10 | The sweep never resolves credentials | sweep test on a `no_credentials` device with no pending task: the executor receives no credentialed request other than the unauthenticated `systemready`, and the registry sees no `add_account`/`update_account` | mutation: call `onboard_device_credentials`, `provision_factory_default` or `adopt_with_admz_account` from the sweep → fails. Control: a pre-authorised `reprovision` task on `needs_setup` still fires |
| 11 | Promotion happens only from the form | `capture_submit` with `promote=on` → `add_entry_credential` called and audited | negative control: session minted with `propose_promote=True`, submitted without the box → not promoted. Mutation: honour the session flag server-side → fails |
| 12 | Promotion is audited separately and never carries the password | audit-row assertion; `redact` check on details | mutation: put the password in details → fails |
| 13 | Cap and posture refusals keep the capture | 3 stored + promote → device credential saved, `promotion_refused` audited, done page says so; `prompt_always` → same | mutation: let `ValueError` propagate → 500 → fails |
| 14 | The credential ADMZ came in on still resolves after `admz` is created | new: `list_entry_credentials()` identical before and after `adopt_with_admz_account` (existing `test_onboarding.py:267` pins the neighbouring `recovery`-row rule for in-place adoption) | mutation: delete the legacy key after success → fails |
| 15 | Unapproved adoption leaves no account on the device | existing `test_onboarding.py:191` (mutation-verified in #447) | keep; cite |
| 16 | Most-recently-successful first; legacy first with no history | new ordering test; existing `test_entry_credentials.py:53` as control | mutation: return stored order → fails |
| 17 | One pass confirms at most `MAX_ATTEMPTS_PER_PASS` entries, two ops each, and stops on first success | _as shipped:_ `test_onboarding.py` (five stored → three confirmed; success at entry 2 → two confirms; `None` → stop) + `test_entry_credentials.py` (five stored → three in `attempt_order()`; the legacy pair counts; exactly at the bound logs nothing; the warning carries no credential); "two ops per entry" by `test_health_auth_aware.py`; the executor's re-send per op is **not counted by any test** | mutations: bound removed / raised / tail-not-head / `None` break → `continue` / `>` → `>=` / credentials in the warning / `describe()` warning / password in the repr → fail |
| 17a | A `no_credentials` demo device is not ready | `admz/demos/readiness.py` test: health `no_credentials` → `online: False` | mutation: add it to `_HEALTHY` → fails |
| 18 | No automatic migration of existing devices | existing `test_onboarding.py:245`; row 10 | — |
| 19 | This plan | `test_doc_inventories.py` (ADR linked from INDEX), `test_doc_links.py` | — |

## Consequences

- One more attention state, and a truthful one: a device in S1 is the one thing in the fleet the operator can fix in a minute, and today it is the one thing every surface calls fine.
- Every renderer changes once; the counts dictionaries change shape by construction rather than by hand.
- The chat model's roster line changes for those devices; with the §8 rule, a model that was told "online" now reads "no credentials" and routes to onboarding or capture without a baseline failing first.
- A demo on a device with no credentials stops counting as ready (ADR-0046) — visible, and right.
- The lockout bound is now a stated number (eight operations per pass: six in the entry loop, two for a stale stored credential — sixteen sends at the wire) with a stated dependency (decision 7) rather than an unmeasured guess defended as a limit.
- `register_discovered_device`'s response grows two fields; the MCP tools reference changes; `tests/test_doc_inventories.py` enforces that.

## What would falsify this

If devices sit at `no_credentials` for days — amber that nobody acts on — then the state was not the fix, routing was, and the next step is a detection event that raises the capture card again rather than a status that waits. And ADR-0061's own falsifier still stands: if operators never tick the promote checkbox after twenty adoptions, the list is ceremony and slice D's ordering is effort spent on a list of one.
