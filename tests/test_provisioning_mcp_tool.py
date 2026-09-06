"""FR-CRED-007 / ADR-0064 slice E at the MCP tool.

`provision_device` carries its own copy of the password ordering — it does
not call `provisioning.provision_factory_default` — so the requirement is
pinned here as well: the fleet `default_password` is never what the tool
writes to a device, on the factory-default path or on the `force_change`
rotation. An explicit `password` is still honoured; nothing secret is in the
result.
"""

from types import SimpleNamespace

import pytest

import admz.mcp.server as server_mod
from admz.discovery.credential_probe import ProbeStatus
from admz.mcp.server import ADMZMCPServer

FLEET = "FleetPass123"
GENERATED = "gen-7fJq2-per-device"


class _Srv:
    """Only the collaborators `_provision_device` touches."""

    def __init__(self):
        self.sent = []
        self.stored = []
        self.registry = SimpleNamespace(
            device_exists=lambda device_id: True,
            get_device_info=lambda device_id: {"host": "1.2.3.4"},
            update_device_info=lambda device_id, updates: None,
            add_device=lambda device_id, info: None,
        )

    async def _execute_on_host(self, host, op, params=None, **kwargs):
        self.sent.append((op, dict(params or {})))
        return True, None

    def _store_provisioned_creds(self, device_id, username, password):
        self.stored.append((device_id, username, password))

    def _generate_device_password(self):
        return GENERATED

    def _serial_to_mac(self, serial):
        return serial


def _probe(status, **overrides):
    fields = dict(status=status, device_info={"serial_number": "ACCC8E000001"},
                  auth=None, detail="", username=None, password=None, auth_method=None)
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _device_answers(monkeypatch, probe):
    async def fake_probe(host):
        return probe

    monkeypatch.setattr(server_mod, "probe_credentials", fake_probe)


@pytest.fixture
def fleet_default_configured(monkeypatch):
    """The setting IS there — and must make no difference to what is written."""
    monkeypatch.setattr("admz.fleet_settings.fleet_settings.get", lambda key: FLEET)


@pytest.mark.asyncio
async def test_a_factory_default_device_gets_a_generated_password(monkeypatch, fleet_default_configured):
    _device_answers(monkeypatch, _probe(ProbeStatus.FACTORY_DEFAULT))
    srv = _Srv()
    out = await ADMZMCPServer._provision_device(srv, {"device_id": "cam-1"})
    assert out["success"] is True and out["status"] == "provisioned"
    assert out["password_source"] == "generated"
    op, params = srv.sent[0]
    assert op == "pwdgrp.cgi:add-user"
    assert params["password"] == GENERATED
    assert srv.stored == [("cam-1", "root", GENERATED)]
    assert FLEET not in repr(out) and GENERATED not in repr(out)


@pytest.mark.asyncio
async def test_an_explicit_password_is_honoured(monkeypatch, fleet_default_configured):
    _device_answers(monkeypatch, _probe(ProbeStatus.FACTORY_DEFAULT))
    srv = _Srv()
    out = await ADMZMCPServer._provision_device(srv, {"device_id": "cam-1", "password": "Chosen-1"})
    assert out["password_source"] == "provided"
    assert srv.sent[0][1]["password"] == "Chosen-1"
    assert srv.stored == [("cam-1", "root", "Chosen-1")]
    assert "Chosen-1" not in repr(out)


@pytest.mark.asyncio
async def test_force_change_rotates_to_a_generated_password(monkeypatch, fleet_default_configured):
    """The legacy `root/pass` rotation is the other write this tool makes, and
    it is not a way to standardise the fleet on the shared secret either."""
    _device_answers(monkeypatch, _probe(ProbeStatus.AUTHENTICATED, username="root",
                                        password="pass", auth_method="digest"))
    srv = _Srv()
    out = await ADMZMCPServer._provision_device(srv, {"device_id": "cam-1", "force_change": True})
    assert out["success"] is True and out["action_taken"] == "changed_password"
    assert out["password_source"] == "generated"
    op, params = srv.sent[0]
    assert op == "pwdgrp.cgi:update-user"
    assert params["password"] == GENERATED
    assert srv.stored[-1] == ("cam-1", "root", GENERATED)
    assert FLEET not in repr(out) and GENERATED not in repr(out)


@pytest.mark.asyncio
async def test_an_empty_password_is_not_a_password(monkeypatch, fleet_default_configured):
    """`password: ""` — a blank field — generates; it neither writes an empty
    password nor falls back to the fleet one."""
    _device_answers(monkeypatch, _probe(ProbeStatus.FACTORY_DEFAULT))
    srv = _Srv()
    out = await ADMZMCPServer._provision_device(srv, {"device_id": "cam-1", "password": ""})
    assert out["password_source"] == "generated"
    assert srv.sent[0][1]["password"] == GENERATED


def test_the_tool_description_says_so():
    import re

    from admz.mcp.tools.provision import TOOLS

    tool = next(t for t in TOOLS if t.name == "provision_device")
    assert "never written to a device" in tool.description
    assert "Password priority" not in tool.description
    assert re.search(r"fleet default_password[^.]*>", tool.description) is None, \
        "no ordering may put the fleet password before generation"
    schema = getattr(tool, "inputSchema", None) or tool.input_schema
    assert "never written to a device" in schema["properties"]["password"]["description"]
