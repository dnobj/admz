"""ADR-0068 S2 — the MCP `provision_device` tool has no credential write of its own.

It used to carry an inline copy of the whole thing: its own factory-default
detector (`probe_credentials` rather than onboarding's unauthenticated
`read_systemready`), its own `pwdgrp.cgi:add-user`, its own `update-user`
rotation, and its own password ordering. That copy did three things ADR-0068
forbids, on the one path the model can reach:

  * it STORED A ROOT CREDENTIAL per device on the factory-default branch;
  * it stored whatever answered a legacy `root/pass` probe as the device's own
    standing credential — a published password promoted to ongoing access;
  * and it never passed ADR-0059's gate, which lives at the decision point
    inside `onboard_device_credentials`. A second implementation of the write is
    a second implementation with no gate.

These tests pin the collapse: the handler registers a host if needed and then
delegates. What it must NOT do is the interesting half, so most of this file is
absences — no add-user, no store, no password argument accepted.

The predecessor file pinned FR-CRED-007 at this tool ("the fleet
default_password is never what it writes"). That claim is now structural rather
than asserted here: the tool writes nothing at all, and the requirement is
pinned where the write lives, in tests/test_provisioning.py.
"""

from types import SimpleNamespace

import pytest

import admz.mcp.server as server_mod
from admz.discovery.credential_probe import ProbeStatus
from admz.mcp.server import ADMZMCPServer

SERIAL = "ACCC8E000001"


class _Srv:
    """Only the collaborators the collapsed handler touches.

    Deliberately does NOT provide `_execute_on_host` or a credential-storing
    helper: if a future edit reintroduces an inline write, these tests fail with
    AttributeError rather than quietly passing against a fake that allowed it.
    """

    def __init__(self, exists=True):
        self.added = []
        self.onboarded = []
        self._exists = exists
        self.registry = SimpleNamespace(
            device_exists=lambda device_id: self._exists,
            get_device_info=lambda device_id: {"host": "1.2.3.4"},
            update_device_info=lambda device_id, updates: None,
            add_device=lambda device_id, info: self.added.append((device_id, info)),
        )

    async def _onboard_device(self, device_id, adopt=False):
        self.onboarded.append((device_id, adopt))
        return {"status": "provisioned", "device_id": device_id,
                "username": "admz", "root_username": "root",
                "root_password_source": "fleet_root",
                "password_source": "generated",
                "message": "ADMZ set root from the fleet root password."}

    @staticmethod
    def _serial_to_mac(serial):
        return serial


def _probe(status, **overrides):
    fields = dict(status=status, device_info={"serial_number": SERIAL},
                  auth=None, detail="", username=None, password=None,
                  auth_method=None)
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _device_answers(monkeypatch, probe):
    async def fake_probe(host):
        return probe

    monkeypatch.setattr(server_mod, "probe_credentials", fake_probe)


# --- the collapse ----------------------------------------------------------


@pytest.mark.asyncio
async def test_a_registered_device_is_delegated_and_never_probed(monkeypatch):
    """One detector. The tool must not run its own factory-default probe —
    onboarding's unauthenticated `read_systemready` is the one that decides."""
    probed = []

    async def fake_probe(host):
        probed.append(host)
        raise AssertionError("the tool ran its own credential probe")

    monkeypatch.setattr(server_mod, "probe_credentials", fake_probe)
    srv = _Srv()
    out = await ADMZMCPServer._provision_device(srv, {"device_id": "cam-1"})

    assert probed == []
    assert srv.onboarded == [("cam-1", False)]
    assert out["success"] is True and out["status"] == "provisioned"
    assert out["onboarding"]["username"] == "admz"


@pytest.mark.asyncio
async def test_success_is_the_onboarding_outcome_not_that_the_tool_ran(monkeypatch):
    """`operations.py` uses the same rule (`ok = status == PROVISIONED`). A tool
    that answered success for a device it never provisioned would tell the
    operator their approval worked."""
    srv = _Srv()

    async def _refused(device_id, adopt=False):
        return {"status": "root_password_not_configured", "device_id": device_id,
                "message": "no fleet root password is set"}

    srv._onboard_device = _refused
    out = await ADMZMCPServer._provision_device(srv, {"device_id": "cam-1"})
    assert out["success"] is False
    assert out["status"] == "root_password_not_configured"
    assert "fleet root password" in out["message"]


