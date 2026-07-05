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

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import AsyncIterator, Optional

from dataclasses import dataclass, field

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from admz.auth import Principal, get_current_principal
from admz.chatbot import SELECTABLE_MODELS, get_chatbot_config
import admz.chatbot.sessions as _sessions_module
from admz.chatbot.client import (
    ChatbotDependencyMissing,
    ChatbotNotConfigured,
    ChatbotTurnError,
    generate_conversation_title,
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
from admz.chatbot.context import (
    build_common_ops_reference,
    build_device_roster,
    build_module_prompt_sections,
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


def _chat_event_timeout_seconds() -> float:
    """How long to wait between SSE events before surfacing a stall as
    an error to the user. Belt-and-braces against the MCP-pool
    cleanup bug (audit HIGH-12): when a pooled subprocess dies in a
    way the self-heal can't fully recover from, the chat stream can
    silently stop emitting events and the browser shows an infinite
    spinner. With this timeout, the stall becomes a clear error the
    user can act on (retry, reload, switch model).

    Default: 120s. Override via ADMZ_CHAT_EVENT_TIMEOUT_SECONDS.
    Set to 0 to disable (legacy behavior — chat hangs forever).
    """
    raw = os.getenv("ADMZ_CHAT_EVENT_TIMEOUT_SECONDS", "")
    if not raw:
        return 120.0
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "ADMZ_CHAT_EVENT_TIMEOUT_SECONDS=%r is not a number; "
            "using 120s default", raw,
        )
        return 120.0
    return value


async def _with_per_event_timeout(aiter, timeout_seconds: float):
    """Wrap an async iterator so each ``__anext__`` is bounded.

    On timeout, yields a synthetic ``error`` ChatEvent and stops. The
    underlying iterator is abandoned (its remaining work is dropped) —
    this is the right behavior because by the time we time out the
    SSE consumer has already given up waiting too.

    When ``timeout_seconds <= 0`` the wrapper is bypassed entirely
    (legacy behavior).
    """
    if timeout_seconds <= 0:
        async for ev in aiter:
            yield ev
        return

    iterator = aiter.__aiter__()
    while True:
        try:
            ev = await asyncio.wait_for(
                iterator.__anext__(),
                timeout=timeout_seconds,
            )
        except StopAsyncIteration:
            return
        except asyncio.TimeoutError:
            logger.warning(
                "chat stream stalled for %.0fs without an event — "
                "yielding error and aborting turn. Likely culprit: "
                "MCP pooled subprocess died and self-heal couldn't "
                "recover (audit HIGH-12).",
                timeout_seconds,
            )
            yield event_error(
                f"Chat stream stalled for {int(timeout_seconds)}s — the "
                "device-tool subprocess may have crashed. Please retry "
                "(the underlying snapshot/command may have completed "
                "successfully on the device side)."
            )
            return
        yield ev


router = APIRouter()


# Template configuration mirrors admz.api.routes.web.
_template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_template_dir))
from admz.api.templating import configure as _configure_templates  # noqa: E402
_configure_templates(templates)


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
            # embed=1 renders the dockable Console without the app chrome.
            "embed": request.query_params.get("embed") == "1",
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
        device_roster=build_device_roster(),
        common_ops=build_common_ops_reference(),
        module_sections=build_module_prompt_sections(),
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
    """Start a *new* conversation.

    The previous conversation is preserved (it stays in the history
    list — nothing is deleted); only the session pointer is reset and a
    fresh, empty active conversation is created. The console's "New chat"
    button posts here for the no-JS path; the drawer uses the JSON route.
    """
    _sessions().clear(principal.name)  # drop interaction + active pointer
    _sessions().create_conversation(principal.name)  # fresh active conversation
    return RedirectResponse(url="/chat", status_code=303)


# ---------------------------------------------------------------------------
# Conversation history — JSON surface for the console's left drawer.
# Every route is scoped to the signed-in principal; touching another
# principal's conversation returns 404 (it simply isn't visible).
# ---------------------------------------------------------------------------


class _ConversationCreate(BaseModel):
    title: str = ""


class _ConversationRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


@router.get("/api/chat/conversations", tags=["chat"])
async def api_list_conversations(
    principal: Principal = Depends(get_current_principal),
):
    """List the principal's conversations, newest-first."""
    return {
        "conversations": _sessions().list_conversations(principal.name),
        "active": _sessions().get_active_conversation(principal.name),
    }


