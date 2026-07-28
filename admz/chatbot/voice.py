"""Realtime voice conversation over the Gemini Live API.

A ``VoiceSession`` bridges a browser (mic audio in, speaker audio out) to a
Gemini **Live** session, with live text transcripts of both sides and the full
ADMZ MCP tool surface available to the model. The browser↔server transport is
a WebSocket (see ``admz/api/routes/voice.py``); this module owns the
server↔Gemini half.

Key facts (verified live against google-genai 2.5.0 with the ADMZ key):
- The only Live/voice-capable model on the key is
  ``gemini-2.5-flash-native-audio-preview-09-2025`` (no 3.x Live variant
  exists for this project). Voice mode always uses that model, independent of
  the text-chat model selection.
- Input audio is 16 kHz / 16-bit / mono PCM; output audio is 24 kHz PCM.
- Tool calls work over Live: the model emits ``tool_call``; we execute via the
  ADMZ MCP session and reply with ``send_tool_response``. Tool execution goes
  through the *same* operations gate as text chat — so read ops run and
  write/dangerous ops come back as a ``blocked`` envelope the model speaks
  ("approve in the ADMZ web UI"). That gives "full tools incl. gated writes"
  without any voice-specific safety bypass.

Test seam: ``send_text()`` lets a test (or a typed-input UI) drive a turn
without audio, so the bridge is exercisable without a microphone.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

logger = logging.getLogger(__name__)

# Live/voice-capable models on the project key (each verified 2026-06-10 to
# stream audio + input/output transcription + tool calls). Listed newest-first;
# the UI lets the operator pick one to A/B test.
#   - gemini-3.1-flash-live-preview            : newest 3.1 audio-to-audio,
#       native audio output + thinking, tuned for low-latency dialogue.
#   - gemini-2.5-flash-native-audio-latest     : rolling 2.5 native-audio alias.
#   - gemini-2.5-flash-native-audio-preview-12-2025 : pinned newer 2.5 native.
#   - gemini-2.5-flash-native-audio-preview-09-2025 : the first one we shipped.
VOICE_MODELS = [
    "gemini-3.1-flash-live-preview",
    "gemini-2.5-flash-native-audio-latest",
    "gemini-2.5-flash-native-audio-preview-12-2025",
    "gemini-2.5-flash-native-audio-preview-09-2025",
]
DEFAULT_VOICE_MODEL = "gemini-3.1-flash-live-preview"
# Back-compat alias.
VOICE_MODEL = DEFAULT_VOICE_MODEL

# Prebuilt voices (verified to work across both model families). Pinning one
# keeps the voice consistent between sessions — without this the Live API picks
# its own each time, which is why the voice varied. Native-audio models support
# many more; these core voices are the portable set.
VOICE_NAMES = ["Puck", "Charon", "Kore", "Fenrir", "Aoede", "Leda", "Orus", "Zephyr"]
DEFAULT_VOICE_NAME = "Puck"


def resolve_voice_model(model: Optional[str]) -> str:
    """Return ``model`` if it's an allowed voice model, else the default."""
    return model if model in VOICE_MODELS else DEFAULT_VOICE_MODEL


def resolve_voice_name(voice: Optional[str]) -> str:
    """Return ``voice`` if it's an allowed prebuilt voice, else the default."""
    return voice if voice in VOICE_NAMES else DEFAULT_VOICE_NAME


# --------------------------------------------------------------------------
# One-shot "dictate" mode: transcribe a recorded clip with a non-realtime
# multimodal model, then submit the text to the normal text chat (so the full
# tool loop + the inline approval widget apply, unchanged). Speech-to-text only
# — no spoken reply.
# --------------------------------------------------------------------------

STT_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]
DEFAULT_STT_MODEL = "gemini-2.5-flash"


def resolve_stt_model(model: Optional[str]) -> str:
    return model if model in STT_MODELS else DEFAULT_STT_MODEL


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    """Wrap raw little-endian 16-bit mono PCM in a minimal WAV container.

    One-shot ``generate_content`` transcription is unreliable on *raw* PCM
    bytes (it hallucinates), but transcribes a proper WAV cleanly. The mic
    worklet emits little-endian Int16, which is exactly WAV's PCM byte order.
    """
    import struct

    ds = len(pcm)
    return (
        b"RIFF" + struct.pack("<I", 36 + ds) + b"WAVE"
        + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
        + b"data" + struct.pack("<I", ds) + pcm
    )


