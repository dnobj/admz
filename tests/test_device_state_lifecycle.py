"""Per-device state must not outlive the device (GH #428).

Production had 14 ``device_health`` rows for 11 devices, and the extras were
reported to the operator as three devices "unreachable" — none were. The same
leak was in every per-device table other stores own: 2,153 orphaned drift
alerts at the time this was written.

Each test that proves something is deleted is paired with one proving the
neighbouring device's rows are NOT — a cascade that takes everything with it
passes the first kind of test just as well as a correct one.
"""

from __future__ import annotations

import sqlite3

import pytest


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry

    reg = SQLiteDeviceRegistry(db_path=str(tmp_path / "t.db"))
    reg.add_device("AAAAAAAAAAAA", {"host": "10.0.0.1"})
    reg.add_device("BBBBBBBBBBBB", {"host": "10.0.0.2"})
    return reg


def _seed_state(reg, *device_ids):
    """Rows in every state table, the way the owning stores would write them.

    Minimal schemas: the tests care that a row keyed on ``device_id`` exists,
    not what the real store puts beside it. Created only if the store has not
    already — a fresh registry has none of these tables yet, which is itself a
    case ``remove_device`` has to survive.
    """
    with sqlite3.connect(reg._db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS device_health (device_id TEXT, status TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS drift_signatures (device_id TEXT, sig TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS drift_alerts (device_id TEXT, key TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS pending_device_actions (device_id TEXT, action TEXT)")
        for d in device_ids:
            conn.execute("INSERT INTO device_health VALUES (?, 'online')", (d,))
            conn.execute("INSERT INTO drift_signatures VALUES (?, 'sig')", (d,))
            conn.execute("INSERT INTO drift_alerts VALUES (?, 'k1')", (d,))
            conn.execute("INSERT INTO drift_alerts VALUES (?, 'k2')", (d,))
            conn.execute("INSERT INTO pending_device_actions VALUES (?, 'x')", (d,))
        conn.commit()


def _count(reg, table, device_id):
    with sqlite3.connect(reg._db_path) as conn:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE device_id=?", (device_id,)
        ).fetchone()[0]


STATE_TABLES = ("device_health", "drift_signatures", "drift_alerts", "pending_device_actions")


# ── remove_device cascades ──────────────────────────────────────────────────

@pytest.mark.parametrize("table", STATE_TABLES)
def test_removing_a_device_removes_its_state(registry, table):
    _seed_state(registry, "AAAAAAAAAAAA", "BBBBBBBBBBBB")
    assert _count(registry, table, "AAAAAAAAAAAA") > 0
    registry.remove_device("AAAAAAAAAAAA")
    assert _count(registry, table, "AAAAAAAAAAAA") == 0, (
        f"{table} row outlived its device — this is the ghost that reported "
        f"'unreachable' for a device that no longer existed"
    )


@pytest.mark.parametrize("table", STATE_TABLES)
def test_removing_a_device_leaves_its_NEIGHBOUR_alone(registry, table):
    """Control: a cascade that takes everything passes the test above too."""
    _seed_state(registry, "AAAAAAAAAAAA", "BBBBBBBBBBBB")
    before = _count(registry, table, "BBBBBBBBBBBB")
    registry.remove_device("AAAAAAAAAAAA")
    assert _count(registry, table, "BBBBBBBBBBBB") == before


def test_removing_a_device_works_before_any_state_table_exists(registry):
    """A fresh install may remove a device before the health monitor has ever
    run — the tables are created by their own stores on first use."""
    registry.remove_device("AAAAAAAAAAAA")
    assert not registry.device_exists("AAAAAAAAAAAA")


def test_the_purge_is_in_the_same_transaction(registry, monkeypatch):
    """If anything after the purge fails, the purge must roll back too. A
    half-removed device with no health row is worse than one with a stale row.

    Injected AFTER the real purge has run its deletes on the open connection,
    so the assertion below is specifically that those deletes were not
    committed on their own. (sqlite3.Connection.execute is C-level and cannot
    be patched, which is why the seam is the purge helper.)"""
    _seed_state(registry, "AAAAAAAAAAAA")

    class _Boom(Exception):
        pass

    real_purge = registry._purge_device_state

    def purge_then_break(conn, device_id):
        purged = real_purge(conn, device_id)          # deletes issued on conn
        assert purged.get("device_health") == 1       # ...and they did run
        raise _Boom("simulated failure after the purge, before commit")

    monkeypatch.setattr(registry, "_purge_device_state", purge_then_break)
    with pytest.raises(_Boom):
        registry.remove_device("AAAAAAAAAAAA")
    monkeypatch.undo()
    # The `with self._connect() as conn:` block exited on the exception with
    # no commit, so the purge's deletes must have rolled back with it.
    assert registry.device_exists("AAAAAAAAAAAA")
    assert _count(registry, "device_health", "AAAAAAAAAAAA") == 1, (
        "the purge's deletes survived a failed remove — it committed on its own"
    )


# ── the startup sweep heals what already leaked ─────────────────────────────

def test_the_sweep_removes_orphans_and_reports_them(registry):
    _seed_state(registry, "AAAAAAAAAAAA", "BBBBBBBBBBBB", "GHOST-1", "P8815-2")
    result = registry.purge_orphaned_device_state()
    assert result["device_health"] == 2
    assert result["drift_alerts"] == 4          # two rows per seeded device
    for table in STATE_TABLES:
        assert _count(registry, table, "GHOST-1") == 0
        assert _count(registry, table, "P8815-2") == 0


def test_the_sweep_leaves_live_devices_alone(registry):
    """Control for the test above."""
    _seed_state(registry, "AAAAAAAAAAAA", "BBBBBBBBBBBB", "GHOST-1")
    registry.purge_orphaned_device_state()
    for table in STATE_TABLES:
        assert _count(registry, table, "AAAAAAAAAAAA") > 0
        assert _count(registry, table, "BBBBBBBBBBBB") > 0


def test_the_sweep_is_idempotent(registry):
    """It runs every startup, so a second run must find nothing."""
    _seed_state(registry, "AAAAAAAAAAAA", "GHOST-1")
    first = registry.purge_orphaned_device_state()
    assert first
    second = registry.purge_orphaned_device_state()
    assert second == {}


def test_the_sweep_survives_missing_tables(registry):
    """Same fresh-install case as remove_device."""
    assert registry.purge_orphaned_device_state() == {}


# ── what is deliberately NOT cascaded ───────────────────────────────────────

def test_records_are_not_deleted_with_the_device(registry):
    """confirm_sessions and capture_sessions are audit-adjacent history.
    Deleting history because its subject left is a separate decision (#408 is
    about how much weight that trail carries), and this test pins that the
    cascade does not quietly make it."""
    with sqlite3.connect(registry._db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS confirm_sessions (token TEXT, device_id TEXT)")
        conn.execute("INSERT INTO confirm_sessions VALUES ('t1', 'AAAAAAAAAAAA')")
        conn.commit()
    registry.remove_device("AAAAAAAAAAAA")
    assert _count(registry, "confirm_sessions", "AAAAAAAAAAAA") == 1
