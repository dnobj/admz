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

import asyncio
import logging
import os
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retry policy for transient Gemini errors
# ---------------------------------------------------------------------------


# HTTP codes we consider retryable. 429 = rate-limited, 5xx = server-side
# transient failures (the canonical 503 "high demand" message from Gemini
# falls here).
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

_DEFAULT_RETRY_MAX_ATTEMPTS = 3   # 1 try + 2 retries
_DEFAULT_RETRY_BASE_DELAY = 0.5   # 0.5s, 1.0s, 2.0s
_DEFAULT_RETRY_JITTER = 0.25       # ±25% jitter on the delay


def _get_retry_max_attempts() -> int:
    """Read ADMZ_GEMINI_RETRY_MAX_ATTEMPTS (default 3, min 1)."""
    raw = os.getenv("ADMZ_GEMINI_RETRY_MAX_ATTEMPTS")
    if raw is None:
        return _DEFAULT_RETRY_MAX_ATTEMPTS
    try:
        return max(1, int(raw))
    except ValueError:
        logger.warning(
            "Invalid ADMZ_GEMINI_RETRY_MAX_ATTEMPTS=%r; using default %d",
            raw,
            _DEFAULT_RETRY_MAX_ATTEMPTS,
        )
        return _DEFAULT_RETRY_MAX_ATTEMPTS


def _get_thinking_budget() -> int:
    """Return the Gemini 'thinking' token budget.

    0 (default) disables thinking — recommended for chat-style use
    where thinking-only completions show up as empty responses.
    Set ADMZ_GEMINI_THINKING_BUDGET to a positive integer to enable
    thinking with that many tokens.
    """
    raw = os.getenv("ADMZ_GEMINI_THINKING_BUDGET")
    if raw is None:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning(
            "Invalid ADMZ_GEMINI_THINKING_BUDGET=%r; using default 0", raw
        )
        return 0


def _get_retry_base_delay() -> float:
    """Read ADMZ_GEMINI_RETRY_BASE_DELAY (seconds, default 0.5)."""
    raw = os.getenv("ADMZ_GEMINI_RETRY_BASE_DELAY")
    if raw is None:
        return _DEFAULT_RETRY_BASE_DELAY
    try:
        return max(0.05, float(raw))
    except ValueError:
        logger.warning(
            "Invalid ADMZ_GEMINI_RETRY_BASE_DELAY=%r; using default %ss",
            raw,
            _DEFAULT_RETRY_BASE_DELAY,
        )
        return _DEFAULT_RETRY_BASE_DELAY


# Error types that indicate a pooled MCP session is dead (subprocess
# crashed, stdio streams closed by the bridge teardown, etc.). When
# we see one of these *before* any chunks have been yielded to the
# user, stream_turn evicts the pool entry and retries the turn once.
def _is_session_dead_error(exc: BaseException) -> bool:
    """True if ``exc`` indicates the pooled MCP session is unusable."""
    if isinstance(exc, BrokenPipeError):
        return True
    # anyio's ClosedResourceError is the canonical signal from
    # mcp.client.session when the stdio streams are gone.
    try:
        import anyio
        if isinstance(exc, anyio.ClosedResourceError):
            return True
    except ImportError:  # pragma: no cover — anyio is a transitive dep
        pass
    # Some SDK versions wrap the underlying error; check the cause/context chain.
    cause = getattr(exc, "__cause__", None)
    if cause is not None and cause is not exc:
        if _is_session_dead_error(cause):
            return True
    ctx = getattr(exc, "__context__", None)
    if ctx is not None and ctx is not exc:
        if _is_session_dead_error(ctx):
            return True
    return False


async def _evict_stale_session(principal: Optional[str]) -> None:
    """Drop ``principal``'s pool entry so the next acquire spawns fresh."""
    if not principal:
        return
    try:
        from admz.chatbot import mcp_pool as _pool_module
        await _pool_module.mcp_pool.evict(principal)
    except Exception as exc:  # pragma: no cover — eviction must never block recovery
        logger.warning("Failed to evict stale MCP session: %s", exc)


def _is_retryable_error(exc: BaseException) -> bool:
    """True if ``exc`` is a transient Gemini error worth retrying.

    google-genai raises errors.ServerError / ClientError with a
    ``code`` (or ``status_code``) attribute. We retry on the
    canonical transient set; everything else surfaces immediately.
    """
    # Probe both common attribute names; SDK has used both.
    code = (
        getattr(exc, "code", None)
        or getattr(exc, "status_code", None)
    )
    try:
        code_int = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_int = None
    return code_int in _RETRYABLE_STATUS_CODES


