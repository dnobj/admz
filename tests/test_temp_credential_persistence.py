"""GH #314: a temp device account must not outlive ADMZ's record of it.

`TempCredentialManager` was an in-memory dict, and all three failure modes came
from that: a dead process lost the record entirely; exhausting cleanup retries
*deleted* the record; the shutdown sweep was graceful-only. The sharpest
instance was not an unlucky race — the MCP server is a per-principal subprocess
reaped after `ADMZ_MCP_POOL_IDLE_SECONDS` (default 300 s) while the TTL ceiling
was 3600 s, so the default configuration permitted a credential outliving its
own tracker by 55 minutes.

An orphaned temp account is indistinguishable from a permanent one: same group,
same capabilities, and Axis devices do not expire accounts.

**The vacuity shape.** "the record survives" is trivially green if nothing was
ever written, and "the account is not deleted" is trivially green if the code
never reaches the give-up branch. So every persistence test asserts through a
*second, independent manager instance* (proving the row is in the file, not the
object), and the orphan tests assert the give-up branch was actually taken.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from admz.mcp.temp_credentials import (
    MAX_TTL_SECONDS,
    MIN_TTL_SECONDS,
    STATE_ACTIVE,
    STATE_ORPHANED,
    TempCredential,
    TempCredentialManager,
    clamp_ttl,
    max_ttl_seconds,
)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Mandatory: no test may reach a real database.

    Both `ADMZ_HOME` and `ADMZ_DB_PATH` are redirected, so even a manager
    constructed with no explicit path resolves inside tmp_path.
    """
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    yield tmp_path


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "temp.db")


def _cred(username="at_deadbeef", device="cam-01", ttl=300, age=0.0):
    return TempCredential(
        device_id=device, username=username, password="tempsecret",
        group="users", created_at=time.time() - age, ttl_seconds=ttl,
    )


# --- persistence: the record outlives the object ---------------------------


def test_record_survives_a_new_manager(db):
    """THE #314 fix. A second manager is a stand-in for a new process — the
    dict-backed version returned nothing here, which is the whole defect."""
    TempCredentialManager(db_path=db).register(_cred())

    fresh = TempCredentialManager(db_path=db)
    rows = fresh.get_all()

    assert len(rows) == 1
    assert (rows[0].device_id, rows[0].username) == ("cam-01", "at_deadbeef")


def test_the_record_is_actually_in_the_file(db):
    """Anti-vacuity for the test above: assert the bytes, not just the API.

    A manager that cached in a class attribute would satisfy `get_all` across
    instances while still losing everything on process death.
    """
    TempCredentialManager(db_path=db).register(_cred())

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT device_id, username, state FROM temp_credentials").fetchall()
    finally:
        conn.close()

    assert rows == [("cam-01", "at_deadbeef", STATE_ACTIVE)]


def test_the_temp_password_is_never_written_to_the_database(db):
    """Cleanup authenticates as the registry admin, never as the temp user, so
    the temp password has no reason to be at rest — and a stolen database must
    not yield a live device credential."""
    TempCredentialManager(db_path=db).register(_cred())

    from pathlib import Path
    assert b"tempsecret" not in Path(db).read_bytes(), (
        "the temp password was persisted")


def test_no_io_in_the_constructor(tmp_path):
    """#254/#258: constructing a store must not touch the filesystem."""
    target = tmp_path / "nested" / "late.db"
    mgr = TempCredentialManager(db_path=str(target))
    assert not target.exists(), "the constructor did I/O"

    mgr.register(_cred())
    assert target.exists()


def test_the_default_path_resolves_at_call_time_not_construction(tmp_path,
                                                                 monkeypatch):
    """#258, on the *default* path — the branch the test above cannot reach.

    A manager built with no explicit path must honour an ``ADMZ_DB_PATH`` set
    **after** construction. Binding it in ``__init__`` is what froze the path
    for the life of the process and is how a test could reach a real database.

    Mutation testing found this gap: making ``__init__`` eagerly resolve
    ``_default_db_path()`` produced zero failures, because every other test
    here sets the env var before constructing.
    """
    mgr = TempCredentialManager()          # no explicit path, nothing resolved yet

    later = tmp_path / "moved" / "admz.db"
    monkeypatch.setenv("ADMZ_DB_PATH", str(later))

    mgr.register(_cred())

    assert later.exists(), (
        "the write did not land at the path set after construction — the store "
        "bound its path in __init__")
    assert mgr._db_path == str(later)


