"""Tests for the snapshot/restore/drift system."""

import logging
import os
import shutil
import subprocess
import tempfile

import pytest
import yaml

from admz.snapshot.models import (
    DeviceSnapshot,
    DriftField,
    DriftReport,
    FacetResult,
    SnapshotStatus,
)
from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
    ReadSpec,
    get_all_facets,
    get_facets_for_device,
    register_facet,
    _registry,
)
from admz.snapshot.facets.image import ImageFacet
from admz.snapshot.facets.network import NetworkFacet
from admz.snapshot.facets.time_config import TimeFacet
from admz.snapshot.facets.stream_profiles import StreamProfilesFacet
from admz.snapshot.facets.users import UsersFacet
from admz.snapshot.facets.events import EventsFacet
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.restore import RestoreBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary git repo and return a GitRepo wrapper."""
    repo_path = str(tmp_path / "config-repo")
    repo = GitRepo(repo_path)
    for key, val in [
        ("user.email", "test@test.com"),
        ("user.name", "Test"),
        ("commit.gpgsign", "false"),
    ]:
        subprocess.run(
            ["git", "config", key, val],
            cwd=repo_path, check=True,
        )
    return repo


@pytest.fixture
def sample_params():
    return {
        "root.Image.I0.Resolution": "1920x1080",
        "root.Image.I0.Compression": "30",
        "root.Image.I0.Rotation": "0",
        "root.Image.I0.Mirror": "no",
        "root.Network.eth0.IPAddress": "192.168.1.100",
        "root.Network.eth0.SubnetMask": "255.255.255.0",
        "root.Network.HostName": "axis-cam-01",
        "root.Time.ObtainFromDHCP": "yes",
        "root.Time.NTP.Server": "pool.ntp.org",
        "root.StreamProfile.S0.Name": "MainStream",
        "root.StreamProfile.S0.Parameters": "videocodec=h264",
        "root.Event.E0.Enabled": "yes",
        "root.Event.E0.Type": "motion",
        "root.Properties.API.HTTP.AdminAccess.Policy": "digest",
    }


@pytest.fixture
def camera_device_info():
    return {
        "device_id": "camera-lobby-01",
        "model": "AXIS P3245-V",
        "host": "192.168.1.100",
        "firmware": "11.8.60",
        "device_type": "camera",
        "api_family": "vapix",
        "location": "Lobby",
        "tags": ["indoor", "lobby"],
    }


# ---------------------------------------------------------------------------
# Test facet adapter framework
# ---------------------------------------------------------------------------

class TestFacetFramework:

    def test_all_builtin_facets_registered(self):
        facet_names = {cls().name for cls in get_all_facets()}
        assert "image" in facet_names
        assert "network" in facet_names
        assert "time" in facet_names
        assert "stream_profiles" in facet_names
        assert "users" in facet_names
        assert "events" in facet_names

    def test_facets_match_vapix_device(self, camera_device_info):
        facets = get_facets_for_device(camera_device_info)
        names = [f.name for f in facets]
        assert "image" in names
        assert "network" in names

    def test_facets_sorted_by_restore_order(self, camera_device_info):
        facets = get_facets_for_device(camera_device_info)
        orders = [f.restore_order for f in facets]
        assert orders == sorted(orders)

    def test_device_criteria_family_filter(self):
        info = {"api_family": "acs", "model": "AXIS Camera Station"}
        facets = get_facets_for_device(info)
        # All builtin facets require vapix, so none should match ACS
        names = [f.name for f in facets]
        assert "image" not in names

    def test_network_facet_restore_order_is_high(self):
        nf = NetworkFacet()
        assert nf.restore_order >= 80

    def test_image_facet_restore_order_is_low(self):
        imf = ImageFacet()
        assert imf.restore_order <= 40


# ---------------------------------------------------------------------------
# Test facet serialization
# ---------------------------------------------------------------------------

class TestFacetSerialization:

    def test_image_serialize(self, sample_params):
        facet = ImageFacet()
        result = facet.serialize({"params": sample_params})
        assert "I0.Resolution" in result
        assert result["I0.Resolution"] == "1920x1080"
        assert "I0.Compression" in result
        # Should NOT contain non-image params
        assert not any(k.startswith("root.") for k in result)

    def test_image_deserialize(self):
        facet = ImageFacet()
        yaml_doc = {"I0.Resolution": "1280x720", "I0.Compression": "50"}
        ops = facet.deserialize(yaml_doc)
        assert len(ops) == 1
        assert ops[0]["operation_id"] == "param.cgi:update"
        assert ops[0]["params"]["root.Image.I0.Resolution"] == "1280x720"

    def test_image_roundtrip(self, sample_params):
        facet = ImageFacet()
        normalized = facet.serialize({"params": sample_params})
        ops = facet.deserialize(normalized)
        restored_params = ops[0]["params"]
        for key, value in restored_params.items():
            assert key in sample_params
            assert sample_params[key] == value

    def test_network_serialize(self, sample_params):
        facet = NetworkFacet()
        result = facet.serialize({"params": sample_params})
        assert "eth0.IPAddress" in result
        assert result["HostName"] == "axis-cam-01"

    def test_network_deserialize(self):
        facet = NetworkFacet()
        yaml_doc = {"HostName": "new-name"}
        ops = facet.deserialize(yaml_doc)
        assert ops[0]["params"]["root.Network.HostName"] == "new-name"

    def test_time_serialize(self, sample_params):
        facet = TimeFacet()
        result = facet.serialize({"params": sample_params})
        assert "NTP.Server" in result
        assert result["NTP.Server"] == "pool.ntp.org"

    def test_stream_profiles_serialize(self, sample_params):
        facet = StreamProfilesFacet()
        result = facet.serialize({"params": sample_params})
        assert "S0.Name" in result
        assert result["S0.Name"] == "MainStream"

    def test_events_serialize(self, sample_params):
        facet = EventsFacet()
        result = facet.serialize({"params": sample_params})
        assert "event" in result
        assert "E0.Enabled" in result["event"]
        assert "E0.Type" in result["event"]

    def test_events_deserialize(self):
        facet = EventsFacet()
        ops = facet.deserialize({"event": {"E0.Enabled": "yes"}})
        assert ops[0]["params"]["root.Event.E0.Enabled"] == "yes"

    def test_users_serialize(self, sample_params):
        facet = UsersFacet()
        result = facet.serialize({"params": sample_params})
        assert "admin_access" in result

    def test_empty_params_returns_empty(self):
        facet = ImageFacet()
        result = facet.serialize({"params": {}})
        assert result == {}

    def test_users_deserialize_returns_empty(self):
        """Users can't be fully restored via param update (needs pwdgrp)."""
        facet = UsersFacet()
        assert facet.deserialize({"admin_access": {}}) == []


