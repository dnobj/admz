"""Tests for admz.snapshot.maintenance.

Real git is used (the tests are fast and the surface is small).
The fixture builds a tiny repo with a few commits so stats /
gc have something to chew on.
"""

import subprocess
from pathlib import Path

import pytest

from admz.snapshot.git_repo import GitRepo
from admz.snapshot.maintenance import (
    GcResult,
    RepoStats,
    commit_intent_stats,
    get_repo_stats,
    is_gc_aggressive,
    is_gc_enabled,
    run_gc,
    set_gc_aggressive,
    set_gc_enabled,
)


@pytest.fixture
def empty_repo(tmp_path):
    """A fresh git repo, no commits yet."""
    repo_path = tmp_path / "configs"
    repo = GitRepo(str(repo_path))
    # Configure git so commits work.
    for key, val in [
        ("user.email", "test@test.com"),
        ("user.name", "Test"),
        ("commit.gpgsign", "false"),
    ]:
        subprocess.run(
            ["git", "config", key, val], cwd=repo_path, check=True
        )
    return repo


@pytest.fixture
def populated_repo(empty_repo):
    """Empty repo plus a few real snapshot commits."""
    for i in range(3):
        device_id = f"cam-{i:02d}"
        empty_repo.write_device_yaml(
            device_id, {"device_id": device_id, "host": f"10.0.0.{i}"}
        )
        empty_repo.commit_snapshot(device_id)
    return empty_repo


# ---------------------------------------------------------------------------
# commit_intent_stats (ADR-0031 slice 4 — observation-growth visibility)
# ---------------------------------------------------------------------------


class TestCommitIntentStats:

    def test_empty_repo_all_zero(self, empty_repo):
        assert commit_intent_stats(empty_repo) == {
            "audit": 0, "snapshot": 0, "baseline": 0, "other": 0,
        }

    def test_counts_by_prefix(self, empty_repo):
        cases = [
            ("Audit: cam-01", "a1"),
            ("Audit: cam-02", "a2"),
            ("Snapshot cam-01", "s1"),
            ("Fleet snapshot: cam-01, cam-02", "s2"),
            ("Scheduled: Nightly backup", "s3"),
            ("Baseline - initial capture", "b1"),
            ("manual operator tweak", "o1"),
        ]
        for message, marker in cases:
            empty_repo.write_device_yaml(
                "cam-01", {"device_id": "cam-01", "marker": marker}
            )
            empty_repo.commit_snapshot("cam-01", message=message)
        stats = commit_intent_stats(empty_repo)
        assert stats == {"audit": 2, "snapshot": 3, "baseline": 1, "other": 1}


# ---------------------------------------------------------------------------
# get_repo_stats
# ---------------------------------------------------------------------------


class TestGetRepoStats:
    def test_empty_repo_reports_zero_commits(self, empty_repo):
        stats = get_repo_stats(empty_repo)
        assert isinstance(stats, RepoStats)
        assert stats.commit_count == 0
        assert stats.oldest_commit_iso is None
        assert stats.newest_commit_iso is None
        # .git dir still exists, so git_bytes > 0 but very small.
        assert stats.git_bytes > 0

    def test_populated_repo_reports_correct_commit_count(self, populated_repo):
        stats = get_repo_stats(populated_repo)
        assert stats.commit_count == 3
        assert stats.oldest_commit_iso is not None
        assert stats.newest_commit_iso is not None

    def test_fleet_bytes_excluded_from_git(self, populated_repo):
        stats = get_repo_stats(populated_repo)
        # The YAML files we wrote live under fleet/
        assert stats.fleet_bytes > 0

    def test_to_dict_has_mb_helpers(self, populated_repo):
        stats = get_repo_stats(populated_repo)
        d = stats.to_dict()
        assert "total_mb" in d
        assert "git_mb" in d
        assert d["total_mb"] == round(stats.total_mb, 2)


# ---------------------------------------------------------------------------
# run_gc
# ---------------------------------------------------------------------------


class TestRunGc:
    def test_gc_on_populated_repo_succeeds(self, populated_repo):
        result = run_gc(populated_repo)
        assert isinstance(result, GcResult)
        assert result.ran is True
        assert result.error is None
        # before/after must be non-negative integers.
        assert result.before_bytes >= 0
        assert result.after_bytes >= 0

    def test_aggressive_gc_runs(self, populated_repo):
        # Just verifies the flag flows through. Doesn't measure
        # actual difference (depends on git version).
        result = run_gc(populated_repo, aggressive=True)
        assert result.ran is True

    def test_gc_with_no_git_dir_returns_error(self, tmp_path):
        # A directory that doesn't have .git inside.
        fake = tmp_path / "not-a-repo"
        fake.mkdir()
        # Construct GitRepo directly; bypass _ensure_repo by manipulating
        # the path post-init.
        repo = GitRepo(str(fake))
        # _ensure_repo created .git — remove it to simulate the error.
        import shutil
        shutil.rmtree(fake / ".git")

        result = run_gc(repo)
        assert result.ran is False
        assert result.error and "git" in result.error.lower()

    def test_to_dict_has_saved_mb(self, populated_repo):
        result = run_gc(populated_repo)
        d = result.to_dict()
        assert "saved_mb" in d
        assert d["saved_mb"] == round(result.saved_mb, 2)


# ---------------------------------------------------------------------------
# Fleet-setting helpers
# ---------------------------------------------------------------------------


class TestFleetSettings:
    @pytest.fixture(autouse=True)
    def _isolate_fs(self, tmp_path, monkeypatch):
        """Repoint fleet_settings at a tmp DB and restore after."""
        from admz import fleet_settings as fs_module
        db_path = str(tmp_path / "admz.db")
        monkeypatch.setenv("ADMZ_DB_PATH", db_path)
        orig = fs_module.fleet_settings
        fs_module.fleet_settings = fs_module.FleetSettings(db_path)
        try:
            yield
        finally:
            fs_module.fleet_settings = orig

    def test_gc_disabled_by_default(self):
        assert is_gc_enabled() is False
        assert is_gc_aggressive() is False

    def test_set_then_get(self):
        set_gc_enabled(True)
        assert is_gc_enabled() is True
        set_gc_enabled(False)
        assert is_gc_enabled() is False

    def test_aggressive_round_trip(self):
        set_gc_aggressive(True)
        assert is_gc_aggressive() is True

    def test_unknown_value_parses_as_disabled(self):
        from admz.fleet_settings import fleet_settings as fs
        fs.set("snapshot_gc_enabled", "nope")
        assert is_gc_enabled() is False
