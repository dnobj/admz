"""Tests for the Org → Site hierarchy (ADR-0032: no Group level).

Covers:
  * SQLite schema (organizations + sites tables, org_id/site_id device
    columns) loads cleanly on a fresh DB AND on an existing DB
    (ALTER TABLE idempotency); the removed Group tables are DROPPED
    idempotently when opening a legacy DB.
  * CRUD round-trip for Organization and Site.
  * Foreign-key enforcement (can't add a Site without its parent Org,
    can't remove an Org while sites still belong to it, etc.).
  * `set_device_org_site` validates that Site belongs to the named Org.
  * Default Org/Site bootstrap in `build_components` is idempotent
    and adopts the legacy config-repo's existing origin URL (the
    homelab-style "operator already did git remote add").
  * `validate_identifier` enforcement on org_id / site_id (CR-5 reuse).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from admz.backends.sqlite_backend import SQLiteDeviceRegistry
from admz.exceptions import (
    BackendError,
    DeviceNotFoundError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """Fresh registry on an isolated tmp DB."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    return SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"),
        key_path=str(tmp_path / "admz.key"),
    )


@pytest.fixture
def org(registry):
    """A populated Org for tests that need a parent."""
    registry.add_organization(
        org_id="axis-comm",
        name="Axis Communications",
        repo_path="/tmp/test-repos/axis-comm",
    )
    return "axis-comm"


@pytest.fixture
def site(registry, org):
    """An Org + Site pair."""
    registry.add_site(
        site_id="aec-chicago",
        org_id=org,
        name="AEC Chicago",
        location="Chicago, IL",
    )
    return ("axis-comm", "aec-chicago")


# ---------------------------------------------------------------------------
# Schema + ALTER TABLE idempotency
# ---------------------------------------------------------------------------


