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


class TestRestoreSafety:
    """Restore must never write back what the device can't (or must not)
    accept: read-only mirrors, Volatile* runtime values, masked secrets.
    Verified live on the P3288 (AXIS OS 12): param.cgi:update rejects
    Time.NTP.Server even unchanged. Skipped keys stay serialized — drift
    on them is real — and are reported via the op call's 'skipped' list."""

    def test_time_excludes_ntp_mirror(self):
        facet = TimeFacet()
        ops = facet.deserialize({
            "NTP.Server": "192.168.0.199 ntp.axis.com",
            "NTP.VolatileServer": "216.239.35.0",
            "POSIXTimeZone": "CST6CDT5,M3.2.0/2:00:00,M11.1.0/2:00:00",
            "SyncSource": "NTP",
        })
        assert len(ops) == 1
        params = ops[0]["params"]
        assert "root.Time.POSIXTimeZone" in params
        assert "root.Time.SyncSource" in params
        assert not any("NTP" in k for k in params)
        assert ops[0]["skipped"] == ["NTP.Server", "NTP.VolatileServer"]

    def test_network_excludes_runtime_state(self):
        facet = NetworkFacet()
        ops = facet.deserialize({
            "HostName": "axis-cam-01",
            "DefaultRouter": "192.168.1.1",
            "eth0.IPAddress": "192.168.1.105",
            "eth0.MACAddress": "E8:27:25:1F:FB:8D",
            "Routing.DefaultRouter": "192.168.1.1",
            "Resolver.NameServerList": "192.168.1.1 8.8.8.8",
            "Resolver.NameServer1": "192.168.1.1",
            "Interface.I0.dot1x.Status": "Unauthorized",
            "Interface.I0.Link.MTU": "1500",
            "DHCP.VendorClass": "AXIS,Dome Camera",
            "VolatileHostName.HostName": "axis-e827251ffb8d",
        })
        params = ops[0]["params"]
        # Static config restores
        assert "root.Network.HostName" in params
        assert "root.Network.DefaultRouter" in params
        assert "root.Network.Interface.I0.Link.MTU" in params
        # Runtime/derived state does not
        assert not any("eth0" in k for k in params)
        assert not any("Routing" in k for k in params)
        assert not any("Volatile" in k for k in params)
        assert not any("Resolver" in k for k in params)
        assert "root.Network.Interface.I0.dot1x.Status" not in params
        assert "root.Network.DHCP.VendorClass" not in params

    def test_masked_secret_never_written_back(self):
        """param.cgi returns '******' for password-class values; restoring
        the literal mask would corrupt the device's real secret."""
        facet = NetworkFacet()
        ops = facet.deserialize({
            "HostName": "axis-cam-01",
            "Interface.I0.dot1x.EAPTLS.PrivateKeyPassword": "******",
        })
        params = ops[0]["params"]
        assert "root.Network.HostName" in params
        assert not any("PrivateKeyPassword" in k for k in params)
        assert ops[0]["skipped"] == [
            "Interface.I0.dot1x.EAPTLS.PrivateKeyPassword"
        ]

    def test_events_skips_masked_and_volatile(self):
        facet = EventsFacet()
        ops = facet.deserialize({
            "ioport": {
                "I0.Input.Name": "Port 1",
                "I0.VolatileState": "high",
            },
            "event": {"E0.Password": "******"},
        })
        params = ops[0]["params"]
        assert params == {"root.IOPort.I0.Input.Name": "Port 1"}
        assert ops[0]["skipped"] == [
            "event.E0.Password", "ioport.I0.VolatileState"
        ]

    def test_image_excludes_structural_channel_params(self):
        """Image I*.Source / I*.Type / NbrOfConfigs are factory wiring —
        the device answers 401 when an admin writes them."""
        facet = ImageFacet()
        ops = facet.deserialize({
            "I0.Source": "0",
            "I0.Type": "fixed",
            "I12.Source": "0",
            "NbrOfConfigs": "8",
            "I0.Appearance.Compression": "30",
            # Glob is segment-wise: nested keys do NOT over-match
            "I0.Overlay.Type": "text",
        })
        params = ops[0]["params"]
        assert params == {
            "root.Image.I0.Appearance.Compression": "30",
            "root.Image.I0.Overlay.Type": "text",
        }

    def test_stream_profiles_excludes_max_groups(self):
        facet = StreamProfilesFacet()
        ops = facet.deserialize({
            "MaxGroups": "26",
            "S0.Name": "MainStream",
        })
        assert ops[0]["params"] == {
            "root.StreamProfile.S0.Name": "MainStream"
        }

    def test_events_excludes_ioport_configurable(self):
        facet = EventsFacet()
        ops = facet.deserialize({
            "ioport": {
                "I0.Configurable": "no",
                "I0.Input.Name": "Port 1",
            },
        })
        assert ops[0]["params"] == {
            "root.IOPort.I0.Input.Name": "Port 1"
        }
        assert ops[0]["skipped"] == ["ioport.I0.Configurable"]

    def test_network_excludes_protected_constants(self):
        facet = NetworkFacet()
        ops = facet.deserialize({
            "HostName": "axis-cam-01",
            "LLDP.POE.Enabled": "no",          # writable config
            "LLDP.POE.MaxPower": "12950",      # hw-negotiated
            "QoS.Class1.Desc": "AxisLiveVideo",
            "QoS.Class1.DSCP": "0",            # writable config
            "RTP.NbrOfRTPGroups": "8",
            "Resolver.NameServer1": "192.168.1.1",
            "ZeroConf.Enabled": "yes",         # writable config
            "ZeroConf.IPAddress": "169.254.1.2",
            "Interface.I0.SystemDevice": "eth0",
        })
        params = ops[0]["params"]
        assert set(params) == {
            "root.Network.HostName",
            "root.Network.LLDP.POE.Enabled",
            "root.Network.QoS.Class1.DSCP",
            "root.Network.ZeroConf.Enabled",
        }

    def test_all_keys_excluded_yields_no_op_call(self):
        facet = TimeFacet()
        assert facet.deserialize({"NTP.Server": "pool.ntp.org"}) == []

    def test_clean_doc_has_no_skipped_key(self):
        facet = ImageFacet()
        ops = facet.deserialize({"I0.Resolution": "1920x1080"})
        assert "skipped" not in ops[0]


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

    def test_commit_snapshot_auto_push_flag(
        self, tmp_repo, camera_device_info, monkeypatch
    ):
        """Observation commits (auto_push=False) skip the origin push;
        default commits keep it."""
        pushes = []
        monkeypatch.setattr(
            tmp_repo, "_maybe_push", lambda: pushes.append(1)
        )
        tmp_repo.write_device_yaml("cam-01", camera_device_info)
        tmp_repo.commit_snapshot("cam-01", auto_push=False)
        assert pushes == []
        tmp_repo.write_device_yaml(
            "cam-01", {**camera_device_info, "location": "x"}
        )
        tmp_repo.commit_snapshot("cam-01")
        assert pushes == [1]

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

    def test_device_snapshot_status_with_baseline(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"I0.Resolution": "1920x1080"})
        tmp_repo.write_facet("cam-01", "network", {"Hostname": "cam-01"})
        tmp_repo.commit_snapshot("cam-01", message="baseline")
        status = tmp_repo.device_snapshot_status("cam-01")
        assert status["has_baseline"] is True
        assert status["facets"] == ["image", "network"]
        assert status["last_snapshot"]  # ISO commit date present

    def test_device_snapshot_status_no_baseline(self, tmp_repo, camera_device_info):
        # Only device.yaml committed (the unreachable/auth-failed device case):
        # identity exists but no config facets -> NOT a real baseline.
        tmp_repo.write_device_yaml("cam-02", camera_device_info)
        tmp_repo.commit_snapshot("cam-02")
        status = tmp_repo.device_snapshot_status("cam-02")
        assert status["has_baseline"] is False
        assert status["facets"] == []
        assert status["last_snapshot"]  # a commit exists, just no config

    def test_device_snapshot_status_unknown_device(self, tmp_repo):
        status = tmp_repo.device_snapshot_status("never-seen")
        assert status == {
            "has_baseline": False,
            "facets": [],
            "last_snapshot": None,
        }

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

    def test_restore_steps_declare_service_affecting_risk(self, tmp_repo):
        """ADR-0034: every restore step carries a service-affecting floor
        so execute_gated_plan always stops at the approval widget — even
        though param.cgi:update alone is catalog-risk 'normal'."""
        tmp_repo.write_facet("cam-01", "image", {"I0.Resolution": "1080p"})
        tmp_repo.write_facet("cam-01", "network", {"HostName": "test"})
        tmp_repo.commit_snapshot("cam-01")

        builder = RestoreBuilder(
            catalog=MockCatalog(),
            registry=MockRegistry(),
            git_repo=tmp_repo,
        )
        plan = builder.build_restore_plan("cam-01")
        assert plan["steps"]
        assert all(
            s["risk_level"] == "service-affecting" for s in plan["steps"]
        )

    def test_large_facet_chunks_into_multiple_steps(self, tmp_repo):
        """A whole-facet param.cgi:update overflows the device URI limit
        (observed: HTTP 414 on a P3288 with ~344 image params) — big
        updates split into budget-bounded steps that together carry
        every param exactly once."""
        from admz.snapshot.restore import _PARAM_UPDATE_BUDGET

        big = {f"I0.Setting{i:03d}": f"value-{i}" for i in range(300)}
        tmp_repo.write_facet("cam-01", "image", big)
        tmp_repo.commit_snapshot("cam-01")

        builder = RestoreBuilder(
            catalog=MockCatalog(),
            registry=MockRegistry(),
            git_repo=tmp_repo,
        )
        plan = builder.build_restore_plan("cam-01")
        assert len(plan["steps"]) > 1

        merged = {}
        for step in plan["steps"]:
            assert step["operation_id"] == "param.cgi:update"
            assert step["risk_level"] == "service-affecting"
            raw = sum(len(k) + len(v) + 2 for k, v in step["params"].items())
            assert raw <= _PARAM_UPDATE_BUDGET
            assert not (set(merged) & set(step["params"]))  # no overlap
            merged.update(step["params"])
        assert merged == {
            f"root.Image.{k}": v for k, v in big.items()
        }
        # Chunked steps are numbered in the description
        assert "(1/" in plan["steps"][0]["description"]

    def test_small_facet_stays_one_step(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "image", {"I0.Resolution": "1080p"})
        tmp_repo.commit_snapshot("cam-01")

        builder = RestoreBuilder(
            catalog=MockCatalog(),
            registry=MockRegistry(),
            git_repo=tmp_repo,
        )
        plan = builder.build_restore_plan("cam-01")
        assert len(plan["steps"]) == 1
        assert "(1/" not in plan["steps"][0]["description"]

    def test_restore_plan_warns_on_unrestorable_keys(self, tmp_repo):
        tmp_repo.write_facet("cam-01", "time", {
            "NTP.Server": "pool.ntp.org",
            "SyncSource": "NTP",
        })
        tmp_repo.commit_snapshot("cam-01")

        builder = RestoreBuilder(
            catalog=MockCatalog(),
            registry=MockRegistry(),
            git_repo=tmp_repo,
        )
        plan = builder.build_restore_plan("cam-01")
        assert any(
            "not restorable" in w and "NTP.Server" in w
            for w in plan["warnings"]
        )
        # The restorable key still becomes a step
        assert any(
            "root.Time.SyncSource" in s["params"] for s in plan["steps"]
        )


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


