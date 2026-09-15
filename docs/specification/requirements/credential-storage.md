# Requirements: credential storage

Where device credentials live, how they're encrypted, how they get
in, how they get out, and what's NEVER stored.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-CRED-001 — SQLite + Fernet (default backend) ✅
Account passwords stored encrypted with `cryptography.fernet.Fernet`
(AES-128-CBC + HMAC-SHA256). Key auto-generated on first run, stored
at `~/.admz/admz.key` with chmod 0o600 (Unix; best-effort on
Windows). Override via `ADMZ_KEY_PATH`. See
[ADR-0010](../decisions/0010-fernet-encryption.md).

### FR-CRED-002 — HashiCorp Vault (enterprise backend) ✅
Selected via `DEVICE_REGISTRY_BACKEND=vault`. Reads/writes to KV-v2
under `secret/data/devices/<device_id>/{device_info,accounts/<account_id>}`.
AppRole (`VAULT_ROLE_ID` + `VAULT_SECRET_ID`) or token
(`VAULT_TOKEN`) auth. Vault's own audit log + access policies apply.
See [ADR-0011](../decisions/0011-pluggable-backends.md).

### FR-CRED-003 — Out-of-band credential capture ✅
`capture_credentials(device_id, ...)` returns a one-time URL the user
opens in a browser to submit the password. The form submits directly
to the registry; the password **never enters the LLM's context, chat
transcript, or server logs**. See
[ADR-0009](../decisions/0009-oob-credential-capture.md).

Implementation: `admz/api/capture.py::CaptureStore` (SQLite, WAL,
per-call connections), `admz/api/routes/capture.py` (browser form +
JSON polling endpoints).

> **[ADR-0068](../decisions/0068-root-is-a-break-glass-credential-admz-sets-and-never-stores.md) adds a second kind of capture session — ✅ shipped 2026-09-15 (S3).** *"The form
> submits directly to the registry"* remains true of the `account` kind, which is
> every session any existing opener mints.
> A **root-adopt** session inverts it: the typed password is used once to
> authenticate, ADMZ creates its own `admz` account, and *that* is what reaches
> the registry — the typed password reaches it never. The two are separate
> handlers selected by a session `kind` (default `account`, unknown values
> refused), so this requirement keeps holding verbatim for every session that
> exists today. FR-CRED-014 carries the new one.

### FR-CRED-004 — Batch capture for fleet provisioning ✅
A single capture session can carry multiple `device_ids` so an
operator entering credentials once stores them across N devices.

### FR-CRED-005 — Active credential probing ✅
`test_device_credentials(host, username?, password?, passwords?)`
sends candidate creds to a device (no-auth → legacy `root/pass` → up
to 5 user-supplied passwords). Returns success/failure WITHOUT
echoing the working password. `store=true` saves to the registry on
success.

### FR-CRED-006 — Per-protocol auth method storage ✅
Detected auth methods (digest/basic/bearer) are stored in
`device_info["auth"] = {"http": ..., "https": ..., "scheme": ...}`
during `provision_device` / `test_device_credentials`. The executor
uses the right scheme per request. See
[ADR-0007](../decisions/0007-per-protocol-auth.md).

### FR-CRED-007 — Auto-provisioning ✅
`provision_device(host_or_device_id, password=...)`:
- Detects factory-default state → calls `pwdgrp.cgi:add-user` to
  create admin user, stores creds.
- Detects legacy default `root/pass` → stores creds (or rotates
  if `force_change=true`).
- Returns structured outcome; generated passwords are never echoed
  in the response.

Password source: explicit arg > 24-char generated, per device. The fleet
`default_password` is **never written to a device**: it is an entry credential
(FR-CRED-011) — an input for authentication on a device set up elsewhere.

