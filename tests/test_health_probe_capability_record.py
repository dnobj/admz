"""GH #458 — the health monitor's Tier-1 ``systemready`` probe consults and
teaches the ADR-0063 capability record.

Observed on production for 11 days after ADR-0063 shipped: zero ERRORs, and
~13 WARNINGs a day of one shape — ``Transport error executing
systemready.cgi:systemReady`` on the T8516, a ``limited_api`` switch. S1
taught the drift audit to stop asking for APIs a device lacks; the health
probe was still asking every sweep, paying one dead request and one warning
to learn what the record already said.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from admz.fleet.health import (
    CORROBORATION_OP,
    SYSTEMREADY_OP,
    DeviceHealthStatus,
    probe_device,
)

T8516 = "t8516"
FW = "6.54.3942"


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setattr(
        "admz.fleet.health._tcp_probe", AsyncMock(return_value=3)
    )


def _per_op(results_by_op):
    """Catalog + executor answering per operation id, recording the ids asked."""
    catalog = MagicMock()

    def _get_operation(family, op_id):
        op = MagicMock()
        op.to_executor_dict.return_value = {"id": op_id}
        return op

    catalog.get_operation.side_effect = _get_operation
    asked = []

    async def _execute(op_dict, device_info, credentials, params):
        asked.append(op_dict["id"])
        return results_by_op[op_dict["id"]]

    executor = MagicMock()
    executor.execute = AsyncMock(side_effect=_execute)
    return catalog, executor, asked


def _switch_ops(*, legacy_ok=True):
    """The T8516 shape: systemready drops the connection; param.cgi answers."""
    ops = {
        SYSTEMREADY_OP: MagicMock(
            success=False, status_code=None,
            error="Transport error: ",
        ),
    }
    if legacy_ok:
        ops[CORROBORATION_OP] = MagicMock(
            success=True, status_code=200, error=None,
            parsed_data="root.Brand.Brand=AXIS\nroot.Brand.ProdNbr=T8516",
        )
    else:
        ops[CORROBORATION_OP] = MagicMock(
            success=False, status_code=None,
            error="Transport error: ",
        )
    return ops


async def _sweep(catalog, executor):
    return await probe_device(
        device_id=T8516,
        device_info={"host": "192.0.2.124", "firmware_version": FW},
        credentials={"username": "root", "password": "x"},
        catalog=catalog, executor=executor,
    )


class TestTheSwitchIsAskedOnce:
    @pytest.mark.asyncio
    async def test_second_sweep_sends_only_the_legacy_read(self, isolated_db):
        from admz.device_capabilities import capability_store

        catalog, executor, asked = _per_op(_switch_ops())

        rec1 = await _sweep(catalog, executor)
        assert rec1.status == DeviceHealthStatus.LIMITED_API
        assert asked == [SYSTEMREADY_OP, CORROBORATION_OP], "sweep 1 probes and learns"
        row = capability_store.get(T8516, "systemready")
        assert row is not None and row.classification == "absent_unconfirmed"
        assert row.firmware == FW

        asked.clear()
        rec2 = await _sweep(catalog, executor)
        assert rec2.status == DeviceHealthStatus.LIMITED_API
        assert asked == [CORROBORATION_OP], (
            "sweep 2 must not send the request the record says will fail"
        )
        assert rec2.consecutive_failures == 0
        assert rec2.last_seen_online is not None
        assert "capability record" in rec2.last_error
        # #460 review, MAJOR-2: a skip sweep teaches NOTHING. Re-teaching on
        # a skip would bump the streak and push the lease forward every
        # sweep — a self-reinforcing lease that never lapses, so a switch
        # that gains JSON-RPC is never re-discovered. Byte-identical row.
        assert capability_store.get(T8516, "systemready") == row
        assert rec2.latency_ms == 3, "a skip sweep's latency is the TCP probe's"

    @pytest.mark.asyncio
    async def test_unreadable_sweep_teaches_nothing(self, isolated_db):
        """The readability control: when the legacy read ALSO fails, the
        device is not readable — systemready's failure is not evidence, no
        row is written, and the next sweep probes everything again."""
        from admz.device_capabilities import capability_store

        catalog, executor, asked = _per_op(_switch_ops(legacy_ok=False))
        rec = await _sweep(catalog, executor)
        assert rec.status != DeviceHealthStatus.LIMITED_API
        assert capability_store.get(T8516, "systemready") is None

        asked.clear()
        await _sweep(catalog, executor)
        assert SYSTEMREADY_OP in asked, "an unrecorded device is probed again"

    @pytest.mark.asyncio
    async def test_expired_lease_probes_again(self, isolated_db, monkeypatch):
        import admz.device_capabilities as dc

        catalog, executor, asked = _per_op(_switch_ops())
        await _sweep(catalog, executor)
        asked.clear()
        real_time = time.time
        monkeypatch.setattr(dc.time, "time", lambda: real_time() + 25 * 3600)
        await _sweep(catalog, executor)
        assert SYSTEMREADY_OP in asked, "a lapsed lease re-probes"
        # ...and the streak backs off: the second unconfirmed lease is 48h.
        row = dc.capability_store.get(T8516, "systemready")
        assert row.fail_streak == 2

    @pytest.mark.asyncio
    async def test_firmware_change_probes_again(self, isolated_db):
        catalog, executor, asked = _per_op(_switch_ops())
        await _sweep(catalog, executor)
        asked.clear()
        rec = await probe_device(
            device_id=T8516,
            device_info={"host": "192.0.2.124", "firmware_version": "6.55.0"},
            credentials={"username": "root", "password": "x"},
            catalog=catalog, executor=executor,
        )
        assert rec.status == DeviceHealthStatus.LIMITED_API
        assert SYSTEMREADY_OP in asked, "rows are keyed by firmware"


class TestHealthyDevicesAreUntouched:
    @pytest.mark.asyncio
    async def test_a_surveyed_camera_is_probed_and_its_row_left_alone(
        self, isolated_db
    ):
        """#460 review, MAJOR-1/3: the S2 survey records `systemready`
        PRESENT for every camera. A PRESENT row must never cause a skip
        (a mutation that skips on any non-stale row would file the whole
        fleet limited_api), and a trustworthy PRESENT row must not be
        rewritten on every ONLINE sweep — the survey's provenance
        (source=discovery, its reason) is kept."""
        from admz.device_capabilities import PRESENT, capability_store

        capability_store.record(
            T8516, "systemready", PRESENT, firmware=FW, source="discovery",
            reason="getApiList reported 'systemready'", now=time.time(),
        )
        before = capability_store.get(T8516, "systemready")
        ok = MagicMock(
            success=True, status_code=200, error=None,
            parsed_data={"systemready": "yes", "needsetup": "no",
                         "uptime": 100, "bootid": "boot-1"},
        )
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: ok,
            CORROBORATION_OP: MagicMock(
                success=True, status_code=200, error=None,
                parsed_data="root.Brand.Brand=AXIS",
            ),
        })
        for _ in range(3):
            asked.clear()
            rec = await _sweep(catalog, executor)
            assert rec.status == DeviceHealthStatus.ONLINE
            assert asked[0] == SYSTEMREADY_OP, "a PRESENT row never skips the probe"
        after = capability_store.get(T8516, "systemready")
        assert after == before, "a trustworthy PRESENT row is not rewritten"
        assert after.source == "discovery"

    @pytest.mark.asyncio
    async def test_a_camera_that_answers_is_never_skipped_and_writes_no_row(
        self, isolated_db
    ):
        """A healthy fleet must not pay a write per device per sweep."""
        from admz.device_capabilities import capability_store

        ok = MagicMock(
            success=True, status_code=200, error=None,
            parsed_data={"systemready": "yes", "needsetup": "no",
                         "uptime": 100, "bootid": "boot-1"},
        )
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: ok,
            CORROBORATION_OP: MagicMock(
                success=True, status_code=200, error=None,
                parsed_data="root.Brand.Brand=AXIS",
            ),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.ONLINE
        assert asked[0] == SYSTEMREADY_OP
        assert capability_store.list(T8516) == []

    @pytest.mark.asyncio
    async def test_a_device_that_starts_answering_overwrites_its_old_row(
        self, isolated_db, monkeypatch
    ):
        """After a lease lapses, a device that now answers systemready gets
        a PRESENT row — the record says what is true, and it is never
        skipped again."""
        import admz.device_capabilities as dc

        catalog, executor, asked = _per_op(_switch_ops())
        await _sweep(catalog, executor)
        assert dc.capability_store.get(T8516, "systemready").supported is False

        # Time passes; the switch gains a JSON-RPC surface.
        real_time = time.time
        monkeypatch.setattr(dc.time, "time", lambda: real_time() + 25 * 3600)
        ok = MagicMock(
            success=True, status_code=200, error=None,
            parsed_data={"systemready": "yes", "needsetup": "no",
                         "uptime": 5, "bootid": "boot-2"},
        )
        catalog2, executor2, asked2 = _per_op({
            SYSTEMREADY_OP: ok, CORROBORATION_OP: _switch_ops()[CORROBORATION_OP],
        })
        rec = await _sweep(catalog2, executor2)
        assert rec.status == DeviceHealthStatus.ONLINE
        row = dc.capability_store.get(T8516, "systemready")
        assert row.supported is True
        assert row.source == "health", "rows the health monitor writes say so"
        # ...and it stays probed from now on (#460 review, MAJOR-3).
        asked2.clear()
        await _sweep(catalog2, executor2)
        assert SYSTEMREADY_OP in asked2


class TestSkipSweepVerdictsNameTheirEvidence:
    @pytest.mark.asyncio
    async def test_host_down_on_a_skip_sweep_is_the_tcp_probes_verdict(
        self, isolated_db, monkeypatch
    ):
        """#460 review, MINOR-1: on a skip sweep the JSON probe was not
        sent, so when the host is down the verdict comes from the TCP probe
        — last_error must say that, not blame the capability record."""
        catalog, executor, asked = _per_op(_switch_ops())
        await _sweep(catalog, executor)          # learn: row written

        monkeypatch.setattr(
            "admz.fleet.health._tcp_probe", AsyncMock(return_value=None)
        )
        asked.clear()
        rec = await _sweep(catalog, executor)    # skip, then host is down
        assert rec.status == DeviceHealthStatus.UNREACHABLE
        assert asked == [], "nothing was sent: the JSON probe was skipped and TCP failed first"
        assert rec.last_error.startswith("host did not accept a TCP connection")
        assert "capability record" in rec.last_error
