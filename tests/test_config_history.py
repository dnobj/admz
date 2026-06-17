"""Tests for the per-device config history routes + git_repo.diff_commit.

Covers admz.snapshot.git_repo.diff_commit (commit-vs-parent, and root-commit
vs the empty tree) and the GET /api/snapshot/history endpoints (annotated
timeline + per-commit diff).
"""

from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from admz.snapshot.git_repo import GitRepo
from admz.api.routes.snapshot import _classify_commit


def _init_git(repo: GitRepo) -> None:
    for k, v in [
        ("user.email", "t@t.co"),
        ("user.name", "tester"),
        ("commit.gpgsign", "false"),
    ]:
        subprocess.run(["git", "config", k, v], cwd=repo.repo_path, check=True)


def _write_facet(repo: GitRepo, device_id: str, facet: str, content: str) -> None:
    d = repo.repo_path / "fleet" / device_id / "config"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{facet}.yaml").write_text(content)


# --------------------------------------------------------------------------
# git_repo.diff_commit
# --------------------------------------------------------------------------

def test_diff_commit_root_and_child(tmp_path):
    repo = GitRepo(str(tmp_path / "repo"))
    _init_git(repo)
    _write_facet(repo, "cam1", "image", "brightness: 50\n")
    sha1 = repo.commit_snapshot("cam1", "Snapshot cam1", auto_push=False)
    _write_facet(repo, "cam1", "image", "brightness: 80\n")
    sha2 = repo.commit_snapshot("cam1", "Audit: cam1", auto_push=False)

    assert sha1 and sha2 and sha1 != sha2

    # Root commit (no parent) -> diffed against the empty tree, so it shows
    # the whole file it added.
    d1 = repo.diff_commit(sha1, path="fleet/cam1/")
    assert "image.yaml" in d1
    assert "brightness: 50" in d1

    # Child commit -> just the change it introduced.
    d2 = repo.diff_commit(sha2, path="fleet/cam1/")
    assert "-brightness: 50" in d2
    assert "+brightness: 80" in d2


def test_classify_commit():
    assert _classify_commit("Snapshot cam1") == "snapshot"
    assert _classify_commit("Accept baseline: cam1") == "baseline"
    assert _classify_commit("Audit: cam1") == "audit"
    assert _classify_commit("Restore cam1") == "restore"
    assert _classify_commit("Delete cam1") == "delete"
    assert _classify_commit("something else") == "other"


# --------------------------------------------------------------------------
# GET /api/snapshot/history routes
# --------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient over the real app with an isolated DB + a config repo
    pre-seeded with two commits for cam1 (and an uncommitted cam2)."""
    db_path = tmp_path / "admz.db"
    repo_path = tmp_path / "config-repo"
    monkeypatch.setenv("ADMZ_DB_PATH", str(db_path))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(repo_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    repo = GitRepo(str(repo_path))
    _init_git(repo)
    _write_facet(repo, "cam1", "image", "brightness: 50\n")
    sha1 = repo.commit_snapshot("cam1", "Snapshot cam1", auto_push=False)
    _write_facet(repo, "cam1", "image", "brightness: 80\n")
    sha2 = repo.commit_snapshot("cam1", "Audit: cam1", auto_push=False)

    import admz.api.main as main_module
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry
    reg = SQLiteDeviceRegistry(
        db_path=str(db_path), key_path=str(tmp_path / "admz.key"),
    )
    reg.add_device("cam1", {"host": "192.0.2.1"})
    reg.set_config_pointers("cam1", baseline_sha=sha1, latest_observed_sha=sha2)
    reg.add_device("cam2", {"host": "192.0.2.2"})  # registered, no commits
    monkeypatch.setattr(main_module, "registry", reg)

    with TestClient(main_module.app, follow_redirects=False) as c:
        yield c, sha1, sha2


class TestConfigHistoryRoutes:
    def test_unknown_device_404(self, client):
        c = client[0]
        assert c.get("/api/snapshot/history/does-not-exist").status_code == 404

    def test_empty_history(self, client):
        c = client[0]
        body = c.get("/api/snapshot/history/cam2").json()
        assert body["count"] == 0
        assert body["commits"] == []
        assert body["baseline_sha"] is None

    def test_history_annotated(self, client):
        c, sha1, sha2 = client
        body = c.get("/api/snapshot/history/cam1").json()
        assert body["count"] == 2
        assert body["baseline_sha"] == sha1
        assert body["latest_observed_sha"] == sha2
        by_sha = {x["sha"]: x for x in body["commits"]}
        assert by_sha[sha1]["is_baseline"] is True
        assert by_sha[sha1]["type"] == "snapshot"
        assert by_sha[sha2]["is_latest_observed"] is True
        assert by_sha[sha2]["is_baseline"] is False
        assert by_sha[sha2]["type"] == "audit"
        assert by_sha[sha2]["short_sha"] == sha2[:12]

    def test_commit_diff(self, client):
        c, sha1, sha2 = client
        body = c.get(f"/api/snapshot/history/cam1/{sha2}/diff").json()
        assert "+brightness: 80" in body["diff"]
        assert "-brightness: 50" in body["diff"]
        assert body["short_sha"] == sha2[:12]

    def test_diff_unknown_device_404(self, client):
        c, sha1, sha2 = client
        assert c.get(f"/api/snapshot/history/ghost/{sha1}/diff").status_code == 404