async def transcribe_audio(
    *,
    api_key: str,
    audio: bytes,
    model: Optional[str] = None,
    sample_rate: int = 16000,
) -> str:
    """Transcribe 16-bit mono PCM to text via a multimodal model.

    Used by dictate mode. The PCM is wrapped in a WAV container first (raw PCM
    transcribes unreliably). Returns the transcript text (empty on no speech).
    """
    from google import genai
    from google.genai import types

    wav = _pcm_to_wav(audio, int(sample_rate))
    client = genai.Client(api_key=api_key)
    resp = await client.aio.models.generate_content(
        model=resolve_stt_model(model),
        contents=[
            types.Part.from_bytes(data=wav, mime_type="audio/wav"),
            types.Part(text=(
                "Transcribe the spoken audio to text verbatim. Reply with ONLY "
                "the transcript — no quotes, no commentary, no preamble. If "
                "there is no clear speech, reply with an empty string."
            )),
        ],
    )
    return (getattr(resp, "text", "") or "").strip()


INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000
INPUT_MIME = f"audio/pcm;rate={INPUT_SAMPLE_RATE}"

_VOICE_PROMPT_NOTE = (
    "\n\n# Voice mode\n"
    "Your replies are spoken aloud, so be concise and conversational. Don't "
    "read out long MAC addresses, tokens, or URLs unless asked. You have the "
    "full ADMZ tool surface: use it to answer questions about the live fleet "
    "and to make changes. If a tool result comes back `blocked` (a "
    "service-affecting or dangerous operation needs web confirmation), an "
    "**approval card appears on the user's screen automatically** — say one "
    "short sentence like 'I've put an approval up on screen — approve it there "
    "and I'll continue.' Do NOT read out the URL or the token; just point them "
    "to the on-screen card. You cannot approve it yourself."
)


def voice_available(config: Any) -> bool:
    """True when a Gemini API key is configured (voice can run)."""
    return bool(getattr(config, "api_key", None))


