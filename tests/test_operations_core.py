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


# --- credential warning on the gate ----------------------------------------
# A gated vapix op against a device with no stored credentials will 401 on
# approval — the confirm card must say so BEFORE the user clicks approve
# (live case: an approved factory reset burned on 401, P3408 2026-07-03).


class _NoCredsRegistry(_FakeRegistry):
    def get_credentials(self, device_id):
        from admz.exceptions import AccountNotFoundError

        raise AccountNotFoundError("no account")


class _BrokenRegistry(_FakeRegistry):
    def get_credentials(self, device_id):
        raise RuntimeError("backend down")


@pytest.mark.asyncio
async def test_gate_warns_when_device_has_no_credentials(store, monkeypatch):
    monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_and_password")
    result = await operations.execute_gated_operation(
        device_id="dev", operation_id="test:op", family="vapix", params={},
        catalog=_FakeCatalog("dangerous"), registry=_NoCredsRegistry(),
        executors=_executors(), store=store,
    )
    assert result["blocked"] is True
    assert "no stored credentials" in result["credential_warning"]
    assert "no stored credentials" in result["message"]
    # …and the confirm page / chat approval card render danger_description:
    session = store.get_session(result["confirm_token"])
    assert "no stored credentials" in session.danger_description


@pytest.mark.asyncio
async def test_gate_no_warning_when_credentials_stored(store, monkeypatch):
    monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_only")
    result = await operations.execute_gated_operation(
        device_id="dev", operation_id="test:op", family="vapix", params={},
        catalog=_FakeCatalog("service-affecting"), registry=_FakeRegistry(),
        executors=_executors(), store=store,
    )
    assert result["blocked"] is True
    assert "credential_warning" not in result
    session = store.get_session(result["confirm_token"])
    assert "no stored credentials" not in session.danger_description


def test_warning_helper_edges():
    # No registry at gate time / non-vapix family / backend hiccup → silent.
    assert operations.missing_credentials_warning(None, "dev") == ""
    assert operations.missing_credentials_warning(_NoCredsRegistry(), "dev", "acs-pro") == ""
    assert operations.missing_credentials_warning(_BrokenRegistry(), "dev") == ""
    # Missing account or empty password → warn.
    assert "no stored credentials" in operations.missing_credentials_warning(
        _NoCredsRegistry(), "dev")

    class _EmptyPw(_FakeRegistry):
        def get_credentials(self, device_id):
            return {"username": "root", "password": ""}

    assert "no stored credentials" in operations.missing_credentials_warning(
        _EmptyPw(), "dev")


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


# --- C-1: cross-process plan approval ----------------------------------------
# Plans created in an MCP subprocess are not in the uvicorn process's
# PlanEngine._plans.  execute_gated_plan must serialise the steps into the
# confirm session, and execute_approved_session must reconstruct the plan
# from that data when the in-memory lookup misses.


class _FakeOpWithRisk(_FakeOp):
    """FakeOp that also carries risk_level for PlanEngine.create_plan()."""
    risk_level = "service-affecting"


class _FakeCatalogForPlan(_FakeCatalog):
    """Catalog that returns an op with risk_level for plan-engine use."""
    def __init__(self):
        super().__init__(risk="service-affecting", op=_FakeOpWithRisk())

    def get_operation(self, family, op_id):
        return _FakeOpWithRisk()


class _FakePlanEngine:
    """Minimal plan engine stand-in for C-1 tests."""

    def __init__(self, catalog, registry, executors):
        from admz.plans.engine import PlanEngine
        self._engine = PlanEngine(catalog, registry, executors)

    def create_plan(self, *a, **kw):
        return self._engine.create_plan(*a, **kw)

    def get_plan(self, plan_id):
        return self._engine.get_plan(plan_id)

    def register_plan(self, plan):
        self._engine.register_plan(plan)

    async def run_plan(self, plan_id):
        return await self._engine.run_plan(plan_id)

    @property
    def _plans(self):
        return self._engine._plans

    @_plans.setter
    def _plans(self, v):
        self._engine._plans = v


@pytest.mark.asyncio
async def test_execute_gated_plan_serialises_steps_into_session(store, monkeypatch):
    """execute_gated_plan stores plan_steps_json in the confirm session
    so a different process can reconstruct the plan on approval."""
    monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_only")

    execs = _executors()
    engine = _FakePlanEngine(_FakeCatalogForPlan(), _FakeRegistry(), execs)
    plan = engine.create_plan("test plan", [
        {"operation_id": "test:op", "device_id": "dev", "params": {"x": "1"}},
    ])

    result = await operations.execute_gated_plan(engine, plan.plan_id, store=store)
    assert result.get("blocked") is True

    session = store.get_session(result["confirm_token"])
    assert session is not None
    assert session.plan_steps_json  # must be non-empty

    import json
    steps = json.loads(session.plan_steps_json)
    assert len(steps) == 1
    assert steps[0]["operation_id"] == "test:op"
    assert steps[0]["device_id"] == "dev"
    assert steps[0]["params"] == {"x": "1"}