# --- the give-up branch keeps the record -----------------------------------


def test_marking_orphaned_keeps_the_row(db):
    """The #314 defect in miniature: giving up used to DELETE the record."""
    mgr = TempCredentialManager(db_path=db)
    mgr.register(_cred())

    mgr.mark_orphaned("cam-01", "at_deadbeef", error="device unreachable")

    assert TempCredentialManager(db_path=db).list_orphaned(), (
        "the record was destroyed at exactly the moment it became interesting")
    row = TempCredentialManager(db_path=db).list_orphaned()[0]
    assert row.state == STATE_ORPHANED
    assert "unreachable" in row.last_error


def test_orphaned_rows_are_not_returned_as_cleanup_work(db):
    """They exhausted their attempts. Silently re-attempting would re-hide the
    thing this issue exists to surface."""
    mgr = TempCredentialManager(db_path=db)
    mgr.register(_cred(ttl=60, age=600))
    assert mgr.get_expired(), "control: it should be due for cleanup first"

    mgr.mark_orphaned("cam-01", "at_deadbeef")
    assert mgr.get_expired() == []
    assert mgr.get_all() == []


def test_orphaned_rows_do_not_consume_the_per_device_limit(db):
    """A past failure must not lock an operator out of creating new
    credentials — the orphan is surfaced, not charged for."""
    mgr = TempCredentialManager(db_path=db)
    for i in range(mgr.max_per_device):
        mgr.register(_cred(username=f"at_{i:08d}"))
        mgr.mark_orphaned("cam-01", f"at_{i:08d}")

    assert mgr.count_active_for_device("cam-01") == 0


def test_remove_deletes_only_after_confirmed_removal(db):
    mgr = TempCredentialManager(db_path=db)
    mgr.register(_cred())
    assert mgr.remove("cam-01", "at_deadbeef") is not None
    assert TempCredentialManager(db_path=db).get_all() == []


def test_cleanup_failures_accumulate_across_processes(db):
    """The counter is the thing that decides orphaning, so it has to survive
    the restart too — otherwise a process that restarts often never gives up
    and never surfaces the account."""
    TempCredentialManager(db_path=db).register(_cred())

    for expected in (1, 2, 3):
        n = TempCredentialManager(db_path=db).record_cleanup_failure(
            "cam-01", "at_deadbeef", error="boom")
        assert n == expected


# --- the TTL ceiling reconciliation ----------------------------------------


def test_ttl_ceiling_is_reconciled_against_the_pool_reaper(monkeypatch):
    """A credential must not outlive the process that cleans it up."""
    monkeypatch.setenv("ADMZ_MCP_POOL_IDLE_SECONDS", "300")
    assert max_ttl_seconds() == 300
    assert clamp_ttl(3600) == 300, (
        "a 1h credential is still permitted against a 300s reaper")


def test_a_longer_reaper_permits_a_longer_ttl(monkeypatch):
    monkeypatch.setenv("ADMZ_MCP_POOL_IDLE_SECONDS", "7200")
    assert max_ttl_seconds() == MAX_TTL_SECONDS, "capped by the nominal ceiling"
    assert clamp_ttl(3600) == 3600


def test_the_ceiling_never_falls_below_the_floor(monkeypatch):
    """A tiny idle timeout must shorten credentials, not make every request
    fail by producing a ceiling under the minimum."""
    monkeypatch.setenv("ADMZ_MCP_POOL_IDLE_SECONDS", "5")
    assert max_ttl_seconds() == MIN_TTL_SECONDS
    assert clamp_ttl(300) == MIN_TTL_SECONDS


def test_ttl_floor_still_applies(monkeypatch):
    monkeypatch.setenv("ADMZ_MCP_POOL_IDLE_SECONDS", "3600")
    assert clamp_ttl(1) == MIN_TTL_SECONDS


