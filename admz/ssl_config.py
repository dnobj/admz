"""Shared TLS-verification policy for ADMZ.

Devices on the local network typically ship with self-signed certificates,
so out of the box ADMZ does **not** verify device TLS certs. Operators
who have invested in a real PKI (or pre-installed trust anchors on the
ADMZ host) can flip the default by setting the ``ADMZ_VERIFY_SSL``
environment variable.

Resolution::

    ADMZ_VERIFY_SSL unset      → False (current behavior, backward compatible)
    ADMZ_VERIFY_SSL=true       → True
    ADMZ_VERIFY_SSL=false      → False
    ADMZ_VERIFY_SSL=1 / 0      → True / False
    ADMZ_VERIFY_SSL=yes / no   → True / False

Case-insensitive. Any other value falls back to False with a warning.

Consumers should call ``verify_ssl_default()`` once at module init (or pass
the result through to httpx clients).
"""

import logging
import os
from typing import Optional


_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}

logger = logging.getLogger(__name__)


def verify_ssl_default(env_value: Optional[str] = None) -> bool:
    """Return the current default for device TLS verification.

    ``env_value`` lets tests override; production reads from
    ``ADMZ_VERIFY_SSL``.
    """
    raw = env_value if env_value is not None else os.getenv("ADMZ_VERIFY_SSL")
    if raw is None or raw == "":
        # Backward-compatible default: device TLS is not verified.
        return False
    norm = raw.strip().lower()
    if norm in _TRUE_VALUES:
        return True
    if norm in _FALSE_VALUES:
        return False
    logger.warning(
        "ADMZ_VERIFY_SSL=%r is not recognized — falling back to False. "
        "Use one of true/false/1/0/yes/no.",
        raw,
    )
    return False
