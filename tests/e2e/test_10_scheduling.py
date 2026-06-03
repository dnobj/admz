"""Unified scheduler via chatbot — user-story coverage.

User-story coverage:
  * US-SCHED-001 — operator (via chat) lists what kinds of scheduled
    jobs exist + creates one.
  * US-DM-003 (scheduled config audits) — drift_audit is reachable
    through the same scheduling interface as snapshot.
  * US-SCHED-007 — chatbot can act as the operator interface for
    setting up recurring audits.

Tied to FR-SCH-010 / FR-SCH-011 / FR-SCH-014.

NOTE: these tests don't trigger an actual drift_audit run because
``check_fleet_drift`` probes every device, which is slow on
unreachable ones. The unit tests in tests/test_unified_scheduler.py
exercise the handler dispatch; here we verify the **operator-facing
flow** through the chatbot.
"""

from __future__ import annotations

import httpx


# Use a distinctive prefix so any leftover schedules from a flaky run
# are easy to identify in /api/schedules.
_TEST_SCHEDULE_ID = "e2e-scheduler-test"


def _cleanup_schedule(base_url: str):
    """Idempotently remove a leftover test schedule."""
    try:
        httpx.delete(
            f"{base_url}/api/schedules/{_TEST_SCHEDULE_ID}",
            timeout=10.0,
        )
    except httpx.RequestError:
        pass


def test_chatbot_lists_registered_job_types(chat, cost_recorder):
    """The operator asks 'what kinds of jobs can I schedule?' — the
    LLM should be able to answer via the new /api/schedules/job-types
    REST endpoint (which it doesn't have an MCP tool for directly,
    but it can call the underlying tool catalogue or just have the
    answer in its tool descriptions).

    Verified by asserting the response mentions both registered
    types. Phrasing-tolerant.
    """
    result = chat(
        "What kinds of recurring jobs can ADMZ schedule? List the "
        "available job_types. One short list, no prose."
    )
    cost_recorder(result)
    assert result.success
    # The two registered types as of this PR.
    assert "snapshot" in result.lower
    assert "drift" in result.lower, (
        f"expected 'drift' in the response, got: {result!r}"
    )


def _read_schedules_json():
    """Pre-existing architectural quirk: MCP subprocess and FastAPI
    main process each have their own in-memory SnapshotScheduler
    (both built via build_components()). They share schedules.json
    on disk but don't re-read on every list. So we verify the
    chatbot's create succeeded by reading the file directly —
    which IS the source of truth on disk."""
    import json
    import os
    path = os.path.expanduser("~/.admz/schedules.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def _purge_schedule_from_disk(schedule_id: str):
    """Idempotent disk-level cleanup."""
    import json
    import os
    path = os.path.expanduser("~/.admz/schedules.json")
    if not os.path.exists(path):
        return
    with open(path) as f:
        data = json.load(f)
    if schedule_id in data:
        del data[schedule_id]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


def test_chatbot_creates_drift_audit_schedule(
    chat, cost_recorder, request,
):
    """End-to-end: chatbot creates a drift_audit schedule via the
    MCP create_snapshot_schedule tool. We verify via the on-disk
    schedules.json (the source of truth that both MCP and REST
    write to) — see the dual-scheduler note above.
    """
    _purge_schedule_from_disk(_TEST_SCHEDULE_ID)
    request.addfinalizer(
        lambda: _purge_schedule_from_disk(_TEST_SCHEDULE_ID)
    )

    result = chat(
        f"Create a recurring drift_audit job. Use schedule_id "
        f"'{_TEST_SCHEDULE_ID}', description 'E2E scheduler test', "
        f"interval '24h', and job_type 'drift_audit'. Use the "
        f"create_snapshot_schedule MCP tool — yes I know the legacy "
        f"name, that tool accepts a job_type parameter now. After "
        f"it returns, just confirm in one sentence that the schedule "
        f"was created."
    )
    cost_recorder(result)
    assert result.success
    assert result.contains_any(
        "created", "scheduled", "added", "registered", "set up",
    ), f"expected confirmation in response, got: {result!r}"

    # Verify via the on-disk schedules.json — the canonical source
    # of truth.
    schedules = _read_schedules_json()
    assert _TEST_SCHEDULE_ID in schedules, (
        f"chatbot claimed to create schedule but disk shows nothing: "
        f"{schedules!r}"
    )
    saved = schedules[_TEST_SCHEDULE_ID]
    assert saved.get("job_type") == "drift_audit", (
        f"schedule landed with wrong job_type: {saved!r}"
    )
