"""Chatbot configuration — model selection, API key lookup, env bootstrap.

The Gemini API key is a *protected fleet setting* (joins the set
defined in :mod:`admz.api.confirm_store`). The env var
``ADMZ_GEMINI_API_KEY`` is read once on first access; if present
and the fleet setting is empty, the env value seeds the setting.
After that, the fleet setting is authoritative.

The selectable-models list is hardcoded rather than fleet-config'd
on purpose: the list of currently-supported Gemini model IDs is a
property of the deployed `google-genai` SDK version, not a runtime
preference. Adding a model = bumping the SDK + this list together.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

import admz.fleet_settings as _fs_module

logger = logging.getLogger(__name__)


def _fs():
    """Lookup the live fleet_settings singleton at call time.

    The module attribute is reassigned by some tests to point at a
    tmp-path DB, so a top-level ``from … import fleet_settings``
    would capture a stale reference.
    """
    return _fs_module.fleet_settings


# Latest-GA Gemini 3.1 models as of May 2026. See ADR-0025.
DEFAULT_MODEL = "gemini-3.1-pro"

SELECTABLE_MODELS: List[str] = [
    "gemini-3.1-pro",
    "gemini-3.1-flash",
    "gemini-3.1-flash-lite",
]


# Fleet-setting keys (also listed in PROTECTED_SETTING_KEYS).
_FS_KEY_API = "gemini_api_key"
_FS_KEY_DEFAULT_MODEL = "gemini_default_model"

# Env-var bootstraps.
_ENV_KEY_API = "ADMZ_GEMINI_API_KEY"
_ENV_KEY_DEFAULT_MODEL = "ADMZ_GEMINI_DEFAULT_MODEL"

# Bootstrap state — env-var seeding runs at most once per process.
_bootstrapped = False


@dataclass
class ChatbotConfig:
    """Snapshot of chatbot configuration as the chat route sees it."""

    api_key: Optional[str]
    default_model: str
    selectable_models: List[str]

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


def _bootstrap_from_env_once() -> None:
    """Seed fleet settings from env vars on first call.

    If the operator sets ``ADMZ_GEMINI_API_KEY`` and there is no
    persisted setting yet, copy the env value into the fleet
    store so subsequent process restarts pick it up without
    needing the env var. The fleet setting then becomes
    authoritative — changing the env var after this point is a
    no-op.
    """
    global _bootstrapped
    if _bootstrapped:
        return
    _bootstrapped = True

    env_api = os.getenv(_ENV_KEY_API)
    if env_api and not _fs().get(_FS_KEY_API):
        _fs().set(_FS_KEY_API, env_api)
        logger.info(
            "Seeded gemini_api_key from %s env var into fleet settings.",
            _ENV_KEY_API,
        )

    env_model = os.getenv(_ENV_KEY_DEFAULT_MODEL)
    if env_model and not _fs().get(_FS_KEY_DEFAULT_MODEL):
        if env_model in SELECTABLE_MODELS:
            _fs().set(_FS_KEY_DEFAULT_MODEL, env_model)
            logger.info(
                "Seeded gemini_default_model=%s from env into fleet settings.",
                env_model,
            )
        else:
            logger.warning(
                "Ignored %s=%r — not in SELECTABLE_MODELS %r.",
                _ENV_KEY_DEFAULT_MODEL,
                env_model,
                SELECTABLE_MODELS,
            )


def get_chatbot_config() -> ChatbotConfig:
    """Load the live chatbot configuration.

    Lazy-bootstraps env-var defaults on first call.
    """
    _bootstrap_from_env_once()

    api_key = _fs().get(_FS_KEY_API)
    default_model = (
        _fs().get(_FS_KEY_DEFAULT_MODEL) or DEFAULT_MODEL
    )
    if default_model not in SELECTABLE_MODELS:
        logger.warning(
            "Fleet-configured gemini_default_model=%r is not selectable; "
            "falling back to %s",
            default_model,
            DEFAULT_MODEL,
        )
        default_model = DEFAULT_MODEL

    return ChatbotConfig(
        api_key=api_key,
        default_model=default_model,
        selectable_models=list(SELECTABLE_MODELS),
    )


def is_chatbot_configured() -> bool:
    """Convenience: returns True iff an API key is configured."""
    return bool(get_chatbot_config().api_key)


def set_api_key(value: str) -> None:
    """Persist the Gemini API key. Only the /settings/chat route should call this."""
    _fs().set(_FS_KEY_API, value.strip())


def clear_api_key() -> None:
    _fs().delete(_FS_KEY_API)


def set_default_model(model: str) -> None:
    if model not in SELECTABLE_MODELS:
        raise ValueError(
            f"Model {model!r} is not in SELECTABLE_MODELS {SELECTABLE_MODELS!r}"
        )
    _fs().set(_FS_KEY_DEFAULT_MODEL, model)


def mask_api_key(value: Optional[str]) -> str:
    """Return a display-safe placeholder for the configured API key."""
    if not value:
        return "(not configured)"
    return f"configured ({len(value)} chars, ends with ...{value[-4:]})"
