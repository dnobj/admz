"""GH #461 + #462 — the health probe's failure branch decides on evidence.

Both found by the adversarial review of #460, both pre-existing:

* #461 — the reachability shortcut matched ``"connect"`` inside
  ``"disconnected"``, so a device whose refusal surfaces as
  ``RemoteProtocolError("Server disconnected …")`` was filed UNREACHABLE before
  the TCP probe and the legacy read ever ran — never ``limited_api``, and the
  #458 capability record could never be taught. Production's T8516 escaped it
  only because its ``httpx.ReadError`` stringifies to nothing.
* #462 — the failure branch never inspected the legacy read for a 401, so a
  ``limited_api`` device with rotated credentials read as "lost its API"
  (``reachable_no_api``) on every sweep, never ``auth_failed``.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from admz.fleet.health import (
    AUTH_CHECK_OP,
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


PARAM_OK = dict(
    success=True, status_code=200, error=None,
    parsed_data="root.Brand.Brand=AXIS\nroot.Brand.ProdNbr=T8516",
)
PARAM_401 = dict(
    success=False, status_code=401,
    error="Authentication failed (401). Check credentials.",
)
BDI_401 = dict(
    success=False, status_code=401,
    error="Authentication failed (401). Check credentials.",
)
BDI_OK = dict(
    success=True, status_code=200, error=None,
    parsed_data={"data": {"propertyList": {"ProdNbr": "T8516", "Version": FW}}},
)
BDI_HTML = dict(
    success=False, status_code=200,
    error="Failed to parse JSON response: Expecting value: line 1 column 1 (char 0)",
)


def _systemready(error, status_code=None):
    return MagicMock(success=False, status_code=status_code, error=error)


async def _sweep(catalog, executor):
    return await probe_device(
        device_id=T8516,
        device_info={"host": "192.0.2.124", "firmware_version": FW},
        credentials={"username": "root", "password": "x"},
        catalog=catalog, executor=executor,
    )


# ---------------------------------------------------------------------------
# #461 — the shortcut is anchored on the executor's prefixes
# ---------------------------------------------------------------------------

class TestReachabilityShortcutIsPrefixAnchored:
    @pytest.mark.asyncio
    async def test_a_disconnected_message_reaches_the_legacy_read(self, isolated_db):
        """The #461 repro: 'disconnected' contains 'connect'. The verdict must
        come from the legacy read, and the capability record must be taught."""
        from admz.device_capabilities import capability_store

        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(
                "Transport error: Server disconnected without sending a response."
            ),
            CORROBORATION_OP: MagicMock(**PARAM_OK),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.LIMITED_API
        assert asked == [SYSTEMREADY_OP, CORROBORATION_OP]
        assert capability_store.get(T8516, "systemready") is not None, (
            "the #458 record is taught — the mechanism engages"
        )

    @pytest.mark.parametrize("error", [
        "Connection failed: [Errno 10061] No connection could be made",
        "Request timed out after 10s",
    ])
    @pytest.mark.asyncio
    async def test_the_executors_own_verdicts_keep_the_fast_path(
        self, isolated_db, error
    ):
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(error),
            CORROBORATION_OP: MagicMock(**PARAM_OK),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.UNREACHABLE
        assert asked == [SYSTEMREADY_OP], "no legacy read on a connect/timeout verdict"

    @pytest.mark.asyncio
    async def test_other_reachability_words_take_the_evidence_path(
        self, isolated_db, monkeypatch
    ):
        """'unreachable'/'refused' in some other exception's text is not the
        executor's verdict. Evidence decides — and reaches the same answer
        for a genuinely dead host."""
        ops = {
            SYSTEMREADY_OP: _systemready("[Errno 101] Network is unreachable"),
            CORROBORATION_OP: MagicMock(**PARAM_OK),
        }
        catalog, executor, asked = _per_op(ops)
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.LIMITED_API, "host up → the legacy read decides"

        monkeypatch.setattr(
            "admz.fleet.health._tcp_probe", AsyncMock(return_value=None)
        )
        catalog, executor, asked = _per_op(ops)
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.UNREACHABLE, "host down → same verdict, via the TCP probe"
        assert CORROBORATION_OP not in asked


# ---------------------------------------------------------------------------
# #462 — a refused legacy read is a credential question
# ---------------------------------------------------------------------------

class TestRefusedLegacyReadIsACredentialQuestion:
    PARSE_FAIL = "Failed to parse JSON response: Expecting value: line 1 column 1 (char 0)"

    @pytest.mark.asyncio
    async def test_both_ops_refuse_is_auth_failed(self, isolated_db):
        """The #462 repro: a limited_api switch whose password was rotated."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(self.PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**PARAM_401),
            AUTH_CHECK_OP: MagicMock(**BDI_401),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert rec.consecutive_failures == 1
        assert rec.last_seen_online is not None, "it IS reachable, just not authable"
        assert "credentials rejected" in rec.last_error
        assert asked == [SYSTEMREADY_OP, CORROBORATION_OP, AUTH_CHECK_OP]

    @pytest.mark.asyncio
    async def test_corroborator_authenticates_is_not_auth_failed(self, isolated_db):
        """GH #149 discipline: one op's 401 is not proof. If the second
        independent op authenticates, the credentials are fine."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(self.PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**PARAM_401),
            AUTH_CHECK_OP: MagicMock(**BDI_OK),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status != DeviceHealthStatus.AUTH_FAILED
        assert rec.status == DeviceHealthStatus.REACHABLE_NO_API
        assert "credentials look valid" in rec.last_error

    @pytest.mark.asyncio
    async def test_indeterminate_corroboration_does_not_condemn(self, isolated_db):
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(self.PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**PARAM_401),
            AUTH_CHECK_OP: MagicMock(**BDI_HTML),   # answered, proves nothing
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.REACHABLE_NO_API
        assert "NOT condemned" in rec.last_error

    @pytest.mark.asyncio
    async def test_the_skip_sweep_sees_the_401_too(self, isolated_db):
        """With the JSON probe skipped on the #458 record, the legacy read is
        the ONLY read — its 401 must still reach the credential verdict."""
        from admz.device_capabilities import ABSENT_UNCONFIRMED, capability_store

        capability_store.record(
            T8516, "systemready", ABSENT_UNCONFIRMED, firmware=FW, now=time.time(),
        )
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(self.PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**PARAM_401),
            AUTH_CHECK_OP: MagicMock(**BDI_401),
        })
        rec = await _sweep(catalog, executor)
        assert SYSTEMREADY_OP not in asked, "control: the JSON probe was skipped"
        assert rec.status == DeviceHealthStatus.AUTH_FAILED

    @pytest.mark.asyncio
    async def test_a_readable_device_is_still_limited_api(self, isolated_db):
        """Control: nothing changes for the switch with working credentials."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(self.PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**PARAM_OK),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.LIMITED_API
        assert AUTH_CHECK_OP not in asked, "no corroboration request on a healthy read"
