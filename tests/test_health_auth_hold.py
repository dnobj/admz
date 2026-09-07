"""#469 / ADR-0065 — a refused credential is not retried on the sweep cadence.

A device whose stored password stops working was re-probed with that password
every 60 s, forever: two to three failed authentications a minute, about 4,300
a day, unattended. `probe_device` read no previous record, so nothing knew the
credential had already been condemned.

The hold escalates (`min(interval * 2**(streak-1), MAX)`), and while it is in
force the sweep sends only what costs no authentication — so reachability
stays fresh and a factory reset stays visible. The two things this file exists
to stop going wrong: a held sweep must never re-derive a status (a device with
a credential would read `online` off the TCP tier and fire `on_online`), and a
held sweep must never count as an observed failure (GH #138).
"""

import sqlite3
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from admz.fleet.health import (
    AuthHold,
    DeviceHealthRecord,
    DeviceHealthStatus,
    DeviceHealthStore,
    HealthMonitor,
    _auth_hold_for,
    _auth_hold_note,
    _next_auth_retry_after,
    clear_auth_hold,
)

SYSTEMREADY_OP = "systemready.cgi:systemReady"
CORROBORATION_OP = "param.cgi:list"
AUTH_CHECK_OP = "basicdeviceinfo.cgi:getAllProperties"

REFUSED = MagicMock(success=False, status_code=401,
                    error="HTTP 401: Unauthorized", parsed_data={})


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setattr("admz.fleet.health._tcp_probe", AsyncMock(return_value=3))
    monkeypatch.setattr("admz.fleet.health._verify_credentials_enabled", lambda: True)
    return tmp_path


def _executor(op_results):
    """Per-op answers, recording every (op id, credentials) pair sent."""
    calls = []

    def _get_operation(_family, op_id):
        if op_id not in op_results:
            return None
        op = MagicMock()
        op.to_executor_dict.return_value = {"id": op_id}
        return op

    catalog = MagicMock()
    catalog.get_operation.side_effect = _get_operation

    async def _execute(op_dict, device_info, credentials, params=None):
        calls.append((op_dict["id"], dict(credentials or {})))
        outcome = op_results[op_dict["id"]]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    executor = MagicMock()
    executor.execute = _execute
    return catalog, executor, calls


def _systemready(needsetup):
    return MagicMock(
        success=True, status_code=200, error=None,
        parsed_data={"data": {"systemready": "yes",
                              "needsetup": "yes" if needsetup else "no",
                              "uptime": "120", "bootid": "b7"}},
    )


def _monitor(store, catalog=None, executor=None, password="wrong"):
    registry = MagicMock()
    registry.list_devices.return_value = [{"device_id": "cam-01", "host": "192.0.2.1"}]
    registry.get_credentials.return_value = {"username": "root", "password": password}
    return HealthMonitor(
        registry=registry, catalog=catalog,
        executors={"vapix": executor} if executor is not None else {},
        store=store,
    )


def _credentialed(calls):
    """Only the calls that carried a password — the ones that cost a login."""
    return [op for op, creds in calls if creds.get("password")]


# ---------------------------------------------------------------------------
# The hold itself
# ---------------------------------------------------------------------------