@pytest.mark.asyncio
async def test_execute_approved_session_reconstructs_plan_cross_process(store, monkeypatch):
    """C-1 fix: when plan_engine has no entry for the plan_id (simulating the
    cross-process gap), execute_approved_session reconstructs it from
    plan_steps_json and still executes the plan successfully."""
    monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_only")

    execs = _executors()
    engine = _FakePlanEngine(_FakeCatalogForPlan(), _FakeRegistry(), execs)
    plan = engine.create_plan("test plan", [
        {"operation_id": "test:op", "device_id": "dev", "params": {"k": "v"}},
    ])

    # Gate creates the confirm session with serialised steps.
    blocked = await operations.execute_gated_plan(engine, plan.plan_id, store=store)
    token = blocked["confirm_token"]
    session = store.get_session(token)
    assert session.plan_steps_json

    # Simulate the cross-process gap: clear the in-memory dict.
    engine._plans.clear()
    assert engine.get_plan(plan.plan_id) is None  # precondition

    # Approve + execute — must reconstruct and run.
    outcome = await operations.execute_approved_session(
        session,
        catalog=_FakeCatalogForPlan(), registry=_FakeRegistry(), executors=execs,
        plan_engine=engine,
    )
    assert outcome.get("success") is True
    assert outcome.get("is_plan") is True
    assert outcome["steps_succeeded"] == 1
    assert execs["vapix"].calls  # the step actually ran


@pytest.mark.asyncio
async def test_execute_approved_session_uses_in_memory_plan_when_present(store, monkeypatch):
    """When the plan IS in the engine's memory (same-process path), the normal
    code path runs without reconstruction."""
    monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_only")

    execs = _executors()
    engine = _FakePlanEngine(_FakeCatalogForPlan(), _FakeRegistry(), execs)
    plan = engine.create_plan("test plan", [
        {"operation_id": "test:op", "device_id": "dev", "params": {}},
    ])

    blocked = await operations.execute_gated_plan(engine, plan.plan_id, store=store)
    session = store.get_session(blocked["confirm_token"])

    # Plan is still in memory — no reconstruction needed.
    assert engine.get_plan(plan.plan_id) is not None

    outcome = await operations.execute_approved_session(
        session,
        catalog=_FakeCatalogForPlan(), registry=_FakeRegistry(), executors=execs,
        plan_engine=engine,
    )
    assert outcome.get("success") is True
    assert outcome["steps_succeeded"] == 1


# --- #334: catalog-declared secret params never reach params_json ----------
# A confirm session for e.g. pwdgrp.cgi:update-user used to store the new
# device password in plaintext in confirm_sessions.params_json AND render it
# unmasked on the approval page. execute_gated_operation now strips any
# catalog-declared secret-shaped VALUE before create_session ever sees it
# (keeping the KEY, so the approval card still shows what's changing);
# execute_approved_session merges the value back in from the approval POST,
# in memory only, at execution time.


class _FakeOpWithPasswordParam(_FakeOp):
    """A pwdgrp.cgi:update-user-shaped operation: {"pwd": "{password}"} is
    exactly the whole-value placeholder shape secret_param_names looks for."""
    request = {"query": {"action": "update", "user": "{username}", "pwd": "{password}"}}


class _FakeOpWithPresetToken(_FakeOp):
    """A PTZ-preset-shaped operation. {PresetToken} is a legitimate resource
    identifier, not a credential — this is the required negative pin for
    #334 finding 6: a substring-based check (is_sensitive_key's "token" in k)
    would misfire on this; the narrow, exact-match vocabulary must not."""
    request = {"query": {"preset": "{PresetToken}"}}


@pytest.mark.asyncio
async def test_secret_param_value_stripped_from_stored_session(store, monkeypatch):
    monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_only")
    result = await operations.execute_gated_operation(
        device_id="dev", operation_id="pwdgrp.cgi:update-user", family="vapix",
        params={"user": "root", "password": "hunter2SECRET"},
        catalog=_FakeCatalog("service-affecting", op=_FakeOpWithPasswordParam()),
        registry=_FakeRegistry(), executors=_executors(), store=store,
    )
    assert result["blocked"] is True
    session = store.get_session(result["confirm_token"])
    # The KEY is kept (so the approval card can still say what's changing)...
    assert session.secret_fields == ["password"]
    # ...but the VALUE never reaches params or params_json, at rest or in the
    # blocked envelope.
    assert "password" not in session.params
    assert "hunter2SECRET" not in session.params_json
    assert "hunter2SECRET" not in str(result)
    # The unrelated ordinary param round-trips untouched — the OTHER
    # direction this fix must not break.
    assert session.params["user"] == "root"
    # The operator is told a field must be entered on the confirm page.
    assert "password" in result["message"]


@pytest.mark.asyncio
async def test_ordinary_operation_has_no_secret_fields_and_round_trips(store, monkeypatch):
    """Pin the other direction explicitly (#334 ask): an operation with no
    catalog-declared secret-shaped params is completely unaffected by this
    fix — no stripping, no secret_fields, every param intact."""
    monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_only")
    result = await operations.execute_gated_operation(
        device_id="dev", operation_id="test:op", family="vapix",
        params={"a": "1", "b": "2"},
        catalog=_FakeCatalog("service-affecting"), registry=_FakeRegistry(),
        executors=_executors(), store=store,
    )
    assert result["blocked"] is True
    session = store.get_session(result["confirm_token"])
    assert session.secret_fields == []
    assert session.params == {"a": "1", "b": "2"}


