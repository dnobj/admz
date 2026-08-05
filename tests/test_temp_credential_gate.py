"""GH #313: create_temp_credentials must not bypass the confirmation gate.

`_create_temp_credentials` reached the VAPIX executor through
`_execute_on_host` directly, so `resolve_confirmation` was never consulted.
#165 reclassified `pwdgrp.cgi:add-user` to `service-affecting`, which closed
the *generic* execution path — `execute_operation`, its REST equivalent, plan
steps — and did not reach this tool at all. "Creating a device account requires
no approval" stayed true here.

**The level is inherited, never hardcoded.** The gate reads the catalog's
risk_level for the operation the tool actually performs, so one classification
governs both paths and there is no second opinion to keep in step (#255). A
catalog that has not picked up #165's atlas change resolves to `none` and
behaves as before — deliberately, because whether to pull the atlas is the
operator's call and this must not depend on it.

**The vacuity shape.** "the tool is gated" is trivially green if the tool
errors early for an unrelated reason — a missing device, bad permissions, no
credentials all return `success: False` without proving anything about the
gate. So every gated assertion checks for the *blocked envelope* specifically
and asserts no device call was made, and `test_none_risk_still_creates` pins
that the ungated path still works.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from admz import operations
from admz.operations import TEMP_CREDENTIAL_OP


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    yield tmp_path


def _server(risk="service-affecting"):
    """An MCP server stub exposing only what the gate path touches."""
    from admz.mcp.server import ADMZMCPServer

    srv = object.__new__(ADMZMCPServer)
    srv.catalog = MagicMock()
    srv.catalog.get_risk_level.return_value = risk
    srv.registry = MagicMock()
    srv.registry.device_exists.return_value = True
    srv.registry.get_device_info.return_value = {"host": "192.0.2.1"}
    srv.registry.get_credentials.return_value = {"username": "root",
                                                 "password": "adminpw"}
    from admz.mcp.temp_credentials import TempCredentialManager
    srv.temp_creds = TempCredentialManager()
    srv._execute_on_host = AsyncMock(return_value=(True, None))
    return srv


def _call(srv, **kw):
    args = {"device_id": "cam-01", "permissions": "admin", "ttl_seconds": 300}
    args.update(kw)
    return asyncio.run(srv._create_temp_credentials(args))


# --- the gate --------------------------------------------------------------


def test_a_gated_risk_blocks_and_creates_no_account():
    """THE #313 defect. Before this the tool created a root-capable account
    with no confirmation card, no confirm URL, and no human."""
    srv = _server(risk="service-affecting")

    out = _call(srv)

    assert out.get("blocked") is True, f"not blocked: {out}"
    assert out.get("success") is False
    assert out.get("confirm_token"), "a blocked envelope must carry a token"
    srv._execute_on_host.assert_not_awaited(), (
        "the account was created despite being blocked")
    assert srv.temp_creds.get_all() == []


def test_the_level_is_read_from_the_catalog_for_the_real_operation():
    """Inherited, not hardcoded — and for the operation actually performed."""
    srv = _server(risk="service-affecting")
    _call(srv)

    srv.catalog.get_risk_level.assert_called_with("vapix", TEMP_CREDENTIAL_OP)
    assert TEMP_CREDENTIAL_OP == "pwdgrp.cgi:add-user"


def test_a_dangerous_classification_is_inherited_too():
    """If an operator raises the class, the gate follows without a code change.

    Asserting the *level* is what makes this test load-bearing. `dangerous` is
    deliberately chosen because it differs from `create_action_session`'s
    historical `service-affecting` default: with only `blocked is True`
    asserted, dropping the `risk=` passthrough killed no test at all —
    mutation testing found that, and this is the fix.
    """
    srv = _server(risk="dangerous")
    out = _call(srv)

    assert out.get("blocked") is True
    assert out.get("risk_level") == "dangerous", (
        "the session did not inherit the catalog's classification")
    assert out.get("confirmation_level") == "url_and_password", (
        "a dangerous classification must resolve to the stronger gate, not the "
        "service-affecting default")


def test_a_service_affecting_classification_resolves_to_the_weaker_gate():
    """The pair, so the test above is not green for a gate stuck on
    url_and_password regardless of what the catalog says."""
    srv = _server(risk="service-affecting")
    out = _call(srv)

    assert out.get("risk_level") == "service-affecting"
    assert out.get("confirmation_level") == "url_only"


def test_none_risk_still_creates_the_account():
    """The anti-vacuity pair, and the pre-atlas-pull path.

    A catalog without #165's reclassification resolves to `none`. This must
    behave exactly as before rather than depending on an atlas pull the
    operator has not made — and without it, every 'blocked' assertion above
    would pass for a tool that can never create anything.
    """
    srv = _server(risk="normal")   # normal → none by default policy

    out = _call(srv)

    assert out.get("success") is True, f"ungated path broke: {out}"
    assert out.get("password"), "the caller must still receive the credential"
    srv._execute_on_host.assert_awaited_once()
    assert len(srv.temp_creds.get_all()) == 1


def test_an_unreadable_catalog_fails_closed():
    """A catalog that raises must not open the gate. Over-refusing is
    recoverable; under-refusing creates an unapproved account."""
    srv = _server()
    srv.catalog.get_risk_level.side_effect = RuntimeError("catalog not loaded")

    out = _call(srv)

    assert out.get("blocked") is True
    srv._execute_on_host.assert_not_awaited()


def test_the_blocked_payload_carries_no_credential():
    """#194/#276: nothing credential-shaped may enter confirm_sessions.

    The password is generated at execution time, after approval, so the
    session payload cannot contain one.
    """
    srv = _server()
    out = _call(srv)

    import json
    blob = json.dumps(out)
    assert "adminpw" not in blob, "the admin password reached the envelope"
    assert "pwd" not in json.dumps(out.get("params") or {})


def test_the_reason_names_what_is_being_approved():
    """An approval card that does not say an account is being created on a
    camera is not informed consent."""
    srv = _server()
    out = _call(srv)
    reason = (out.get("danger_description") or "") + (out.get("reason") or "")
    assert "cam-01" in reason
    assert "account" in reason.lower()


# --- the approved executor -------------------------------------------------


def test_the_registered_action_exists():
    assert "create_temp_credentials" in operations._ACTION_EXECUTORS


def test_approval_creates_the_account_and_records_it(monkeypatch, tmp_path):
    """The other half: on approval the account is created AND registered.

    Registering is only possible from this process because #314 made the store
    shared. While it was per-process memory, an approved creation would have
    orphaned the account on every use — which is why persistence shipped first.
    """
    from admz.mcp.temp_credentials import TempCredentialManager

    created = {}

    async def _fake_exec(catalog, executors, host, op_id, params, **kw):
        created.update({"host": host, "op": op_id, "params": params})
        return True, None

    monkeypatch.setattr("admz.provisioning.execute_on_host", _fake_exec)
    monkeypatch.setattr("admz.api.context.get_context",
                        lambda: MagicMock(catalog=MagicMock(), executors={}))

    registry = MagicMock()
    registry.get_device_info.return_value = {"host": "192.0.2.1"}
    registry.get_credentials.return_value = {"username": "root", "password": "a"}

    out = asyncio.run(operations._action_create_temp_credentials(
        {"action": "create_temp_credentials", "device_id": "cam-01",
         "permissions": "viewer", "ttl_seconds": 120},
        registry))

    assert out["success"] is True
    assert created["op"] == TEMP_CREDENTIAL_OP
    assert created["params"]["grp"] == "users"
    assert out["password"], "the approver must receive the credential"

    rows = TempCredentialManager().get_all()
    assert len(rows) == 1, "the account was created but never recorded (#314)"
    assert rows[0].username == out["username"]


def test_approval_with_bad_permissions_creates_nothing(monkeypatch):
    calls = []

    async def _fake_exec(*a, **k):
        calls.append(a)
        return True, None

    monkeypatch.setattr("admz.provisioning.execute_on_host", _fake_exec)
    out = asyncio.run(operations._action_create_temp_credentials(
        {"device_id": "cam-01", "permissions": "superuser"}, MagicMock()))

    assert out["success"] is False
    assert calls == []


def test_a_failed_device_call_records_nothing(monkeypatch):
    """No account created means no record — the inverse of #314's rule."""
    from admz.mcp.temp_credentials import TempCredentialManager

    async def _fails(*a, **k):
        return False, "401 Unauthorized"

    monkeypatch.setattr("admz.provisioning.execute_on_host", _fails)
    monkeypatch.setattr("admz.api.context.get_context",
                        lambda: MagicMock(catalog=MagicMock(), executors={}))

    registry = MagicMock()
    registry.get_device_info.return_value = {"host": "192.0.2.1"}
    registry.get_credentials.return_value = {"username": "root", "password": "a"}

    out = asyncio.run(operations._action_create_temp_credentials(
        {"device_id": "cam-01", "permissions": "viewer"}, registry))

    assert out["success"] is False
    assert TempCredentialManager().get_all() == []


# --- create_action_session's new risk passthrough --------------------------


def test_risk_defaults_preserve_existing_callers():
    """Every pre-#313 caller passed no risk and must keep service-affecting."""
    import inspect
    sig = inspect.signature(operations.create_action_session)
    assert sig.parameters["risk"].default == "service-affecting"
