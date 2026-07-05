"""SD-card presence mining (health cadence) — extraction, store, probe, roster.

"Is a card inserted?" is answered by disks-list.cgi's per-disk ``status``
attribute (disconnected = empty slot, OK = present and working) — NOT by
root.Storage params, whose Enabled=yes only means the slot is configured.
The health monitor mines it opportunistically on authenticated probes and
the chatbot roster / REST health API surface it.
"""

import asyncio
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import pytest

from admz.device_facts import extract_sd_card
from admz.fleet.health import (
    DeviceHealthRecord,
    DeviceHealthStatus,
    DeviceHealthStore,
    _probe_sd_card,
)


# Shape the executor actually produces for the C1110-E (attrs @-prefixed,
# disk as a list — one SD_DISK + one NetworkShare).
PARSED_TWO_DISKS = {
    "@noNamespaceSchemaLocation": "http://www.axis.com/vapix/http_cgi/disk/list1.xsd",
    "disks": {
        "@numberofdisks": "2",
        "disk": [
            {
                "@diskid": "SD_DISK", "@totalsize": "28922852",
                "@freesize": "27545772", "@status": "OK",
                "@filesystem": "ext4",
            },
            {
                "@diskid": "NetworkShare", "@totalsize": "0",
                "@freesize": "0", "@status": "disconnected",
                "@filesystem": "cifs",
            },
        ],
    },
}


class TestExtractSdCard:
    def test_card_present(self):
        assert extract_sd_card(PARSED_TWO_DISKS) == ("OK", 28922852)

    def test_empty_slot(self):
        parsed = {"disks": {"disk": [
            {"@diskid": "SD_DISK", "@totalsize": "0", "@status": "disconnected"},
        ]}}
        assert extract_sd_card(parsed) == ("disconnected", 0)

    def test_single_disk_as_dict_not_list(self):
        # xmltodict collapses a single child element to a dict.
        parsed = {"disks": {"disk": {
            "@diskid": "SD_DISK", "@totalsize": "1000", "@status": "OK",
        }}}
        assert extract_sd_card(parsed) == ("OK", 1000)

    def test_unprefixed_attribute_keys(self):
        parsed = {"disks": {"disk": [
            {"diskid": "SD_DISK", "totalsize": "512", "status": "failed"},
        ]}}
        assert extract_sd_card(parsed) == ("failed", 512)

    def test_no_sd_slot(self):
        # e.g. a P8815-2: only a NetworkShare entry.
        parsed = {"disks": {"disk": [
            {"@diskid": "NetworkShare", "@totalsize": "0", "@status": "disconnected"},
        ]}}
        assert extract_sd_card(parsed) == ("no_slot", None)

    def test_unrecognized_shape_is_unknown(self):
        assert extract_sd_card(None) == (None, None)
        assert extract_sd_card("not xml") == (None, None)
        assert extract_sd_card({"unrelated": True}) == (None, None)

    def test_garbage_totalsize_still_returns_status(self):
        parsed = {"disks": {"disk": [
            {"@diskid": "SD_DISK", "@totalsize": "n/a", "@status": "OK"},
        ]}}
        assert extract_sd_card(parsed) == ("OK", None)


# ---------------------------------------------------------------------------
# Store round-trip + column migration
# ---------------------------------------------------------------------------


class TestStoreSdFields:
    def test_round_trip(self, tmp_path):
        store = DeviceHealthStore(str(tmp_path / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.ONLINE,
            sd_status="OK", sd_total_kb=28922852,
        ))
        out = store.get("cam-01")
        assert out.sd_status == "OK"
        assert out.sd_total_kb == 28922852
        assert out.to_dict()["sd_status"] == "OK"
        assert out.to_dict()["sd_total_kb"] == 28922852

    def test_migrates_pre_sd_table(self, tmp_path):
        # A database created before the sd columns existed gains them on
        # the next store construction (ALTER TABLE migration).
        db = str(tmp_path / "admz.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE device_health ("
            " device_id TEXT PRIMARY KEY, status TEXT NOT NULL,"
            " last_check REAL, last_seen_online REAL, latency_ms INTEGER,"
            " consecutive_failures INTEGER NOT NULL DEFAULT 0,"
            " last_error TEXT NOT NULL DEFAULT '',"
            " uptime_seconds INTEGER, bootid TEXT)"
        )
        conn.execute(
            "INSERT INTO device_health (device_id, status) VALUES ('old', 'online')"
        )
        conn.commit()
        conn.close()

        store = DeviceHealthStore(db)
        old = store.get("old")
        assert old.sd_status is None  # legacy row: unknown, not blanked-wrong
        store.upsert(DeviceHealthRecord(
            device_id="old", status=DeviceHealthStatus.ONLINE,
            sd_status="disconnected",
        ))
        assert store.get("old").sd_status == "disconnected"


# ---------------------------------------------------------------------------
# The probe helper
# ---------------------------------------------------------------------------


def _catalog_with_op():
    op = MagicMock()
    op.to_executor_dict.return_value = {"id": "disks-list.cgi:list-disks"}
    catalog = MagicMock()
    catalog.get_operation.return_value = op
    return catalog


