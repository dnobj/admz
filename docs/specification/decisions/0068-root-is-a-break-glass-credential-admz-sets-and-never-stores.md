# ADR-0068 — Root is a break-glass credential ADMZ sets and never stores: every device carries two accounts, and only ADMZ's own is kept

**Status:** Proposed — 2026-09-14
**Closes when shipped:** the remainder of #411 (FR-CRED-011/012 — ADMZ's own account, in practice)
**Amends:** [ADR-0061](0061-entry-credentials-and-the-admz-account.md) decision 3 (*"The entry credential is never deleted or rotated by ADMZ"* — narrowed) · [ADR-0064](0064-a-device-admz-cannot-authenticate-to-is-never-online.md) — reverses slice E's password ordering for `root`, moots decision 9, narrows §2 rule 3, and makes the S3/S4 state rows unreachable
**Relates to:** [ADR-0059](0059-gate-provisioning-at-the-decision-point.md) (account creation is the decision point — this adds one named exemption) · [ADR-0009](0009-oob-credential-capture.md) (the prompt this re-shapes) · [ADR-0034](0034-uniform-widget-gating.md) (one gate, no flat refusals) · [ADR-0010](0010-fernet-encryption.md) (what makes a stored fleet password safe at rest) · FR-CRED-003/007/011/012/013 and a new FR-CRED-014 · #185 / #326 / #199 (the exposure this knowingly reinstates) · #296 (shared vs per-device as first-class modes) · #165 (`add-user` is ungated)

_Plan-first per `process.md`: this document merges before any code. File:line references are against master `e27d34c`._

## Context

### What ADMZ actually does today, measured

Production, 2026-09-14 — **11 stored device accounts. Every one is `username=root`, `account_id=default`. There are zero `admz` accounts.**

| `purpose` | n |
|---|---|
| Provisioned by provision_device | 5 |
| Device onboarding — automatic resolution failed (a human typed it) | 4 |
| Auto-stored by credential probe | 1 |
| primary | 1 |

So `adopt_with_admz_account` — the function ADR-0061 was written to introduce, shipped in #447 — **has never successfully run on this fleet.** The owner found this the ordinary way: they enrolled an AXIS C8110 and watched ADMZ generate a 24-character password, write it to `root`, and store that as the device's credential.

ADR-0061 named the shape correctly ("fleet credentials get you in; ADMZ's own account keeps you in") and three of its five slices shipped. What did not happen is the part that shows up in the account table.

### Four paths add a credential, and only one implements the model

| Path | Code | What it stores |
|---|---|---|
| Factory default (`needsetup=yes`) | `onboarding.py:299-364` → `provisioning.py:171` | **`root`** + generated password, then **returns** (`:359-363`) — never reaches `admz` |
| Stored credential verifies | `onboarding.py:206-221` | nothing (correct) |
| An entry credential authenticates | `onboarding.py:389-501` → `adopt_with_admz_account` | **`admz`** — the intended shape, never exercised here |
| Nothing authenticates → the operator is prompted | `routes/capture.py:258-363` | **whatever the human typed**, unconditionally (`:311-321`) |

A fifth writer diverges further: MCP `_provision_device` (`mcp/server.py:4580`) carries its own inline copy of the add-user write with its own factory-default detector, stores whatever answers a legacy `root/pass` probe (`:4721`), stores a generated root password after its `force_change` rotation (`:4768`), and is **ungated** (`_DESTRUCTIVE_MCP_TOOLS = frozenset()`, `:238`).

### What the owner wants, and the reason that decides the design

Stated this session:

> *"I don't want the admz generated password to be the only credential on the device. So regardless of IF we can program admz user without root, we should always have root before we create admz."*

That sentence settles more than it appears to. It means the open question ADR-0064 decision 9 deferred — *does an Axis unit accept a non-`root` first account?* — **no longer gates anything**, because root is written either way. And it means root is not a leftover of how Axis initial setup works; it is a **deliberate second credential, known to a human, that survives the loss of ADMZ's database.**

Which is precisely the cost FR-CRED-007 currently documents and accepts:

> *"a device provisioned from factory default holds only its generated password, so after a loss of ADMZ's database the entry credentials do not get back into it — it is factory-reset and provisioned again."*

A known break-glass root password deletes that sentence. That is the gain, and it is the reason to accept the exposure in §"What this reinstates" below.

### Nothing has shipped, so there is no migration

