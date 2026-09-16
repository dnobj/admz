"""The ``[console]`` note a review writes (ADR-0071 §4).

An ``event`` row is trusted ground truth — the forgery guard leaves it alone —
so it is the one lane device-written text must never ride. The note names the
notice id, the device **id**, counts, ages and the source: never a nickname,
model, host, parameter value or an event notice's title.

"Nothing has been changed" is part of every note: a notice is attention, not
an action.
"""

from __future__ import annotations

import time
from typing import Iterable, List, Optional

from admz.notices.store import KIND_DRIFT, Notice

PREFIX = "[console] The user opened"
CLOSING = "Nothing has been changed."


def _ident(value: object) -> str:
    """An identifier as the note may carry it: one line, bounded."""
    from admz.validators import sanitize_display_text
    return sanitize_display_text(value, max_length=64)


def _ago(ts: Optional[float], now: float) -> str:
    try:
        secs = now - float(ts or 0)
    except (TypeError, ValueError):
        return "at an unknown time"
    if not ts or secs < 0:
        return "at an unknown time"
    if secs < 60:
        return "under a minute ago"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def _count(value: object) -> int:
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def describe(notice: Notice, now: Optional[float] = None) -> str:
    """One notice, in the note's vocabulary."""
    from admz.notices.producers import SOURCE_LABELS

    now = time.time() if now is None else now
    source = SOURCE_LABELS.get(notice.source, "a check")
    device = _ident(notice.device_id)
    if notice.kind == KIND_DRIFT:
        parts: List[str] = []
        fields = _count(notice.summary.get("fields"))
        absent = _count(notice.summary.get("facets_absent"))
        if fields or not absent:
            parts.append(f"{fields} field(s) differ from its blessed baseline")
        if absent:
            parts.append(f"{absent} baselined facet(s) are no longer present")
        return (
            f"configuration drift on device {device} — {' and '.join(parts)}; "
            f"first seen {_ago(notice.created_at, now)}, last confirmed "
            f"{_ago(notice.updated_at, now)} by {source}"
        )
    where = f"on device {device}" if device else "fleet-wide"
    return (
        f"an event detection ({_ident(notice.task_id) or 'no task id'}) fired "
        f"{where} — {notice.occurrences} time(s); first seen "
        f"{_ago(notice.created_at, now)}, last fired {_ago(notice.updated_at, now)}"
    )


def review_note(notices: Iterable[Notice], now: Optional[float] = None) -> str:
    """The note for one notice, or one note for several."""
    items = list(notices)
    if not items:
        raise ValueError("a review note needs at least one notice")
    now = time.time() if now is None else now
    if len(items) == 1:
        n = items[0]
        return (f"{PREFIX} notice #{n.id} for review from the Console: "
                f"{describe(n, now)}. {CLOSING}")
    body = "; ".join(f"#{n.id} {describe(n, now)}" for n in items)
    return (f"{PREFIX} {len(items)} notices for review from the Console: "
            f"{body}. {CLOSING}")
