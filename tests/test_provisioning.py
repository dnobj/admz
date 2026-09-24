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
        #: Every params dict sent, in order. ADR-0068 makes provisioning a TWO
        #: write sequence, so `last` alone can no longer see what happened.
        self.sent = []

    async def execute(self, op, device, creds, params):
        self.last = (op, device, creds, params)
        self.sent.append(dict(params))
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


#: ADR-0068's break-glass root password, for the tests below.
BREAK_GLASS = "BreakGlass-Root-7ab3"


def _settings(monkeypatch, **values):
    """Configure fleet settings **by key**, never blind.

    Every test in this class used to patch ``fleet_settings.get`` with a
    key-blind ``lambda k: "FleetPass123"``. Under ADR-0068 that is actively
    dangerous rather than merely sloppy: ``fleet_root_password`` is now a key
    this module reads, so a blind lambda *configures the break-glass password
    to the test's own literal* and the device then legitimately receives it —
    turning "the shared secret never reaches the device" into a tautology that
    passes while being violated. Keys not named here read as unset.
    """
    monkeypatch.setattr("admz.fleet_settings.fleet_settings.get",
                        lambda k: values.get(k))


class TestProvisionFactoryDefault:
    """ADR-0068: root from the break-glass password, then ``admz``, store only
    ``admz``. A root credential is never stored per device."""

    @pytest.mark.asyncio
    async def test_root_then_admz_and_only_admz_is_stored(self, monkeypatch):
        _settings(monkeypatch, fleet_root_password=BREAK_GLASS)
        execr = _Executor()
        reg = _Registry()
        res = await provisioning.provision_factory_default(
            _Catalog(), {"vapix": execr}, reg, device_id="cam-1", host="1.2.3.4",
        )
        assert res["success"] is True
        assert res["root_password_source"] == "fleet_root"
        assert res["password_source"] == "generated"
        # no password of any kind is in the result
        assert "password" not in res
        # TWO accounts were written to the device, root first
        assert [s["username"] for s in execr.sent] == ["root", "admz"]
        assert execr.sent[0]["password"] == BREAK_GLASS
        # ...and ONLY admz is stored
        assert set(reg.accounts) == {("cam-1", "default")}
        acc = reg.accounts[("cam-1", "default")]
        assert acc["username"] == "admz" and acc["account_type"] == "admin"
        assert acc["password"] == execr.sent[1]["password"] != BREAK_GLASS
        assert acc["generated_by_admz"] is True
        assert ("cam-1", {"auth_method": "digest"}) in reg.info_updates

    @pytest.mark.asyncio
    async def test_the_break_glass_password_is_stored_nowhere(self, monkeypatch):
        """The invariant, asserted as an absence across every stored row."""
        _settings(monkeypatch, fleet_root_password=BREAK_GLASS)
        execr = _Executor()
        reg = _Registry()
        res = await provisioning.provision_factory_default(
            _Catalog(), {"vapix": execr}, reg, device_id="cam-1", host="1.2.3.4",
        )
        assert BREAK_GLASS not in repr(res)
        assert BREAK_GLASS not in repr(reg.accounts)
        assert not any(a.get("username") == "root" for a in reg.accounts.values())

    @pytest.mark.asyncio
    async def test_a_configured_fleet_default_is_not_written(self, monkeypatch):
        """FR-CRED-007 (ADR-0064 slice E) still holds, and is now the sharper
        claim: the *entry* credential is never written even though a different
        fleet setting legitimately is. `default_password` and
        `fleet_root_password` are different keys and only one reaches a device."""
        _settings(monkeypatch, default_password="FleetPass123",
                  fleet_root_password=BREAK_GLASS)
        execr = _Executor()
        reg = _Registry()
        res = await provisioning.provision_factory_default(
            _Catalog(), {"vapix": execr}, reg, device_id="cam-1", host="1.2.3.4",
        )
        assert res["success"] is True
        assert all(s["password"] != "FleetPass123" for s in execr.sent)
        assert "FleetPass123" not in repr(reg.accounts)
        assert "FleetPass123" not in repr(res)

    @pytest.mark.asyncio
    async def test_no_break_glass_configured_writes_nothing_at_all(self, monkeypatch):
        """ADR-0068 decision 8. The alternatives were storing root (forbidden)
        or generating-and-discarding it (a device nobody can ever log into), so
        refusing is the only consistent answer — and it must not touch the
        device on the way out."""
        _settings(monkeypatch, default_password="FleetPass123")
        execr = _Executor()
        reg = _Registry()
        res = await provisioning.provision_factory_default(
            _Catalog(), {"vapix": execr}, reg, device_id="cam-1", host="1.2.3.4",
        )
        assert res["success"] is False
        assert res["status"] == "root_password_not_configured"
        assert execr.sent == [], "the device was contacted despite the refusal"
        assert reg.accounts == {}
        # the entry credential is NOT a fallback for the missing root password
        assert "FleetPass123" not in repr(res)

    @pytest.mark.asyncio
    async def test_the_unattended_handler_is_refused(self, monkeypatch):
        """ADR-0068's required mitigation, at the function boundary."""
        _settings(monkeypatch, fleet_root_password=BREAK_GLASS)
        execr = _Executor()
        reg = _Registry()
        res = await provisioning.provision_factory_default(
            _Catalog(), {"vapix": execr}, reg, device_id="cam-1", host="1.2.3.4",
            attended=False,
        )
        assert res["success"] is False
        assert res["status"] == "unattended_not_permitted"
        assert execr.sent == [] and reg.accounts == {}

    @pytest.mark.asyncio
    async def test_an_explicit_password_is_still_honoured(self, monkeypatch):
        """A caller with its own root password overrides the setting — and it is
        still not stored."""
        _settings(monkeypatch, fleet_root_password=BREAK_GLASS)
        execr = _Executor()
        reg = _Registry()
        res = await provisioning.provision_factory_default(
            _Catalog(), {"vapix": execr}, reg, device_id="cam-1", host="1.2.3.4",
            password="Chosen-1",
        )
        assert res["root_password_source"] == "provided"
        assert execr.sent[0]["password"] == "Chosen-1"
        assert "Chosen-1" not in repr(reg.accounts)
        assert "Chosen-1" not in repr(res)

    @pytest.mark.asyncio
    async def test_a_failed_root_write_stores_nothing(self, monkeypatch):
        _settings(monkeypatch, fleet_root_password=BREAK_GLASS)
        execr = _Executor(result=_Result(success=False, status_code=500, error="boom"))
        reg = _Registry()
        res = await provisioning.provision_factory_default(
            _Catalog(), {"vapix": execr}, reg, device_id="cam-1", host="1.2.3.4",
        )
        assert res["success"] is False
        assert res["error"] == "boom" and res["stage"] == "root"
        # no creds stored when the device didn't accept the user
        assert reg.accounts == {}

    @pytest.mark.asyncio
    async def test_root_set_but_admz_failed_stores_nothing(self, monkeypatch):
        """ADR-0068 decision 4, the cell that matters most: the device now has a
        root password the operator knows, and ADMZ keeps NOTHING. Storing the
        break-glass value per device to paper over this is the one thing the
        invariant forbids."""
        _settings(monkeypatch, fleet_root_password=BREAK_GLASS)

        class _FailSecond(_Executor):
            async def execute(self, op, device, creds, params):
                self.sent.append(dict(params))
                self.last = (op, device, creds, params)
                if params.get("username") == "admz":
                    return _Result(success=False, error="device said no")
                return _Result()

        execr = _FailSecond()
        reg = _Registry()
        res = await provisioning.provision_factory_default(
            _Catalog(), {"vapix": execr}, reg, device_id="cam-1", host="1.2.3.4",
        )
        assert res["success"] is False
        assert res["status"] == "admz_account_failed"
        assert res["root_set"] is True
        assert reg.accounts == {}, "nothing may be stored for the device"
        assert BREAK_GLASS not in repr(res)


