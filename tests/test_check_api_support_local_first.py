"""ADR-0063 S3 (#453) — check_api_support answers the local row first, passes
firmware correctly, and never falls back to a partial snapshot.

The defect chain this closes (D2 in the ADR): ADMZ stores the observed
firmware as ``firmware_version``; the atlas resolver reads ``firmware``. So
every lookup passed ``firmware=None`` and silently took the latest-snapshot
fallback — whose tie-break prefers partial captures, producing confident
``supported=false`` for APIs the device has.
"""

import asyncio
import time
from types import SimpleNamespace

import pytest


class FakeRegistry:
    def __init__(self, devices):
        self.devices = devices

    def get_device_info(self, device_id):
        return dict(self.devices.get(device_id, {}))

    def device_exists(self, device_id):
        return device_id in self.devices


class RecordingResolver:
    """Stands in for the atlas resolver; records exactly what it was asked."""

    def __init__(self, result=None):
        self.calls = []
        self.result = result or SimpleNamespace(
            device_id="cam-01", model="AXIS Q1656", firmware="12.10.68",
            snapshot=None, supported=None, api_version=None, notes=[],
        )

    def check_api_support(self, *, device_id, catalog_api_id, device_info):
        self.calls.append(("check", device_id, catalog_api_id, dict(device_info)))
        return self.result

    def get_all_apis(self, *, device_id, device_info):
        self.calls.append(("all", device_id, None, dict(device_info)))
        return self.result


def _server(registry, resolver):
    from admz.mcp.server import ADMZMCPServer

    server = SimpleNamespace(
        registry=registry, capabilities_resolver=resolver,
    )
    server._check_api_support = ADMZMCPServer._check_api_support.__get__(server)
    return server


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))


class TestLocalRowAnswersFirst:
    def test_absent_row_answers_without_touching_the_atlas(self, isolated_db):
        from admz.device_capabilities import ABSENT, capability_store

        registry = FakeRegistry({"sw-01": {
            "model": "AXIS T8516", "firmware_version": "6.54.3942",
        }})
        capability_store.record(
            "sw-01", "sip", ABSENT, firmware="6.54.3942",
            reason="HTTP 404", now=time.time(),
        )
        resolver = RecordingResolver()
        out = asyncio.run(_server(registry, resolver)._check_api_support("sw-01", "sip"))

        assert out["supported"] is False
        assert out["source"] == "probe"
        assert out["match"] == "local"
        assert out["classification"] == "absent"
        assert resolver.calls == [], "the atlas must not be consulted"

    def test_present_row_beats_the_atlas(self, isolated_db):
        from admz.device_capabilities import PRESENT, capability_store

        registry = FakeRegistry({"cam-01": {
            "model": "AXIS Q1656", "firmware_version": "12.10.68",
        }})
        capability_store.record(
            "cam-01", "sip", PRESENT, firmware="12.10.68", now=time.time(),
        )
        resolver = RecordingResolver()
        out = asyncio.run(_server(registry, resolver)._check_api_support("cam-01", "sip"))
        assert out["supported"] is True
        assert out["source"] == "probe"
        assert resolver.calls == []

    def test_unconfirmed_row_is_null_not_false(self, isolated_db):
        """The ADR's honesty rule at the resolver surface: 'could not verify'
        must never read as 'the device lacks it'."""
        from admz.device_capabilities import ABSENT_UNCONFIRMED, capability_store

        registry = FakeRegistry({"sw-01": {
            "model": "AXIS T8516", "firmware_version": "6.54.3942",
        }})
        capability_store.record(
            "sw-01", "ntp", ABSENT_UNCONFIRMED, firmware="6.54.3942",
            reason="Transport error", now=time.time(),
        )
        resolver = RecordingResolver()
        out = asyncio.run(_server(registry, resolver)._check_api_support("sw-01", "ntp"))
        assert out["supported"] is None
        assert out["classification"] == "absent_unconfirmed"
        assert any("could not verify" in n for n in out["notes"])
        assert resolver.calls == []

    def test_stale_row_is_skipped_with_a_note_and_atlas_consulted(
        self, isolated_db
    ):
        from admz.device_capabilities import ABSENT, capability_store

        registry = FakeRegistry({"cam-01": {
            "model": "AXIS Q1656", "firmware_version": "12.10.68",
        }})
        # Row recorded under OLD firmware → stale at the current one.
        capability_store.record(
            "cam-01", "sip", ABSENT, firmware="11.11.0", now=time.time(),
        )
        resolver = RecordingResolver()
        out = asyncio.run(_server(registry, resolver)._check_api_support("cam-01", "sip"))
        assert len(resolver.calls) == 1
        assert any("stale local row" in n for n in out["notes"])