class VoiceSession:
    """Server-side half of a realtime voice conversation.

    Lifecycle: ``async with VoiceSession(...) as vs:`` opens the MCP tool
    session and the Gemini Live session. Feed input with ``send_audio`` /
    ``send_text``; consume model output (audio + transcripts + tool notices)
    by iterating ``stream()``. Tool calls are handled internally.
    """

    def __init__(
        self,
        *,
        api_key: str,
        principal_name: str,
        display_name: Optional[str] = None,
        groups: Optional[List[str]] = None,
        model: Optional[str] = None,
        voice: Optional[str] = None,
        use_tools: bool = True,
    ):
        self._api_key = api_key
        self._principal_name = principal_name
        self._display_name = display_name
        self._groups = groups
        self._model = resolve_voice_model(model)
        self._voice = resolve_voice_name(voice)
        self._use_tools = use_tools

        self._mcp = None
        self._mcp_cm = None
        self._live_cm = None
        self._session = None
        self._types = None

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def voice_name(self) -> str:
        return self._voice

    @property
    def tools_enabled(self) -> bool:
        return self._mcp is not None

    # -- lifecycle ----------------------------------------------------------

    async def __aenter__(self) -> "VoiceSession":
        from google import genai
        from google.genai import types

        from admz.chatbot.system_prompt import build_system_prompt
        from admz.chatbot.context import (
            build_demos_section,
            build_inference_section,
            build_module_prompt_sections,
        )
        from admz.chatbot.client import _mcp_declarations

        self._types = types
        tools = []

        if self._use_tools:
            try:
                from admz.chatbot.mcp_bridge import open_mcp_session

                extra_env = {
                    "ADMZ_PRINCIPAL_NAME": self._principal_name,
                    "ADMZ_MCP_NO_SCHEDULER": "1",  # H-1: pool subprocesses don't schedule
                }
                if self._display_name:
                    extra_env["ADMZ_PRINCIPAL_DISPLAY_NAME"] = self._display_name
                if self._groups:
                    extra_env["ADMZ_PRINCIPAL_GROUPS"] = ",".join(self._groups)
                self._mcp_cm = open_mcp_session(extra_env=extra_env)
                self._mcp = await self._mcp_cm.__aenter__()
                tools = await _mcp_declarations(self._mcp, types)
            except Exception as exc:  # degrade to no-tools rather than fail the call
                logger.warning("Voice: MCP tools unavailable, continuing without: %s", exc)
                self._mcp = None

        prompt = build_system_prompt(
            self._principal_name, display_name=self._display_name,
            groups=self._groups,
            module_sections=build_module_prompt_sections(),
            demos_section=build_demos_section(),
            inference_section=build_inference_section(),
        ) + _VOICE_PROMPT_NOTE

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction=prompt,
            tools=tools,
            # Pin the voice so it's consistent between sessions.
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self._voice
                    )
                )
            ),
        )

        client = genai.Client(api_key=self._api_key)
        self._live_cm = client.aio.live.connect(model=self._model, config=config)
        self._session = await self._live_cm.__aenter__()
        logger.info(
            "Voice session opened (model=%s, tools=%d) for %s",
            self._model, sum(len(getattr(t, "function_declarations", []) or []) for t in tools),
            self._principal_name,
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._live_cm is not None:
            try:
                await self._live_cm.__aexit__(*exc)
            except Exception:  # pragma: no cover - best effort
                pass
        if self._mcp_cm is not None:
            try:
                await self._mcp_cm.__aexit__(*exc)
            except Exception:  # pragma: no cover - best effort
                pass

    # -- input --------------------------------------------------------------

    async def send_audio(self, pcm: bytes) -> None:
        """Feed a chunk of 16 kHz/16-bit/mono PCM mic audio to the model."""
        await self._session.send_realtime_input(
            audio=self._types.Blob(data=pcm, mime_type=INPUT_MIME)
        )

    async def send_audio_end(self) -> None:
        """Signal end of the user's audio stream (lets VAD finalize promptly)."""
        await self._session.send_realtime_input(audio_stream_end=True)

    async def send_text(self, text: str) -> None:
        """Drive a turn with typed text (test seam / typed-input UI)."""
        await self._session.send_client_content(
            turns=self._types.Content(
                role="user", parts=[self._types.Part(text=text)]
            ),
            turn_complete=True,
        )

    # -- output -------------------------------------------------------------

    async def stream(self) -> AsyncIterator[Dict[str, Any]]:
        """Yield browser-facing events from the model.

        Event shapes:
          {"type": "audio", "data": bytes}            — 24 kHz PCM to play
          {"type": "input_transcript", "text": str}   — what the user said
          {"type": "output_transcript", "text": str}  — what the model said
          {"type": "tool_call", "name", "args"}        — a tool was invoked
          {"type": "tool_result", "name", "blocked"}   — its outcome (compact)
          {"type": "interrupted"} / {"type": "turn_complete"}
        """
        types = self._types
        # The SDK's receive() yields the messages for ONE turn and then
        # completes — so loop it. Without the outer loop the read side ended
        # after the first exchange, the WebSocket closed, and the browser shut
        # the mic off (i.e. it was a single-turn call, not a conversation).
        while True:
            produced = False
            async for msg in self._session.receive():
                produced = True
                tc = getattr(msg, "tool_call", None)
                if tc and getattr(tc, "function_calls", None):
                    for fc in tc.function_calls:
                        args = dict(getattr(fc, "args", None) or {})
                        yield {"type": "tool_call", "name": fc.name, "args": args}
                        result = await self._run_tool(fc.name, args)
                        await self._session.send_tool_response(
                            function_responses=[types.FunctionResponse(
                                id=getattr(fc, "id", None), name=fc.name, response=result,
                            )]
                        )
                        yield {
                            "type": "tool_result", "name": fc.name,
                            "blocked": bool(result.get("blocked")),
                            "success": result.get("success"),
                            # Surface the confirm token so the browser can show
                            # the same approval card the text chat uses, instead
                            # of the model reading the URL aloud.
                            "confirm_token": result.get("confirm_token"),
                        }
                    continue

                sc = getattr(msg, "server_content", None)
                if sc is None:
                    continue
                it = getattr(sc, "input_transcription", None)
                if it and getattr(it, "text", None):
                    yield {"type": "input_transcript", "text": it.text}
                ot = getattr(sc, "output_transcription", None)
                if ot and getattr(ot, "text", None):
                    yield {"type": "output_transcript", "text": ot.text}
                mt = getattr(sc, "model_turn", None)
                if mt:
                    for p in (getattr(mt, "parts", None) or []):
                        inline = getattr(p, "inline_data", None)
                        if inline and getattr(inline, "data", None):
                            yield {"type": "audio", "data": inline.data}
                if getattr(sc, "interrupted", None):
                    yield {"type": "interrupted"}
                if getattr(sc, "turn_complete", None):
                    yield {"type": "turn_complete"}
            # receive() ended. If it produced nothing at all, the session has
            # closed (e.g. the client hung up) — stop. Otherwise loop to await
            # the next turn.
            if not produced:
                break

    async def _run_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if self._mcp is None:
            return {"success": False, "error": "tools unavailable in this session"}
        from admz.chatbot.client import _call_mcp_tool

        try:
            return await _call_mcp_tool(self._mcp, name, args)
        except Exception as exc:
            logger.warning("Voice tool %s failed: %s", name, exc)
            return {"success": False, "error": str(exc)}
