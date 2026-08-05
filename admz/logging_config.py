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

``configure_logging()`` also installs :class:`_HttpxUrlRedactingFilter`
on the ``httpx`` logger (#157): httpx logs the full request URL —
query string included — at INFO, and VAPIX credential-setting
operations put the plaintext password in that query string. See the
filter's docstring for why every query *value* is masked rather than
matching against a fixed set of "secret" key names.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

from admz.redact import redact_url


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


_URL_TOKEN_RE = re.compile(r"\S+://\S+")


class _HttpxUrlRedactingFilter(logging.Filter):
    """Masks query-parameter values in the URL httpx logs at INFO for every
    request (#157).

    Installed httpx (0.28.1) logs the fully assembled request URL —
    including its query string — via ``logging.getLogger("httpx").info(...)``
    on every request/response pair (``httpx/_client.py``). VAPIX operations
    that set a device password put the plaintext password in that query
    string, by the CGI's own wire format (the atlas ``pwdgrp.cgi`` catalog
    entries), and ``admz/executor/vapix.py`` also lets a caller inject
    arbitrary extra query parameters under any name — so no fixed "these are
    the secret key names" list can be complete. This filter sidesteps that by
    not trying: it redacts every query VALUE unconditionally
    (``admz.redact.redact_url(..., keys=None)``), keeping keys, method, host,
    path and status intact. See ``admz/redact.py`` for the full reasoning.

    Attached to the ``httpx`` *logger* (not to root's handler): httpx always
    logs through ``logging.getLogger("httpx")`` directly
    (``httpx/_client.py:117``), and a logger-level filter runs once in
    ``Logger.handle()`` before the record is handed to any handler — so it
    redacts the record before it reaches root's single ``StreamHandler``,
    regardless of whether that handler's formatter is the plain-text
    ``Formatter`` or ``JsonFormatter`` (``ADMZ_LOG_FORMAT``); both read the
    same already-redacted ``record.msg``. A filter attached to the handler
    instead would not survive this module's own handler-rebuild:
    ``configure_logging()`` discards and recreates that handler on every
    call, silently dropping any filter attached to it — the ``httpx`` logger
    object, by contrast, persists across calls, which is why the guard below
    only adds this filter once.

    Operates on the fully rendered message text (``record.getMessage()``)
    rather than assuming a specific ``record.args`` shape, so it survives an
    httpx release that reorders or adds arguments to its log call — it only
    needs a bare ``scheme://`` token to appear somewhere in the line, which
    any URL httpx logs will produce (URLs cannot contain a literal space).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:  # noqa: BLE001 — never let a formatting quirk crash logging
            return True
        match = _URL_TOKEN_RE.search(rendered)
        if not match:
            return True
        redacted = redact_url(match.group(0))
        if redacted is None:
            return True
        record.msg = rendered[: match.start()] + redacted + rendered[match.end() :]
        record.args = ()
        return True


def _ensure_httpx_redaction_filter() -> None:
    """Idempotently attach :class:`_HttpxUrlRedactingFilter` to the ``httpx``
    logger. Safe to call every time :func:`configure_logging` runs — unlike
    the root handler, the ``httpx`` logger object is not recreated, so a
    naive unconditional ``addFilter`` would stack a duplicate on every call.
    """
    httpx_logger = logging.getLogger("httpx")
    if not any(isinstance(f, _HttpxUrlRedactingFilter) for f in httpx_logger.filters):
        httpx_logger.addFilter(_HttpxUrlRedactingFilter())


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

    # #157: httpx logs the full assembled request URL (query string
    # included) at INFO, and ADMZ never otherwise touches the "httpx"
    # logger — so without this, a VAPIX device password set via
    # pwdgrp.cgi:add-user/update-user lands in plaintext in this same
    # handler. See _HttpxUrlRedactingFilter for why it must attach to the
    # logger rather than to `handler` above.
    _ensure_httpx_redaction_filter()