class TestTheSweepStopsSpendingLogins:
    @pytest.mark.asyncio
    async def test_the_second_sweep_sends_no_credentialed_operation(self, isolated):
        """The point of the issue. Sweep 1 condemns the credential; sweep 2
        must ask the device nothing about it."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        catalog, executor, calls = _executor(
            {SYSTEMREADY_OP: REFUSED, CORROBORATION_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)

        await monitor.sweep_once()
        after_first = len(_credentialed(calls))
        assert after_first >= 2, "control: the first sweep really does probe"
        assert store.get("cam-01").status is DeviceHealthStatus.AUTH_FAILED
        assert store.get("cam-01").auth_fail_streak == 1

        await monitor.sweep_once()
        assert len(_credentialed(calls)) == after_first, \
            "the second sweep spent no authentication"
        assert store.get("cam-01").status is DeviceHealthStatus.AUTH_FAILED

    @pytest.mark.asyncio
    async def test_the_hold_expires_and_the_streak_escalates(self, isolated):
        store = DeviceHealthStore(str(isolated / "admz.db"))
        catalog, executor, calls = _executor(
            {SYSTEMREADY_OP: REFUSED, CORROBORATION_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)

        await monitor.sweep_once()
        first = len(_credentialed(calls))
        assert store.get("cam-01").auth_fail_streak == 1

        # the deadline passes
        row = store.get("cam-01")
        row.auth_retry_after = time.time() - 1
        store.upsert(row)

        await monitor.sweep_once()
        assert len(_credentialed(calls)) > first, "the hold expired, so it asked again"
        after = store.get("cam-01")
        assert after.auth_fail_streak == 2, "and the next wait is longer"
        assert after.auth_retry_after > time.time()

    @pytest.mark.asyncio
    async def test_a_held_sweep_does_not_inflate_the_failure_counter(self, isolated):
        """GH #138: a sweep that asked nothing did not observe a failure."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), consecutive_failures=7,
            last_error="credentials rejected — both A and B refused them",
            auth_fail_streak=3, auth_retry_after=time.time() + 900,
        ))
        catalog, executor, calls = _executor({SYSTEMREADY_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)

        await monitor.sweep_once()
        await monitor.sweep_once()

        row = store.get("cam-01")
        assert row.consecutive_failures == 7, "no sweep observed a failure"
        assert row.auth_fail_streak == 3, "and none of them escalated the hold"
        assert _credentialed(calls) == []

    @pytest.mark.asyncio
    async def test_the_condemnation_reason_survives_and_stays_bounded(self, isolated):
        """`last_error` is what routes the operator to capture. The hold note
        is suffixed onto it, never substituted, and re-suffixing is idempotent
        so it cannot grow one sweep at a time."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), consecutive_failures=1,
            last_error="credentials rejected — both systemready and param.cgi refused them",
            auth_fail_streak=2, auth_retry_after=time.time() + 300,
        ))
        catalog, executor, _calls = _executor({SYSTEMREADY_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)

        await monitor.sweep_once()
        await monitor.sweep_once()
        await monitor.sweep_once()

        err = store.get("cam-01").last_error
        assert "credentials rejected" in err
        assert "param.cgi refused them" in err
        assert err.count("credential check held") == 1, "suffixed once, not once per sweep"
        assert len(err) <= 200


class TestHoldingIsNotKnowing:
    @pytest.mark.asyncio
    async def test_a_held_device_never_reads_online(self, isolated):
        """The landmine. A held device still HAS a credential, so a sweep that
        fell through to the TCP tier would file `online` and fire `on_online`
        at a device ADMZ cannot authenticate to — what FR-HLT-011 exists to
        prevent. The monitor here has no catalog or executor at all, which is
        the shape that skips every gate below Tier 0."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), consecutive_failures=1,
            last_error="credentials rejected — both A and B refused them",
            auth_fail_streak=1, auth_retry_after=time.time() + 600,
        ))
        monitor = _monitor(store, catalog=None, executor=None)

        with patch("admz.tasks.store.tasks_store.claim_for_event",
                   return_value=[]) as claim:
            await monitor.sweep_once()

        assert store.get("cam-01").status is DeviceHealthStatus.AUTH_FAILED
        assert [c for c in claim.call_args_list if "on_online" in str(c)] == []

    @pytest.mark.asyncio
    async def test_a_factory_reset_is_still_seen_while_held(self, isolated):
        """The hold suppresses authentication, not observation: `needsetup`
        arrives on the unauthenticated read, so the pre-authorised trigger
        still fires. And that read carries no credential."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), consecutive_failures=1,
            last_error="credentials rejected", auth_fail_streak=1,
            auth_retry_after=time.time() + 600,
        ))
        catalog, executor, calls = _executor({SYSTEMREADY_OP: _systemready(True)})
        monitor = _monitor(store, catalog, executor)

        await monitor.sweep_once()

        row = store.get("cam-01")
        assert row.status is DeviceHealthStatus.NEEDS_SETUP
        assert row.uptime_seconds == 120 and row.bootid == "b7"
        assert calls == [(SYSTEMREADY_OP, {"username": "", "password": ""})], \
            "asked with no credential at all"
        assert row.auth_fail_streak == 0 and row.auth_retry_after is None, \
            "the credential question no longer applies"

    @pytest.mark.asyncio
    async def test_a_held_device_that_stops_answering_is_unreachable(self, isolated):
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), consecutive_failures=1,
            last_error="credentials rejected", auth_fail_streak=2,
            auth_retry_after=time.time() + 600,
        ))
        catalog, executor, calls = _executor({SYSTEMREADY_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)

        with patch("admz.fleet.health._tcp_probe", AsyncMock(return_value=None)):
            await monitor.sweep_once()

        row = store.get("cam-01")
        assert row.status is DeviceHealthStatus.UNREACHABLE
        assert _credentialed(calls) == []
        assert row.auth_fail_streak == 2 and row.auth_retry_after is not None, \
            "a flap answers nothing about the credential, so the hold stands"

    @pytest.mark.asyncio
    async def test_the_hold_survives_an_intervening_unreachable(self, isolated):
        """Otherwise a device that flaps pays a full authenticated probe on
        every flap and the escalation never grows."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        catalog, executor, calls = _executor(
            {SYSTEMREADY_OP: REFUSED, CORROBORATION_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)

        await monitor.sweep_once()
        baseline = len(_credentialed(calls))

        with patch("admz.fleet.health._tcp_probe", AsyncMock(return_value=None)):
            await monitor.sweep_once()
        assert store.get("cam-01").status is DeviceHealthStatus.UNREACHABLE

        await monitor.sweep_once()
        assert len(_credentialed(calls)) == baseline, "still held after the flap"
        assert store.get("cam-01").auth_fail_streak == 1

    @pytest.mark.asyncio
    async def test_a_working_credential_clears_the_hold(self, isolated):
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), consecutive_failures=4,
            last_error="credentials rejected", auth_fail_streak=3,
            auth_retry_after=time.time() - 1,   # due
        ))
        catalog, executor, _calls = _executor(
            {SYSTEMREADY_OP: _systemready(False),
             AUTH_CHECK_OP: MagicMock(
                 success=True, status_code=200, error=None,
                 parsed_data={"data": {"propertyList": {"ProdNbr": "P3245"}}})})
        monitor = _monitor(store, catalog, executor)

        await monitor.sweep_once()

        row = store.get("cam-01")
        assert row.status is DeviceHealthStatus.ONLINE
        assert row.auth_fail_streak == 0 and row.auth_retry_after is None


