"""ADR-0071 §2 — who raises and resolves notices.

Drift raises at the one choke point every caller shares
(``DriftDetector.check_drift``), so these tests drive a real detector over a
real git repo with a stubbed device read. The ``notify`` action, the accept
path and the startup backfill are driven through their own entry points.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from admz.notices import producers
from admz.notices import store as store_module
from admz.notices.store import NoticeStore
from admz.snapshot import drift_alerts as da_module
from admz.snapshot.drift import DriftDetector
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.models import DriftField, DriftReport
from tests.test_drift import FakeRegistry, FakeSnapshotEngine

BASE = {"root.Image.I0.Resolution": "1920x1080", "root.Image.I0.Rotation": "0"}


@pytest.fixture
def notices(tmp_path, monkeypatch):
    fresh = NoticeStore(str(tmp_path / "admz.db"))
    monkeypatch.setattr(store_module, "notices_store", fresh)
    monkeypatch.setattr(da_module, "drift_alerts",
                        da_module.DriftAlertStore(str(tmp_path / "admz.db")))
    return fresh


@pytest.fixture
def flag(tmp_path, repoint_fleet_settings):
    from admz.fleet_settings import FleetSettings
    return repoint_fleet_settings(FleetSettings(str(tmp_path / "settings.db")))


class _Rig:
    """A real detector over a real repo; ``live`` is what the device reads."""

    def __init__(self, tmp_path):
        repo_path = str(tmp_path / "config-repo")
        self.repo = GitRepo(repo_path)
        for key, val in [("user.email", "t@t.com"), ("user.name", "T"),
                         ("commit.gpgsign", "false")]:
            subprocess.run(["git", "config", key, val], cwd=repo_path, check=True)
        self.repo.write_facet("cam-01", "image",
                              {"I0.Resolution": "1920x1080", "I0.Rotation": "0"})
        sha = self.repo.commit_snapshot("cam-01")
        self.registry = FakeRegistry({"cam-01": {
            "host": "192.0.2.5", "api_family": "vapix", "baseline_sha": sha,
            "model": "AXIS C8110"}})
        self.engine = FakeSnapshotEngine(self.registry, live_params=dict(BASE),
                                         git_repo=self.repo)
        self.detector = DriftDetector(self.engine, self.repo)

    async def check(self, **live):
        self.engine.live_params = {**BASE, **live}
        return await self.detector.check_drift("cam-01")


@pytest.fixture
def rig(tmp_path, notices):
    return _Rig(tmp_path)


def _live(store):
    return store.get_live("drift:cam-01")


def _age_row(tmp_path, notice_id, seconds):
    """Move a notice's clocks into the past, so a later write is measurable."""
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "admz.db"))
    try:
        conn.execute(
            "UPDATE notices SET created_at=created_at-?, updated_at=updated_at-?, "
            "confirmed_at=confirmed_at-? WHERE id=?",
            (seconds, seconds, seconds, notice_id))
        conn.commit()
    finally:
        conn.close()