def _compute_retry_delay(attempt: int, base: float, jitter: float = _DEFAULT_RETRY_JITTER) -> float:
    """Exponential backoff with optional jitter.

    ``attempt`` is 1-indexed (first retry = 1). Delay is base * 2**(attempt-1)
    with ±jitter*100% randomization to spread retries from concurrent users.
    """
    delay = base * (2 ** (attempt - 1))
    if jitter:
        delay *= 1.0 + random.uniform(-jitter, jitter)
    return max(0.0, delay)


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
    """Lazy-import :mod:`google.genai`. Raises ChatbotDependencyMissing if absent.

    Also disables genai's optional aiohttp transport — it has a bug
    in 2.4.0 where the streaming response reader calls
    ``aiohttp.StreamReader.readline(max_line_length=...)``, which
    aiohttp 3.13+ doesn't accept. Forcing ``has_aiohttp=False`` makes
    genai route streaming through its httpx transport, which works.
    Aiohttp itself stays installed (the discovery stack depends on
    it transitively via ``async_upnp_client``) — we just stop genai
    from picking it up.
    """
    try:
        from google import genai  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ChatbotDependencyMissing(
            "The google-genai package is not installed. Add it to "
            "requirements.txt and pip install, or disable the chatbot."
        ) from exc

    # Workaround for google-genai 2.4.0 streaming bug. Setting the
    # module attribute is enough — the flag is checked at request
    # time, not import time. Harmless if genai later fixes the bug
    # (forcing httpx still works).
    try:
        from google.genai import _api_client as _genai_api_client
        if getattr(_genai_api_client, "has_aiohttp", False):
            _genai_api_client.has_aiohttp = False
            logger.debug(
                "google-genai aiohttp transport disabled to avoid the "
                "readline(max_line_length=...) streaming bug; falling "
                "back to httpx."
            )
    except Exception:  # pragma: no cover — defensive
        pass

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


def _build_contents(history: Optional[list], user_message: str):
    """Build the ``contents`` arg for generate_content_stream.

    Without history: returns the bare user_message string (SDK accepts
    it as a single user turn). With history: builds a list of role-
    tagged items in chronological order ending with the new user
    message.

    Each item has the shape::

        {"role": "user" | "model", "parts": [{"text": "<text>"}]}

    The 'model' role is what Gemini uses for assistant turns (not
    'assistant' as OpenAI does — same content, different name).
    """
    if not history:
        return user_message

    items = []
    for entry in history:
        role = entry.get("role", "user")
        text = entry.get("text", "")
        if not text:
            continue
        # Normalize: only 'user' and 'model' roles are accepted.
        normalized_role = "model" if role in ("model", "assistant") else "user"
        items.append({"role": normalized_role, "parts": [{"text": text}]})
    items.append({"role": "user", "parts": [{"text": user_message}]})
    return items


