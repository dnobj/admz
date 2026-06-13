"""Slot/unit device identity (ADR-0036): the delete tombstone + the
mac_address backfill that makes `mac_address` the authoritative unit key.

(The replace-hardware rebind has its own test file.)
"""

from __future__ import annotations

import subprocess

import pytest


# ---------------------------------------------------------------------------
# Delete tombstone — operations.tombstone_device + _action_delete_device
# ---------------------------------------------------------------------------


def _git_repo(tmp_path):
    from admz.snapshot.git_repo import GitRepo
    repo = GitRepo(str(tmp_path / "config-repo"))
    for k, v in (("user.email", "t@t.com"), ("user.name", "T"),
                 ("commit.gpgsign", "false")):
        subprocess.run(["git", "config", k, v], cwd=repo.repo_path, check=True)
    return repo


class TestTombstone:
    def test_writes_removed_marker_and_commit(self, tmp_path):
        from admz import operations
        repo = _git_repo(tmp_path)
        # Seed some committed config so there's history to keep.
        repo.write_facet("cam-1", "image", {"I0.Resolution": "1080p"})
        repo.commit_snapshot("cam-1", message="snap", auto_push=False)

        operations.tombstone_device("cam-1", repo, removed_by="alice")

        marker = repo.device_path("cam-1") / "REMOVED.yaml"
        assert marker.exists()
        body = marker.read_text()
        assert "removed: true" in body
        assert "alice" in body
        # The tombstone commit is in the log, AND the prior config history
        # is retained (the original snapshot commit is still there).
        log = repo.log(path="fleet/cam-1", max_count=5)
        messages = [c["message"] for c in log]
        assert any("Removed: cam-1" in m for m in messages)
        assert any("snap" in m for m in messages)  # history kept
        # The config facet is still readable at current HEAD.
        assert repo.read_facet("cam-1", "image", "HEAD") is not None

    def test_no_git_repo_is_noop(self):
        from admz import operations
        # Must not raise when there's no repo (the test/dispatch path).
        operations.tombstone_device("cam-x", None)

    def test_action_delete_tombstones_then_removes(self, tmp_path):
        from admz import operations

        class _Reg:
            def __init__(self):
                self.removed = []
            def device_exists(self, d):
                return d not in self.removed
            def remove_device(self, d):
                self.removed.append(d)

        repo = _git_repo(tmp_path)
        repo.write_facet("cam-2", "image", {"x": "1"})
        repo.commit_snapshot("cam-2", message="snap", auto_push=False)

        reg = _Reg()
        out = operations._action_delete_device(
            {"action": "delete_device", "device_id": "cam-2", "removed_by": "bob"},
            reg, git_repo=repo,
        )
        assert out["success"] is True
        assert reg.removed == ["cam-2"]
        assert (repo.device_path("cam-2") / "REMOVED.yaml").exists()

    def test_action_delete_unknown_device(self, tmp_path):
        from admz import operations

        class _Reg:
            def device_exists(self, d):
                return False
            def remove_device(self, d):  # pragma: no cover
                raise AssertionError("should not be called")

        out = operations._action_delete_device(
            {"action": "delete_device", "device_id": "ghost"}, _Reg(),
            git_repo=_git_repo(tmp_path),
        )
        assert out["success"] is False
        assert "not found" in out["error"].lower()


# ---------------------------------------------------------------------------
# mac_address: populated on add, backfilled for legacy rows
# ---------------------------------------------------------------------------


@pytest.fixture
def registry(tmp_path):
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry
    return SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"), key_path=str(tmp_path / "admz.key"),
    )


class TestMacAddressAuthoritative:
    def test_add_defaults_mac_from_mac_device_id(self, registry):
        # A slot whose device_id is a MAC gets mac_address populated.
        registry.add_device("B8A44F0C5B32", {"host": "10.0.0.1"})
        assert registry.get_device_info("B8A44F0C5B32")["mac_address"] == "B8A44F0C5B32"

    def test_add_does_not_override_given_mac(self, registry):
        registry.add_device("slot-1", {"host": "10.0.0.2", "mac_address": "AA:BB:CC:DD:EE:FF"})
        assert registry.get_device_info("slot-1")["mac_address"] == "AA:BB:CC:DD:EE:FF"

    def test_non_mac_device_id_no_default(self, registry):
        # A non-MAC device_id (e.g. a model slug) gets no invented MAC.
        registry.add_device("lobby-cam", {"host": "10.0.0.3"})
        assert not registry.get_device_info("lobby-cam").get("mac_address")

    def test_backfill_fills_legacy_rows(self, registry):
        # Simulate a legacy row: MAC device_id but no mac_address.
        import json, sqlite3
        conn = sqlite3.connect(registry._db_path)
        conn.execute(
            "INSERT INTO devices (device_id, info_json, created_at) VALUES (?, ?, ?)",
            ("ACCC8EE6E7EE", json.dumps({"host": "10.0.0.9"}), 0.0),
        )
        conn.commit(); conn.close()
        assert not registry.get_device_info("ACCC8EE6E7EE").get("mac_address")

        from admz.components import _backfill_mac_addresses
        _backfill_mac_addresses(registry)
        assert registry.get_device_info("ACCC8EE6E7EE")["mac_address"] == "ACCC8EE6E7EE"