class TestDriftTransitions:
    @pytest.mark.asyncio
    async def test_appeared_changed_cleared_on_one_row(self, rig, notices):
        await rig.check()                                   # first look: in sync
        assert notices.list(status=None) == []

        report = await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        assert report.alert_transition == "appeared"
        n = _live(notices)
        assert (n.kind, n.status, n.occurrences) == ("drift", "open", 1)
        assert n.title == "Configuration drift on cam-01"
        assert (n.source, n.task_id) == ("check_drift", "")
        assert n.summary["fields"] == 1
        assert n.summary["transition"] == "appeared"
        assert n.summary["by_class"] == {"service_config": 1}
        assert n.severity == "medium"
        first_seen = n.created_at

        await rig.check(**{"root.Image.I0.Resolution": "1280x720",
                           "root.Image.I0.Rotation": "180"})
        again = _live(notices)
        assert again.id == n.id
        assert again.occurrences == 2
        assert again.created_at == first_seen
        assert again.summary["fields"] == 2
        assert again.summary["transition"] == "changed"

        report = await rig.check()
        assert report.alert_transition == "cleared"
        closed = notices.get(n.id)
        assert (closed.status, closed.resolution, closed.handled_by) == (
            "handled", "cleared", "check_drift")

    @pytest.mark.asyncio
    async def test_drift_on_the_first_look_raises(self, rig, notices):
        """The alert store records nothing for a first observation, so the
        detector says "appeared" itself when that observation is drifted."""
        report = await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        assert report.alert_transition is None
        assert _live(notices).summary["transition"] == "appeared"

    @pytest.mark.asyncio
    async def test_an_unchanged_signature_raises_nothing(self, rig, notices):
        await rig.check()
        await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        n = _live(notices)
        assert n.occurrences == 1
        # A dismissed notice stays dismissed until the drift changes.
        notices.handle(n.id, "dismissed", by="anonymous")
        await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        assert _live(notices) is None
        await rig.check(**{"root.Image.I0.Resolution": "800x600"})
        assert _live(notices).id != n.id

    @pytest.mark.asyncio
    async def test_the_same_drift_again_confirms_the_notice(self, rig, notices,
                                                            tmp_path):
        """No transition, still drifted: the notice is confirmed — later
        `confirmed_at`, the confirming check named — and nothing else moves."""
        await rig.check()
        await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        n = _live(notices)
        _age_row(tmp_path, n.id, seconds=1000)
        before = notices.get(n.id)
        with producers.notice_provenance("drift_audit", "sched-5"):
            await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        after = notices.get(n.id)
        assert after.confirmed_at > before.confirmed_at + 900
        assert (after.updated_at, after.created_at) == (before.updated_at, before.created_at)
        assert after.occurrences == 1
        assert (after.source, after.task_id) == ("drift_audit", "sched-5")
        assert after.summary == before.summary

    @pytest.mark.asyncio
    async def test_the_same_drift_again_leaves_a_snooze_asleep(self, rig, notices):
        await rig.check()
        await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        n = _live(notices)
        notices.snooze(n.id, until=n.updated_at + 10 ** 6)
        await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        assert notices.get(n.id).status == "snoozed"

    @pytest.mark.asyncio
    async def test_a_change_wakes_a_snooze(self, rig, notices):
        await rig.check()
        await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        n = _live(notices)
        notices.snooze(n.id, until=n.updated_at + 10 ** 6)
        await rig.check(**{"root.Image.I0.Resolution": "800x600"})
        assert _live(notices).status == "open"

    @pytest.mark.asyncio
    async def test_the_flag_stops_raising_but_never_resolving(self, rig, notices, flag):
        await rig.check()
        await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        n = _live(notices)
        flag.set("drift_notices_enabled", "false")
        assert producers.drift_notices_enabled() is False
        await rig.check(**{"root.Image.I0.Resolution": "800x600"})
        assert _live(notices).occurrences == 1               # not bumped
        await rig.check()
        assert notices.get(n.id).resolution == "cleared"     # still resolved

    def test_the_flag_defaults_on(self, flag):
        assert producers.drift_notices_enabled() is True
        flag.set("drift_notices_enabled", "true")
        assert producers.drift_notices_enabled() is True

    @pytest.mark.asyncio
    async def test_a_quiet_task_raises_nothing(self, rig, notices):
        await rig.check()
        with producers.notice_provenance("drift_audit", "sched-1", notify_console=False):
            await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        assert notices.list(status=None) == []

    @pytest.mark.asyncio
    async def test_a_producer_failure_never_masks_the_report(self, rig, notices,
                                                              monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("notices table locked")
        monkeypatch.setattr(producers, "drift_transition", boom)
        await rig.check()
        report = await rig.check(**{"root.Image.I0.Resolution": "1280x720"})
        assert report.has_drift is True
        assert report.alert_transition == "appeared"

    def test_severity_follows_the_highest_importance(self, notices):
        registry = FakeRegistry({"cam-9": {"host": "192.0.2.9", "baseline_sha": "b"}})
        report = DriftReport(device_id="cam-9", has_drift=True, fields=[
            DriftField(facet="other", path="root.SNMP.V1.WriteCommunity",
                       expected="private", actual="SECRET-VALUE-123"),
            DriftField(facet="image", path="I0.Resolution",
                       expected="1920x1080", actual="1280x720"),
        ])
        n = producers.drift_transition("appeared", report, registry=registry)
        assert n.severity == "high"
        assert n.summary["highest_importance"] == "high"
        assert n.summary["by_class"] == {"security_sensitive": 1, "service_config": 1}

    def test_the_row_holds_no_values(self, notices):
        registry = FakeRegistry({"cam-9": {"host": "192.0.2.9", "baseline_sha": "b",
                                           "nickname": "Lobby-Nick"}})
        report = DriftReport(device_id="cam-9", has_drift=True, fields=[
            DriftField(facet="other", path="root.SNMP.V1.WriteCommunity",
                       expected="OLD-VALUE-456", actual="SECRET-VALUE-123")])
        n = producers.drift_transition("appeared", report, registry=registry)
        stored = repr(n.to_dict())
        for text in ("SECRET-VALUE-123", "OLD-VALUE-456", "Lobby-Nick"):
            assert text not in stored
        assert set(n.summary) <= {"fields", "facets_absent", "by_class",
                                  "highest_importance", "firmware_changed",
                                  "transition"}

    @pytest.mark.asyncio
    async def test_demo_owned_drift_alone_raises_nothing(self, notices):
        report = DriftReport(device_id="cam-9", has_drift=True, fields=[
            DriftField(facet="image", path="I0.A", expected="1", actual="2",
                       bucket="demo_set")])
        assert producers.drift_transition(None, report) is None
        assert notices.list(status=None) == []


class TestTheAuditStampsProvenance:
    @pytest.mark.asyncio
    async def test_source_and_task(self, rig, notices):
        from admz.tasks.handlers import TaskContext, execute_task_action
        from admz.tasks.store import Task

        await rig.check()
        rig.engine.live_params = {**BASE, "root.Image.I0.Resolution": "1280x720"}
        result = await execute_task_action(
            Task(id="sched-9", action_type="drift_audit"),
            TaskContext(drift_detector=rig.detector))
        assert result["success"] is True
        n = _live(notices)
        assert (n.source, n.task_id) == ("drift_audit", "sched-9")
        # The stamp ends with the sweep: a manual check afterwards is manual.
        assert producers.current_provenance().source == "check_drift"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("value", [False, "false", "0"])
    async def test_notify_console_off(self, rig, notices, value):
        from admz.tasks.handlers import TaskContext, execute_task_action
        from admz.tasks.store import Task

        await rig.check()
        rig.engine.live_params = {**BASE, "root.Image.I0.Resolution": "1280x720"}
        await execute_task_action(
            Task(id="sched-9", action_type="drift_audit",
                 action_params={"notify_console": value}),
            TaskContext(drift_detector=rig.detector))
        assert notices.list(status=None) == []


class TestNotifyRaisesAnEventNotice:
    @pytest.mark.asyncio
    async def test_two_firings_one_row(self, notices):
        from admz.tasks.handlers import execute_task_action
        from admz.tasks.store import Task

        task = Task(id="det-r1", action_type="notify", device_id="cam-1",
                    action_params={"message": "Door opened\nafter hours"})
        first = await execute_task_action(task)
        second = await execute_task_action(task)
        assert first["success"] is True
        assert first["notice_id"] == second["notice_id"]
        n = notices.get(first["notice_id"])
        assert (n.kind, n.subject_key, n.occurrences) == ("event", "event:det-r1:cam-1", 2)
        assert n.title == "Door opened after hours"
        assert (n.source, n.task_id, n.device_id) == ("notify", "det-r1", "cam-1")
        assert f"(notice #{n.id})" in second["summary"]

    @pytest.mark.asyncio
    async def test_a_fleet_wide_rule_keys_on_fleet(self, notices):
        from admz.tasks.handlers import execute_task_action
        from admz.tasks.store import Task

        result = await execute_task_action(
            Task(id="det-r2", action_type="notify", description="Tamper"))
        n = notices.get(result["notice_id"])
        assert (n.subject_key, n.title) == ("event:det-r2:fleet", "Tamper")

    @pytest.mark.asyncio
    async def test_a_store_failure_is_a_failure(self, notices, monkeypatch):
        from admz.tasks.handlers import execute_task_action
        from admz.tasks.store import Task

        def boom(**kw):
            raise RuntimeError("database is locked")
        monkeypatch.setattr(notices, "raise_notice", boom)
        result = await execute_task_action(Task(id="det-r3", action_type="notify"))
        assert result["success"] is False
        assert "database is locked" in result["error"]
        assert "notice_id" not in result

    @pytest.mark.asyncio
    async def test_the_detection_audit_row_names_the_notice(self, notices, monkeypatch):
        from admz import audit
        from admz.events.evaluator import DetectionEvaluator

        rows = []
        monkeypatch.setattr(audit, "record_event",
                            lambda principal, action, **kw: rows.append((action, kw)))
        fires = []
        store = SimpleNamespace(record_fire=lambda *a: fires.append(a))
        evaluator = DetectionEvaluator(registry=None, store=store)
        rule = SimpleNamespace(id="r7", name="Door", action_type="notify",
                               action_params={"message": "Door"}, tag=None)
        await evaluator._fire(rule, {"device_id": "cam-1", "type": "t", "id": 1}, 5)
        action, kw = rows[-1]
        assert action == "detection.fired"
        assert kw["details"]["notice_id"] == notices.list()[0].id

    def test_the_sweep_audit_may_carry_the_notice_id(self):
        from admz.fleet.health import _AUDITABLE_OUTCOME_KEYS
        assert "notice_id" in _AUDITABLE_OUTCOME_KEYS


class TestAcceptResolves:
    def _raise(self, device_id):
        return store_module.notices_store.raise_notice(
            kind="drift", subject_key=f"drift:{device_id}", device_id=device_id)

    def test_accepting_the_latest_observation(self, notices):
        from admz import operations
        n = self._raise("dev-a")
        operations.refresh_drift_after_accept("dev-a", "s1", "s1",
                                              accepted_by="HOMELAB\\alice")
        closed = notices.get(n.id)
        assert (closed.status, closed.resolution, closed.handled_by) == (
            "handled", "accepted", "HOMELAB\\alice")

    def test_accepting_an_older_commit(self, notices):
        from admz import operations
        n = self._raise("dev-b")
        operations.refresh_drift_after_accept("dev-b", "old", "new", accepted_by="bob")
        assert notices.get(n.id).resolution == "accepted"

    def test_the_in_sync_report_after_it_does_not_relabel_it(self, notices):
        """refresh_drift_after_accept records a synthetic in-sync report, which
        logs a `cleared` transition; the notice must still read `accepted`."""
        from admz import operations
        da_module.drift_alerts.process_report(DriftReport(
            device_id="dev-c", has_drift=True,
            fields=[DriftField(facet="f", path="p", expected="a", actual="b")]))
        n = self._raise("dev-c")
        operations.refresh_drift_after_accept("dev-c", "s", "s", accepted_by="carol")
        assert notices.get(n.id).resolution == "accepted"
        assert notices.list(status=None)[0].id == n.id


class TestBackfill:
    def _drifted(self, device_id, fields=3):
        da_module.drift_alerts.process_report(DriftReport(
            device_id=device_id, has_drift=True,
            fields=[DriftField(facet="f", path=f"p{i}", expected="a", actual="b")
                    for i in range(fields)]))

    def test_raises_once_for_drift_already_known(self, notices):
        registry = FakeRegistry({
            "cam-a": {"baseline_sha": "b1"},
            "cam-b": {"baseline_sha": "b2"},     # in sync
            "cam-c": {},                          # no baseline
        })
        self._drifted("cam-a")
        da_module.drift_alerts.process_report(DriftReport(device_id="cam-b",
                                                          has_drift=False))
        self._drifted("cam-c")
        assert producers.backfill_drift_notices(registry) == 1
        n = notices.get_live("drift:cam-a")
        assert (n.source, n.summary["fields"], n.occurrences) == ("backfill", 3, 1)
        signature = da_module.drift_alerts.get_last_signature("cam-a")
        assert n.created_at == signature["updated_at"]
        assert producers.backfill_drift_notices(registry) == 0
        assert notices.get_live("drift:cam-a").occurrences == 1

    def test_a_dismissed_notice_is_not_raised_again(self, notices):
        registry = FakeRegistry({"cam-a": {"baseline_sha": "b1"}})
        self._drifted("cam-a")
        producers.backfill_drift_notices(registry)
        notices.handle(notices.get_live("drift:cam-a").id, "dismissed")
        assert producers.backfill_drift_notices(registry) == 0
        assert notices.get_live("drift:cam-a") is None

    def test_nothing_when_the_flag_is_off(self, notices, flag):
        flag.set("drift_notices_enabled", "off")
        registry = FakeRegistry({"cam-a": {"baseline_sha": "b1"}})
        self._drifted("cam-a")
        assert producers.backfill_drift_notices(registry) == 0


class TestTheFlagIsDeclared:
    def test_known_and_not_model_writable(self):
        from admz.setting_policy import KNOWN_SETTING_KEYS, LLM_WRITABLE_SETTING_KEYS
        assert "drift_notices_enabled" in KNOWN_SETTING_KEYS
        assert "drift_notices_enabled" not in LLM_WRITABLE_SETTING_KEYS