ADMZ has not been released, and the owner has said they will re-onboard the existing devices by hand. ADR-0061 and ADR-0064 both carry a "do not migrate existing devices automatically" decision; this ADR does not need one, because there is no installed base to protect. **No migration slice exists.** The consequence worth knowing: re-onboarding an ADMZ-provisioned device rotates its root to the break-glass value (§8), which is how those 11 devices reach the target state instead of stranding a generated root password nobody holds.

## Decision

**Every device ADMZ manages carries two accounts. ADMZ writes `root` from a known fleet break-glass password, then creates its own `admz` account with a generated password — and stores only `admz`. A root credential is never stored per device.**

| | Lives on the device | Known to |
|---|---|---|
| `root` | yes | **the operator** — one fleet-wide value they can type into any camera |
| `admz` | yes | **ADMZ only** — generated per device, stored Fernet-encrypted |

### 1 · Root is written first, then `admz`, in one gated operation

On the factory-default path the order is fixed and both writes sit behind the single existing approval (`onboarding.py:315`): `add-user root` → mark `auth_method` → `add-user admz` (authenticated as root) → store `admz`. The gate's copy must name **both** accounts and say where the root password came from — `discovery/gated.py:114-117` already requires the card to name every write it authorises.

### 2 · The root password is a fleet setting, and it is break-glass

A new store-encrypted setting `fleet_root_password`. It is **not** LLM-writable: `setting_policy.py`'s deny-by-default plus `redact.py`'s name-shape predicate give masking, reveal-gating and MCP refusal from the name alone. Its purpose is human recovery, so the operator is expected to know it — that is the feature, not a leak.

### 3 · A root credential is never stored per device

Not on the factory-default path, not from the operator prompt, not as a fallback when something else fails. Two existing fallbacks therefore retire:

- `onboarding.py:490` stores the working entry pair as `default` when the `admz` write fails. The legacy pair's username defaults to `root` (`entry_credentials.py:163`) and ADR-0061 measured eight of nine production devices on `root`, so this is the forbidden case by construction. `ENTRY_CREDENTIALS_SAVED` stops being a success status.
- `RECOVERY_ACCOUNT_ID` (`onboarding.py:49`, written at `:271`) stashes the pre-adoption credential per device — a per-device root credential whenever the device came in on root. See §8.

### 4 · Only `admz` is stored, and a failed `admz` write stores nothing

If root is written and the `admz` create then fails, ADMZ stores nothing and returns `admz_account_failed`. The device reads `no_credentials` — amber, attention bucket, not demo-ready — and the way back in is the break-glass password. This is the owner's decision, stated as *"store nothing — the fleet setting is the way back,"* and it is projected honestly rather than papered over with a fallback.

This is strictly better than today's equivalent failure, where a store that fails after a successful write leaves a generated root password with **no copy anywhere** and only a factory reset recovers the device.

### 5 · No break-glass password configured means ADMZ refuses to provision

There are only three possible behaviours, and two are unacceptable: store the root password (violates §3), or generate-and-discard it (leaves a device nobody can ever log into — worse than today). So an unset `fleet_root_password` is a **hard precondition failure**: status `root_password_not_configured`, **zero device writes**, registry untouched. Setting one key becomes a setup prerequisite, which is acceptable only because nothing has shipped.

### 6 · The operator prompt offers exactly two outcomes, and neither stores the password for that device

When nothing ADMZ holds gets in, it asks — and the typed root password is used **once**, to authenticate, so ADMZ can create `admz`. In the owner's words the choice is:

> *"two possibilities: the provided root password is saved (added to fleet-wide list) or not. never saved for that device."*

So the form presents a **`required` radio group with nothing pre-selected** — *use it once and discard it* / *add it to the fleet entry list* — rather than a checkbox, because an unticked box is a silent answer to an either/or. FR-CRED-012's guarantee that promotion is never pre-checked is preserved and strengthened.

This requires the capture submit to do something it has never done: **talk to the device.** `capture_submit` performs zero device I/O today; its only effect is the registry write. The new flow authenticates (`fleet.health._confirm_credentials`, `strict=True`), then adopts (`provisioning.adopt_with_admz_account`) — the same two calls in the same order that `onboarding.py` already makes at `:409` and `:476`.

**Promotion is gated on authentication, not on storage.** Today it happens only after the device credential is stored (`routes/capture.py:339-345`). Under this ADR there is no device credential to store, so the gate re-points to the 2xx from the device: a refused password promotes nothing (promoting an unproven secret would spend two failed authentications against every future device forever), while a password that *worked* but whose `admz` write failed **does** promote if asked — it demonstrably authenticates, the operator chose it, and the entry list is then the route to retry.

### 7 · Storing nothing for the device is a normal outcome, not an error

