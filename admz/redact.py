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

GH #336: this predicate itself had a gap, in exactly the shape #217 and #157
already named — the canonical list was still an enumeration, and the wire
format is what actually needed enumerating. ``pwd`` and ``pass`` are the
literal VAPIX query keys that carry a device password
(``pwdgrp.cgi:add-user``/``update-user``, ``networkshare-add.cgi:add``) —
neither is a substring of anything in ``_SENSITIVE_KEY_PARTS``, so a value
under either key reached ``mcp/server.py::_sanitize_tool_args`` (and every
other one of this predicate's ~12 callers) unmasked. Added the same way
``pat`` already was: a delimiter-bounded discrete-token match, not a bare
substring — ``pass`` as a substring would mask ``bypass``/``passive``/
``compass``, the exact leak/noise trade #310 already refused for httpx URLs.

GH #336 items 2/3 — why THIS is still the one canonical predicate, and two
close-looking relatives are not folded in here. There are three places in
this codebase that answer "is this value a secret?", and after fixing the
gap above it would be easy to read the remaining two as further drift that
should be consolidated into this one. It would be a mistake to do that.

* **This module** answers it for a bare key-name string, from call sites —
  the MCP audit sanitizer, chat display, fleet-settings masking, the CLI,
  snapshot facets — that mostly have **no catalog operation to resolve at
  all**. What VAPIX operation does a fleet-setting name or a chat-display
  dict key correspond to? None; the question doesn't parse. So this
  predicate has to stay general-purpose and catalog-agnostic — a bare
  string in, a yes/no out, no other context assumed or required.
* **``admz/executor/vapix.py::secret_param_names`` / ``SECRET_PLACEHOLDER_NAMES``**
  (#334) answers it for one **already-resolved catalog operation**'s own
  request template, at a point deep inside ``execute_gated_operation`` where
  exactly that context — and nothing else — is available. It is
  deliberately narrower and exact-match rather than substring, because the
  VAPIX catalog uses ``*Token``-suffixed and bare ``{Token}`` placeholders
  throughout for legitimate non-secret resource identifiers
  (``{PresetToken}``, ``{RelayToken}``, ONVIF door references) that this
  predicate's substring rule on ``token`` would wrongly flag and silently
  strip from a confirm session with no password-entry field to explain why.
  That file's own module comment works through this in full, including the
  same "a future reader who helpfully consolidates this would reintroduce
  the regression" warning this paragraph is making from the other side.
* **``redact_url``** below answers it for a URL string with **no key names
  at all**, by masking every query value unconditionally rather than
  enumerating anything (#310) — the URL vocabulary isn't closed, so there
  is nothing here to consolidate with either.

Consolidating any pair makes the absorbing predicate wrong for cases the
other exists to handle: making this module structural breaks it for fleet
settings and chat display (nothing to resolve); making the VAPIX predicate
a substring match reopens the ``{PresetToken}`` regression #334 was written
to prevent. Three lists that don't drift into each other is not an
accident here — it's three domains that only look like one from a
distance. What DOES need to hold, and is guarded by
``tests/test_sensitivity_predicate_completeness.py::TestCatalogDeclaredSecretsAreRecognized``:
every wire key the VAPIX predicate derives from the catalog must also be
recognised by this one — not because they should be the same list, but
because a value this predicate misses is a value the audit log, chat
display, and every other general-purpose surface above will show in the
clear, regardless of what the narrower catalog-structural predicate got
right closer to the wire.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MASK = "***"

# Substring matches. ``key`` and the discrete tokens below are handled
# separately because their bare substrings over-match (file_path, pattern,
# bypass, passive, the literal ``key`` argument of set_fleet_setting which
# names a setting, not a secret).
_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
)

# Short, ambiguous spellings that must match as a discrete, delimiter-bounded
# component of the key — never as a bare substring, because each is also a
# real prefix/infix of ordinary, non-secret words:
#
#   pat  -> file_path, upgrade_path, pattern    (real hit: github_pat)
#   pwd  -> (short; kept consistent with the others rather than assumed safe)
#   pass -> bypass, passive, compass, passthrough
#
# ``pwd`` and ``pass`` are here because they are not hypothetical — they are
# the actual VAPIX wire-query keys that carry a device password on the wire
# (``pwdgrp.cgi:add-user`` / ``update-user`` -> ``pwd``; ``networkshare-add.cgi:add``
# -> ``pass``), confirmed by parsing every operation in the atlas catalog
# (GH #336). Joining them into ``_SENSITIVE_KEY_PARTS`` as bare substrings
# was considered and rejected: #310 already refused exactly that trade for
# httpx URLs (a leak/noise trade), and ``pass`` as a substring would mask
# every argument merely containing it as a byte sequence, not a token.
_DISCRETE_SENSITIVE_TOKENS_RE = re.compile(r"(?:^|[_\-.])(?:pat|pwd|pass)(?:[_\-.]|$)")


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
    return bool(_DISCRETE_SENSITIVE_TOKENS_RE.search(k))


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