# ---------------------------------------------------------------------------
# Test GitRepo
# ---------------------------------------------------------------------------

class TestGitRepo:

    def test_init_creates_repo(self, tmp_repo):
        assert (tmp_repo.repo_path / ".git").exists()

    def test_no_changes_initially(self, tmp_repo):
        assert not tmp_repo.has_changes()

    def test_write_device_yaml(self, tmp_repo, camera_device_info):
        path = tmp_repo.write_device_yaml("camera-lobby-01", camera_device_info)
        assert path.exists()
        data = yaml.safe_load(open(path))
        assert data["model"] == "AXIS P3245-V"

    def test_write_facet(self, tmp_repo):
        normalized = {"I0.Resolution": "1920x1080"}
        raw = {"root.Image.I0.Resolution": "1920x1080"}
        path = tmp_repo.write_facet("cam-01", "image", normalized, raw=raw)
        assert path.exists()
        assert (tmp_repo.device_path("cam-01") / "raw" / "image.yaml").exists()

    def test_commit_snapshot(self, tmp_repo, camera_device_info):
        tmp_repo.write_device_yaml("cam-01", camera_device_info)
        sha = tmp_repo.commit_snapshot("cam-01")
        assert sha is not None
        assert len(sha) == 40

    def test_commit_no_changes_returns_none(self, tmp_repo, camera_device_info):
        tmp_repo.write_device_yaml("cam-01", camera_device_info)
        tmp_repo.commit_snapshot("cam-01")
        sha2 = tmp_repo.commit_snapshot("cam-01")
        assert sha2 is None

    def test_read_facet_after_commit(self, tmp_repo):
        normalized = {"I0.Resolution": "1920x1080", "I0.Compression": "30"}
        tmp_repo.write_facet("cam-01", "image", normalized)
        tmp_repo.commit_snapshot("cam-01")
        data = tmp_repo.read_facet("cam-01", "image")
        assert data == normalized

    def test_read_facet_nonexistent(self, tmp_repo, camera_device_info):
        tmp_repo.write_device_yaml("cam-01", camera_device_info)
        tmp_repo.commit_snapshot("cam-01")
        data = tmp_repo.read_facet("cam-01", "nonexistent")
        assert data is None

    def test_diff(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"resolution": "1080p"})
        tmp_repo.commit_snapshot("cam-01", message="v1")

        tmp_repo.write_facet("cam-01", "image", {"resolution": "4k"})
        tmp_repo.commit_snapshot("cam-01", message="v2")

        diff = tmp_repo.diff("HEAD~1", "HEAD")
        assert "1080p" in diff
        assert "4k" in diff

    def test_log(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"resolution": "1080p"})
        tmp_repo.commit_snapshot("cam-01", message="first snapshot")

        history = tmp_repo.log()
        assert len(history) == 1
        assert history[0]["message"] == "first snapshot"

    def test_list_devices(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"a": "1"})
        tmp_repo.write_facet("cam-02", "image", {"a": "2"})
        devices = tmp_repo.list_devices()
        assert devices == ["cam-01", "cam-02"]

    def test_create_tag(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"a": "1"})
        tmp_repo.commit_snapshot("cam-01")
        tmp_repo.create_tag("v1")
        assert "v1" in tmp_repo.list_tags()

    def test_fleet_snapshot_commit(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"a": "1"})
        tmp_repo.write_facet("cam-02", "image", {"b": "2"})
        sha = tmp_repo.commit_fleet_snapshot(["cam-01", "cam-02"])
        assert sha is not None
        history = tmp_repo.log()
        assert "cam-01" in history[0]["message"]
        assert "cam-02" in history[0]["message"]


