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

**Every terminal outcome discards the stash, not just success** (GH #170). The
paragraph above — "until the approval executes — then it is consumed" — was
true of success and silently false of deny, TTL expiry, and plain abandonment
(the user fills the form, then never returns): a token orphaned by any of
those left its plaintext resident for as long as the process ran, because
purging was lazy — triggered only as a side effect of *other* rule-capture
activity (:func:`stash_rule_secrets`, :func:`consume_captured_rule_secrets`)
happening to occur later in the same process. On a quiet install, "later"
could mean never. Three changes close this:

1. :func:`discard_rule_secrets` — written for exactly this, previously wired
   to nothing — is now called from the deny handler
   (``admz/api/routes/confirm.py::chat_confirm_deny``), the only deny path
   that exists (the plain web ``/confirm/{token}`` form has no deny action at
   all — only chat's inline approval card does).
2. :func:`has_rule_secrets` now purges expired entries as a side effect of
   reading, not just of writing — so a caller that only ever checks (never
   stashes or consumes) still keeps the dict bounded.
3. A small periodic sweep (:func:`start_background_purge` /
   :func:`stop_background_purge`, wired into ``admz/api/main.py``'s
   lifespan) makes the TTL a real, time-triggered bound instead of one that
   only fires when something unrelated happens to touch this module — the
   case (1) and (2) above cannot reach: an abandoned token that nothing ever
   reads or writes again. This mirrors the lesson GH #314 already recorded
   for a different in-memory secret-adjacent store
   (``admz/mcp/temp_credentials.py``) — reactive-only cleanup silently
   depends on something else happening to trigger it, which is exactly the
   failure mode that let both defects go unnoticed. The sweep is a bare
   ``asyncio`` loop, not an OS thread and not a job on the operator-facing
   task scheduler (``admz/tasks/``) — that scheduler exists for actions an
   operator chooses to schedule; this is internal hygiene enforcing a bound
   already fixed at ``_TTL_SECONDS``, not something to expose as a task.

**What "discarded" does and does not mean.** ``discard_rule_secrets`` (and
the purge paths above) drop the dict entry — the only reference ADMZ holds to
the string — making it eligible for garbage collection. That is **not** the
same claim as "erased from process memory." Python gives no API to zero a
``str``'s backing bytes, and CPython gives no guarantee about when freed
memory is reused or overwritten; a dump taken between the drop and whatever
later reuses that memory could still show it. What this buys: the value is
no longer *reachable* from ADMZ's own code within, at most, one sweep
interval of its TTL — down from "until the process restarts, on a quiet
install." What it does not buy: erasure. If that stronger guarantee is ever
required, it needs a mutable buffer type Python can scrub deliberately (e.g.
a ``bytearray`` overwritten before release) — a larger change than this one
and not attempted here.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Slightly longer than the confirm-session TTL (300s) so the secret survives a
# user who enters credentials, then takes a minute to approve.
_TTL_SECONDS = 600.0

# How often the background sweep checks for orphaned stashes (GH #170). Not
# tied to _TTL_SECONDS: this bounds how long an entry can outlive its TTL
# with nothing else touching the module, not the TTL itself.
_SWEEP_INTERVAL_SECONDS = 60.0

_LOCK = threading.Lock()
# token -> {"values": {soap_param_name: value}, "expires": epoch_seconds}
_SECRETS: Dict[str, Dict] = {}

_sweep_task: Optional["asyncio.Task"] = None


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
    """True if a non-expired secret stash exists for this token.

    Purges expired entries as a side effect (GH #170), same as
    :func:`stash_rule_secrets` and :func:`consume_captured_rule_secrets` —
    so a caller that only ever *checks* (e.g. the confirm page deciding
    whether to show "credentials captured") still keeps the dict bounded,
    not just callers that write.
    """
    now = time.time()
    with _LOCK:
        _purge_expired_locked(now)
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


def _sweep_once() -> None:
    """One purge pass — the unit the background loop repeats. Split out so a
    test can drive a "sweep fires" scenario synchronously, without waiting on
    a real sleep (GH #170)."""
    with _LOCK:
        _purge_expired_locked(time.time())


async def _sweep_loop() -> None:
    while True:
        await asyncio.sleep(_SWEEP_INTERVAL_SECONDS)
        try:
            _sweep_once()
        except Exception:  # noqa: BLE001 — one bad pass must not kill the loop
            logger.warning("rule-secret sweep pass failed", exc_info=True)


def start_background_purge() -> None:
    """Start the periodic sweep (GH #170). Idempotent — safe to call more
    than once (e.g. a lifespan that restarts without a clean shutdown).

    This is the only thing that reaches an orphaned stash that nothing ever
    reads or writes again — :func:`discard_rule_secrets` (wired into deny)
    and the purge-on-read in :func:`has_rule_secrets` both require *some*
    call to happen for that specific token; a token nobody ever touches
    again needs a clock, not a caller.
    """
    global _sweep_task
    if _sweep_task is None or _sweep_task.done():
        _sweep_task = asyncio.create_task(_sweep_loop())


def stop_background_purge() -> None:
    """Cancel the sweep. Safe to call when it was never started."""
    global _sweep_task
    if _sweep_task is not None:
        _sweep_task.cancel()
        _sweep_task = None
