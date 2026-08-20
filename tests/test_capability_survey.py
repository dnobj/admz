"""ADR-0063 S2 (#452) — the capability survey for every install.

Survey-for-everyone means: the full ``getApiList`` enumeration runs locally
(positives only, into the ADR-0063 store) for any install — after onboarding,
on a firmware change, on a 30-day cadence — while *contributing* anything to
the atlas stays behind ``survey.contributor``, including the "Run now" path
that used to push with a stored PAT while the toggle was off.
"""

import asyncio
import time
from types import SimpleNamespace
from typing import Any, Dict

import httpx
import pytest

import axis_api_atlas
from axis_api_atlas.catalog.loader import CatalogLoader

from admz.executor.vapix import VapixExecutor

API_LIST = [
    {"id": "sip", "version": "2.2", "name": "SIP"},
    {"id": "fwmgr", "version": "1.0", "name": "Firmware management"},
    {"id": "ntp", "version": "1.3", "name": "NTP"},
]


class FakeRegistry:
    def __init__(self, devices):
        self.devices = devices

    def get_device_info(self, device_id):
        return dict(self.devices.get(device_id, {}))

    def device_exists(self, device_id):
        return device_id in self.devices

    def list_devices(self):
        return [{**info, "device_id": did} for did, info in self.devices.items()]

    def get_credentials(self, device_id, account_id="default", requester=None):
        return {"username": "x", "password": "y"}

    def update_device_info(self, device_id, updates):
        self.devices.setdefault(device_id, {}).update(updates)


@pytest.fixture(scope="module")
def catalog():
    return CatalogLoader(axis_api_atlas.default_data_path())


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    path = tmp_path / "admz.db"
    monkeypatch.setenv("ADMZ_DB_PATH", str(path))
    return path


def _executor(handler):
    return VapixExecutor(
        timeout=2.0, retries=0, transport=httpx.MockTransport(handler)
    )


def _api_list_handler(request):
    if "apidiscovery" in request.url.path:
        return httpx.Response(200, json={"data": {"apiList": API_LIST}})
    return httpx.Response(404, text="Not Found")


# ---------------------------------------------------------------------------
# The enumeration — positives only, id-mapped, absent rows cleared
# ---------------------------------------------------------------------------

class TestRunCapabilitySurvey:
    @pytest.mark.asyncio
    async def test_positives_recorded_under_catalog_ids(
        self, catalog, isolated_db
    ):
        from admz.device_capabilities import capability_store, run_capability_survey

        registry = FakeRegistry({"cam-01": {
            "host": "192.0.2.5", "firmware_version": "12.1.65",
        }})
        result = await run_capability_survey(
            device_id="cam-01", registry=registry, catalog=catalog,
            executors={"vapix": _executor(_api_list_handler)},
        )
        assert result["success"] is True
        keys = {r.probe_key: r for r in capability_store.list("cam-01")}
        # Device-reported "fwmgr" lands under the CATALOG id.
        assert "firmware-manager" in keys
        assert "fwmgr" not in keys
        assert keys["sip"].classification == "present"
        assert keys["sip"].source == "discovery"
        assert keys["sip"].firmware == "12.1.65"

    @pytest.mark.asyncio
    async def test_positive_clears_an_absent_row_and_absence_writes_nothing(
        self, catalog, isolated_db
    ):
        """The two controls from the issue: a positive over an ``absent`` row
        clears it; an API missing from the list writes NOTHING — getApiList
        is legacy-only, so absence from it proves nothing."""
        from admz.device_capabilities import (
            ABSENT,
            capability_store,
            run_capability_survey,
        )

        registry = FakeRegistry({"cam-01": {
            "host": "192.0.2.5", "firmware_version": "12.1.65",
        }})
        capability_store.record(
            "cam-01", "sip", ABSENT, firmware="12.1.65", now=time.time()
        )
        capability_store.record(
            "cam-01", "action-rules", ABSENT, firmware="12.1.65", now=time.time()
        )

        await run_capability_survey(
            device_id="cam-01", registry=registry, catalog=catalog,
            executors={"vapix": _executor(_api_list_handler)},
        )
        rows = {r.probe_key: r for r in capability_store.list("cam-01")}
        assert rows["sip"].classification == "present", "positive clears absent"
        # action-rules is NOT in the device's list: the row is untouched —
        # still absent, same lease — not flipped, not deleted, not re-leased.
        assert rows["action-rules"].classification == "absent"

    @pytest.mark.asyncio
    async def test_failed_read_records_nothing(self, catalog, isolated_db):
        from admz.device_capabilities import capability_store, run_capability_survey

        def handler(request):
            raise httpx.RemoteProtocolError("dropped", request=request)

        registry = FakeRegistry({"sw-01": {"host": "192.0.2.16"}})
        result = await run_capability_survey(
            device_id="sw-01", registry=registry, catalog=catalog,
            executors={"vapix": _executor(handler)},
        )
        assert result["success"] is False
        assert capability_store.list("sw-01") == []


