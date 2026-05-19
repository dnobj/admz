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