@router.post("/api/chat/conversations", tags=["chat"])
async def api_create_conversation(
    body: _ConversationCreate = Body(default_factory=_ConversationCreate),
    principal: Principal = Depends(get_current_principal),
):
    """Start a new conversation and make it active (the drawer's '+ New chat')."""
    title = (body.title or "").strip()[:200]
    cid = _sessions().create_conversation(
        principal.name,
        title=title,
        title_source="manual" if title else "pending",
    )
    record_event(
        principal,
        action="chat.conversation_create",
        resource=f"conversation:{cid}",
    )
    return {"id": cid}


@router.get("/api/chat/conversations/{conversation_id}", tags=["chat"])
async def api_get_conversation(
    conversation_id: str,
    principal: Principal = Depends(get_current_principal),
):
    """Full transcript of one conversation (rendered when reopened)."""
    meta = _sessions().get_conversation(principal.name, conversation_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": meta["id"],
        "title": meta["title"],
        "title_source": meta["title_source"],
        "messages": _sessions().get_messages(principal.name, conversation_id),
    }


@router.post("/api/chat/conversations/{conversation_id}/activate", tags=["chat"])
async def api_activate_conversation(
    conversation_id: str,
    principal: Principal = Depends(get_current_principal),
):
    """Switch the active conversation — subsequent turns continue this one."""
    if not _sessions().set_active_conversation(principal.name, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True, "active": conversation_id}


@router.patch("/api/chat/conversations/{conversation_id}", tags=["chat"])
async def api_rename_conversation(
    conversation_id: str,
    body: _ConversationRename,
    principal: Principal = Depends(get_current_principal),
):
    """Rename a conversation (pins the title — no longer auto-retitled)."""
    title = body.title.strip()[:200]
    if not title:
        raise HTTPException(status_code=400, detail="Title must not be empty")
    if not _sessions().rename_conversation(principal.name, conversation_id, title):
        raise HTTPException(status_code=404, detail="Conversation not found")
    record_event(
        principal,
        action="chat.conversation_rename",
        resource=f"conversation:{conversation_id}",
    )
    return {"ok": True, "title": title}