class TestReprovisionHandler:
    """A queued recovery that fires raises a ``setup`` notice and never
    provisions (ADR-0068; changed 2026-09-23).

    Provisioning writes the fleet root password, and this handler fires
    unattended against whatever answers at the device's address hours after
    the approval (#185/#326). From ADR-0068 until 2026-09-23 it called
    ``provision_factory_default(attended=False)``, which refused, so every fired
    task failed while the chat still promised a re-provision. It now hands the
    moment to a person: a Console notice that leads to an attended onboarding.
    """

    @staticmethod
    def _live_setup(device_id):
        from admz.notices.producers import setup_subject
        from admz.notices.store import notices_store
        return notices_store.get_live(setup_subject(device_id))

    @pytest.mark.asyncio
    async def test_it_raises_a_setup_notice_and_never_provisions(self, monkeypatch):
        from admz.tasks.handlers import execute_task_action
        from admz.tasks.store import Task

        async def must_not_run(*a, **k):
            raise AssertionError("the unattended handler reached provisioning")

        monkeypatch.setattr(
            "admz.provisioning.provision_factory_default", must_not_run)

        out = await execute_task_action(Task(
            id="t-setup-1", device_id="cam-setup-1", action_type="reprovision"))

        assert out["success"] is True
        notice = self._live_setup("cam-setup-1")
        assert notice is not None and out["notice_id"] == notice.id
        assert (notice.kind, notice.task_id) == ("setup", "t-setup-1")

    @pytest.mark.asyncio
    async def test_a_second_firing_bumps_the_same_notice(self):
        from admz.tasks.handlers import execute_task_action
        from admz.tasks.store import Task

        first = await execute_task_action(Task(
            id="t-a", device_id="cam-setup-2", action_type="reprovision"))
        second = await execute_task_action(Task(
            id="t-b", device_id="cam-setup-2", action_type="reprovision"))
        assert first["notice_id"] == second["notice_id"]
        assert self._live_setup("cam-setup-2").occurrences == 2

    @pytest.mark.asyncio
    async def test_a_notice_store_failure_is_reported(self, monkeypatch):
        """#455: a handler that cannot do its job says so, rather than
        reporting a success the task row would then show as done."""
        from admz.tasks.handlers import execute_task_action
        from admz.tasks.store import Task

        def broken(*a, **k):
            raise RuntimeError("no such table")

        monkeypatch.setattr("admz.notices.producers.setup_notice", broken)
        out = await execute_task_action(Task(
            id="t-c", device_id="cam-setup-3", action_type="reprovision"))
        assert out["success"] is False
        assert "notice not raised" in out["error"]

    @pytest.mark.asyncio
    async def test_unattended_reprovision_never_sends_a_SHARED_secret(
        self, monkeypatch
    ):
        """GH #185/#326, end to end through the real wiring and the REAL
        provision_factory_default (not mocked): with a fleet root password
        configured, nothing leaves the process for the device — the queued
        recovery raises a notice and touches nothing.

        Deliberately an outcome test, not an implementation test. If a future
        change routes this handler back into provisioning, this goes red on the
        fact that matters: a fleet-wide credential bound for an address ADMZ
        cannot verify.
        """
        from admz.fleet.pending_actions import execute_pending_action
        from admz.recovery_actions import register_recovery_handlers

        BREAK_GLASS_SECRET = "FLEET-WIDE-BREAK-GLASS-9f3a1c"
        _settings(monkeypatch, fleet_root_password=BREAK_GLASS_SECRET,
                  default_password="FLEET-ENTRY-PAIR-1234")
        execr = _Executor()
        reg = _Registry()

        class _Ctx:
            registry = reg
            catalog = _Catalog()
            executors = {"vapix": execr}

        register_recovery_handlers(_Ctx())
        await execute_pending_action({"action": "reprovision"}, "cam-setup-4")

        assert execr.sent == [], (
            "the unattended recovery contacted the device; under ADR-0068 the "
            "next thing it would send is the fleet-wide root password "
            "(GH #185/#326)")
        assert BREAK_GLASS_SECRET not in repr(execr.sent)
        assert reg.accounts == {}
        assert self._live_setup("cam-setup-4") is not None

    @pytest.mark.asyncio
    async def test_onboarding_closes_the_notice(self):
        """The notice asks for an onboarding; a successful one answers it."""
        from admz.notices.producers import RESOLUTION_ONBOARDED, setup_notice
        from admz.notices.store import notices_store
        from admz.onboarding import PROVISIONED, _with_survey

        notice = setup_notice("cam-setup-5")
        _with_survey({"status": PROVISIONED, "device_id": "cam-setup-5"})

        assert self._live_setup("cam-setup-5") is None
        closed = notices_store.get(notice.id)
        assert (closed.status, closed.resolution) == ("handled", RESOLUTION_ONBOARDED)

    @pytest.mark.asyncio
    async def test_a_gated_or_failed_onboarding_leaves_it_open(self):
        """Control: only a success exit closes it."""
        from admz.notices.producers import setup_notice
        from admz.onboarding import APPROVAL_REQUIRED, _with_survey

        setup_notice("cam-setup-6")
        _with_survey({"status": APPROVAL_REQUIRED, "device_id": "cam-setup-6"})
        assert self._live_setup("cam-setup-6") is not None


