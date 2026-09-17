"""ADR-0072 §1 — the discovery scan store: one row per run, bound once to the
conversation that produced it, gone after a day."""

from __future__ import annotations

import pytest

from admz.discovery.scan_store import RETENTION_SECONDS, DiscoveryScanStore

T0 = 1_800_000_000.0

DEVICES = [
    {"device_id": "E82725315CDF", "ip_address": "192.0.2.41", "is_axis": True,
     "registry_info": {"host": "192.0.2.41"}},
    {"device_id": "", "ip_address": "192.0.2.99", "is_axis": False},
]


@pytest.fixture
def store(tmp_path):
    return DiscoveryScanStore(str(tmp_path / "admz.db"))


class TestSave:
    def test_a_scan_round_trips(self, store):
        scan = store.save_scan(principal="alice", devices=DEVICES,
                               subnet="192.0.2.0/24", axis_only=False, now=T0)
        got = store.get_scan(scan.scan_id, now=T0 + 5)
        assert got is not None
        assert (got.principal, got.subnet, got.axis_only) == (
            "alice", "192.0.2.0/24", False)
        assert got.devices == DEVICES
        assert got.conversation_id == ""
        assert got.age_seconds(T0 + 5) == 5

    def test_scan_ids_are_unguessable_and_unique(self, store):
        a = store.save_scan(principal="alice", devices=[], now=T0)
        b = store.save_scan(principal="alice", devices=[], now=T0)
        assert a.scan_id != b.scan_id
        # The console widget and the chat route match on this shape.
        assert len(a.scan_id) >= 20
        assert all(c.isalnum() or c in "-_" for c in a.scan_id)

    def test_a_scan_needs_a_principal(self, store):
        with pytest.raises(ValueError):
            store.save_scan(principal="", devices=[], now=T0)

    def test_an_unknown_scan_is_none(self, store):
        assert store.get_scan("nope") is None
        assert store.get_scan("") is None


class TestRetention:
    def test_a_scan_past_retention_reads_as_gone(self, store):
        scan = store.save_scan(principal="alice", devices=[], now=T0)
        assert store.get_scan(scan.scan_id, now=T0 + RETENTION_SECONDS + 1) is None

    def test_a_later_save_purges_expired_rows(self, store):
        store.save_scan(principal="alice", devices=[], now=T0)
        assert store.count() == 1
        store.save_scan(principal="alice", devices=[],
                        now=T0 + RETENTION_SECONDS + 10_000)
        assert store.count() == 1


class TestBinding:
    def test_the_owner_binds_once(self, store):
        scan = store.save_scan(principal="alice", devices=[], now=T0)
        assert store.bind_conversation(scan.scan_id, "alice", "conv-1") is True
        # A scan belongs to the turn that produced it: a second bind is refused.
        assert store.bind_conversation(scan.scan_id, "alice", "conv-2") is False
        assert store.get_scan(scan.scan_id, now=T0).conversation_id == "conv-1"

    def test_another_principal_cannot_bind(self, store):
        scan = store.save_scan(principal="alice", devices=[], now=T0)
        assert store.bind_conversation(scan.scan_id, "mallory", "conv-x") is False
        assert store.get_scan(scan.scan_id, now=T0).conversation_id == ""

    def test_empty_arguments_bind_nothing(self, store):
        scan = store.save_scan(principal="alice", devices=[], now=T0)
        assert store.bind_conversation(scan.scan_id, "alice", "") is False
        assert store.bind_conversation("", "alice", "conv-1") is False


class TestDefaultPath:
    def test_the_singleton_follows_admz_db_path(self, tmp_path, monkeypatch):
        from admz.discovery.scan_store import discovery_scans

        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "elsewhere.db"))
        scan = discovery_scans.save_scan(principal="alice", devices=[])
        assert (tmp_path / "elsewhere.db").exists()
        assert discovery_scans.get_scan(scan.scan_id) is not None