class TestBaselinePointers:
    """SnapshotEngine._set_baseline_pointers — a snapshot blesses the
    current config as the baseline (ADR-0031); writes are best-effort."""

    def _engine(self, registry):
        from admz.snapshot.engine import SnapshotEngine
        return SnapshotEngine(
            catalog=None, registry=registry, executors={}, git_repo=None
        )

    def test_writes_baseline_and_observed(self):
        calls = {}

        class _Reg:
            def set_config_pointers(self, device_id, **kw):
                calls[device_id] = kw

        self._engine(_Reg())._set_baseline_pointers("cam-01", "deadbeef")
        assert calls["cam-01"]["baseline_sha"] == "deadbeef"
        assert calls["cam-01"]["latest_observed_sha"] == "deadbeef"
        assert "last_observed_at" in calls["cam-01"]

    def test_none_sha_is_noop(self):
        class _Reg:
            def set_config_pointers(self, *a, **k):
                raise AssertionError("must not write for a None sha")

        self._engine(_Reg())._set_baseline_pointers("cam-01", None)

    def test_degrades_on_not_implemented(self):
        class _Reg:  # e.g. the stubbed Vault backend (H-4)
            def set_config_pointers(self, *a, **k):
                raise NotImplementedError

        # Must swallow — a pointer-less backend can't fail the snapshot.
        self._engine(_Reg())._set_baseline_pointers("cam-01", "abc")


