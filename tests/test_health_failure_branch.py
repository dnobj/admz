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

The #462 half has a second layer, found by the review of this PR's first
round: the corroborating op is JSON-RPC, and a legacy-only device — the very
device #462 is about — can never answer it. A corroborator that *cannot*
answer on a sweep whose JSON probe already failed is not "unproven"; it is
the device saying it has no second surface to ask, and the legacy read's
refusal is the only evidence it can give.
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
TCP_MS = 3


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setattr(
        "admz.fleet.health._tcp_probe", AsyncMock(return_value=TCP_MS)
    )


def _per_op(results_by_op, *, missing=()):
    """A catalog that resolves every op id (except ``missing``) and an
    executor that answers per op id — raising when the value is an
    exception — recording the order in which ops were asked."""
    catalog = MagicMock()

    def _get_operation(family, op_id):
        if op_id in missing:
            return None
        op = MagicMock()
        op.to_executor_dict.return_value = {"id": op_id}
        return op

    catalog.get_operation.side_effect = _get_operation
    asked = []

    async def _execute(op_dict, device_info, credentials, params):
        asked.append(op_dict["id"])
        answer = results_by_op[op_dict["id"]]
        if isinstance(answer, BaseException):
            raise answer
        return answer

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
PARAM_403 = dict(success=False, status_code=403, error="HTTP 403: Forbidden")
BDI_401 = dict(
    success=False, status_code=401,
    error="Authentication failed (401). Check credentials.",
)
BDI_403 = dict(success=False, status_code=403, error="HTTP 403: Forbidden")
BDI_OK = dict(
    success=True, status_code=200, error=None,
    parsed_data={"data": {"propertyList": {
        "ProdNbr": "T8516", "SerialNumber": "ACCC8ED78C7B", "Version": FW,
    }}},
)
# The three ways a JSON-RPC op fails on a device that has no JSON surface:
# the production T8516's dropped connection (its ReadError stringifies to
# nothing), a 404, and HTML where JSON was expected.
BDI_T8516 = dict(success=False, status_code=None, error="Transport error: ")
BDI_404 = dict(success=False, status_code=404, error="HTTP 404: Not Found")
BDI_HTML = dict(
    success=False, status_code=200,
    error="Failed to parse JSON response: Expecting value: line 1 column 1 (char 0)",
)
BDI_503 = dict(success=False, status_code=503, error="HTTP 503: Service Unavailable")
PARSE_FAIL = "Failed to parse JSON response: Expecting value: line 1 column 1 (char 0)"


def _systemready(error, status_code=None):
    return MagicMock(success=False, status_code=status_code, error=error)


async def _sweep(catalog, executor):
    return await probe_device(
        device_id=T8516,
        device_info={"host": "192.0.2.124", "firmware_version": FW},
        credentials={"username": "root", "password": "x"},
        catalog=catalog, executor=executor,
    )


