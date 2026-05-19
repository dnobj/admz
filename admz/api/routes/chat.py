"""Chatbot routes — Phase 5A scaffolding + Phase 5B streaming.

Surfaces:

  - ``GET  /chat``                  — the chat page (Jinja2)
  - ``POST /chat``                  — non-streaming single turn (fallback,
                                       still used when JS is disabled)
  - ``POST /chat/stream``           — Server-Sent Events streaming turn
  - ``POST /chat/clear``            — clear the principal's session
  - ``GET  /settings/chat``         — admin config page
  - ``POST /settings/chat``         — save API key / default model

The streaming endpoint emits :class:`~admz.chatbot.events.ChatEvent`
values over SSE. The browser-side renderer in ``chat.html``
consumes them via ``fetch()`` + a ``ReadableStream`` reader.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from admz.auth import Principal, get_current_principal
from admz.chatbot import SELECTABLE_MODELS, get_chatbot_config
import admz.chatbot.sessions as _sessions_module
from admz.chatbot.client import (
    ChatbotDependencyMissing,
    ChatbotNotConfigured,
    ChatbotTurnError,
    run_turn,
    stream_turn,
)
from admz.chatbot.config import (
    clear_api_key,
    mask_api_key,
    set_api_key,
    set_default_model,
)
from admz.chatbot.events import (
    ChatEventType,
    event_error,
)
from admz.chatbot.system_prompt import build_system_prompt
from admz.chatbot.usage import (
    check_budget,
    estimate_cost_usd,
    get_daily_budget,
    set_daily_budget,
)
import admz.chatbot.usage as _usage_module
from admz.audit import record_event


def _token_usage():
    """Lookup the live token_usage singleton at call time (tests swap it)."""
    return _usage_module.token_usage


def _sessions():
    """Look up the live chat_sessions singleton at call time (tests swap it)."""
    return _sessions_module.chat_sessions

logger = logging.getLogger(__name__)


router = APIRouter()


# Template configuration mirrors admz.api.routes.web.
_template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_template_dir))


# ---------------------------------------------------------------------------
# /chat — the chat UI
# ---------------------------------------------------------------------------


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    """Render the chat page.

    If no API key is configured, render a friendly "not
    configured" state with a link to /settings/chat.
    """
    config = get_chatbot_config()
    last_model = _sessions().last_model(principal.name) or config.default_model

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "title": "Chat",
            "principal": principal,
            "configured": config.configured,
            "selectable_models": config.selectable_models,
            "default_model": config.default_model,
            "last_model": last_model,
            # No persisted transcript: Phase 5A shows only the
            # current turn's response. Phase 5B may add an
            # ephemeral page-local log.
            "answer": None,
            "user_message": None,
            "error": None,
            "usage": None,
        },
    )


@router.post("/chat", response_class=HTMLResponse)
async def chat_submit(
    request: Request,
    message: str = Form(...),
    model: str = Form(""),
    principal: Principal = Depends(get_current_principal),
):
    """Run one chat turn and render the response."""
    config = get_chatbot_config()

    # Per-user model selection: trust the form value if it's in
    # the selectable list; otherwise use the org default. Keeps
    # the surface narrow — a bad form post can't request an
    # arbitrary model name.
    chosen_model = (
        model if model in SELECTABLE_MODELS else config.default_model
    )

    if not config.configured:
        return templates.TemplateResponse(
            "chat.html",
            {
                "request": request,
                "title": "Chat",
                "principal": principal,
                "configured": False,
                "selectable_models": config.selectable_models,
                "default_model": config.default_model,
                "last_model": chosen_model,
                "answer": None,
                "user_message": message,
                "error": (
                    "Chatbot is not configured. Ask an administrator "
                    "to set the Gemini API key at /settings/chat."
                ),
                "usage": None,
            },
            status_code=503,
        )

    prev_id = _sessions().get_interaction_id(principal.name)
    system_prompt = build_system_prompt(
        principal_name=principal.name,
        display_name=principal.display_name,
        groups=principal.groups,
    )

    logger.debug(
        "[chat] user=%s model=%s prev_id=%s message=%r",
        principal.name,
        chosen_model,
        prev_id,
        message,
    )

    error_text: Optional[str] = None
    answer_text: Optional[str] = None
    usage = None

    try:
        result = await run_turn(
            user_message=message,
            api_key=config.api_key,
            model=chosen_model,
            system_prompt=system_prompt,
            previous_interaction_id=prev_id,
        )
        answer_text = result.text
        usage = {
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
        if result.interaction_id:
            _sessions().set_interaction_id(
                principal.name, result.interaction_id, chosen_model
            )
    except ChatbotDependencyMissing as exc:
        error_text = (
            "The google-genai package is not installed on the server. "
            f"({exc})"
        )
    except ChatbotNotConfigured as exc:
        error_text = str(exc)
    except ChatbotTurnError as exc:
        error_text = f"Gemini returned an error: {exc}"
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("Unexpected chat turn failure: %s", exc)
        error_text = f"Unexpected error: {exc}"

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "[chat] user=%s model=%s tokens=%s/%s ok=%s response=%r%s",
            principal.name,
            chosen_model,
            (usage or {}).get("input_tokens") if usage else None,
            (usage or {}).get("output_tokens") if usage else None,
            error_text is None,
            answer_text or "",
            f" error={error_text!r}" if error_text else "",
        )

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "title": "Chat",
            "principal": principal,
            "configured": True,
            "selectable_models": config.selectable_models,
            "default_model": config.default_model,
            "last_model": chosen_model,
            "answer": answer_text,
            "user_message": message,
            "error": error_text,
            "usage": usage,
        },
    )


@router.post("/chat/clear")
async def chat_clear(
    principal: Principal = Depends(get_current_principal),
):
    """Reset the principal's Gemini conversation."""
    _sessions().clear(principal.name)
    return RedirectResponse(url="/chat", status_code=303)


