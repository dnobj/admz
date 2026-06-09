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
import json
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

    Default is **-1 (dynamic)**: the model decides how much to think per
    turn. This matters a lot for tool use — with thinking disabled (0),
    gemini-2.5-flash tends to answer device-operation requests from its
    (wrong) training priors instead of calling `query_catalog`/`execute_operation`
    (the canonical failure: it told a user `setMagnification` needs "a number
    between 1 and 9999" and refused, never querying). Dynamic thinking fixes
    that, and is also required by the *-pro models (which reject a budget of 0
    with "only works in thinking mode").

    Override with ADMZ_GEMINI_THINKING_BUDGET:
      -1 = dynamic (default), 0 = disabled, >0 = fixed token budget.
    """
    raw = os.getenv("ADMZ_GEMINI_THINKING_BUDGET")
    if raw is None:
        return -1
    try:
        val = int(raw)
        return val if val >= -1 else -1
    except ValueError:
        logger.warning(
            "Invalid ADMZ_GEMINI_THINKING_BUDGET=%r; using dynamic (-1)", raw
        )
        return -1


def _manual_tool_loop_enabled() -> bool:
    """Whether to run tools through the in-ADMZ manual function-calling loop.

    Default ON. Set ADMZ_GEMINI_MANUAL_TOOL_LOOP=0 to fall back to the SDK's
    automatic function calling (AFC) — a kill-switch for the core-path change.
    Only affects tool-using turns; the no-tools path is unchanged either way.
    """
    return os.getenv("ADMZ_GEMINI_MANUAL_TOOL_LOOP", "true").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _get_max_tool_iterations() -> int:
    """Max non-streaming tool rounds in the manual loop (default 8)."""
    raw = os.getenv("ADMZ_GEMINI_MAX_TOOL_ITERATIONS")
    if raw is None:
        return 8
    try:
        return max(1, int(raw))
    except ValueError:
        logger.warning(
            "Invalid ADMZ_GEMINI_MAX_TOOL_ITERATIONS=%r; using 8", raw
        )
        return 8


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
    event_tool_result,
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
    if models is None:
        raise ChatbotTurnError(
            "google-genai client exposes no aio.models. Upgrade google-genai."
        )
    sys_inst = request_kwargs.get("system_instruction")

    # --- Manual function-calling loop (fixes the gemini-3.x empty-turn AFC bug).
    # When tools are in play we drive the function-calling loop ourselves instead
    # of relying on the SDK's automatic function calling, whose async-streaming
    # path bails before the continuation call on gemini-3.x (split function-call
    # args + mandatory thought_signature). See docs/chatbot-gemini-3x-afc.md.
    if mcp_session is not None and _manual_tool_loop_enabled():
        async for chunk in _run_manual_tool_loop(
            models,
            request_kwargs["model"],
            request_kwargs["contents"],
            sys_inst,
            mcp_session,
        ):
            yield chunk
        return

    # --- Legacy single streaming call: no-tools turns, or the AFC kill-switch.
    stream_fn = getattr(models, "generate_content_stream", None)
    if stream_fn is None:
        raise ChatbotTurnError(
            "google-genai client exposes no aio.models.generate_content_stream. "
            "Upgrade google-genai."
        )

    config: dict = {}
    if sys_inst:
        config["system_instruction"] = sys_inst
    if mcp_session is not None:
        config["tools"] = [mcp_session]
    # ADMZ_GEMINI_THINKING_BUDGET: -1 dynamic (default), 0 disables, >0 fixed.
    # Dynamic is required for reliable tool use and for the *-pro models.
    config["thinking_config"] = {"thinking_budget": _get_thinking_budget()}

    call_kwargs = {
        "model": request_kwargs["model"],
        "contents": request_kwargs["contents"],
    }
    if config:
        call_kwargs["config"] = _build_generate_config(config)

    result = stream_fn(**call_kwargs)
    async for chunk in _as_async_iter(result):
        yield chunk


# ---------------------------------------------------------------------------
# Manual function-calling loop (AFC replacement; all models)
# ---------------------------------------------------------------------------
#
# We drive the tool loop in ADMZ rather than via the SDK's automatic function
# calling. The documented manual convention (current Google docs) is:
#   * disable AFC; pass explicit FunctionDeclarations (NOT the raw MCP session,
#     which "relies on AFC" and is experimental);
#   * non-streaming generate_content per turn (streaming + manual function calls
#     is the fragile path — exactly the 3.x defect);
#   * append the model's ``candidates[0].content`` VERBATIM to history (that is
#     how thought_signatures round-trip on gemini-3, otherwise the API 400s),
#     then a function_response Content; loop until the model returns no call.
# Verified live on gemini-2.5-flash AND gemini-3.5-flash.


class _ToolCallChunk:
    """Synthetic chunk → TOOL_CALL event (the translator reads step_type+name).

    ``args`` (redacted) + ``call_id`` feed the UI's expand pane and let the
    frontend bind a later tool_result to the exact card (robust when the same
    tool name is called many times in one turn).
    """

    def __init__(self, name: str, args=None, call_id=None):
        self.step_type = "function_call"
        self.name = name
        self.args = args
        self.call_id = call_id


class _ToolResultChunk:
    """Synthetic chunk → TOOL_RESULT event (per-tool completion, real-time)."""

    def __init__(self, name, status, summary, call_id, result=None):
        self.step_type = "function_result"
        self.name = name
        self.status = status        # "ok" | "error" | "skipped"
        self.summary = summary      # short, inline (already redacted)
        self.call_id = call_id
        self.result = result        # full redacted result dict (expand pane)


class _TextChunk:
    """Synthetic chunk → TEXT event (the translator reads .text)."""

    def __init__(self, text: str):
        self.text = text


class _UsageMetadata:
    def __init__(self, input_tokens: int, output_tokens: int):
        self.prompt_token_count = input_tokens
        self.candidates_token_count = output_tokens


class _UsageChunk:
    """Synthetic terminal chunk carrying summed usage + interaction id → DONE."""

    def __init__(self, input_tokens: int, output_tokens: int, interaction_id):
        self.usage_metadata = _UsageMetadata(input_tokens, output_tokens)
        self.id = interaction_id


def _normalize_contents(contents: Any) -> list:
    """The loop appends Content/Part objects, so coerce to a mutable list."""
    if isinstance(contents, str):
        return [{"role": "user", "parts": [{"text": contents}]}]
    if isinstance(contents, list):
        return list(contents)
    return [contents]


async def _mcp_declarations(mcp_session: Any, types: Any) -> list:
    """Build explicit Gemini tool declarations from the MCP server's list_tools.

    Decouples the manual loop from the SDK's experimental MCP-session-as-tool
    auto-execution. The MCP inputSchema (JSON Schema) is passed through via
    ``parameters_json_schema`` — verified accepted by 2.5-flash and 3.5-flash.
    """
    listed = await mcp_session.list_tools()
    tools = getattr(listed, "tools", listed) or []
    decls = []
    for t in tools:
        schema = getattr(t, "inputSchema", None)
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        decls.append(
            types.FunctionDeclaration(
                name=t.name,
                description=getattr(t, "description", "") or "",
                parameters_json_schema=schema,
            )
        )
    return [types.Tool(function_declarations=decls)] if decls else []


def _extract_function_calls(resp: Any):
    """Return (list of function_call objects, raw model Content) from a response."""
    content = None
    try:
        content = resp.candidates[0].content
    except Exception:  # noqa: BLE001 - SDK shape drift / no candidates
        content = None
    calls = list(getattr(resp, "function_calls", None) or [])
    if not calls and content is not None:
        for part in (getattr(content, "parts", None) or []):
            fc = getattr(part, "function_call", None)
            if fc is not None:
                calls.append(fc)
    return calls, content


def _response_text(resp: Any) -> str:
    try:
        t = getattr(resp, "text", None)
        if t:
            return t
    except Exception:  # noqa: BLE001 - .text raises on non-text parts
        pass
    try:
        parts = resp.candidates[0].content.parts or []
        return "".join(getattr(p, "text", "") or "" for p in parts)
    except Exception:  # noqa: BLE001
        return ""


def _chunk_text(text: str):
    """Yield a long answer in modest whitespace-aligned slices (progressive UI)."""
    if not text:
        return
    i, n = 0, len(text)
    while i < n:
        j = min(i + 80, n)
        if j < n:
            k = text.find(" ", j)
            if k != -1 and k - j < 24:
                j = k
        yield text[i:j]
        i = j


def _make_function_response_part(types: Any, name: str, response: dict, call_id):
    """Build a function_response Part, tolerant of SDK-version signature drift."""
    fn = getattr(getattr(types, "Part", None), "from_function_response", None)
    if fn is not None:
        if call_id is not None:
            try:
                return fn(name=name, response=response, id=call_id)
            except TypeError:
                pass  # older SDK (e.g. 2.5.0) has no id kwarg
        try:
            return fn(name=name, response=response)
        except Exception:  # noqa: BLE001
            pass
    return {"function_response": {"name": name, "response": response}}


async def _call_mcp_tool(mcp_session: Any, name: str, args: Any) -> dict:
    """Execute an MCP tool and return its JSON result as a dict."""
    out = await mcp_session.call_tool(name, dict(args or {}))
    content = getattr(out, "content", out)
    try:
        first = content[0]
        text = getattr(first, "text", None)
        if text is not None:
            return json.loads(text)
    except Exception:  # noqa: BLE001 - non-JSON / empty result
        pass
    return {"result": str(content)[:2000]}


# --- display helpers for the tool-card UI (args/result panes + status) -------

_SENSITIVE_KEY_PARTS = ("password", "passwd", "secret", "token", "api_key", "apikey", "key")
_MAX_DISPLAY_STR = 300
_MAX_DISPLAY_LIST = 50


def _redact_for_display(obj: Any, depth: int = 0) -> Any:
    """Make a tool's args/result safe + compact to show in the chat UI.

    Masks values whose key looks like a credential, truncates long strings and
    lists, and depth-guards. Device/operation IDs pass through (they help the
    operator read the card). Never sends a raw secret to the browser.
    """
    if depth > 6:
        return "…"
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kl = str(k).lower()
            if any(p in kl for p in _SENSITIVE_KEY_PARTS):
                out[k] = "***"
            else:
                out[k] = _redact_for_display(v, depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        items = [_redact_for_display(v, depth + 1) for v in list(obj)[:_MAX_DISPLAY_LIST]]
        extra = len(obj) - _MAX_DISPLAY_LIST
        if extra > 0:
            items.append(f"… (+{extra} more)")
        return items
    if isinstance(obj, str) and len(obj) > _MAX_DISPLAY_STR:
        return obj[:_MAX_DISPLAY_STR] + f"… ({len(obj)} chars)"
    return obj


def _short(text: Any, limit: int = 120) -> str:
    s = str(text).replace("\n", " ").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _classify_tool_result(payload: Any):
    """Map a tool result dict → (status, short inline summary) for the card.

    status ∈ ok | error | skipped. A confirm-gated result (blocked) is
    'skipped' (awaiting approval), NOT an error.
    """
    if not isinstance(payload, dict):
        return "ok", _short(payload)
    if payload.get("blocked"):
        return "skipped", _short(payload.get("message") or "Awaiting approval")
    if payload.get("error") or payload.get("success") is False:
        return "error", _short(payload.get("error") or payload.get("message") or "failed")
    # normal — prefer a human-readable field, else a compact key=value line
    for key in ("message", "summary", "status"):
        if payload.get(key):
            return "ok", _short(payload[key])
    scalars = [
        f"{k}={_short(v, 40)}"
        for k, v in payload.items()
        if isinstance(v, (str, int, float, bool))
    ]
    if scalars:
        return "ok", _short(", ".join(scalars[:5]))
    return "ok", "done"


async def _run_manual_tool_loop(models, model, contents, sys_inst, mcp_session):
    """Drive the function-calling loop in ADMZ; yield translator-ready chunks."""
    from google.genai import types  # type: ignore[import-not-found]

    gen = getattr(models, "generate_content", None)
    if gen is None:
        raise ChatbotTurnError(
            "google-genai client exposes no aio.models.generate_content. "
            "Upgrade google-genai."
        )

    config: dict = {}
    if sys_inst:
        config["system_instruction"] = sys_inst
    config["tools"] = await _mcp_declarations(mcp_session, types)
    config["automatic_function_calling"] = {"disable": True}
    config["thinking_config"] = {"thinking_budget": _get_thinking_budget()}
    config_obj = _build_generate_config(config)

    convo = _normalize_contents(contents)
    total_in = total_out = 0
    last_interaction_id = None
    max_iter = _get_max_tool_iterations()
    next_call_id = 0  # unique per executed tool, across iterations

    hit_cap = True
    for _ in range(max_iter):
        resp = await gen(model=model, contents=convo, config=config_obj)
        ti, to = _extract_usage_from_chunk(resp)
        total_in += ti or 0
        total_out += to or 0
        last_interaction_id = (
            getattr(resp, "id", None)
            or getattr(resp, "response_id", None)
            or last_interaction_id
        )

        calls, content = _extract_function_calls(resp)
        if not calls:
            for piece in _chunk_text(_response_text(resp)):
                yield _TextChunk(piece)
            hit_cap = False
            break

        # Append the model's turn VERBATIM (carries gemini-3 thought_signature),
        # then one function_response per call. Parallel calls: execute all.
        if content is not None:
            convo.append(content)
        for fc in calls:
            call_id = str(next_call_id)
            next_call_id += 1
            name = getattr(fc, "name", "") or "tool"
            raw_args = getattr(fc, "args", {}) or {}
            yield _ToolCallChunk(
                name, args=_redact_for_display(dict(raw_args)), call_id=call_id
            )
            payload = await _call_mcp_tool(mcp_session, name, raw_args)
            safe_payload = _redact_for_display(payload)
            status, summary = _classify_tool_result(safe_payload)
            yield _ToolResultChunk(
                name, status, summary, call_id, result=safe_payload
            )
            part = _make_function_response_part(
                types, name, payload, getattr(fc, "id", None)
            )
            convo.append(types.Content(role="user", parts=[part]))

    if hit_cap:
        logger.warning("manual tool loop hit max iterations (%d)", max_iter)
        yield _TextChunk(
            f"(Stopped after {max_iter} tool calls without a final answer — "
            "please refine your request.)"
        )

    # Final yield: summed usage so stream_turn's "keep latest" reports the total.
    yield _UsageChunk(total_in, total_out, last_interaction_id)


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
        return event_tool_call(
            name=name,
            args_summary=f"{name}(...)",
            call_id=getattr(chunk, "call_id", None),
            args=getattr(chunk, "args", None),
        )
    if step_type == "function_result":
        name = getattr(chunk, "name", None) or "tool"
        return event_tool_result(
            name=name,
            status=getattr(chunk, "status", "ok"),
            summary=getattr(chunk, "summary", "") or "",
            call_id=getattr(chunk, "call_id", None),
            result=getattr(chunk, "result", None),
        )
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