# ---------------------------------------------------------------------------
# The firmware event (FR-KNW-013)
# ---------------------------------------------------------------------------

class TestNoteFirmware:
    def _audit_actions(self):
        from admz.audit import AuditLog
        return [e.action for e in AuditLog().list_recent(limit=20)]

    def _survey_tasks(self, device_id):
        from admz.device_capabilities import SURVEY_ACTION_TYPE
        from admz.tasks.store import tasks_store
        return [t for t in tasks_store.list_active_for(device_id)
                if t.action_type == SURVEY_ACTION_TYPE]

    def test_real_change_audits_and_enqueues(self, isolated_db):
        from admz.device_capabilities import note_firmware

        assert note_firmware(
            "cam-01", prev="11.11.181", new="11.11.205"
        ) == "device.firmware_changed"
        assert "device.firmware_changed" in self._audit_actions()
        tasks = self._survey_tasks("cam-01")
        assert len(tasks) == 1
        assert "firmware changed 11.11.181 → 11.11.205" in tasks[0].description

    def test_first_sight_audits_observed_and_does_not_enqueue(self, isolated_db):
        from admz.device_capabilities import note_firmware

        assert note_firmware(
            "cam-02", prev="", new="11.11.205"
        ) == "device.firmware_observed"
        actions = self._audit_actions()
        assert "device.firmware_observed" in actions
        assert "device.firmware_changed" not in actions
        assert self._survey_tasks("cam-02") == []

    def test_unchanged_is_silent(self, isolated_db):
        from admz.device_capabilities import note_firmware

        assert note_firmware("cam-03", prev="12.0.0", new="12.0.0") is None
        assert note_firmware("cam-03", prev="x", new="") is None
        assert self._audit_actions() == []
        assert self._survey_tasks("cam-03") == []

    def test_enqueue_is_deduped(self, isolated_db):
        from admz.device_capabilities import note_firmware

        note_firmware("cam-04", prev="1.0", new="2.0")
        note_firmware("cam-04", prev="2.0", new="3.0")
        assert len(self._survey_tasks("cam-04")) == 1

    @pytest.mark.asyncio
    async def test_engine_dump_lift_fires_the_event(self, isolated_db, tmp_path):
        """The engine seam — the one that reaches a ``limited_api`` device
        whose health probe never authenticates far enough for facts."""
        import subprocess

        from admz.snapshot.drift import DriftDetector
        from admz.snapshot.engine import SnapshotEngine
        from admz.snapshot.git_repo import GitRepo

        repo_path = str(tmp_path / "config-repo")
        repo = GitRepo(repo_path)
        for key, val in [("user.email", "t@t"), ("user.name", "T"),
                         ("commit.gpgsign", "false")]:
            subprocess.run(["git", "config", key, val], cwd=repo_path, check=True)

        dump = {"v": "root.Brand.Brand=AXIS\nroot.Properties.Firmware.Version=1.20.3\n"}

        def handler(request):
            if "param.cgi" in request.url.path:
                return httpx.Response(200, text=dump["v"])
            return httpx.Response(404, text="Not Found")

        registry = FakeRegistry({"sw-01": {"host": "192.0.2.16",
                                           "api_family": "vapix"}})
        engine = SnapshotEngine(
            catalog=CatalogLoader(axis_api_atlas.default_data_path()),
            registry=registry,
            executors={"vapix": _executor(handler)}, git_repo=repo,
        )
        detector = DriftDetector(engine, repo)
        await detector.check_drift("sw-01")
        # First sight: observed, no survey task.
        assert self._survey_tasks("sw-01") == []

        dump["v"] = dump["v"].replace("1.20.3", "1.21.0")
        await detector.check_drift("sw-01")
        assert "device.firmware_changed" in self._audit_actions()
        assert len(self._survey_tasks("sw-01")) == 1