Today a submission that stores nothing **is** a 500 (`routes/capture.py:323-334`, pinned by `tests/test_entry_promotion.py:233-246`). The two meanings are kept apart by splitting on a session `kind` rather than by weakening that check: the existing body moves verbatim into the `account` handler and keeps its 500; the new `root_adopt` handler has no `saved` list at all.

> For a root-adopt session, **200 means ADMZ finished and the page says what happened; 500 means ADMZ left an account behind that it cannot use.**

An unknown `kind` fails closed (410) — it must never fall through to the path that *stores* the password. Same posture as #397's unknown risk class.

### 8 · `RECOVERY_ACCOUNT_ID` retires, and in-place adoption converges on the same two accounts

`_keep_recovery_account`'s docstring is the real argument against simply deleting it: for a device whose stored password ADMZ generated, that row *"would be the only copy — exactly the loss a registry wipe would cause, arriving through the front door."* True, and §3 still forbids keeping it. The resolution is to remove the thing being preserved rather than the preservation:

- **Where ADMZ generated the current password** (it provisioned this device), rotate `root` to the break-glass value via `pwdgrp.cgi:update-user` *before* creating `admz`. The old value is then **invalidated, not lost** — nothing needs stashing.
- **Where a human supplied it** (entry list or capture), leave `root` alone. It is the operator's, it exists outside ADMZ, and this is exactly the case ADR-0061 decision 3 was protecting.

Provenance is an explicit boolean on the stored account, written by ADMZ's own provisioning path; absent means human-supplied, so the conservative branch is the default. **This is the narrowing of ADR-0061 decision 3:** ADMZ may rotate a credential it generated itself, because the reason for the rule — *"If ADMZ's database is lost, every generated `admz` password is lost with it"* — is precisely what the break-glass password removes.

### 9 · The root-adopt form's submit button is the ADR-0059 approval

`gate_scan_write` would otherwise raise a confirmation card for the decision the operator just made by typing the device's administrator password — the gate fatigue ADR-0034 names and ADR-0061 already cites when refusing a second prompt for adoption. The exemption is defensible on its own terms rather than on convenience: `POST /confirm/{token}`, the mechanism the gate resolves to, is authorised by **token possession alone and has no CSRF check at all** (KL-CRED-003). This form adds `check_same_origin`, a human typing that device's own admin password, and a button whose text names the write. It is strictly stronger than the card it replaces.

Two things follow and are deliberately recorded rather than left implicit: **ADR-0064 §2 rule 3** (*"Every S1 exit that writes an account passes ADR-0059's gate"*) gains a named exception, and the button's wording becomes load-bearing and gets its own test.

## What this reinstates, stated honestly

