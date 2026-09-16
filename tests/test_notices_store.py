"""ADR-0071 §1 — the notices store: one live row per subject, a clock-driven
sweep, and nothing but identifiers and counts in a row."""

from __future__ import annotations

import sqlite3

import pytest

from admz.notices import store as store_module
from admz.notices.store import (
    EXPIRE_OPEN_AFTER_SECONDS,
    PURGE_CLOSED_AFTER_SECONDS,
    NoticeStore,
)

T0 = 1_800_000_000.0


@pytest.fixture
def store(tmp_path):
    return NoticeStore(str(tmp_path / "admz.db"))


def _drift(store, device_id="cam-1", now=T0, **kw):
    return store.raise_notice(
        kind="drift", subject_key=f"drift:{device_id}", device_id=device_id,
        title=f"Configuration drift on {device_id}", summary={"fields": 4},
        severity="low", source="drift_audit", task_id="sched-1", now=now, **kw)


class TestRaise:
    def test_a_new_subject_opens_a_row(self, store):
        n = _drift(store)
        assert n.id >= 1
        assert (n.status, n.occurrences) == ("open", 1)
        assert n.created_at == n.updated_at == T0
        assert n.summary == {"fields": 4}
        assert (n.source, n.task_id, n.severity) == ("drift_audit", "sched-1", "low")

    def test_a_second_raise_updates_the_same_row(self, store):
        first = _drift(store)
        again = store.raise_notice(
            kind="drift", subject_key="drift:cam-1", device_id="cam-1",
            summary={"fields": 7}, severity="high", source="check_drift",
            now=T0 + 60)
        assert again.id == first.id
        assert again.occurrences == 2
        assert again.created_at == T0          # first seen stays true
        assert again.updated_at == T0 + 60
        assert again.summary == {"fields": 7}
        assert (again.severity, again.source) == ("high", "check_drift")
        assert len(store.list(status=None)) == 1

    def test_a_raise_wakes_a_snoozed_row(self, store):
        n = _drift(store)
        store.snooze(n.id, until=T0 + 86400)
        woken = _drift(store, now=T0 + 10)
        assert woken.id == n.id
        assert woken.status == "open"
        assert woken.snoozed_until is None

    def test_a_closed_subject_opens_a_new_row(self, store):
        first = _drift(store)
        store.resolve("drift:cam-1", "cleared", by="drift_audit", now=T0 + 5)
        second = _drift(store, now=T0 + 10)
        assert second.id != first.id
        assert second.occurrences == 1
        assert store.get(first.id).status == "handled"

    def test_the_index_allows_one_live_row_per_subject(self, store, tmp_path):
        """The invariant lives in the schema, not only in raise_notice."""
        _drift(store)
        conn = sqlite3.connect(str(tmp_path / "admz.db"))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO notices (kind, subject_key, status, created_at, "
                    "updated_at) VALUES ('drift', 'drift:cam-1', 'snoozed', 1, 1)")
            # A closed row for the same subject is fine.
            conn.execute(
                "INSERT INTO notices (kind, subject_key, status, created_at, "
                "updated_at) VALUES ('drift', 'drift:cam-1', 'handled', 1, 1)")
        finally:
            conn.close()

    @pytest.mark.parametrize("kw", [
        {"kind": "task"},
        {"severity": "urgent"},
        {"subject_key": ""},
    ])
    def test_bad_input_is_refused(self, store, kw):
        args = {"kind": "drift", "subject_key": "drift:x", "severity": "low", **kw}
        with pytest.raises(ValueError):
            store.raise_notice(**args)


