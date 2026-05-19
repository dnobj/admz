"""Gemini Interactions API client for the ADMZ chatbot.

This module wraps the experimental :mod:`google.genai` SDK and is
imported *lazily* — the import only fires when a chat request
arrives. Installs without the chatbot dependency continue to work
normally; the `/chat` route renders a "not configured" page if
either the SDK or the API key is missing.

The native-MCP feature in :mod:`google.genai` is marked
experimental; if it breaks we fall back to a hand-translation
path (FR-CB-007 fallback note). Phase 5A keeps the wiring simple:
one turn, non-streaming, surface the model's text response. Tool
calls happen inside :mod:`google.genai` against the in-process
MCP server — ADMZ doesn't see individual tool invocations in
this phase.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ChatbotNotConfigured(Exception):
    """Raised when /chat is hit with no API key configured."""


class ChatbotDependencyMissing(Exception):
    """Raised when google-genai isn't installed in the environment."""


class ChatbotTurnError(Exception):
    """Wraps any provider-side error so the route can render a friendly message."""


@dataclass
class TurnResult:
    """Result of a single chat turn."""

    text: str
    model: str
    interaction_id: Optional[str]
    # Approximate token count for the cost footer. None if the SDK
    # didn't surface usage info.
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


def _import_genai() -> Any:
    """Lazy-import :mod:`google.genai`. Raises ChatbotDependencyMissing if absent."""
    try:
        from google import genai  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ChatbotDependencyMissing(
            "The google-genai package is not installed. Add it to "
            "requirements.txt and pip install, or disable the chatbot."
        ) from exc
    return genai


async def run_turn(
    *,
    user_message: str,
    api_key: str,
    model: str,
    system_prompt: str,
    previous_interaction_id: Optional[str] = None,
) -> TurnResult:
    """Run one chat turn against Gemini.

    Phase 5A: non-streaming, one round-trip. The MCP server tool
    surface is *not* yet wired in this function — Phase 5B will
    add it once the streaming path lands. Phase 5A proves the
    end-to-end plumbing (auth → route → SDK → response → store).

    The function is async to match the rest of the FastAPI
    surface and to keep the future streaming version a drop-in
    replacement.
    """
    genai = _import_genai()

    if not api_key:
        raise ChatbotNotConfigured(
            "Gemini API key is not configured. Visit /settings/chat."
        )

    try:
        client = genai.Client(api_key=api_key)
    except Exception as exc:  # pragma: no cover — depends on SDK shape
        raise ChatbotTurnError(f"Failed to construct Gemini client: {exc}") from exc

    # The Interactions API is the v1.55+ primitive — keep the call
    # site narrow so the next phase can swap to the streaming
    # variant and add the local-MCP tool source without
    # disturbing the route.
    request_kwargs = {
        "model": model,
        "system_instruction": system_prompt,
        "contents": user_message,
    }
    if previous_interaction_id:
        request_kwargs["previous_interaction_id"] = previous_interaction_id

    try:
        response = await _invoke(client, request_kwargs)
    except ChatbotTurnError:
        raise
    except Exception as exc:
        logger.exception("Gemini turn failed: %s", exc)
        raise ChatbotTurnError(str(exc)) from exc

    return _result_from_response(response, model)


async def _invoke(client: Any, request_kwargs: dict) -> Any:
    """Call the Gemini Interactions API.

    Isolated as its own function so tests can patch it without
    monkey-patching the SDK.
    """
    interactions = getattr(client, "interactions", None)
    if interactions is None:
        raise ChatbotTurnError(
            "google-genai client does not expose the Interactions API. "
            "Upgrade to google-genai>=1.55."
        )

    create = getattr(interactions, "create", None)
    if create is None:
        raise ChatbotTurnError(
            "google-genai interactions.create() not available."
        )

    # The SDK may expose either an async or sync create(); prefer
    # the async variant if present.
    acreate = getattr(interactions, "acreate", None)
    if acreate is not None:
        return await acreate(**request_kwargs)
    return create(**request_kwargs)


