"""Unit tests for the shared gated-execution core (admz/operations.py).

This is the anti-drift guard for the MCP/REST/plan unification: every surface
now routes device operations through these functions, so the gate behavior is
defined and asserted in one place. The MCP and REST acceptance suites
(test_mcp_risk_gates.py, test_api_routes.py) prove the surfaces delegate here.
"""

from __future__ import annotations

import pytest

from admz import operations
from admz.api.confirm_store import ConfirmStore
from admz.exceptions import (
    DeviceNotFoundError,
    NoExecutorError,
    OperationNotFoundError,
)
from admz.executor.models import StepResult


# --- fakes -----------------------------------------------------------------


class _FakeOp:
    danger_description = ""
    service_impact = ""

    def to_executor_dict(self):
        return {"id": "test:op"}


class _FakeCatalog:
    def __init__(self, risk="normal", op=_FakeOp()):
        self._risk = risk
        self._op = op

    def get_risk_level(self, family, op_id):
        return self._risk

    def get_operation(self, family, op_id):
        return self._op


class _FakeRegistry:
    def __init__(self, exists=True):
        self._exists = exists

    def device_exists(self, device_id):
        return self._exists

    def get_device_info(self, device_id):
        return {"host": "192.0.2.1"}

    def get_credentials(self, device_id):
        return {"username": "root", "password": "x"}


class _FakeExecutor:
    def __init__(self):
        self.calls = []

    async def execute(self, op, device, credentials, params):
        self.calls.append((op["id"], dict(params)))
        return StepResult(
            operation_id="test:op", device_id="dev", success=True,
            status_code=200, parsed_data={"ok": True}, duration_ms=5.0,
        )


@pytest.fixture
def store(tmp_path):
    return ConfirmStore(str(tmp_path / "confirm.db"))


def _executors():
    return {"vapix": _FakeExecutor()}


# --- execute_gated_operation ----------------------------------------------


@pytest.mark.asyncio
async def test_none_level_runs_inline(store, monkeypatch):
    monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "none")
    execs = _executors()
    result = await operations.execute_gated_operation(
        device_id="dev", operation_id="test:op", family="vapix", params={"a": "1"},
        catalog=_FakeCatalog("read-only"), registry=_FakeRegistry(),
        executors=execs, store=store,
    )
    assert result["success"] is True
    assert "blocked" not in result
    assert execs["vapix"].calls == [("test:op", {"a": "1"})]


@pytest.mark.asyncio
@pytest.mark.parametrize("level", ["llm_confirm", "url_only", "url_and_password"])
async def test_gated_levels_block_without_executing(store, monkeypatch, level):
    monkeypatch.setattr(operations, "resolve_confirmation", lambda r: level)
    execs = _executors()
    result = await operations.execute_gated_operation(
        device_id="dev", operation_id="test:op", family="vapix", params={},
        catalog=_FakeCatalog("service-affecting"), registry=_FakeRegistry(),
        executors=execs, store=store,
    )
    assert result["blocked"] is True
    assert result["confirmation_level"] == level
    assert result["confirm_url"].startswith("/confirm/")
    assert result["confirm_tool"] == "confirm_dangerous_operation"
    assert result["message"]
    # The op must NOT have run, and a session must exist in the store.
    assert execs["vapix"].calls == []
    assert store.get_session(result["confirm_token"]) is not None


@pytest.mark.asyncio
async def test_reason_prefers_danger_description(store, monkeypatch):
    monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_and_password")
    op = _FakeOp()
    op.danger_description = "This wipes all settings."
    result = await operations.execute_gated_operation(
        device_id="dev", operation_id="test:op", family="vapix", params={},
        catalog=_FakeCatalog("dangerous", op=op), registry=_FakeRegistry(),
        executors=_executors(), store=store,
    )
    assert "wipes all settings" in result["reason"]


# --- run_execution_tail typed errors --------------------------------------


@pytest.mark.asyncio
async def test_tail_raises_operation_not_found():
    class _NoOp(_FakeCatalog):
        def get_operation(self, family, op_id):
            return None

    with pytest.raises(OperationNotFoundError):
        await operations.run_execution_tail(
            device_id="dev", operation_id="nope", family="vapix", params={},
            catalog=_NoOp(), registry=_FakeRegistry(), executors=_executors(),
        )


