# Realtime voice conversation (Gemini Live)

ADMZ's web console supports a **spoken** conversation with the assistant —
talk to it, hear it answer, and see live text transcripts of both sides — with
the **full ADMZ tool surface** available to the model. Click the 🎙 mic button
in the console composer to start; click it again to stop.

## What model it uses (important)

Voice mode always uses **`gemini-2.5-flash-native-audio-preview-09-2025`**,
independent of the text-chat model selector. This is the only Live/voice-capable
model available on the project's API key — there is **no 3.x voice/Live variant**
(verified live: `gemini-3-pro-preview`, `gemini-3.5-flash`, and the older
`gemini-2.0-flash-live-001` all return "not found for API version v1beta" on this
key). The text models in the dropdown (2.5/3.x) are unaffected; they're for typed
chat.

## What it can do

Full tools, including gated writes:

- **Read** — "How many devices do I have?", "Is the P8815 online?" → the model
  calls real MCP tools (`list_devices`, `search_devices`, `get_device_health`,
  …) and answers from live data.
- **Write** — service-affecting / dangerous operations run through the **same
  confirmation gate** as text chat. A gated op comes back as a `blocked`
  envelope, and the model is instructed to tell you out loud that it needs
  approval in the ADMZ web UI (you can't click a `/confirm` link while talking —
  approve it in the browser, or, in dev, via `tools/dev_auto_approve.py`).

There is no voice-specific safety bypass — voice reuses the text-chat tool
loop and gate verbatim.

## Architecture

```
browser  ──WebSocket /api/chat/voice──►  ADMZ (FastAPI)  ──►  Gemini Live
  mic ─16kHz PCM (binary frames)─►        VoiceSession         (native-audio)
  speaker ◄─24kHz PCM (binary)──          + MCP tools
  transcript ◄─JSON events──              + operations gate
```

- **Browser** (`static/voice.js` + `static/voice-worklet.js`): captures mic
  audio in a 16 kHz `AudioContext` + an `AudioWorklet` that emits 16-bit PCM,
  sends it as binary WS frames; plays the model's 24 kHz PCM via a scheduled
  queue; renders input/output transcripts into the console.
- **Route** (`admz/api/routes/voice.py`): the `WS /api/chat/voice` endpoint.
  Binary frames = audio; JSON frames = control (`{"type":"text",...}` for typed
  input, `{"type":"audio_end"}`). Server→browser: binary = audio to play, JSON =
  transcripts / tool notices / status.
- **Bridge** (`admz/chatbot/voice.py::VoiceSession`): opens the MCP tool session
  + the Gemini Live session (audio response + input/output transcription + the
  ADMZ system prompt + the 45 tools as `FunctionDeclaration`s). Handles
  `tool_call` → `_call_mcp_tool` (through the gate) → `send_tool_response`.
  `send_text()` is a test/typed-input seam so the bridge is exercisable without
  a microphone.

## Audio formats

- Input (mic → Gemini): 16 kHz, 16-bit, mono PCM.
- Output (Gemini → speaker): 24 kHz, 16-bit, mono PCM.

## Availability

The mic button is enabled whenever a Gemini API key is configured (the same
key as text chat — `ADMZ_GEMINI_API_KEY` env / `gemini_api_key` fleet setting).
With no key, voice (and chat) are disabled.

## Tested

- **Server bridge, end to end (real Gemini + real tools + real fleet):** a typed
  turn drove `search_devices` + `get_device_health` and the model spoke "The
  AXIS P8815-2 … is currently online" (393 KB audio + transcript). A simpler
  turn drove `list_devices` → "There are 8 devices registered in your fleet."
- **Route contract:** `tests/test_voice_route.py` (mocked session) — ready
  handshake, audio→binary / events→JSON forwarding, typed-input + binary-audio
  input paths, not-configured error.
- **Not yet automated:** the browser microphone capture + speaker playback —
  that half needs a human to speak. The server proves the rest.

## Limitations / next

- Browser mic/playback is best-effort v1 (no barge-in tuning, no device picker).
- Voice transcripts are not persisted to the chat session history (the text
  chat's `previous_interaction_id` continuity doesn't span voice yet).
- WebSocket auth resolves the principal best-effort and falls back to anonymous
  (matching the default `ADMZ_AUTH_BACKEND=none`); production behind Windows IWA
  would carry the proxy headers on the WS upgrade.