def _seed_skip_row():
    """Put the #458 record in place so the JSON probe is skipped."""
    from admz.device_capabilities import ABSENT_UNCONFIRMED, capability_store

    capability_store.record(
        T8516, "systemready", ABSENT_UNCONFIRMED, firmware=FW, now=time.time(),
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
        "Connection failed: All connection attempts failed",
        "Request timed out after 10s",
    ])
    @pytest.mark.asyncio
    async def test_the_executors_own_verdicts_keep_the_fast_path(
        self, isolated_db, error
    ):
        """The executor's two host verdicts (``executor/vapix.py``'s
        ConnectError and TimeoutException clauses), in their real text."""
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
        """A reachability word inside a *transport* error (the executor's
        wrapper for everything that is not a connect or timeout verdict —
        here an ENETUNREACH raised mid-request) is not the executor's
        verdict. Evidence decides — and reaches the same answer for a
        genuinely dead host."""
        ops = {
            SYSTEMREADY_OP: _systemready(
                "Transport error: [Errno 101] Network is unreachable"
            ),
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

    @pytest.mark.asyncio
    async def test_a_prefix_inside_the_message_is_not_a_verdict(self, isolated_db):
        """The rule is *anchoring*, not vocabulary. This string is synthetic
        on purpose — the executor never embeds a verdict mid-message — so
        that a substring-anywhere rule cannot pass for a prefix rule."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(
                "Transport error: peer said Connection failed: reset"
            ),
            CORROBORATION_OP: MagicMock(**PARAM_OK),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.LIMITED_API
        assert CORROBORATION_OP in asked

    @pytest.mark.asyncio
    async def test_a_non_string_error_never_takes_the_fast_path(self, isolated_db):
        """A result whose ``error`` is not a string (a foreign result shape,
        a mock without one) must not answer ``startswith`` truthily and
        file the device UNREACHABLE with no probe sent."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: MagicMock(success=False, status_code=None),
            CORROBORATION_OP: MagicMock(**PARAM_OK),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status != DeviceHealthStatus.UNREACHABLE
        assert CORROBORATION_OP in asked, "evidence path, not the shortcut"


# ---------------------------------------------------------------------------
# #462 — a refused legacy read is a credential question
# ---------------------------------------------------------------------------

class TestRefusedLegacyReadIsACredentialQuestion:
    @pytest.mark.asyncio
    async def test_both_ops_refuse_is_auth_failed(self, isolated_db):
        """A device with a JSON surface that happens to be unusable this
        sweep, whose password was rotated: both auth ops refuse."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**PARAM_401),
            AUTH_CHECK_OP: MagicMock(**BDI_401),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert rec.consecutive_failures == 1
        assert rec.last_seen_online is not None, "it IS reachable, just not authable"
        assert "both refused" in rec.last_error
        assert asked == [SYSTEMREADY_OP, CORROBORATION_OP, AUTH_CHECK_OP]

    @pytest.mark.parametrize("legacy, corroborator", [
        (PARAM_403, BDI_403),
        (PARAM_401, BDI_403),
        (PARAM_403, BDI_401),
    ])
    @pytest.mark.asyncio
    async def test_a_403_is_a_refusal_on_either_op(
        self, isolated_db, legacy, corroborator
    ):
        """Both ops are viewer-level in the atlas, so a 403 is the account
        being refused, not a privilege nuance — the same set
        ``_confirm_credentials`` uses."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**legacy),
            AUTH_CHECK_OP: MagicMock(**corroborator),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert "both refused" in rec.last_error
        assert asked == [SYSTEMREADY_OP, CORROBORATION_OP, AUTH_CHECK_OP]

    @pytest.mark.asyncio
    async def test_a_401_reported_in_text_counts_as_refused(self, isolated_db):
        """Parity with the systemready-401 trigger: an anchored
        "Authentication failed (401)" text is a refusal even when the result
        carries no status code. (The VAPIX executor sets the code today; the
        clause is defensive, and this pins that it is wired, not decorative.)"""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(
                success=False, status_code=None,
                error="Authentication failed (401). Check credentials.",
            ),
            AUTH_CHECK_OP: MagicMock(**BDI_401),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert AUTH_CHECK_OP in asked

    @pytest.mark.asyncio
    async def test_corroborator_authenticates_is_not_auth_failed(self, isolated_db):
        """GH #149 discipline: one op's 401 is not proof. If the second
        independent op authenticates, the credentials are fine — and the
        facts it returned ride along for the sweep to flush."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**PARAM_401),
            AUTH_CHECK_OP: MagicMock(**BDI_OK),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.REACHABLE_NO_API
        assert "credentials look valid" in rec.last_error
        assert rec.consecutive_failures == 0, "settled state, not a failing probe"
        assert rec.last_seen_online is not None, "the host answered"
        assert rec.observed_facts, "the corroborator's identity facts ride along"
        assert "T8516" in " ".join(rec.observed_facts.values())

    # --- the second layer: a legacy-only device has no corroborator to ask --

    @pytest.mark.parametrize("corroborator", [BDI_T8516, BDI_404, BDI_HTML])
    @pytest.mark.asyncio
    async def test_a_legacy_only_device_with_a_rotated_password_is_auth_failed(
        self, isolated_db, corroborator
    ):
        """The actual #462 device: a switch that speaks legacy CGI only. Its
        JSON probe failed (that is why the sweep is here), the legacy read
        refused the password, and the JSON corroborator cannot answer in any
        of the three ways a missing surface fails. The legacy refusal is the
        only evidence this device can ever give — condemn on it."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready("Transport error: "),
            CORROBORATION_OP: MagicMock(**PARAM_401),
            AUTH_CHECK_OP: MagicMock(**corroborator),
        })
        rec = await _sweep(catalog, executor)
        assert asked == [SYSTEMREADY_OP, CORROBORATION_OP, AUTH_CHECK_OP]
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert rec.consecutive_failures == 1
        assert rec.last_seen_online is not None
        assert "does not serve the JSON surface" in rec.last_error
        assert AUTH_CHECK_OP in rec.last_error, "names what it asked"

    @pytest.mark.asyncio
    async def test_the_skip_sweep_condemns_the_legacy_only_device_too(self, isolated_db):
        """With the JSON probe skipped on the #458 record, the legacy read is
        the ONLY read — the production T8516 with a rotated password. Its
        401 must reach the verdict, with the TCP probe's latency."""
        _seed_skip_row()
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready("Transport error: "),
            CORROBORATION_OP: MagicMock(**PARAM_401),
            AUTH_CHECK_OP: MagicMock(**BDI_T8516),
        })
        rec = await _sweep(catalog, executor)
        assert SYSTEMREADY_OP not in asked, "control: the JSON probe was skipped"
        assert asked == [CORROBORATION_OP, AUTH_CHECK_OP]
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert rec.latency_ms == TCP_MS, "no JSON probe was timed; the TCP probe's"

    @pytest.mark.asyncio
    async def test_the_skip_sweep_sees_a_double_refusal_too(self, isolated_db):
        _seed_skip_row()
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**PARAM_401),
            AUTH_CHECK_OP: MagicMock(**BDI_401),
        })
        rec = await _sweep(catalog, executor)
        assert SYSTEMREADY_OP not in asked
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert "both refused" in rec.last_error

    @pytest.mark.parametrize("corroborator", [
        MagicMock(**BDI_503),
        RuntimeError("executor blew up"),
    ])
    @pytest.mark.asyncio
    async def test_a_transient_corroborator_answer_does_not_condemn(
        self, isolated_db, corroborator
    ):
        """A 5xx or an executor error on the corroborator proves nothing
        either way: the device does serve the op, it just failed this sweep.
        Don't move the status; the next sweep asks again."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**PARAM_401),
            AUTH_CHECK_OP: corroborator,
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.REACHABLE_NO_API
        assert "NOT condemned" in rec.last_error
        assert rec.consecutive_failures == 0
        assert rec.last_seen_online is not None
        assert AUTH_CHECK_OP in asked

    @pytest.mark.asyncio
    async def test_an_uncatalogued_corroborator_is_single_op_judgement(self, isolated_db):
        """No corroborating op in the catalog: condemn (a stale password must
        not read as healthy because the second op is unavailable — the
        stance ``_corroborate_rejection`` already takes), and say so, rather
        than claiming an op that was never sent refused anything."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**PARAM_401),
        }, missing=(AUTH_CHECK_OP,))
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert AUTH_CHECK_OP not in asked
        assert "not in the catalog" in rec.last_error
        assert "both refused" not in rec.last_error

    @pytest.mark.asyncio
    async def test_a_readable_device_is_still_limited_api(self, isolated_db):
        """Control: nothing changes for the switch with working credentials."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _systemready(PARSE_FAIL, status_code=200),
            CORROBORATION_OP: MagicMock(**PARAM_OK),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.LIMITED_API
        assert AUTH_CHECK_OP not in asked, "no corroboration request on a healthy read"