> **This ordering was changed by [ADR-0061](../decisions/0061-entry-credentials-and-the-admz-account.md)**
> and shipped by **ADR-0064 slice E ✅ (2026-09-06)**. Until then it was
> *explicit arg > fleet `default_password` > generated*: preferring the shared
> fleet password was least appropriate exactly here — writing a brand-new
> account on a factory-default device — and #327 had already moved unattended
> reprovision to always generate. Now `provision_factory_default`'s
> `allow_fleet_default` defaults to `False` (an explicit `password=` is still
> honoured; `True` is an opt-in no caller passes, pinned by a test), and the
> MCP `provision_device` tool — which carries its own copy of the write and
> does not call that function — generates too, on its factory-default path and
> its `force_change` rotation. The username stays `root` until a measurement
> says an Axis unit accepts a non-`root` first account (ADR-0061's table says
> `admz`; unverified).
>
> The trade, stated plainly: a device provisioned from factory default holds
> only its generated password, so after a loss of ADMZ's database the entry
> credentials do not get back into it — it is factory-reset and provisioned
> again. The recovery control is therefore the one the README already
> demands: back up `admz.db` **and** `admz.key` together (README §Backup).
> Under the old ordering the fleet password on the device was a recovery route
> only when `default_username` was the account written (`root`); an install
> whose pair is `operator/…` never had one. #296 part 2 (shared versus
> per-device as a first-class setting) is where a deliberate shared mode
> would live.

> ⚠️ **The block above is superseded for `root`.** Its account of the fleet
> `default_password` is still correct and permanent; its account of *what is
> written to a factory-defaulted device*, and the database-loss trade it
> accepts, are not. Read the next block before acting on it.

> **[ADR-0068](../decisions/0068-root-is-a-break-glass-credential-admz-sets-and-never-stores.md) changes what is written and deletes the trade above — ✅ shipped
> 2026-09-14 (S1).** Measured on production 2026-09-14: **all 11 stored accounts are
> `root`/`default`; there are zero `admz` accounts** — so the factory-default
> path has been the fleet's only provisioner and it stops at `root`. Under
> ADR-0068 it writes **two** accounts: `root` from a new store-encrypted
> `fleet_root_password` fleet setting — operator-known **break-glass** — and then
> `admz` with a generated password, of which **only `admz` is stored**. A root
> credential is never stored per device.
>
> Two consequences for the text above. The sentence *"the fleet
> `default_password` is **never written to a device**"* stays true permanently:
> the root password is a **different** setting, and `default_password` remains an
> entry credential only. But the trade in the preceding block — *"after a loss of
> ADMZ's database the entry credentials do not get back into it — it is
> factory-reset and provisioned again"* — **is deleted**, because a human knows
> the break-glass password and can log into any provisioned device without ADMZ.
> That gain is the reason ADR-0068 knowingly reverses slice E for `root` and
> reinstates #185/#326's exposure of a shared secret to a `needsetup=yes` peer
> whose identity is unverified; the ADR states the exposure plainly rather than
> claiming per-device non-storage mitigates it (it does not — the wire exposure
> is unchanged; what changes is that the disclosed value unlocks no device's
> `admz` account). The unattended `reprovision` handler must **not** write it.
>
> ADR-0064 decision 9 — whether an Axis unit accepts a non-`root` first account —
> becomes **moot** rather than deferred: root is written first either way, because
> the owner's requirement is that ADMZ's generated password is never the device's
> only credential. `allow_fleet_default` is removed; an unset `fleet_root_password`
> makes ADMZ **refuse to provision**, writing nothing, rather than fall back to a
> generated-and-stored or generated-and-discarded root password. #296 part 2's
> "deliberate shared mode" is what `fleet_root_password` is.
>
> **As shipped (S1).** `write_root_account` takes no `registry`, so "this cannot
> store a credential" is checkable from the signature rather than from a boolean
> a caller might pass wrongly; `provision_factory_default` keeps its name and
> signature (three gate-test suites bind to it) and becomes the composition
> root → `admz` → store `admz`. Two refusals write nothing: `attended=False`,
> which is how the unattended `reprovision` handler is now stopped, and no
> break-glass configured. The success status stays `PROVISIONED` — `operations.py`
> reports `ok = status == PROVISIONED`, so renaming it would have told the
> operator who approved the write that it failed.