@pytest.mark.asyncio
async def test_preset_token_param_is_not_treated_as_secret(store, monkeypatch):
    """#334 finding 6, pinned at the execute_gated_operation level too (see
    tests/test_vapix_secret_param_names.py for the unit-level pin): a
    {PresetToken}-shaped param must never be stripped or listed as a secret
    field — it's a resource identifier, not a credential."""
    monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_only")
    result = await operations.execute_gated_operation(
        device_id="dev", operation_id="ptz.cgi:gotoPreset", family="vapix",
        params={"preset": "preset-42"},
        catalog=_FakeCatalog("service-affecting", op=_FakeOpWithPresetToken()),
        registry=_FakeRegistry(), executors=_executors(), store=store,
    )
    session = store.get_session(result["confirm_token"])
    assert session.secret_fields == []
    assert session.params == {"preset": "preset-42"}


@pytest.mark.asyncio
async def test_execute_approved_session_merges_secret_value_and_executes(store):
    session = store.create_session(
        device_id="dev", operation_id="test:op", family="vapix",
        params={"user": "root"}, secret_fields=["password"],
        risk_level="service-affecting", confirmation_level="url_only",
    )
    execs = _executors()
    outcome = await operations.execute_approved_session(
        session, catalog=_FakeCatalog(), registry=_FakeRegistry(), executors=execs,
        secret_values={"password": "hunter2SECRET"},
    )
    assert outcome["success"] is True
    # The executor actually received the TRUE value, merged in memory only.
    assert execs["vapix"].calls == [
        ("test:op", {"user": "root", "password": "hunter2SECRET"})
    ]


@pytest.mark.asyncio
async def test_execute_approved_session_refuses_if_secret_value_missing(store):
    session = store.create_session(
        device_id="dev", operation_id="test:op", family="vapix",
        params={"user": "root"}, secret_fields=["password"],
        risk_level="service-affecting", confirmation_level="url_only",
    )
    execs = _executors()
    outcome = await operations.execute_approved_session(
        session, catalog=_FakeCatalog(), registry=_FakeRegistry(), executors=execs,
        secret_values=None,
    )
    assert outcome["success"] is False
    assert "password" in outcome["error"]
    assert execs["vapix"].calls == []  # nothing was ever sent to the device


@pytest.mark.asyncio
async def test_execute_approved_session_refuses_on_empty_secret_value(store):
    """An explicitly-empty string must refuse the same as a wholly absent
    key — an empty password field submitted is not a value."""
    session = store.create_session(
        device_id="dev", operation_id="test:op", family="vapix",
        params={"user": "root"}, secret_fields=["password"],
        risk_level="service-affecting", confirmation_level="url_only",
    )
    execs = _executors()
    outcome = await operations.execute_approved_session(
        session, catalog=_FakeCatalog(), registry=_FakeRegistry(), executors=execs,
        secret_values={"password": ""},
    )
    assert outcome["success"] is False
    assert execs["vapix"].calls == []


@pytest.mark.asyncio
async def test_execute_approved_session_without_secret_fields_unaffected(store):
    """The other direction again, at the execute_approved_session layer: a
    session with no secret_fields runs exactly as it always did, whether or
    not a caller happens to pass secret_values."""
    session = store.create_session(
        device_id="dev", operation_id="test:op", family="vapix", params={"a": "1"},
        risk_level="dangerous", confirmation_level="url_and_password",
    )
    execs = _executors()
    outcome = await operations.execute_approved_session(
        session, catalog=_FakeCatalog(), registry=_FakeRegistry(), executors=execs,
    )
    assert outcome["success"] is True
    assert execs["vapix"].calls == [("test:op", {"a": "1"})]


@pytest.mark.asyncio
async def test_consume_confirmation_refuses_when_secret_fields_pending(store):
    """#334: chat/MCP completion of a credential-bearing session is refused
    unconditionally — even at llm_confirm level, i.e. even if an operator
    has reconfigured this risk class away from a url_* flow — because
    neither surface has a safe way to collect the value. Mirrors the
    existing enforce_url_flow_block shape one check above this in
    consume_confirmation."""
    session = store.create_session(
        device_id="dev", operation_id="test:op", family="vapix",
        params={"user": "root"}, secret_fields=["password"],
        risk_level="service-affecting", confirmation_level="llm_confirm",
    )
    execs = _executors()
    result = await operations.consume_confirmation(
        session.token, catalog=_FakeCatalog(), registry=_FakeRegistry(),
        executors=execs, store=store, confirmed_by="chat",
        enforce_url_flow_block=False,
    )
    assert result["success"] is False
    assert "password" in result["error"]
    assert "/confirm/" in result["confirm_url"]
    assert execs["vapix"].calls == []
    # The session must remain pending — the web form can still complete it.
    assert store.get_session(session.token) is not None
