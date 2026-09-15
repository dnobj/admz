"""Approval and capture links — telling one a tool issued from one the model wrote.

An approval (``/confirm/<token>``) or capture (``/capture/<token>``) link is
real only when a tool call issued it: the session behind the token exists
because the gate created it. The chat model can also *write* a link of that
shape — copying it from earlier replies in the conversation — and a written
link has no session behind it. On 2026-09-15 a continuation turn told the
operator "the confirmation card for AXIS P8815-2 is ready" with a
``/confirm/`` link it had invented; nothing had been started.

Two defences share this module:

- :func:`redact_links` removes links from the model's own earlier replies
  before they are sent back to it as history, so the conversation stops
  teaching it the pattern. The stored transcript is unchanged.
- :func:`unbacked_tokens` finds the tokens a reply links that no tool issued
  this turn, so the tool loop can ask the model to make the real call instead
  of showing the link.

The console keeps its own check (``flagUnbackedLinks`` in ``chat.js``) as the
last line of defence. ``api/routes/chat.py`` matches narrower shapes because it
links sessions by kind; for "might the model have invented this" every shape
counts.
"""

from __future__ import annotations

import json
import re
from typing import Iterable, Set

#: Any approval or capture session link: ``/confirm/``, ``/capture/``,
#: ``/capture/rule/`` and ``/capture/fleet/``, each followed by a token.
LINK_RE = re.compile(r"/(?:confirm|capture(?:/(?:rule|fleet))?)/([A-Za-z0-9_-]{20,})")

#: What a link in an earlier reply becomes. Plain words, because the model reads it.
REDACTED = "(approval link — valid only in the turn that issued it)"


def tokens_in(value: object) -> Set[str]:
    """Every session token linked in ``value`` — text, or a JSON-able tool result.

    Never raises: a scan failure must not break a turn.
    """
    if isinstance(value, str):
        blob = value
    else:
        try:
            blob = json.dumps(value, default=str)
        except Exception:  # noqa: BLE001 - see the docstring
            return set()
    return set(LINK_RE.findall(blob))


def unbacked_tokens(text: str, issued: Iterable[str]) -> Set[str]:
    """The tokens ``text`` links that are not among those ``issued`` this turn."""
    return tokens_in(text) - set(issued)


def redact_links(text: str) -> str:
    """``text`` with every approval or capture link replaced by :data:`REDACTED`."""
    return LINK_RE.sub(REDACTED, text)
