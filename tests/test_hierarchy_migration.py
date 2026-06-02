"""Tests for the Slice-1 device hierarchy backfill migration.

Covers:
  * Existing devices without org_id/site_id get assigned to
    (default, default).
  * Each backfilled device gets the 'ungrouped' group as its
    primary membership.
  * Already-migrated devices are skipped (counter increments without
    rewriting their assignments).
  * Dry-run reports correct counts without writing.
  * Per-device errors don't halt the rest of the migration.
"""

from __future__ import annotations

import pytest

from admz.backends.sqlite_backend import SQLiteDeviceRegistry
from admz.migrations import migrate_hierarchy_backfill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _registry(tmp_path, monkeypatch):
    """Fresh registry with the default hierarchy already bootstrapped."""
    db = tmp_path / "admz.db"
    monkeypatch.setenv("ADMZ_DB_PATH", str(db))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_REPO_PATH_ROOT", str(tmp_path / "repos"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from admz import fleet_settings as fs_module
    fresh_fs = fs_module.FleetSettings(str(db))
    monkeypatch.setattr(fs_module, "fleet_settings", fresh_fs)

    registry = SQLiteDeviceRegistry(
        db_path=str(db), key_path=str(tmp_path / "admz.key"),
    )
    # Bootstrap the default org/site/group inline (don't bring all of
    # build_components into the test — we just need the rows).
    registry.add_organization(
        org_id="default", name="Default Organization",
        repo_path=str(tmp_path / "config-repo"),
    )
    registry.add_site(
        site_id="default", org_id="default", name="Default Site",
    )
    registry.add_device_group(
        group_id="ungrouped", site_id="default", name="Ungrouped",
    )
    return registry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHierarchyBackfill:
    def test_empty_registry(self, tmp_path, monkeypatch):
        registry = _registry(tmp_path, monkeypatch)
        result = migrate_hierarchy_backfill(registry)
        assert result["devices_total"] == 0
        assert result["backfilled"] == 0
        assert result["primary_assigned"] == 0

    def test_backfills_pre_hierarchy_devices(
        self, tmp_path, monkeypatch
    ):
        registry = _registry(tmp_path, monkeypatch)
        # Three devices added pre-hierarchy: their org_id/site_id
        # are NULL and they have no group memberships.
        for did in ("cam-01", "cam-02", "cam-03"):
            registry.add_device(did, {"host": "192.0.2.1"})

        result = migrate_hierarchy_backfill(registry)
        assert result["devices_total"] == 3
        assert result["backfilled"] == 3
        assert result["primary_assigned"] == 3
        assert result["already_migrated"] == 0

        for did in ("cam-01", "cam-02", "cam-03"):
            os_pair = registry.get_device_org_site(did)
            assert os_pair == {"org_id": "default", "site_id": "default"}
            primary = registry.get_device_primary_group(did)
            assert primary["group_id"] == "ungrouped"

    def test_idempotent_when_rerun(self, tmp_path, monkeypatch):
        registry = _registry(tmp_path, monkeypatch)
        registry.add_device("cam-01", {"host": "192.0.2.1"})

        # First run does the work.
        first = migrate_hierarchy_backfill(registry)
        assert first["backfilled"] == 1
        assert first["primary_assigned"] == 1
        assert first["already_migrated"] == 0

        # Second run sees the device as already migrated.
        second = migrate_hierarchy_backfill(registry)
        assert second["backfilled"] == 0
        assert second["primary_assigned"] == 0
        assert second["already_migrated"] == 1

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch):
        registry = _registry(tmp_path, monkeypatch)
        registry.add_device("cam-01", {"host": "192.0.2.1"})
        result = migrate_hierarchy_backfill(registry, dry_run=True)
        assert result["dry_run"] is True
        assert result["backfilled"] == 1
        # But the device wasn't actually written.
        assert registry.get_device_org_site("cam-01") is None
        assert registry.get_device_primary_group("cam-01") is None

    def test_mixed_state_partially_migrated(self, tmp_path, monkeypatch):
        """A device that already has org_id/site_id but no primary
        group gets ONLY the primary-group assignment."""
        registry = _registry(tmp_path, monkeypatch)
        registry.add_device("cam-01", {"host": "192.0.2.1"})
        # Half-migrated: org+site assigned but no group.
        registry.set_device_org_site("cam-01", "default", "default")
        result = migrate_hierarchy_backfill(registry)
        assert result["backfilled"] == 0           # org/site already set
        assert result["primary_assigned"] == 1     # group assigned now
        assert result["already_migrated"] == 0

    def test_existing_membership_preserved(self, tmp_path, monkeypatch):
        """A device with an existing primary group in some OTHER
        group is left alone (counter increments as already_migrated
        because it has org/site/primary already)."""
        registry = _registry(tmp_path, monkeypatch)
        registry.add_device("cam-01", {"host": "192.0.2.1"})
        # Real custom group in a real custom site under a custom org.
        registry.add_organization(
            "axis-comm", "Axis", str(tmp_path / "axis-repo"),
        )
        registry.add_site("aec", "axis-comm", "AEC Chicago")
        registry.add_device_group("lobby", "aec", "Lobby")
        registry.set_device_org_site("cam-01", "axis-comm", "aec")
        registry.set_device_primary_group("cam-01", "lobby")

        result = migrate_hierarchy_backfill(registry)
        assert result["already_migrated"] == 1
        # cam-01 still belongs to the custom hierarchy, not default.
        assert registry.get_device_org_site("cam-01") == {
            "org_id": "axis-comm", "site_id": "aec",
        }
        assert registry.get_device_primary_group("cam-01")["group_id"] == "lobby"

    def test_continues_past_per_device_error(self, tmp_path, monkeypatch):
        """A failing device doesn't halt the rest."""
        registry = _registry(tmp_path, monkeypatch)
        registry.add_device("cam-01", {"host": "192.0.2.1"})
        registry.add_device("cam-02", {"host": "192.0.2.2"})

        original = registry.set_device_primary_group

        def flaky(device_id, group_id):
            if device_id == "cam-01":
                raise RuntimeError("simulated transient failure")
            return original(device_id, group_id)

        monkeypatch.setattr(registry, "set_device_primary_group", flaky)
        result = migrate_hierarchy_backfill(registry)
        assert result["devices_total"] == 2
        # cam-01 got its org/site set but failed on group; cam-02 succeeded.
        assert any(
            e["device_id"] == "cam-01" for e in result.get("errors", [])
        )
        assert result["primary_assigned"] == 1   # only cam-02 made it
        # cam-01's org/site still got written (the error came AFTER):
        assert registry.get_device_org_site("cam-01") == {
            "org_id": "default", "site_id": "default",
        }
