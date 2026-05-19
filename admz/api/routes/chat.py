"""Chatbot routes — Phase 5A scaffolding.

Three surfaces:

  - ``GET /chat``                   — the chat page (Jinja2)
  - ``POST /chat``                  — submit one turn, render result
  - ``POST /chat/clear``            — clear the principal's session
  - ``GET /settings/chat``          — admin config page
  - ``POST /settings/chat``         — save API key / default model

The route is intentionally lightweight: Phase 5A is non-streaming
and renders responses server-side. Phase 5B will introduce the SSE
endpoint and a small client-side renderer.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from admz.auth import Principal, get_current_principal
from admz.chatbot import SELECTABLE_MODELS, get_chatbot_config
import admz.chatbot.sessions as _sessions_module
from admz.chatbot.client import (
    ChatbotDependencyMissing,
    ChatbotNotConfigured,
    ChatbotTurnError,
    run_turn,
)
from admz.chatbot.config import (
    clear_api_key,
    mask_api_key,
    set_api_key,
    set_default_model,
)
from admz.chatbot.system_prompt import build_system_prompt


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
# /settings/chat — admin configuration
# ---------------------------------------------------------------------------


@router.get("/settings/chat", response_class=HTMLResponse)
async def chat_settings_page(
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    """Render the chatbot admin page (API key + default model)."""
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
    principal: Principal = Depends(get_current_principal),
):
    """Persist API key or default-model changes from the admin page."""
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
            "success": success,
            "error": error,
        },
    )
