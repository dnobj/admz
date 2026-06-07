# Gemini 3.x + MCP tools: the empty-turn (AFC) issue and how to fix it

**Status:** Diagnosed; fix not yet implemented. gemini-2.5-flash (the default) is
unaffected and reliable. This is the reference for adding gemini-3.x support.

## Symptom

With **gemini-3.x** models (`gemini-3.5-flash`, `gemini-3.1-pro-preview`,
`gemini-3.1-flash-lite`) and MCP tools enabled, a turn that calls a tool ends
with `output_tokens > 0` but **no visible text** — an empty chat bubble. The chat
client already has a "Case B" backstop that detects this and tells the user to
switch to gemini-2.5-flash. With **gemini-2.5-flash the same prompts work.**

## Root cause (confirmed from SDK source)

Not an ADMZ bug — an **unfixed defect in `google-genai`'s async + streaming
automatic-function-calling (AFC) loop.**

- ADMZ drives chat through `client.aio.models.generate_content_stream`
  (`admz/chatbot/client.py`, `_stream_via_models_api`) — the async-streaming-AFC
  path.
- In the SDK (`google/genai/models.py`, async-stream AFC loop) there is a
  maintainer TODO **`b/453739108` — "make AFC logic more robust like the other 3
  methods."** The sync, sync-stream, and async-non-stream AFC loops are robust;
  the async-stream one is not.
- It extracts the function call from only the **first** streamed chunk.
  gemini-2.5-flash lands a complete `function_call.args` in that chunk → works.
  **gemini-3.x splits function-call args across chunks and interleaves a
  mandatory `thought_signature`**, so the first chunk has no complete args →
  the loop `break`s **before issuing the AFC continuation request** → empty turn.
- Tracked upstream: [python-genai #1593](https://github.com/googleapis/python-genai/issues/1593)
  (open). **Not fixed through google-genai 2.8.0** (latest as of 2026-06-03) —
  upgrading alone does **not** fix it.

This is also why gemini-3.x / `*-pro` rejected `thinking_budget: 0`
("only works in thinking mode"); the dynamic-thinking default (`-1`) in
`_get_thinking_budget` is the correct setting for these models.

## Recommended fix — Option B: manual function-calling loop (AFC disabled)

Run the function-calling loop in ADMZ instead of relying on the broken SDK AFC.
Feasible because the SDK still **registers** MCP tools when AFC is disabled
(`parse_config_for_mcp_sessions` runs regardless) — it just stops auto-executing
them and surfaces `function_call` parts to the caller. ADMZ already holds the live
MCP session (`mcp_bridge.py` / `mcp_pool.py`).

Loop (replaces the AFC reliance in `_stream_via_models_api`):

1. Non-streaming `client.aio.models.generate_content` with
   `automatic_function_calling={"disable": True}` and `tools=[mcp_session]`.
2. If the response has `function_call` parts: for each, `await
   mcp_session.call_tool(fc.name, fc.args)`; append the **raw model `Content`**
   (verbatim — it carries gemini-3's `id` + `thought_signature`) and a
   `Part.from_function_response(...)` to `contents`; loop.
3. When a turn has no function call, switch to `generate_content_stream` (AFC
   still disabled) for the final text-only turn so the user keeps token streaming
   (safe — no tools to execute on the last turn).

Benefits: works on 2.5-flash **and** 3.x; no dependency on an upstream fix; gives
ADMZ real tool-call events (the UI already wants them).

### Alternatives
- **Option C** — keep AFC but use non-streaming `generate_content` for tool turns
  (its async-non-stream AFC loop is the robust one), stream a final no-tools turn.
  Less code; loses ADMZ-side tool-call visibility.
- **Option A** — upgrade `google-genai`. Worth doing for model support (bump the
  `>=1.55` pin toward 2.8.0) but it is **not** the fix.

## Code areas (Option B)
- `admz/chatbot/client.py::_stream_via_models_api` — the manual loop; keep the
  current single streaming call when `mcp_session is None`.
- config builder — add `automatic_function_calling={"disable": True}`; keep the
  dynamic `thinking_config`.
- `_extract_function_call_from_chunk` — reuse to read function calls off the
  non-streaming response; the existing `event_tool_call` emission becomes a real
  signal.

## Test implications
- The chat-API "Case B / AFC-broken-stream" test encodes the *current* bug as
  expected behaviour — rewrite it to assert the manual loop yields text on 3.x.
- Keep generous e2e timeouts (the loop adds one round-trip per tool turn).
- Add a unit test: patch `generate_content` to return a `function_call` then a
  text part; assert `call_tool` is invoked and the model `Content` (with
  `thought_signature`) is appended to `contents` verbatim.

## Sources
- python-genai issues [#1593](https://github.com/googleapis/python-genai/issues/1593),
  [#106](https://github.com/googleapis/python-genai/issues/106),
  [#331](https://github.com/googleapis/python-genai/issues/331)
- [Gemini API — Function calling (gemini-3 id + mandatory thought_signature)](https://ai.google.dev/gemini-api/docs/function-calling)
- SDK source: `google/genai/models.py` (async-stream AFC loop; TODO b/453739108),
  `_extra_utils.py`.
