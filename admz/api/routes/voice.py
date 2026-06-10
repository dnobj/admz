"""WebSocket route for realtime voice conversation (Gemini Live).

``WS /api/chat/voice`` bridges the browser to a :class:`VoiceSession`:

  browser → server : binary frames = 16 kHz/16-bit/mono PCM mic audio;
                     JSON text frames = control ({"type":"text","text":...}
                     for typed input, {"type":"audio_end"} to end a phrase).
  server → browser : binary frames = 24 kHz PCM to play; JSON frames =
                     transcripts / tool notices / status (see VoiceSession).

The session uses the native-audio model with full ADMZ tools; tool calls run
through the same operations gate as text chat (writes come back ``blocked``
for web confirmation).
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)


async def _ws_principal(websocket: WebSocket):
    """Resolve the principal for a WebSocket.

    The HTTP auth middleware doesn't run on WS upgrades, so authenticate
    directly via the active backend (header-based backends still see the
    upgrade request's headers). Falls back to anonymous — matching the
    default ``ADMZ_AUTH_BACKEND=none`` behaviour of the HTTP routes.
    """
    from admz.auth import Principal
    try:
        from admz.auth import get_active_backend

        return await get_active_backend().authenticate(websocket)
    except Exception:
        return Principal(
            name="anonymous", display_name="anonymous",
            source="none", is_anonymous=True,
        )


@router.websocket("/api/chat/voice")
async def voice_ws(websocket: WebSocket):
    await websocket.accept()

    from admz.chatbot.config import get_chatbot_config
    from admz.chatbot.voice import VoiceSession, voice_available

    config = get_chatbot_config()
    if not voice_available(config):
        await websocket.send_json(
            {"type": "error", "error": "Voice is not configured (no Gemini API key)."}
        )
        await websocket.close(code=1011)
        return

    principal = await _ws_principal(websocket)

    try:
        async with VoiceSession(
            api_key=config.api_key,
            principal_name=principal.name,
            display_name=getattr(principal, "display_name", None),
            groups=list(getattr(principal, "groups", None) or []),
        ) as vs:
            await websocket.send_json({
                "type": "ready",
                "model": vs.model_name,
                "tools_enabled": vs.tools_enabled,
                "input_sample_rate": 16000,
                "output_sample_rate": 24000,
            })
            await _relay(websocket, vs)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # surface a tidy error, then close
        logger.warning("Voice session error: %s", exc, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "error": str(exc)[:200]})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


async def _relay(websocket: WebSocket, vs) -> None:
    """Pump browser↔Gemini until either side ends."""

    async def from_browser():
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                return
            data_bytes = msg.get("bytes")
            if data_bytes is not None:
                await vs.send_audio(data_bytes)
                continue
            text = msg.get("text")
            if not text:
                continue
            try:
                ctrl = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                continue
            kind = ctrl.get("type")
            if kind == "text" and ctrl.get("text"):
                await vs.send_text(ctrl["text"])
            elif kind == "audio_end":
                await vs.send_audio_end()

    async def to_browser():
        async for ev in vs.stream():
            if ev.get("type") == "audio":
                await websocket.send_bytes(ev["data"])
            else:
                await websocket.send_json(ev)

    tasks = [
        asyncio.create_task(from_browser()),
        asyncio.create_task(to_browser()),
    ]
    try:
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