class TestAdoptWithAdmzAccount:
    """ADR-0061 / FR-CRED-011: use a working entry credential to create ADMZ's
    own per-device account. The entry credential gets ADMZ in; this is what
    keeps it in."""

    @pytest.mark.asyncio
    async def test_creates_admz_with_a_generated_password_and_stores_it(self):
        execr = _Executor()
        reg = _Registry()
        entry = {"username": "root", "password": "entry-secret"}
        res = await provisioning.adopt_with_admz_account(
            _Catalog(), {"vapix": execr}, reg,
            device_id="cam-1", host="1.2.3.4", entry=entry,
        )
        assert res["success"] is True
        assert res["status"] == "admz_account_created"
        assert res["username"] == "admz"
        # the generated password is NEVER in the result
        assert "password" not in res
        acc = reg.accounts[("cam-1", "default")]
        assert acc["username"] == "admz"
        assert acc["password"] and acc["password"] != "entry-secret", (
            "ADMZ must store its OWN generated password, not the entry credential"
        )
        assert "ADR-0061" in acc["purpose"]

    @pytest.mark.asyncio
    async def test_authenticates_AS_the_entry_credential(self):
        """The one way this differs from provision_factory_default: that writes
        to a device with no account (auth none); this writes to a device that
        already has an owner, as that owner."""
        execr = _Executor()
        entry = {"username": "root", "password": "entry-secret"}
        await provisioning.adopt_with_admz_account(
            _Catalog(), {"vapix": execr}, _Registry(),
            device_id="cam-1", host="1.2.3.4", entry=entry,
        )
        op, device, creds, params = execr.last
        assert creds == entry
        assert params["username"] == "admz" and params["group"] == "root"

    @pytest.mark.asyncio
    async def test_the_written_password_is_the_stored_password(self):
        """Control: what went to the device is what ADMZ kept."""
        execr = _Executor()
        reg = _Registry()
        await provisioning.adopt_with_admz_account(
            _Catalog(), {"vapix": execr}, reg,
            device_id="cam-1", host="1.2.3.4",
            entry={"username": "root", "password": "x"},
        )
        assert execr.last[3]["password"] == reg.accounts[("cam-1", "default")]["password"]

    @pytest.mark.asyncio
    async def test_a_failed_write_stores_nothing_and_says_so(self):
        """The caller falls back to the entry credential; this must not have
        half-stored an account for a device that never got one."""
        execr = _Executor(result=_Result(success=False, error="device said no"))
        reg = _Registry()
        res = await provisioning.adopt_with_admz_account(
            _Catalog(), {"vapix": execr}, reg,
            device_id="cam-1", host="1.2.3.4",
            entry={"username": "root", "password": "x"},
        )
        assert res["success"] is False
        assert res["status"] == "admz_account_failed"
        assert "device said no" in res["error"]
        assert ("cam-1", "default") not in reg.accounts

    @pytest.mark.asyncio
    async def test_reaches_the_device_the_way_the_probe_did(self):
        """A device the probe found HTTPS-only+Basic must be written to that way,
        or the account write guesses again and fails on a device the same
        credential just read (the A1210, 2026-08-17)."""
        execr = _Executor()
        info = {"auth_method": "basic", "auth": {"scheme": "https", "https": "basic"}}
        await provisioning.adopt_with_admz_account(
            _Catalog(), {"vapix": execr}, _Registry(),
            device_id="cam-1", host="1.2.3.4",
            entry={"username": "root", "password": "x"}, device_info=info,
        )
        op, device, creds, params = execr.last
        assert device.get("auth_method") == "basic"
        assert (device.get("auth") or {}).get("scheme") == "https"


