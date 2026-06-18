"""Tests for the shared provisioning primitives + the deferred reprovision handler."""

from __future__ import annotations

import pytest

from admz import provisioning


class _Op:
    id = "pwdgrp.cgi:add-user"
    cgi = ""
    method = "GET"
    risk_level = "dangerous"
    request: dict = {}
    response: dict = {}
    requires: dict = {}
    endpoint = ""
    generation = "legacy-cgi"
    auth: dict = {}
    service_impact = ""
    base_path = ""
    path = ""


class _Catalog:
    def get_operation(self, family, op_id):
        return _Op()


class _Result:
    def __init__(self, success=True, status_code=200, error=None):
        self.success = success
        self.status_code = status_code
        self.error = error


class _Executor:
    def __init__(self, result=None):
        self._result = result or _Result()
        self.last = None

    async def execute(self, op, device, creds, params):
        self.last = (op, device, creds, params)
        return self._result


class _Registry:
    def __init__(self):
        self.accounts = {}
        self.info_updates = []

    def account_exists(self, did, aid):
        return (did, aid) in self.accounts

    def remove_account(self, did, aid):
        self.accounts.pop((did, aid), None)

    def add_account(self, did, aid, data):
        self.accounts[(did, aid)] = data

    def update_device_info(self, did, updates):
        self.info_updates.append((did, updates))

    def get_device_info(self, did):
        return {"host": "1.2.3.4"}


class TestProvisionFactoryDefault:
    @pytest.mark.asyncio
    async def test_success_stores_creds_no_leak(self, monkeypatch):
        monkeypatch.setattr("admz.fleet_settings.fleet_settings.get", lambda k: None)  # generated pw
        execr = _Executor()
        reg = _Registry()
        res = await provisioning.provision_factory_default(
            _Catalog(), {"vapix": execr}, reg, device_id="cam-1", host="1.2.3.4",
        )
        assert res["success"] is True
        assert res["password_source"] == "generated"
        # password is NEVER in the result
        assert "password" not in res
        # creds stored as the admin 'default' account
        acc = reg.accounts[("cam-1", "default")]
        assert acc["username"] == "root" and acc["account_type"] == "admin"
        assert acc["password"]  # a real password was set
        # the add-user op ran with that password; device marked digest-authed
        assert execr.last[3]["password"] == acc["password"]
        assert ("cam-1", {"auth_method": "digest"}) in reg.info_updates

    @pytest.mark.asyncio
    async def test_uses_fleet_default_password(self, monkeypatch):
        monkeypatch.setattr("admz.fleet_settings.fleet_settings.get", lambda k: "FleetPass123")
        execr = _Executor()
        reg = _Registry()
        res = await provisioning.provision_factory_default(
            _Catalog(), {"vapix": execr}, reg, device_id="cam-1", host="1.2.3.4",
        )
        assert res["password_source"] == "fleet_default"
        assert reg.accounts[("cam-1", "default")]["password"] == "FleetPass123"

    @pytest.mark.asyncio
    async def test_vapix_failure_returns_error_no_creds(self, monkeypatch):
        monkeypatch.setattr("admz.fleet_settings.fleet_settings.get", lambda k: None)
        execr = _Executor(result=_Result(success=False, status_code=500, error="boom"))
        reg = _Registry()
        res = await provisioning.provision_factory_default(
            _Catalog(), {"vapix": execr}, reg, device_id="cam-1", host="1.2.3.4",
        )
        assert res["success"] is False
        assert res["error"] == "boom"
        # no creds stored when the device didn't accept the user
        assert reg.accounts == {}


class TestReprovisionHandler:
    @pytest.mark.asyncio
    async def test_handler_provisions(self, monkeypatch):
        from admz.fleet.pending_actions import execute_pending_action
        from admz.recovery_actions import register_recovery_handlers

        monkeypatch.setattr("admz.fleet.pending_actions._HANDLERS", {})
        called = {}

        async def fake_provision(catalog, executors, registry, *, device_id, host, username="root"):
            called["args"] = (device_id, host, username)
            return {"success": True}

        monkeypatch.setattr(
            "admz.provisioning.provision_factory_default", fake_provision
        )

        class _Ctx:
            registry = _Registry()
            catalog = object()
            executors = {}

        register_recovery_handlers(_Ctx())
        await execute_pending_action({"action": "reprovision"}, "cam-1")
        assert called["args"] == ("cam-1", "1.2.3.4", "root")

    @pytest.mark.asyncio
    async def test_handler_raises_on_provision_failure(self, monkeypatch):
        from admz.fleet.pending_actions import execute_pending_action
        from admz.recovery_actions import register_recovery_handlers

        monkeypatch.setattr("admz.fleet.pending_actions._HANDLERS", {})

        async def fake_provision(*a, **k):
            return {"success": False, "error": "device rejected user"}

        monkeypatch.setattr(
            "admz.provisioning.provision_factory_default", fake_provision
        )

        class _Ctx:
            registry = _Registry()
            catalog = object()
            executors = {}

        register_recovery_handlers(_Ctx())
        with pytest.raises(RuntimeError):
            await execute_pending_action({"action": "reprovision"}, "cam-1")