**ADR-0064 slice E removed exactly this, and the argument it removed it for is still true.** `provisioning.py:196-226` says a factory-defaulted peer — whose `needsetup=yes` claim is unauthenticated and whose identity is unverified — is the *least* appropriate place to prefer a shared secret, because *"a spoofed peer — a reassigned DHCP lease, ARP spoofing, the port a decommissioned camera vacated — walks away with a credential valid on every other device ADMZ manages"* (#185, #326, #199, #171/#292).

What "we never store it per device" changes about that: **nothing.** The wire exposure is identical. A spoofed peer still learns the value, and the value still unlocks human login on every device ADMZ has provisioned.

What it does change:

- the disclosed value unlocks **no device's `admz` account**, so ADMZ's own standing access to the fleet does not fall with it;
- recovery from disclosure is rotating **one fleet setting** (plus a re-provision pass), not touching the registry;
- the operator regains a way into a device after losing `admz.db`, which today requires a factory reset.

That is a real trade, not a neutral one, and it is accepted deliberately.

**One mitigation is required rather than optional.** The unattended `reprovision` detection handler (`tasks/handlers.py:388`) fires up to 24 hours later against whatever answers on that IP, with no human present, and is ungated by ADR-0059 design. It must **not** write the break-glass password — it defers to an attended flow, which `handlers.py:370-377` already names as the honest fix. An attended provision is a human looking at one device; the deferred handler is the case #326 describes, where *"the registry can end up believing it holds a working credential it never actually set."*

**#165 gets worse, and should be re-read.** `pwdgrp.cgi:add-user` is `risk_level: normal` → confirmation level `none` → ungated, while `remove-user` is `service-affecting`. This ADR adds a second add-user write per device and a root rotation. The gate that matters is onboarding's, not the operation's, so this is not a new hole — but the asymmetry #165 describes now covers more writes.

**#296 is partly answered and should be reconciled, not closed by this.** Its part 2 asks for shared-vs-per-device as explicit first-class modes; `fleet_root_password` *is* the shared mode arriving for real, for `root` only, with `admz` permanently per-device. Its part 1 (encrypt `default_password` at rest) is already done.

## What this does not do

- **Migrate anything.** Nothing has shipped; the owner re-onboards. No grandfathering, no one-shot conversion job.
- **Measure whether `admz` can be a factory-default device's first account.** ADR-0064 decision 9 is **moot**, not deferred — root is written either way.
- **Rotate the `admz` password.** ADR-0061 left rotation to its own ADR and that still stands.
- **Remove any account, on any device, ever.** The orphaned-`admz` question (ADR-0061, `q_70025d93`) is untouched.
- **Let the model choose the root password, or read it.** `fleet_root_password` is not in `LLM_WRITABLE_SETTING_KEYS`; FR-SEC-012's allow-set is unchanged.
- **Make the unattended reprovision path use the break-glass value** — see above.
- **Change what the generic capture does.** Password rotation and the device page's "Enter credentials" legitimately write a device credential; they keep `kind="account"` and behave exactly as today.
- **Claim the typed password is erased from memory.** The form says what is checkable — not written to the database, the logs, or the assistant's context — and stops there, because `rules/capture.py:62-74` already established that dropping a reference is not erasure.

## Decisions taken — the owner has settled the first five

| # | Question | Decision |
|---|---|---|
| 1 | Measure non-root-first before designing? | **No — irrelevant.** Root is set first on every device regardless (owner) |
| 2 | What is root *for*? | **Break-glass the operator knows** (owner) |
| 3 | What may the prompt do with the typed password? | **Two outcomes: fleet list, or discard. Never stored for that device** (owner) |
| 4 | `admz` creation fails after root is set? | **Store nothing** (owner) |
| 5 | Existing devices? | **Re-onboarded by hand; no migration** (owner) |
| 6 | `persist=False` flag, or split the function? | **Split.** `write_root_account` takes no `registry`, so "cannot store a credential" is a property of the signature |
| 7 | Status returned by a successful factory-default provision | **`PROVISIONED`, unchanged** — `operations.py:1309` reports `ok = status == PROVISIONED`, so changing it would report `success: False` to the operator who just approved it |
| 8 | Break-glass unset? | **Refuse, writing nothing** (§5) |
| 9 | `recovery` account | **Retire**; rotate instead where ADMZ generated the password (§8) |
| 10 | How does the capture session carry the new intent? | **A `kind` column**, defaulting to `account`, unknown values failing closed (§7) |
| 11 | Is the adopt synchronous? | **Yes, bounded at 45 s.** Async would have to park the typed root password somewhere — and the only durable somewhere is the SQLite capture store, which is the one thing this design exists to prevent |
| 12 | Is the form submit the gate? | **Yes**, as a named ADR-0059 exemption (§9) |

## Slices, in PR order

Serial — `provisioning.py` is shared by S1/S2 and `onboarding.py` by S1/S3, so no two may be in flight.

**S0 — this document**, plus `INDEX.md`, FR-CRED-003/007/011/012/013 amendments, a new FR-CRED-014, and FR-SEC-007a's encrypted-settings list.

**S1 — the core flow.** `setting_policy.py` (two one-line additions), `provisioning.py` (`FLEET_ROOT_PASSWORD_KEY`, `write_root_account`, `provision_factory_default` recomposed, `allow_fleet_default` removed), `onboarding.py` (the `:490` fallback and `RECOVERY_ACCOUNT_ID` retired, rotation on provenance, gate copy), `entry_credentials.py` (the break-glass value as a synthetic last attempt, so a partial failure is retryable), `tasks/handlers.py` (the deferred handler does not write it).

**S2 — collapse the MCP duplicate.** `mcp/server.py::_provision_device` routes through `_onboard_device` exactly as `_register_device` already does (`:3977-3982`), inheriting the gate, the `read_systemready` detector and the statuses in one edit; `force_change` retires.

**S3 — the operator prompt.** `api/capture.py` (`kind` + `outcome` columns via the `_MIGRATION_COLUMNS` pattern), `routes/capture.py` (the handler split), two new templates, `routes/devices.py` + `operations.py` + `mcp/server.py` (`reason_code`), `web.py` + `device_detail.html` (two distinctly-labelled actions).

## Verification matrix

| # | Claim | Test | Mutation that must fail |
|---|---|---|---|
| 1 | Root precedes `admz` | `sent[0].username == "root"`, `sent[1].username == "admz"` | swap or drop the root write |
| 2 | The break-glass value is sent and stored nowhere | absent from every account row and from `repr(result)` | `store_provisioned_creds(..., "root", break_glass)` |
| 3 | Only `admz` is stored | `set(accounts) == {"default"}`, `username == "admz"` | add a `root` or `recovery` row |
| 4 | Unset break-glass writes nothing | `execr.sent == []`, no account, `root_password_not_configured` | fall back to a generated root password — the cell that silently restores today's behaviour |
| 5 | A failed `admz` write stores nothing | both the provisioning and the entry-loop paths | restore `onboarding.py:490` |
| 6 | The success status still satisfies the approval executor | approved run → `success is True` | return `admz_account_created` → fails at `operations.py:1309` |
| 7 | The typed root password never becomes the device credential | including a raw-byte scan of the SQLite file (the NFR-CRED-001 pattern) | the old unconditional store at `routes/capture.py:311-321` |
| 8 | The device is authenticated before any write | `adopt_with_admz_account` not called on a refused password | skip the confirm → an unproven password reaches `add-user` |
| 9 | Promotion is gated on authentication | refused → nothing promoted; adopt-failed → promotion stands | move promote above the confirm, or below the adopt check |
| 10 | An unknown `kind` fails closed | 410, no account row | `else: treat as account` |
| 11 | The form never claims the typed password is stored, and the button names the write | regex the rendered template | reuse `capture_form.html` |
| 12 | The radios have no default and are `required` | regex both inputs | pre-select either option |
| 13 | Break-glass is never LLM-writable, and is encrypted at rest | explicit membership assertion, not only the parametrized round-trip | a key never added to the set cannot fail a parametrized test — this repo's vacuity trap |
| 14 | The MCP tool stores no root credential and is gated | no `(device, "root", …)` tuple; no approval → blocked, zero sends | restore `server.py:4721`; remove the gate |
| 15 | The deferred reprovision handler does not send the break-glass password | handler test with the setting configured | pass it through → fails |
| 16 | The AST guard still forbids entry credentials reaching a device write, and now pins which fleet key `provisioning.py` may read | `tests/test_provisioning.py:344` re-scoped both ways | resolve the value inside the function to dodge the check → the positive pin fails |
| 17 | This plan | `test_doc_inventories.py`, `test_doc_links.py` | — |

**A trap that must be cleared first.** `tests/test_provisioning.py:91,:108,:123,:137,:218` monkeypatch `fleet_settings.get` **key-blind** (`lambda k: "FleetPass123"`). Every one must become key-specific before any assertion here is trustworthy, or they silently *configure* the break-glass to that value and then legitimately send it.

**Manual, on the owner's authorised test device (192.168.1.141), factory-defaulted first**, since the browser half has no JS test tooling in this repo: provision with the setting set (two accounts on the device, one row in ADMZ, break-glass logs in by hand); provision with it unset (refused, nothing written); a wrong password at the prompt (form re-renders, token live, nothing promoted); the right one with each of the two choices; and a forced `add-user` failure (nothing stored, `no_credentials`, break-glass still gets in). `tests/e2e/MANUAL_root_adopt_tests.md`, on the `MANUAL_password_tests.md` pattern.

## Consequences

- Every managed device ends in one shape, reachable two ways, with a human-known way in that does not depend on ADMZ's database surviving. FR-CRED-007's factory-reset trade is deleted rather than restated.
- The fleet gains a shared secret that is genuinely secret-bearing recovery material. Backing up `admz.key` still matters; knowing the break-glass password becomes an operational responsibility.
- One setting becomes a prerequisite for provisioning at all, and its absence is a refusal rather than a silent fallback.
- The four credential-writing paths collapse toward one implementation; the MCP tool stops being a second, ungated, divergent provisioner.
- The capture surface acquires a second purpose and must stay visibly distinct from the first — the operator's mental model ("I am giving ADMZ the password") is identical in both cases while the outcome is not.
- ADR-0064's state machine loses S3 and S4 as reachable states: nothing stores a borrowed or typed credential any more. S2 becomes the only managed state.

## What would falsify this

If operators find they never know the break-glass password when they need it — it was set once by someone else, or rotated and not written down — then root is not break-glass in practice, it is a second generated secret with extra steps, and the honest answer is per-device generated root with an explicit export mechanism rather than a shared value. If the shared value leaks through a spoofed `needsetup` peer in real use, §"What this reinstates" was the wrong trade and the answer is attended-only provisioning, not a narrower fallback. And if the prompt's two-way choice is always answered the same way, the radio group is ceremony and one of the two outcomes should simply be the rule.
