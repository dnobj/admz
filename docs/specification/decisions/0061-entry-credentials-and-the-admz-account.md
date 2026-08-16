# ADR-0061 — Fleet credentials get you in; ADMZ's own per-device account keeps you in

**Status:** Proposed (2026-08-16).
**Relates to:** ADR-0059 (gate provisioning at the decision point — account
creation is that decision), ADR-0009 (out-of-band credential capture — the
fallback path), ADR-0034 (confirmation gates), ADR-0010 / #405 (encryption at
rest for `default_password`, which this makes load-bearing), FR-CRED-007
(auto-provisioning, whose password-source ordering this changes), FR-CRED-008
(temporary `at_*` users — a different mechanism, deliberately untouched),
`q_d7314a51` (resolved 2026-08-07 — the compromise this supersedes).

## Context

ADMZ's fleet credential does two unrelated jobs today, and does neither well.

**Job one — get in.** A device set up before ADMZ existed, or by hand, or by a
previous operator, has *some* admin credential. ADMZ needs it once, to reach the
device at all.

**Job two — stay in.** Whatever credential ADMZ uses for the next two years of
health polls, config reads, drift audits and gated writes.

`onboarding.py:229` conflates them: when the fleet pair authenticates, ADMZ
stores **that same pair** as the device's ongoing credential. So a single shared
password ends up being the standing key to every device that was ever onboarded
that way — and rotating it means either touching every device or breaking ADMZ's
access to all of them.

### The measurement that shows it is already not working

Production, 2026-08-16:

```
fleet_settings.default_username = 'operator'
fleet_settings.default_password = <set>
```

Of the **nine** stored device accounts, **not one uses `operator`.** Eight are
`root`; one is `admz`. Several of the `root` entries carry
`purpose: "Device onboarding — automatic resolution failed"`, meaning a human
typed `root` into the capture form because that is what the device actually
wanted.

So the fleet pair as configured cannot resolve anything on this fleet, and the
capture fallback has been doing all the work. The single `admz` account is the
tell that the intended shape was already understood; it just was not built.

### Why a single password is the wrong shape for job one

A fleet acquired over time has *eras* — different setup batches, different
usernames, different passwords. `default_password` is one string and
`default_username` is one string, so ADMZ can express exactly one era. Every
device from any other era falls through to a capture prompt even when ADMZ could
have authenticated it.

### What the compromise settled, and why this is better

`q_d7314a51` was answered *"shared fleet default, with encouragement to use
per-device generated passwords."* That is a genuine tension split down the
middle: shared is convenient, per-device is safer, so do some of each and hope.

Separating the two jobs dissolves it. **Shared is right for entry** — you cannot
have a per-device secret for a device you have never met. **Generated-per-device
is right for ongoing** — nothing needs to know it but ADMZ. Each credential does
the job it is actually good at, and neither is a compromise.

Two pieces already point this way. #327 made unattended reprovision always
generate its own password rather than reuse the fleet one. And FR-CRED-007's
current ordering — *explicit arg > fleet `default_password` > generated* —
prefers the shared secret precisely where it is least appropriate: writing a
brand-new account on a factory-default device.

## Decision

**1 · Fleet credentials become a list of entry credentials.** Each entry is a
`(username, password)` pair, because usernames vary by era as much as passwords
do. They are used **only** to authenticate to a device ADMZ does not yet manage.
They are never stored as a device's ongoing credential.

**2 · ADMZ creates its own account on every device it manages.** Username
`admz`, administrator group, password generated per device, stored encrypted.
This becomes the ongoing credential for all subsequent access.

**3 · The entry credential is never deleted or rotated by ADMZ.** It is the
recovery path — see Consequences.

**4 · When no entry credential works, ADMZ asks.** The existing capture flow
(ADR-0009), with one addition: an opt-in *"also try this on other devices"* that
promotes the captured pair to the entry list.

### Onboarding under the new model

