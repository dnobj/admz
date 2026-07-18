"""Demo-owned config fragments — storage + validation (ADR-0047, slice 1).

The fragment is inert data in this slice: captured, versioned, displayed —
never read by drift and never pushed. These tests pin the storage roundtrip
(real git repo) and the capture-time validation matrix.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field as dc_field

import pytest

from admz.demos import fragments as fr
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.models import DriftField


@pytest.fixture
def repo(tmp_path):
    repo_path = str(tmp_path / "config-repo")
    r = GitRepo(repo_path)
    for key, val in [("user.email", "t@t"), ("user.name", "T"),
                     ("commit.gpgsign", "false")]:
        subprocess.run(["git", "config", key, val], cwd=repo_path, check=True)
    return r


@dataclass
class _Demo:
    id: str = "abc123def456"
    name: str = "Loitering"


# ---------------------------------------------------------------------------
# Paths + roles
# ---------------------------------------------------------------------------


class TestPathsAndRoles:
    def test_rel_path(self):
        assert fr.fragment_rel_path("abc123", "detector") == \
            "demos/abc123/roles/detector.yaml"

    def test_role_normalization(self):
        assert fr.normalize_role("Front Door") == "front-door"
        assert fr.normalize_role("  detector ") == "detector"
        assert fr.normalize_role("") == "default"
        assert fr.normalize_role(None) == "default"
        assert fr.normalize_role("a/b\\c") == "a-b-c"

    def test_traversal_rejected(self):
        with pytest.raises(ValueError):
            fr.fragment_rel_path("../evil", "role")
        with pytest.raises(ValueError):
            fr.fragment_rel_path("abc123", "../../evil")


class TestGenericWriter:
    def test_write_yaml_escapes_blocked(self, repo):
        with pytest.raises(ValueError):
            repo.write_yaml("../outside.yaml", {"a": 1})

    def test_write_and_remove(self, repo):
        p = repo.write_yaml("demos/x/roles/r.yaml", {"a": "1"})
        assert p.exists()
        assert repo.remove_path("demos/x") is True
        assert not p.exists()
        assert repo.remove_path("demos/x") is False  # already gone


# ---------------------------------------------------------------------------
# Storage roundtrip
# ---------------------------------------------------------------------------


class TestFragmentStore:
    def test_add_load_roundtrip(self, repo):
        demo = _Demo()
        sha = fr.add_entries(repo, demo, "detector", [
            {"facet": "other", "path": "Motion.M0.Enabled", "value": "yes"},
            {"facet": "image", "path": "Appearance.Resolution", "value": "1920x1080"},
        ])
        assert sha  # committed
        got = fr.load_fragment(repo, demo.id, "detector")
        assert got["other"]["set"]["Motion.M0.Enabled"] == "yes"
        assert got["image"]["set"]["Appearance.Resolution"] == "1920x1080"
        assert fr.list_roles(repo, demo.id) == ["detector"]
        counts = fr.fragment_entry_count(got)
        assert counts == {"set": 2, "require": 0}

    def test_values_stored_as_strings(self, repo):
        # flatten stringifies — a YAML-native bool would round-trip wrong.
        demo = _Demo()
        fr.add_entries(repo, demo, "r", [
            {"facet": "other", "path": "K", "value": True},
        ])
        got = fr.load_fragment(repo, demo.id, "r")
        assert got["other"]["set"]["K"] == "True"
        assert isinstance(got["other"]["set"]["K"], str)

    def test_idempotent_add_is_no_commit(self, repo):
        demo = _Demo()
        e = [{"facet": "other", "path": "K", "value": "v"}]
        assert fr.add_entries(repo, demo, "r", e)
        assert fr.add_entries(repo, demo, "r", e) is None  # unchanged

    def test_require_mode_kept_separate(self, repo):
        demo = _Demo()
        fr.add_entries(repo, demo, "r",
                       [{"facet": "other", "path": "A", "value": "1"}], mode="set")
        fr.add_entries(repo, demo, "r",
                       [{"facet": "other", "path": "B", "value": "2"}], mode="require")
        got = fr.load_fragment(repo, demo.id, "r")
        assert got["other"]["set"] == {"A": "1"}
        assert got["other"]["require"] == {"B": "2"}

    def test_remove_entries_and_empty_cleanup(self, repo):
        demo = _Demo()
        fr.add_entries(repo, demo, "r", [
            {"facet": "other", "path": "A", "value": "1"},
            {"facet": "other", "path": "B", "value": "2"},
        ])
        assert fr.remove_entries(repo, demo, "r", [{"facet": "other", "path": "A"}])
        got = fr.load_fragment(repo, demo.id, "r")
        assert "A" not in got["other"]["set"] and "B" in got["other"]["set"]
        # Removing the last entry deletes the file entirely.
        assert fr.remove_entries(repo, demo, "r", [{"facet": "other", "path": "B"}])
        assert fr.load_fragment(repo, demo.id, "r") == {}
        assert fr.list_roles(repo, demo.id) == []

    def test_delete_demo_fragments(self, repo):
        demo = _Demo()
        fr.add_entries(repo, demo, "a", [{"facet": "other", "path": "K", "value": "v"}])
        fr.add_entries(repo, demo, "b", [{"facet": "other", "path": "K", "value": "v"}])
        assert fr.delete_demo_fragments(repo, demo.id, demo.name)
        assert fr.load_all_fragments(repo, demo.id) == {}
        # History still has it — read the file at the pre-delete commit.
        log = repo._run_git("log", "--oneline").stdout
        assert "assign 1 key" in log

    def test_multiple_roles(self, repo):
        demo = _Demo()
        fr.add_entries(repo, demo, "detector", [{"facet": "other", "path": "A", "value": "1"}])
        fr.add_entries(repo, demo, "responder", [{"facet": "audio", "path": "B", "value": "2"}])
        allf = fr.load_all_fragments(repo, demo.id)
        assert set(allf) == {"detector", "responder"}

    def test_malformed_fragment_reads_empty(self, repo):
        demo = _Demo()
        path = repo._safe_rel_path(fr.fragment_rel_path(demo.id, "r"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not: valid: yaml: [")
        assert fr.load_fragment(repo, demo.id, "r") == {}


# ---------------------------------------------------------------------------
# Capture-time validation matrix
# ---------------------------------------------------------------------------


class _FakeParamFacet:
    """revert_param accepts anything (like CatchAllParamsFacet)."""

    def canonical_key(self, path):
        return f"root.{path}"

    def revert_param(self, path, value):
        return (f"root.{path}", str(value))


class _ReadOnlyFacet:
    def canonical_key(self, path):
        return f"snap:{path}"

    def revert_param(self, path, value):
        return None


def _field(path="Motion.M0.Enabled", expected="no", actual="yes",
           canonical=None, facet="other"):
    return DriftField(facet=facet, path=path, expected=expected, actual=actual,
                      canonical_key=canonical or f"root.{path}")


_DEV = {"device_id": "cam-1", "ip_address": "192.0.2.55", "host": "192.0.2.55",
        "mac_address": "B8:A4:4F:11:22:33", "serial_number": "B8A44F112233",
        "tags": []}


class TestValidateAssignment:
    def test_writable_present_key_is_ok(self):
        ok, reason, warns = fr.validate_assignment(
            _field(), _FakeParamFacet(), "set", _DEV)
        assert ok and not warns

    def test_missing_from_baseline_rejected(self):
        # param.cgi can't CREATE keys — the demo must override, not invent.
        ok, reason, _ = fr.validate_assignment(
            _field(expected=fr.MISSING), _FakeParamFacet(), "set", _DEV)
        assert not ok and reason == "not-in-baseline"

    def test_read_only_facet_rejected_for_set(self):
        ok, reason, _ = fr.validate_assignment(
            _field(), _ReadOnlyFacet(), "set", _DEV)
        assert not ok and reason == "read-only"

    def test_read_only_facet_fine_for_require(self):
        # require is never pushed, so writability doesn't matter.
        ok, reason, _ = fr.validate_assignment(
            _field(), _ReadOnlyFacet(), "require", _DEV)
        assert ok

    def test_unknown_facet_rejected_for_set(self):
        ok, reason, _ = fr.validate_assignment(_field(), None, "set", _DEV)
        assert not ok and reason == "read-only"

    def test_ignored_key_rejected(self, monkeypatch):
        # Drift filters ignored keys before compare — an ignored fragment key
        # would never be verified.
        monkeypatch.setattr("admz.snapshot.ignore.applicable_rules",
                            lambda did, tags=None: [{"key": "x", "scope": "global"}])
        monkeypatch.setattr("admz.snapshot.ignore.is_ignored",
                            lambda k, device_id=None, tags=None, rules=None: True)
        ok, reason, _ = fr.validate_assignment(
            _field(), _FakeParamFacet(), "set", _DEV)
        assert not ok and reason == "ignored"

    def test_unknown_mode_rejected(self):
        ok, reason, _ = fr.validate_assignment(
            _field(), _FakeParamFacet(), "delete", _DEV)
        assert not ok

    def test_device_local_value_warns_but_allows(self):
        ok, _, warns = fr.validate_assignment(
            _field(path="Recipient.R0.URL",
                   actual="http://192.0.2.55/notify", expected="http://x/"),
            _FakeParamFacet(), "set", _DEV)
        assert ok
        assert warns and "ip" in warns[0]

    def test_bare_mac_in_value_detected(self):
        hits = fr.device_local_hits("hostname-b8a44f112233", _DEV)
        assert "mac" in hits or "serial" in hits

    def test_clean_value_no_hits(self):
        assert fr.device_local_hits("1920x1080", _DEV) == []


# ---------------------------------------------------------------------------
# Attribution (slice 2): overlay + buckets in the REAL drift detector
# ---------------------------------------------------------------------------

from admz.demos.store import Demo
from admz.snapshot.drift import DriftDetector
from admz.snapshot.drift_alerts import DriftAlertStore, _attributed_counts


class _FakeDemoStore:
    def __init__(self, demos):
        self._demos = demos

    def list(self):
        return list(self._demos)


class _FakeRegistry:
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

    def set_config_pointers(self, device_id, **kwargs):
        pass


def _engine(registry, live_params):
    # git_repo=None on purpose: with a repo, check_drift commits an Audit
    # observation FIRST, which moves HEAD — and these tests pin the baseline
    # at "HEAD", so the compare would see live == baseline. Same convention
    # as tests/test_drift.py.
    from admz.snapshot.engine import SnapshotEngine

    class _E(SnapshotEngine):
        def __init__(self):
            super().__init__(catalog=None, registry=registry, executors={},
                             git_repo=None)

        async def _read_all_params(self, device_id, device_info, family):
            return dict(live_params)

        async def _read_extra_ops(self, device_id, device_info, facets, family):
            return {}

    return _E()


def _demo_with_fragment(repo, *, name="Loitering", device_ids=("cam-01",),
                        active=True, value="3840x2160"):
    demo = Demo(id="d" + name.lower()[:10], name=name,
                device_ids=list(device_ids), active=active)
    fr.add_entries(repo, demo, "default",
                   [{"facet": "image", "path": "I0.Resolution", "value": value}])
    return demo


BASE = {"I0.Resolution": "1920x1080", "I0.Compression": "30"}
LIVE_KEY = "root.Image.I0.Resolution"


def _setup(repo, live_res, demos, *, scenario=None):
    repo.write_facet("cam-01", "image", dict(BASE))
    repo.commit_snapshot("cam-01")
    info = {"host": "192.0.2.9", "api_family": "vapix", "baseline_sha": "HEAD"}
    if scenario:
        info["active_scenario"] = scenario
    registry = _FakeRegistry({"cam-01": info})
    live = {LIVE_KEY: live_res, "root.Image.I0.Compression": "30"}
    detector = DriftDetector(
        _engine(registry, live), repo, demo_store=_FakeDemoStore(demos))
    return detector


class TestDriftAttribution:
    @pytest.mark.asyncio
    async def test_demo_set_is_deliberate_not_drift(self, repo):
        demo = _demo_with_fragment(repo, active=True)
        detector = _setup(repo, "3840x2160", [demo])
        report = await detector.check_drift("cam-01")
        assert report.has_drift is False        # fully explained
        assert report.real_fields == []
        [f] = report.fields
        assert f.bucket == "demo_set"
        assert f.owner == demo.id and f.owner_name == "Loitering"
        assert f.expected == "1920x1080"        # base value, for display
        assert f.actual == "3840x2160"

    @pytest.mark.asyncio
    async def test_demo_broken_when_live_differs_from_demo(self, repo):
        demo = _demo_with_fragment(repo, active=True)
        detector = _setup(repo, "1280x720", [demo])   # neither base nor demo
        report = await detector.check_drift("cam-01")
        assert report.has_drift is True
        [f] = report.fields
        assert f.bucket == "demo_broken"
        assert f.expected == "3840x2160"        # the DEMO value: revert repairs
        assert f.actual == "1280x720"

    @pytest.mark.asyncio
    async def test_demo_broken_when_fragment_not_loaded(self, repo):
        # Live still equals base: a plain compare sees nothing, but the active
        # demo needs its key loaded -> drift AGAINST the demo.
        demo = _demo_with_fragment(repo, active=True)
        detector = _setup(repo, "1920x1080", [demo])
        report = await detector.check_drift("cam-01")
        [f] = report.fields
        assert f.bucket == "demo_broken"
        assert f.expected == "3840x2160" and f.actual == "1920x1080"

    @pytest.mark.asyncio
    async def test_candidate_when_inactive_demo_matches(self, repo):
        demo = _demo_with_fragment(repo, active=False)
        detector = _setup(repo, "3840x2160", [demo])
        report = await detector.check_drift("cam-01")
        assert report.has_drift is True          # still real drift
        [f] = report.fields
        assert f.bucket == "candidate"
        assert f.candidates == [{"id": demo.id, "name": "Loitering"}]

    @pytest.mark.asyncio
    async def test_unclaimed_when_nothing_matches(self, repo):
        demo = _demo_with_fragment(repo, active=False)  # demo wants 4K
        detector = _setup(repo, "1280x720", [demo])     # live is neither
        report = await detector.check_drift("cam-01")
        [f] = report.fields
        assert f.bucket == "unclaimed" and f.candidates == []

    @pytest.mark.asyncio
    async def test_legacy_scenario_partition_skips_overlay(self, repo):
        # A device held by an ADR-0044 scenario keeps its semantics: no
        # attribution at all until the scenario ends.
        demo = _demo_with_fragment(repo, active=True)
        detector = _setup(repo, "3840x2160", [demo], scenario="night-mode")
        report = await detector.check_drift("cam-01")
        [f] = report.fields
        assert f.bucket == "unclaimed" and f.owner is None

    @pytest.mark.asyncio
    async def test_out_of_scope_demo_is_invisible(self, repo):
        demo = _demo_with_fragment(repo, active=True, device_ids=("other-cam",))
        detector = _setup(repo, "3840x2160", [demo])
        report = await detector.check_drift("cam-01")
        [f] = report.fields
        assert f.bucket == "unclaimed"

    @pytest.mark.asyncio
    async def test_no_demo_store_means_no_attribution(self, repo):
        repo.write_facet("cam-01", "image", dict(BASE))
        repo.commit_snapshot("cam-01")
        registry = _FakeRegistry({"cam-01": {
            "host": "192.0.2.9", "api_family": "vapix", "baseline_sha": "HEAD"}})
        detector = DriftDetector(
            _engine(registry, {LIVE_KEY: "3840x2160",
                               "root.Image.I0.Compression": "30"}), repo)
        report = await detector.check_drift("cam-01")
        [f] = report.fields
        assert f.bucket == "unclaimed"


class TestAttributedSignature:
    def _report(self, repo, live, demos):
        import asyncio

        detector = _setup(repo, live, demos)
        return asyncio.new_event_loop().run_until_complete(
            detector.check_drift("cam-01"))

    def test_field_count_is_unclaimed_only(self, repo, tmp_path):
        demo = _demo_with_fragment(repo, active=True)
        report = self._report(repo, "3840x2160", [demo])   # fully demo-explained
        store = DriftAlertStore(str(tmp_path / "alerts.db"))
        store.process_report(report)
        sig = store.get_last_signature("cam-01")
        assert sig["field_count"] == 0                     # roster reads in-sync
        assert sig["attributed"]["demo_set"] == 1
        assert sig["attributed"]["by_demo"] == {}

    def test_by_demo_counts_broken_keys(self, repo, tmp_path):
        demo = _demo_with_fragment(repo, active=True)
        report = self._report(repo, "1280x720", [demo])
        counts = _attributed_counts(report)
        assert counts["by_demo"] == {demo.id: 1}
        assert counts["demo_names"][demo.id] == "Loitering"
        store = DriftAlertStore(str(tmp_path / "alerts.db"))
        store.process_report(report)
        assert store.get_last_signature("cam-01")["field_count"] == 1

    def test_adopt_transition_changes_signature_once(self, repo, tmp_path):
        # Same live state, demo inactive -> active: the signature must change
        # (deliberate transition), then stay stable on the next check.
        demo = _demo_with_fragment(repo, active=False)
        store = DriftAlertStore(str(tmp_path / "alerts.db"))
        store.process_report(self._report(repo, "3840x2160", [demo]))
        s1 = store.get_last_signature("cam-01")["signature"]
        demo.active = True
        store.process_report(self._report(repo, "3840x2160", [demo]))
        s2 = store.get_last_signature("cam-01")["signature"]
        assert s1 != s2
        store.process_report(self._report(repo, "3840x2160", [demo]))
        assert store.get_last_signature("cam-01")["signature"] == s2