### FR-CRED-008 — Temporary device-side users ✅
`create_temp_credentials(device_id, permissions, ttl_seconds)`
creates an `at_<8 hex>` user on the device, returns the plaintext
(this is the one place plaintext **is** intentional — the whole point
is that the LLM uses these creds directly for a brief window).

Max 3 temp creds per device. TTL 60–3600s. Background loop cleans
expired ones via `pwdgrp.cgi:remove-user`.

### FR-CRED-011 — Entry credentials get in; the `admz` account stays in 🚧
A fleet credential authenticates ADMZ to a device it does not yet manage. It
is **never** stored as that device's ongoing credential. See
[ADR-0061](../decisions/0061-entry-credentials-and-the-admz-account.md).

- **Entry credentials are a list of `(username, password)` pairs.** Usernames
  vary by setup era as much as passwords do — production today has
  `default_username = 'operator'` while none of its nine stored device
  accounts use it.
- **ADMZ creates an `admz` administrator account per device**, with a password
  generated for that device and stored encrypted. That is the ongoing
  credential.
- **ADMZ never deletes, rotates or disables the account it authenticated
  with.** If ADMZ's database is lost, the entry credential is the only way
  back in — which makes the entry list recovery material and #405 (encryption
  at rest) a prerequisite, not an adjacent cleanup.
- **Creating the account is a gated write.** `pwdgrp.cgi:add-user` with
  `group=root` is ADR-0059's decision point. This path reaches it on devices
  that are *not* factory-defaulted, which ADR-0059 did not cover; adoption
  must not create an account merely because a password answered.
- **Attempts are bounded.** Stop on first success, order by
  most-recently-successful, cap the count. N credentials is N failed
  authentications, and Axis brute-force behaviour varies by model and
  firmware — measure once against a spare device before shipping.