# ---------------------------------------------------------------------------
# Test auto-push (snapshot → origin)
# ---------------------------------------------------------------------------
#
# Auto-push hooks the commit paths so a configured `origin` remote
# stays in sync without manual intervention. Tests use a second
# tmp git repo (bare) as the origin so we never hit the network.


@pytest.fixture
def bare_origin(tmp_path):
    """A bare git repo we can push to, used as `origin` for tmp_repo."""
    bare = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", str(bare)], check=True,
        capture_output=True,
    )
    return bare


def _set_origin(repo: GitRepo, url: str) -> None:
    subprocess.run(
        ["git", "remote", "add", "origin", url],
        cwd=repo.repo_path, check=True, capture_output=True,
    )


class TestAutoPush:
    def test_no_origin_skips_push_silently(
        self, tmp_repo, camera_device_info, monkeypatch
    ):
        # ADMZ_AUTO_PUSH defaults to ON; without origin configured
        # the push is silently skipped. The snapshot still commits.
        monkeypatch.delenv("ADMZ_AUTO_PUSH", raising=False)
        tmp_repo.write_device_yaml("cam-01", camera_device_info)
        sha = tmp_repo.commit_snapshot("cam-01")
        assert sha is not None  # commit succeeded

    def test_origin_set_pushes_after_commit(
        self, tmp_repo, bare_origin, camera_device_info, monkeypatch
    ):
        monkeypatch.delenv("ADMZ_AUTO_PUSH", raising=False)
        _set_origin(tmp_repo, str(bare_origin))
        tmp_repo.write_device_yaml("cam-01", camera_device_info)
        sha = tmp_repo.commit_snapshot("cam-01")
        assert sha is not None

        # The bare origin should now have HEAD pointing at our SHA.
        # `git rev-parse HEAD` is cheaper than `ls-remote`.
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=bare_origin, capture_output=True, text=True, check=True,
        )
        assert result.stdout.strip() == sha

    def test_env_var_false_disables_push(
        self, tmp_repo, bare_origin, camera_device_info, monkeypatch
    ):
        monkeypatch.setenv("ADMZ_AUTO_PUSH", "false")
        _set_origin(tmp_repo, str(bare_origin))
        tmp_repo.write_device_yaml("cam-01", camera_device_info)
        sha = tmp_repo.commit_snapshot("cam-01")
        assert sha is not None

        # The bare origin should NOT have the commit yet.
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=bare_origin, capture_output=True, text=True, check=False,
        )
        # Bare repo with no commits has no HEAD ref.
        assert result.returncode != 0 or result.stdout.strip() != sha

    def test_push_failure_is_non_fatal(
        self, tmp_repo, tmp_path, camera_device_info, monkeypatch, caplog
    ):
        # Point origin at a path that doesn't exist; push will fail
        # but the local commit must still succeed + return its SHA.
        monkeypatch.delenv("ADMZ_AUTO_PUSH", raising=False)
        _set_origin(tmp_repo, str(tmp_path / "does-not-exist.git"))
        tmp_repo.write_device_yaml("cam-01", camera_device_info)
        with caplog.at_level(logging.WARNING):
            sha = tmp_repo.commit_snapshot("cam-01")
        assert sha is not None  # local commit preserved
        # And a WARNING was logged
        assert any(
            "auto-push" in rec.message and "failed" in rec.message
            for rec in caplog.records
        )

    def test_fleet_commit_also_pushes(
        self, tmp_repo, bare_origin, monkeypatch
    ):
        monkeypatch.delenv("ADMZ_AUTO_PUSH", raising=False)
        _set_origin(tmp_repo, str(bare_origin))
        tmp_repo.write_facet("cam-01", "image", {"a": "1"})
        tmp_repo.write_facet("cam-02", "image", {"b": "2"})
        sha = tmp_repo.commit_fleet_snapshot(["cam-01", "cam-02"])
        assert sha is not None
        # Verify it landed on origin
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=bare_origin, capture_output=True, text=True, check=True,
        )
        assert result.stdout.strip() == sha


