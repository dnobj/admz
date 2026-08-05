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

GH #217: name-based masking is structurally blind to the ``{key: <name>,
value: <secret>}`` argument shape, where the sensitivity of one field is
declared by a *sibling* rather than by its own name. ``set_fleet_setting``
is that shape: ``key`` is exempt (it names a setting) and ``value`` never
looks sensitive, so the secret was the one field no rule inspected. See
:func:`sibling_masked_fields`.

GH #157: a fourth surface — URLs reaching a log line, whether ADMZ's own
(``admz/modules/acs_pro/firebird.py``) or a third-party library's
(the ``httpx`` request logger, via ``admz/logging_config.py``). See
:func:`redact_url`, which masks by *value*, not by enumerating key names —
the query-key vocabulary a URL can carry is not closed, so a key-name list
is the wrong shape here for the same reason it failed three times for
fleet-setting keys (``admz/setting_policy.py``).
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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


#: Fields that carry a *name* qualifying a sibling value field. ``key`` and
#: ``name`` are the shapes that actually occur (``set_fleet_setting``'s
#: arguments; SOAP ``<Parameter Name=… Value=…>``, which
#: ``rules/runner.py::redact_soap_body`` already solves the same way); the
#: rest are cheap insurance against the next tool to adopt the shape.
_NAME_FIELDS = (
    "key",
    "name",
    "setting",
    "setting_key",
    "param",
    "parameter",
    "field",
)

#: Fields whose sensitivity a sibling name field may declare.
_VALUE_FIELDS = ("value", "val", "new_value", "setting_value")


def sibling_masked_fields(mapping: Any) -> frozenset:
    """Value-carrying field names in ``mapping`` that a *sibling* name field
    declares sensitive.

    ``{"key": "default_password", "value": "hunter2"}`` → ``{"value"}``;
    ``{"key": "default_username", "value": "root"}`` → empty.

    Deliberately fail-safe: it triggers only when a mapping holds BOTH a name
    field and a value field, and in that narrow case it would rather mask an
    innocent value than let a credential through. ``is_sensitive_key`` matches
    ``key`` as a substring, so a name field holding e.g. ``"monkey"`` will
    over-mask its sibling — an acceptable trade against the invariant above.
    """
    if not isinstance(mapping, Mapping):
        return frozenset()
    declares_secret = any(
        isinstance(mapping.get(nf), str) and is_sensitive_key(mapping[nf])
        for nf in _NAME_FIELDS
    )
    if not declares_secret:
        return frozenset()
    return frozenset(vf for vf in _VALUE_FIELDS if vf in mapping)


def redact_structure(obj: Any, *, _depth: int = 0, max_depth: int = 10) -> Any:
    """Return a copy of ``obj`` with every value under a sensitive key masked.

    Recurses into BOTH mappings and lists/tuples (the audit sanitizer's
    list-recursion hole was the concrete leak this module exists to close).
    Also masks sibling-declared values (#217, :func:`sibling_masked_fields`).
    Non-container leaves pass through unchanged; no truncation — display
    concerns (string/list caps) stay with the chat layer.
    """
    if _depth > max_depth:
        return MASK
    if isinstance(obj, Mapping):
        sibling = sibling_masked_fields(obj)
        return {
            k: (MASK if (is_sensitive_key(k) or k in sibling)
                else redact_structure(v, _depth=_depth + 1, max_depth=max_depth))
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [
            redact_structure(v, _depth=_depth + 1, max_depth=max_depth)
            for v in obj
        ]
    return obj


# ---------------------------------------------------------------------------
# URL redaction (#157)
# ---------------------------------------------------------------------------
#
# Originally lived only in admz/modules/acs_pro/firebird.py, scoped to the ACS
# webhook URL. Promoted here so a second implementation never has to be
# written — and so it doesn't have to be, since #157's leak (VAPIX device
# passwords reaching the log via httpx's INFO request line) needed the same
# "mask a URL's secrets" operation from a call site that must not import an
# optional, driver-dependent module (acs_pro/firebird.py pulls in
# firebird-driver) just to redact a log line.


def redact_url(url: Any, *, keys: Optional[Iterable[str]] = None) -> Optional[str]:
    """Mask secrets a URL may carry: ``user:pass@`` userinfo, always; and
    query-parameter values, either every one of them (``keys=None``, the
    default) or only those whose key matches ``keys`` (case-insensitive).

    ``keys=None`` — mask every query value — is the recommended mode for any
    URL whose query vocabulary isn't closed. A fixed "these are the secret
    key names" list cannot be complete by construction wherever a caller can
    inject an arbitrary query parameter under any name — exactly what
    ``admz/executor/vapix.py`` does for VAPIX operations, so a device
    password can arrive at this function under any key. This project has
    already reproduced that precise enumeration failure three times over,
    for fleet-setting keys rather than query keys: three independent
    enumeration methods returned 8, 10 and 18 "protected" keys, each missing
    ones the others found (see ``admz/setting_policy.py``). Its fix was to
    stop enumerating the unsafe set and change which way the default fails.
    ``keys=None`` applies the same fix here: an unrecognised parameter is
    hidden, not exposed.

    Pass an explicit ``keys`` only where the caller can show the query
    vocabulary is closed and the non-secret values are worth keeping — e.g.
    the ACS webhook URL's own well-known parameters
    (``admz/modules/acs_pro/firebird.py``).
    """
    if url in (None, ""):
        return None
    try:
        text = str(url)
        parts = urlsplit(text)
        netloc = parts.netloc
        if "@" in netloc:
            netloc = "***@" + netloc.rsplit("@", 1)[1]
        query = parts.query
        if query:
            pairs = parse_qsl(query, keep_blank_values=True)
            if keys is None:
                query = urlencode([(k, MASK) for k, _ in pairs])
            else:
                key_set = {k.lower() for k in keys}
                query = urlencode([
                    (k, MASK if k.lower() in key_set else v) for k, v in pairs
                ])
        return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))
    except Exception:  # noqa: BLE001 — never let redaction failure leak the raw URL
        return "***"