def test_no_pool_means_no_ceiling(monkeypatch):
    """Standalone `python -m admz mcp` has no reaper to outlive."""
    monkeypatch.setenv("ADMZ_MCP_STANDALONE", "1")
    assert max_ttl_seconds() == MAX_TTL_SECONDS


# --- startup reconciliation ------------------------------------------------


def _server_with(mgr, *, removal_succeeds=True):
    """A stand-in exposing only what _reconcile_temp_credentials touches."""
    from admz.mcp.server import ADMZMCPServer

    srv = object.__new__(ADMZMCPServer)
    srv.temp_creds = mgr
    srv._remove_temp_user = AsyncMock(return_value=removal_succeeds)
    return srv


def test_reconciliation_retries_a_record_left_by_a_dead_process(db):
    """What turns "we lost it" into "we retry it".

    Before persistence this could not exist: a dead process took its only
    knowledge of the account with it, so there was nothing to reconcile.
    """
    TempCredentialManager(db_path=db).register(_cred(ttl=60, age=600))

    mgr = TempCredentialManager(db_path=db)
    srv = _server_with(mgr, removal_succeeds=True)
    counts = asyncio.run(srv._reconcile_temp_credentials())

    assert counts == {"checked": 1, "removed": 1, "failed": 0}
    srv._remove_temp_user.assert_awaited_once()
    assert TempCredentialManager(db_path=db).get_all() == [], (
        "the device account was removed but the record was left behind")


def test_reconciliation_leaves_unexpired_records_alone(db):
    """Anti-vacuity: it must not simply delete everything it finds."""
    TempCredentialManager(db_path=db).register(_cred(ttl=3600, age=0))

    mgr = TempCredentialManager(db_path=db)
    srv = _server_with(mgr)
    counts = asyncio.run(srv._reconcile_temp_credentials())

    assert counts["checked"] == 0
    srv._remove_temp_user.assert_not_awaited()
    assert len(TempCredentialManager(db_path=db).get_all()) == 1


def test_a_failed_reconciliation_records_the_attempt_and_keeps_the_row(db):
    TempCredentialManager(db_path=db).register(_cred(ttl=60, age=600))

    mgr = TempCredentialManager(db_path=db)
    srv = _server_with(mgr, removal_succeeds=False)
    counts = asyncio.run(srv._reconcile_temp_credentials())

    assert counts == {"checked": 1, "removed": 0, "failed": 1}
    rows = TempCredentialManager(db_path=db).get_all()
    assert len(rows) == 1, "a failed removal must not drop the record"
    assert rows[0].cleanup_attempts == 1


def test_reconciliation_does_not_retry_orphaned_records(db):
    mgr = TempCredentialManager(db_path=db)
    mgr.register(_cred(ttl=60, age=600))
    mgr.mark_orphaned("cam-01", "at_deadbeef")

    srv = _server_with(mgr)
    counts = asyncio.run(srv._reconcile_temp_credentials())

    assert counts["checked"] == 0
    srv._remove_temp_user.assert_not_awaited()
    assert len(mgr.list_orphaned()) == 1, "the orphan must stay listed"


def test_reconciliation_never_raises_on_an_unreadable_store(db, monkeypatch):
    """A device offline at startup, or an unreadable DB, must not stop the MCP
    server from starting."""
    mgr = TempCredentialManager(db_path=db)
    monkeypatch.setattr(
        TempCredentialManager, "get_all",
        MagicMock(side_effect=sqlite3.OperationalError("database is locked")))

    counts = asyncio.run(_server_with(mgr)._reconcile_temp_credentials())
    assert counts == {"checked": 0, "removed": 0, "failed": 0}


# --- the cleanup loop's give-up branch -------------------------------------
#
# These exist because mutation testing found the gap: restoring the #314 defect
# (give-up deletes the record) produced ZERO red, since the branch lived inside
# a `while True: await sleep(30)` body no test could drive. The loop body is now
# `_cleanup_expired_temp_credentials`, and these pin it.