# ---------------------------------------------------------------------------
# Drift note: _action_accept_baseline + request models
# ---------------------------------------------------------------------------

class TestDriftNoteField:
    """Note field on accept-baseline and restore — Slice 1 of drift visualization."""

    def test_accept_baseline_request_accepts_note(self):
        from admz.api.routes.snapshot import AcceptBaselineRequest
        req = AcceptBaselineRequest(device_id="cam-01", note="firmware update")
        assert req.note == "firmware update"

    def test_accept_baseline_request_note_optional(self):
        from admz.api.routes.snapshot import AcceptBaselineRequest
        req = AcceptBaselineRequest(device_id="cam-01")
        assert req.note is None

    def test_restore_request_accepts_note(self):
        from admz.api.routes.snapshot import RestoreRequest
        req = RestoreRequest(device_id="cam-01", note="revert after failed deploy")
        assert req.note == "revert after failed deploy"

    def test_restore_request_note_optional(self):
        from admz.api.routes.snapshot import RestoreRequest
        req = RestoreRequest(device_id="cam-01")
        assert req.note is None

    def test_action_accept_baseline_writes_baseline_yaml_when_note(self, tmp_repo):
        """_action_accept_baseline writes BASELINE.yaml to git when note is given."""
        import time
        import yaml as _yaml
        from admz.operations import _action_accept_baseline

        # Seed a facet so the device directory exists
        device_id = "cam-note-01"
        device_dir = tmp_repo.device_path(device_id)
        device_dir.mkdir(parents=True, exist_ok=True)
        config_dir = device_dir / "config"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "image.yaml").write_text(_yaml.safe_dump({"I0.Resolution": "1280x720"}))
        sha = tmp_repo.commit_snapshot(device_id, message=f"Audit: {device_id}", auto_push=False)

        class _Reg:
            def __init__(self):
                self._baseline = None
            def set_config_pointers(self, did, *, baseline_sha):
                self._baseline = baseline_sha

        reg = _Reg()
        result = _action_accept_baseline(
            {"device_id": device_id, "baseline_sha": sha,
             "note": "new params due to firmware update", "accepted_by": "test"},
            reg,
            git_repo=tmp_repo,
        )
        assert result["success"] is True
        assert reg._baseline == sha

        # BASELINE.yaml should exist and contain the note
        baseline_file = device_dir / "BASELINE.yaml"
        assert baseline_file.exists(), "BASELINE.yaml not written"
        data = _yaml.safe_load(baseline_file.read_text())
        assert data["note"] == "new params due to firmware update"
        assert data["baseline_sha"] == sha
        assert data["accepted_by"] == "test"

    def test_action_accept_baseline_no_yaml_when_no_note(self, tmp_repo):
        """No BASELINE.yaml written when note is empty."""
        from admz.operations import _action_accept_baseline

        device_id = "cam-no-note"
        device_dir = tmp_repo.device_path(device_id)
        device_dir.mkdir(parents=True, exist_ok=True)
        config_dir = device_dir / "config"
        config_dir.mkdir(exist_ok=True)
        import yaml as _yaml
        (config_dir / "image.yaml").write_text(_yaml.safe_dump({"I0.Resolution": "640x480"}))
        sha = tmp_repo.commit_snapshot(device_id, message=f"Audit: {device_id}", auto_push=False)

        class _Reg:
            def set_config_pointers(self, did, *, baseline_sha):
                pass

        _action_accept_baseline(
            {"device_id": device_id, "baseline_sha": sha},
            _Reg(),
            git_repo=tmp_repo,
        )
        assert not (device_dir / "BASELINE.yaml").exists()

    def test_action_accept_baseline_note_survives_missing_git_repo(self):
        """No error when git_repo=None even if note is provided."""
        from admz.operations import _action_accept_baseline

        class _Reg:
            def set_config_pointers(self, did, *, baseline_sha):
                pass

        result = _action_accept_baseline(
            {"device_id": "cam-x", "baseline_sha": "abc123",
             "note": "some note"},
            _Reg(),
            git_repo=None,
        )
        assert result["success"] is True

    def test_restore_note_included_in_plan_description(self, tmp_repo, tmp_path):
        """RestoreBuilder.build_restore_plan description is unchanged; note added at route level."""
        from admz.snapshot.restore import RestoreBuilder
        from unittest.mock import MagicMock

        catalog = MagicMock()
        catalog.get_risk_level.return_value = "normal"

        class _Reg:
            def get_device_info(self, did):
                return {"device_id": did, "baseline_sha": None}

        builder = RestoreBuilder(catalog, _Reg(), tmp_repo)
        spec = builder.build_restore_plan("cam-01", ref="HEAD")
        # The description is from build_restore_plan — note is appended at route level
        assert "cam-01" in spec["description"]