# ---------------------------------------------------------------------------
# /chat/stream — Server-Sent Events
# ---------------------------------------------------------------------------


@router.post("/chat/stream")
async def chat_stream(
    message: str = Form(...),
    model: str = Form(""),
    principal: Principal = Depends(get_current_principal),
):
    """Stream a chat turn as Server-Sent Events.

    Emits :class:`~admz.chatbot.events.ChatEvent` values in the
    SSE wire format. The browser-side renderer reads chunks via
    ``fetch()`` + ``ReadableStream.getReader()`` and dispatches on
    the event type.

    Headers worth noting:
      - ``X-Accel-Buffering: no`` — disables nginx/uwsgi
        buffering so events flush as they're written.
      - ``Cache-Control: no-cache`` — guards against intermediary
        caches storing the event stream.
    """
    config = get_chatbot_config()
    chosen_model = (
        model if model in SELECTABLE_MODELS else config.default_model
    )

    async def event_source() -> AsyncIterator[str]:
        if not config.configured:
            yield event_error(
                "Gemini API key is not configured. Visit /settings/chat."
            ).to_sse()
            return

        # Phase 5D: budget gate. Checked here (not inside stream_turn)
        # so the route can audit-log the rejection with the principal.
        budget = check_budget(principal.name)
        if not budget.allowed:
            record_event(
                principal,
                action="chat_budget_exceeded",
                resource=f"model:{chosen_model}",
                details={
                    "via_chatbot": True,
                    "used_today": budget.used_today,
                    "budget": budget.budget,
                },
                success=False,
                error_message=budget.reason,
            )
            yield event_error(budget.reason).to_sse()
            return

        prev_id = _sessions().get_interaction_id(principal.name)
        system_prompt = build_system_prompt(
            principal_name=principal.name,
            display_name=principal.display_name,
            groups=principal.groups,
        )

        # DEBUG logging: capture the user's message at turn start. The
        # full conversation only ends up in logs when ADMZ_LOG_LEVEL=DEBUG.
        # See the requirements doc (web-chatbot.md) for the privacy note.
        logger.debug(
            "[chat] user=%s model=%s prev_id=%s message=%r",
            principal.name,
            chosen_model,
            prev_id,
            message,
        )

        captured_interaction_id: Optional[str] = None
        captured_input_tokens: int = 0
        captured_output_tokens: int = 0
        turn_succeeded = True
        turn_error: Optional[str] = None
        # DEBUG-only buffer of streamed text so we can log the full
        # assistant response at end-of-turn. Kept local to the route;
        # never persisted.
        assistant_text_parts: list = []
        tool_call_log: list = []

        try:
            async for chat_event in stream_turn(
                user_message=message,
                api_key=config.api_key,
                model=chosen_model,
                system_prompt=system_prompt,
                previous_interaction_id=prev_id,
                principal=principal.name,
            ):
                # Capture terminal metadata + augment the done event
                # with cost estimate before forwarding.
                if chat_event.type == ChatEventType.DONE:
                    captured_interaction_id = chat_event.payload.get(
                        "interaction_id"
                    )
                    captured_input_tokens = int(
                        chat_event.payload.get("input_tokens") or 0
                    )
                    captured_output_tokens = int(
                        chat_event.payload.get("output_tokens") or 0
                    )
                    cost = estimate_cost_usd(
                        chosen_model,
                        captured_input_tokens,
                        captured_output_tokens,
                    )
                    chat_event.payload["cost_usd"] = cost
                    chat_event.payload["model"] = chosen_model
                elif chat_event.type == ChatEventType.ERROR:
                    turn_succeeded = False
                    turn_error = chat_event.payload.get("message", "")
                elif chat_event.type == ChatEventType.TEXT:
                    # Accumulate for end-of-turn DEBUG log.
                    chunk = chat_event.payload.get("chunk", "")
                    if chunk:
                        assistant_text_parts.append(chunk)
                elif chat_event.type == ChatEventType.TOOL_CALL:
                    tool_call_log.append(
                        chat_event.payload.get("name", "?")
                    )
                yield chat_event.to_sse()
        except ChatbotDependencyMissing as exc:
            turn_succeeded = False
            turn_error = str(exc)
            yield event_error(str(exc)).to_sse()
        except ChatbotNotConfigured as exc:
            turn_succeeded = False
            turn_error = str(exc)
            yield event_error(str(exc)).to_sse()
        except ChatbotTurnError as exc:
            turn_succeeded = False
            turn_error = str(exc)
            yield event_error(f"Gemini stream error: {exc}").to_sse()
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("Unexpected chat stream failure: %s", exc)
            turn_succeeded = False
            turn_error = str(exc)
            yield event_error(f"Unexpected error: {exc}").to_sse()
            return

        if captured_interaction_id:
            _sessions().set_interaction_id(
                principal.name, captured_interaction_id, chosen_model
            )

        # DEBUG: emit the assembled assistant response + any tool calls.
        # Skipped silently when logger isn't at DEBUG, so production
        # operators don't pay for the string construction.
        if logger.isEnabledFor(logging.DEBUG):
            assistant_text = "".join(assistant_text_parts)
            logger.debug(
                "[chat] user=%s model=%s tools=%s tokens=%d/%d cost=$%s "
                "ok=%s response=%r%s",
                principal.name,
                chosen_model,
                tool_call_log or "(none)",
                captured_input_tokens,
                captured_output_tokens,
                f"{estimate_cost_usd(chosen_model, captured_input_tokens, captured_output_tokens) or 0:.6f}",
                turn_succeeded,
                assistant_text,
                f" error={turn_error!r}" if turn_error else "",
            )

        # Phase 5D: record usage + emit an audit entry for this turn.
        # Best-effort — never let a usage/audit failure break the
        # already-streamed response.
        try:
            cost = estimate_cost_usd(
                chosen_model, captured_input_tokens, captured_output_tokens
            )
            if captured_input_tokens or captured_output_tokens:
                _token_usage().record_turn(
                    principal=principal.name,
                    model=chosen_model,
                    input_tokens=captured_input_tokens,
                    output_tokens=captured_output_tokens,
                    cost_usd=cost,
                )
            record_event(
                principal,
                action="chat_turn",
                resource=f"model:{chosen_model}",
                details={
                    "via_chatbot": True,
                    "model": chosen_model,
                    "input_tokens": captured_input_tokens,
                    "output_tokens": captured_output_tokens,
                    "cost_usd": cost,
                    "had_previous_session": prev_id is not None,
                },
                success=turn_succeeded,
                error_message=turn_error or "",
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "Failed to record chat turn usage/audit: %s", exc
            )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# /settings/chat — admin configuration
