# ADMZ end-to-end chat suite

These tests **POST to a live `/api/chat`** and assert on what Gemini does
with the ADMZ MCP toolbox. They simulate real user interactions — they
spend real Gemini API credits and they touch the live SQLite registry +
config-repo git tree.

**Don't run in normal CI.** They're opt-in via `--run-e2e`. The flag is
the only safety latch.

## Running

```
cd C:\admz\admz
# 1. Make sure a fresh server is running:
.venv\Scripts\python.exe -m admz api --host 127.0.0.1 --port 4242

# 2. In another shell, run the suite:
.venv\Scripts\python.exe -m pytest tests/e2e --run-e2e -v --no-cov
```

If the server isn't reachable at `localhost:4242`, the suite skips itself
with a clear message.

Override the base URL via `ADMZ_E2E_BASE_URL=http://...`.

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
