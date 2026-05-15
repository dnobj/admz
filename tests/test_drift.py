"""Tests for the drift detector + restore profile path."""

import subprocess

import pytest
import yaml

from admz.snapshot.drift import DriftDetector, _flatten
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.restore import RestoreBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_repo(tmp_path):
    repo_path = str(tmp_path / "config-repo")
    repo = GitRepo(repo_path)
    for key, val in [
        ("user.email", "test@test.com"),
        ("user.name", "Test"),
        ("commit.gpgsign", "false"),
    ]:
        subprocess.run(
            ["git", "config", key, val], cwd=repo_path, check=True
        )
    return repo


class FakeRegistry:
    def __init__(self, devices):
        self.devices = devices

    def get_device_info(self, device_id):
        return dict(self.devices.get(device_id, {}))

    def device_exists(self, device_id):
        return device_id in self.devices

    def list_devices(self):
        return [
            {**info, "device_id": did} for did, info in self.devices.items()
        ]

    def get_credentials(self, device_id, account_id="default", requester=None):
        return {"username": "x", "password": "y"}


class FakeCatalog:
    def get_operation(self, family, op_id):
        return None

    def get_risk_level(self, family, op_id):
        return "normal"


class FakeSnapshotEngine:
    """Stub that provides _read_all_params and _read_extra_ops without
    actually hitting devices. The drift detector uses these."""

    def __init__(self, registry, live_params=None):
        self.registry = registry
        self.live_params = live_params or {}

    async def _read_all_params(self, device_id, device_info, family):
        return dict(self.live_params)

    async def _read_extra_ops(self, device_id, device_info, facets, family):
        return {}


# ---------------------------------------------------------------------------
# _flatten helper
# ---------------------------------------------------------------------------

class TestFlatten:

    def test_flat_dict(self):
        assert _flatten({"a": "1", "b": "2"}) == {"a": "1", "b": "2"}

    def test_nested_dict(self):
        result = _flatten({"event": {"E0.Enabled": "yes"}})
        assert result == {"event.E0.Enabled": "yes"}

    def test_deeply_nested(self):
        result = _flatten({"a": {"b": {"c": "v"}}})
        assert result == {"a.b.c": "v"}

    def test_stringifies_values(self):
        result = _flatten({"count": 5, "enabled": True})
        assert result["count"] == "5"
        assert result["enabled"] == "True"

    def test_empty_dict(self):
        assert _flatten({}) == {}


# ---------------------------------------------------------------------------
# DriftDetector
# ---------------------------------------------------------------------------

class TestDriftDetector:

    @pytest.mark.asyncio
    async def test_no_drift_when_live_matches_git(self, tmp_repo):
        # Set up: git has image config that matches live
        tmp_repo.write_facet("cam-01", "image", {"I0.Resolution": "1920x1080"})
        tmp_repo.commit_snapshot("cam-01")

        registry = FakeRegistry({
            "cam-01": {"host": "1.2.3.4", "api_family": "vapix"}
        })
        engine = FakeSnapshotEngine(
            registry,
            live_params={"root.Image.I0.Resolution": "1920x1080"},
        )
        detector = DriftDetector(engine, tmp_repo)
        report = await detector.check_drift("cam-01")

        assert report.has_drift is False
        assert report.facets_drifted == 0
        assert report.fields == []

    @pytest.mark.asyncio
    async def test_drift_when_live_differs_from_git(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"I0.Resolution": "1920x1080"})
        tmp_repo.commit_snapshot("cam-01")

        registry = FakeRegistry({
            "cam-01": {"host": "1.2.3.4", "api_family": "vapix"}
        })
        engine = FakeSnapshotEngine(
            registry,
            live_params={"root.Image.I0.Resolution": "1280x720"},
        )
        detector = DriftDetector(engine, tmp_repo)
        report = await detector.check_drift("cam-01")

        assert report.has_drift is True
        assert report.facets_drifted == 1
        assert len(report.fields) == 1
        field = report.fields[0]
        assert field.facet == "image"
        assert field.expected == "1920x1080"
        assert field.actual == "1280x720"

    @pytest.mark.asyncio
    async def test_drift_when_param_missing_from_live(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"I0.Resolution": "1920x1080"})
        tmp_repo.commit_snapshot("cam-01")

        registry = FakeRegistry({
            "cam-01": {"host": "1.2.3.4", "api_family": "vapix"}
        })
        engine = FakeSnapshotEngine(registry, live_params={})
        detector = DriftDetector(engine, tmp_repo)
        report = await detector.check_drift("cam-01")

        assert report.has_drift is True
        assert report.fields[0].actual == "<missing>"

    @pytest.mark.asyncio
    async def test_facets_with_no_git_state_are_skipped(self, tmp_repo):
        """If a facet has no committed YAML, it's not checked at all."""
        # No commits at all
        registry = FakeRegistry({
            "cam-01": {"host": "1.2.3.4", "api_family": "vapix"}
        })
        engine = FakeSnapshotEngine(
            registry,
            live_params={"root.Image.I0.Resolution": "1920x1080"},
        )
        detector = DriftDetector(engine, tmp_repo)
        report = await detector.check_drift("cam-01")

        assert report.facets_checked == 0
        assert report.has_drift is False

    @pytest.mark.asyncio
    async def test_multi_facet_drift(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"I0.Resolution": "1920x1080"})
        tmp_repo.write_facet("cam-01", "network", {"HostName": "axis-cam"})
        tmp_repo.commit_snapshot("cam-01")

        registry = FakeRegistry({
            "cam-01": {"host": "1.2.3.4", "api_family": "vapix"}
        })
        engine = FakeSnapshotEngine(
            registry,
            live_params={
                "root.Image.I0.Resolution": "1920x1080",  # same
                "root.Network.HostName": "renamed-cam",   # drifted
            },
        )
        detector = DriftDetector(engine, tmp_repo)
        report = await detector.check_drift("cam-01")

        assert report.has_drift is True
        assert report.facets_checked == 2
        assert report.facets_drifted == 1
        assert all(f.facet == "network" for f in report.fields)

    @pytest.mark.asyncio
    async def test_fleet_drift_returns_per_device_reports(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"I0.Resolution": "1920x1080"})
        tmp_repo.write_facet("cam-02", "image", {"I0.Resolution": "1280x720"})
        tmp_repo.commit_snapshot("fleet")

        registry = FakeRegistry({
            "cam-01": {"host": "1.2.3.4", "api_family": "vapix"},
            "cam-02": {"host": "1.2.3.5", "api_family": "vapix"},
        })
        engine = FakeSnapshotEngine(
            registry,
            # Same live state for both; cam-01 matches, cam-02 drifts
            live_params={"root.Image.I0.Resolution": "1920x1080"},
        )
        detector = DriftDetector(engine, tmp_repo)
        reports = await detector.check_fleet_drift()

        assert len(reports) == 2
        by_id = {r.device_id: r for r in reports}
        assert by_id["cam-01"].has_drift is False
        assert by_id["cam-02"].has_drift is True


