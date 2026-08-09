"""The provisioning gate at the decision point (ADR-0059 slice 2).

Provisioning a factory-defaulted device creates a **root admin account on a
real device**. Before this, that was gated at two discovery entry points and
ungated on three others — `register_discovered_device` was held while
`register_device`, reaching the identical write, was not.

The gate now sits at the decision point: inside `onboard_device_credentials`,
immediately before `provision_factory_default`, where `read_systemready` has
just established that the device *is* factory-defaulted. Everything before that
point is a read, so the widget costs an unreachable or already-credentialed
device nothing — they return earlier and are pinned as doing so here.

Pinned:
  - unapproved + needsetup → APPROVAL_REQUIRED, and provisioning NEVER RUNS
  - approved for a provisioning action → provisions, no widget
  - approved for an UNRELATED action → still gates (slice 1's review finding)
  - every non-provisioning path is untouched — the "operators won't notice"
    claim, which is the one most likely to be wrong
  - the envelope carries device id + host, not the device's own metadata
  - the audit rows name the password SOURCE, never the password
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from admz.approval_context import approved
from admz.onboarding import (
    ALREADY_CREDENTIALED,
    APPROVAL_REQUIRED,
    CREDENTIALS_NEEDED,
    PROVISIONED,
    onboard_device_credentials,
)


PASSWORD = "generated-secret-do-not-log"


@pytest.fixture
def registry():
    reg = MagicMock()
    # `get_device_info`, not `get_device` — onboarding calls the former, and a
    # MagicMock's auto-attribute would otherwise put an unserialisable mock
    # into the blocked envelope's payload.
    reg.get_device_info.return_value = {"host": "192.0.2.50",
                                        "device_id": "cam-fresh"}
    reg.get_credentials.return_value = None
    return reg


@pytest.fixture(autouse=True)
def _reachable(monkeypatch):
    """Reachable device, systemready says needsetup=yes — i.e. every test here
    is the factory-default case unless it overrides.

    Patched at the SOURCE modules, matching `test_onboarding.py`'s idiom:
    `onboard_device_credentials` imports these inside the function body, so
    patching `admz.onboarding.<name>` binds nothing. And the suite-wide
    `ADMZ_DISABLE_ONBOARDING_PROBES` must be cleared or onboarding returns
    `credentials_needed` before it ever reaches the gate.
    """
    monkeypatch.delenv("ADMZ_DISABLE_ONBOARDING_PROBES", raising=False)
    monkeypatch.setattr("admz.fleet.health._tcp_probe", AsyncMock(return_value=3))
    monkeypatch.setattr(
        "admz.fleet.systemready.read_systemready",
        AsyncMock(return_value={"needsetup": True}),
    )


@pytest.fixture
def provision_spy(monkeypatch):
    """A spy on the write itself.

    Asserting only on the returned status would pass even if provisioning had
    already happened and the gate fired afterwards — which is the failure that
    matters. This proves the device was never touched.
    """
    spy = AsyncMock(return_value={
        "success": True, "username": "root", "password_source": "generated",
        "password": PASSWORD,
    })
    monkeypatch.setattr("admz.provisioning.provision_factory_default", spy)
    return spy


async def _onboard(registry):
    return await onboard_device_credentials(
        device_id="cam-fresh", registry=registry,
        catalog=MagicMock(), executors={"vapix": MagicMock()},
    )


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


class TestUnapproved:
    @pytest.mark.asyncio
    async def test_returns_approval_required(self, registry, provision_spy):
        out = await _onboard(registry)
        assert out["status"] == APPROVAL_REQUIRED

    @pytest.mark.asyncio
    async def test_the_device_is_never_touched(self, registry, provision_spy):
        await _onboard(registry)
        provision_spy.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_it_carries_the_blocked_envelope(self, registry, provision_spy):
        """The caller must be able to surface an approval link without knowing
        anything about this module."""
        out = await _onboard(registry)
        assert out.get("confirm_token")
        assert out.get("success") is False

    @pytest.mark.asyncio
    async def test_the_envelope_does_not_carry_device_metadata(
        self, registry, provision_spy
    ):
        """Device id + host only. On a factory-defaulted unit the device's own
        advertised metadata is an unauthenticated claim (#193) — it adds
        nothing to "may ADMZ create a root account here?" and would put
        unverified strings on the approval card."""
        registry.get_device_info.return_value = {
            "host": "192.0.2.50",
            "model": "<script>EVIL</script>",
            "serial": "attacker-supplied",
        }
        out = await _onboard(registry)
        blob = repr(out)
        assert "attacker-supplied" not in blob
        assert "EVIL" not in blob


class TestApproved:
    @pytest.mark.asyncio
    async def test_provisions_with_no_widget(self, registry, provision_spy):
        with approved("register_discovered_device", "tok-1"):
            out = await _onboard(registry)
        assert out["status"] == PROVISIONED
        provision_spy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_the_survey_approval_also_covers_it(self, registry, provision_spy):
        with approved("start_demo_survey", "tok-2"):
            out = await _onboard(registry)
        assert out["status"] == PROVISIONED

    @pytest.mark.asyncio
    async def test_an_unrelated_approval_still_gates(self, registry, provision_spy):
        """**Approval for X is not approval for Y.** Slice 1's review found the
        marker was set for every approved action; if the gate asked merely "is
        anything approved?", approving a task deletion would have authorised
        creating a root account here."""
        with approved("delete_task", "tok-3"):
            out = await _onboard(registry)
        assert out["status"] == APPROVAL_REQUIRED
        provision_spy.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_the_password_never_reaches_the_result(
        self, registry, provision_spy
    ):
        with approved("register_discovered_device", "tok-1"):
            out = await _onboard(registry)
        assert PASSWORD not in repr(out)
        assert out.get("password_source") == "generated"


# ---------------------------------------------------------------------------
# The paths that must NOT change — "operators won't notice" is the claim
# most likely to be wrong, so each one gets a test
# ---------------------------------------------------------------------------


class TestUngatedPathsAreUntouched:
    @pytest.mark.asyncio
    async def test_working_stored_credentials(self, registry, provision_spy,
                                              monkeypatch):
        registry.get_credentials.return_value = {"username": "root",
                                                 "password": "works"}
        monkeypatch.setattr(
            "admz.fleet.health._confirm_credentials",
            AsyncMock(return_value=(True, {}, None)),
        )
        out = await _onboard(registry)
        assert out["status"] == ALREADY_CREDENTIALED
        provision_spy.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unreachable_device(self, registry, provision_spy, monkeypatch):
        monkeypatch.setattr("admz.fleet.health._tcp_probe",
                            AsyncMock(return_value=None))
        out = await _onboard(registry)
        assert out["status"] == CREDENTIALS_NEEDED
        provision_spy.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_not_factory_defaulted(self, registry, provision_spy,
                                         monkeypatch):
        """The ordinary device add: systemready says it is already set up, so
        the gate is never reached and the operator sees nothing new."""
        monkeypatch.setattr(
            "admz.fleet.systemready.read_systemready",
            AsyncMock(return_value={"needsetup": False}),
        )
        out = await _onboard(registry)
        assert out["status"] != APPROVAL_REQUIRED
        provision_spy.assert_not_awaited()


# ---------------------------------------------------------------------------
# The approved executor
# ---------------------------------------------------------------------------


class TestApprovedExecutorIsRegistered:
    def test_the_action_exists_and_grants_provisioning(self):
        from admz.operations import (
            _ACTION_EXECUTORS, _PROVISIONING_APPROVAL_ACTIONS)
        assert "provision_device_credentials" in _ACTION_EXECUTORS
        assert "provision_device_credentials" in _PROVISIONING_APPROVAL_ACTIONS

    @pytest.mark.asyncio
    async def test_it_refuses_when_the_address_moved_since_approval(
        self, registry, provision_spy
    ):
        """Found in review. The approval card names a host; mDNS reconcile can
        repoint a device between the widget and the click (#193's subject).
        Re-reading the current host would provision whatever is at the new
        address while the operator believes they approved the old one."""
        from admz.operations import _action_provision_device_credentials

        registry.get_device_info.return_value = {"host": "192.0.2.99"}
        out = await _action_provision_device_credentials(
            {"action": "provision_device_credentials",
             "device_id": "cam-fresh", "host": "192.0.2.50"},
            registry,
        )
        assert out["success"] is False
        assert "changed since approval" in out["error"]
        provision_spy.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_failed_provision_is_not_reported_as_success(
        self, registry, provision_spy, monkeypatch
    ):
        """Also from review: the executor used to return success=True whatever
        onboarding said, so a device that went unreachable between approval
        and execution would report a successful provisioning."""
        from admz import operations

        monkeypatch.setattr(
            "admz.provisioning.provision_factory_default",
            AsyncMock(return_value={"success": False, "error": "vapix said no"}),
        )
        # Patched at the source module: the executor imports `get_context`
        # inside its body, so patching `operations.get_context` binds nothing.
        monkeypatch.setattr(
            "admz.api.context.get_context",
            lambda: MagicMock(catalog=MagicMock(), executors={"vapix": MagicMock()}),
        )
        # Wrapped as production wraps it: `execute_approved_session` enters the
        # approved context before dispatching. See the test below for what
        # happens without it.
        with approved("provision_device_credentials", "tok-x"):
            out = await operations._action_provision_device_credentials(
                {"action": "provision_device_credentials",
                 "device_id": "cam-fresh", "host": "192.0.2.50"},
                registry,
            )
        assert out["success"] is False
        assert out["status"] == "provision_failed"

    @pytest.mark.asyncio
    async def test_the_executor_does_not_self_approve(self, registry,
                                                      provision_spy, monkeypatch):
        """Called outside an approval it gates, rather than provisioning.

        The executor is only ever reached through `execute_approved_session`,
        which establishes the context — but it must not carry its own
        authority, or anything that could invoke it directly would inherit
        provisioning rights. Fail-closed."""
        from admz import operations

        monkeypatch.setattr(
            "admz.api.context.get_context",
            lambda: MagicMock(catalog=MagicMock(), executors={"vapix": MagicMock()}),
        )
        out = await operations._action_provision_device_credentials(
            {"action": "provision_device_credentials",
             "device_id": "cam-fresh", "host": "192.0.2.50"},
            registry,
        )
        assert out["status"] == APPROVAL_REQUIRED
        provision_spy.assert_not_awaited()

    def test_it_does_not_reuse_the_registering_executor(self):
        """`register_discovered_device` calls `registry.add_device`, which
        RAISES on a device that already exists — and this gate fires mostly for
        devices ADMZ has already registered. Reusing it would mean the operator
        approves and gets "Device already exists"."""
        import ast
        import inspect
        from admz.operations import _action_provision_device_credentials

        tree = ast.parse(
            inspect.getsource(_action_provision_device_credentials).strip())
        called = {
            node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        # Parsed, not grepped: this function's own docstring explains why it
        # does NOT call add_device, so a substring check matches its own
        # comment and passes for the wrong reason — the same vacuity trap that
        # bit the #350 label assertions.
        assert "add_device" not in called