# ---------------------------------------------------------------------------
# Onboarding success exits (never from a gated branch)
# ---------------------------------------------------------------------------

class TestOnboardingEnqueue:
    @pytest.fixture
    def calls(self, monkeypatch, isolated_db):
        import admz.onboarding as onboarding_module

        recorded = []
        monkeypatch.setattr(
            "admz.device_capabilities.enqueue_capability_survey",
            lambda device_id, **kw: recorded.append((device_id, kw)) or "tid",
        )
        return recorded

    def test_success_statuses_enqueue(self, calls):
        from admz.onboarding import (
            ENTRY_CREDENTIALS_SAVED,
            OWN_ACCOUNT_CREATED,
            PROVISIONED,
            _with_survey,
        )

        for status in (PROVISIONED, OWN_ACCOUNT_CREATED, ENTRY_CREDENTIALS_SAVED):
            _with_survey({"status": status, "device_id": f"d-{status}"})
        assert [c[0] for c in calls] == [
            "d-provisioned", "d-admz_account_created", "d-fleet_credentials_saved",
        ]

    def test_gated_and_failed_exits_never_enqueue(self, calls):
        from admz.onboarding import (
            APPROVAL_REQUIRED,
            CREDENTIALS_NEEDED,
            PROVISION_FAILED,
            _with_survey,
        )

        for status in (APPROVAL_REQUIRED, CREDENTIALS_NEEDED, PROVISION_FAILED):
            _with_survey({"status": status, "device_id": "d1"})
        assert calls == []

    def test_already_credentialed_is_first_sight_only(self, calls, isolated_db):
        from admz.device_capabilities import ABSENT, capability_store
        from admz.onboarding import ALREADY_CREDENTIALED, _with_survey

        _with_survey({"status": ALREADY_CREDENTIALED, "device_id": "fresh"})
        assert [c[0] for c in calls] == ["fresh"]

        capability_store.record("seen", "sip", ABSENT, firmware="1.0", now=1.0)
        _with_survey({"status": ALREADY_CREDENTIALED, "device_id": "seen"})
        assert [c[0] for c in calls] == ["fresh"]  # unchanged — not first sight


# ---------------------------------------------------------------------------
# The handler + the cadence
# ---------------------------------------------------------------------------

