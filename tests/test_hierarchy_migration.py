"""Tests for the hierarchy backfill migration (ADR-0032: org/site only).

Pre-Slice-1 devices have NULL org_id/site_id; the migration assigns them
to (default, default). The former assign-to-"ungrouped"-group step was
removed with the Group level — operational grouping is device tags now.
"""

from __future__ import annotations

import pytest

from admz.backends.sqlite_backend import SQLiteDeviceRegistry
from admz.migrations import migrate_hierarchy_backfill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _registry(tmp_path, monkeypatch):
    """Fresh registry with the default Org/Site already bootstrapped."""
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
    # Bootstrap the default org/site inline (don't bring all of
    # build_components into the test — we just need the rows).
    registry.add_organization(
        org_id="default", name="Default Organization",
        repo_path=str(tmp_path / "config-repo"),
    )
    registry.add_site(
        site_id="default", org_id="default", name="Default Site",
    )
    return registry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _strand(registry, *device_ids):
    """Put a device into the pre-#427 state: NULL org_id/site_id.

    `add_device` now assigns the local site, so a device created through the
    API is no longer a subject for this migration. Six production devices ARE
    in the NULL state — added while `add_device` did not assign one — so the
    backfill still has to find and fix exactly that, and these tests still have
    to reproduce it. `set_device_org_site` refuses None (it validates the org
    exists), which is right for the API and useless here.
    """
    import sqlite3

    with sqlite3.connect(registry._db_path) as conn:
        for did in device_ids:
            conn.execute(
                "UPDATE devices SET org_id=NULL, site_id=NULL WHERE device_id=?",
                (did,),
            )
        conn.commit()


class TestHierarchyBackfill:
    def test_empty_registry(self, tmp_path, monkeypatch):
        registry = _registry(tmp_path, monkeypatch)
        result = migrate_hierarchy_backfill(registry)
        assert result["devices_total"] == 0
        assert result["backfilled"] == 0
        assert result["already_migrated"] == 0

    def test_backfills_pre_hierarchy_devices(self, tmp_path, monkeypatch):
        registry = _registry(tmp_path, monkeypatch)
        for i in range(3):
            registry.add_device(f"cam-{i:02d}", {"host": f"10.0.0.{i}"})
        _strand(registry, *(f"cam-{i:02d}" for i in range(3)))
        result = migrate_hierarchy_backfill(registry)
        assert result["devices_total"] == 3
        assert result["backfilled"] == 3
        for i in range(3):
            did = f"cam-{i:02d}"
            assert registry.get_device_org_site(did) == {
                "org_id": "default", "site_id": "default",
            }

    def test_idempotent_when_rerun(self, tmp_path, monkeypatch):
        registry = _registry(tmp_path, monkeypatch)
        registry.add_device("cam-01", {"host": "10.0.0.1"})
        _strand(registry, "cam-01")
        first = migrate_hierarchy_backfill(registry)
        assert first["backfilled"] == 1
        second = migrate_hierarchy_backfill(registry)
        assert second["backfilled"] == 0
        assert second["already_migrated"] == 1

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch):
        registry = _registry(tmp_path, monkeypatch)
        registry.add_device("cam-01", {"host": "10.0.0.1"})
        _strand(registry, "cam-01")
        result = migrate_hierarchy_backfill(registry, dry_run=True)
        assert result["dry_run"] is True
        assert result["backfilled"] == 1  # would have
        assert registry.get_device_org_site("cam-01") is None

    def test_existing_assignment_preserved(self, tmp_path, monkeypatch):
        """A device already assigned to a custom org/site is left alone."""
        registry = _registry(tmp_path, monkeypatch)
        registry.add_organization("acme", "Acme", repo_path="/tmp/acme")
        registry.add_site("hq", "acme", "HQ")
        registry.add_device("cam-01", {"host": "10.0.0.1"})
        registry.set_device_org_site("cam-01", "acme", "hq")
        result = migrate_hierarchy_backfill(registry)
        assert result["already_migrated"] == 1
        assert result["backfilled"] == 0
        assert registry.get_device_org_site("cam-01") == {
            "org_id": "acme", "site_id": "hq",
        }

    def test_continues_past_per_device_error(self, tmp_path, monkeypatch):
        registry = _registry(tmp_path, monkeypatch)
        registry.add_device("cam-01", {"host": "10.0.0.1"})
        registry.add_device("cam-02", {"host": "10.0.0.2"})
        _strand(registry, "cam-01", "cam-02")

        original = registry.set_device_org_site

        def flaky(device_id, org_id, site_id):
            if device_id == "cam-01":
                raise RuntimeError("boom")
            return original(device_id, org_id, site_id)

        monkeypatch.setattr(registry, "set_device_org_site", flaky)
        result = migrate_hierarchy_backfill(registry)
        # cam-01 failed; cam-02 succeeded — migration didn't halt.
        assert result["backfilled"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["device_id"] == "cam-01"
        assert registry.get_device_org_site("cam-02") is not None
