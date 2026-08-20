"""ADR-0063 — capability knowledge is local-first (S1, #451).

The scenario every test here is built around is the one the ADR was written
for: the hourly drift audit probed ``sip:getSIPAccounts`` on a T8516 PoE
switch and logged an ERROR traceback — then did it again an hour later, and
every hour since. A switch has no SIP. Nothing asked.

The fixture is deliberately the *real* stack below the network: the real
``VapixExecutor`` over an ``httpx.MockTransport``, the real atlas catalog, the
real ``SnapshotEngine`` and ``DriftDetector``. Only the wire is faked, and the
wire behaves exactly as the T8516 does: ``param.cgi`` answers; every other
endpoint drops the connection (``httpx.RemoteProtocolError`` — a *transport*
error, not a clean 404). That detail is the whole reason the ADR's
classification table has a third row: a rule of "transport → no record" would
never learn this device while every test stayed green.
"""

import logging
import time
import subprocess

import httpx
import pytest

import axis_api_atlas
from axis_api_atlas.catalog.loader import CatalogLoader

from admz.executor.vapix import VapixExecutor
from admz.snapshot.drift import DriftDetector
from admz.snapshot.engine import SnapshotEngine
from admz.snapshot.git_repo import GitRepo


# ---------------------------------------------------------------------------
# The wire
# ---------------------------------------------------------------------------

SWITCH_ID = "switch-01"
SWITCH_FW = "1.20.3"

# A param.cgi dump as the switch returns it: Brand, a firmware line (VOLATILE
# — dropped from the parsed params, which is exactly why the engine must lift
# it *before* parsing), and some Network keys so the ``network`` facet has
# something to say.
SWITCH_DUMP = (
    "root.Brand.Brand=AXIS\n"
    "root.Brand.ProdNbr=T8516\n"
    f"root.Properties.Firmware.Version={SWITCH_FW}\n"
    "root.Network.HostName=axis-t8516\n"
    "root.Network.eth0.MACAddress=B8:A4:4F:00:00:16\n"
)


class Wire:
    """Records every request; answers like a T8516.

    ``param.cgi`` → 200 with the dump. Anything else → the connection drops
    mid-handshake, which httpx surfaces as ``RemoteProtocolError``. The list
    of (method, path) pairs is the evidence the tests reason over.
    """

    def __init__(self, dump=SWITCH_DUMP, param_ok=True):
        self.dump = dump
        self.param_ok = param_ok
        self.calls = []

    def __call__(self, request):
        self.calls.append((request.method, request.url.path))
        if "param.cgi" in request.url.path:
            if self.param_ok:
                return httpx.Response(200, text=self.dump)
            raise httpx.RemoteProtocolError(
                "Server disconnected without sending a response.",
                request=request,
            )
        raise httpx.RemoteProtocolError(
            "Server disconnected without sending a response.", request=request
        )

    def non_param_calls(self):
        return [c for c in self.calls if "param.cgi" not in c[1]]

    def reset(self):
        self.calls = []


# ---------------------------------------------------------------------------
# Fixtures — real catalog, real executor, real engine, real git
# ---------------------------------------------------------------------------

class FakeRegistry:
    def __init__(self, devices):
        self.devices = devices
        self.updates = []

    def get_device_info(self, device_id):
        return dict(self.devices.get(device_id, {}))

    def device_exists(self, device_id):
        return device_id in self.devices

    def list_devices(self):
        return [{**info, "device_id": did} for did, info in self.devices.items()]

    def get_credentials(self, device_id, account_id="default", requester=None):
        return {"username": "x", "password": "y"}

    def set_config_pointers(self, device_id, **kwargs):
        pass

    def update_device_info(self, device_id, updates):
        self.updates.append((device_id, dict(updates)))
        self.devices.setdefault(device_id, {}).update(updates)


@pytest.fixture(scope="module")
def catalog():
    return CatalogLoader(axis_api_atlas.default_data_path())