# ---------------------------------------------------------------------------
# Test git subprocess hardening (Hotfix #38)
# ---------------------------------------------------------------------------
#
# Background: subprocess.run on git calls without stdin=DEVNULL,
# timeout, or CREATE_NO_WINDOW (Windows) can hang for minutes when
# invoked from inside an MCP subprocess. The homelab snapshot hung
# on `git status --porcelain` — a local read-only op that should
# take ~100ms. GitRepo._run_git now defaults to a 30s local timeout
# and explicit stdin=DEVNULL.


class TestGitSubprocessHardening:
    def test_local_default_timeout_env_var(self, monkeypatch):
        from admz.snapshot.git_repo import _resolve_local_timeout
        monkeypatch.delenv("ADMZ_GIT_LOCAL_TIMEOUT_SECONDS", raising=False)
        assert _resolve_local_timeout() == 30.0
        monkeypatch.setenv("ADMZ_GIT_LOCAL_TIMEOUT_SECONDS", "10")
        assert _resolve_local_timeout() == 10.0
        monkeypatch.setenv("ADMZ_GIT_LOCAL_TIMEOUT_SECONDS", "abc")
        assert _resolve_local_timeout() == 30.0   # falls back

    def test_network_default_timeout_env_var(self, monkeypatch):
        from admz.snapshot.git_repo import _resolve_network_timeout
        monkeypatch.delenv("ADMZ_GIT_NETWORK_TIMEOUT_SECONDS", raising=False)
        assert _resolve_network_timeout() == 60.0
        monkeypatch.setenv("ADMZ_GIT_NETWORK_TIMEOUT_SECONDS", "120")
        assert _resolve_network_timeout() == 120.0

    def test_normal_git_call_succeeds(self, tmp_repo, camera_device_info):
        # Sanity: the new stdin/timeout/flags don't break normal calls.
        tmp_repo.write_device_yaml("cam-01", camera_device_info)
        sha = tmp_repo.commit_snapshot("cam-01")
        assert sha is not None

    def test_status_runs_with_devnull_stdin(self, tmp_repo):
        # `has_changes` is what hung on the homelab. Verify it works
        # with the hardened invocation (stdin=DEVNULL is implicit
        # because _run_git always sets it now).
        assert tmp_repo.has_changes() is False
        tmp_repo.write_facet("cam-01", "image", {"a": "1"})
        assert tmp_repo.has_changes() is True

    def test_timeout_kwarg_propagates(self, tmp_repo, monkeypatch):
        # _run_git's timeout kwarg should be passed through to
        # subprocess.run. Inject a probe that captures the call.
        captured = {}
        real_run = subprocess.run

        def fake_run(*args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            captured["stdin"] = kwargs.get("stdin")
            return real_run(*args, **kwargs)

        monkeypatch.setattr(subprocess, "run", fake_run)
        tmp_repo._run_git("status", "--porcelain", check=False, timeout=5.0)
        assert captured["timeout"] == 5.0
        assert captured["stdin"] == subprocess.DEVNULL

    def test_push_uses_network_timeout(
        self, tmp_repo, bare_origin, camera_device_info, monkeypatch
    ):
        # auto-push should pass the network timeout (default 60s,
        # or whatever ADMZ_GIT_NETWORK_TIMEOUT_SECONDS overrides to).
        monkeypatch.delenv("ADMZ_AUTO_PUSH", raising=False)
        monkeypatch.setenv("ADMZ_GIT_NETWORK_TIMEOUT_SECONDS", "45")
        _set_origin(tmp_repo, str(bare_origin))

        timeouts_seen: list = []
        real_run = subprocess.run

        def fake_run(*args, **kwargs):
            if args and isinstance(args[0], list) and len(args[0]) > 1 and args[0][1] == "push":
                timeouts_seen.append(kwargs.get("timeout"))
            return real_run(*args, **kwargs)

        monkeypatch.setattr(subprocess, "run", fake_run)
        tmp_repo.write_device_yaml("cam-01", camera_device_info)
        tmp_repo.commit_snapshot("cam-01")
        # At least one push happened; it should have used the 45s
        # network timeout, not the 30s local default.
        assert any(t == 45.0 for t in timeouts_seen), (
            f"expected push with timeout=45.0, got {timeouts_seen}"
        )

    def test_push_timeout_is_non_fatal(
        self, tmp_repo, bare_origin, camera_device_info, monkeypatch, caplog
    ):
        # If push times out, the local commit must still succeed +
        # return its SHA. The WARNING is logged.
        _set_origin(tmp_repo, str(bare_origin))

        real_run = subprocess.run

        def fake_run(*args, **kwargs):
            if args and isinstance(args[0], list) and len(args[0]) > 1 and args[0][1] == "push":
                # Simulate a push that hangs past the timeout.
                raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout", 0))
            return real_run(*args, **kwargs)

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.delenv("ADMZ_AUTO_PUSH", raising=False)
        tmp_repo.write_device_yaml("cam-01", camera_device_info)
        with caplog.at_level(logging.WARNING):
            sha = tmp_repo.commit_snapshot("cam-01")
        assert sha is not None   # local commit preserved
        assert any(
            "auto-push timed out" in r.message for r in caplog.records
        )


# ---------------------------------------------------------------------------
# Test RestoreBuilder
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Test RestoreBuilder
# ---------------------------------------------------------------------------

class MockCatalog:
    def get_risk_level(self, family, op_id):
        if "factorydefault" in op_id:
            return "dangerous"
        return "safe"


class MockRegistry:
    def __init__(self):
        self.devices = {
            "cam-01": {
                "model": "AXIS P3245-V",
                "host": "192.168.1.100",
                "api_family": "vapix",
            }
        }

    def get_device_info(self, device_id):
        return dict(self.devices.get(device_id, {}))

    def device_exists(self, device_id):
        return device_id in self.devices


class TestRestoreBuilder:

    def test_build_restore_plan_from_committed_config(self, tmp_repo):
        normalized = {"I0.Resolution": "1920x1080", "I0.Compression": "30"}
        tmp_repo.write_facet("cam-01", "image", normalized)
        tmp_repo.commit_snapshot("cam-01")

        builder = RestoreBuilder(
            catalog=MockCatalog(),
            registry=MockRegistry(),
            git_repo=tmp_repo,
        )
        plan = builder.build_restore_plan("cam-01")
        assert len(plan["steps"]) > 0
        assert plan["steps"][0]["operation_id"] == "param.cgi:update"
        assert plan["steps"][0]["params"]["root.Image.I0.Resolution"] == "1920x1080"

    def test_restore_plan_empty_when_no_config(self, tmp_repo):
        # Commit something to have a HEAD
        tmp_repo.write_device_yaml("cam-01", {"model": "test"})
        tmp_repo.commit_snapshot("cam-01")

        builder = RestoreBuilder(
            catalog=MockCatalog(),
            registry=MockRegistry(),
            git_repo=tmp_repo,
        )
        plan = builder.build_restore_plan("cam-01")
        # image facet has no data, so restore is empty
        # (device.yaml doesn't produce restore steps)
        assert plan["steps"] == [] or all(
            s["operation_id"] == "param.cgi:update" for s in plan["steps"]
        )

    def test_restore_plan_filters_facets(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"I0.Resolution": "1080p"})
        tmp_repo.write_facet("cam-01", "network", {"HostName": "test"})
        tmp_repo.commit_snapshot("cam-01")

        builder = RestoreBuilder(
            catalog=MockCatalog(),
            registry=MockRegistry(),
            git_repo=tmp_repo,
        )
        plan = builder.build_restore_plan("cam-01", facet_names=["image"])
        # Should only restore image, not network
        for step in plan["steps"]:
            assert "root.Image" in str(step["params"])

    def test_restore_plan_warns_on_dangerous_ops(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"I0.Resolution": "1080p"})
        tmp_repo.commit_snapshot("cam-01")

        catalog = MockCatalog()
        # Override to make param.cgi:update dangerous for testing
        catalog.get_risk_level = lambda f, op: "dangerous"

        builder = RestoreBuilder(
            catalog=catalog,
            registry=MockRegistry(),
            git_repo=tmp_repo,
        )
        plan = builder.build_restore_plan("cam-01")
        assert any("dangerous" in w for w in plan["warnings"])