class TestFirmwarePassedCorrectly:
    def test_the_d2_fix_assert_the_call(self, isolated_db):
        """The issue's verification line, verbatim: a device with no local
        row and firmware 12.10.68 is looked up with firmware='12.10.68'."""
        registry = FakeRegistry({"cam-01": {
            "model": "AXIS Q1656", "firmware_version": "12.10.68",
        }})
        resolver = RecordingResolver()
        asyncio.run(_server(registry, resolver)._check_api_support("cam-01", "sip"))
        (_kind, _did, _api, passed_info) = resolver.calls[0]
        assert passed_info["firmware"] == "12.10.68"

    def test_no_snapshot_at_that_firmware_is_null_match_none(self, isolated_db):
        """The control the old code fails: a non-matching firmware yields
        supported=null and match='none' — never a confident false from a
        fallback to another snapshot."""
        registry = FakeRegistry({"cam-01": {
            "model": "AXIS Q1656", "firmware_version": "12.10.68",
        }})
        resolver = RecordingResolver(result=SimpleNamespace(
            device_id="cam-01", model="AXIS Q1656", firmware="12.10.68",
            snapshot=None, supported=None, api_version=None,
            notes=["No snapshot for firmware '12.10.68'."],
        ))
        out = asyncio.run(_server(registry, resolver)._check_api_support("cam-01", "sip"))
        assert out["supported"] is None
        assert out["match"] == "none"
        assert out["source"] == "none"

    def test_unknown_firmware_says_so_and_skips_the_atlas(self, isolated_db):
        registry = FakeRegistry({"cam-01": {"model": "AXIS Q1656"}})
        resolver = RecordingResolver()
        out = asyncio.run(_server(registry, resolver)._check_api_support("cam-01", "sip"))
        assert out["supported"] is None
        assert out["match"] == "none"
        assert resolver.calls == [], (
            "empty firmware must not reach the resolver — that is the "
            "latest-snapshot fallback path"
        )
        assert any("firmware is unknown" in n.lower() for n in out["notes"])

    def test_exact_match_is_labelled(self, isolated_db):
        snap = SimpleNamespace(firmware="12.10.68", discovered="2026-02-19",
                               api_count=95, apis={"sip": "2.2"})
        registry = FakeRegistry({"cam-01": {
            "model": "AXIS Q1656", "firmware_version": "12.10.68",
        }})
        resolver = RecordingResolver(result=SimpleNamespace(
            device_id="cam-01", model="AXIS Q1656", firmware="12.10.68",
            snapshot=snap, supported=True, api_version="2.2", notes=[],
        ))
        out = asyncio.run(_server(registry, resolver)._check_api_support("cam-01", "sip"))
        assert out["supported"] is True
        assert out["match"] == "exact"
        assert out["source"] == "atlas"

    def test_unknown_firmware_full_snapshot_still_carries_local_rows(
        self, isolated_db
    ):
        """#457 review, MAJOR-1: the unknown-firmware early return withheld
        the device's own rows — exactly when they are the only data anyone
        has. Rows recorded under firmware "" are non-stale for a firmware-less
        device and must ride the full-snapshot answer."""
        from admz.device_capabilities import PRESENT, capability_store

        registry = FakeRegistry({"cam-01": {"model": "AXIS Q1656"}})  # no fw
        capability_store.record(
            "cam-01", "sip", PRESENT, firmware="", now=time.time(),
        )
        resolver = RecordingResolver()
        out = asyncio.run(_server(registry, resolver)._check_api_support("cam-01", None))
        assert resolver.calls == []
        keys = {r["probe_key"] for r in out.get("local_capabilities", [])}
        assert "sip" in keys

    def test_device_reported_id_is_normalized_for_the_local_lookup(
        self, isolated_db, monkeypatch
    ):
        """#457 review, MINOR-2: local rows are keyed by CATALOG api id, but
        a caller may echo a device-reported id it read out of a snapshot
        ('fwmgr'). Without normalization local-first is silently skipped for
        exactly the vocabulary the tool's own output teaches."""
        from admz.device_capabilities import PRESENT, capability_store

        registry = FakeRegistry({"cam-01": {
            "model": "AXIS Q1656", "firmware_version": "12.10.68",
        }})
        capability_store.record(
            "cam-01", "firmware-manager", PRESENT, firmware="12.10.68",
            now=time.time(),
        )
        resolver = RecordingResolver()
        server = _server(registry, resolver)
        server.capabilities_loader = SimpleNamespace(
            device_id_to_catalog_api_id=lambda i: {
                "fwmgr": "firmware-manager"
            }.get(i, i),
        )
        out = asyncio.run(server._check_api_support("cam-01", "fwmgr"))
        assert out["supported"] is True
        assert out["match"] == "local"
        assert resolver.calls == [], (
            "the device-reported alias must hit the local row, not the atlas"
        )

    def test_serialized_rows_carry_the_tristate(self, isolated_db):
        """#457 review, MINOR-4: an absent_unconfirmed row STORES supported=0
        (never trusted as present) but serializes supported=null — rendering
        it false says 'the device lacks it', the conflation both reviews
        flagged."""
        from admz.device_capabilities import (
            ABSENT,
            ABSENT_UNCONFIRMED,
            PRESENT,
            capability_store,
        )

        now = time.time()
        capability_store.record("d1", "a", PRESENT, firmware="1.0", now=now)
        capability_store.record("d1", "b", ABSENT, firmware="1.0", now=now)
        capability_store.record(
            "d1", "c", ABSENT_UNCONFIRMED, firmware="1.0", now=now
        )
        by_key = {r.probe_key: r.to_dict() for r in capability_store.list("d1")}
        assert by_key["a"]["supported"] is True
        assert by_key["b"]["supported"] is False
        assert by_key["c"]["supported"] is None
        # Selection semantics unchanged: the dataclass attr stays False.
        assert all(not r.supported for r in capability_store.list("d1")
                   if r.probe_key == "c")

    def test_full_snapshot_carries_local_capabilities(self, isolated_db):
        from admz.device_capabilities import PRESENT, capability_store

        snap = SimpleNamespace(firmware="12.10.68", discovered="2026-02-19",
                               api_count=95, apis={"sip": "2.2"})
        registry = FakeRegistry({"cam-01": {
            "model": "AXIS Q1656", "firmware_version": "12.10.68",
        }})
        capability_store.record(
            "cam-01", "ntp", PRESENT, firmware="12.10.68", now=time.time(),
        )
        resolver = RecordingResolver(result=SimpleNamespace(
            device_id="cam-01", model="AXIS Q1656", firmware="12.10.68",
            snapshot=snap, supported=None, api_version=None, notes=[],
        ))
        out = asyncio.run(_server(registry, resolver)._check_api_support("cam-01", None))
        keys = {r["probe_key"] for r in out.get("local_capabilities", [])}
        assert "ntp" in keys