class TestHandlerAndCadence:
    @pytest.mark.asyncio
    async def test_detection_task_end_to_end(self, catalog, isolated_db):
        from admz.device_capabilities import (
            capability_store,
            enqueue_capability_survey,
        )
        from admz.tasks.handlers import TaskContext, execute_task_action
        from admz.tasks.store import tasks_store

        registry = FakeRegistry({"cam-01": {
            "host": "192.0.2.5", "firmware_version": "12.1.65",
        }})
        tid = enqueue_capability_survey("cam-01", reason="test")
        task = tasks_store.get(tid)
        ctx = TaskContext(
            registry=registry, catalog=catalog,
            executors={"vapix": _executor(_api_list_handler)},
        )
        result = await execute_task_action(task, ctx)
        assert result["success"] is True
        assert result["surveyed"] == 1
        assert result["apis_recorded"] == len(API_LIST)
        keys = {r.probe_key for r in capability_store.list("cam-01")}
        assert {"sip", "ntp", "firmware-manager"} <= keys

    def test_schedule_synced_from_the_setting(self, isolated_db, tmp_path):
        """#455 review, MINOR-1: the fleet setting is LIVE (synced at every
        app build), not consulted-once — and it is the authority for the
        interval. The operator's PAUSE is theirs and survives syncs."""
        from admz.device_capabilities import (
            SURVEY_INTERVAL_DEFAULT,
            SURVEY_SCHEDULE_ID,
            ensure_capability_survey_schedule,
        )
        from admz.tasks.store import TaskStore

        store = TaskStore(str(tmp_path / "tasks.db"))
        setting = {"value": None}
        settings = SimpleNamespace(get=lambda key: setting["value"])

        ensure_capability_survey_schedule(store, settings)
        task = store.get(SURVEY_SCHEDULE_ID)
        assert task is not None
        assert task.interval_seconds == SURVEY_INTERVAL_DEFAULT
        assert task.action_type == "capability_survey"

        # The setting changes → the next build applies it.
        setting["value"] = "86400"
        ensure_capability_survey_schedule(store, settings)
        assert store.get(SURVEY_SCHEDULE_ID).interval_seconds == 86400

        # An operator's pause sticks across syncs and setting edits.
        store.update(SURVEY_SCHEDULE_ID, enabled=False)
        setting["value"] = "43200"
        ensure_capability_survey_schedule(store, settings)
        again = store.get(SURVEY_SCHEDULE_ID)
        assert again.enabled is False
        assert again.interval_seconds == 43200

    def test_zero_interval_means_opted_out(self, isolated_db, tmp_path):
        """`0` never creates the schedule, and force-disables an existing
        one — the setting, not deletion, is the opt-out authority (a deleted
        singleton is re-seeded on the next restart by design)."""
        from admz.device_capabilities import (
            SURVEY_SCHEDULE_ID,
            ensure_capability_survey_schedule,
        )
        from admz.tasks.store import TaskStore

        store = TaskStore(str(tmp_path / "tasks.db"))
        setting = {"value": "0"}
        settings = SimpleNamespace(get=lambda key: setting["value"])
        ensure_capability_survey_schedule(store, settings)
        assert store.get(SURVEY_SCHEDULE_ID) is None

        setting["value"] = None
        ensure_capability_survey_schedule(store, settings)
        assert store.get(SURVEY_SCHEDULE_ID).enabled is True
        setting["value"] = "0"
        ensure_capability_survey_schedule(store, settings)
        assert store.get(SURVEY_SCHEDULE_ID).enabled is False


# ---------------------------------------------------------------------------
# Production dispatch shapes + the failed-task lifecycle (#455 review)
# ---------------------------------------------------------------------------

class TestDispatchShapes:
    """The handler is reached two ways in production, and neither matched the
    explicit-full-ctx shape the end-to-end test uses. Pin both (#455 review,
    MINOR-5): renaming an engine attribute or reordering the app lifespan
    must fail a test, not fail production with a green suite."""

    @pytest.mark.asyncio
    async def test_scheduler_shape_resolves_deps_from_the_engine(
        self, catalog, isolated_db
    ):
        from admz.device_capabilities import enqueue_capability_survey
        from admz.tasks.handlers import TaskContext, execute_task_action
        from admz.tasks.store import tasks_store

        registry = FakeRegistry({"cam-01": {"host": "192.0.2.5"}})
        engine = SimpleNamespace(
            registry=registry, catalog=catalog,
            executors={"vapix": _executor(_api_list_handler)},
        )
        tid = enqueue_capability_survey("cam-01", reason="test")
        result = await execute_task_action(
            tasks_store.get(tid), TaskContext(snapshot_engine=engine)
        )
        assert result["success"] is True and result["surveyed"] == 1

    @pytest.mark.asyncio
    async def test_default_installed_context_carries_the_deps(
        self, catalog, isolated_db
    ):
        """The health sweep fires detections with NO explicit ctx — the
        lifespan-installed default must carry registry/catalog/executors."""
        from admz.device_capabilities import enqueue_capability_survey
        from admz.recovery_actions import register_recovery_handlers
        from admz.tasks.handlers import execute_task_action, set_task_context
        from admz.tasks.store import tasks_store

        registry = FakeRegistry({"cam-01": {"host": "192.0.2.5"}})
        register_recovery_handlers(SimpleNamespace(
            snapshot_engine=None, drift_detector=None,
            registry=registry, catalog=catalog,
            executors={"vapix": _executor(_api_list_handler)},
        ))
        try:
            tid = enqueue_capability_survey("cam-01", reason="test")
            result = await execute_task_action(tasks_store.get(tid))
            assert result["success"] is True and result["surveyed"] == 1
        finally:
            from admz.tasks.handlers import TaskContext
            set_task_context(TaskContext())

    @pytest.mark.asyncio
    async def test_contextless_shape_fails_gracefully(self, isolated_db):
        from admz.device_capabilities import enqueue_capability_survey
        from admz.tasks.handlers import TaskContext, execute_task_action
        from admz.tasks.store import tasks_store

        tid = enqueue_capability_survey("cam-01", reason="test")
        result = await execute_task_action(tasks_store.get(tid), TaskContext())
        assert result["success"] is False
        assert "context incomplete" in result["summary"]