# ---------------------------------------------------------------------------
# Test DeviceSnapshot model
# ---------------------------------------------------------------------------

class TestSnapshotModel:

    def test_to_summary(self):
        snap = DeviceSnapshot(
            device_id="cam-01",
            device_info={"model": "test"},
            facets=[
                FacetResult(name="image", success=True, normalized={"a": "1"}),
                FacetResult(name="network", success=False, error="timeout"),
            ],
            status=SnapshotStatus.PARTIAL,
        )
        summary = snap.to_summary()
        assert summary["device_id"] == "cam-01"
        assert summary["facets_succeeded"] == 1
        assert summary["facets_failed"] == 1
        assert "image" in summary["succeeded"]
        assert summary["failed"][0]["name"] == "network"

    def test_succeeded_and_failed_facets(self):
        snap = DeviceSnapshot(
            device_id="cam-01",
            device_info={},
            facets=[
                FacetResult(name="a", success=True),
                FacetResult(name="b", success=False, error="err"),
                FacetResult(name="c", success=True),
            ],
        )
        assert len(snap.succeeded_facets) == 2
        assert len(snap.failed_facets) == 1


# ---------------------------------------------------------------------------
# Test DriftReport model
# ---------------------------------------------------------------------------

class TestDriftReport:

    def test_to_summary(self):
        report = DriftReport(
            device_id="cam-01",
            has_drift=True,
            facets_checked=3,
            facets_drifted=1,
            fields=[
                DriftField(
                    facet="image",
                    path="I0.Resolution",
                    expected="1920x1080",
                    actual="1280x720",
                ),
            ],
        )
        summary = report.to_summary()
        assert summary["has_drift"] is True
        assert summary["facets_drifted"] == 1
        assert len(summary["drifted_fields"]) == 1
        assert summary["drifted_fields"][0]["expected"] == "1920x1080"