@pytest.fixture
def tmp_repo(tmp_path):
    repo_path = str(tmp_path / "config-repo")
    repo = GitRepo(repo_path)
    for key, val in [
        ("user.email", "test@test.com"),
        ("user.name", "Test"),
        ("commit.gpgsign", "false"),
    ]:
        subprocess.run(["git", "config", key, val], cwd=repo_path, check=True)
    return repo


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Every store resolves its path at call time (#258); point them all at a
    throwaway file so capability rows cannot leak between tests."""
    path = tmp_path / "admz.db"
    monkeypatch.setenv("ADMZ_DB_PATH", str(path))
    return path


def _switch_registry(**extra):
    return FakeRegistry({
        SWITCH_ID: {
            "host": "192.0.2.16", "api_family": "vapix",
            "model": "AXIS T8516 PoE+ Network Switch", **extra,
        }
    })


def _engine(catalog, registry, wire, git_repo):
    executor = VapixExecutor(
        timeout=2.0, retries=0, transport=httpx.MockTransport(wire)
    )
    return SnapshotEngine(
        catalog=catalog, registry=registry,
        executors={"vapix": executor}, git_repo=git_repo,
    )


# ---------------------------------------------------------------------------
# The claim the whole slice is built on
# ---------------------------------------------------------------------------

class TestTheSwitchIsLearnedAfterOneAudit:
    """The first row of the plan's verification matrix — written before the
    classifier existed, and it failed first."""

    @pytest.mark.asyncio
    async def test_second_audit_issues_no_requests_to_apis_the_switch_refused(
        self, catalog, tmp_repo, isolated_db
    ):
        wire = Wire()
        registry = _switch_registry()
        engine = _engine(catalog, registry, wire, tmp_repo)
        detector = DriftDetector(engine, tmp_repo)

        # Cycle 1: nothing is known, so every API-backed facet probes — and
        # every probe except param.cgi drops the connection. That is the
        # learning.
        await detector.check_drift(SWITCH_ID)
        probed = {path for _m, path in wire.non_param_calls()}
        assert "/vapix/call" in probed, "control: the wire must have been probed"
        assert "/axis-cgi/ntp.cgi" in probed

        # Cycle 2: the audit consults what it learned. Zero requests to the
        # APIs the switch refused — and no new traffic of any kind beyond the
        # param.cgi reads the audit always makes.
        wire.reset()
        report = await detector.check_drift(SWITCH_ID)
        assert wire.non_param_calls() == [], (
            "the second audit re-probed APIs the device demonstrably lacks: "
            f"{wire.non_param_calls()}"
        )
        assert wire.calls, "control: param.cgi was still read"

        # And the report says so honestly rather than recording success.
        assert report.facet_status["sip"] == "skipped"
        assert report.facet_status["ntp"] == "skipped"
        assert report.facet_status["applications"] == "skipped"
        assert report.facet_status["network"] == "ok"

    @pytest.mark.asyncio
    async def test_unreadable_device_teaches_nothing(
        self, catalog, tmp_repo, isolated_db
    ):
        """The same-cycle readability control. When even param.cgi drops the
        connection, the device is not readable — every failure is
        indeterminate, no rows are written, and the NEXT audit probes
        everything again. Remove the control and this test fails: the
        outage would be recorded as 'the device lacks every API'.

        Driven through ``snapshot_device`` deliberately: ``check_drift`` has
        its own readability pre-gate and returns before the learner runs, so
        a drift-path version of this test passes with the control deleted —
        the first run of the mutation checks proved exactly that."""
        from admz.device_capabilities import capability_store

        wire = Wire(param_ok=False)
        registry = _switch_registry()
        engine = _engine(catalog, registry, wire, tmp_repo)

        await engine.snapshot_device(SWITCH_ID)
        assert wire.non_param_calls(), (
            "control: the extra reads were attempted during the outage"
        )
        assert capability_store.list(SWITCH_ID) == [], (
            "an outage must not be recorded as absence"
        )

        # Recovery: the device comes back; the next audit probes everything.
        wire2 = Wire()
        engine2 = _engine(catalog, registry, wire2, tmp_repo)
        await DriftDetector(engine2, tmp_repo).check_drift(SWITCH_ID)
        assert wire2.non_param_calls(), "recovered device must be probed"

    @pytest.mark.asyncio
    async def test_absent_unconfirmed_expires_and_reprobes(
        self, catalog, tmp_repo, isolated_db, monkeypatch
    ):
        """A transport-refusal row is a lease, not a verdict: once it expires
        the audit probes again (an API enabled later must be noticed)."""
        import admz.device_capabilities as dc

        wire = Wire()
        registry = _switch_registry()
        engine = _engine(catalog, registry, wire, tmp_repo)
        detector = DriftDetector(engine, tmp_repo)
        await detector.check_drift(SWITCH_ID)

        wire.reset()
        await detector.check_drift(SWITCH_ID)
        assert wire.non_param_calls() == []

        # A day and a bit passes; the 24h unconfirmed lease lapses.
        real_time = time.time
        monkeypatch.setattr(
            dc.time, "time", lambda: real_time() + 25 * 3600
        )
        wire.reset()
        await detector.check_drift(SWITCH_ID)
        assert wire.non_param_calls(), "expired rows must re-probe"

    @pytest.mark.asyncio
    async def test_firmware_change_makes_every_row_stale(
        self, catalog, tmp_repo, isolated_db
    ):
        """Rows are keyed by firmware: an upgrade invalidates them with no
        invalidation code — the next audit re-probes."""
        wire = Wire()
        registry = _switch_registry()
        engine = _engine(catalog, registry, wire, tmp_repo)
        detector = DriftDetector(engine, tmp_repo)
        await detector.check_drift(SWITCH_ID)
        wire.reset()
        await detector.check_drift(SWITCH_ID)
        assert wire.non_param_calls() == []

        # The switch takes a firmware upgrade; the dump now reports it.
        wire.dump = SWITCH_DUMP.replace(SWITCH_FW, "1.21.0")
        wire.reset()
        await detector.check_drift(SWITCH_ID)
        assert wire.non_param_calls(), (
            "rows recorded under the old firmware must not suppress probes "
            "after an upgrade"
        )

    @pytest.mark.asyncio
    async def test_force_probe_ignores_absent_rows(
        self, catalog, tmp_repo, isolated_db
    ):
        """An explicit operator capture may re-ask an API the audit recorded
        absent — without waiting for the lease to lapse."""
        wire = Wire()
        registry = _switch_registry()
        engine = _engine(catalog, registry, wire, tmp_repo)
        detector = DriftDetector(engine, tmp_repo)
        await detector.check_drift(SWITCH_ID)

        wire.reset()
        await engine.snapshot_device(SWITCH_ID, force_probe=True)
        assert wire.non_param_calls(), "force_probe must ignore absent rows"

        # The audit path is unchanged by it.
        wire.reset()
        await detector.check_drift(SWITCH_ID)
        assert wire.non_param_calls() == []


class TestFirmwareLiftedFromDump:
    """The dump's firmware line is VOLATILE (dropped from parsed params), so
    the engine lifts it from the raw text first and persists the delta —
    reaching devices the health monitor cannot authenticate to."""

    @pytest.mark.asyncio
    async def test_lift_writes_registry_delta_once(
        self, catalog, tmp_repo, isolated_db
    ):
        wire = Wire()
        registry = _switch_registry()
        engine = _engine(catalog, registry, wire, tmp_repo)
        await DriftDetector(engine, tmp_repo).check_drift(SWITCH_ID)

        assert (SWITCH_ID, {"firmware_version": SWITCH_FW}) in registry.updates
        count = len(registry.updates)
        # Unchanged firmware on the next audit writes nothing (no churn).
        await DriftDetector(engine, tmp_repo).check_drift(SWITCH_ID)
        assert len(registry.updates) == count

    def test_parse_still_drops_the_volatile_key(self):
        from admz.snapshot.engine import _parse_param_dump, firmware_from_dump
        assert firmware_from_dump(SWITCH_DUMP) == SWITCH_FW
        assert "root.Properties.Firmware.Version" not in _parse_param_dump(
            SWITCH_DUMP
        )


# ---------------------------------------------------------------------------
# The classifier — the piece the plan flagged as "most likely still wrong"
# ---------------------------------------------------------------------------

class _R:
    """Minimal StepResult stand-in."""

    def __init__(self, success=False, status_code=None, error=None):
        self.success = success
        self.status_code = status_code
        self.error = error


class TestClassify:
    from admz.device_capabilities import ABSENT, ABSENT_UNCONFIRMED, PRESENT

    @pytest.mark.parametrize("result,expected", [
        (_R(success=True), "present"),
        (_R(success=True, status_code=200), "present"),
        # Clean "not here" answers → absent.
        (_R(status_code=404, error="HTTP 404: Not Found"), "absent"),
        (_R(status_code=405, error="HTTP 405"), "absent"),
        (_R(status_code=501, error="HTTP 501"), "absent"),
        (_R(status_code=400, error="HTTP 400"), "absent"),
        (_R(status_code=410, error="HTTP 410"), "absent"),
        # A JSON-RPC error object (200 + error) → the API endpoint answered
        # and refused the method: absent.
        (_R(status_code=200, error="-32601: Method not found"), "absent"),
        # Ambiguous on a readable device → absent_unconfirmed.
        (_R(status_code=401, error="Authentication failed (401)."),
         "absent_unconfirmed"),
        (_R(status_code=403, error="HTTP 403"), "absent_unconfirmed"),
        (_R(status_code=500, error="HTTP 500"), "absent_unconfirmed"),
        (_R(status_code=503, error="HTTP 503"), "absent_unconfirmed"),
        (_R(status_code=200, error="Failed to parse JSON response: x"),
         "absent_unconfirmed"),
        # The T8516's actual failure: transport error, no status at all.
        (_R(error="Transport error: Server disconnected"),
         "absent_unconfirmed"),
        (_R(error="Request timed out after 10s"), "absent_unconfirmed"),
        (_R(error="Connection failed: refused"), "absent_unconfirmed"),
    ])
    def test_readable_device(self, result, expected):
        from admz.device_capabilities import classify
        assert classify(result, device_readable=True) == expected

    @pytest.mark.parametrize("result", [
        _R(status_code=404, error="HTTP 404"),
        _R(error="Transport error: x"),
        _R(status_code=500, error="HTTP 500"),
    ])
    def test_unreadable_device_is_indeterminate(self, result):
        """The control: with the device unreadable, NO failure is evidence."""
        from admz.device_capabilities import classify
        assert classify(result, device_readable=False) is None

    def test_success_counts_even_when_unreadable_flag_wrong(self):
        """A 2xx is proof of presence regardless of the control — the read
        itself demonstrates readability."""
        from admz.device_capabilities import classify
        assert classify(_R(success=True), device_readable=False) == "present"


class TestStoreLifecycle:
    def _store(self, tmp_path):
        from admz.device_capabilities import DeviceCapabilityStore
        return DeviceCapabilityStore(str(tmp_path / "caps.db"))

    def test_unconfirmed_streak_backs_off_and_caps(self, tmp_path):
        from admz.device_capabilities import (
            ABSENT_UNCONFIRMED, UNCONFIRMED_MAX_TTL_SECONDS,
        )
        store = self._store(tmp_path)
        now = 1_000_000.0
        r1 = store.record("d1", "sip", ABSENT_UNCONFIRMED, firmware="1.0", now=now)
        assert r1.fail_streak == 1
        assert r1.expires_at == pytest.approx(now + 24 * 3600)
        r2 = store.record("d1", "sip", ABSENT_UNCONFIRMED, firmware="1.0", now=now)
        assert r2.fail_streak == 2
        assert r2.expires_at == pytest.approx(now + 48 * 3600)
        r3 = store.record("d1", "sip", ABSENT_UNCONFIRMED, firmware="1.0", now=now)
        assert r3.expires_at == pytest.approx(now + 96 * 3600)
        for _ in range(6):
            r = store.record("d1", "sip", ABSENT_UNCONFIRMED, firmware="1.0", now=now)
        assert r.expires_at == pytest.approx(now + UNCONFIRMED_MAX_TTL_SECONDS)

    def test_streak_resets_on_firmware_change_and_on_absent(self, tmp_path):
        from admz.device_capabilities import ABSENT, ABSENT_UNCONFIRMED
        store = self._store(tmp_path)
        store.record("d1", "sip", ABSENT_UNCONFIRMED, firmware="1.0", now=1.0)
        r = store.record("d1", "sip", ABSENT_UNCONFIRMED, firmware="2.0", now=2.0)
        assert r.fail_streak == 1  # new firmware, new lease
        r = store.record("d1", "sip", ABSENT, firmware="2.0", now=3.0)
        assert r.fail_streak == 0
        assert r.classification == "absent"

    def test_view_excludes_stale(self, tmp_path):
        from admz.device_capabilities import ABSENT, PRESENT
        store = self._store(tmp_path)
        now = 1_000_000.0
        store.record("d1", "sip", ABSENT, firmware="1.0", now=now)
        store.record("d1", "ntp", PRESENT, firmware="1.0", now=now)
        # Trusted at the recorded firmware, inside the lease.
        assert set(store.view("d1", "1.0", now + 60)) == {"sip", "ntp"}
        # Different firmware → nothing is trusted.
        assert store.view("d1", "2.0", now + 60) == {}
        # Lease lapsed → the absent row drops out; present has no expiry.
        week = 7 * 86400
        assert set(store.view("d1", "1.0", now + week + 1)) == {"ntp"}

    def test_rows_recorded_under_unknown_firmware_go_stale_when_known(
        self, tmp_path
    ):
        from admz.device_capabilities import ABSENT
        store = self._store(tmp_path)
        store.record("d1", "sip", ABSENT, firmware="", now=1.0)
        assert "sip" in store.view("d1", "", 2.0)
        assert store.view("d1", "9.80.1", 2.0) == {}

    def test_forget_clears_the_device(self, tmp_path):
        from admz.device_capabilities import ABSENT
        store = self._store(tmp_path)
        store.record("d1", "sip", ABSENT, firmware="1.0", now=1.0)
        store.record("d2", "sip", ABSENT, firmware="1.0", now=1.0)
        assert store.forget("d1") == 1
        assert store.list("d1") == []
        assert len(store.list("d2")) == 1

    def test_reason_is_capped(self, tmp_path):
        from admz.device_capabilities import ABSENT
        store = self._store(tmp_path)
        r = store.record(
            "d1", "sip", ABSENT, firmware="1.0", reason="x" * 5000, now=1.0
        )
        assert len(r.reason) <= 200


class TestProbeKeys:
    def test_api_id_when_the_catalog_has_one(self, catalog):
        from admz.device_capabilities import probe_key_for
        assert probe_key_for(catalog, "vapix", "sip:getSIPAccounts") == "sip"
        assert probe_key_for(catalog, "vapix", "ntp.cgi:getNTPInfo") == "ntp"
        assert probe_key_for(
            catalog, "vapix", "event-schedules:listSchedules"
        ) == "event-schedules"

    def test_api_name_when_no_api_id(self, catalog):
        from admz.device_capabilities import probe_key_for
        # Legacy CGIs carry no api_id in the catalog — the API name is the key.
        assert probe_key_for(
            catalog, "vapix", "applications-list.cgi:list"
        ) == "applications-list.cgi"

    def test_fake_catalog_without_metadata_method(self):
        from admz.device_capabilities import probe_key_for

        class FakeCatalog:
            def get_operation(self, family, op_id):
                return None

        assert probe_key_for(FakeCatalog(), "vapix", "sip:getSIPAccounts") == "sip"
        assert probe_key_for(None, "vapix", "ntp.cgi:getNTPInfo") == "ntp.cgi"


class TestSelectionStaysOutOfTheAdapterIndex:
    """``get_facets_for_device`` is the STATIC index — nine callers (restore,
    drift canonical keys, demos) need it unfiltered. The capability view is
    applied only where reads are issued."""

    def test_absent_row_does_not_remove_the_facet_from_the_index(
        self, isolated_db
    ):
        from admz.device_capabilities import ABSENT, capability_store
        from admz.snapshot.facets import get_facets_for_device

        capability_store.record(
            "cam-09", "sip", ABSENT, firmware="12.1.65", now=time.time()
        )
        names = [
            f.name for f in get_facets_for_device(
                {"device_id": "cam-09", "api_family": "vapix",
                 "firmware_version": "12.1.65"}
            )
        ]
        assert "sip" in names


class TestMinFirmwareComparison:
    """The lexicographic bug: "9.80" >= "12" as strings, so pre-12 devices
    matched 12-only facets. Tuple comparison via the one parser."""

    def _matches(self, firmware):
        from admz.snapshot.facets.base import DeviceCriteria, FacetAdapter

        class F(FacetAdapter):
            name = "f"
            applies_to = [DeviceCriteria(min_firmware="12")]
            write_ops = []

            def serialize(self, raw):
                return {}

            def deserialize(self, doc):
                return []

        info = {"api_family": "vapix"}
        if firmware is not None:
            info["firmware_version"] = firmware
        return F().matches_device(info)

    def test_parse_version_accepts_bare_major(self):
        from admz.firmware.upgrade_path import parse_version
        assert parse_version("12") == (12, 0, 0)

    def test_pre_12_device_is_excluded(self):
        assert self._matches("9.80.1") is False  # the bug matched this

    def test_12_device_is_included(self):
        assert self._matches("12.1.65") is True

    def test_unknown_firmware_fails_closed(self):
        assert self._matches("") is False
        assert self._matches(None) is False


class TestDeviceFirmware:
    def test_observed_beats_manual(self):
        from admz.device_capabilities import device_firmware
        assert device_firmware(
            {"firmware_version": "12.1.65", "firmware": "11.0.0"}
        ) == "12.1.65"
        assert device_firmware({"firmware": "11.0.0"}) == "11.0.0"
        assert device_firmware({}) == ""
        assert device_firmware(None) == ""


# ---------------------------------------------------------------------------
# Drift honesty (FR-DRF-012/013)
# ---------------------------------------------------------------------------

class TestDriftHonesty:
    # The live network doc as the Wire's dump serializes it — baselines seed
    # both keys so the network facet compares clean and the sip facet is the
    # only variable in each test.
    NETWORK_BASELINE = {
        "HostName": "axis-t8516",
        "eth0.MACAddress": "B8:A4:4F:00:00:16",
    }

    def _seed_baseline_with_sip(self, tmp_repo):
        tmp_repo.write_facet(SWITCH_ID, "network", dict(self.NETWORK_BASELINE))
        tmp_repo.write_facet(
            SWITCH_ID, "sip",
            {"config": {"Enabled": "yes"}},
        )
        return tmp_repo.commit_snapshot(SWITCH_ID)

    @pytest.mark.asyncio
    async def test_baseline_facet_now_skipped_is_facets_absent(
        self, catalog, tmp_repo, isolated_db
    ):
        """A baselined facet the device is known to lack IS drift — reported
        as facets_absent, with NO DriftField (a revert must never write to an
        API the device does not have)."""
        baseline = self._seed_baseline_with_sip(tmp_repo)
        wire = Wire()
        registry = _switch_registry(baseline_sha=baseline)
        engine = _engine(catalog, registry, wire, tmp_repo)
        detector = DriftDetector(engine, tmp_repo)

        await detector.check_drift(SWITCH_ID)   # cycle 1: learn
        report = await detector.check_drift(SWITCH_ID)  # cycle 2: skip

        assert "sip" in report.facets_absent
        assert report.has_drift is True
        assert all(f.facet != "sip" for f in report.fields), (
            "an absent facet must not produce revertable DriftFields"
        )
        summary = report.to_summary()
        assert summary["facets_absent"] == report.facets_absent

    @pytest.mark.asyncio
    async def test_failed_read_is_unverified_not_drift(
        self, catalog, tmp_repo, isolated_db
    ):
        """The latent bug this closes: a transient API failure used to read
        every stored key as <missing> and report the whole facet drifted.
        Cycle 1 (nothing learned yet, reads fail) must say 'unverified'."""
        baseline = self._seed_baseline_with_sip(tmp_repo)
        wire = Wire()
        registry = _switch_registry(baseline_sha=baseline)
        engine = _engine(catalog, registry, wire, tmp_repo)
        report = await DriftDetector(engine, tmp_repo).check_drift(SWITCH_ID)

        assert "sip" in report.facets_unverified
        assert all(f.facet != "sip" for f in report.fields)
        # network still compares fine and matches its baseline.
        assert report.facet_status["network"] == "ok"

    @pytest.mark.asyncio
    async def test_facet_absent_only_when_baselined(
        self, catalog, tmp_repo, isolated_db
    ):
        """No baseline entry for sip → a skipped sip read is not drift of any
        kind; nothing to report."""
        tmp_repo.write_facet(SWITCH_ID, "network", dict(self.NETWORK_BASELINE))
        baseline = tmp_repo.commit_snapshot(SWITCH_ID)
        wire = Wire()
        registry = _switch_registry(baseline_sha=baseline)
        engine = _engine(catalog, registry, wire, tmp_repo)
        detector = DriftDetector(engine, tmp_repo)

        await detector.check_drift(SWITCH_ID)
        report = await detector.check_drift(SWITCH_ID)
        assert report.facets_absent == []
        assert report.has_drift is False


class TestSignatureStability:
    """The alerting hash folds facets_absent in ONLY when non-empty —
    otherwise every stored signature changes on deploy and the fleet fires a
    'changed' storm for nothing."""

    def _report(self, **kw):
        from admz.snapshot.models import DriftField, DriftReport
        report = DriftReport(device_id="d1", has_drift=True, **kw)
        report.fields.append(DriftField(
            facet="network", path="HostName", expected="a", actual="b",
        ))
        return report

    def test_empty_absent_leaves_signature_unchanged(self):
        """Byte-equality with the PRE-#451 formula, computed inline. Comparing
        two new-code signatures to each other is vacuous — an unconditional
        append changes both identically and they still agree (the first run
        of the mutation checks proved exactly that). Every signature stored
        in production was written by this formula; it must keep matching."""
        import hashlib
        import json

        from admz.snapshot.drift_alerts import _signature_for

        report = self._report(facets_absent=[])
        rows = sorted(
            (f.facet, f.path, f.expected, f.actual, f.bucket, f.owner or "")
            for f in report.fields
        )
        blob = json.dumps(rows, separators=(",", ":"))
        pre_451 = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        assert _signature_for(report) == pre_451
        assert _signature_for(self._report()) == pre_451

    def test_absent_facets_change_the_signature(self):
        from admz.snapshot.drift_alerts import _signature_for
        assert _signature_for(self._report()) != _signature_for(
            self._report(facets_absent=["sip"])
        )

    def test_absent_only_drift_transitions_as_appeared(self, tmp_path):
        """A device whose ONLY drift is an absent facet must alert as
        'appeared', not 'changed: 0 → 0 field(s)'."""
        from admz.snapshot.drift_alerts import DriftAlertStore
        from admz.snapshot.models import DriftReport

        store = DriftAlertStore(str(tmp_path / "alerts.db"))
        clean = DriftReport(device_id="d1", has_drift=False)
        store.process_report(clean)          # baseline
        absent = DriftReport(
            device_id="d1", has_drift=True, facets_absent=["sip"],
        )
        alert = store.process_report(absent)
        assert alert is not None and alert.transition == "appeared"
        assert "sip" in alert.summary
        cleared = store.process_report(
            DriftReport(device_id="d1", has_drift=False)
        )
        assert cleared is not None and cleared.transition == "cleared"


# ---------------------------------------------------------------------------
# The executor stops shouting about transport refusals
# ---------------------------------------------------------------------------

class TestTransportErrorLogging:
    @pytest.mark.asyncio
    async def test_no_error_log_for_a_dropped_connection(self, catalog, caplog):
        def handler(request):
            raise httpx.RemoteProtocolError("Server disconnected", request=request)

        executor = VapixExecutor(
            timeout=2.0, retries=0, transport=httpx.MockTransport(handler)
        )
        op = catalog.get_operation("vapix", "sip:getSIPAccounts").to_executor_dict()
        with caplog.at_level(logging.WARNING, logger="admz.executor.vapix"):
            result = await executor.execute(
                op, {"host": "192.0.2.16", "device_id": "sw", "auth": None},
                {"username": "u", "password": "p"}, {},
            )
        assert result.success is False
        assert result.error.startswith("Transport error:")
        vapix_records = [
            r for r in caplog.records if r.name == "admz.executor.vapix"
        ]
        assert vapix_records, "the refusal must still be logged (WARNING)"
        assert all(r.levelno < logging.ERROR for r in vapix_records)
        assert all(r.exc_info is None for r in vapix_records), (
            "no traceback for an expected refusal"
        )

    @pytest.mark.asyncio
    async def test_non_transport_surprise_still_logs_error(self, catalog, caplog):
        """The control: the catch-all is untouched for genuine surprises."""
        def handler(request):
            raise RuntimeError("boom")

        executor = VapixExecutor(
            timeout=2.0, retries=0, transport=httpx.MockTransport(handler)
        )
        op = catalog.get_operation("vapix", "sip:getSIPAccounts").to_executor_dict()
        with caplog.at_level(logging.WARNING, logger="admz.executor.vapix"):
            result = await executor.execute(
                op, {"host": "192.0.2.16", "device_id": "sw", "auth": None},
                {"username": "u", "password": "p"}, {},
            )
        assert result.success is False
        assert any(
            r.levelno == logging.ERROR for r in caplog.records
            if r.name == "admz.executor.vapix"
        )


# ---------------------------------------------------------------------------
# Rollup + rebind
# ---------------------------------------------------------------------------

class TestRollupAndRebind:
    @pytest.mark.asyncio
    async def test_skipped_is_settled_never_partial(
        self, catalog, tmp_repo, isolated_db
    ):
        """All reads that ran succeeded; some were skipped as unsupported —
        that snapshot is COMPLETED, not PARTIAL."""
        from admz.snapshot.models import SnapshotStatus

        wire = Wire()
        registry = _switch_registry()
        engine = _engine(catalog, registry, wire, tmp_repo)
        detector = DriftDetector(engine, tmp_repo)
        await detector.check_drift(SWITCH_ID)   # learn

        snapshot = await engine.snapshot_device(SWITCH_ID)
        assert snapshot.skipped_facets, "control: something was skipped"
        assert snapshot.status == SnapshotStatus.COMPLETED
        summary = snapshot.to_summary()
        assert summary["facets_skipped"] == len(snapshot.skipped_facets)
        skipped_names = {s["name"] for s in summary["skipped"]}
        assert "sip" in skipped_names

    def test_capabilities_on_the_428_cascade(self):
        from admz.backends.sqlite_backend import SQLiteDeviceRegistry
        assert "device_capabilities" in SQLiteDeviceRegistry._DEVICE_STATE_TABLES

    def test_remove_device_purges_capability_rows(self, tmp_path, monkeypatch):
        from admz.backends.sqlite_backend import SQLiteDeviceRegistry
        from admz.device_capabilities import ABSENT, DeviceCapabilityStore

        db = str(tmp_path / "admz.db")
        monkeypatch.setenv("ADMZ_DB_PATH", db)
        backend = SQLiteDeviceRegistry(
            db_path=db, key_path=str(tmp_path / "admz.key")
        )
        backend.add_device("d1", {"host": "192.0.2.5"})
        store = DeviceCapabilityStore(db)
        store.record("d1", "sip", ABSENT, firmware="1.0", now=1.0)
        backend.remove_device("d1")
        assert store.list("d1") == []
