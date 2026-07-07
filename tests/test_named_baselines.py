"""Tests for named config baselines (alternate configurations).

Covers the SQLiteDeviceRegistry storage (save/list/upsert/delete/cascade) and
the read route GET /api/snapshot/baselines/{device_id} (active annotation).
The write routes (save/delete) require an authenticated principal, so they're
exercised by the registry unit tests + the live check with a Bearer key.
"""

from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from admz.backends.sqlite_backend import SQLiteDeviceRegistry
from admz.snapshot.git_repo import GitRepo
from admz.exceptions import DeviceNotFoundError


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
# registry storage
# --------------------------------------------------------------------------

class TestNamedBaselineStorage:
    def _reg(self, tmp_path):
        return SQLiteDeviceRegistry(
            db_path=str(tmp_path / "t.db"), key_path=str(tmp_path / "t.key"),
        )

    def test_save_list_upsert_delete(self, tmp_path):
        reg = self._reg(tmp_path)
        reg.add_device("cam1", {"host": "192.0.2.1"})
        reg.save_named_baseline("cam1", "event", "aaa", note="loud", created_by="dnich")
        reg.save_named_baseline("cam1", "quiet", "bbb")
        assert {b["name"] for b in reg.list_named_baselines("cam1")} == {"event", "quiet"}

        # upsert overwrites the commit for an existing name
        reg.save_named_baseline("cam1", "event", "ccc")
        ev = next(b for b in reg.list_named_baselines("cam1") if b["name"] == "event")
        assert ev["commit_sha"] == "ccc"
        assert ev["note"] == ""  # cleared on upsert (we passed no note)

        assert reg.delete_named_baseline("cam1", "quiet") is True
        assert reg.delete_named_baseline("cam1", "nope") is False
        assert [b["name"] for b in reg.list_named_baselines("cam1")] == ["event"]

    def test_cascade_on_device_delete(self, tmp_path):
        reg = self._reg(tmp_path)
        reg.add_device("cam1", {"host": "x"})
        reg.save_named_baseline("cam1", "v", "sha")
        reg.remove_device("cam1")
        reg.add_device("cam1", {"host": "x"})  # same id, fresh
        assert reg.list_named_baselines("cam1") == []  # no orphaned rows

    def test_save_unknown_device_raises(self, tmp_path):
        reg = self._reg(tmp_path)
        with pytest.raises(DeviceNotFoundError):
            reg.save_named_baseline("ghost", "v", "sha")

    def test_newest_first(self, tmp_path):
        reg = self._reg(tmp_path)
        reg.add_device("cam1", {"host": "x"})
        reg.save_named_baseline("cam1", "first", "a")
        reg.save_named_baseline("cam1", "second", "b")
        assert reg.list_named_baselines("cam1")[0]["name"] == "second"


# --------------------------------------------------------------------------
# GET /api/snapshot/baselines/{device_id}
# --------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
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
    sha2 = repo.commit_snapshot("cam1", "Snapshot cam1", auto_push=False)

    import admz.api.main as main_module
    reg = SQLiteDeviceRegistry(
        db_path=str(db_path), key_path=str(tmp_path / "admz.key"),
    )
    reg.add_device("cam1", {"host": "192.0.2.1"})
    reg.set_config_pointers("cam1", baseline_sha=sha1)
    reg.save_named_baseline("cam1", "main", sha1, created_by="seed")
    reg.save_named_baseline("cam1", "variant", sha2, note="brighter")
    monkeypatch.setattr(main_module, "registry", reg)

    with TestClient(main_module.app, follow_redirects=False) as c:
        yield c, sha1, sha2


class TestNamedBaselineRoutes:
    def test_list_with_active_annotation(self, client):
        c, sha1, sha2 = client
        body = c.get("/api/snapshot/baselines/cam1").json()
        assert body["baseline_sha"] == sha1
        assert body["active_name"] == "main"  # main's commit == baseline_sha
        by = {b["name"]: b for b in body["baselines"]}
        assert by["main"]["is_active"] is True
        assert by["variant"]["is_active"] is False
        assert by["variant"]["note"] == "brighter"
        assert by["variant"]["short_sha"] == sha2[:12]

    def test_list_unknown_device_404(self, client):
        c = client[0]
        assert c.get("/api/snapshot/baselines/ghost").status_code == 404


# The old per-tag/all-devices "apply-tag-baseline" (which re-pointed the
# baseline) was retired in ADR-0044. Its successor — scenario activate / return
# / save (baseline-stable, group-scoped) — is tested in tests/test_scenarios.py.
