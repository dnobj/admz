"""Shared logging configuration for ADMZ.

Both entry points (`admz api` and `admz mcp`) call ``configure_logging()``
at startup. The log level is driven by the ``ADMZ_LOG_LEVEL`` environment
variable (default: ``INFO``).

Valid levels: ``CRITICAL``, ``ERROR``, ``WARNING``, ``INFO``, ``DEBUG``.
Case-insensitive. Unknown values fall back to ``INFO`` with a warning.

Example::

    ADMZ_LOG_LEVEL=DEBUG python -m admz api --port 4242
"""

import logging
import os
from typing import Optional


_VALID_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


def resolve_log_level(env_value: Optional[str] = None) -> int:
    """Map ``ADMZ_LOG_LEVEL`` to a logging-module integer level.

    Pass ``env_value`` explicitly in tests; otherwise it's read from the
    environment.
    """
    raw = (env_value if env_value is not None else os.getenv("ADMZ_LOG_LEVEL", "INFO"))
    name = raw.strip().upper()
    if name in _VALID_LEVELS:
        return getattr(logging, name)
    # Fall back to INFO and log the fallback at WARNING level so the
    # mis-set env var is visible.
    logging.warning(
        "ADMZ_LOG_LEVEL=%r is not one of %s — falling back to INFO",
        raw,
        sorted(_VALID_LEVELS),
    )
    return logging.INFO


def configure_logging(level: Optional[int] = None) -> None:
    """Apply the shared ADMZ logging configuration.

    Safe to call more than once; subsequent calls just adjust the root
    level. The format includes timestamp, level, logger name, and message.
    """
    if level is None:
        level = resolve_log_level()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # If basicConfig was already called (e.g. by uvicorn), force the level
    # on the root logger so ADMZ_LOG_LEVEL still takes effect.
    logging.getLogger().setLevel(level)
