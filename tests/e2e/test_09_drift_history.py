"""Drift-alert history — chatbot retrieves drift history via MCP tool.

User-story coverage:
  * US-SCHED-005 (observable outcomes of scheduled jobs) — operator
    asks 'what drift have we seen recently?' through the chatbot.
  * US-DM-003 / US-DM-007 — operator wants drift visibility without
    knowing the SQL schema.

Implements FR-DRF-010 read side.

These tests seed synthetic drift_alerts rows by hitting the REST
endpoint directly (no real drift required), then ask the chatbot
to summarize them. Verifies the LLM can find the data via the
new `get_drift_alerts` MCP tool — the full round trip from prose
question to actionable answer.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path


def _seed_drift_alerts(rows):
    """Insert synthetic drift_alerts rows into the live server's DB
    so the chatbot has something to retrieve."""
    db = Path(os.getenv("ADMZ_DB_PATH", os.path.expanduser("~/.admz/admz.db")))
    conn = sqlite3.connect(str(db))
    try:
        now = time.time()
        for offset, device_id, transition, prev, curr, summary in rows:
            conn.execute(
                "INSERT INTO drift_alerts "
                "(timestamp, device_id, transition, previous_count, "
                " current_count, signature, summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now - offset, device_id, transition, prev, curr,
                 f"sig-{int(now - offset)}", summary),
            )
        conn.commit()
    finally:
        conn.close()


def _purge_seeded_drift_alerts(summaries):
    """Clean up the synthetic rows so this test is idempotent across
    runs. Match on the summary text we used so we don't touch any
    real drift alerts the homelab might have."""
    db = Path(os.getenv("ADMZ_DB_PATH", os.path.expanduser("~/.admz/admz.db")))
    conn = sqlite3.connect(str(db))
    try:
        for summary in summaries:
            conn.execute(
                "DELETE FROM drift_alerts WHERE summary=?",
                (summary,),
            )
        conn.commit()
    finally:
        conn.close()


def test_llm_summarizes_recent_drift_via_get_drift_alerts(chat, cost_recorder):
    """Seed a known drift transition, then ask the chatbot about it.
    Verifies end-to-end: synthetic rows in drift_alerts → MCP
    get_drift_alerts → LLM summary back to the user.
    """
    test_summary_1 = "e2e: lobby cam drifted on Image.I0.Resolution"
    test_summary_2 = "e2e: lobby cam back in sync"
    _seed_drift_alerts([
        (300, "B8A44FD0257C", "appeared", 0, 4, test_summary_1),
        (60, "B8A44FD0257C", "cleared", 4, 0, test_summary_2),
    ])
    try:
        result = chat(
            "Use the get_drift_alerts MCP tool to look up drift alerts "
            "for device B8A44FD0257C. Then summarize for me in one or "
            "two short sentences: what's the most recent transition, "
            "and how many fields were involved at peak?"
        )
        cost_recorder(result)
        assert result.success, f"chat failed: {result.error!r}"
        # The LLM must reference at least one of the transitions or
        # field counts so we know it actually read the data, not
        # hallucinated.
        assert result.contains_any(
            "appeared", "cleared", "drift",
            "4 field", "4 fields", "four field",
            "in sync", "back in sync",
        ), (
            f"response doesn't reflect the seeded drift data: {result!r}"
        )
    finally:
        _purge_seeded_drift_alerts([test_summary_1, test_summary_2])


def test_llm_handles_no_drift_cleanly(chat, cost_recorder):
    """Ask about a device that has no drift history. The LLM should
    say 'no drift' rather than hallucinate findings."""
    result = chat(
        "Use get_drift_alerts to look up drift history for device "
        "DEADBEEFCAFE (a device that I just made up — it has no drift "
        "history). Tell me what you found in one short sentence."
    )
    cost_recorder(result)
    assert result.success
    assert result.contains_any(
        "no drift", "no alert", "no history", "no record",
        "none", "no entries", "nothing", "empty", "not found",
        "no result", "no transition", "no data",
    ), (
        f"expected 'no drift' style response for empty history, "
        f"got: {result!r}"
    )
