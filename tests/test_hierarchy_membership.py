"""Every device belongs to a site, and both counters agree (GH #427).

An operator saw 5 devices in the sidebar and 11 on the roster page, from one
registry. Two causes, both covered here:

* ``add_device`` never wrote ``org_id``/``site_id``, so every device added
  after the one-shot backfill had none.
* the nav counted with strict equality (NULL dropped) while the roster kept
  NULL devices — one rule, stated twice, two ways.
"""

from __future__ import annotations

import pytest

from admz.hierarchy import device_is_in_site


# ── the shared predicate ────────────────────────────────────────────────────

def test_a_device_in_the_active_site_is_in_scope():
    assert device_is_in_site("default", "default") is True


def test_a_device_in_a_DIFFERENT_site_is_not():
    """Control for the test above — the predicate must still discriminate."""
    assert device_is_in_site("warehouse", "default") is False


def test_a_device_with_no_site_is_treated_as_in_scope():
    """The disagreement that produced 5-vs-11.

    A NULL is a gap in ADMZ's records, not a device that lives elsewhere.
    Hiding it would make it unmanageable rather than merely miscounted.
    """
    assert device_is_in_site(None, "default") is True
    assert device_is_in_site("", "default") is True


def test_with_no_active_site_everything_is_in_scope():
    """A registry with no hierarchy at all (e.g. Vault) must still render."""
    assert device_is_in_site("anything", None) is True
    assert device_is_in_site(None, None) is True


# ── add_device assigns a site ───────────────────────────────────────────────

@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry

    reg = SQLiteDeviceRegistry(db_path=str(tmp_path / "t.db"))
    reg.add_organization("default", "Default Organization", str(tmp_path / "repo"))
    reg.add_site("default", "default", "Default Site")
    return reg


def test_a_newly_added_device_lands_in_the_site(registry):
    registry.add_device("AABBCCDDEEFF", {"host": "10.0.0.1"})
    got = registry.get_device_org_site("AABBCCDDEEFF") or {}
    assert got.get("site_id") == "default", (
        "a device added through the registry must belong to a site — this is "
        "the defect that put 6 of 11 devices outside every site"
    )
    assert got.get("org_id") == "default"


def test_it_uses_the_declared_site_not_the_literal_string_default(tmp_path, monkeypatch):
    """An operator who renamed or replaced their site still gets devices in it.

    Hard-coding ``"default"`` would put new devices in a site id that does not
    exist, which is the same invisible-orphan failure wearing a different name.
    """
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry

    reg = SQLiteDeviceRegistry(db_path=str(tmp_path / "t2.db"))
    reg.add_organization("acme", "Acme", str(tmp_path / "repo2"))
    reg.add_site("hq", "acme", "Head Office")
    reg.add_device("AABBCCDDEE01", {"host": "10.0.0.2"})
    got = reg.get_device_org_site("AABBCCDDEE01") or {}
    assert got.get("site_id") == "hq" and got.get("org_id") == "acme"


def test_an_add_still_works_with_no_hierarchy_at_all(tmp_path, monkeypatch):
    """An add must never fail because the hierarchy is missing."""
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry

    reg = SQLiteDeviceRegistry(db_path=str(tmp_path / "t3.db"))
    reg.add_device("AABBCCDDEE02", {"host": "10.0.0.3"})
    assert reg.device_exists("AABBCCDDEE02")


# ── the backfill heals what was already stranded ────────────────────────────

def test_the_backfill_assigns_a_site_to_a_stranded_device(registry):
    from admz.migrations.hierarchy_backfill import migrate_hierarchy_backfill

    import sqlite3

    registry.add_device("AABBCCDDEE03", {"host": "10.0.0.4"})
    # Strand it the way production's six stranded devices actually are: NULL in
    # the columns. `set_device_org_site` refuses None (it validates the org
    # exists), which is correct for the API and useless for reproducing the bug.
    with sqlite3.connect(registry._db_path) as conn:
        conn.execute(
            "UPDATE devices SET org_id=NULL, site_id=NULL WHERE device_id=?",
            ("AABBCCDDEE03",),
        )
        conn.commit()
    assert (registry.get_device_org_site("AABBCCDDEE03") or {}).get("site_id") in (None, "")

    result = migrate_hierarchy_backfill(registry)
    assert result["backfilled"] >= 1
    assert (registry.get_device_org_site("AABBCCDDEE03") or {}).get("site_id") == "default"


def test_the_backfill_is_idempotent(registry):
    """Control: a second run must change nothing, since it runs every startup."""
    from admz.migrations.hierarchy_backfill import migrate_hierarchy_backfill

    registry.add_device("AABBCCDDEE04", {"host": "10.0.0.5"})
    migrate_hierarchy_backfill(registry)
    second = migrate_hierarchy_backfill(registry)
    assert second["backfilled"] == 0
