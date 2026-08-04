"""Same-origin enforcement for browser-only, state-changing POSTs (#3).

## Why this is needed, and where it is *not*

CSRF needs **ambient authority** — credentials the browser attaches on its own.
ADMZ has four auth backends and they are not equally exposed:

===================  ===========================================  ============
backend              how a browser authenticates                  CSRF-able?
===================  ===========================================  ============
``windows-local``    ``admz_session`` cookie, ``SameSite=Lax``    **no**
``api-key``          ``Authorization: Bearer`` (never ambient)    **no**
``none``             nothing to borrow                            n/a
``windows``          proxy does Negotiate, injects a trusted      **YES**
``composite``        header — no cookie, so SameSite cannot help  **YES**
===================  ===========================================  ============

``SameSite=Lax`` already stops a cross-site POST from carrying
``admz_session`` (``admz/api/routes/auth_web.py``), and the in-process
Negotiate SSO path (ADR-0035) ends in that same cookie — so the deployment
described in ``CLAUDE.md`` is not the vulnerable one.

The gap is :class:`~admz.auth.ReverseProxyAuth` (ADR-0021): IIS/nginx performs
the Negotiate handshake with the browser and injects ``X-Remote-User``. The
browser supplies those credentials **automatically, on any request to that
origin, with no cookie involved**, so ``SameSite`` is irrelevant and a
cross-site form POST is fully authenticated. ``ADMZ_AUTH_BACKEND=composite``
includes that backend and is what ``docs/DEPLOYMENT_WINDOWS.md`` documents.

So #3 is real, but for a different reason than it states: the issue says "an
attacker who obtains a capture URL", and an attacker who has the token can
simply POST it themselves. What CSRF actually buys is the *victim's ambient
credentials* on an endpoint the attacker cannot otherwise reach.

## Fail closed, deliberately

If neither ``Origin`` nor ``Referer`` is present the request is **rejected**.
That is the stricter of the two options and it is affordable here because the
endpoints this guards are browser-only: they render an HTML form a human types
credentials into. A request to one of them with no browser provenance at all is
anomalous in its own right, and there is no legitimate non-browser client —
checked, none exists in ``admz/``, ``tools/``, ``scripts/`` or the docs.

Fail-open-on-absent was the alternative and is defensible: every current browser
sends ``Origin`` on a cross-origin POST, so the realistic attack is blocked
either way. It was rejected because it would silently accept exactly the
request shape that has no reason to exist.

## Host, not scheme

Comparison is on **host and port**, not scheme. Behind a TLS-terminating proxy
the browser sends ``Origin: https://admz.corp`` while ADMZ sees plain HTTP and
no ``X-Forwarded-Proto`` (uvicorn is started without ``proxy_headers``), so
comparing schemes would reject the very deployment that most needs this check.
Scheme adds nothing against CSRF: an attacker on ``http://evil.example`` and on
``https://evil.example`` is refused identically.

``ADMZ_TRUSTED_ORIGINS`` (comma-separated) exists for deployments where the
public hostname differs from the ``Host`` ADMZ receives.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Set
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

ENV_TRUSTED_ORIGINS = "ADMZ_TRUSTED_ORIGINS"


def _hostport(value: str) -> Optional[str]:
    """Normalise an origin-ish string to ``host[:port]``, lowercased.

    Accepts a full URL (``Referer``) or a bare origin (``Origin``). Returns
    None when there is no usable host, which callers treat as a failure rather
    than as a match.
    """
    if not value:
        return None
    parts = urlsplit(value.strip())
    if not parts.netloc:
        return None
    # netloc may carry userinfo; strip it. Keep the port.
    netloc = parts.netloc.rsplit("@", 1)[-1].lower()
    return netloc or None


def trusted_origins() -> Set[str]:
    """Extra ``host[:port]`` values accepted in addition to the request's own."""
    raw = os.getenv(ENV_TRUSTED_ORIGINS, "")
    out = set()
    for item in raw.split(","):
        hp = _hostport(item if "//" in item else f"//{item.strip()}")
        if hp:
            out.add(hp)
    return out


def expected_hostports(request: Request) -> Set[str]:
    """What this request considers "its own origin".

    Derived from the ``Host`` header — the value the browser sent and the one a
    reverse proxy normally forwards unchanged — rather than from
    ``request.url``, which a proxy hop can rewrite.
    """
    allowed = trusted_origins()
    host = (request.headers.get("host") or "").strip().lower()
    if host:
        allowed.add(host)
    return allowed


def check_same_origin(request: Request) -> None:
    """Raise ``HTTPException(403)`` unless this POST came from our own origin.

    Order: ``Origin`` if present, else ``Referer``. Both absent → refused.
    """
    allowed = expected_hostports(request)

    origin = request.headers.get("origin")
    # "null" is what a sandboxed iframe or a redirected cross-origin POST
    # sends. It is never our own origin, so treat it as a mismatch rather
    # than as absent — falling through to Referer would weaken the check.
    if origin:
        actual = _hostport(origin) if origin.lower() != "null" else None
        source = "Origin"
    else:
        referer = request.headers.get("referer")
        if not referer:
            logger.warning(
                "Rejecting %s %s: no Origin or Referer header. This endpoint "
                "serves a browser form only; see admz/csrf.py.",
                request.method,
                request.url.path,
            )
            raise HTTPException(
                status_code=403,
                detail=(
                    "This form must be submitted from the ADMZ web interface. "
                    "The request carried no Origin or Referer header."
                ),
            )
        actual = _hostport(referer)
        source = "Referer"

    if actual is None or actual not in allowed:
        logger.warning(
            "Rejecting %s %s: %s %r is not one of %s",
            request.method,
            request.url.path,
            source,
            actual,
            sorted(allowed),
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "This form must be submitted from the ADMZ web interface. "
                f"The request's {source} did not match this server."
            ),
        )