# ---------------------------------------------------------------------------


@router.get("/settings/chat", response_class=HTMLResponse)
async def chat_settings_page(
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    """Render the chatbot admin page (API key + default model + budget)."""
    config = get_chatbot_config()
    return templates.TemplateResponse(
        "chat_settings.html",
        {
            "request": request,
            "title": "Chat Settings",
            "principal": principal,
            "api_key_state": mask_api_key(config.api_key),
            "configured": config.configured,
            "selectable_models": config.selectable_models,
            "default_model": config.default_model,
            "daily_token_budget": get_daily_budget(),
            "today_usage": _token_usage().today_summary(principal.name),
            "success": None,
            "error": None,
        },
    )


@router.post("/settings/chat", response_class=HTMLResponse)
async def chat_settings_save(
    request: Request,
    action: str = Form(...),
    api_key: Optional[str] = Form(None),
    default_model: Optional[str] = Form(None),
    daily_token_budget: Optional[str] = Form(None),
    principal: Principal = Depends(get_current_principal),
):
    """Persist API key / default-model / daily-budget changes."""
    success: Optional[str] = None
    error: Optional[str] = None

    if action == "set_api_key":
        if not api_key or not api_key.strip():
            error = "API key cannot be empty. Use 'Clear key' to remove."
        else:
            set_api_key(api_key)
            success = "Gemini API key saved."
    elif action == "clear_api_key":
        clear_api_key()
        success = "Gemini API key cleared."
    elif action == "set_default_model":
        if not default_model or default_model not in SELECTABLE_MODELS:
            error = f"Invalid model. Choose one of: {', '.join(SELECTABLE_MODELS)}"
        else:
            set_default_model(default_model)
            success = f"Default model set to {default_model}."
    elif action == "set_daily_token_budget":
        try:
            budget = int((daily_token_budget or "0").strip())
            if budget < 0:
                raise ValueError("must be >= 0")
            set_daily_budget(budget)
            success = (
                "Daily token budget cleared (unlimited)."
                if budget == 0
                else f"Daily token budget set to {budget:,} tokens per principal."
            )
        except (ValueError, TypeError) as exc:
            error = (
                f"Invalid budget: {exc}. Use a non-negative integer; "
                "0 disables enforcement."
            )
    else:
        error = f"Unknown action: {action!r}"

    config = get_chatbot_config()
    return templates.TemplateResponse(
        "chat_settings.html",
        {
            "request": request,
            "title": "Chat Settings",
            "principal": principal,
            "api_key_state": mask_api_key(config.api_key),
            "configured": config.configured,
            "selectable_models": config.selectable_models,
            "default_model": config.default_model,
            "daily_token_budget": get_daily_budget(),
            "today_usage": _token_usage().today_summary(principal.name),
            "success": success,
            "error": error,
        },
    )
