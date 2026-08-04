"""Out-of-band capture of a rule's RECIPIENT credentials.

A notification/send-* action inlines a login + password for a third-party
recipient (an HTTP endpoint, an SMTP server) into its action configuration. To
keep that secret out of the LLM conversation, ADMZ never accepts it in chat:
the user enters it on a dedicated web form (``/capture/rule/{token}``), and it is
held **only in this (web) process's memory**, keyed by the rule's confirm-session
token, until the approval executes — then it is consumed (single-use) and merged
into the atlas-rendered config body just before it is sent to the device.

The secret therefore never touches: the chat context, the confirm-session
payload, the audit log, or any on-disk store. The pending rule *spec* (which
carries no secret) crosses the MCP-subprocess → web-process boundary through the
ordinary ``confirm_store`` (SQLite); the secret does not. Single-process web tier
is assumed (same as the plan engine / scheduler singletons). See ADR-0043.

**What enforces the "never reaches the payload" half** (#194): ``create_action_rule``
refuses outright — it does not silently strip — any ``param_choices`` key that
resolves to a sensitive param, matching by SOAP name *or* ``ui_label``,
case-insensitively, exactly as the atlas resolver that consumes those keys does
(``capabilities.secret_choice_keys``). The previous exact-name, case-sensitive
``pop`` was narrower than both the resolver and the tool schema, so
``{"Password": ...}`` survived it and was persisted verbatim. Note the guarantee is
upheld by keeping secrets *out of* the payload — **not** by redacting the payload
on the way to disk: ``redact_structure`` masks ``secret_fields`` too, and
``routes/rule_capture.py`` reads that back to render the form, so redacting here
would break this mechanism rather than protect it.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Optional

# Slightly longer than the confirm-session TTL (300s) so the secret survives a
# user who enters credentials, then takes a minute to approve.
_TTL_SECONDS = 600.0

_LOCK = threading.Lock()
# token -> {"values": {soap_param_name: value}, "expires": epoch_seconds}
_SECRETS: Dict[str, Dict] = {}


def _purge_expired_locked(now: float) -> None:
    for tok in [t for t, e in _SECRETS.items() if e["expires"] <= now]:
        _SECRETS.pop(tok, None)


def stash_rule_secrets(token: str, values: Dict[str, str]) -> None:
    """Hold captured recipient secrets for a pending rule, keyed by its confirm
    token. Overwrites any prior stash for the token (a re-submit)."""
    now = time.time()
    with _LOCK:
        _purge_expired_locked(now)
        _SECRETS[token] = {"values": dict(values), "expires": now + _TTL_SECONDS}


def has_rule_secrets(token: str) -> bool:
    """True if a non-expired secret stash exists for this token."""
    now = time.time()
    with _LOCK:
        entry = _SECRETS.get(token)
        return bool(entry) and entry["expires"] > now


def consume_captured_rule_secrets(token: str) -> Dict[str, str]:
    """Return AND remove the captured secrets for a token (single-use). Empty
    dict if none or expired — the caller treats that as 'not captured'."""
    now = time.time()
    with _LOCK:
        entry = _SECRETS.pop(token, None)
        _purge_expired_locked(now)
    if not entry or entry["expires"] <= now:
        return {}
    return dict(entry["values"])


def discard_rule_secrets(token: str) -> None:
    """Drop a token's stash (e.g. on denial). Best-effort."""
    with _LOCK:
        _SECRETS.pop(token, None)