class TestProbeSdCard:
    def test_success(self):
        result = MagicMock(success=True, parsed_data=PARSED_TWO_DISKS)
        executor = MagicMock(execute=AsyncMock(return_value=result))
        out = asyncio.run(_probe_sd_card(
            catalog=_catalog_with_op(), executor=executor,
            device_info={"host": "h"}, device_id="d",
            credentials={"username": "u", "password": "p"},
            timeout_seconds=5.0,
        ))
        assert out == ("OK", 28922852)
        # probed with diskid=all so slot absence is also observable
        assert executor.execute.await_args.args[3] == {"diskid": "all"}

    def test_op_missing_from_catalog(self):
        catalog = MagicMock()
        catalog.get_operation.return_value = None
        out = asyncio.run(_probe_sd_card(
            catalog=catalog, executor=MagicMock(),
            device_info={}, device_id="d", credentials={},
            timeout_seconds=5.0,
        ))
        assert out == (None, None)

    def test_executor_failure_is_unknown(self):
        executor = MagicMock(execute=AsyncMock(side_effect=RuntimeError("boom")))
        out = asyncio.run(_probe_sd_card(
            catalog=_catalog_with_op(), executor=executor,
            device_info={}, device_id="d", credentials={},
            timeout_seconds=5.0,
        ))
        assert out == (None, None)

    def test_unsuccessful_result_is_unknown(self):
        result = MagicMock(success=False, parsed_data=None)
        executor = MagicMock(execute=AsyncMock(return_value=result))
        out = asyncio.run(_probe_sd_card(
            catalog=_catalog_with_op(), executor=executor,
            device_info={}, device_id="d", credentials={},
            timeout_seconds=5.0,
        ))
        assert out == (None, None)


# ---------------------------------------------------------------------------
# Sweep keeps the last known value when a probe can't tell
# ---------------------------------------------------------------------------


class TestSweepPreservesSd:
    def test_unknown_probe_keeps_previous(self, tmp_path, monkeypatch):
        from admz.fleet import health as h

        store = DeviceHealthStore(str(tmp_path / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.ONLINE,
            sd_status="OK", sd_total_kb=1000,
        ))

        async def _fake_probe(**kwargs):
            return DeviceHealthRecord(
                device_id="cam-01", status=DeviceHealthStatus.ONLINE,
                last_check=1.0, sd_status=None, sd_total_kb=None,
            )

        monkeypatch.setattr(h, "probe_device", _fake_probe)
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "cam-01", "host": "h"}]
        registry.get_credentials.return_value = None
        monitor = h.HealthMonitor(registry=registry, store=store)
        asyncio.run(monitor.sweep_once())

        out = store.get("cam-01")
        assert out.sd_status == "OK"
        assert out.sd_total_kb == 1000

    def test_fresh_value_overwrites(self, tmp_path, monkeypatch):
        from admz.fleet import health as h

        store = DeviceHealthStore(str(tmp_path / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.ONLINE,
            sd_status="OK", sd_total_kb=1000,
        ))

        async def _fake_probe(**kwargs):
            return DeviceHealthRecord(
                device_id="cam-01", status=DeviceHealthStatus.ONLINE,
                last_check=1.0, sd_status="disconnected", sd_total_kb=0,
            )

        monkeypatch.setattr(h, "probe_device", _fake_probe)
        registry = MagicMock()
        registry.list_devices.return_value = [{"device_id": "cam-01", "host": "h"}]
        registry.get_credentials.return_value = None
        monitor = h.HealthMonitor(registry=registry, store=store)
        asyncio.run(monitor.sweep_once())

        assert store.get("cam-01").sd_status == "disconnected"


# ---------------------------------------------------------------------------
# Roster label
# ---------------------------------------------------------------------------


class TestRosterSdLabel:
    def _rec(self, **kw):
        from types import SimpleNamespace

        return SimpleNamespace(
            status=SimpleNamespace(value="online"),
            sd_status=kw.get("sd_status"),
            sd_total_kb=kw.get("sd_total_kb"),
        )

    def test_labels(self):
        from admz.chatbot.context import _sd_label

        assert _sd_label(self._rec()) == ""
        assert _sd_label(self._rec(sd_status="no_slot")) == "sd: no slot"
        assert _sd_label(self._rec(sd_status="disconnected")) == "sd: none"
        assert _sd_label(
            self._rec(sd_status="OK", sd_total_kb=28922852)
        ) == "sd: inserted 28GB OK"
        assert _sd_label(
            self._rec(sd_status="failed", sd_total_kb=None)
        ) == "sd: inserted (failed)"

    def test_roster_line_includes_sd(self, monkeypatch):
        from admz.chatbot import context as ctx

        monkeypatch.setattr(
            ctx, "_health_by_id",
            lambda: {"CAM1": self._rec(sd_status="OK", sd_total_kb=28922852)},
        )
        monkeypatch.setattr(ctx, "_drift_label", lambda d: "")

        class _Reg:
            def list_devices(self):
                return [{"device_id": "CAM1", "model": "C1110-E", "host": "h"}]

        out = ctx.build_device_roster(_Reg())
        assert "sd: inserted 28GB OK" in out
        assert "online" in out
