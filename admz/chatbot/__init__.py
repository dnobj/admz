"""
ADMZ chatbot package — Gemini-powered web chat with native MCP tool use.

See:
  - ADR-0024 (bundled web chatbot)
  - ADR-0025 (Gemini 3.1 + native MCP)
  - docs/specification/requirements/web-chatbot.md

The :mod:`google.genai` SDK is imported lazily inside
:mod:`admz.chatbot.client` so that ADMZ installs without the
chatbot dependency still work — only `/chat` requests trigger
the import.
"""

from admz.chatbot.config import (
    DEFAULT_MODEL,
    SELECTABLE_MODELS,
    ChatbotConfig,
    get_chatbot_config,
    is_chatbot_configured,
)
from admz.chatbot.sessions import ChatSessionStore, chat_sessions

__all__ = [
    "DEFAULT_MODEL",
    "SELECTABLE_MODELS",
    "ChatbotConfig",
    "ChatSessionStore",
    "chat_sessions",
    "get_chatbot_config",
    "is_chatbot_configured",
]