@router.delete("/api/chat/conversations/{conversation_id}", tags=["chat"])
async def api_delete_conversation(
    conversation_id: str,
    principal: Principal = Depends(get_current_principal),
):
    """Delete a conversation and all of its messages."""
    if not _sessions().delete_conversation(principal.name, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    record_event(
        principal,
        action="chat.conversation_delete",
        resource=f"conversation:{conversation_id}",
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Shared turn-runner
# ---------------------------------------------------------------------------
#
# Both /chat/stream (SSE) and /api/chat (JSON) need the same machinery:
# budget check → invoke stream_turn → forward/collect events → record
# usage + audit. The SSE route forwards each event to the wire as it
# arrives; the JSON route accumulates events and returns them at end of
# turn. Factor that machinery into one async generator so neither
# duplicates the policy.


# Confirm/capture session URLs inside tool results (mirrors the regexes the
# console widgets use in chat.js — the authoritative signal that a session
# was created this turn).
_CONFIRM_URL_RE = re.compile(r"/confirm/([A-Za-z0-9_-]{20,})")
_CAPTURE_URL_RE = re.compile(r"/capture/(?!fleet/)([A-Za-z0-9_-]{20,})")
# A rule recipient-secret capture URL — /capture/rule/{token} where {token} is
# the rule's CONFIRM token. Recorded as "confirm" so the eventual approval note
# (keyed by the same token) fires. Sits before _CAPTURE_URL_RE would ever look.
_RULE_CAPTURE_URL_RE = re.compile(r"/capture/rule/([A-Za-z0-9_-]{20,})")


def _scan_action_tokens(result: object, tool_name: str) -> list:
    """``(kind, token, tool_name)`` for every confirm/capture session URL in
    a tool result. Never raises — a scan failure must not break a turn."""
    try:
        blob = json.dumps(result, default=str)
    except Exception:  # noqa: BLE001
        return []
    found = []
    for kind, rx in (
        ("confirm", _CONFIRM_URL_RE),
        ("confirm", _RULE_CAPTURE_URL_RE),
        ("capture", _CAPTURE_URL_RE),
    ):
        for m in rx.finditer(blob):
            entry = (kind, m.group(1), tool_name)
            if entry not in found:
                found.append(entry)
    return found


@dataclass
class _TurnSummary:
    """Aggregated result of one chat turn — what /api/chat returns."""

    success: bool = True
    response: str = ""
    error: Optional[str] = None
    model: str = ""
    interaction_id: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Optional[float] = None
    tool_calls: list = field(default_factory=list)
    # (kind, token, tool_name) for confirm/capture sessions this turn's
    # tools created — linked to the conversation after the turn so their
    # out-of-band resolution can be noted back into it.
    action_tokens: list = field(default_factory=list)
    # Set when budget gate rejected the turn before the SDK ran.
    rejected_by_budget: bool = False


async def _run_chat_turn(
    *,
    principal: Principal,
    message: str,
    model_request: str,
    config,
    use_tools: bool = True,
):
    """Async generator: yields (event, summary) tuples per chat event.

    The generator does the policy work — budget gate, stream_turn
    invocation, exception wrapping, usage/audit recording. Callers
    consume the events to forward downstream (SSE) or accumulate them
    (JSON). A final ``(None, summary)`` tuple signals end-of-turn with
    the populated summary.
    """
    summary = _TurnSummary()
    chosen_model = (
        model_request if model_request in SELECTABLE_MODELS
        else config.default_model
    )
    summary.model = chosen_model

    if not config.configured:
        summary.success = False
        summary.error = "Gemini API key is not configured. Visit /settings/chat."
        yield (event_error(summary.error), None)
        yield (None, summary)
        return

    budget = check_budget(principal.name)
    if not budget.allowed:
        summary.success = False
        summary.error = budget.reason
        summary.rejected_by_budget = True
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
        yield (event_error(budget.reason), None)
        yield (None, summary)
        return

    prev_id = _sessions().get_interaction_id(principal.name)
    history = _sessions().get_history(principal.name)
    system_prompt = build_system_prompt(
        principal_name=principal.name,
        display_name=principal.display_name,
        groups=principal.groups,
        device_roster=build_device_roster(),
        common_ops=build_common_ops_reference(),
        module_sections=build_module_prompt_sections(),
    )

    logger.debug(
        "[chat] user=%s model=%s prev_id=%s history_turns=%d message=%r",
        principal.name,
        chosen_model,
        prev_id,
        len(history) // 2,  # 2 rows per turn
        message,
    )

    text_parts: list = []
    # Wrap the stream with a per-event timeout. If the MCP subprocess
    # dies in a way self-heal can't recover from, the underlying
    # iterator will stop emitting events; this surfaces it as an
    # error event after `ADMZ_CHAT_EVENT_TIMEOUT_SECONDS` (default
    # 120s) instead of hanging forever.
    raw_stream = stream_turn(
        user_message=message,
        api_key=config.api_key,
        model=chosen_model,
        system_prompt=system_prompt,
        previous_interaction_id=prev_id,
        history=history,
        # CR-4: pass the full Principal so its name, source, and
        # groups can be forwarded to the MCP subprocess via env
        # vars and surface in every audit-log row the subprocess
        # writes. The pool keys on principal.name internally.
        principal=principal,
        use_tools=use_tools,
    )
    try:
        async for chat_event in _with_per_event_timeout(
            raw_stream, _chat_event_timeout_seconds(),
        ):
            if chat_event.type == ChatEventType.DONE:
                summary.interaction_id = chat_event.payload.get("interaction_id")
                summary.input_tokens = int(
                    chat_event.payload.get("input_tokens") or 0
                )
                summary.output_tokens = int(
                    chat_event.payload.get("output_tokens") or 0
                )
                summary.cost_usd = estimate_cost_usd(
                    chosen_model,
                    summary.input_tokens,
                    summary.output_tokens,
                )
                # Augment the event so SSE consumers see model + cost.
                chat_event.payload["cost_usd"] = summary.cost_usd
                chat_event.payload["model"] = chosen_model
            elif chat_event.type == ChatEventType.ERROR:
                summary.success = False
                summary.error = chat_event.payload.get("message", "")
            elif chat_event.type == ChatEventType.TEXT:
                chunk = chat_event.payload.get("chunk", "")
                if chunk:
                    text_parts.append(chunk)
            elif chat_event.type == ChatEventType.TOOL_CALL:
                summary.tool_calls.append(chat_event.payload.get("name", "?"))
            elif chat_event.type == ChatEventType.TOOL_RESULT:
                # Confirm/capture sessions announce themselves via their
                # URLs in the tool result (token-named keys are masked by
                # redaction; the URL strings survive — same signal the
                # console widgets render from).
                summary.action_tokens.extend(
                    _scan_action_tokens(
                        chat_event.payload.get("result"),
                        chat_event.payload.get("name", "?"),
                    )
                )
            yield (chat_event, None)
    except ChatbotDependencyMissing as exc:
        summary.success = False
        summary.error = str(exc)
        yield (event_error(str(exc)), None)
    except ChatbotNotConfigured as exc:
        summary.success = False
        summary.error = str(exc)
        yield (event_error(str(exc)), None)
    except ChatbotTurnError as exc:
        summary.success = False
        summary.error = str(exc)
        yield (event_error(f"Gemini stream error: {exc}"), None)
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("Unexpected chat turn failure: %s", exc)
        summary.success = False
        summary.error = str(exc)
        yield (event_error(f"Unexpected error: {exc}"), None)

    summary.response = "".join(text_parts)

    # Bug 5 backstop: detect Gemini's "I called a tool but didn't
    # produce visible text" failure modes. We split into two cases
    # because they map to different recommended actions:
    #
    # Case A — TRUE empty turn (output_tokens == 0): thinking-only
    # completion or content-filter near-miss. Rephrasing usually
    # helps.
    #
    # Case B — output_tokens > 0 but no text reached us. We've
    # observed this on gemini-3.5-flash with MCP tools enabled:
    # AFC fires the tool, MCP returns the result, but the SDK
    # doesn't make the AFC continuation call to ask Gemini for
    # the final text. Net: the user sees nothing. Recommend
    # switching to gemini-2.5-flash (which doesn't have the
    # issue) or retrying.
    if (
        summary.success
        and not summary.response
        and not summary.error
    ):
        if summary.output_tokens == 0:
            # Case A — truly empty completion (thinking-only / safety filter).
            summary.success = False
            summary.error = (
                f"The model ({chosen_model}) returned no text. This sometimes "
                "happens on ambiguous prompts, when the model's safety filters "
                "are triggered, or when thinking-mode consumed the response "
                "budget. Try rephrasing the question — being more specific "
                "often helps."
            )
        else:
            # Case B — output tokens > 0 but no visible text. The gemini-3.x AFC
            # continuation bug that used to cause this is now handled by the
            # in-ADMZ manual function-calling loop (see chatbot/client.py), so
            # this is just a neutral backstop for other causes (e.g. a mid-stream
            # content-filter or a malformed final turn).
            summary.success = False
            summary.error = (
                f"The model ({chosen_model}) produced {summary.output_tokens} "
                "output tokens but no visible text. Please retry or rephrase "
                "the request."
            )
        logger.warning(
            "[chat] empty response on %s (tokens=%d) — surfacing as friendly error",
            chosen_model,
            summary.output_tokens,
        )

    if summary.interaction_id:
        _sessions().set_interaction_id(
            principal.name, summary.interaction_id, chosen_model
        )

    # Append this turn to conversation history so the next turn sees
    # it. Only persist successful turns with non-empty responses —
    # replaying budget rejections / SDK errors would just confuse
    # the LLM next time. Best-effort: a write failure here must not
    # break the already-streamed response.
    if summary.success and summary.response:
        try:
            _sessions().append_turn(
                principal.name, message, summary.response
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("Failed to append chat history: %s", exc)

        # One-time LLM title: on the conversation's first turn, upgrade the
        # provisional snippet title to a terse generated one. Best-effort —
        # a failure leaves the snippet title and never affects the response.
        try:
            conv_id = _sessions().get_active_conversation(principal.name)
            meta = (
                _sessions().get_conversation(principal.name, conv_id)
                if conv_id else None
            )
            if (
                meta
                and meta["message_count"] == 2  # exactly one turn so far
                and meta["title_source"] in ("pending", "snippet")
            ):
                title = await generate_conversation_title(
                    api_key=config.api_key,
                    model=chosen_model,
                    user_message=message,
                    assistant_message=summary.response,
                )
                if title:
                    _sessions().set_title(principal.name, conv_id, title, "llm")
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("conversation title step skipped: %s", exc)

    # Link any confirm/capture sessions this turn created to the
    # conversation, so their out-of-band resolution (card approval,
    # credential form) is noted back where the model sees it next turn.
    # Best-effort: linkage failure must never break an answered turn.
    if summary.action_tokens:
        try:
            conv_id = _sessions().get_active_conversation(principal.name)
            if conv_id:
                for kind, token, tool_name in summary.action_tokens:
                    _sessions().link_action(
                        token, principal.name, conv_id, kind, label=tool_name
                    )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("Failed to link action tokens: %s", exc)

    # Record usage + audit (best-effort).
    try:
        if summary.input_tokens or summary.output_tokens:
            _token_usage().record_turn(
                principal=principal.name,
                model=chosen_model,
                input_tokens=summary.input_tokens,
                output_tokens=summary.output_tokens,
                cost_usd=summary.cost_usd,
            )
        record_event(
            principal,
            action="chat_turn",
            resource=f"model:{chosen_model}",
            details={
                "via_chatbot": True,
                "model": chosen_model,
                "input_tokens": summary.input_tokens,
                "output_tokens": summary.output_tokens,
                "cost_usd": summary.cost_usd,
                "had_previous_session": prev_id is not None,
                "tool_calls": summary.tool_calls,
            },
            success=summary.success,
            error_message=summary.error or "",
        )
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Failed to record chat turn usage/audit: %s", exc)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "[chat] user=%s model=%s tools=%s tokens=%d/%d cost=$%s "
            "ok=%s response=%r%s",
            principal.name,
            chosen_model,
            summary.tool_calls or "(none)",
            summary.input_tokens,
            summary.output_tokens,
            f"{summary.cost_usd or 0:.6f}",
            summary.success,
            summary.response,
            f" error={summary.error!r}" if summary.error else "",
        )

    yield (None, summary)


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

    async def event_source() -> AsyncIterator[str]:
        async for chat_event, _summary in _run_chat_turn(
            principal=principal,
            message=message,
            model_request=model,
            config=config,
        ):
            if chat_event is None:
                # End-of-turn sentinel; summary is in _summary but the
                # SSE consumer already has it (done + text events).
                continue
            yield chat_event.to_sse()

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
# /api/chat — JSON endpoint for programmatic testing / scripted scenarios
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Body of POST /api/chat."""

    message: str = Field(
        ..., description="User message to send to the chatbot.",
    )
    model: Optional[str] = Field(
        None,
        description=(
            "Gemini model id (one of SELECTABLE_MODELS). When omitted "
            "or unknown, falls back to the org default."
        ),
    )
    use_tools: bool = Field(
        True,
        description=(
            "Pass the ADMZ MCP server to Gemini as a tool source. "
            "Set false to run a tool-less turn for isolating SDK behavior."
        ),
    )


class ChatResponse(BaseModel):
    """Body of POST /api/chat."""

    success: bool
    response: str
    error: Optional[str] = None
    model: str
    interaction_id: Optional[str] = None
    input_tokens: int
    output_tokens: int
    cost_usd: Optional[float] = None
    tool_calls: list[str] = Field(default_factory=list)
    rejected_by_budget: bool = False


@router.post("/api/chat", response_model=ChatResponse, tags=["chat"])
async def chat_json(
    body: ChatRequest = Body(...),
    principal: Principal = Depends(get_current_principal),
) -> ChatResponse:
    """Run a chat turn and return the full result as JSON.

    Same auth, budget gate, audit log, and MCP tool surface as
    ``/chat/stream`` — the only difference is the wire format. Lets
    operators script test scenarios (curl, requests, pytest, etc.)
    without parsing SSE.

    Example::

        curl -X POST http://localhost:4242/api/chat \\
             -H 'Content-Type: application/json' \\
             -d '{"message": "list my devices"}'
    """
    config = get_chatbot_config()
    final_summary: Optional[_TurnSummary] = None

    async for _event, summary in _run_chat_turn(
        principal=principal,
        message=body.message,
        model_request=body.model or "",
        config=config,
        use_tools=body.use_tools,
    ):
        if summary is not None:
            final_summary = summary

    assert final_summary is not None  # _run_chat_turn always yields it last

    return ChatResponse(
        success=final_summary.success,
        response=final_summary.response,
        error=final_summary.error,
        model=final_summary.model,
        interaction_id=final_summary.interaction_id,
        input_tokens=final_summary.input_tokens,
        output_tokens=final_summary.output_tokens,
        cost_usd=final_summary.cost_usd,
        tool_calls=final_summary.tool_calls,
        rejected_by_budget=final_summary.rejected_by_budget,
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