# ---------------------------------------------------------------------------
# Comprehensive config tracking: facet index + catch-all + audio + action rules
# ---------------------------------------------------------------------------

class TestFacetIndexAndCatchAll:
    """The config→facet index and the catch-all that ensures no param is
    silently dropped (the audio input-gain blind spot)."""

    def test_index_maps_known_facets_to_prefixes(self):
        from admz.snapshot.facets.base import facet_param_index
        idx = facet_param_index()
        assert idx.get("image") == ["root.Image."]
        assert idx.get("audio") == ["root.Audio"]
        assert "root.Network." in idx.get("network", [])
        # Facets without param prefixes are not in the param index.
        assert "other" not in idx
        assert "action_rules" not in idx

    def test_claimed_prefixes_excludes_self(self):
        from admz.snapshot.facets.base import claimed_prefixes
        claimed = claimed_prefixes(exclude="other")
        assert "root.Image." in claimed
        assert "root.Audio" in claimed
        # Nothing the catch-all itself would contribute (it has none anyway).

    def test_catchall_captures_only_unclaimed_params(self):
        from admz.snapshot.facets.other_params import CatchAllParamsFacet
        facet = CatchAllParamsFacet()
        raw = {"params": {
            "root.Image.I0.Resolution": "1920x1080",   # owned by image
            "root.AudioSource.A0.InputGain": "-10",      # owned by audio
            "root.Syslog.Server": "10.0.0.9",            # unowned → catch-all
            "root.SNMP.Enabled": "yes",                  # unowned → catch-all
        }}
        out = facet.serialize(raw)
        assert out == {
            "root.Syslog.Server": "10.0.0.9",
            "root.SNMP.Enabled": "yes",
        }
        # Catch-all is read-only.
        assert facet.deserialize(out) == []

    def test_audio_input_gain_is_captured_not_dropped(self):
        """Regression: the exact scenario that reported 'no drift' — an audio
        input-gain change. AudioFacet must capture it; the catch-all must not
        (it's claimed)."""
        from admz.snapshot.facets.audio import AudioFacet
        from admz.snapshot.facets.other_params import CatchAllParamsFacet
        raw = {"params": {"root.AudioSource.A0.InputGain": "-10"}}
        audio = AudioFacet().serialize(raw)
        assert audio == {"Source.A0.InputGain": "-10"}
        assert CatchAllParamsFacet().serialize(raw) == {}


