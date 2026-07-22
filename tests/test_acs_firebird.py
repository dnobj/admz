"""ACS Pro Firebird firing reader + poller (ADR-0041).

The reader copies ACS's embedded ``.FDB`` and runs read-only SELECTs (the live DB
is locked exclusively by ACS). These tests drive the pure logic via the injectable
``Reader`` seam (no real DB) + mock the gating/availability for the poller, so the
suite runs on any host — with or without ACS/Firebird installed.
"""

from __future__ import annotations

import asyncio
import datetime


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ── normalize ────────────────────────────────────────────────────────────────
def test_normalize_firing_maps_to_canonical_store_record():
    from admz.modules.acs_pro.firebird import normalize_firing
    row = {
        "id": 33,
        "timestamp": datetime.datetime(2026, 6, 22, 18, 57, 35, tzinfo=datetime.timezone.utc),
        "rule_id": 7,
        "rule_name": "  External Trigger Example  ",
        "title": "test fired",
        "camera_ids": "Lobby",
        "trigger_type": "ExternalTrigger",
    }
    rec = normalize_firing(row)
    assert rec["id"] == "acsfb-33"          # stable per LOG row → store dedups
    assert rec["source"] == "acs"
    assert rec["type"] == "ACS/ActionRule"
    assert rec["device_id"] == "Lobby" and rec["device_name"] == "Lobby"
    assert rec["data"]["category"] == "action_rule"
    assert rec["data"]["topic"] == "ACS/ActionRule"
    assert rec["data"]["rule_name"] == "External Trigger Example"   # trimmed
    assert rec["data"]["via"] == "firebird"
    assert "External Trigger Example" in rec["summary"]
    assert rec["ts_ms"] > 0                 # tz-aware datetime → epoch ms


def test_normalize_firing_tolerates_missing_fields():
    from admz.modules.acs_pro.firebird import normalize_firing
    rec = normalize_firing({"id": 1})
    assert rec["id"] == "acsfb-1"
    assert rec["data"]["rule_name"] == "ACS action rule"   # fallback name
    assert rec["device_id"] is None
    assert rec["ts_ms"] == 0


# ── rule inventory (injected reader) ─────────────────────────────────────────
def test_list_rules_joins_actions_and_hides_predefined():
    from admz.modules.acs_pro.firebird import CONFIG_DB, list_rules

    def reader(db, sql, params=None):
        assert db == CONFIG_DB
        if sql.startswith("SELECT ID, NAME, IS_ENABLED"):
            # The WHERE clause must exclude the auto per-camera Predefined* rules.
            assert "NOT STARTING WITH 'Predefined'" in sql
            return [
                {"id": 7, "name": "External Trigger Example", "is_enabled": 1},
                {"id": 8, "name": "Night Motion", "is_enabled": 0},
            ]
        if sql.startswith("SELECT RULE_ID, ACTION_TYPE"):
            return [
                {"rule_id": 7, "action_type": 1, "discriminator": "HttpNotificationActionEntity"},
                {"rule_id": 7, "action_type": 2, "discriminator": "RecordActionEntity"},
                {"rule_id": 8, "action_type": 2, "discriminator": "RecordActionEntity"},
            ]
        raise AssertionError("unexpected sql: " + sql)

    rules = list_rules(reader=reader)
    assert [r["name"] for r in rules] == ["External Trigger Example", "Night Motion"]
    r7 = next(r for r in rules if r["id"] == 7)
    assert r7["enabled"] is True
    assert "HttpNotification" in r7["actions"] and "Record" in r7["actions"]
    r8 = next(r for r in rules if r["id"] == 8)
    assert r8["enabled"] is False


def test_max_and_read_new_firings_use_alarm_discriminator():
    from admz.modules.acs_pro.firebird import LOGS_DB, max_firing_id, read_new_firings

    seen = {}

    def reader(db, sql, params=None):
        assert db == LOGS_DB
        seen["sql"] = sql
        seen["params"] = params
        if "MAX(ID)" in sql:
            return [{"max_id": 32}]
        return [{"id": 33, "rule_name": "test"}]

    assert max_firing_id(reader=reader) == 32
    rows = read_new_firings(30, reader=reader)
    assert rows and rows[0]["id"] == 33
    assert "DISCRIMINATOR='AlarmEntity'" in seen["sql"]
    assert "ID > ?" in seen["sql"]
    # system alarms (RULE_ID=0) must be excluded — they're not rule firings (#125)
    assert "RULE_ID <> 0" in seen["sql"]
    assert seen["params"] == [30]
    # reserved words must be quoted to survive the Firebird parser
    assert '"TIMESTAMP"' in seen["sql"]


def test_read_new_firings_excludes_system_alarms():
    """RULE_ID=0 ``AlarmEntity`` rows are ACS *system* alarms (unexpected-server-
    shutdown notices etc., RULE_NAME=NULL) — not action-rule firings. A synthetic
    LOG with both row shapes must yield only the real firing (#125)."""
    from admz.modules.acs_pro.firebird import LOGS_DB, read_new_firings

    log_rows = [
        # system alarm as observed live (171/177 AlarmEntity rows on an unclean start)
        {"id": 40, "discriminator": "AlarmEntity", "rule_id": 0, "rule_name": None,
         "title": "Server was shut down unexpectedly", "camera_ids": None},
        # real named rule firing
        {"id": 41, "discriminator": "AlarmEntity", "rule_id": 18086,
         "rule_name": "External Trigger Example", "title": "test", "camera_ids": "Lobby"},
    ]

    def reader(db, sql, params=None):
        # Evaluate the query's WHERE clauses against the synthetic table the way
        # Firebird would — if the SQL lacked the RULE_ID filter, the system alarm
        # would come back and the assertion below would fail.
        assert db == LOGS_DB
        rows = [r for r in log_rows if r["discriminator"] == "AlarmEntity"]
        rows = [r for r in rows if r["id"] > params[0]]
        if "RULE_ID <> 0" in sql:
            rows = [r for r in rows if r["rule_id"] != 0]
        return sorted(rows, key=lambda r: r["id"])

    rows = read_new_firings(0, reader=reader)
    assert [r["id"] for r in rows] == [41]
    assert rows[0]["rule_name"] == "External Trigger Example"


