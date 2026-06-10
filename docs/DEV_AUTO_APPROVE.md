# Dev auto-approver — end-to-end testing of approval-gated flows

> ⚠️ **Development only. Never run this against a production ADMZ.**

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

## Passwords

If the dev environment has **no** `confirm_password_hash` fleet setting, ADMZ
already downgrades `url_and_password` → `url_only`, so no password is needed —
nothing in the verification code is bypassed. To exercise the password path,
set a known dev confirm password as the fleet setting and pass it via
`ADMZ_DEV_CONFIRM_PASSWORD`; the approver supplies it to the real endpoint,
which verifies it normally.

## Usage

Run from `C:\admz\admz` with the API server up on `:4242`:

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

Flags: `--base-url` (default `$ADMZ_BASE_URL` or `http://localhost:4242`),
`--allow-tags`, `--all` + `--i-understand-this-is-not-production`,
`--watch`, `--interval`.

## Typical agent workflow

1. Tag the test device(s) `lab` in the registry.
2. Start the approver in watch mode in the background.
3. Drive an end-to-end flow that trips a gate — e.g. chat *"reboot the P8815"*
   → the gate blocks → the approver auto-approves → the op executes →
   `await_device_recovery` confirms the device came back (changed bootid).
4. Assert the end state and the audit trail (`confirm.approve` +
   `dev.auto_approve` rows).

The operator can walk away after step 2; the loop completes unattended.

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