def _exhausted(mgr, username="at_deadbeef"):
    """Drive a record to the give-up threshold through the real API."""
    for _ in range(mgr.max_cleanup_attempts):
        mgr.record_cleanup_failure("cam-01", username, error="boom")


def test_giving_up_marks_orphaned_and_does_not_delete(db):
    """THE #314 defect. This is the assertion that was missing."""
    mgr = TempCredentialManager(db_path=db)
    mgr.register(_cred(ttl=60, age=600))
    _exhausted(mgr)

    srv = _server_with(mgr)
    counts = asyncio.run(srv._cleanup_expired_temp_credentials())

    assert counts["orphaned"] == 1, "the give-up branch was not taken"
    srv._remove_temp_user.assert_not_awaited(), "attempts were exhausted"

    fresh = TempCredentialManager(db_path=db)
    assert fresh.get_all() == [], "it should no longer be active work"
    orphans = fresh.list_orphaned()
    assert len(orphans) == 1, "the record was DELETED — the #314 defect"
    assert orphans[0].username == "at_deadbeef"


def test_a_successful_pass_removes_both_account_and_record(db):
    """The pair. Without it, the test above passes for a cleanup that never
    removes anything at all."""
    mgr = TempCredentialManager(db_path=db)
    mgr.register(_cred(ttl=60, age=600))

    srv = _server_with(mgr, removal_succeeds=True)
    counts = asyncio.run(srv._cleanup_expired_temp_credentials())

    assert counts == {"removed": 1, "failed": 0, "orphaned": 0}
    srv._remove_temp_user.assert_awaited_once()
    assert TempCredentialManager(db_path=db).list_orphaned() == []
    assert TempCredentialManager(db_path=db).get_all() == []


def test_a_failed_pass_increments_the_counter_and_keeps_the_row(db):
    """Without the increment a record would retry forever and never surface."""
    mgr = TempCredentialManager(db_path=db)
    mgr.register(_cred(ttl=60, age=600))

    srv = _server_with(mgr, removal_succeeds=False)
    counts = asyncio.run(srv._cleanup_expired_temp_credentials())

    assert counts == {"removed": 0, "failed": 1, "orphaned": 0}
    rows = TempCredentialManager(db_path=db).get_all()
    assert len(rows) == 1
    assert rows[0].cleanup_attempts == 1, "the attempt was not recorded"


def test_repeated_failures_eventually_orphan_rather_than_retry_forever(db):
    """End to end through the real API: N failed passes, then the give-up."""
    mgr = TempCredentialManager(db_path=db)
    mgr.register(_cred(ttl=60, age=600))
    srv = _server_with(mgr, removal_succeeds=False)

    for _ in range(mgr.max_cleanup_attempts):
        asyncio.run(srv._cleanup_expired_temp_credentials())

    final = asyncio.run(srv._cleanup_expired_temp_credentials())
    assert final["orphaned"] == 1
    assert len(TempCredentialManager(db_path=db).list_orphaned()) == 1


def test_one_unreachable_device_does_not_stop_the_pass(db):
    """A raising removal must be a counted failure, not an escape."""
    mgr = TempCredentialManager(db_path=db)
    mgr.register(_cred(username="at_00000001", ttl=60, age=600))
    mgr.register(_cred(username="at_00000002", ttl=60, age=600))

    srv = _server_with(mgr)
    srv._remove_temp_user = AsyncMock(side_effect=RuntimeError("connreset"))
    counts = asyncio.run(srv._cleanup_expired_temp_credentials())

    assert counts["failed"] == 2, "the pass stopped at the first bad device"
    assert len(TempCredentialManager(db_path=db).get_all()) == 2


def test_a_raising_removal_is_counted_as_failure_not_propagated(db):
    TempCredentialManager(db_path=db).register(_cred(ttl=60, age=600))

    mgr = TempCredentialManager(db_path=db)
    srv = _server_with(mgr)
    srv._remove_temp_user = AsyncMock(side_effect=RuntimeError("connreset"))

    counts = asyncio.run(srv._reconcile_temp_credentials())
    assert counts["failed"] == 1
    assert len(TempCredentialManager(db_path=db).get_all()) == 1