class TestFailedSurveyLifecycle:
    """#455 review, MAJOR-1: a one-shot survey whose device failed used to be
    marked 'done' and audited as fired — the firmware-change trigger consumed
    silently, precisely when the device is mid-reboot after the upgrade that
    queued it. The failure must land on the task row and in the audit."""

    @pytest.mark.asyncio
    async def test_failed_single_device_marks_the_task_failed(
        self, catalog, isolated_db
    ):
        from admz.audit import AuditLog
        from admz.device_capabilities import enqueue_capability_survey
        from admz.fleet.health import HealthMonitor
        from admz.recovery_actions import register_recovery_handlers
        from admz.tasks.handlers import TaskContext, set_task_context
        from admz.tasks.store import tasks_store

        def rebooting(request):  # every endpoint drops mid-upgrade
            raise httpx.RemoteProtocolError("rebooting", request=request)

        registry = FakeRegistry({"cam-01": {"host": "192.0.2.5"}})
        register_recovery_handlers(SimpleNamespace(
            snapshot_engine=None, drift_detector=None,
            registry=registry, catalog=catalog,
            executors={"vapix": _executor(rebooting)},
        ))
        try:
            tid = enqueue_capability_survey("cam-01", reason="fw change")
            monitor = HealthMonitor(
                registry=registry, catalog=catalog,
                executors={"vapix": _executor(rebooting)},
            )
            await monitor._run_pending(tasks_store.get(tid))
        finally:
            set_task_context(TaskContext())

        task = tasks_store.get(tid)
        assert task.status == "failed"
        assert task.last_error, "the reason must land on the row"
        actions = [e.action for e in AuditLog().list_recent(limit=10)]
        assert "deferred_action_failed" in actions
        assert "deferred_action_fired" not in actions

    @pytest.mark.asyncio
    async def test_fleet_sweep_is_not_failed_by_one_device(
        self, catalog, isolated_db
    ):
        """The recurring schedule stays success-with-counts — a cadence run
        is not failed by one device's bad hour."""
        from admz.tasks.handlers import TaskContext, execute_task_action
        from admz.tasks.store import Task

        calls = {"n": 0}

        def half_broken(request):
            calls["n"] += 1
            if "apidiscovery" not in request.url.path:
                return httpx.Response(404)
            # cam-01 answers; cam-02 drops.
            if calls["n"] <= 1:
                return httpx.Response(200, json={"data": {"apiList": API_LIST}})
            raise httpx.RemoteProtocolError("down", request=request)

        registry = FakeRegistry({
            "cam-01": {"host": "192.0.2.5"},
            "cam-02": {"host": "192.0.2.6"},
        })
        task = Task(id="cap-sweep", trigger_kind="schedule",
                    action_type="capability_survey", interval_seconds=86400)
        result = await execute_task_action(task, TaskContext(
            registry=registry, catalog=catalog,
            executors={"vapix": _executor(half_broken)},
        ))
        assert result["success"] is True
        assert result["surveyed"] == 1 and result["failed"] == 1


# ---------------------------------------------------------------------------
# The push gate (ADR-0030 amendment): run always allowed, PUSH needs the
# capability — including "Run now"
# ---------------------------------------------------------------------------