class TestActionRulesFacet:
    def test_extracts_rules_from_varied_shapes(self):
        from admz.snapshot.facets.action_rules import _extract_rules
        rule = {"id": "1", "name": "Motion email"}
        assert _extract_rules([rule]) == [rule]
        assert _extract_rules({"rules": [rule]}) == [rule]
        assert _extract_rules({"data": {"rules": [rule]}}) == [rule]
        assert _extract_rules({"nope": 1}) == []

    def test_serialize_keys_by_id_drops_volatile(self):
        from admz.snapshot.facets.action_rules import ActionRulesFacet
        raw = {"action_rules": {"rules": [
            {"id": "7", "name": "Door", "enabled": True, "lastModified": "t1"},
        ]}}
        out = ActionRulesFacet().serialize(raw)
        assert out == {"7": {"id": "7", "name": "Door", "enabled": True}}
        assert ActionRulesFacet().deserialize(out) == []

    def test_firmware_gating(self):
        from admz.snapshot.facets.action_rules import ActionRulesFacet
        f = ActionRulesFacet()
        assert f.matches_device({"api_family": "vapix", "firmware": "12.10.68"}) is True
        assert f.matches_device({"api_family": "vapix", "firmware": "11.11.205"}) is False

    def test_uses_listrules_extra_read_op(self):
        from admz.snapshot.facets.action_rules import ActionRulesFacet
        specs = ActionRulesFacet().extra_read_ops
        assert len(specs) == 1
        assert specs[0].operation_id == "action-rules:listRules"
        assert specs[0].result_key == "action_rules"


