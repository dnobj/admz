# ADMZ end-to-end chat suite

These tests **POST to a live `/api/chat`** and assert on what Gemini does
with the ADMZ MCP toolbox. They simulate real user interactions — they
spend real Gemini API credits and they touch the live SQLite registry +
config-repo git tree.

> ⚠️ **Never point this at production.** CLAUDE.md: *"Never point tests,
> agents, or experiments at `:4242` or `C:\ProgramData\admz`."* The suite
> defaults to staging (`:4243`) and refuses outright — raises, not a skip
> — if the resolved target is `:4242` (see
> [`admz/target_guard.py`](../../admz/target_guard.py), #180).

**Don't run in normal CI.** They're opt-in via `--run-e2e`. The flag gates
*whether* the suite runs; the target guard above gates *where* — the flag
alone was previously the only safety latch, which is what #180 fixed.

## Running

```
cd C:\admz\admz
# 1. Make sure a fresh staging server is running:
.venv\Scripts\python.exe -m admz api --host 127.0.0.1 --port 4243

# 2. In another shell, run the suite:
.venv\Scripts\python.exe -m pytest tests/e2e --run-e2e -v --no-cov
```

If the server isn't reachable at `localhost:4243`, the suite skips itself
with a clear message.

Override the base URL via `ADMZ_E2E_BASE_URL=http://...`. Pointing it at
`:4242` refuses (see the warning above) unless
`ADMZ_E2E_ALLOW_PRODUCTION_URL` is set to that *exact* URL — a deliberate,
loud, single-purpose opt-in, not a boolean flag left on from an earlier
session.

## Cost + duration

Each test makes 1–3 Gemini calls (gemini-2.5-flash by default). As of
2026 pricing, a full pass is **~$0.03–$0.05** and takes **~3–5 minutes**.
The summary at the end of the run lists per-test cost + tokens.

## When to run

- **Before tagging a release.** Catches LLM-prompt regressions that
  unit tests can't see (e.g. the LLM started phrasing failures
  differently, or the SDK changed how it surfaces tool calls).
- **After touching the chatbot code path** (`admz/chatbot/`,
  `admz/api/routes/chat.py`, `admz/mcp/server.py`).
- **After bumping the Gemini SDK / changing the default model.**

## What it covers

| File | What it asserts |
|---|---|
| `test_01_sanity.py` | `/api/chat` responds at all; no-tool turn works; tokens are tracked. |
| `test_02_inventory.py` | LLM can list devices, look up a specific one by ID. |
| `test_03_health.py` | Fleet health summary is reachable + reflects real state. |
| `test_04_catalog.py` | Catalog queries work (LLM can find a VAPIX operation by intent). |
| `test_05_snapshot.py` | Snapshot path — both the commit-something case AND the no-changes-since-last case produce sensible responses. |
| `test_06_safety.py` | Dangerous operations trip the confirmation gate before any side effect. |
| `test_07_capture.py` | Asking to provision credentials produces a `/capture/<token>` URL. |
| `test_08_multi_turn.py` | Conversation context carries between turns (the LLM remembers what we just talked about). |
| `test_09_drift_history.py` | Drift-alert history is queryable through chat (`get_drift_alerts`). |
| `test_10_scheduling.py` | Unified scheduler — chatbot lists job types + creates a `drift_audit` schedule. |
| `test_11_specialized_hardware.py` | The LLM picks the *right* API for the device: "flash white" on a D4200-VE strobe siren resolves to `siren_and_light.cgi`, not `findmydevice.cgi`. Regression for the resolver "flash" synonym gap. |
| `test_12_device_resolution.py` | The agent resolves a device referenced by model name ("the D4200") to its device_id via `search_devices`/`list_devices` instead of asking the user for the MAC. Regression for the "I need the device_id, please provide it" stall. |

## What it does NOT cover

- Network discovery (slow + LAN-dependent).
- Restore / plan execute (data-loss potential against real fleet).
- Actually approving a `/confirm/<token>` and rebooting a device.
- LLM behavior with the `gemini-3.x` models (default is `gemini-2.5-flash`
  per `chatbot/config.py`). Switch via `model` param if you want to
  verify a specific model.

## Assertion philosophy

Gemini's phrasing varies between runs. Tests should be **strict on
shape, loose on prose**:

- ✓ "the response is non-empty, output_tokens > 0, success=true"
- ✓ "the response mentions one of {sha, committed, unchanged, no changes}"
- ✗ "the response says exactly 'I committed snapshot abc1234'"

If a test fails, look at the failure's `ChatResult` repr — it includes
the model, tokens, elapsed time, and the first 200 chars of the
response. That's usually enough to tell whether it's a real regression
or just an unusually-phrased LLM output.

## When a test legitimately fails

LLM phrasing changes happen. Before assuming a real regression:
1. Re-run just the failing test 2–3 times — Gemini is non-deterministic.
2. Look at the actual response text in the failure log.
3. If the response is correct but phrased in a way the assertion missed,
   relax the assertion (add another acceptable substring to `contains_any`).
4. Only call it a real bug if the response demonstrates broken behavior
   (e.g. claims a snapshot failed when it succeeded, calls a tool that
   doesn't exist, leaks plaintext credentials).