# ---------------------------------------------------------------------------
# RestoreBuilder.build_profile_plan
# ---------------------------------------------------------------------------

class TestRestoreBuilderProfile:

    def test_profile_plan_applies_baseline_to_device(self, tmp_repo):
        # Create a shared profile in the repo
        profile_dir = tmp_repo.repo_path / "profiles" / "lobby-baseline" / "config"
        profile_dir.mkdir(parents=True)
        with open(profile_dir / "image.yaml", "w") as f:
            yaml.dump({"I0.Resolution": "1920x1080"}, f)
        tmp_repo.commit_snapshot("profile-setup")

        registry = FakeRegistry({
            "cam-01": {"host": "1.2.3.4", "api_family": "vapix"}
        })
        builder = RestoreBuilder(
            catalog=FakeCatalog(),
            registry=registry,
            git_repo=tmp_repo,
        )
        plan = builder.build_profile_plan("cam-01", "lobby-baseline")

        assert plan["steps"]
        assert plan["steps"][0]["operation_id"] == "param.cgi:update"
        assert (
            plan["steps"][0]["params"]["root.Image.I0.Resolution"] == "1920x1080"
        )

    def test_profile_plan_empty_when_profile_missing(self, tmp_repo):
        # Need a HEAD for git operations
        tmp_repo.write_device_yaml("cam-01", {"host": "x"})
        tmp_repo.commit_snapshot("init")

        registry = FakeRegistry({
            "cam-01": {"host": "1.2.3.4", "api_family": "vapix"}
        })
        builder = RestoreBuilder(
            catalog=FakeCatalog(),
            registry=registry,
            git_repo=tmp_repo,
        )
        plan = builder.build_profile_plan("cam-01", "nonexistent-profile")

        assert plan["steps"] == []

    def test_profile_plan_overrides_specific_fields(self, tmp_repo):
        profile_dir = tmp_repo.repo_path / "profiles" / "lobby-baseline" / "config"
        profile_dir.mkdir(parents=True)
        with open(profile_dir / "network.yaml", "w") as f:
            yaml.dump({"HostName": "default-name"}, f)
        tmp_repo.commit_snapshot("profile-setup")

        registry = FakeRegistry({
            "cam-01": {"host": "1.2.3.4", "api_family": "vapix"}
        })
        builder = RestoreBuilder(
            catalog=FakeCatalog(),
            registry=registry,
            git_repo=tmp_repo,
        )
        plan = builder.build_profile_plan(
            "cam-01",
            "lobby-baseline",
            overrides={"HostName": "device-specific-name"},
        )

        # The override should replace the profile's value
        assert (
            plan["steps"][0]["params"]["root.Network.HostName"]
            == "device-specific-name"
        )