class TestSchema:
    def test_new_tables_exist(self, registry):
        import sqlite3
        with sqlite3.connect(registry._db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        names = {r[0] for r in rows}
        assert {
            "devices", "accounts",
            "organizations", "sites",
        }.issubset(names)
        # ADR-0032: the Group tables are gone.
        assert "device_groups" not in names
        assert "device_group_memberships" not in names

    def test_devices_has_hierarchy_columns(self, registry):
        import sqlite3
        with sqlite3.connect(registry._db_path) as conn:
            cols = {
                row[1] for row in conn.execute("PRAGMA table_info(devices)")
            }
        assert {"device_id", "info_json", "org_id", "site_id"}.issubset(cols)

    def test_alter_idempotent_on_reopen(self, tmp_path):
        """Opening the DB twice in succession must not error on the
        ADD COLUMN — the apply step checks PRAGMA table_info first."""
        db = str(tmp_path / "admz.db")
        key = str(tmp_path / "admz.key")
        r1 = SQLiteDeviceRegistry(db_path=db, key_path=key)
        # Touch r1 so SQLite flushes, then construct a second registry
        # over the same file. If the ALTER ran a second time we'd get
        # OperationalError("duplicate column name").
        r1.list_organizations()
        r2 = SQLiteDeviceRegistry(db_path=db, key_path=key)
        r2.list_organizations()  # smoke

    def test_group_tables_dropped_from_legacy_db(self, tmp_path):
        """Opening a registry over a pre-ADR-0032 DB (which still has the
        Group tables) drops them — idempotently across reopens."""
        import sqlite3
        db = str(tmp_path / "legacy.db")
        conn = sqlite3.connect(db)
        conn.executescript(
            "CREATE TABLE devices (device_id TEXT PRIMARY KEY, "
            "info_json TEXT NOT NULL);"
            "CREATE TABLE device_groups (group_id TEXT PRIMARY KEY, "
            "site_id TEXT, name TEXT);"
            "CREATE TABLE device_group_memberships (device_id TEXT, "
            "group_id TEXT, is_primary INTEGER, added_at REAL);"
            "INSERT INTO device_groups VALUES ('ungrouped', 'default', "
            "'Ungrouped');"
        )
        conn.commit()
        conn.close()
        for _ in range(2):  # idempotent across reopens
            SQLiteDeviceRegistry(
                db_path=db, key_path=str(tmp_path / "k.key"),
            )
            names = {
                r[0]
                for r in sqlite3.connect(db).execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert "device_groups" not in names
            assert "device_group_memberships" not in names
            assert {"devices", "organizations", "sites"}.issubset(names)


# ---------------------------------------------------------------------------
# Organization CRUD
# ---------------------------------------------------------------------------


class TestOrganizationCRUD:
    def test_add_and_get(self, registry):
        registry.add_organization(
            org_id="axis-comm",
            name="Axis Communications",
            repo_path="/tmp/r",
            repo_remote_url="git@example.com:axis/x.git",
            metadata={"hint": "demo"},
        )
        o = registry.get_organization("axis-comm")
        assert o["org_id"] == "axis-comm"
        assert o["name"] == "Axis Communications"
        assert o["repo_path"] == "/tmp/r"
        assert o["repo_remote_url"] == "git@example.com:axis/x.git"
        assert o["metadata"] == {"hint": "demo"}

    def test_get_missing_returns_none(self, registry):
        assert registry.get_organization("nope") is None

    def test_duplicate_pk_raises(self, registry):
        registry.add_organization("axis-comm", "Axis", "/tmp/r")
        with pytest.raises(BackendError, match="already exists"):
            registry.add_organization("axis-comm", "Axis Again", "/tmp/r")

    def test_list_orders_by_id(self, registry):
        registry.add_organization("zorg", "Z", "/tmp/z")
        registry.add_organization("aorg", "A", "/tmp/a")
        ids = [o["org_id"] for o in registry.list_organizations()]
        assert ids == ["aorg", "zorg"]

    def test_update_only_allowed_fields(self, registry, org):
        registry.update_organization(
            org, {"name": "Renamed", "repo_remote_url": "git@new.com:x.git"}
        )
        o = registry.get_organization(org)
        assert o["name"] == "Renamed"
        assert o["repo_remote_url"] == "git@new.com:x.git"

    def test_update_immutable_repo_path_is_ignored(self, registry, org):
        # repo_path is filesystem-bound; the update_organization signature
        # ignores it for safety.
        registry.update_organization(org, {"repo_path": "/somewhere/else"})
        o = registry.get_organization(org)
        assert o["repo_path"] == "/tmp/test-repos/axis-comm"

    def test_remove_with_child_site_refuses(self, registry, site):
        with pytest.raises(BackendError, match="site"):
            registry.remove_organization(site[0])

    def test_remove_when_empty(self, registry, org):
        # No sites / devices — should work.
        registry.remove_organization(org)
        assert registry.get_organization(org) is None

    def test_invalid_org_id_rejected(self, registry):
        # CR-5 validator should reject path-traversal-shaped IDs.
        with pytest.raises(ValueError):
            registry.add_organization(
                "../escape", "evil", "/tmp/r",
            )


# ---------------------------------------------------------------------------
# Site CRUD
# ---------------------------------------------------------------------------


class TestSiteCRUD:
    def test_add_and_get(self, registry, org):
        registry.add_site(
            "aec", org, "AEC Chicago", location="Chicago, IL",
        )
        s = registry.get_site("aec")
        assert s["site_id"] == "aec"
        assert s["org_id"] == org
        assert s["name"] == "AEC Chicago"
        assert s["location"] == "Chicago, IL"

    def test_add_site_with_missing_org_fails(self, registry):
        with pytest.raises(BackendError, match="Parent Org"):
            registry.add_site("aec", "no-such-org", "AEC")

    def test_list_filtered_by_org(self, registry):
        registry.add_organization("org-a", "A", "/tmp/a")
        registry.add_organization("org-b", "B", "/tmp/b")
        registry.add_site("site-1", "org-a", "Site 1")
        registry.add_site("site-2", "org-a", "Site 2")
        registry.add_site("site-3", "org-b", "Site 3")
        a_sites = registry.list_sites(org_id="org-a")
        assert {s["site_id"] for s in a_sites} == {"site-1", "site-2"}

    def test_update_site(self, registry, site):
        registry.update_site(site[1], {"name": "AEC NYC", "location": "NY"})
        s = registry.get_site(site[1])
        assert s["name"] == "AEC NYC"
        assert s["location"] == "NY"

    def test_remove_empty_site(self, registry, site):
        registry.remove_site(site[1])
        assert registry.get_site(site[1]) is None

    def test_remove_site_with_devices_refuses(self, registry, site):
        registry.add_device("cam-01", {"host": "192.0.2.1"})
        registry.set_device_org_site("cam-01", site[0], site[1])
        with pytest.raises(BackendError, match="device"):
            registry.remove_site(site[1])


# ---------------------------------------------------------------------------
# Device → Org/Site assignment
# ---------------------------------------------------------------------------


class TestDeviceOrgSite:
    @pytest.fixture
    def cam(self, registry, site):
        registry.add_device("cam-01", {"host": "192.0.2.1"})
        return "cam-01"

    def test_set_and_get(self, registry, site, cam):
        registry.set_device_org_site(cam, site[0], site[1])
        result = registry.get_device_org_site(cam)
        assert result == {"org_id": site[0], "site_id": site[1]}

    def test_get_for_a_new_device_returns_the_local_site(self, registry, cam):
        """A brand-new device belongs to a site (GH #427).

        This test previously asserted the opposite — that a new device had NULL
        columns — which was an accurate description of the defect: `add_device`
        never wrote them, a one-shot migration assigned them once, and every
        device added afterwards was outside every site. That produced 5 in the
        nav and 11 on the roster from one registry.
        """
        got = registry.get_device_org_site(cam) or {}
        assert got.get("site_id"), "a device in the registry must belong to a site"

    def test_get_for_a_device_stranded_before_the_fix_returns_none(self, registry, cam):
        """The NULL state still has to be readable — six production devices are
        in it, and the startup backfill has to be able to find them."""
        import sqlite3

        with sqlite3.connect(registry._db_path) as conn:
            conn.execute(
                "UPDATE devices SET org_id=NULL, site_id=NULL WHERE device_id=?",
                (cam,),
            )
            conn.commit()
        assert registry.get_device_org_site(cam) is None

    def test_site_must_belong_to_org(self, registry, cam):
        registry.add_organization("org-a", "A", "/tmp/a")
        registry.add_organization("org-b", "B", "/tmp/b")
        registry.add_site("site-x", "org-a", "X")
        # Trying to assign cam to (org-b, site-x) — but site-x is
        # under org-a, not org-b.
        with pytest.raises(BackendError, match="belongs to Org"):
            registry.set_device_org_site(cam, "org-b", "site-x")


# ---------------------------------------------------------------------------
# Default hierarchy bootstrap in build_components
# ---------------------------------------------------------------------------


def _isolate_admz_env(tmp_path, monkeypatch):
    """Common boilerplate for tests that call build_components.

    Points every ADMZ-rooted path under tmp_path BEFORE importing
    components (which transitively imports fleet_settings — a
    module-level singleton that opens its own DB at import time).
    Re-points the fleet_settings singleton to a fresh in-tmp_path
    instance to defeat the import-timing capture other tests may
    have already triggered.
    """
    db_path = tmp_path / "admz.db"
    monkeypatch.setenv("ADMZ_DB_PATH", str(db_path))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_REPO_PATH_ROOT", str(tmp_path / "repos"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from admz import fleet_settings as fs_module
    fresh_fs = fs_module.FleetSettings(str(db_path))
    monkeypatch.setattr(fs_module, "fleet_settings", fresh_fs)

    # The fleet.health module captures its own reference; repoint
    # that too. health.py:47 does `import admz.fleet_settings as
    # _fs_module` then uses _fs_module.fleet_settings at call time
    # so the monkeypatched attribute is picked up — no action needed.
    return db_path


class TestDefaultBootstrap:
    def test_creates_default_org_site(self, tmp_path, monkeypatch):
        db_path = _isolate_admz_env(tmp_path, monkeypatch)
        registry = SQLiteDeviceRegistry(
            db_path=str(db_path),
            key_path=str(tmp_path / "admz.key"),
        )
        from admz.components import build_components
        build_components(
            registry,
            catalog_path=str(tmp_path / "catalog-stub"),
            config_repo_path=str(tmp_path / "config-repo"),
        )
        assert registry.get_organization("default") is not None
        assert registry.get_site("default") is not None
        # ADR-0032: no Group level — the ABC stub raises.
        assert not hasattr(registry, "get_device_group")

    def test_bootstrap_idempotent(self, tmp_path, monkeypatch):
        db_path = _isolate_admz_env(tmp_path, monkeypatch)
        registry = SQLiteDeviceRegistry(
            db_path=str(db_path),
            key_path=str(tmp_path / "admz.key"),
        )
        from admz.components import build_components
        for _ in range(3):
            build_components(
                registry,
                catalog_path=str(tmp_path / "catalog-stub"),
                config_repo_path=str(tmp_path / "config-repo"),
            )
        orgs = registry.list_organizations()
        assert len([o for o in orgs if o["org_id"] == "default"]) == 1

    def test_adopts_existing_legacy_origin(self, tmp_path, monkeypatch):
        # Simulate the homelab user: ~/.admz/config-repo/ already
        # exists with an `origin` remote configured by hand. The
        # bootstrap must adopt that URL into default.repo_remote_url.
        legacy = tmp_path / "config-repo"
        legacy.mkdir()
        subprocess.run(
            ["git", "init", str(legacy)], check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(legacy), "remote", "add", "origin",
             "https://github.com/pettheory/admz-config-homelab.git"],
            check=True, capture_output=True,
        )

        db_path = _isolate_admz_env(tmp_path, monkeypatch)
        registry = SQLiteDeviceRegistry(
            db_path=str(db_path),
            key_path=str(tmp_path / "admz.key"),
        )
        from admz.components import build_components
        build_components(
            registry,
            catalog_path=str(tmp_path / "catalog-stub"),
            config_repo_path=str(legacy),
        )
        default = registry.get_organization("default")
        assert default["repo_path"] == str(legacy)
        assert default["repo_remote_url"] == (
            "https://github.com/pettheory/admz-config-homelab.git"
        )