# ── availability / gating ────────────────────────────────────────────────────
def test_firebird_available_reports_missing_driver(monkeypatch):
    import admz.modules.acs_pro.firebird as fb
    # Simulate "driver not installed" by making the import fail.
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name.startswith("firebird"):
            raise ImportError("no firebird")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, reason = fb.firebird_available()
    assert ok is False and "driver" in reason.lower()


def test_firebird_enabled_env_override(monkeypatch):
    import admz.modules.acs_pro.firebird as fb
    monkeypatch.setenv("ADMZ_ACS_FIREBIRD", "1")
    assert fb.firebird_enabled() is True
    monkeypatch.delenv("ADMZ_ACS_FIREBIRD", raising=False)
    monkeypatch.setattr(fb, "_setting", lambda k: "")
    assert fb.firebird_enabled() is False


# ── poller ───────────────────────────────────────────────────────────────────
class _Store:
    def __init__(self):
        self.rows = []

    def append(self, rec):
        if any(r["id"] == rec["id"] for r in self.rows):
            return False
        self.rows.append(rec)
        return True


def _patch_fb(monkeypatch, *, enabled=True, available=True, firings=None, max_id=0):
    """Stub the firebird module functions the poller imports lazily."""
    import admz.modules.acs_pro.config as acs_cfg
    import admz.modules.acs_pro.firebird as fb

    monkeypatch.setattr(fb, "firebird_enabled", lambda: enabled)
    monkeypatch.setattr(fb, "firebird_available", lambda: (available, "ok" if available else "nope"))
    monkeypatch.setattr(acs_cfg, "acs_enabled", lambda: True)
    monkeypatch.setattr(fb, "max_firing_id", lambda reader=None: max_id)

    def read_new(since_id, reader=None):
        return [r for r in (firings or []) if int(r["id"]) > int(since_id)]

    monkeypatch.setattr(fb, "read_new_firings", read_new)


def test_poll_fires_new_firings_and_advances_high_water(monkeypatch):
    fired = []
    rows = [
        {"id": 31, "rule_name": "old"},
        {"id": 33, "rule_name": "test"},
    ]
    _patch_fb(monkeypatch, firings=rows)
    from admz.events.acs_firebird_ingest import AcsFirebirdPoller

    async def on_event(rec):
        fired.append(rec)

    p = AcsFirebirdPoller(store=_Store(), on_event=on_event)
    p._hw_id = 32                              # 31 is historical, 33 is new
    res = _run(p.poll_once())
    assert res["fired"] == 1
    assert fired and fired[0]["data"]["rule_name"] == "test"
    assert p._hw_id == 33
    assert len(p.store.rows) == 1


def test_second_poll_does_not_refire(monkeypatch):
    fired = []
    rows = [{"id": 33, "rule_name": "test"}]
    _patch_fb(monkeypatch, firings=rows)
    from admz.events.acs_firebird_ingest import AcsFirebirdPoller

    async def on_event(rec):
        fired.append(rec)

    p = AcsFirebirdPoller(store=_Store(), on_event=on_event)
    p._hw_id = 32
    _run(p.poll_once())
    _run(p.poll_once())                        # hw advanced past 33 → no refire
    assert len(fired) == 1
    assert len(p.store.rows) == 1


def test_poll_noop_when_disabled(monkeypatch):
    _patch_fb(monkeypatch, enabled=False, firings=[{"id": 99, "rule_name": "x"}])
    from admz.events.acs_firebird_ingest import AcsFirebirdPoller
    p = AcsFirebirdPoller(store=_Store())
    res = _run(p.poll_once())
    assert res["enabled"] is False and res["fired"] == 0
    assert p.store.rows == []


def test_poll_noop_when_unavailable(monkeypatch):
    _patch_fb(monkeypatch, available=False, firings=[{"id": 99, "rule_name": "x"}])
    from admz.events.acs_firebird_ingest import AcsFirebirdPoller
    p = AcsFirebirdPoller(store=_Store())
    res = _run(p.poll_once())
    assert res["enabled"] is False and res["fired"] == 0


def test_poll_swallows_read_failure(monkeypatch):
    import admz.modules.acs_pro.firebird as fb
    _patch_fb(monkeypatch)

    def boom(since_id, reader=None):
        raise RuntimeError("copy locked")

    monkeypatch.setattr(fb, "read_new_firings", boom)
    from admz.events.acs_firebird_ingest import AcsFirebirdPoller
    p = AcsFirebirdPoller(store=_Store())
    res = _run(p.poll_once())                  # must not raise
    assert res["fired"] == 0 and "error" in res
    assert p.last_error


def test_status_shape(monkeypatch):
    _patch_fb(monkeypatch)
    from admz.events.acs_firebird_ingest import AcsFirebirdPoller
    st = AcsFirebirdPoller(store=_Store()).status()
    for k in ("enabled", "running", "available", "reason", "high_water",
              "last_count", "fired_total", "last_error"):
        assert k in st