# ---------------------------------------------------------------------------
# Test engine helpers
# ---------------------------------------------------------------------------

class TestEngineHelpers:

    def test_parse_param_dump(self):
        from admz.snapshot.engine import _parse_param_dump
        text = (
            "root.Image.I0.Resolution=1920x1080\n"
            "root.Image.I0.Compression=30\n"
            "root.Network.HostName=axis-cam\n"
        )
        result = _parse_param_dump(text)
        assert result["root.Image.I0.Resolution"] == "1920x1080"
        assert result["root.Network.HostName"] == "axis-cam"

    def test_parse_param_dump_filters_volatile(self):
        from admz.snapshot.engine import _parse_param_dump
        text = (
            "root.Image.I0.Resolution=1920x1080\n"
            "root.Properties.System.Soc.Temperature=45\n"
        )
        result = _parse_param_dump(text)
        assert "root.Image.I0.Resolution" in result
        assert "root.Properties.System.Soc.Temperature" not in result

    def test_parse_param_dump_filters_sensitive(self):
        from admz.snapshot.engine import _parse_param_dump
        text = (
            "root.Image.I0.Resolution=1920x1080\n"
            "root.HTTPS.PrivateKey=SECRET_DATA\n"
        )
        result = _parse_param_dump(text)
        assert "root.Image.I0.Resolution" in result
        assert "root.HTTPS.PrivateKey" not in result

    def test_parse_param_dump_skips_comments(self):
        from admz.snapshot.engine import _parse_param_dump
        text = "# comment\nroot.Image.I0.Resolution=1920x1080\n"
        result = _parse_param_dump(text)
        assert "root.Image.I0.Resolution" in result
        assert len(result) == 1