class TestClose:
    def test_resolve_closes_the_live_row(self, store):
        n = _drift(store)
        closed = store.resolve("drift:cam-1", "accepted", by="HOMELAB\\alice",
                               now=T0 + 3)
        assert closed.id == n.id
        assert (closed.status, closed.resolution, closed.handled_by) == (
            "handled", "accepted", "HOMELAB\\alice")
        assert closed.handled_at == T0 + 3
        assert store.resolve("drift:cam-1", "cleared") is None

    def test_resolve_closes_a_snoozed_row_too(self, store):
        n = _drift(store)
        store.snooze(n.id, until=T0 + 100)
        assert store.resolve("drift:cam-1", "cleared").status == "handled"

    def test_handle_is_by_id_and_only_once(self, store):
        n = _drift(store)
        assert store.handle(n.id, "dismissed", by="anonymous").resolution == "dismissed"
        assert store.handle(n.id, "dismissed") is None
        assert store.handle(9999, "dismissed") is None

    def test_snooze_only_a_live_row(self, store):
        n = _drift(store)
        snoozed = store.snooze(n.id, until=T0 + 3600)
        assert (snoozed.status, snoozed.snoozed_until) == ("snoozed", T0 + 3600)
        assert snoozed.updated_at == T0        # not new information
        store.handle(n.id, "dismissed")
        assert store.snooze(n.id, until=T0 + 7200) is None
        assert store.snooze(9999, until=T0) is None

    def test_mark_reviewed(self, store):
        n = _drift(store)
        store.mark_reviewed(n.id, "conv-1", now=T0 + 9)
        got = store.get(n.id)
        assert (got.review_conversation_id, got.reviewed_at) == ("conv-1", T0 + 9)
        assert got.status == "open"


class TestSweep:
    def test_a_due_snooze_wakes(self, store):
        n = _drift(store)
        store.snooze(n.id, until=T0 + 100)
        assert store.sweep(now=T0 + 99)["woken"] == 0
        assert store.get(n.id).status == "snoozed"
        assert store.sweep(now=T0 + 100)["woken"] == 1
        assert store.get(n.id).status == "open"

    def test_an_idle_open_row_expires_after_thirty_days(self, store):
        n = _drift(store)
        assert store.sweep(now=T0 + EXPIRE_OPEN_AFTER_SECONDS)["expired"] == 0
        assert store.sweep(now=T0 + EXPIRE_OPEN_AFTER_SECONDS + 1)["expired"] == 1
        got = store.get(n.id)
        assert (got.status, got.resolution) == ("expired", "expired")
        # An expired subject raises afresh.
        assert _drift(store, now=T0 + EXPIRE_OPEN_AFTER_SECONDS + 2).id != n.id

    def test_closed_rows_are_purged_after_ninety_days(self, store):
        n = _drift(store)
        store.resolve("drift:cam-1", "cleared", now=T0)
        assert store.sweep(now=T0 + PURGE_CLOSED_AFTER_SECONDS)["purged"] == 0
        assert store.sweep(now=T0 + PURGE_CLOSED_AFTER_SECONDS + 1)["purged"] == 1
        assert store.get(n.id) is None
        assert store.has_any("drift:cam-1") is False

    def test_reads_sweep_at_most_once_a_minute(self, store, monkeypatch):
        calls = []
        monkeypatch.setattr(store, "sweep", lambda now=None: calls.append(now))
        store.list()
        store.count_open()
        assert len(calls) == 1


class TestRead:
    def test_list_filters_and_orders(self, store):
        a = _drift(store, "cam-a", now=T0)
        b = _drift(store, "cam-b", now=T0 + 10)
        e = store.raise_notice(kind="event", subject_key="event:det-1:cam-a",
                               device_id="cam-a", title="Door", now=T0 + 20)
        store.snooze(b.id, until=T0 + 10 ** 9)
        assert [n.id for n in store.list()] == [e.id, a.id]
        assert [n.id for n in store.list(status="live")] == [e.id, b.id, a.id]
        assert [n.id for n in store.list(status="snoozed")] == [b.id]
        assert [n.id for n in store.list(kind="drift", status="live")] == [b.id, a.id]
        assert [n.id for n in store.list(device_id="cam-a")] == [e.id, a.id]
        assert [n.id for n in store.list(limit=1)] == [e.id]
        assert store.count_open() == 2

    def test_get_live_and_has_any(self, store):
        assert store.get_live("drift:cam-1") is None
        assert store.has_any("drift:cam-1") is False
        n = _drift(store)
        assert store.get_live("drift:cam-1").id == n.id
        store.handle(n.id, "dismissed")
        assert store.get_live("drift:cam-1") is None
        assert store.has_any("drift:cam-1") is True


class TestSingleton:
    def test_construction_touches_nothing(self, tmp_path):
        target = tmp_path / "nested" / "admz.db"
        NoticeStore(str(target))
        assert not target.parent.exists()

    def test_the_singleton_resolves_its_path_at_call_time(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "late.db"))
        assert store_module.notices_store._db_path == str(tmp_path / "late.db")
        store_module.notices_store.count_open()
        assert (tmp_path / "late.db").exists()