@pytest.mark.asyncio
async def test_a_host_only_call_registers_then_delegates(monkeypatch):
    _device_answers(monkeypatch, _probe(ProbeStatus.FACTORY_DEFAULT))
    srv = _Srv(exists=False)
    out = await ADMZMCPServer._provision_device(srv, {"host": "1.2.3.4"})

    assert out["auto_registered"] is True
    assert srv.added and srv.added[0][0] == SERIAL
    assert srv.added[0][1]["tags"] == ["axis", "auto-registered"]
    assert srv.onboarded == [(SERIAL, False)]


@pytest.mark.asyncio
async def test_an_unreachable_host_only_call_registers_nothing(monkeypatch):
    _device_answers(monkeypatch, _probe(ProbeStatus.UNREACHABLE, detail="no route"))
    srv = _Srv(exists=False)
    out = await ADMZMCPServer._provision_device(srv, {"host": "1.2.3.4"})

    assert out["success"] is False and out["status"] == "unreachable"
    assert srv.added == [] and srv.onboarded == []


@pytest.mark.asyncio
async def test_a_host_beside_a_known_device_id_does_not_redirect_the_write(monkeypatch):
    """#193's shape. Approving a provision for one device and having it land on
    a caller-supplied address is the failure `operations.py` already refuses when
    the address moved since approval; the tool must not open it a second way."""
    _device_answers(monkeypatch, _probe(ProbeStatus.FACTORY_DEFAULT))
    srv = _Srv()
    out = await ADMZMCPServer._provision_device(
        srv, {"device_id": "cam-1", "host": "10.9.9.9"})

    assert srv.onboarded == [("cam-1", False)]
    assert srv.added == []
    assert "10.9.9.9" not in repr(out)


# --- what it will no longer accept ----------------------------------------


@pytest.mark.parametrize("arg,value", [
    ("password", "Chosen-1"),
    ("username", "operator"),
    ("force_change", True),
])
@pytest.mark.asyncio
async def test_the_retired_arguments_are_refused_not_ignored(arg, value):
    """Silently dropping a caller's explicit password is worse than refusing it:
    the caller believes it was set. The refusal also says where a real password
    change belongs."""
    srv = _Srv()
    out = await ADMZMCPServer._provision_device(srv, {"device_id": "cam-1", arg: value})

    assert out["success"] is False
    assert arg in out["error"]
    assert "capture_credentials" in out["error"]
    assert srv.onboarded == [], "the device was touched despite the refusal"
    assert value not in repr(out) if isinstance(value, str) else True


@pytest.mark.asyncio
async def test_an_absent_or_falsey_retired_argument_is_not_a_refusal():
    """Control: a caller passing `force_change: false` — or nothing at all — is
    not opting into anything, and must not be turned away."""
    srv = _Srv()
    out = await ADMZMCPServer._provision_device(
        srv, {"device_id": "cam-1", "force_change": False, "password": ""})
    assert out["success"] is True
    assert srv.onboarded == [("cam-1", False)]


@pytest.mark.asyncio
async def test_neither_host_nor_device_id_is_an_error():
    srv = _Srv()
    out = await ADMZMCPServer._provision_device(srv, {})
    assert out["success"] is False
    assert "host" in out["error"] and "device_id" in out["error"]
    assert srv.onboarded == []


# --- the server no longer owns a way to write a credential ----------------


def test_the_inline_write_helpers_are_gone():
    """Structural, not stylistic. An idle helper on the MCP server whose whole
    job is "store a device credential in the registry" is an invitation for the
    next handler to call it and bypass the gate a second time — which is exactly
    how this tool came to have its own copy of the write.
    """
    assert not hasattr(ADMZMCPServer, "_store_provisioned_creds")
    assert not hasattr(ADMZMCPServer, "_generate_device_password")
    # `_execute_on_host` stays: other handlers (temp credentials, rules) use it.
    assert hasattr(ADMZMCPServer, "_execute_on_host")