def test_no_caller_hands_an_entry_credential_to_a_device_write():
    """FR-CRED-007: an ENTRY credential is never written to a device.

    Re-scoped by ADR-0068, and the re-scope matters more than the original.
    This guard keyed on ``allow_fleet_default``, a kwarg that no longer exists —
    so it had become **vacuous**: ``offenders == []`` was trivially true and the
    check silently stopped covering anything. Three changes fix that:

    1. ``fleet_settings`` is dropped as a needle. It was a proxy for "reads a
       fleet setting", and that proxy dies the moment a *different* fleet
       setting is legitimately written — which is exactly what
       ``fleet_root_password`` now is. The needles name the **entry**
       credential specifically instead.
    2. The callee set follows the WRITE rather than one function name, so
       ``write_root_account`` and ``adopt_with_admz_account`` are covered too.
    3. :func:`test_provisioning_reads_exactly_one_fleet_setting` below adds the
       positive half. Without it, resolving a value *inside*
       ``provision_factory_default`` would dodge this check entirely — quieter
       than failing, and therefore worse.
    """
    import ast
    import pathlib

    import admz

    ENTRY_NEEDLES = ("default_password", "LEGACY_PASS_KEY",
                     "entry_credentials", "SETTING_KEY")
    DEVICE_WRITERS = ("provision_factory_default", "write_root_account",
                      "adopt_with_admz_account")

    def _mentions(node, needles):
        for sub in ast.walk(node):
            text = getattr(sub, "id", None) or getattr(sub, "attr", None)
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                text = sub.value
            if text and any(n in text for n in needles):
                return True
        return False

    root = pathlib.Path(admz.__file__).parent
    offenders = []
    for f in sorted(root.rglob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = getattr(node.func, "attr", None) or getattr(node.func, "id", None) or ""
            if callee not in DEVICE_WRITERS:
                continue
            for kw in node.keywords:
                if kw.arg in ("password", "entry") and _mentions(kw.value, ENTRY_NEEDLES):
                    offenders.append(
                        f"{f.relative_to(root)}:{node.lineno} {kw.arg}")
    # what this cannot see: **kwargs forwarding and a re-implemented write
    # (the MCP tool is one — pinned by tests/test_provisioning_mcp_tool.py)
    assert offenders == []


def test_provisioning_reads_exactly_one_fleet_setting():
    """The positive half of the guard above (ADR-0068).

    ``admz/provisioning.py`` writes passwords to devices, so *which* fleet
    setting it may read is a security property, not a detail. It is exactly
    ``fleet_root_password`` — the break-glass root value. If
    ``default_password`` ever reappears here, the entry credential is one line
    away from a device write again, and the negative guard above cannot see it
    because the read would be internal rather than a kwarg at a call site.
    """
    import ast
    import pathlib

    from admz import provisioning

    src = pathlib.Path(provisioning.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    consts = {
        t.id: n.value.value
        for n in tree.body if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and isinstance(n.value, ast.Constant)
        and isinstance(n.value.value, str)
    }
    keys = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and getattr(node.func, "attr", None) in ("get", "set")
                and getattr(getattr(node.func, "value", None), "id", None) == "fleet_settings"
                and node.args):
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                keys.add(arg.value)
            elif isinstance(arg, ast.Name):
                keys.add(consts.get(arg.id, f"<unresolved {arg.id}>"))

    assert keys == {"fleet_root_password"}, (
        f"admz/provisioning.py reads fleet settings {sorted(keys)}; it may read "
        "exactly {'fleet_root_password'}. The fleet default_password is an "
        "ENTRY credential and must never be written to a device (FR-CRED-007).")


def test_the_break_glass_key_is_encrypted_at_rest_and_never_llm_writable():
    """Asserted by MEMBERSHIP, not only through the parametrized round-trip.

    ``tests/test_setting_encryption.py`` parametrizes over
    ``STORE_ENCRYPTED_SETTING_KEYS``, so it cannot fail for a key that was never
    added to the set — this repo's named vacuity trap. This says the key is in
    there, out loud.
    """
    from admz.setting_policy import (
        LLM_WRITABLE_SETTING_KEYS,
        STORE_ENCRYPTED_SETTING_KEYS,
        is_llm_writable,
    )
    from admz.provisioning import FLEET_ROOT_PASSWORD_KEY

    assert FLEET_ROOT_PASSWORD_KEY in STORE_ENCRYPTED_SETTING_KEYS
    assert FLEET_ROOT_PASSWORD_KEY not in LLM_WRITABLE_SETTING_KEYS
    assert is_llm_writable(FLEET_ROOT_PASSWORD_KEY) is False, (
        "the model must not be able to set the credential that unlocks every "
        "device ADMZ has provisioned")
    # and the name alone is enough for masking / reveal-gating (FR-SEC-007)
    from admz.redact import is_sensitive_key
    assert is_sensitive_key(FLEET_ROOT_PASSWORD_KEY) is True
