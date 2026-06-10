"""Shared redaction rules — the one place that decides "is this a secret?".

D-2 (review 2026-06-10): three surfaces each kept their own sensitive-key
list and they drifted — chat masked ``apikey``/``key`` but audit didn't,
fleet-settings masked ``pat`` but not ``api_key``, and the audit sanitizer
didn't recurse into lists, so a password inside a list of dicts reached the
audit log in plaintext. All three now delegate here.

Deliberately a leaf module (stdlib only) so anything can import it.

Security invariant (project-wide): device passwords must NEVER appear in
event payloads, audit rows, or chat cards. Key *names* may pass through —
they tell the operator what was present; only values are masked.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

MASK = "***"

# Substring matches. ``key`` and ``pat`` are handled separately below
# because their bare substrings over-match (file_path, pattern, the literal
# ``key`` argument of set_fleet_setting which names a setting, not a secret).
_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
)

# ``pat`` (personal access token) only as a discrete token: github_pat,
# survey.pat — but never file_path / upgrade_path / pattern.
_PAT_TOKEN_RE = re.compile(r"(?:^|[_\-.])pat(?:[_\-.]|$)")


def is_sensitive_key(key: Any) -> bool:
    """True if values stored under ``key`` must be masked before display,
    logging, or audit."""
    k = str(key).lower()
    if any(part in k for part in _SENSITIVE_KEY_PARTS):
        return True
    # Compound key names (api_key already matched above): ssh_key, fernet_key,
    # keyfile, private_key... The bare argument name ``key`` is exempt — it
    # carries a setting *name* (e.g. set_fleet_setting), not a secret.
    if "key" in k and k != "key":
        return True
    return bool(_PAT_TOKEN_RE.search(k))


def redact_structure(obj: Any, *, _depth: int = 0, max_depth: int = 10) -> Any:
    """Return a copy of ``obj`` with every value under a sensitive key masked.

    Recurses into BOTH mappings and lists/tuples (the audit sanitizer's
    list-recursion hole was the concrete leak this module exists to close).
    Non-container leaves pass through unchanged; no truncation — display
    concerns (string/list caps) stay with the chat layer.
    """
    if _depth > max_depth:
        return MASK
    if isinstance(obj, Mapping):
        return {
            k: (MASK if is_sensitive_key(k)
                else redact_structure(v, _depth=_depth + 1, max_depth=max_depth))
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [
            redact_structure(v, _depth=_depth + 1, max_depth=max_depth)
            for v in obj
        ]
    return obj