async def stream_turn(
    *,
    user_message: str,
    api_key: str,
    model: str,
    system_prompt: str,
    previous_interaction_id: Optional[str] = None,
    history: Optional[list] = None,
    use_tools: bool = True,
    principal: Any = None,
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

    ``history`` is a list of ``{"role": "user"|"model", "text": ...}``
    dicts representing prior turns. When non-empty, it's converted
    to the Gemini ``contents=[...]`` wire shape with role markers
    so the model sees prior conversation. The route loads this from
    the chat_history SQLite table per principal.

    ``previous_interaction_id`` is retained for backward compatibility
    but the models API ignores it — history threading happens via
    ``history`` now.

    ``use_tools`` is True by default: the bridge passes an MCP
    session to Gemini as a tool source. When ``principal`` is
    provided, the session is acquired through the per-principal
    pool (Phase 7) so multiple turns reuse the same MCP
    subprocess. With ``principal=None`` we fall back to the
    per-turn spawn from Phase 5B-MCP — that's the path tests use
    when they don't want pooling semantics. If the bridge fails
    (mcp not installed, spawn error), the turn proceeds without
    tools and an informational text event notes the degradation.
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

    # Build the contents array. If history is present, include each
    # prior turn as a separate item with role markers, then append the
    # new user message. The SDK accepts either a plain string (single
    # user turn) or a list of role-tagged items — we always use the
    # list form when there's history.
    contents = _build_contents(history, user_message)

    request_kwargs = {
        "model": model,
        "system_instruction": system_prompt,
        "contents": contents,
    }
    if previous_interaction_id:
        # Retained for any legacy path that still cares; the models
        # API ignores it but no harm in carrying it.
        request_kwargs["previous_interaction_id"] = previous_interaction_id

    final_interaction_id: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    yielded_chunks = False  # Tracks whether any text/tool_call event has been emitted

    # Open the MCP bridge if requested; degrade to no-tools on failure.
    # When a principal is supplied, route through the pool so the
    # MCP subprocess survives between turns. Otherwise use the
    # per-turn spawn path (Phase 5B-MCP).
    #
    # Two attempts in the loop: the first tries the pooled session
    # if one exists; if it's dead (anyio.ClosedResourceError when
    # the SDK calls list_tools on the stale stdio streams), we evict
    # the pool entry and retry once with a fresh subprocess. Only
    # safe to retry if no chunks have been yielded to the caller —
    # otherwise we'd duplicate text in the user's view.
    failed_with_session_dead = False
    for session_attempt in (1, 2):
        if failed_with_session_dead:
            await _evict_stale_session(principal)
            failed_with_session_dead = False

        mcp_cm = _open_mcp_or_none(use_tools, principal=principal)
        try:
            async with mcp_cm as mcp_session:
                if use_tools and mcp_session is None:
                    yield event_text(
                        "(MCP tools unavailable — proceeding without device access. "
                        "Check server logs for bridge errors.)\n"
                    )
                    yielded_chunks = True
                async for chunk in _invoke_stream_with_retry(
                    client, request_kwargs, mcp_session=mcp_session
                ):
                    if logger.isEnabledFor(logging.DEBUG):
                        _log_chunk_shape(chunk)

                    # Track usage_metadata + interaction_id from EVERY
                    # chunk, not just terminal ones. google-genai 2.x
                    # attaches usage_metadata to every text chunk; keep
                    # the latest so the final done event is accurate.
                    chunk_in, chunk_out = _extract_usage_from_chunk(chunk)
                    if chunk_in is not None:
                        input_tokens = chunk_in
                    if chunk_out is not None:
                        output_tokens = chunk_out
                    chunk_id = (
                        getattr(chunk, "id", None)
                        or getattr(chunk, "interaction_id", None)
                        or getattr(chunk, "response_id", None)
                    )
                    if chunk_id:
                        final_interaction_id = chunk_id

                    event = _translate_stream_chunk(chunk)
                    if event is None:
                        continue
                    if event.type.value == "done":
                        # done-shape chunks: metadata already tracked above.
                        continue
                    yielded_chunks = True
                    yield event
            # Stream finished cleanly — break the session-retry loop.
            break
        except Exception as exc:
            if (
                _is_session_dead_error(exc)
                and session_attempt == 1
                and not yielded_chunks
                and principal is not None
            ):
                # Safe to retry — pool entry is stale, evict and try once more.
                logger.warning(
                    "MCP pooled session for %s appears dead (%s); "
                    "evicting and retrying turn once",
                    principal,
                    type(exc).__name__,
                )
                failed_with_session_dead = True
                continue
            logger.exception("Gemini streaming failed: %s", exc)
            yield event_error(f"Gemini stream error: {exc}")
            return

    yield event_done(
        interaction_id=final_interaction_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


@asynccontextmanager
async def _open_mcp_or_none(use_tools: bool, *, principal: Any = None):
    """Yield an MCP session, or ``None`` if tools are disabled / bridge fails.

    Centralizes the 'best-effort tools' policy: if the bridge can't
    be opened, the chat still works (just without device access).
    The decision is intentionally not exposed as a flag the model
    can flip — it's a deployment-time concern.

    ``principal`` accepts either a bare string name (legacy/test
    callers) or a :class:`admz.auth.Principal` (CR-4: full identity
    is forwarded to the MCP subprocess via env vars so every tool
    call is audit-logged with the correct requester).

    When ``principal`` is provided, route through the pool so the
    MCP subprocess survives idle between turns (Phase 7). Otherwise
    use the per-turn spawn (Phase 5B-MCP). Tests that don't want
    pool semantics pass ``principal=None``.
    """
    if not use_tools:
        yield None
        return

    if principal is not None:
        from admz.chatbot import mcp_pool as _pool_module
        async with _pool_module.mcp_pool.acquire(principal) as session:
            yield session
        return

    try:
        async with open_mcp_session() as session:
            yield session
    except (McpBridgeMissing, McpBridgeError) as exc:
        logger.warning("MCP bridge unavailable, proceeding without tools: %s", exc)
        yield None


async def _invoke_stream_with_retry(
    client: Any,
    request_kwargs: dict,
    *,
    mcp_session: Any = None,
):
    """Wrap _invoke_stream with retry-on-transient-error semantics.

    Retries the *entire* stream call when Gemini returns a
    retryable status (429 / 5xx) and **no chunks have yet been
    yielded** to the caller. Once a chunk has been forwarded
    downstream we can't safely retry — the user would see
    duplicated text — so the next failure surfaces unchanged.

    Safety notes:
      - With AFC enabled, retrying means the SDK re-executes any
        tools it already invoked. Read-only tools (list_devices,
        get_device, query_catalog, etc.) are idempotent so this
        is fine. Write tools are gated behind the /confirm flow
        before the MCP tool actually fires, so a retry doesn't
        re-execute the user's intent.
      - Bounded by ADMZ_GEMINI_RETRY_MAX_ATTEMPTS (default 3).
    """
    max_attempts = _get_retry_max_attempts()
    base_delay = _get_retry_base_delay()

    for attempt in range(1, max_attempts + 1):
        yielded_any = False
        try:
            async for chunk in _invoke_stream(
                client, request_kwargs, mcp_session=mcp_session
            ):
                yielded_any = True
                yield chunk
            # Stream completed cleanly — done.
            return
        except Exception as exc:
            if yielded_any:
                # Can't retry mid-stream; surface the error so the
                # caller can convert it into an event_error.
                raise
            if not _is_retryable_error(exc):
                raise
            if attempt >= max_attempts:
                logger.warning(
                    "Gemini stream giving up after %d attempt(s): %s",
                    attempt,
                    exc,
                )
                raise
            delay = _compute_retry_delay(attempt, base_delay)
            logger.info(
                "Gemini stream retrying (attempt %d/%d) after %.2fs: %s",
                attempt,
                max_attempts,
                delay,
                exc,
            )
            await asyncio.sleep(delay)


async def _invoke_stream(
    client: Any,
    request_kwargs: dict,
    *,
    mcp_session: Any = None,
):
    """Call the SDK's streaming method and yield raw chunks.

    Always routes through ``client.aio.models.generate_content_stream``
    — that's the SDK surface that supports MCP tools, history
    threading via the ``contents=[...]`` shape, AND the
    ``thinking_config`` knob we use to suppress empty-output
    completions. The Interactions API path was attractive for its
    server-side conversation state but it doesn't honor
    thinking_config, doesn't support MCP tools, and the
    ``previous_interaction_id`` it returns is silently ignored by
    every other API surface we use. Not worth the inconsistency.

    Isolated as its own function so tests can patch it without
    monkey-patching the SDK.
    """
    async for chunk in _stream_via_models_api(
        client, request_kwargs, mcp_session=mcp_session
    ):
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

    # Disable Gemini 2.5's "thinking" mode by default. Thinking-mode
    # responses occasionally emit zero output tokens (the model spent
    # its budget reasoning internally without producing visible text),
    # which surfaces to the user as empty bot bubbles. For chat-style
    # use, the cost of thinking outweighs the benefit; explicit
    # reasoning isn't useful when the answer is "look up the device's
    # IP from history" or "list 8 devices."
    #
    # Operators who want thinking enabled can set
    # ADMZ_GEMINI_THINKING_BUDGET > 0 (in tokens). 0 disables.
    thinking_budget = _get_thinking_budget()
    if thinking_budget == 0:
        config["thinking_config"] = {"thinking_budget": 0}
    elif thinking_budget > 0:
        config["thinking_config"] = {"thinking_budget": thinking_budget}

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


def _log_chunk_shape(chunk: Any) -> None:
    """DEBUG: log a chunk's shape so translator misses are visible.

    Off unless the logger is at DEBUG. Stays compact — repr of the
    chunk plus the candidate-part text if present.
    """
    try:
        text = _extract_text_from_chunk(chunk) or ""
        usage = getattr(chunk, "usage_metadata", None) or getattr(chunk, "usage", None)
        logger.debug(
            "[chat] raw chunk type=%s text=%r usage=%r",
            type(chunk).__name__,
            text[:200],
            usage,
        )
    except Exception:  # pragma: no cover — diagnostic must never crash
        logger.debug("[chat] raw chunk type=%s (repr failed)", type(chunk).__name__)


def _extract_text_from_chunk(chunk: Any) -> Optional[str]:
    """Pull text out of a google-genai streaming chunk.

    The SDK puts text under ``candidates[0].content.parts[*].text``.
    Older shapes might surface a flat ``.text`` property or ``.delta``;
    we try the flat path first, then walk the nested structure.
    """
    flat = (
        getattr(chunk, "text", None)
        or getattr(chunk, "delta", None)
        or getattr(chunk, "output_text", None)
    )
    if isinstance(flat, str) and flat:
        return flat

    # google-genai GenerateContentResponse: candidates[0].content.parts[*].text
    candidates = getattr(chunk, "candidates", None)
    if candidates:
        try:
            content = getattr(candidates[0], "content", None)
            parts = getattr(content, "parts", None) if content else None
        except (IndexError, AttributeError):
            return None
        if parts:
            collected = []
            for part in parts:
                t = getattr(part, "text", None)
                if isinstance(t, str) and t:
                    collected.append(t)
            if collected:
                return "".join(collected)
    return None


def _extract_function_call_from_chunk(chunk: Any) -> Optional[str]:
    """Pull a function_call name from a chunk if present.

    With AFC enabled the SDK handles tool roundtrips internally, but
    some response shapes surface the function_call to the consumer
    too. Return the name (we render a card) so the UI can show what
    fired.
    """
    fc = getattr(chunk, "function_call", None)
    if fc is not None:
        name = getattr(fc, "name", None)
        if isinstance(name, str) and name:
            return name

    candidates = getattr(chunk, "candidates", None)
    if candidates:
        try:
            content = getattr(candidates[0], "content", None)
            parts = getattr(content, "parts", None) if content else None
        except (IndexError, AttributeError):
            return None
        if parts:
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    name = getattr(fc, "name", None)
                    if isinstance(name, str) and name:
                        return name
    return None


def _extract_usage_from_chunk(chunk: Any):
    """Return (input_tokens, output_tokens) from a chunk, or (None, None).

    google-genai puts usage on ``usage_metadata`` with fields
    ``prompt_token_count`` and ``candidates_token_count``. Older
    SDKs used ``input_tokens``/``output_tokens`` on a ``usage`` dict.
    """
    um = getattr(chunk, "usage_metadata", None)
    if um is not None:
        in_t = (
            getattr(um, "prompt_token_count", None)
            or getattr(um, "input_tokens", None)
        )
        out_t = (
            getattr(um, "candidates_token_count", None)
            or getattr(um, "output_tokens", None)
        )
        if in_t is not None or out_t is not None:
            return in_t, out_t

    usage = getattr(chunk, "usage", None)
    if isinstance(usage, dict):
        return (
            usage.get("input_tokens") or usage.get("prompt_tokens"),
            usage.get("output_tokens") or usage.get("completion_tokens"),
        )
    if usage is not None:
        return (
            getattr(usage, "input_tokens", None)
            or getattr(usage, "prompt_tokens", None),
            getattr(usage, "output_tokens", None)
            or getattr(usage, "completion_tokens", None),
        )
    return None, None


def _translate_stream_chunk(chunk: Any) -> Optional[ChatEvent]:
    """Translate one SDK chunk into a ChatEvent.

    Returns None to skip the chunk silently. Probes both the legacy
    flat shape (text/delta/output_text on the chunk object) and the
    real google-genai 2.x shape (candidates[].content.parts[]).
    """
    # Tool-call step (Phase 5B-MCP). AFC may handle these internally
    # but some chunks still surface them.
    step_type = getattr(chunk, "step_type", None)
    if step_type in ("function_call", "tool_call"):
        name = (
            getattr(chunk, "name", None)
            or _extract_function_call_from_chunk(chunk)
            or "tool"
        )
        return event_tool_call(name=name, args_summary=f"{name}(...)")
    fc_name = _extract_function_call_from_chunk(chunk)
    if fc_name and not _extract_text_from_chunk(chunk):
        return event_tool_call(name=fc_name, args_summary=f"{fc_name}(...)")

    # Text delta — flat OR nested under candidates[].content.parts[].
    delta = _extract_text_from_chunk(chunk)
    if delta:
        return event_text(delta)

    # Terminal metadata — usage_metadata on the final chunk.
    input_tokens, output_tokens = _extract_usage_from_chunk(chunk)
    interaction_id = (
        getattr(chunk, "id", None)
        or getattr(chunk, "interaction_id", None)
        or getattr(chunk, "response_id", None)
    )
    if input_tokens is not None or output_tokens is not None or interaction_id:
        return event_done(
            interaction_id=interaction_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    return None
