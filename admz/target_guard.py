"""Single-sourced refusal against pointing E2E/dev tooling at the live
production ADMZ instance (#180).

**Mirrors the shape ``tests/_admz_isolation.py`` uses for ``ADMZ_HOME``**
(that module's docstring is the reference for this one): don't trust that a
safe *default* was picked — resolve the value through the same precedence
the calling tool actually uses for its own request, and verify *that*
result. Fail closed with a raised exception, not a skip: a pytest ``skip``
reads as "nothing to do here" and scrolls past in a one-line summary; a
:class:`RuntimeError` stops the run and prints why.

**Why this is a shared module and not duplicated per-tool.** Two separate
tools resolve "which ADMZ instance do I talk to" the same dangerous way:
``tests/e2e/conftest.py`` (host process: pytest) and
``tools/dev_auto_approve.py`` (host process: a standalone CLI). A guard
written into only one of them is a guard that *looks* total in a diff but
isn't — the #180 verification comment named this as exactly how one tool
would end up covered while the other quietly keeps the old default. Putting
the check here means both tools call the same, single, tested function.

CLAUDE.md states the rule this enforces: "Never point tests, agents, or
experiments at :4242 or C:\\ProgramData\\admz."
"""

from __future__ import annotations

import os
from typing import Mapping, Optional
from urllib.parse import urlsplit

#: The production port. Matched against the resolved *host:port*, not string
#: equality against a fixed URL, so ``http://127.0.0.1:4242``,
#: ``http://localhost:4242`` and (in principle) ``http://[::1]:4242`` are all
#: caught alike, the way ``tests/_admz_isolation.py`` matches path
#: *containment* rather than a fixed string.
PRODUCTION_PORT = 4242

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

#: The one named, explicit opt-in (#180 review: "one explicit, loud, named
#: opt-in... it must not be satisfiable by accident, and it must not be the
#: kind of variable that lingers in a shell from an earlier session").
#:
#: Deliberately NOT a boolean (``=1`` / ``=true``). Its value must equal the
#: *exact* URL being refused. That gets both properties for free: typing the
#: literal production URL into an "I accept" variable is the "say the
#: dangerous thing out loud" property, and a value left over from a past
#: session only keeps working for as long as you keep pointing at the exact
#: same URL it names — point somewhere else, and a stale boolean would still
#: silently say yes, but a stale URL-pinned value stops matching.
ESCAPE_HATCH_ENV = "ADMZ_E2E_ALLOW_PRODUCTION_URL"


def targets_production(url: str) -> bool:
    """True if ``url`` resolves to the production host:port.

    Any loopback spelling on :data:`PRODUCTION_PORT`. A bare host with no
    explicit port (``http://127.0.0.1``) is not production under this check
    — ADMZ has no documented default-port deployment, and guessing one would
    risk false positives against an unrelated local service.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return host in _LOOPBACK_HOSTS and parts.port == PRODUCTION_PORT


def format_refusal(url: str, *, source: str) -> str:
    return "\n".join([
        "",
        "ADMZ target guard FAILED - refusing to run (#180).",
        "",
        f"{source} resolved to {url!r}, which is the production ADMZ",
        "instance (port 4242). CLAUDE.md is explicit about this:",
        '  "Never point tests, agents, or experiments at :4242 or',
        '   C:\\ProgramData\\admz."',
        "",
        "Point this at staging instead (port 4243), e.g.:",
        "    ADMZ_E2E_BASE_URL=http://127.0.0.1:4243",
        "",
        "If you mean to target production, deliberately, with explicit",
        f"human authorization: set {ESCAPE_HATCH_ENV} to the *exact* URL",
        f"above — {url!r} — not '1' or 'true'. Any other value refuses.",
        "",
    ])


def refuse_if_production(
    url: str,
    *,
    source: str,
    env: Optional[Mapping[str, str]] = None,
) -> None:
    """Raise :class:`RuntimeError` if ``url`` is the production instance and
    the escape hatch was not set to that exact URL.

    ``source`` names what resolved ``url`` (e.g. ``"ADMZ_E2E_BASE_URL (or
    the :4243 default)"``) so the refusal message says where the bad value
    came from.
    """
    if not targets_production(url):
        return
    env = os.environ if env is None else env
    if env.get(ESCAPE_HATCH_ENV) == url:
        return
    raise RuntimeError(format_refusal(url, source=source))