@pytest.mark.asyncio
async def test_tail_raises_no_executor():
    with pytest.raises(NoExecutorError):
        await operations.run_execution_tail(
            device_id="dev", operation_id="test:op", family="vapix", params={},
            catalog=_FakeCatalog(), registry=_FakeRegistry(), executors={},
        )


@pytest.mark.asyncio
async def test_tail_raises_device_not_found():
    with pytest.raises(DeviceNotFoundError):
        await operations.run_execution_tail(
            device_id="dev", operation_id="test:op", family="vapix", params={},
            catalog=_FakeCatalog(), registry=_FakeRegistry(exists=False),
            executors=_executors(),
        )


@pytest.mark.asyncio
async def test_tail_empty_creds_fallback_when_no_account():
    from admz.exceptions import AccountNotFoundError

    class _NoCreds(_FakeRegistry):
        def get_credentials(self, device_id):
            raise AccountNotFoundError("none")

    execs = _executors()
    await operations.run_execution_tail(
        device_id="dev", operation_id="test:op", family="vapix", params={},
        catalog=_FakeCatalog(), registry=_NoCreds(), executors=execs,
    )
    assert execs["vapix"].calls  # executed with the empty-cred fallback


# --- consume_confirmation --------------------------------------------------


@pytest.mark.asyncio
async def test_consume_llm_confirm_completes_and_executes(store):
    session = store.create_session(
        device_id="dev", operation_id="test:op", family="vapix", params={"p": "1"},
        risk_level="service-affecting", confirmation_level="llm_confirm",
    )
    execs = _executors()
    result = await operations.consume_confirmation(
        session.token, catalog=_FakeCatalog(), registry=_FakeRegistry(),
        executors=execs, store=store, confirmed_by="test",
        enforce_url_flow_block=True,
    )
    assert result["confirmed"] is True
    assert result["success"] is True
    assert execs["vapix"].calls  # the op actually ran
    # single-use: a second consume fails
    again = await operations.consume_confirmation(
        session.token, catalog=_FakeCatalog(), registry=_FakeRegistry(),
        executors=_executors(), store=store, confirmed_by="test",
        enforce_url_flow_block=True,
    )
    assert again["success"] is False
    assert "Invalid or expired" in again["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("level", ["url_only", "url_and_password"])
async def test_consume_refuses_url_flow_when_enforced(store, level):
    session = store.create_session(
        device_id="dev", operation_id="test:op", family="vapix", params={},
        risk_level="dangerous", confirmation_level=level,
    )
    execs = _executors()
    result = await operations.consume_confirmation(
        session.token, catalog=_FakeCatalog(), registry=_FakeRegistry(),
        executors=execs, store=store, confirmed_by="rest",
        enforce_url_flow_block=True,
    )
    assert result["success"] is False
    assert result["confirmation_level"] == level
    assert "/confirm/" in result["confirm_url"]
    assert execs["vapix"].calls == []          # never ran
    # the session must remain pending (NOT consumed) so the web form can use it
    assert store.get_session(session.token) is not None


@pytest.mark.asyncio
async def test_consume_invalid_token(store):
    result = await operations.consume_confirmation(
        "no-such-token", catalog=_FakeCatalog(), registry=_FakeRegistry(),
        executors=_executors(), store=store, confirmed_by="mcp",
        enforce_url_flow_block=True,
    )
    assert result["success"] is False
    assert "Invalid or expired" in result["error"]


# --- execute_approved_session (the gap-fix helper) -------------------------


@pytest.mark.asyncio
async def test_execute_approved_session_runs_single_op(store):
    session = store.create_session(
        device_id="dev", operation_id="test:op", family="vapix", params={},
        risk_level="dangerous", confirmation_level="url_and_password",
    )
    execs = _executors()
    outcome = await operations.execute_approved_session(
        session, catalog=_FakeCatalog(), registry=_FakeRegistry(), executors=execs,
    )
    assert outcome["confirmed"] is True
    assert outcome["success"] is True
    assert execs["vapix"].calls  # ran on approval
