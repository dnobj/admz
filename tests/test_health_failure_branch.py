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

The #462 half has a second layer, found by this PR's own reviews: the
corroborating op is JSON-RPC, and a legacy-only device — the very device #462
is about — can never answer it. A JSON surface that is *demonstrably not
there to ask* (this sweep's own probe, or the corroborator, failing in a
missing-surface shape on ADR-0063's line) is not "unproven"; the legacy read's
refusal is the only evidence the device can give. A live surface's bad moment
— a 5xx, a 429, a JSON-RPC application error at 200 — never condemns.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from admz.fleet.health import (
    _JSON_ABSENT,
    _JSON_TRANSIENT,
    AUTH_CHECK_OP,
    CORROBORATION_OP,
    SYSTEMREADY_OP,
    DeviceHealthStatus,
    _json_answer_kind,
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


def _r(**kw):
    """A StepResult-shaped answer."""
    return MagicMock(**{"success": False, "status_code": None, "error": None, **kw})


PARAM_OK = dict(
    success=True, status_code=200, error=None,
    parsed_data="root.Brand.Brand=AXIS\nroot.Brand.ProdNbr=T8516",
)
PARAM_401 = dict(status_code=401, error="Authentication failed (401). Check credentials.")
PARAM_403 = dict(status_code=403, error="HTTP 403: Forbidden")
BDI_401 = dict(status_code=401, error="Authentication failed (401). Check credentials.")
BDI_403 = dict(status_code=403, error="HTTP 403: Forbidden")
BDI_OK = dict(
    success=True, status_code=200, error=None,
    parsed_data={"data": {"propertyList": {
        "ProdNbr": "T8516", "SerialNumber": "ACCC8ED78C7B", "Version": FW,
    }}},
)
PARSE_FAIL = "Failed to parse JSON response: Expecting value: line 1 column 1 (char 0)"
# The three ways a JSON-RPC op fails on a device that has no JSON surface:
# the production T8516's dropped connection (its ReadError stringifies to
# nothing), a 404, and HTML where JSON was expected.
MISSING_SURFACE = [
    dict(status_code=None, error="Transport error: "),
    dict(status_code=404, error="HTTP 404: Not Found"),
    dict(status_code=200, error=PARSE_FAIL),
]
# A JSON surface that exists and had a bad moment this sweep.
SR_503 = dict(status_code=503, error="HTTP 503: Service Unavailable")


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
            SYSTEMREADY_OP: _r(
                error="Transport error: Server disconnected without sending a response."
            ),
            CORROBORATION_OP: _r(**PARAM_OK),
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
            SYSTEMREADY_OP: _r(error=error),
            CORROBORATION_OP: _r(**PARAM_OK),
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
            SYSTEMREADY_OP: _r(error="Transport error: [Errno 101] Network is unreachable"),
            CORROBORATION_OP: _r(**PARAM_OK),
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
            SYSTEMREADY_OP: _r(error="Transport error: peer said Connection failed: reset"),
            CORROBORATION_OP: _r(**PARAM_OK),
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
            CORROBORATION_OP: _r(**PARAM_OK),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status != DeviceHealthStatus.UNREACHABLE
        assert CORROBORATION_OP in asked, "evidence path, not the shortcut"


# ---------------------------------------------------------------------------
# The JSON-answer classifier: ADR-0063's absent line + the legacy-only shapes
# ---------------------------------------------------------------------------

class TestJsonAnswerKind:
    @pytest.mark.parametrize("status_code, error, kind", [
        # the two legacy-only shapes
        (None, "Transport error: ", _JSON_ABSENT),
        (None, "Transport error: Server disconnected without sending a response.", _JSON_ABSENT),
        (200, PARSE_FAIL, _JSON_ABSENT),
        # ADR-0063's hard-absent codes and method-absent marks, reused
        (400, "HTTP 400: Bad Request", _JSON_ABSENT),
        (404, "HTTP 404: Not Found", _JSON_ABSENT),
        (405, "HTTP 405: Method Not Allowed", _JSON_ABSENT),
        (410, "HTTP 410: Gone", _JSON_ABSENT),
        (501, "HTTP 501: Not Implemented", _JSON_ABSENT),
        (200, "-32601: Method not found", _JSON_ABSENT),
        (200, "2000: API version not supported", _JSON_ABSENT),
        # a live surface's bad moment
        (200, "1100: Internal error", _JSON_TRANSIENT),
        (200, "2001: Access forbidden", _JSON_TRANSIENT),
        (500, "HTTP 500: Internal Server Error", _JSON_TRANSIENT),
        (502, "HTTP 502: Bad Gateway", _JSON_TRANSIENT),
        (503, "HTTP 503: Service Unavailable", _JSON_TRANSIENT),
        (504, "HTTP 504: Gateway Timeout", _JSON_TRANSIENT),
        (408, "HTTP 408: Request Timeout", _JSON_TRANSIENT),
        (429, "HTTP 429: Too Many Requests", _JSON_TRANSIENT),
        (302, "HTTP 302: Found", _JSON_TRANSIENT),
        # the host, not the surface
        (None, "Connection failed: All connection attempts failed", _JSON_TRANSIENT),
        (None, "Request timed out after 10s", _JSON_TRANSIENT),
        (None, "", _JSON_TRANSIENT),
    ])
    def test_kind(self, status_code, error, kind):
        assert _json_answer_kind(_r(status_code=status_code, error=error)) == kind


# ---------------------------------------------------------------------------
# #462 — a refused legacy read is a credential question
# ---------------------------------------------------------------------------

class TestRefusedLegacyReadIsACredentialQuestion:
    @pytest.mark.asyncio
    async def test_both_ops_refuse_is_auth_failed(self, isolated_db):
        """A device with a JSON surface that had a bad moment this sweep,
        whose password was rotated: both auth ops refuse."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _r(**SR_503),
            CORROBORATION_OP: _r(**PARAM_401),
            AUTH_CHECK_OP: _r(**BDI_401),
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
            SYSTEMREADY_OP: _r(**SR_503),
            CORROBORATION_OP: _r(**legacy),
            AUTH_CHECK_OP: _r(**corroborator),
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
            SYSTEMREADY_OP: _r(**SR_503),
            CORROBORATION_OP: _r(error="Authentication failed (401). Check credentials."),
            AUTH_CHECK_OP: _r(**BDI_401),
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
            SYSTEMREADY_OP: _r(**SR_503),
            CORROBORATION_OP: _r(**PARAM_401),
            AUTH_CHECK_OP: _r(**BDI_OK),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.REACHABLE_NO_API
        assert "credentials look valid" in rec.last_error
        assert rec.consecutive_failures == 0, "settled state, not a failing probe"
        assert rec.last_seen_online is not None, "the host answered"
        assert rec.observed_facts, "the corroborator's identity facts ride along"
        assert "T8516" in " ".join(rec.observed_facts.values())

    @pytest.mark.asyncio
    async def test_a_success_without_a_status_is_not_proof_of_credentials(self, isolated_db):
        """``success`` alone is not an authenticated 2xx."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _r(**SR_503),
            CORROBORATION_OP: _r(**PARAM_401),
            AUTH_CHECK_OP: _r(success=True, status_code=None, error=None),
        })
        rec = await _sweep(catalog, executor)
        assert "credentials look valid" not in rec.last_error
        assert rec.status != DeviceHealthStatus.AUTH_FAILED

    # --- the second layer: a JSON surface that is not there to ask ---------

    @pytest.mark.parametrize("probe", MISSING_SURFACE)
    @pytest.mark.asyncio
    async def test_this_sweeps_own_json_failure_is_the_corroboration(
        self, isolated_db, probe
    ):
        """The actual #462 device on a probe sweep: the JSON probe failed in
        a missing-surface shape and the legacy read refused the password.
        The JSON surface was asked THIS sweep and was not there — no second
        JSON op is sent (one dead request and one WARNING fewer), and the
        verdict names this sweep's evidence."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _r(**probe),
            CORROBORATION_OP: _r(**PARAM_401),
            AUTH_CHECK_OP: _r(**BDI_401),   # present, must not be asked
        })
        rec = await _sweep(catalog, executor)
        assert asked == [SYSTEMREADY_OP, CORROBORATION_OP]
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert rec.consecutive_failures == 1
        assert rec.last_seen_online is not None
        assert "no JSON surface to corroborate" in rec.last_error
        assert SYSTEMREADY_OP in rec.last_error, "names this sweep's evidence"

    @pytest.mark.parametrize("corroborator", MISSING_SURFACE)
    @pytest.mark.asyncio
    async def test_the_skip_sweep_asks_and_condemns_the_legacy_only_device(
        self, isolated_db, corroborator
    ):
        """With the JSON probe skipped on the #458 record there is no fresh
        evidence, so the corroborator IS asked — and on a legacy-only device
        it cannot answer, in any of the three shapes. The legacy read is the
        only read; its 401 reaches the verdict, with the TCP probe's
        latency."""
        _seed_skip_row()
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _r(error="Transport error: "),
            CORROBORATION_OP: _r(**PARAM_401),
            AUTH_CHECK_OP: _r(**corroborator),
        })
        rec = await _sweep(catalog, executor)
        assert SYSTEMREADY_OP not in asked, "control: the JSON probe was skipped"
        assert asked == [CORROBORATION_OP, AUTH_CHECK_OP]
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert rec.latency_ms == TCP_MS, "no JSON probe was timed; the TCP probe's"
        assert "no JSON surface to corroborate" in rec.last_error
        assert AUTH_CHECK_OP in rec.last_error, "names what it asked"

    @pytest.mark.parametrize("corroborator", MISSING_SURFACE)
    @pytest.mark.asyncio
    async def test_a_live_json_surface_this_sweep_still_asks_and_classifies(
        self, isolated_db, corroborator
    ):
        """The JSON probe had a bad moment (a 503 — the surface exists), so
        the corroborator is asked; when IT fails in a missing-surface shape
        the verdict is the same single-op judgement, naming the corroborator."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _r(**SR_503),
            CORROBORATION_OP: _r(**PARAM_401),
            AUTH_CHECK_OP: _r(**corroborator),
        })
        rec = await _sweep(catalog, executor)
        assert asked == [SYSTEMREADY_OP, CORROBORATION_OP, AUTH_CHECK_OP]
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert AUTH_CHECK_OP in rec.last_error

    @pytest.mark.asyncio
    async def test_the_skip_sweep_sees_a_double_refusal_too(self, isolated_db):
        _seed_skip_row()
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _r(**SR_503),
            CORROBORATION_OP: _r(**PARAM_401),
            AUTH_CHECK_OP: _r(**BDI_401),
        })
        rec = await _sweep(catalog, executor)
        assert SYSTEMREADY_OP not in asked
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert "both refused" in rec.last_error

    @pytest.mark.parametrize("corroborator", [
        _r(status_code=503, error="HTTP 503: Service Unavailable"),
        _r(status_code=500, error="HTTP 500: Internal Server Error"),
        _r(status_code=502, error="HTTP 502: Bad Gateway"),
        _r(status_code=504, error="HTTP 504: Gateway Timeout"),
        _r(status_code=408, error="HTTP 408: Request Timeout"),
        _r(status_code=429, error="HTTP 429: Too Many Requests"),
        _r(status_code=200, error="1100: Internal error"),
        _r(status_code=200, error="2001: Access forbidden"),
        RuntimeError("executor blew up"),
    ])
    @pytest.mark.asyncio
    async def test_a_live_surfaces_bad_moment_does_not_condemn(
        self, isolated_db, corroborator
    ):
        """A 5xx, a 4xx ADR-0063 does not call absent, a JSON-RPC
        *application* error at 200 (the endpoint exists and answered in
        JSON, over an HTTP layer that accepted the credentials), or an
        executor error: the device serves the op, this answer proves nothing.
        Don't move the status; the next sweep asks again."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _r(**SR_503),
            CORROBORATION_OP: _r(**PARAM_401),
            AUTH_CHECK_OP: corroborator,
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.REACHABLE_NO_API
        assert "NOT condemned" in rec.last_error
        assert rec.consecutive_failures == 0
        assert rec.last_seen_online is not None
        assert AUTH_CHECK_OP in asked

    @pytest.mark.parametrize("corroborator", [
        _r(status_code=501, error="HTTP 501: Not Implemented"),
        _r(status_code=200, error="-32601: Method not found"),
    ])
    @pytest.mark.asyncio
    async def test_adr_0063s_absent_line_is_reused(self, isolated_db, corroborator):
        """501 and the method-absent JSON-RPC marks are ADR-0063's own
        "not here" verdicts, not bad moments."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _r(**SR_503),
            CORROBORATION_OP: _r(**PARAM_401),
            AUTH_CHECK_OP: corroborator,
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert "no JSON surface to corroborate" in rec.last_error

    @pytest.mark.asyncio
    async def test_an_uncatalogued_corroborator_is_single_op_judgement(self, isolated_db):
        """No corroborating op in the catalog: condemn (a stale password must
        not read as healthy because the second op is unavailable — the
        stance ``_corroborate_rejection`` already takes), and say so, rather
        than claiming an op that was never sent refused anything."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _r(**SR_503),
            CORROBORATION_OP: _r(**PARAM_401),
        }, missing=(AUTH_CHECK_OP,))
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert AUTH_CHECK_OP not in asked
        assert "not in the catalog" in rec.last_error
        assert "both refused" not in rec.last_error

    @pytest.mark.asyncio
    async def test_the_verdict_message_fits_its_cap_and_keeps_its_reason(self, isolated_db):
        """``last_error`` is capped at 200; the reason inside is capped first
        so the cap never eats the diagnostic (round-2 review F5)."""
        _seed_skip_row()
        long_reason = "Failed to parse JSON response: " + "x" * 160
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _r(error="Transport error: "),
            CORROBORATION_OP: _r(**PARAM_401),
            AUTH_CHECK_OP: _r(status_code=200, error=long_reason),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.AUTH_FAILED
        assert len(rec.last_error) <= 200
        assert rec.last_error.endswith(")"), rec.last_error

    @pytest.mark.asyncio
    async def test_a_readable_device_is_still_limited_api(self, isolated_db):
        """Control: nothing changes for the switch with working credentials."""
        catalog, executor, asked = _per_op({
            SYSTEMREADY_OP: _r(status_code=200, error=PARSE_FAIL),
            CORROBORATION_OP: _r(**PARAM_OK),
        })
        rec = await _sweep(catalog, executor)
        assert rec.status == DeviceHealthStatus.LIMITED_API
        assert AUTH_CHECK_OP not in asked, "no corroboration request on a healthy read"