class TestTheOperatorCanAlwaysAsk:
    @pytest.mark.asyncio
    async def test_force_bypasses_the_hold(self, isolated):
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), consecutive_failures=1,
            last_error="credentials rejected", auth_fail_streak=5,
            auth_retry_after=time.time() + 1800,
        ))
        catalog, executor, calls = _executor(
            {SYSTEMREADY_OP: REFUSED, CORROBORATION_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)

        await monitor.sweep_once()
        assert _credentialed(calls) == [], "control: the ordinary sweep holds"

        await monitor.sweep_once(force=True)
        assert _credentialed(calls) != [], "an operator who asks gets a check"

    def test_the_sweep_route_forces(self):
        """The only recovery path from the UI if a device is ever wedged."""
        import inspect

        from admz.api.routes import health as health_routes

        src = inspect.getsource(health_routes.trigger_health_sweep)
        assert "sweep_once(force=True)" in src


class TestTheCurve:
    def test_it_doubles_and_then_stops(self, isolated):
        now = 0.0
        waits = [round(_next_auth_retry_after(s, now)) for s in range(1, 8)]
        assert waits == [60, 120, 240, 480, 960, 1800, 1800]

    def test_it_is_bounded_however_long_the_streak(self, isolated):
        now = time.time()
        assert _next_auth_retry_after(40, now) - now <= 1800.0

    def test_a_clock_step_backwards_does_not_park_the_deadline(self, isolated):
        """An NTP correction or a resumed VM can leave a deadline far in the
        future. Anything beyond one whole ceiling is treated as due."""
        now = time.time()
        parked = DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            auth_retry_after=now + 30 * 24 * 3600,
        )
        assert _auth_hold_for(parked, now).active is False

        sane = DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            auth_retry_after=now + 300,
        )
        assert _auth_hold_for(sane, now).active is True

    def test_no_row_and_no_deadline_are_not_a_hold(self, isolated):
        now = time.time()
        assert _auth_hold_for(None, now).active is False
        assert _auth_hold_for(DeviceHealthRecord(
            device_id="c", status=DeviceHealthStatus.AUTH_FAILED), now).active is False

    def test_the_ceiling_can_be_switched_off(self, isolated, monkeypatch):
        from admz.fleet_settings import fleet_settings

        monkeypatch.setattr(fleet_settings, "get",
                            lambda k: "0" if k == "health_auth_hold_max_seconds" else None)
        now = time.time()
        assert _next_auth_retry_after(3, now) == 0.0
        assert _auth_hold_for(DeviceHealthRecord(
            device_id="c", status=DeviceHealthStatus.AUTH_FAILED,
            auth_retry_after=now + 300), now).active is False

    def test_the_note_never_replaces_the_condemnation(self):
        note = _auth_hold_note("credentials rejected — both A and B refused them", 900)
        assert note.startswith("credentials rejected — both A and B refused them")
        assert "15 min" in note
        assert _auth_hold_note(note, 60).count("credential check held") == 1


