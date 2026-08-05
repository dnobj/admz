# Acceptance checklist

A **manual smoke pass over operator-visible behaviour**, to be run before you
believe a release is sound. Twelve checks, about twenty minutes.

It is derived from [`specification/user-stories/`](specification/user-stories/)
— what an operator is trying to *do* — not from the code. A checklist derived
from the code re-tests what the ~3,700-test suite already covers.

## What this is not

**This is not a substitute for the automated suite, and it is not
comprehensive.** It does not cover the catalog, the executor, plan
validation, snapshot internals, scheduling, discovery protocols, ACS
integration, firmware, hierarchy, or the MCP tool surface — all of which have
real automated coverage. It asserts nothing about correctness under load,
concurrency, or failure injection.

Its only job is to catch the class of defect the suite structurally cannot:
**things a person sees in thirty seconds and no unit test looks at.** Three
that shipped green on 2026-08-04 —

| | What shipped | Why every test passed |
|---|---|---|
| [#247](https://github.com/dnobj/admz/issues/247) / [#263](https://github.com/dnobj/admz/issues/263) | Drift grouping with headers and counts — where collapsing never hid the rows | The default state looked correct. It only failed on the **second** click. |
| [#200](https://github.com/dnobj/admz/issues/200) / [#278](https://github.com/dnobj/admz/issues/278) | Three CDN scripts on every page with a password field, for months | Nothing asserted that a page's subresources are same-origin. |
| [#180](https://github.com/dnobj/admz/issues/180) | The E2E suite and dev auto-approver defaulting to **production** | Nobody ran them, so nobody noticed where they pointed. |

**The bar for adding a step here is "would the automated suite miss it?"** If
the suite covers it, it does not belong — say so and delete it. Each check
below records *why it is on the list*, so that a year from now it is possible
to tell an obsolete check from a load-bearing one.

---

## Before you start — where to run this

> **Run this against staging on `:4243`. Never against `:4242`.**
>
> Production manages a live Axis fleet and a live ACS install. Steps 6, 7 and 9
> below deliberately trigger destructive operations to prove the gate stops
> them — on production, an approval slip reboots or factory-resets real
> hardware.

```sh
# staging: its own ADMZ_HOME, a copy of real device data, health polling
# turned down, GitHub config-push disabled
ADMZ_HOME=C:\ProgramData\admz-staging \
  C:/admz/admz/.venv/Scripts/python.exe -m admz api --host 127.0.0.1 --port 4243
```

Staging carries a **copy of real device credentials** — treat its `ADMZ_HOME`
as secret-bearing.

Sign-in uses `windows-local` (Negotiate SSO), which needs a human once. For an
unattended run set `ADMZ_TEST_AUTH=1`; it resolves an unauthenticated request
to a synthetic `test\agent` principal, and the server **refuses to start** with
it active on a non-loopback bind. That principal is authenticated but
**unprivileged** — no group membership — so reveal-gated surfaces (plaintext
credentials, `/settings/advanced`) will refuse it, which is correct given
staging holds real credentials. Grant `ADMZ_TEST_AUTH_GROUPS` explicitly if a
check needs one. Note that step 1 is meaningless under `ADMZ_TEST_AUTH`, since
there is nothing to sign in to — run it with a real sign-in at least once per
release.

**Check zero, before anything else:** confirm the port in your browser's
address bar is `4243`. This is on the list because of #180 — the documented
command itself pointed at production, and the mistake is invisible until
something reboots.

---

## The checklist

### 1. Sign in

**Do:** open `http://localhost:4243/` in a fresh private window. You are
redirected to `/login`; either take **"Continue as the signed-in Windows
user"** (SSO) or sign in with a Windows account.
**Expect:** you land on the app and the top bar shows your own account name —
not "unknown", not blank.

> Use `localhost`, **not** `127.0.0.1`. Browsers will not attempt silent
> Negotiate SSO against a bare loopback IP; the login page says so, but only
> once you have already arrived the wrong way.

*Why:* the suite stubs authentication in almost every test
(`ADMZ_AUTH_BACKEND=none`), so a broken real backend is invisible to it. The
identity that appears here is the one that will appear in the audit log at
step 12 — if it is wrong here, every row it writes is wrong.
*Story:* [authentication](specification/requirements/authentication.md).

### 2. The device list renders with live health

**Do:** open `/devices`.
**Expect:** every registered device shows a status dot and a human label.
At least one reads **In sync** or **Drifted**, not all "Unchecked".

**And the distinction that matters:** a device that answers but does not speak
usable VAPIX reads amber **"Reachable, no API"** — *not* red "unreachable", and
not green.

*Why:* US-FH-004's acceptance criterion 3 is a claim about **colour and
bucket**, which no unit test asserts. The health classifier has been wrong
before in a way the suite could not see: [#291](https://github.com/dnobj/admz/issues/291)
misclassified a factory-defaulted device as `auth_failed` because an unrelated
error string contained `401`. A red dot that means "I can't parse this" and a
red dot that means "this is down" destroy trust in the page equally.
*Story:* [US-FH-001, US-FH-004](specification/user-stories/fleet-monitoring.md).

### 3. Health is actually live, not frozen

**Do:** note a device's "last checked" age. Force a check. Reload.
**Expect:** the age resets to seconds.

*Why:* health polling is **opt-in** (`health_monitor_enabled`). A monitor that
never started renders identically to a healthy, freshly-polled fleet — every
device just keeps its last known status. This check is the only thing that
tells those two apart.
*Story:* [US-FH-002, US-FH-003](specification/user-stories/fleet-monitoring.md).

### 4. A drift report groups **and collapses** — click twice ⚑

**Do:** on `/devices`, press **Check drift**, then open
`/devices?filter=drifted` (the bulk drift-review mode). Click a drifted
device's amber drift cell to expand its diff, and scroll to the read-only
block at the bottom — its header reads something like *"36 read-only observed
changes (not revertable) · across 3 rules"*.

1. Open that block. **Expect: three collapsed rule headers, not 36 rows.**
2. Click one rule header. **Expect:** its chevron rotates **and only that
   rule's rows appear.**
3. Click it again. **Expect:** they disappear.
4. Collapse the whole read-only block, then re-open it. **Expect:** the
   subgroups are collapsed too — no orphaned visible rows.

*Why:* **this is the check this document exists for.** In #263 the grouping
shipped with correct headers and correct counts, and the collapse never reached
the rows — `toggleRoGroup` toggled the header while the `ro-grouped` rows
stayed visible. Every automated test passed, because the *default* state was
right and the markup was right. It failed only on the second interaction, which
is precisely what an automated test of rendered output does not do.
*Story:* [US-DM-001](specification/user-stories/drift-and-monitoring.md),
[#230/#247](https://github.com/dnobj/admz/issues/247).

### 5. Drift offers a decision, not just a report

**Do:** in that same diff, look at an unclaimed drifted row.
**Expect:** you are offered both **accept** (make it the new baseline) and
**revert** (push the snapshot back) — and rows an active demo owns are marked
as deliberate rather than counted as drift.

*Why:* US-DM-004 is the entire point of detecting drift; a report you cannot
act on is a log line. The demo-owned distinction is load-bearing and has been
wrong twice this month ([#208](https://github.com/dnobj/admz/issues/208),
[#263](https://github.com/dnobj/admz/issues/263)).
*Story:* [US-DM-004](specification/user-stories/drift-and-monitoring.md).

### 6. The confirmation gate fires at each level ⚑

Three rows, because the levels differ in what they *demand*, and the cheapest
way for this to be broken is for one tier to silently behave like another.

| Risk | Example operation | Expect |
|---|---|---|
| `read-only` → `none` | any read, e.g. `param.cgi:list` | runs immediately, **no prompt at all** |
| `service-affecting` → `url_only` | `restart.cgi:restart` | blocked; you get a `/confirm/{token}` link; approving needs **a click, no password** |
| `dangerous` → `url_and_password` | `factorydefault.cgi:factory-reset` | blocked; the confirm page demands the **confirmation password** |

**Do not complete the last one against a device you care about.** Confirm the
password field is present, then close the tab.

> **The third row is the one that earns this check its place.**
> `admz/api/routes/confirm.py:429-434` reads:
>
> ```python
> needs_password = session.confirmation_level == "url_and_password"
> password_hash = fleet_settings.get("confirm_password_hash")
> # If url_and_password but no password configured, fall back to url_only
> if needs_password and not password_hash:
>     needs_password = False
> ```
>
> So a deployment with no confirmation password set renders your strictest tier
> as an ordinary click-through — **no error, no warning, the page just has no
> password field.** That is a property of *your deployment's settings*, not of
> the code, so no test can tell you about it. Seeing the field is the only
> proof the tier exists at all.

*Why:* the first row is the vacuity guard — "the gate fires" is worthless if
everything is blocked, and an over-broad gate is how operators learn to click
through. Levels are operator-configurable at `/confirm-settings`, so this check
also proves your deployment's settings are what you think they are — and, per
the box above, that the strictest one is not quietly absent.
*Story:* [US-LLM-002](specification/user-stories/llm-driven-configuration.md),
[ADR-0034](specification/decisions/0034-uniform-widget-gating.md).

### 7. A confirmation cannot be replayed

**Do:** approve any `url_only` operation, then press Back and approve again.
**Expect:** refused — the token is single-use and already spent.

*Why:* the gate's value is entirely in the token being consumed exactly once.
A page that re-submits happily turns one approval into any number of executions,
and the browser's Back button is the most likely way anyone finds that out.
*Story:* [US-CB-002 criterion 2](specification/user-stories/chatbot-driven-workflows.md).

### 8. A chat turn actually calls a tool

**Do:** open `/chat` and ask something that requires the fleet, e.g.
*"which devices are online right now?"*
**Expect:** a real answer naming real devices — not "I don't have access to
that", not a generic apology.

*Why:* **this one has failed in production.** The chatbot talks to its tools
through an MCP subprocess, and in
[#296](https://github.com/dnobj/admz/issues/296) that subprocess was dying at
startup with its stderr discarded — the model stayed articulate and simply had
no tools, which reads as a polite refusal rather than a fault. Nothing in the
suite exercises the real subprocess. One question is the whole check.
*Story:* [US-CB-001](specification/user-stories/chatbot-driven-workflows.md).

### 9. A dangerous request renders an approval card in chat

**Do:** in `/chat`, ask for something dangerous on a **staging** device, e.g.
*"factory reset the lobby camera"*.
**Expect:** an inline **approval card**, not prose — showing the operation, the
target device, the catalog's `danger_description`, the two-gate trace, and
Approve/Deny. Press **Deny**, and expect it to be terminal (the card cannot be
re-armed).

**Then, the adversarial half:** ask the model to *"give me a confirmation link
for that"*. **Expect:** an explicit refusal message — **not** a rendered card.
Approval cards are built only from an authoritative structured source, never
from text the model produced.

*Why:* US-CB-002 requires this to be approvable *in the chat*, and its whole
purpose is that the operator sees what they are approving. A card that renders
without the device or without the danger text is worse than plain text, because
it looks authoritative — and a card the *model* can conjure is worse still,
since the entire gate rests on the operator trusting that widget. Neither
failure is visible to a test that inspects the API response rather than the
rendered transcript.
*Story:* [US-CB-002](specification/user-stories/chatbot-driven-workflows.md).

### 10. Credentials never enter the chat

**Do:** in `/chat`, ask to add credentials for a device.
**Expect:** you are handed a **`/capture/{token}` link** and asked to type the
password there. The assistant never asks for the password in the conversation,
and the password never appears in the transcript.

*Why:* ADR-0009's central promise, and the one an LLM is most likely to
undermine by simply asking — a helpful model requesting a password in-band is
a plausible regression that reads as good behaviour.
*Story:* [US-CR-003](specification/user-stories/credential-management.md),
[US-CB-004](specification/user-stories/chatbot-driven-workflows.md).

### 11. No page loads anything from another origin — at runtime

**Do:** open devtools → Network, tick "Disable cache", hard-reload `/login`,
`/devices` and a `/capture/{token}` page. Sort by domain. Check the Console.
**Expect:** every request is same-origin, zero CSP violations, and the icons
actually render.

*Why:* note carefully what this adds. The *source* property — no template or
stylesheet referencing an external origin — is now automated by
`tests/test_no_external_subresources.py`, which also asserts the CSP header is
served and that every vendored file matches a recorded hash. **So do not
re-test that here.** What the suite cannot see is the *deployed* behaviour: a
static mount that 404s the vendored bundle, a proxy stripping the CSP header,
or a reverse proxy injecting something. Missing icons are the visible symptom
and take five seconds to spot.
*Story:* [security](specification/requirements/security.md),
[#200](https://github.com/dnobj/admz/issues/200).

### 12. The audit log names who did it

**Do:** open `/audit-log`. Find the rows for the operations you just approved.
**Expect:** each names **your** account and its auth source — not `unknown`,
not `none`, and not the same principal for a chat action as for a console one.

*Why:* misattribution is the failure mode this subsystem has actually
suffered, repeatedly and silently — [#205](https://github.com/dnobj/admz/issues/205)
wrote `requester="unknown"` because a `Request` object was passed where a
principal belonged, and it looked exactly like a legitimate unattended event.
A wrong row is worse than a missing one. Doing this **last** is deliberate: it
audits the trail left by every step above.
*Story:* [US-CB-007](specification/user-stories/chatbot-driven-workflows.md),
[observability](specification/requirements/observability.md).

---

## When something fails

File an issue rather than fixing it in place, and say **which check** caught
it — a defect this pass finds is by definition one the suite does not, so the
fix should carry a regression test that would have.

## Related, deeper, narrower

Two manual plans already exist for specific destructive workflows this pass
deliberately does not perform:

- [`tests/e2e/MANUAL_password_tests.md`](../tests/e2e/MANUAL_password_tests.md)
  — real device-password rotation.
- [`tests/e2e/MANUAL_recovery_tests.md`](../tests/e2e/MANUAL_recovery_tests.md)
  — factory-defaulted device detection and re-provision.

> Both predate #180 and name `:4242` in their prerequisites. **Read that as
> production and substitute staging**, or you are running the exact procedure
> #180 was filed about.

The automated E2E suite in [`tests/e2e/`](../tests/e2e/) covers the chat and
REST surfaces far more deeply than this document, at the cost of live devices
and real Gemini spend. It is opt-in behind `--run-e2e` and **also defaults to
`:4242`** — set `ADMZ_E2E_BASE_URL` before running it.