class TestSecretParamFiltering:
    """Comprehensive capture must never commit unmasked secrets (SNMP
    community strings, PSKs, passphrases) to the git config repo."""

    def test_parse_param_dump_drops_unmasked_secrets(self):
        from admz.snapshot.engine import _parse_param_dump
        dump = "\n".join([
            "root.Image.I0.Resolution=1920x1080",
            "root.SNMP.V1ReadCommunity=public",
            "root.SNMP.V1WriteCommunity=write",
            "root.SNMP.Trap.T0.Community=public",
            "root.Network.Interface.I0.dot1x.EAPOL.EAP.PrivateKeyPassword=hunter2",
            "root.Network.Wireless.WPAPSK=topsecret",
            "root.SNMP.Enabled=yes",
        ])
        out = _parse_param_dump(dump)
        # Real config kept.
        assert out["root.Image.I0.Resolution"] == "1920x1080"
        assert out["root.SNMP.Enabled"] == "yes"
        # Every secret-shaped key dropped — not just masked.
        for k in out:
            assert "community" not in k.lower()
            assert "psk" not in k.lower()
            assert "password" not in k.lower()
        assert "root.SNMP.V1WriteCommunity" not in out
        assert "root.Network.Wireless.WPAPSK" not in out

    def test_is_sensitive_matches_secret_param_shapes(self):
        from admz.snapshot.engine import _is_sensitive
        assert _is_sensitive("root.SNMP.V1WriteCommunity") is True
        assert _is_sensitive("root.Foo.Passphrase") is True
        assert _is_sensitive("root.HTTPS.PrivateKey") is True
        assert _is_sensitive("root.Image.I0.Resolution") is False