| Situation | Today | Under this ADR |
|---|---|---|
| Stored credential verifies | nothing to do | nothing to do |
| Factory-defaulted (`needsetup=yes`) | create account, password from fleet default | create `admz`, **generated** password |
| An entry credential authenticates | **store the fleet pair as the credential** | use it to create `admz`, store **that** |
| Nothing authenticates | capture session | capture session **+ promote checkbox** |

The change is one function. Steps 1, 2 and 4 keep their shape; step 3 stops
storing what it borrowed.

### The promote checkbox

Ticking it is **not** "save this password." It is *"try this secret against
every other device in the fleet."* The label must say that, it defaults
**unchecked**, and the promotion is audited as its own event — distinct from the
capture itself.

For MCP callers the capture response carries the flag, but the agent may only
**propose** it. The widget shows it and the human confirms. The person typing
the secret is the only one who knows whether it is safe to spray at the whole
fleet, and that judgement cannot live in a tool argument.

## Consequences

### The gate

Creating an administrator account is `pwdgrp.cgi:add-user` with `group=root` —
exactly the write ADR-0059 moved the gate to. This path now performs it on
devices that are **not** factory-defaulted, which ADR-0059's analysis did not
cover. `onboarding._APPROVAL_ACTIONS` needs a member for it, and the
`APPROVAL_REQUIRED` envelope already exists to carry it. **A device that is
merely being adopted must not create an account without approval** just because
it happened to answer a password.

### Lockout is the real operational risk

Trying N entry credentials is N failed authentications, and Axis brute-force
behaviour varies by model and firmware. Required: stop on first success, order
by most-recently-successful, cap the attempts, and **measure it once against a
spare device before shipping.** Adding a fourth credential to the list should
not be the thing that locks ADMZ out of the fleet.

### Never delete the credential you came in on

If ADMZ's database is lost, every generated `admz` password is lost with it. The
entry credential is then the only way back in. So ADMZ must not remove, rotate
or disable the account it authenticated with — and this is a rule, not a
preference. It also means the entry list is **secret-bearing recovery material**,
which makes #405 (encrypt `default_password` at rest) a prerequisite rather than
an adjacent tidy-up.

### Orphaned `admz` accounts

Remove a device from ADMZ and its `admz` account stays on the camera, valid,
with a password nobody holds. This is `q_70025d93`'s orphaned-credential problem
arriving through a new door, and it needs an answer at design time: offer removal
on delete, or document that it persists. Silently leaving admin accounts on
decommissioned hardware is not acceptable; *deliberately* leaving them, written
down, might be.

### Three kinds of device-side account now exist

Worth naming before someone conflates them:

| Account | Lifetime | Who uses it |
|---|---|---|
| `at_<8 hex>` (FR-CRED-008) | 60–3600 s | the LLM, directly, plaintext by design |
| `admz` (this ADR) | as long as ADMZ manages the device | ADMZ's own executor |
| pre-existing / entry | whatever the operator set up | ADMZ once, at adoption |

### Migration

Nine devices currently store a credential that may be an entry credential rather
than an `admz` account. This ADR does **not** migrate them automatically — that
would mean creating accounts on nine live devices as a side effect of a deploy,
which is precisely the class of thing that should be a decision. Existing devices
keep working; adoption of the new shape is per-device and gated.

## What this does not do

- **No password rotation for `admz`.** Rotation needs its own recovery story and
  its own ADR. Generating once is strictly better than today; generating and
  rotating is a larger claim.
- **No removal of existing accounts**, on any device, ever, as part of this.
- **No change to temporary credentials** (FR-CRED-008). Different lifetime,
  different consumer, deliberately untouched.
- **No decision on `operator`.** Whether that username was aspirational or stale
  is a question for the owner; this ADR only stops one string from having to be
  right for every device.

## What would falsify this

If entry credentials turn out to be single-use in practice — every device
adopted through capture rather than through a list — then the list is ceremony
and one credential plus the capture form would have been enough. The signal is
the promote checkbox: **if operators never tick it, the list is not earning its
complexity.** Worth checking after twenty adoptions rather than assuming.
