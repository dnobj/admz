"""Response security headers, principally a Content-Security-Policy (#200).

## What this policy is, and what it deliberately is not

**It is complete against external subresource loads. It is weak against XSS.**
Read that as the design, not as an oversight.

``script-src`` retains ``'unsafe-inline'``. A strict policy would be much
stronger, and it is also a large refactor that this change is not: the
templates currently contain **16 inline ``<script>`` blocks, 32 inline ``on*=``
event handlers, 11 ``<style>`` blocks and 640 inline ``style="…"``
attributes**. ``script-src 'self'`` alone would break the UI on the first page
load. Nonces or hashes for ~699 constructs is its own piece of work, tracked
separately.

The key property is that ``'unsafe-inline'`` **does not weaken the source
allow-list**. A policy of ``script-src 'self' 'unsafe-inline'`` still refuses
``https://unpkg.com`` — which is exactly the threat in #200, where an attacker
who compromises a CDN or an npm package executes in the same document as the
Windows sign-in form, the credential capture forms and the ADR-0034
confirmation-gate password prompt. So this closes that completely while leaving
the XSS story for later.

## Why it can be tight everywhere else

As of #200 ADMZ loads **no** external subresources: ``lucide`` is vendored
under ``static/vendor/`` and the Google Fonts ``@import`` is gone. Verified by
``tests/test_no_external_subresources.py``, which fails on any new one. So
``default-src 'self'`` costs nothing today, and the guard test is what keeps
that true.

Audited before choosing the directives, so these are measured rather than
copied from a blog post:

* **no ``eval`` or ``new Function``** anywhere in ``static/`` or the templates,
  *including the vendored lucide bundle* — so no ``'unsafe-eval'``.
* **no ``blob:``/``data:`` images, no ``createObjectURL``, no ``url()`` at all
  in the CSS** — so ``img-src 'self'`` is enough; ``data:`` is allowed anyway
  because it is the one thing a future inline SVG or favicon would want and it
  carries no script.
* **WebSockets are used** (``voice.js``, ``voice-worklet.js``). Same-origin
  ``ws:``/``wss:`` is covered by ``'self'`` in CSP Level 3, which every browser
  this tool targets implements. Called out because it is the directive most
  likely to bite if someone tightens ``connect-src`` further.
* **``AudioWorklet.addModule``** loads a same-origin worklet; ``worker-src
  'self'`` is set explicitly rather than relying on the ``script-src``
  fallback.

``frame-ancestors 'none'`` supersedes ``X-Frame-Options`` on modern browsers;
the legacy header is sent too because it costs one line and older browsers
ignore the CSP directive. ``form-action 'self'`` complements #3's same-origin
POST check from the other direction: #3 refuses a form *arriving* from
elsewhere, this refuses one *leaving* for elsewhere.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

#: The policy, assembled from the audit above.
CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        # 'unsafe-inline' is retained on purpose (see module docstring). It
        # permits the existing inline scripts and handlers; it does NOT permit
        # https://unpkg.com, which is the point.
        "script-src 'self' 'unsafe-inline'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        # Same-origin ws:/wss: is covered by 'self' under CSP3.
        "connect-src 'self'",
        "worker-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    )
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    # Superseded by frame-ancestors above; kept for browsers that predate it.
    "X-Frame-Options": "DENY",
    # Capture and confirm URLs carry single-use tokens in the path. Sending a
    # full Referer off-site would leak them; same-origin keeps the header
    # useful for #3's Referer fallback while never emitting it cross-origin.
    "Referrer-Policy": "same-origin",
}


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach :data:`SECURITY_HEADERS` to every response.

    Applied unconditionally — including to ``/static`` and to error responses.
    A policy that covers only the pages someone remembered to decorate is the
    kind of protection that reads as complete and is not.
    """
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        # Do not clobber a header a route set deliberately.
        if name not in response.headers:
            response.headers[name] = value
    return response
