"""Shared logging configuration for ADMZ.

Both entry points (``admz api`` and ``admz mcp``) call
``configure_logging()`` at startup. Configuration is env-driven:

  ADMZ_LOG_LEVEL  — CRITICAL / ERROR / WARNING / INFO (default) / DEBUG
  ADMZ_LOG_FORMAT — text (default) or json

Text format is human-readable, intended for interactive terminals:

    2026-05-18T14:32:01 INFO     admz.api.main: ADMZ API server starting

JSON format emits one JSON object per line, intended for log
aggregators (Splunk, Loki, ELK, Datadog, CloudWatch):

    {"timestamp":"2026-05-18T14:32:01.234567","level":"INFO",
     "logger":"admz.api.main","message":"ADMZ API server starting"}

``logger.info("hi %s", name, extra={"device_id": "cam-01"})`` —
anything in ``extra=`` is merged into the JSON object verbatim, so
operational logs can carry structured fields alongside the message.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional


_VALID_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
_VALID_FORMATS = {"text", "json"}


def resolve_log_level(env_value: Optional[str] = None) -> int:
    """Map ``ADMZ_LOG_LEVEL`` to a logging-module integer level.

    Pass ``env_value`` explicitly in tests; otherwise it's read from the
    environment.
    """
    raw = (env_value if env_value is not None else os.getenv("ADMZ_LOG_LEVEL", "INFO"))
    name = raw.strip().upper()
    if name in _VALID_LEVELS:
        return getattr(logging, name)
    logging.warning(
        "ADMZ_LOG_LEVEL=%r is not one of %s — falling back to INFO",
        raw,
        sorted(_VALID_LEVELS),
    )
    return logging.INFO


def resolve_log_format(env_value: Optional[str] = None) -> str:
    """Return the requested log format: ``"text"`` or ``"json"``.

    Unknown values fall back to ``"text"`` with a warning.
    """
    raw = env_value if env_value is not None else os.getenv("ADMZ_LOG_FORMAT", "text")
    name = (raw or "text").strip().lower()
    if name in _VALID_FORMATS:
        return name
    logging.warning(
        "ADMZ_LOG_FORMAT=%r is not one of %s — falling back to text",
        raw, sorted(_VALID_FORMATS),
    )
    return "text"


# Attributes set on every LogRecord by the stdlib; everything else
# the user put in extra={...} we want to round-trip into the JSON.
_STANDARD_LOGRECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "asctime", "message", "taskName",
}


class JsonFormatter(logging.Formatter):
    """One-JSON-object-per-line formatter for log aggregators.

    Emits ``timestamp`` (ISO 8601 UTC), ``level``, ``logger``, ``message``,
    plus any non-standard fields passed via ``extra={...}``. Exception
    info, when present, becomes a ``exception`` field with the traceback
    text.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Build the base payload
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc)
        payload: dict = {
            "timestamp": ts.isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge extras (anything not in the standard LogRecord attribute set)
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOGRECORD_ATTRS or key.startswith("_"):
                continue
            # Skip None message defaults from the args tuple, etc.
            payload[key] = value
        # Exception info → string
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Stack info → string
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        # default=str makes non-serializable values (dataclasses,
        # datetime instances, sets) become their repr rather than
        # raising — matches the audit log's defensive behavior.
        return json.dumps(payload, default=str)


def configure_logging(
    level: Optional[int] = None,
    fmt: Optional[str] = None,
) -> None:
    """Apply the shared ADMZ logging configuration.

    Safe to call more than once; subsequent calls re-set the formatter
    on the root logger's handler and adjust the level. The format is
    text by default; pass ``fmt="json"`` (or set ``ADMZ_LOG_FORMAT=json``)
    for one-object-per-line structured logs.
    """
    if level is None:
        level = resolve_log_level()
    if fmt is None:
        fmt = resolve_log_format()

    if fmt == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    # Wipe any existing handlers basicConfig left around so the
    # new formatter takes hold. logging.basicConfig is idempotent but
    # doesn't let us change the formatter on subsequent calls, which
    # is the whole point of the reconfigure path.
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(level)
