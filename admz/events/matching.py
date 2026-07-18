"""Shared event-record matcher (ADR-0041 amendment).

One implementation of "does this normalized event match a spec?", used by BOTH
:class:`~admz.events.detections.EventDetection` (the firing half) and watched
events / the ingest gate (the capture half). A *spec* is scope (``source`` +
``device_id`` OR ``tag``) plus a ``match`` object (``category`` / ``topic`` /
``condition``); all supplied criteria are AND-ed.

Keeping this in one place means watched-event gating and detection firing can
never silently diverge in what they consider a match.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def record_matches(
    rec: Dict[str, Any],
    *,
    source: str = "device",
    device_id: Optional[str] = None,
    tag: Optional[str] = None,
    match: Optional[Dict[str, Any]] = None,
    device_tags: Optional[List[str]] = None,
) -> bool:
    """True if ``rec`` (a normalized event, see :mod:`admz.events.normalize`)
    satisfies the scope + match spec.

    - ``source`` must equal the record's source.
    - ``device_id`` (exact) OR ``tag`` (membership in ``device_tags``) scopes it;
      neither set ⇒ any device of that source.
    - ``match``: ``category`` (exact), ``topic`` (case-insensitive substring of
      the record's topic/type), and ``condition`` (``{key, op, value}`` over the
      inner ``data.data`` map; ops: ``eq`` default, ``ne``, ``exists``).
    """
    if rec.get("source") != source:
        return False

    did = rec.get("device_id")
    if device_id:
        if did != device_id:
            return False
    elif tag:
        if tag not in (device_tags or []):
            return False

    m = match or {}
    data = rec.get("data") or {}

    if m.get("category") and data.get("category") != m["category"]:
        return False

    if m.get("topic") and str(m["topic"]).lower() not in (rec.get("type") or "").lower():
        return False

    cond = m.get("condition") or {}
    key = cond.get("key")
    if key:
        inner = data.get("data") or {}
        op = (cond.get("op") or "eq").lower()
        if op == "exists":
            if key not in inner:
                return False
        else:
            val, target = inner.get(key), cond.get("value")
            if op == "ne":
                if str(val) == str(target):
                    return False
            elif str(val) != str(target):  # eq (default)
                return False
    return True