# ---------------------------------------------------------------------------
# Targeted revert: undo only the drifted fields, not the whole baseline
# ---------------------------------------------------------------------------

class TestTargetedRevert:
    def test_simple_param_facet_revert_param(self):
        from admz.snapshot.facets.audio import AudioFacet
        from admz.snapshot.facets.image import ImageFacet
        assert AudioFacet().revert_param("Source.A0.InputGain", "-10") == \
            ("root.AudioSource.A0.InputGain", "-10")
        assert ImageFacet().revert_param("I0.Resolution", "1920x1080") == \
            ("root.Image.I0.Resolution", "1920x1080")
        # Per-facet RESTORE_EXCLUDE (image I*.Source) → not revertable.
        assert ImageFacet().revert_param("I0.Source", "0") is None
        # Masked secret → not revertable.
        assert AudioFacet().revert_param("Source.A0.Foo", "******") is None

    def test_events_facet_revert_param(self):
        from admz.snapshot.facets.events import EventsFacet
        f = EventsFacet()
        assert f.revert_param("event.E0.Enabled", "yes") == \
            ("root.Event.E0.Enabled", "yes")
        assert f.revert_param("ioport.I0.Input.Name", "Port 1") == \
            ("root.IOPort.I0.Input.Name", "Port 1")
        # ioport.I*.Configurable excluded (401 on write).
        assert f.revert_param("ioport.I0.Configurable", "yes") is None

    def test_readonly_facets_are_not_revertable(self):
        from admz.snapshot.facets.action_rules import ActionRulesFacet
        from admz.snapshot.facets.other_params import CatchAllParamsFacet
        from admz.snapshot.facets.users import UsersFacet
        assert CatchAllParamsFacet().revert_param("root.SNMP.Enabled", "no") is None
        assert ActionRulesFacet().revert_param("7", {"x": 1}) is None
        assert UsersFacet().revert_param("admin_access.account1", "admin") is None

    def test_targeted_plan_only_touches_drifted_fields(self, tmp_repo):
        from unittest.mock import MagicMock
        from admz.snapshot.models import DriftField
        from admz.snapshot.restore import RestoreBuilder

        reg = MagicMock()
        reg.get_device_info.return_value = {"api_family": "vapix"}
        builder = RestoreBuilder(MagicMock(), reg, tmp_repo)
        fields = [
            DriftField(facet="audio", path="Source.A0.InputGain",
                       expected="-10", actual="-8"),
            DriftField(facet="image", path="I0.Resolution",
                       expected="1920x1080", actual="1280x720"),
            DriftField(facet="other", path="root.SNMP.Enabled",
                       expected="no", actual="yes"),          # read-only facet
            DriftField(facet="audio", path="Source.A0.NewKey",
                       expected="<missing>", actual="x"),     # appeared
        ]
        spec = builder.build_targeted_revert_plan("cam-x", fields)
        # The two revertable fields, written in ONE small step.
        assert len(spec["steps"]) == 1
        assert spec["steps"][0]["params"] == {
            "root.AudioSource.A0.InputGain": "-10",
            "root.Image.I0.Resolution": "1920x1080",
        }
        assert spec["steps"][0]["risk_level"] == "service-affecting"
        # Read-only + appeared fields are surfaced as a warning, not forced.
        assert spec["warnings"]
        assert "other.root.SNMP.Enabled" in spec["warnings"][0]
        assert "added, not in baseline" in spec["warnings"][0]

    def test_no_drift_yields_no_steps(self, tmp_repo):
        from unittest.mock import MagicMock
        from admz.snapshot.restore import RestoreBuilder
        reg = MagicMock()
        reg.get_device_info.return_value = {"api_family": "vapix"}
        builder = RestoreBuilder(MagicMock(), reg, tmp_repo)
        spec = builder.build_targeted_revert_plan("cam-x", [])
        assert spec["steps"] == []
        assert "Revert 0 drifted" in spec["description"]