**Shipped (#411 slices 1–2):** `admz/entry_credentials.py` — the list, stored
as one Fernet-encrypted `entry_credentials` fleet setting, with the legacy
`default_username`/`default_password` pair read as entry #1 so an existing
install keeps working with no migration step. Storage is capped at three
(FR-CRED-013). Onboarding step 3 walks the list; the first credential that
authenticates is used to create ADMZ's own `admz` account
(`provisioning.adopt_with_admz_account`), and *that* is stored. If the account
write fails but the entry credential works, the entry credential is stored under
a status and purpose that say so — a managed device on a shared credential beats
an unmanaged one, but nobody should read it as the good path.

**The account write is gated at the same decision point as factory-default
provisioning**, with the same approval — not a second one. An operator who
approved "onboard this device" approved ADMZ setting up its own access; a
second prompt for the same decision is the gate fatigue ADR-0034 names. The gate
sits after a credential is *confirmed to work*, not before the loop: an add that
falls through to capture must not raise a widget for an account write that never
happens.

**Shipped since (#411 slice 3, #449):** adopting an already-credentialed device
onto the `admz` account in place, keeping the credential it came in on.

**Not yet shipped**, re-planned in
[ADR-0064](../decisions/0064-a-device-admz-cannot-authenticate-to-is-never-online.md)
as slices C–F together with #443: the per-pass attempt bound (FR-CRED-013,
slice C — shipped 2026-09-06), the promote checkbox (FR-CRED-012, slice D — shipped 2026-09-06),
FR-CRED-007's generated-wins ordering (slice E — shipped 2026-09-06), and most-recently-successful
ordering (FR-CRED-013, slice F — waits for the lockout measurement). Two facts to hold while reading the
rest: the list has two writers — `python -m admz settings set entry_credentials`
and, since slice D, the capture form's promote checkbox — and no settings-page
editor, so an install's effective list is its legacy pair until someone
promotes; and the lockout measurement ADR-0061 asked for has not been run.

Existing devices are **not** migrated automatically. Creating accounts on nine
live devices as a deploy side effect is a decision, not a consequence.

**[ADR-0068](../decisions/0068-root-is-a-break-glass-credential-admz-sets-and-never-stores.md) amends three of the statements above (📋, not yet shipped).**

- **The rotation rule is narrowed.** *"ADMZ never deletes, rotates or disables
  the account it authenticated with"* becomes: ADMZ never touches a credential a
  **human** supplied, and **may rotate one it generated itself**. The rule's own
  stated reason — *"If ADMZ's database is lost, the entry credential is the only
  way back in"* — is exactly what the break-glass root password removes. So on
  in-place adoption of a device ADMZ provisioned, `root` is rotated to the
  break-glass value before `admz` is created, and the per-device `recovery`
  account (#449) retires: the old value is **invalidated, not lost**, so there is
  nothing left to preserve. Deletion and disabling remain forbidden everywhere.
- **The borrowed-credential fallback retires.** *"If the account write fails but
  the entry credential works, the entry credential is stored under a status and
  purpose that say so"* — ADMZ stores **nothing** instead. The pair's username
  defaults to `root`, so storing it is precisely the per-device root credential
  ADR-0068 forbids. The device reads `no_credentials` (amber, attention, not
  demo-ready) and the break-glass password is the way back in. This reverses a
  written trade — *"a managed device on a shared credential beats an unmanaged
  one"* — deliberately: the operator's break-glass credential is not ADMZ's to
  keep. `ENTRY_CREDENTIALS_SAVED` stops being a success status.
- **Migration is not deferred, it is absent.** *"Existing devices are **not**
  migrated automatically"* stands, and ADR-0068 needs no migration decision at
  all: ADMZ has not shipped, and the owner re-onboards the existing devices by
  hand. Re-onboarding an ADMZ-provisioned device rotates its root to the
  break-glass value, which is how those 11 devices reach the target shape rather
  than stranding a generated root password nobody holds.

### FR-CRED-013 — At most three entry credentials, or none at all 🚧
The list is capped at **three** where it is stored, so what the settings page
shows is what exists; since ADR-0064 slice C the device-facing loop is bounded
separately to the same number (below), and `describe()` reports both what is
stored and what is tried, so the page can never show six credentials while ADMZ
tries three. The legacy `default_username`/`default_password` pair occupies a
slot, because it is one of the credentials that gets tried.

Three began as a conservative guess. The measurement ADR-0061 asked for is now
done (**Lockout measurement**, below): on the device tested there is no
failed-login lockout at all, only a rate throttle ADMZ runs some 400× under. So
three stands — conservative against a measured floor, no longer a guess defended
as if it were one.

**The per-pass attempt bound (ADR-0064 slice C) ✅.** The entry loop makes at
most **3 entries × 2 ops = 6 credentialed operations** — a wrong entry costs
two, the primary auth-required op and its corroborator (#149/#150) — and at the
wire **up to 12 credentialed sends**, because the executor re-sends an op once
when the 401 challenge names a different auth method than the device profile;
each Digest op also costs one unauthenticated challenge round-trip. The loop is
not the whole pass: onboarding first checks a *stored* credential, and a stale
one is corroborated the same way, so one pass is at most **8 operations /
16 sends**.

✅ **(ADR-0065 decision 4, #475 — shipped 2026-09-07.)** A pair the
stored-credential check saw **refused** is skipped when the loop reaches it:
the maximum is unchanged, but no pair is put to a device to **authenticate**
twice in one pass. A refusal only — an unanswered check says nothing about the
credential, and skipping on silence would drop a pair that works. (Step 2's
`systemready` read still carries the stored credential; that op is auth-free by
design but, unlike the health sweep's, its auth is not forced off — #479.)

The
pass stops on the first success and breaks on an unreachable (`None`) answer. The
bound (`MAX_ATTEMPTS_PER_PASS`, equal to the storage cap) is enforced **where
the attempt list is built** — `entry_credentials.attempt_order()`, which the
onboarding loop iterates and which `describe()` reports as *in use* — not only
at storage: the storage-time cap keeps the settings page honest, but the CLI
writer bypasses it (`_parse` never truncates), so without this one command
could make a pass unbounded. A list stored over the bound is warned about —
once per pass, counts only, never from the settings page's read — and its tail
is never tried; `describe()` also reports `max_attempts_per_pass`. This half
needed no measurement and shipped first.

**Most-recently-successful ordering (ADR-0064 slice F) 📋.** `attempt_order`
tries the most-recently-successful credential first; with no history the
legacy pair is first, which is today's behaviour and the control. This half was
gated on the lockout behaviour being measured (ADR-0064, decision 7); that
measurement is now done and recorded below, so the gate is lifted — slice F is
free to plan and build, and its 📋 marks only that it has not yet shipped.

**Lockout measurement (ADR-0064 decision 7) — 2026-09-09.** Run directly over
Digest against a live fleet device — an AXIS P3408-VE on AXIS OS 12.10.68 — not
through ADMZ, with owner authorisation to fail logins deliberately and to read
settings and logs; the account was left clean afterwards (final
correct-credential probes `200`, nothing on the device changed). It answers both
halves of decision 7:

- **The right credential is never refused or delayed.** Across ~65 deliberate
  wrong-password attempts — 5 then 20 in sequence, then 40 at once — every wrong
  attempt drew a clean `401` at ~210 ms and the correct password answered `200`
  immediately (~0.3 s) each time. There is **no cumulative failed-login lockout**
  on this device: nothing accumulates, nothing stays locked.
- **The anonymous Digest challenge does not count as a failure.** An
  unauthenticated request draws a `401` *challenge*, not a *failure* — 80 of them
  at ~41/s registered nothing. Only a completed wrong-credential attempt counts,
  so the one unauthenticated challenge round-trip each Digest op costs carries no
  lockout weight; only the authed leg with a bad password does.
- **The only login-abuse protection is a rate throttle — a forced delay, not a
  lockout.** Axis labels it "Prevent brute-force attacks"; it is the
  `root.System.PreventDoSAttack` group, one-to-one with the web-UI panel:
  `ActivatePasswordThrottling=On`, block for `DoSBlockingPeriod=10` s once auth
  failures exceed `DoSPageCount`/`DoSSiteCount=20` per
  `DoSPageInterval`/`DoSSiteInterval=1` s. The block is a fixed 10 s and
  self-clears. No cumulative-lockout parameter exists anywhere in the device's
  1,440-line parameter tree, and no brute-force / login-delay / fail2ban entry
  exists in its 64-endpoint API-discovery list.
- **A single well-behaved client cannot reach the threshold.** 40 concurrent
  wrong-password Digest auths completed at ~6/s — the device paces its own CGI
  throughput — well under the 20/s trip line, so the throttle never engaged. It
  is built for a connection-reusing flood, not a normal client.

**What it means for the numbers here.** ADMZ's worst case is a device stuck in
`auth_failed`, re-probed every 60 s at 2–3 failed auths — about **0.05
failures/s, ~400× below this device's 20/s trip line**. ADMZ cannot trip even
the rate throttle; if it somehow did, the cost is a self-clearing 10 s delay,
never a lockout. The cap of three and ADR-0065's 30-minute hold ceiling
([FR-HLT-012](fleet-health.md)) are confirmed conservative on this device —
belt-and-suspenders, not load-bearing.

**Caveat — one device.** This is a single older platform. AXIS OS also ships a
separate, escalating **"Brute force delay protection"** (fail2ban/PAM-backed,
web UI → System → Security) that *does* act on cumulative failures; it is off by
default and absent from this model's API set, but a newer device on which an
operator has enabled it is the one residual case — and it is exactly what
ADR-0065's escalating hold absorbs under any answer. A second measurement on a
newer model carrying that feature would close the caveat.

An installation may also **store none and prompt every time**
(`entry_credentials_prompt_always`). That is a posture, not an empty list:
adds are refused while it holds, and any value already stored is ignored rather
than used — so turning it on stops ADMZ using a credential immediately, with
nothing to delete first. Nothing is deleted on the operator's behalf, so turning
it off restores what was there.

It costs less than it appears. Nothing requires a stored fleet password: since
ADR-0064 slice E `provision_factory_default` never writes one (the generated
password wins, FR-CRED-007), as the deferred reprovision path has since #185.
The only thing the posture gives up
is that adopting an **already-set-up** device always asks a human — which is
precisely what it is choosing.

**[ADR-0068](../decisions/0068-root-is-a-break-glass-credential-admz-sets-and-never-stores.md) adds one attempt and falsifies the paragraph above (📋, not yet
shipped).** After ADMZ sets `root` from the break-glass password, a pass that
fails partway leaves a device whose root password ADMZ *holds* but
`attempt_order()` does not know — so a retry would fail even though a working
credential is configured. The break-glass value therefore becomes a **synthetic
attempt, tried last**, and `describe()` reports it, so the settings page cannot
understate what ADMZ puts to a device. The measured lockout floor below makes
the extra attempt free: ADMZ runs some 400× under the only protection that
exists on the device tested.

And *"Nothing requires a stored fleet password"* stops being true. Under ADR-0068
provisioning a factory-defaulted device **requires** `fleet_root_password` and
refuses without it. The `entry_credentials_prompt_always` posture survives — it
governs the **entry list**, which is a different setting — but its cost is no
longer "nothing": an installation running that posture still has to set a root
password, or it cannot provision a factory-default device at all.

### FR-CRED-012 — Captured credentials may be promoted to the entry list ✅
When nothing authenticates, the capture flow (FR-CRED-003 / ADR-0009) offers an
opt-in *"also try this on other devices."*

This is a **scope promotion**, not a save: the secret becomes something ADMZ
will offer to every device in the fleet. So it defaults **unchecked**, the label
says what it does rather than "save", and the promotion is audited as its own
event, separate from the capture.

MCP callers may **propose** the flag; the capture *form* renders the proposal
as a hint (the chat capture card does not show it) and the human decides. The
person typing the secret is the only one
who knows whether it is safe to spray at the whole fleet, and that judgement
cannot live in a tool argument.

**Mechanics (ADR-0064 slice D, shipped 2026-09-06).** The capture session carries `propose_promote`
(default `False`); the form renders an unchecked checkbox whose label says what
promotion does, and a proposal renders as a hint that never pre-checks it. On
submit with the box ticked, the entry is added **after** the device credential
is stored; `entry_credential.promoted` or `entry_credential.promotion_refused`
(cap, posture) is audited with the username and device ids only — never the
password — and a refusal never loses the capture; the done page says which
happened. The Fleet Settings page renders the list's `describe()` (usernames,
labels, posture, cap; every stored entry marked *tried* or *stored, never tried* against slice C's bound; the page renders without the list if reading it fails) — the first operator view of it. A failure inside the promotion itself (anything but the cap or the posture) is logged and reported as a refusal, never a 500 — the capture has already succeeded and consumed its token; audit rows carry the signed-in principal when there is one. The flag reaching the
store requires the form submission, never the tool argument.

> **[ADR-0068](../decisions/0068-root-is-a-break-glass-credential-admz-sets-and-never-stores.md) re-points the ordering rule (📋, not yet shipped).** Promotion happens
> *"**after** the device credential is stored"* today. A root-adopt session
> (FR-CRED-014) stores no device credential, so promotion is gated on the
> **device authenticating** instead: a password the device refused promotes
> nothing — promoting an unproven secret would spend two failed authentications
> against every future device forever — while a password that authenticated but
> whose `admz` write then failed **does** promote if the operator asked, because
> it demonstrably works and the entry list is then the route to retry. Everything
> else is unchanged: never pre-checked, audited as its own event with the
> username and device ids only, a refusal never loses the capture, and the flag
> reaching the store still requires the form submission.

### FR-CRED-014 — A root password ADMZ is given is used once and never becomes the device's credential ✅
When nothing ADMZ holds authenticates, it asks the operator for the device's
administrator password — and that password is **never stored as that device's
credential**. See
[ADR-0068](../decisions/0068-root-is-a-break-glass-credential-admz-sets-and-never-stores.md).

- **The fleet root password is break-glass.** `fleet_root_password` is a
  store-encrypted fleet setting (FR-SEC-007a) holding the password ADMZ writes to
  `root` on a device it provisions. It is deliberately **not** per-device, so the
  operator knows one value that logs into any provisioned device independently of
  ADMZ's database. It is not LLM-writable — FR-SEC-012's allow-set is unchanged —
  and the name carries `password`, so masking, reveal-gating and the MCP refusal
  follow from the name-shape predicate (FR-SEC-007) with no new special case.
- **The prompt offers exactly two outcomes**, as a `required` radio group with
  **nothing pre-selected**: add the typed password to the fleet entry list
  (FR-CRED-012), or discard it. Not a checkbox — an unticked box is a silent
  answer to an either/or. In **neither** case is it stored for that device.
- **Submitting performs device I/O**, which no capture session does today: ADMZ
  authenticates the typed pair strictly, then creates its own `admz` account and
  stores that. The sequence is synchronous and **bounded**; on expiry the result
  is reported as unconfirmed, never as success, and nothing is stored. It is
  synchronous on purpose — parking the typed root password between a POST and a
  worker would mean persisting it, which is the one thing this requirement exists
  to prevent.
- **Storing nothing for the device is a normal outcome, not an error.** Today a
  submission that stores nothing *is* a 500. For a root-adopt session, **200
  means ADMZ finished and the page says what happened; 500 means ADMZ left an
  account behind that it cannot use.** The token stays live for any failure that
  never touched the device, and is consumed once the `admz` write is attempted.
- **The form must not overstate what is kept.** It may not reuse the existing
  *"These credentials are stored encrypted"* copy, which is false here. It says
  what is checkable — not written to ADMZ's database, its logs, or the
  assistant's context — and stops short of "erased from memory". It also states
  that the operator's own password keeps working: ADMZ never changes, disables or
  deletes it.
- **The submit button is the approval** (one named ADR-0059 exemption), so its
  text names the write. This is stronger than the confirmation card it replaces:
  `POST /confirm/{token}` is authorised by token possession alone with no CSRF
  check (KL-CRED-003), while this form adds a same-origin check and a human
  typing that device's own administrator password.

### FR-CRED-009 — Device passwords are never displayed; no LLM retrieval ✅
Device-account passwords are **never displayed** through any web/REST
surface — the account page shows only a "stored · never displayed" lock,
and the device-credential reveal endpoint (`GET /api/devices/{id}/credentials`)
and its `web_reveal_credentials_enabled` flag were **removed entirely**.
ADMZ reads the plaintext from the secrets backend only at execution time
to reach the device.

No credential-retrieval flag remains. The `get_credentials` MCP tool was
removed (CR-1), and its `tool_get_credentials_enabled` flag was deleted
(#151) after its only surviving effect turned out to be an anonymous
bypass of the fleet-setting reveal gate. `create_temp_credentials`
(a short-lived device-side account) is the ad-hoc LLM access path. See
[ADR-0020](../decisions/0020-protected-fleet-settings.md).

Reveal of **fleet-level** secrets (admin values like API keys, NOT device
passwords) is a separate surface — `GET /api/fleet/settings/{key}/reveal`,
gated by membership in `ADMZ_REVEAL_GROUPS`. Anonymous callers are always
denied.

### FR-CRED-010 — Per-protocol detection on every probe ✅
`_detect_auth_schemes()` parses `WWW-Authenticate` from 401 responses
on both HTTP and HTTPS. Result stored as a dict per FR-CRED-006.

## Non-functional requirements

### NFR-CRED-001 — Plaintext never in raw DB bytes ✅
Tested in `tests/test_sqlite_backend.py::test_password_is_encrypted_at_rest`
— the SQLite file is inspected for the plaintext password string,
which must not appear.

### NFR-CRED-002 — Audit log records every credential access ✅
Internal credential reads (`registry.get_credentials`, used by the
executor/plan engine at execution time) and fleet-setting reveals
(`GET /api/fleet/settings/{key}/reveal`) write `audit_log` rows with the
authenticated principal as requester, the resource, success/failure, and
error message. (The device-credential reveal endpoint itself was removed —
device passwords are never returned over web/REST.)

### NFR-CRED-003 — Capture tokens are 256-bit single-use ✅
`secrets.token_urlsafe(32)`. SQLite `UPDATE … WHERE status='pending'`
prevents double-consumption.

### NFR-CRED-004 — Capture / confirm endpoints rate-limited ✅ (Phase 4 stretch)
10-burst + 10/minute sustained per-IP, configurable.
[reliability.md](reliability.md), [security.md](security.md) KG-SEC-005.

## Known limitations

### KL-CRED-001 — Fernet key has no rotation path ⚠️
Lose `~/.admz/admz.key` → lose all credentials. Documented in README;
no master-key wrap (see [ADR-0010](../decisions/0010-fernet-encryption.md)
"Negative consequences").

### KL-CRED-002 — No automatic credential rotation ⚠️
Manual rotation works via three paths:
- `provision_device(..., force_change=true)` (LLM/MCP/CLI)
- **Web UI "Change password" button** on the account detail
  page — creates a one-time capture session bound to the
  existing device + account_id and redirects the operator to
  the standard `/capture/{token}` OOB form (per ADR-0009).
  Reuses the established capture machinery; the new password
  enters ADMZ only via the browser form, never via chat or
  arbitrary HTML submissions.
- `DeviceRegistry.update_account(device_id, account_id, updates)`
  (programmatic; atomic — replaces the legacy
  `remove_account` + `add_account` pattern that briefly left
  the account observably missing).

Scheduled / policy-driven rotation isn't implemented.

### KL-CRED-003 — No CSRF on capture form POSTs ⚠️
Tokens are single-use and high-entropy, but a CSRF token in the form
would be defense-in-depth. KG-SEC-002 — the capture forms now enforce
same-origin on POST (#3, `admz/csrf.py`); `POST /confirm/{token}` still does not.

### KL-CRED-004 — Vault mount-point / path-prefix not in env ⚠️
The factory docstring lists `VAULT_MOUNT_POINT` and `VAULT_PATH_PREFIX`
as recognized env vars but the Vault backend doesn't actually read
them. Operators with non-default Vault setups pass them
programmatically.

## References

- ADRs: [0007](../decisions/0007-per-protocol-auth.md), [0009](../decisions/0009-oob-credential-capture.md), [0010](../decisions/0010-fernet-encryption.md), [0011](../decisions/0011-pluggable-backends.md), [0014](../decisions/0014-config-in-git-creds-in-db.md), [0020](../decisions/0020-protected-fleet-settings.md)
- Cross-cutting: [security.md](security.md), [authentication.md](authentication.md)
- Code: `admz/backends/`, `admz/api/capture.py`, `admz/mcp/temp_credentials.py`, `admz/discovery/credential_probe.py`