def test_the_handler_contains_no_credential_write_of_its_own():
    """Reads the source, because the tests above use a fake `_onboard_device`
    and so cannot see a stray write that happens beside it.

    The **docstring is stripped first**, and that is not a convenience: the
    handler's docstring names the operations it used to perform, in order to
    explain why it no longer performs them. Scanning the whole source made this
    guard fail on its own subject's explanation — the same trap as the capability
    drift scanner, which reads any `ADMZ_`-prefixed token in a comment as an
    environment variable. Stripping the docstring also makes the check sharper
    rather than weaker: real code is what can execute a write, and a write cannot
    hide in a docstring.
    """
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(
        inspect.getsource(ADMZMCPServer._provision_device)))
    fn = tree.body[0]
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)
            and isinstance(fn.body[0].value.value, str)):
        fn.body = fn.body[1:]          # drop the docstring, keep every statement
    code = ast.unparse(fn)

    assert code.strip(), "the docstring strip left nothing to check"
    for forbidden in ("pwdgrp.cgi:add-user", "pwdgrp.cgi:update-user",
                      "_store_provisioned_creds", "_generate_device_password"):
        assert forbidden not in code, (
            f"provision_device performs its own credential write ({forbidden}); "
            "it must delegate to onboard_device_credentials, which is where "
            "ADR-0059's gate lives")
    # ...and it positively DOES delegate — otherwise the absences above are
    # satisfied by a handler that simply does nothing.
    assert "_onboard_device" in code


def test_the_tool_description_says_what_it_now_does():
    from admz.mcp.tools.provision import TOOLS

    tool = next(t for t in TOOLS if t.name == "provision_device")
    schema = getattr(tool, "inputSchema", None) or tool.input_schema

    # the two-account model, and the invariant
    assert "'root' set to the fleet root password" in tool.description
    assert "never stored per device" in tool.description
    assert "gated" in tool.description
    # the retired arguments are gone from the schema, not merely undocumented
    assert set(schema["properties"]) == {"device_id", "host"}
    # and no ordering may put the fleet entry credential before anything
    assert "never written to a device" in tool.description
    assert "Password priority" not in tool.description


# --- onboard_device names the credential that got in -----------------------


def _onboarded(monkeypatch, outcome):
    """The handler's message for one onboarding outcome, no device involved."""
    async def fake_onboard(**kwargs):
        return dict(outcome)

    monkeypatch.setattr("admz.onboarding.onboard_device_credentials", fake_onboard)
    srv = SimpleNamespace(registry=None, catalog=None, executors={})
    return ADMZMCPServer._onboard_device(srv, "cam-1")


@pytest.mark.asyncio
async def test_onboard_device_says_when_the_fleet_root_password_got_in(monkeypatch):
    """Tried first since 2026-09-16 (ADR-0068's amendment), so it is often the
    credential that works — and it is not an entry credential."""
    out = await _onboarded(monkeypatch, {
        "status": "admz_account_created", "device_id": "cam-1", "username": "admz",
        "entry_username": "root", "via_fleet_root": True})
    assert "using the fleet root password" in out["message"]
    assert "entry credential" not in out["message"]


@pytest.mark.asyncio
async def test_onboard_device_still_says_when_an_entry_credential_got_in(monkeypatch):
    out = await _onboarded(monkeypatch, {
        "status": "admz_account_created", "device_id": "cam-1", "username": "admz",
        "entry_username": "u0", "via_fleet_root": False})
    assert "using an entry credential" in out["message"]


def test_onboard_device_tells_the_model_the_order():
    """The model explains onboarding to the operator from this description."""
    import asyncio

    from tests import mcp_harness

    tool = asyncio.run(mcp_harness.find_tool(ADMZMCPServer(), "onboard_device"))
    text = " ".join(tool.description.split())
    assert ("try the fleet root password as 'root' FIRST, then each ENTRY "
            "credential") in text