# ---------------------------------------------------------------------------
# The reset
# ---------------------------------------------------------------------------


class TestACredentialWriteEndsTheHold:
    def test_it_is_visible_to_another_process(self, isolated):
        """The MCP server writes credentials in a separate process, so the
        reset is a row write and is read back through a different store."""
        writer = DeviceHealthStore(str(isolated / "admz.db"))
        writer.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), auth_fail_streak=4,
            auth_retry_after=time.time() + 1800,
        ))
        reader = DeviceHealthStore(str(isolated / "admz.db"))
        assert reader.get("cam-01").auth_retry_after is not None  # control

        clear_auth_hold("cam-01")   # resolves ADMZ_DB_PATH at call time

        row = reader.get("cam-01")
        assert row.auth_fail_streak == 0 and row.auth_retry_after is None
        assert row.status is DeviceHealthStatus.AUTH_FAILED, "the verdict is untouched"

    def test_it_never_creates_a_row(self, isolated):
        """#428 purges health rows inside the device-delete transaction; a
        reset must not conjure one back."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        clear_auth_hold("never-swept")
        assert store.get("never-swept") is None

    def test_it_never_raises(self, isolated, monkeypatch):
        """A credential write must not fail because the health store is
        unavailable."""
        monkeypatch.setattr(
            "admz.fleet.health.device_health_store.clear_auth_hold",
            MagicMock(side_effect=sqlite3.OperationalError("database is locked")),
        )
        clear_auth_hold("cam-01")  # must not raise

    def test_the_default_account_clears_it_and_recovery_does_not(self, isolated, tmp_path):
        """The sweep authenticates with `default`. Stashing a `recovery`
        password answers nothing about the credential it uses."""
        from admz.backends.sqlite_backend import SQLiteDeviceRegistry

        store = DeviceHealthStore(str(isolated / "admz.db"))
        registry = SQLiteDeviceRegistry(
            db_path=str(isolated / "admz.db"), key_path=str(tmp_path / "admz.key"))
        registry.add_device("cam-01", {"host": "192.0.2.1"})

        def _held():
            store.upsert(DeviceHealthRecord(
                device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
                last_check=time.time(), auth_fail_streak=3,
                auth_retry_after=time.time() + 1800,
            ))

        _held()
        registry.add_account("cam-01", "recovery", {"username": "root", "password": "old"})
        assert store.get("cam-01").auth_retry_after is not None, "recovery is not the sweep's account"

        registry.add_account("cam-01", "default", {"username": "root", "password": "new"})
        assert store.get("cam-01").auth_retry_after is None

        _held()
        registry.update_account("cam-01", "default", {"password": "newer"})
        assert store.get("cam-01").auth_retry_after is None

        _held()
        registry.remove_account("cam-01", "default")
        assert store.get("cam-01").auth_retry_after is None


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class TestTheHoldYieldsToTheOperator:
    @pytest.mark.asyncio
    async def test_a_credential_written_mid_probe_is_not_overwritten(self, isolated):
        """The sweep writes the whole row at the end. A credential write that
        clears the hold while the probe is in flight must win — otherwise the
        operator's reset is silently resurrected and they wait it out."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), consecutive_failures=2,
            last_error="credentials rejected", auth_fail_streak=3,
            auth_retry_after=time.time() + 1800,
        ))

        async def _clear_then_answer(*_a, **_k):
            clear_auth_hold("cam-01")          # the operator, mid-probe
            return 3

        catalog, executor, _calls = _executor({SYSTEMREADY_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)
        with patch("admz.fleet.health._tcp_probe", _clear_then_answer):
            await monitor.sweep_once()

        row = store.get("cam-01")
        assert row.auth_retry_after is None, "the operator's reset survived the upsert"
        assert row.auth_fail_streak == 0

    @pytest.mark.asyncio
    async def test_the_first_hold_is_one_ordinary_interval(self, isolated):
        """Stated so nobody reads the escalation as an immediate lockout: the
        first retry lands on the normal cadence, and only then does the wait
        start doubling."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        catalog, executor, _calls = _executor(
            {SYSTEMREADY_OP: REFUSED, CORROBORATION_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)

        before = time.time()
        await monitor.sweep_once()
        row = store.get("cam-01")
        assert row.auth_fail_streak == 1
        assert 55 <= row.auth_retry_after - before <= 65


class TestTheColumnsArrive:
    def test_a_database_that_predates_them_migrates(self, isolated):
        path = str(isolated / "old.db")
        conn = sqlite3.connect(path)
        conn.executescript(
            "CREATE TABLE device_health ("
            " device_id TEXT PRIMARY KEY, status TEXT NOT NULL, last_check REAL,"
            " last_seen_online REAL, latency_ms INTEGER,"
            " consecutive_failures INTEGER NOT NULL DEFAULT 0,"
            " last_error TEXT NOT NULL DEFAULT '', uptime_seconds INTEGER,"
            " bootid TEXT, sd_status TEXT, sd_total_kb INTEGER);"
        )
        conn.execute(
            "INSERT INTO device_health (device_id, status, consecutive_failures,"
            " last_error) VALUES ('cam-01', 'auth_failed', 3, 'rejected')")
        conn.commit()
        conn.close()

        store = DeviceHealthStore(path)
        row = store.get("cam-01")
        assert row is not None
        assert row.auth_fail_streak == 0 and row.auth_retry_after is None
        assert row.consecutive_failures == 3, "the old row is intact"

        cols = {r[1] for r in sqlite3.connect(path).execute(
            "PRAGMA table_info(device_health)")}
        assert {"auth_fail_streak", "auth_retry_after"} <= cols

    def test_a_migration_failure_leaves_the_path_unmarked_so_the_next_try_retries(
            self, isolated, monkeypatch):
        """Driven through `_connect`, because the property under test is that
        `_ready` is not populated — asserting it after calling `_create_schema`
        directly would pass however the code behaved."""
        import admz.fleet.health as health_mod

        path = str(isolated / "x.db")
        store = DeviceHealthStore(path)
        monkeypatch.setattr(
            health_mod, "_MIGRATION_COLUMNS",
            health_mod._MIGRATION_COLUMNS + (("not a column", "INTEGER"),))

        store._connect().close()
        assert path not in store._ready, "a failed migration is not 'done'"

        # and it self-heals once the cause is gone, after the retry window
        monkeypatch.setattr(health_mod, "_SCHEMA_RETRY_SECONDS", 0.0)
        monkeypatch.setattr(
            health_mod, "_MIGRATION_COLUMNS",
            tuple(c for c in health_mod._MIGRATION_COLUMNS if c[0] != "not a column"))
        store._connect().close()
        assert path in store._ready

    def test_a_repeated_failure_is_not_re_run_on_every_connection(
            self, isolated, monkeypatch):
        """A sustained lock would otherwise re-run the whole schema on each of
        the three store calls the sweep makes per device."""
        import admz.fleet.health as health_mod

        path = str(isolated / "y.db")
        store = DeviceHealthStore(path)
        attempts = []
        real = store._create_schema

        def _counting(p):
            attempts.append(p)
            return False

        monkeypatch.setattr(store, "_create_schema", _counting)
        store._connect().close()
        store._connect().close()
        store._connect().close()
        assert len(attempts) == 1, "remembered the failure for the retry window"
        assert real is not None

    def test_the_fields_reach_the_read_surfaces(self, isolated):
        row = DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            auth_fail_streak=2, auth_retry_after=1234.0,
        )
        d = row.to_dict()
        assert d["auth_fail_streak"] == 2 and d["auth_retry_after"] == 1234.0


@pytest.mark.asyncio
async def test_a_hold_needs_a_credential_to_hold(isolated):
    """A device whose credential was removed bypasses the hold entirely and is
    judged afresh: the verdict was about a credential that no longer exists,
    and holding on it would keep a `no_credentials` device reading
    `auth_failed` until the ceiling."""
    from admz.exceptions import AccountNotFoundError

    store = DeviceHealthStore(str(isolated / "admz.db"))
    store.upsert(DeviceHealthRecord(
        device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
        last_check=time.time(), last_error="credentials rejected",
        auth_fail_streak=4, auth_retry_after=time.time() + 1800,
    ))
    catalog, executor, calls = _executor({SYSTEMREADY_OP: _systemready(False)})
    monitor = _monitor(store, catalog, executor)
    monitor.registry.get_credentials.side_effect = AccountNotFoundError("gone")

    await monitor.sweep_once()

    row = store.get("cam-01")
    assert row.status is DeviceHealthStatus.NO_CREDENTIALS
    assert row.auth_fail_streak == 0 and row.auth_retry_after is None
    assert _credentialed(calls) == []


class TestTheHoldTellsTheTruth:
    @pytest.mark.asyncio
    async def test_a_flap_does_not_make_the_note_assert_a_tcp_failure(self, isolated):
        """`last_error` is overwritten by any intervening sweep. Suffixing the
        hold onto whatever happens to be there would leave a row that says
        `auth_failed` while its text reports a TCP connect failure that did not
        happen on this sweep. The specific wording of the original refusal does
        not survive a flap; a true generic one does."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        catalog, executor, _calls = _executor(
            {SYSTEMREADY_OP: REFUSED, CORROBORATION_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)

        await monitor.sweep_once()
        assert "refused them" in store.get("cam-01").last_error

        with patch("admz.fleet.health._tcp_probe", AsyncMock(return_value=None)):
            await monitor.sweep_once()
        assert "TCP connect" in store.get("cam-01").last_error

        await monitor.sweep_once()
        err = store.get("cam-01").last_error
        assert store.get("cam-01").status is DeviceHealthStatus.AUTH_FAILED
        assert "TCP connect" not in err, "the row must not assert a failure it did not see"
        assert "credential check held" in err and "refused the stored credential" in err

    @pytest.mark.asyncio
    async def test_the_note_stays_within_the_column_however_long_the_reason(self, isolated):
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), last_error="credentials rejected — " + ("x" * 400),
            auth_fail_streak=1, auth_retry_after=time.time() + 600,
        ))
        catalog, executor, _calls = _executor({SYSTEMREADY_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)

        await monitor.sweep_once()
        assert len(store.get("cam-01").last_error) <= 200

    @pytest.mark.asyncio
    async def test_an_unreachable_sweep_still_counts_as_a_failure(self, isolated):
        """Only a sweep that was actually held is exempt from the failure
        counter. A device that stops answering during a hold really did fail a
        probe, and FR-HLT-007 must still see it."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), consecutive_failures=2,
            last_error="credentials rejected", auth_fail_streak=1,
            auth_retry_after=time.time() + 600,
        ))
        catalog, executor, _calls = _executor({SYSTEMREADY_OP: REFUSED})
        monitor = _monitor(store, catalog, executor)

        with patch("admz.fleet.health._tcp_probe", AsyncMock(return_value=None)):
            await monitor.sweep_once()

        row = store.get("cam-01")
        assert row.status is DeviceHealthStatus.UNREACHABLE
        assert row.consecutive_failures == 3, "a real failed probe still counts"

    @pytest.mark.asyncio
    async def test_a_held_sweep_keeps_the_facts_the_free_read_gave_it(self, isolated):
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), last_error="credentials rejected",
            auth_fail_streak=1, auth_retry_after=time.time() + 600,
        ))
        catalog, executor, _calls = _executor({SYSTEMREADY_OP: _systemready(False)})
        monitor = _monitor(store, catalog, executor)

        await monitor.sweep_once()

        row = store.get("cam-01")
        assert row.status is DeviceHealthStatus.AUTH_FAILED
        assert row.uptime_seconds == 120 and row.bootid == "b7"

    @pytest.mark.asyncio
    async def test_an_expired_deadline_is_not_carried_onto_a_flap(self, isolated):
        """FR-HLT-012 exposes the deadline so an operator can see when the next
        check is due. A timestamp in the past says nothing and must not sit
        there."""
        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), last_error="credentials rejected",
            auth_fail_streak=3, auth_retry_after=time.time() - 5,
        ))
        # No catalog or executor, so nothing can reach a credential verdict:
        # the deadline has expired, so this is not a held sweep either.
        monitor = _monitor(store, catalog=None, executor=None)

        with patch("admz.fleet.health._tcp_probe", AsyncMock(return_value=None)):
            await monitor.sweep_once()

        row = store.get("cam-01")
        assert row.status is DeviceHealthStatus.UNREACHABLE
        assert row.auth_retry_after is None
        assert row.auth_fail_streak == 3, "the escalation itself is not forgotten"


class TestSweepsDoNotClobberEachOther:
    @pytest.mark.asyncio
    async def test_a_forced_sweep_is_not_undone_by_one_already_in_flight(self, isolated):
        """`POST /api/fleet/health/sweep` is the documented recovery path. Each
        `_check` writes a whole row, so without serialisation the operator's
        result is overwritten by whichever sweep finishes last."""
        import asyncio

        store = DeviceHealthStore(str(isolated / "admz.db"))
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), last_error="credentials rejected",
            auth_fail_streak=5, auth_retry_after=time.time() + 1800,
        ))
        gate = asyncio.Event()

        async def _slow_tcp(*_a, **_k):
            await gate.wait()
            return 3

        catalog, executor, _calls = _executor(
            {SYSTEMREADY_OP: _systemready(False),
             AUTH_CHECK_OP: MagicMock(
                 success=True, status_code=200, error=None,
                 parsed_data={"data": {"propertyList": {"ProdNbr": "P3245"}}})})
        monitor = _monitor(store, catalog, executor)

        with patch("admz.fleet.health._tcp_probe", _slow_tcp):
            held = asyncio.create_task(monitor.sweep_once())
            await asyncio.sleep(0)
            forced = asyncio.create_task(monitor.sweep_once(force=True))
            await asyncio.sleep(0)
            gate.set()
            await asyncio.gather(held, forced)

        row = store.get("cam-01")
        assert row.status is DeviceHealthStatus.ONLINE, \
            "the operator's check is the last word, not the sweep it interrupted"
        assert row.auth_retry_after is None


class TestTheResetFollowsItsOwnDatabase:
    def test_a_registry_with_an_explicit_path_clears_the_right_row(self, isolated, tmp_path):
        """A registry built with an explicit `db_path` is a supported
        construction. Clearing through the process-default store would target
        another file, match nothing, and report success."""
        from admz.backends.sqlite_backend import SQLiteDeviceRegistry

        elsewhere = str(tmp_path / "elsewhere.db")
        store = DeviceHealthStore(elsewhere)
        registry = SQLiteDeviceRegistry(
            db_path=elsewhere, key_path=str(tmp_path / "admz.key"))
        registry.add_device("cam-01", {"host": "192.0.2.1"})
        store.upsert(DeviceHealthRecord(
            device_id="cam-01", status=DeviceHealthStatus.AUTH_FAILED,
            last_check=time.time(), auth_fail_streak=3,
            auth_retry_after=time.time() + 1800,
        ))
        assert str(isolated / "admz.db") != elsewhere, "control: not the env path"

        registry.add_account("cam-01", "default", {"username": "root", "password": "new"})

        assert store.get("cam-01").auth_retry_after is None
