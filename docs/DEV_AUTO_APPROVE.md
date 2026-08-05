# Dev auto-approver — end-to-end testing of approval-gated flows

> ⚠️ **Development only. Never run this against a production ADMZ.**
> CLAUDE.md is explicit: *"Never point tests, agents, or experiments at
> :4242 or `C:\ProgramData\admz`."* `tools/dev_auto_approve.py` now refuses
> outright — raises, doesn't just print a warning — if `--base-url` resolves
> to `:4242` (see [`admz/target_guard.py`](../admz/target_guard.py), #180).

## The problem it solves

ADMZ's `url_only` / `url_and_password` confirmation gates are deliberately
**human-only**: the in-process LLM/MCP path *cannot* self-approve a write to a
device (ADR-0005/0006 — the two-gate safety model). That's exactly what you
want in production, but it makes **unattended end-to-end testing** of
approval-requiring flows impossible — an automated agent can mint the confirm
token but can never click "Confirm", so the flow stalls at the gate.

`tools/dev_auto_approve.py` lets an agent (or a CI job) complete those flows
on its own **without weakening any production code.**

## How it stays safe

The key idea: this is **not a gate bypass.** It's an automated stand-in for
the human. Approval still goes through the *real* approval endpoint
(`POST /api/chat/confirm/{token}` — the same route the in-chat approval widget
uses), so password verification, execution, and audit all run exactly as in
production. The safety invariant holds literally: the in-process path still
can't self-approve — approval comes from a **separate process** acting
out-of-band, just like a human at a browser.

Defense in depth — every layer must hold, or it refuses to act:

1. **Lives outside the shipped package.** It's in `tools/`, never imported by
   `admz/`. Production wheels don't contain it; nothing in the app changes
   behaviour because of it.
2. **Explicit env guard.** Does nothing unless `ADMZ_DEV_AUTO_APPROVE=1`.
3. **Lab/test scope.** By default only approves sessions whose device(s) carry
   a `lab` or `test` tag. A *plan* is in scope only if **all** its devices are
   tagged. `--all` disables the scope but additionally requires
   `--i-understand-this-is-not-production`.
4. **Loud + audited.** Every approval writes a distinct `dev.auto_approve`
   audit row stamped `confirmed_by="dev-auto-approver"` (alongside the normal
   `confirm.approve` row), plus a stderr line — a dev approval can never be
   mistaken for a real human one.
5. **Fails closed.** Guard unset → exits without acting → the system behaves
   exactly as production.

## It is a declared advanced capability

`ADMZ_DEV_AUTO_APPROVE` is registered as `dev.auto_approve` in
`admz/capabilities.py` (class `dev-only`, never production-appropriate) — see
[ADR-0052](specification/decisions/0052-advanced-capability-switches.md). The
registration changes nothing about how this tool works; it makes the *state*
legible. With the variable set on the ADMZ service, the installation says so at
startup (a WARNING on `admz.security`), in `curl /api/health`, on a red topbar
chip on every page, in a once-per-boot `capability.active` audit row, on
`/settings/advanced`, via the `get_advanced_capabilities` MCP tool, and in the
chatbot's system prompt — which is what stops the assistant telling an operator
an approval is "waiting for you" while this script is about to take it.

The registry **declares, it does not enforce** (ADR-0052 §6): this tool posts to
the real confirmation endpoint exactly as a browser does, and the server does
not try to tell the difference. Registering it is not a bypass and not a
hardening — it is the guarantee that nobody is surprised.

Note the class is `dev-only` and env-only *by design*: it can never be switched
on from a browser, only by somebody with service control on the box, plus a
restart.

## Passwords

If the dev environment has **no** `confirm_password_hash` fleet setting, ADMZ
already downgrades `url_and_password` → `url_only`, so no password is needed —
nothing in the verification code is bypassed. To exercise the password path,
set a known dev confirm password as the fleet setting and pass it via
`ADMZ_DEV_CONFIRM_PASSWORD`; the approver supplies it to the real endpoint,
which verifies it normally.

## Usage

Run from `C:\admz\admz` with the API server up on `:4243` (staging —
never `:4242`, which is production on this machine):

```bash
# One-shot: approve everything currently pending and in-scope, then exit
ADMZ_DEV_AUTO_APPROVE=1 .venv/Scripts/python.exe tools/dev_auto_approve.py

# Watch mode — "step away and let it run". Any in-scope gate that appears
# gets auto-approved within ~1s. Ctrl-C to stop.
ADMZ_DEV_AUTO_APPROVE=1 .venv/Scripts/python.exe tools/dev_auto_approve.py --watch

# Approve specific tokens only
ADMZ_DEV_AUTO_APPROVE=1 .venv/Scripts/python.exe tools/dev_auto_approve.py <token> ...

# Override the in-scope tags (default: lab,test)
ADMZ_DEV_AUTO_APPROVE=1 .venv/Scripts/python.exe tools/dev_auto_approve.py --watch --allow-tags lab,test,bench
```

Flags: `--base-url` (default `$ADMZ_E2E_BASE_URL`, then `$ADMZ_BASE_URL` as a
deprecated alias, then `http://localhost:4243`; refuses if it resolves to
`:4242` — see the warning above), `--allow-tags`, `--all` +
`--i-understand-this-is-not-production`, `--watch`, `--interval`.

## Typical agent workflow

1. Tag the test device(s) `lab` in the registry.
2. Start the approver in watch mode in the background.
3. Drive an end-to-end flow that trips a gate — e.g. chat *"reboot the P8815"*
   → the gate blocks → the approver auto-approves → the op executes →
   `await_device_recovery` confirms the device came back (changed bootid).
4. Assert the end state and the audit trail (`confirm.approve` +
   `dev.auto_approve` rows).

The operator can walk away after step 2; the loop completes unattended.

## Verified live run (smoke test)

This sequence was run end-to-end against a real device (P8815-2,
`ACCC8EE6E7EE`) on 2026-06-10 and is the reproducible smoke test for the
whole chain — gate → unattended approval → real reboot → recovery → audit.
Run it against any `lab`-tagged, reachable device.

**The original run predates the staging split** (ADR-0054, landed
2026-08-04) and used what was then a shared dev/test instance on `:4242` —
that history is unchanged below for accuracy. `:4242` is production today.
The commands below are updated to target staging (`:4243`); do not
substitute `:4242` when repeating this test.

```bash
# 0. Servers up on :4243 (staging, .venv); pick a lab-tagged device id.
DID=ACCC8EE6E7EE

# 1. Capture the baseline bootid (also confirms it's online + creds work).
#    Returns status="still_waiting" with the current bootid as baseline_bootid.
.venv/Scripts/python.exe - <<PY
import asyncio, json
from admz.factory import create_device_registry
from admz.components import build_components
from admz.recovery import await_device_recovery
reg = create_device_registry(); cat = build_components(reg).catalog
r = asyncio.run(await_device_recovery(device_id="$DID", timeout_s=8, poll_interval_s=2, catalog=cat, registry=reg))
print("baseline bootid:", r["baseline_bootid"])
PY

# 2. Start the auto-approver in watch mode (background), scoped to lab.
ADMZ_DEV_AUTO_APPROVE=1 .venv/Scripts/python.exe tools/dev_auto_approve.py \
    --watch --base-url http://127.0.0.1:4243 --allow-tags lab &

# 3. Trip the gate: a service-affecting reboot. Returns blocked + a token;
#    the op does NOT run yet.
curl -s -X POST http://127.0.0.1:4243/api/catalog/execute \
  -H "Content-Type: application/json" \
  -d "{\"device_id\":\"$DID\",\"operation_id\":\"restart.cgi:restart\",\"family\":\"vapix\",\"params\":{}}"

# 4. The watcher approves within ~1s (its log shows "✔ APPROVED (dev) … success=True")
#    and the device reboots.

# 5. Confirm recovery: pass the baseline from step 1.
.venv/Scripts/python.exe - <<PY
import asyncio, json
from admz.factory import create_device_registry
from admz.components import build_components
from admz.recovery import await_device_recovery
reg = create_device_registry(); cat = build_components(reg).catalog
r = asyncio.run(await_device_recovery(device_id="$DID", timeout_s=120, poll_interval_s=3,
    baseline_bootid="<baseline-from-step-1>", catalog=cat, registry=reg))
print(r["status"], "| new bootid", r["bootid"], "| offline_observed", r["offline_observed"])
PY
```

Expected (and observed) outcome:

| Stage | Result |
|---|---|
| Trip the gate (step 3) | `blocked: true`, `confirmation_level: url_only`, op did **not** execute |
| Watcher (step 4) | `✔ APPROVED (dev) … → restart.cgi:restart … execution success=True` |
| Recovery (step 5) | `status: recovered`, `offline_observed: true`, **new bootid ≠ baseline**, fresh uptime, `needsetup: false` (~18s here) |
| Audit log | `catalog.execute` (success=False — gate held) · `confirm.approve` (success=True, `confirmed_by=chat`) · `dev.auto_approve` (`requester=dev-auto-approver`, "not a human approval") |

Audit check:

```bash
.venv/Scripts/python.exe -c "
from admz.audit import AuditLog; import time
log = AuditLog(); since = time.time() - 600
for a in ('catalog.execute','confirm.approve','dev.auto_approve'):
    for r in log.list_recent(action=a, since=since, limit=3):
        print(a, '| success', r.success, '| confirmed_by', (r.details or {}).get('confirmed_by'))
"
```

Stop the watcher when done (it's a polling loop): kill the
`tools/dev_auto_approve.py` process, or run it in one-shot mode (no `--watch`)
instead of leaving it resident.

## What it deliberately does NOT do

- **No MCP `dev_approve` tool.** Approval stays in a separate process; adding
  an in-surface approval tool would collapse the human/agent separation the
  whole design preserves.
- **No production code path changes.** There is no `if dev: skip_approval`
  branch anywhere in `admz/`.

## Tests

- `tests/test_dev_auto_approve.py` — guard + scope logic (incl. plans with
  mixed tags) with a mocked endpoint.
- `tests/test_dev_auto_approve_live.py` — drives the **real**
  `/api/chat/confirm/{token}` route via a FastAPI TestClient against an
  isolated tmp DB: lab session → approved + completed + audited; prod session
  → skipped + left pending.
