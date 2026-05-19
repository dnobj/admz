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
from admz.chatbot.usage import (
    BudgetCheck,
    DailyUsage,
    PRICING,
    TokenUsageStore,
    check_budget,
    estimate_cost_usd,
    get_daily_budget,
    set_daily_budget,
    token_usage,
)

__all__ = [
    "DEFAULT_MODEL",
    "PRICING",
    "SELECTABLE_MODELS",
    "BudgetCheck",
    "ChatbotConfig",
    "ChatSessionStore",
    "DailyUsage",
    "TokenUsageStore",
    "chat_sessions",
    "check_budget",
    "estimate_cost_usd",
    "get_chatbot_config",
    "get_daily_budget",
    "is_chatbot_configured",
    "set_daily_budget",
    "token_usage",
]