class TestContributionGate:
    def _run(self, monkeypatch, *, enabled, has_pat=True):
        from admz.survey import runner as runner_module

        submitted = []

        class FakeSubmitter:
            def submit(self, root, *, branch, title, body):
                submitted.append(branch)
                return SimpleNamespace(pr_url="https://pr", message="ok")

        monkeypatch.setattr(runner_module.secrets, "is_enabled", lambda: enabled)
        monkeypatch.setattr(runner_module.secrets, "has_pat", lambda: has_pat)
        monkeypatch.setattr(runner_module.secrets, "get_pat", lambda: "x")
        monkeypatch.setattr(runner_module.secrets, "get_repo", lambda: "o/r")
        monkeypatch.setattr(
            runner_module.secrets, "get_contributor", lambda: "site"
        )
        monkeypatch.setattr(
            runner_module, "assemble_bundle", lambda *a, **k: "root"
        )
        import admz.survey.github as github_module
        monkeypatch.setattr(
            github_module, "write_offline", lambda root: "offline.zip"
        )
        monkeypatch.setattr(github_module, "GitHubSubmitter", FakeSubmitter)

        survey = SimpleNamespace(model="M1", openapi_specs={},
                                 redacted_snapshot={})
        collector = SimpleNamespace(
            profile="strict",
            survey_fleet=lambda ids: SimpleNamespace(
                surveys=[survey], skipped={}, errors={}
            ),
        )
        report = runner_module.run_survey(
            submit=True, respect_enabled=False, collector=collector,
            submitter=FakeSubmitter(),
        )
        return report, submitted

    def test_run_now_with_pat_and_toggle_off_stays_offline(self, monkeypatch):
        """The path #452 closes: Run now + stored PAT + capability OFF used
        to open a PR anyway."""
        report, submitted = self._run(monkeypatch, enabled=False)
        assert report.status == "offline"
        assert submitted == []

    def test_toggle_on_still_submits(self, monkeypatch):
        report, submitted = self._run(monkeypatch, enabled=True)
        assert report.status == "submitted"
        assert len(submitted) == 1


# ---------------------------------------------------------------------------
# Read surfaces
# ---------------------------------------------------------------------------

class TestReadSurfaces:
    @pytest.mark.asyncio
    async def test_mcp_listing_reports_rows_with_staleness(self, isolated_db):
        from admz.device_capabilities import ABSENT, PRESENT, capability_store
        from admz.mcp.dispatch import _list_device_capabilities

        registry = FakeRegistry({"cam-01": {"firmware_version": "2.0"}})
        now = time.time()
        capability_store.record("cam-01", "sip", PRESENT, firmware="2.0", now=now)
        capability_store.record("cam-01", "ntp", ABSENT, firmware="1.0", now=now)

        from admz.mcp.server import ADMZMCPServer

        class _Server:
            def __init__(self):
                self.registry = registry

            _list_device_capabilities = ADMZMCPServer._list_device_capabilities

        result = await _list_device_capabilities(
            SimpleNamespace(server=_Server()), {"device_id": "cam-01"}
        )
        assert result["success"] is True
        rows = {r["probe_key"]: r for r in result["capabilities"]}
        assert rows["sip"]["stale"] is False
        assert rows["ntp"]["stale"] is True  # recorded under old firmware
        assert result["count"] == 2

    def test_rest_route_shape(self, isolated_db):
        from fastapi.testclient import TestClient

        from admz.api.routes import devices as devices_routes
        from admz.device_capabilities import PRESENT, capability_store
        from fastapi import FastAPI

        registry = FakeRegistry({"cam-01": {"firmware_version": "2.0"}})
        app = FastAPI()
        app.include_router(devices_routes.router, prefix="/api")
        app.dependency_overrides[devices_routes.get_registry] = lambda: registry

        capability_store.record(
            "cam-01", "sip", PRESENT, firmware="2.0", now=time.time()
        )
        client = TestClient(app)
        resp = client.get("/api/devices/cam-01/capabilities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["device_id"] == "cam-01"
        assert body["count"] == 1
        assert body["capabilities"][0]["probe_key"] == "sip"
        assert body["capabilities"][0]["stale"] is False
        assert client.get("/api/devices/nope/capabilities").status_code == 404