def _result_from_response(response: Any, model: str) -> TurnResult:
    """Extract a normalized TurnResult from the SDK's response object.

    google-genai's response object shape varies a bit across point
    releases; we defensively probe a few attribute names rather
    than coupling to one.
    """
    text = (
        getattr(response, "text", None)
        or getattr(response, "output_text", None)
        or ""
    )
    interaction_id = (
        getattr(response, "id", None)
        or getattr(response, "interaction_id", None)
    )

    usage = getattr(response, "usage", None) or {}
    input_tokens = None
    output_tokens = None
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
        output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
    else:
        input_tokens = (
            getattr(usage, "input_tokens", None)
            or getattr(usage, "prompt_tokens", None)
        )
        output_tokens = (
            getattr(usage, "output_tokens", None)
            or getattr(usage, "completion_tokens", None)
        )

    return TurnResult(
        text=text or "",
        model=model,
        interaction_id=interaction_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


# ---------------------------------------------------------------------------
# Streaming variant — Phase 5B
# ---------------------------------------------------------------------------
#
# stream_turn() is an async generator that yields ChatEvent objects.
# The route forwards them to the browser as SSE. Phase 5B-MCP will
# wire the MCP server in via the tools kwarg here without touching
# the route or the browser-side renderer.


from admz.chatbot.events import (  # noqa: E402 — kept near its consumer
    ChatEvent,
    ChatEventType,
    event_done,
    event_error,
    event_start,
    event_text,
    event_tool_call,
)
from admz.chatbot.mcp_bridge import (  # noqa: E402
    McpBridgeError,
    McpBridgeMissing,
    open_mcp_session,
)


async def stream_turn(
    *,
    user_message: str,
    api_key: str,
    model: str,
    system_prompt: str,
    previous_interaction_id: Optional[str] = None,
    use_tools: bool = True,
):
    """Stream a chat turn as :class:`ChatEvent`s.

    Yields a sequence:

      1. one ``start`` event with the model name
      2. zero or more ``text`` events with incremental chunks
      3. zero or more ``tool_call`` / ``tool_result`` events
         (when MCP bridge is available — Phase 5B-MCP)
      4. one ``done`` event with the final interaction_id + usage
         (or an ``error`` event if the SDK raised)

    The route consumes these and forwards them over SSE.
    Streaming is one-shot: a single async iteration consumes the
    whole stream.

    ``use_tools`` is True by default: the bridge spawns
    ``python -m admz mcp`` and passes the session to Gemini as a
    tool source. If the bridge fails (mcp not installed, spawn
    error), the turn proceeds without tools and an informational
    text event notes the degradation.
    """
    if not api_key:
        yield event_error(
            "Gemini API key is not configured. Visit /settings/chat."
        )
        return

    try:
        genai = _import_genai()
    except ChatbotDependencyMissing as exc:
        yield event_error(str(exc))
        return

    try:
        client = genai.Client(api_key=api_key)
    except Exception as exc:  # pragma: no cover — SDK construction
        yield event_error(f"Failed to construct Gemini client: {exc}")
        return

    yield event_start(model)

    request_kwargs = {
        "model": model,
        "system_instruction": system_prompt,
        "contents": user_message,
    }
    if previous_interaction_id:
        request_kwargs["previous_interaction_id"] = previous_interaction_id

    final_interaction_id: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    # Open the MCP bridge if requested; degrade to no-tools on failure.
    # The bridge subprocess lives for the duration of this turn — when
    # the async-with exits, the MCP server subprocess is reaped.
    mcp_cm = _open_mcp_or_none(use_tools)

    try:
        async with mcp_cm as mcp_session:
            if use_tools and mcp_session is None:
                yield event_text(
                    "(MCP tools unavailable — proceeding without device access. "
                    "Check server logs for bridge errors.)\n"
                )
            async for chunk in _invoke_stream(
                client, request_kwargs, mcp_session=mcp_session
            ):
                event = _translate_stream_chunk(chunk)
                if event is None:
                    continue
                # Capture terminal metadata for the final 'done' event.
                if event.type.value == "done":
                    final_interaction_id = event.payload.get("interaction_id")
                    input_tokens = event.payload.get("input_tokens")
                    output_tokens = event.payload.get("output_tokens")
                    # Don't yield 'done' here — we yield it once at the end.
                    continue
                yield event
    except Exception as exc:
        logger.exception("Gemini streaming failed: %s", exc)
        yield event_error(f"Gemini stream error: {exc}")
        return

    yield event_done(
        interaction_id=final_interaction_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


@asynccontextmanager
async def _open_mcp_or_none(use_tools: bool):
    """Yield an MCP session, or ``None`` if tools are disabled / bridge fails.

    Centralizes the 'best-effort tools' policy: if the bridge can't
    be opened, the chat still works (just without device access).
    The decision is intentionally not exposed as a flag the model
    can flip — it's a deployment-time concern.
    """
    if not use_tools:
        yield None
        return
    try:
        async with open_mcp_session() as session:
            yield session
    except (McpBridgeMissing, McpBridgeError) as exc:
        logger.warning("MCP bridge unavailable, proceeding without tools: %s", exc)
        yield None


async def _invoke_stream(
    client: Any,
    request_kwargs: dict,
    *,
    mcp_session: Any = None,
):
    """Call the SDK's streaming method and yield raw chunks.

    When ``mcp_session`` is provided, route through
    ``client.aio.models.generate_content_stream`` with
    ``config=GenerateContentConfig(tools=[mcp_session])``. That's
    the documented path for ``google-genai``'s native MCP
    integration. When no session is provided, fall back to the
    Interactions API (which is leaner but doesn't support MCP tools
    in the same way).

    Isolated as its own function so tests can patch it without
    monkey-patching the SDK.
    """
    # MCP-bearing path: aio.models.generate_content_stream with
    # tools=[session]. This is the FastMCP-confirmed shape.
    if mcp_session is not None:
        async for chunk in _stream_via_models_api(
            client, request_kwargs, mcp_session=mcp_session
        ):
            yield chunk
        return

    # Otherwise, prefer the Interactions API (slimmer protocol for
    # text-only turns). Fall back to the models API if the SDK
    # version doesn't surface interactions.
    interactions = getattr(client, "interactions", None)
    if interactions is not None:
        stream_fn = (
            getattr(interactions, "astream", None)
            or getattr(interactions, "stream", None)
        )
        if stream_fn is not None:
            result = stream_fn(**request_kwargs)
            async for chunk in _as_async_iter(result):
                yield chunk
            return

    async for chunk in _stream_via_models_api(client, request_kwargs):
        yield chunk


async def _stream_via_models_api(
    client: Any, request_kwargs: dict, *, mcp_session: Any = None
):
    """Stream via ``client.aio.models.generate_content_stream``.

    Builds the SDK's ``GenerateContentConfig`` defensively — the
    config class lives under ``genai.types`` and the SDK is happy
    to accept a dict in its place across recent versions.
    """
    aio = getattr(client, "aio", None)
    models = getattr(aio, "models", None) if aio else None
    stream_fn = getattr(models, "generate_content_stream", None) if models else None
    if stream_fn is None:
        raise ChatbotTurnError(
            "google-genai client exposes neither interactions.stream nor "
            "aio.models.generate_content_stream. Upgrade google-genai."
        )

    config: dict = {}
    sys_inst = request_kwargs.get("system_instruction")
    if sys_inst:
        config["system_instruction"] = sys_inst
    if mcp_session is not None:
        config["tools"] = [mcp_session]

    call_kwargs = {
        "model": request_kwargs["model"],
        "contents": request_kwargs["contents"],
    }
    if config:
        call_kwargs["config"] = _build_generate_config(config)

    result = stream_fn(**call_kwargs)
    async for chunk in _as_async_iter(result):
        yield chunk


def _build_generate_config(config: dict) -> Any:
    """Construct a GenerateContentConfig from a kwargs dict.

    Tries ``genai.types.GenerateContentConfig`` first (the documented
    class); falls back to the raw dict if the class isn't importable
    or doesn't accept our kwargs cleanly. The SDK accepts dicts in
    place of typed configs across recent versions, so the fallback is
    safe.
    """
    try:
        from google.genai import types  # type: ignore[import-not-found]
        cls = getattr(types, "GenerateContentConfig", None)
        if cls is not None:
            return cls(**config)
    except Exception as exc:  # pragma: no cover — SDK shape drift
        logger.debug(
            "GenerateContentConfig unavailable, passing dict instead: %s", exc
        )
    return config


async def _as_async_iter(result: Any):
    """Adapt sync or async iterables to a uniform async iter."""
    if hasattr(result, "__aiter__"):
        async for item in result:
            yield item
        return
    # Could be a coroutine returning an iterable.
    if hasattr(result, "__await__"):
        result = await result
        if hasattr(result, "__aiter__"):
            async for item in result:
                yield item
            return
    # Sync iterable.
    for item in result:
        yield item


def _translate_stream_chunk(chunk: Any) -> Optional[ChatEvent]:
    """Translate one SDK chunk into a ChatEvent.

    Returns None to skip the chunk silently. The SDK's chunk
    shape varies across point releases, so we probe a few common
    attribute names. Streaming chunks come in three flavors:

      - text chunk: a partial text delta
      - tool_call: an explicit function-call step (Phase 5B-MCP
        will exercise this once tools are wired)
      - terminal: the final chunk carries the interaction_id +
        usage info; we use the ``done`` event type as a carrier
        in the stream and translate it to a real ``done`` at the
        end (see stream_turn)
    """
    # Tool-call step: most relevant once MCP is wired.
    step_type = getattr(chunk, "step_type", None)
    if step_type == "function_call" or step_type == "tool_call":
        name = (
            getattr(chunk, "name", None)
            or getattr(getattr(chunk, "function_call", None), "name", None)
            or "tool"
        )
        return event_tool_call(name=name, args_summary=f"{name}(...)")

    # Text delta.
    delta = (
        getattr(chunk, "text", None)
        or getattr(chunk, "delta", None)
        or getattr(chunk, "output_text", None)
    )
    if isinstance(delta, str) and delta:
        return event_text(delta)

    # Terminal metadata (the SDK calls the last chunk
    # "completion" or surfaces usage on it).
    usage = getattr(chunk, "usage", None)
    interaction_id = (
        getattr(chunk, "id", None)
        or getattr(chunk, "interaction_id", None)
    )
    if usage or interaction_id:
        input_tokens = None
        output_tokens = None
        if isinstance(usage, dict):
            input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
            output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
        elif usage is not None:
            input_tokens = (
                getattr(usage, "input_tokens", None)
                or getattr(usage, "prompt_tokens", None)
            )
            output_tokens = (
                getattr(usage, "output_tokens", None)
                or getattr(usage, "completion_tokens", None)
            )
        return event_done(
            interaction_id=interaction_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    return None
