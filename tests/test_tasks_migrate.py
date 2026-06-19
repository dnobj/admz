"""Tests for the legacy -> unified tasks migration (ADR-0037)."""

from __future__ import annotations

import json
import sqlite3
import time

from admz.tasks.migrate import migrate_legacy
from admz.tasks.store import TRIGGER_DETECTION, TRIGGER_SCHEDULE, TaskStore

_LEGACY_PENDING_SCHEMA = """
CREATE TABLE pending_device_actions (
    id TEXT PRIMARY KEY, device_id TEXT, action_json TEXT, trigger TEXT,
    baseline_bootid TEXT, approved_by TEXT, description TEXT,
    created_at REAL, expires_at REAL, status TEXT, last_error TEXT
);
"""


def _seed_pending(db_path, *, pid, device_id, action, trigger, status="pending"):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_LEGACY_PENDING_SCHEMA)
    except sqlite3.OperationalError:
        pass  # table already exists
    now = time.time()
    conn.execute(
        "INSERT INTO pending_device_actions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (pid, device_id, json.dumps(action), trigger, "", "dnich",
         "recover", now, now + 3600, status, ""),
    )
    conn.commit()
    conn.close()


def _write_schedules(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_migrates_schedules_json(tmp_path):
    db = str(tmp_path / "admz.db")
    sched = tmp_path / "schedules.json"
    _write_schedules(sched, {
        "nightly": {"id": "nightly", "description": "Nightly snap",
                    "interval_seconds": 86400, "tag_filter": "lab",
                    "enabled": True, "job_type": "snapshot"},
        "audit": {"id": "audit", "description": "Drift audit",
                  "interval_seconds": 21600, "enabled": False,
                  "job_type": "drift_audit"},
    })

    summary = migrate_legacy(db_path=db, schedules_path=str(sched))
    assert summary["schedules_migrated"] == 2

    store = TaskStore(db)
    tasks = {t.id: t for t in store.schedule_tasks()}
    assert set(tasks) == {"nightly", "audit"}
    assert tasks["nightly"].action_type == "snapshot"
    assert tasks["nightly"].tag_filter == "lab"
    assert tasks["nightly"].trigger_kind == TRIGGER_SCHEDULE
    assert tasks["audit"].action_type == "drift_audit"
    assert tasks["audit"].enabled is False
    # schedules.json backed up, not deleted
    assert not sched.exists()
    assert (tmp_path / "schedules.json.migrated").exists()
    assert summary["schedules_backup"]


def test_migrates_pending_actions(tmp_path):
    db = str(tmp_path / "admz.db")
    _seed_pending(db, pid="p1", device_id="cam-1",
                  action={"action": "reprovision", "username": "root"},
                  trigger="on_needs_setup")

    summary = migrate_legacy(db_path=db, schedules_path=str(tmp_path / "none.json"))
    assert summary["pending_migrated"] == 1

    store = TaskStore(db)
    detections = store.list(trigger_kind=TRIGGER_DETECTION)
    assert len(detections) == 1
    t = detections[0]
    assert t.id == "p1" and t.device_id == "cam-1"
    assert t.action_type == "reprovision"
    assert t.action_params == {"username": "root"}
    assert t.event == "on_needs_setup"
    assert t.approved_by == "dnich"
    # still claimable by the sweep
    assert len(store.list_active_for("cam-1")) == 1


def test_idempotent(tmp_path):
    db = str(tmp_path / "admz.db")
    sched = tmp_path / "schedules.json"
    _write_schedules(sched, {"s": {"id": "s", "description": "d",
                                   "interval_seconds": 60}})
    _seed_pending(db, pid="p1", device_id="cam-1",
                  action={"action": "reprovision"}, trigger="on_needs_setup")

    first = migrate_legacy(db_path=db, schedules_path=str(sched))
    assert first["schedules_migrated"] == 1 and first["pending_migrated"] == 1

    # second run: schedules.json already backed up (gone), pending already a task
    second = migrate_legacy(db_path=db, schedules_path=str(sched))
    assert second["schedules_migrated"] == 0
    assert second["pending_migrated"] == 0
    assert second["skipped"] >= 1  # the pending row is already a task

    store = TaskStore(db)
    assert len(store.list(trigger_kind=TRIGGER_DETECTION)) == 1  # no dupes
    assert len(store.schedule_tasks()) == 1


def test_no_legacy_data_is_noop(tmp_path):
    db = str(tmp_path / "admz.db")
    summary = migrate_legacy(db_path=db, schedules_path=str(tmp_path / "absent.json"))
    assert summary == {"schedules_migrated": 0, "pending_migrated": 0,
                       "skipped": 0, "schedules_backup": None}
