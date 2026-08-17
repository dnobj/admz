"""Discovery-driven provisioning is held for the approval widget (#199).

A survey that registers what it finds also **provisions** what it finds:
``onboard_device_credentials`` sends a factory-defaulted unit through
``provision_factory_default`` — ``pwdgrp.cgi:add-user``, ``group=root``,
``auth_method="none"``. Until this, one REST call or two MCP tool calls could
scan an operator-named subnet and create an admin account on every unclaimed
device on it, with nothing in the way.

The gate is at the **two discovery-driven entry points**, not on
``provision_factory_default``, because three callers reach that step
legitimately and must not be held —
``tasks/handlers.py::_run_reprovision`` (a *scheduled* task nothing can approve
on behalf of), the REST single-device onboard, and MCP ``_register_device``.
``TestTheLegitimateCallersAreUntouched`` is the test of that claim, and it is
the reason this design was chosen over the tidier-sounding one.

**Vacuity note.** "the call is blocked" is trivially green if everything is
blocked, so `TestAPermittedOperationIsUnaffected` pins what must still go
through un-gated: a ``fast`` run, a ``register_new=False`` sweep (it scans and
reads, it writes to no device), and the three legitimate provisioning callers.
And "the gate exists" says nothing about whether approval *works*, so
`TestApprovalActuallyRuns` drives the approved path to the real core.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, __import__("os").path.dirname(__file__))

from test_demo_inference_runs import (  # noqa: E402,F401
    client, ctx, isolate_admz_dirs,
)

SURVEY = {"mode": "survey"}


# ── the gate fires ───────────────────────────────────────────────────────────
class TestTheSurveyIsGated:
    def test_an_unapproved_survey_is_blocked_not_started(self, client, ctx):
        """THE defect: this returned `started: True` and began writing."""
        body = client.post("/api/demos/inference/runs", json=SURVEY).json()
        assert body["blocked"] is True, "a provisioning survey started unapproved"
        assert body["success"] is False
        assert body.get("started") is not True
        assert body["confirm_token"]
        # And nothing was started.
        assert ctx.inference_run_store.running(mode="survey") == []

    def test_it_is_service_affecting_at_url_only_by_default(self, client, ctx):
        """The operator's decision: the normal risk row, not a new tier and not
        `url_and_password`. `url_only` is already what `service-affecting` maps
        to, so this joins the table rather than extending it."""
        body = client.post("/api/demos/inference/runs", json=SURVEY).json()
        assert body["risk_level"] == "service-affecting"
        assert body["confirmation_level"] == "url_only"

    def test_the_card_names_the_blast_radius(self, client, ctx):
        """A named CIDR and an auto-detected sweep are the same click
        otherwise, and the subnet is the whole risk."""
        body = client.post("/api/demos/inference/runs",
                           json={**SURVEY, "subnet": "10.20.0.0/24"}).json()
        assert "10.20.0.0/24" in body["reason"]

    def test_the_card_names_EVERY_write_the_one_approval_authorises(self, client, ctx):
        """This approval is in onboarding._APPROVAL_ACTIONS, so no branch will
        prompt again. It therefore has to say up front everything it covers
        (ADR-0061, #411): a fresh root account on a factory-defaulted device
        AND ADMZ's own 'admz' account on one an entry credential opens.

        The first draft named only the factory-default write. The operator
        would have approved admz-account creation without the card ever
        mentioning it."""
        body = client.post("/api/demos/inference/runs",
                           json={**SURVEY, "subnet": "10.20.0.0/24"}).json()
        reason = body["reason"].lower()
        assert "factory-defaulted" in reason
        assert "admz" in reason and "entry credential" in reason
        # and it says the entry credential survives — that is ADR-0061's rule
        assert "left in place" in reason

    def test_an_auto_detected_sweep_says_so_rather_than_inventing_a_cidr(
            self, client, ctx):
        body = client.post("/api/demos/inference/runs", json=SURVEY).json()
        assert "auto-detected" in body["reason"]

    def test_the_console_operator_is_gated_too(self, client, ctx):
        """Deliberately NOT `demos/gated.py`'s policy. There the operator edits
        their own fleet metadata; here the decision names the authenticated user
        as part of the threat, so copying `is_interactive` would have left the
        REST survey — the louder path — exactly as it was.

        The test client is an authenticated console principal, so every other
        test in this class already relies on this; asserted once explicitly so
        the intent is not mistaken for an oversight."""
        from admz.discovery import gated
        assert not hasattr(gated, "is_interactive"), (
            "an interactive exemption was added; that reopens the REST path")
        assert client.post("/api/demos/inference/runs",
                           json=SURVEY).json()["blocked"] is True


class TestTheMcpEntryGateWasRetired:
    """ADR-0059 slice 3 removed this gate, and that is the intended change.

    #199 added it as the second discovery-driven path into provisioning.
    Provisioning is now gated at the decision point inside
    `onboard_device_credentials`, so the root-account creation is still held —
    by a widget that names the actual device and fires only when the device
    really is factory-defaulted.

    What remained here was a gate on the REGISTRY WRITE, justified by "the
    model discovered this device rather than a human naming it". That does not
    survive: `register_device` performs the same `registry.add_device` with no
    gate, one tool call away, and ADR-0059's own argument is that the
    distinction is unenforceable for an autonomous caller. A gate one tool call
    from an ungated equivalent is false assurance.
    """

    def test_it_registers_without_an_entry_widget(self, monkeypatch):
        import asyncio

        from admz.mcp.server import ADMZMCPServer

        added = []
        srv = ADMZMCPServer.__new__(ADMZMCPServer)
        srv.registry = NS(add_device=lambda did, info: added.append(did))
        srv.catalog = None
        srv.executors = {}

        async def _onboard(**kwargs):
            return {"status": "credentials_needed", "device_id": kwargs["device_id"]}

        monkeypatch.setattr("admz.onboarding.onboard_device_credentials", _onboard)
        out = asyncio.run(
            srv._register_discovered_device(
                {"device_id": "AABBCCDDEE01", "ip_address": "10.20.0.9"}))

        assert out["success"] is True
        assert added == ["AABBCCDDEE01"]
        assert not out.get("blocked")

    def test_but_provisioning_still_gates_downstream(self, monkeypatch):
        """The protection that actually matters is unchanged — it just moved.
        A factory-defaulted device still cannot get a root account without an
        approval, and now the widget names that device."""
        import asyncio

        from admz.mcp.server import ADMZMCPServer

        srv = ADMZMCPServer.__new__(ADMZMCPServer)
        srv.registry = NS(add_device=lambda did, info: None)
        srv.catalog = None
        srv.executors = {}

        async def _onboard(**kwargs):
            # What the real chokepoint returns for an unapproved factory-default.
            return {"status": "approval_required", "blocked": True,
                    "device_id": kwargs["device_id"]}

        monkeypatch.setattr("admz.onboarding.onboard_device_credentials", _onboard)
        out = asyncio.run(
            srv._register_discovered_device(
                {"device_id": "AABBCCDDEE01", "ip_address": "10.20.0.9"}))

        assert out["onboarding"]["status"] == "approval_required"


class TestTheSurveyGateRemains:
    def test_the_survey_is_the_one_remaining_entry_gate(self):
        """#255's shape is two implementations of one predicate drifting. After
        slice 3 there is one entry gate, not two, and the survey is it."""
        import ast
        import pathlib

        callers = []
        for path in ("admz/api/routes/demos.py", "admz/mcp/server.py"):
            tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
            for n in ast.walk(tree):
                if isinstance(n, ast.Call) and getattr(
                        n.func, "id", None) == "gate_scan_write":
                    callers.append(path)
        assert sorted(callers) == ["admz/api/routes/demos.py"], (
            "the MCP entry gate was retired in ADR-0059 slice 3; a new "
            "gate_scan_write caller needs its own justification")

        # And neither entry point hand-rolls its own session beside the shared
        # gate. Scoped to these two functions on purpose: six other ADR-0034
        # actions in server.py call `create_action_session` directly and are
        # none of this change's business.
        import inspect

        from admz.api.routes.demos import start_inference_run
        src = inspect.getsource(start_inference_run)
        assert "gate_scan_write" in src
        assert "create_action_session" not in src, (
            "start_inference_run builds its own session instead of using "
            "the one shared gate")

        # The MCP path no longer gates at entry (slice 3) — it must also not
        # have grown a hand-rolled replacement.
        from admz.mcp.server import ADMZMCPServer
        mcp_src = inspect.getsource(ADMZMCPServer._register_discovered_device)
        assert "create_action_session" not in mcp_src


# ── what must still work ─────────────────────────────────────────────────────
class TestAPermittedOperationIsUnaffected:
    def test_a_fast_run_is_not_gated(self, client, ctx):
        """FIRST. `fast` reads the registry and the last snapshots and touches
        no device. If this were blocked the gate would be indiscriminate and
        every assertion above would be worthless."""
        body = client.post("/api/demos/inference/runs",
                           json={"mode": "fast"}).json()
        assert body.get("blocked") is not True
        assert body["success"] is True and "run" in body

    def test_a_read_only_sweep_is_not_gated(self, client, ctx, monkeypatch):
        """`register_new=False` is the documented opt-out: it registers nothing
        and therefore provisions nothing. Gating it would be friction with no
        risk reduction — the scan itself is #199's *other*, still-open half."""
        from admz.demos.inference import collect
        monkeypatch.setattr(collect, "run_survey",
                            lambda *a, **k: _noop_coro())
        body = client.post("/api/demos/inference/runs",
                           json={"mode": "survey", "register_new": False}).json()
        assert body.get("blocked") is not True
        assert body["started"] is True

    def test_the_already_running_409_still_precedes_the_gate(self, client, ctx):
        """Approving a survey that is only going to 409 wastes the click."""
        ctx.inference_run_store.start(mode="survey")
        res = client.post("/api/demos/inference/runs", json=SURVEY)
        assert res.status_code == 409 and "already running" in res.json()["detail"]


async def _noop_coro():
    return None


class TestTheLegitimateCallersAreUntouched:
    """The measured claim behind gating the entry points rather than the
    provisioning step. If any of these became gated, the design is wrong."""

    def test_the_scheduled_reprovision_task_reaches_provisioning_directly(self):
        """The decisive one. Nothing can approve a widget on the scheduler's
        behalf, so a gate here would not delay the write — it would fail it."""
        import inspect

        from admz.tasks import handlers
        src = inspect.getsource(handlers._run_reprovision)
        assert "provision_factory_default" in src
        assert "gate_scan_write" not in src and "blocked" not in src

    def test_the_rest_single_device_onboard_is_ungated(self):
        """The operator typed this device's address; intent is explicit and
        singular, and the device set was not chosen by a scan."""
        import inspect

        from admz.api.routes import devices
        src = inspect.getsource(devices._run_onboarding)
        assert "onboard_device_credentials" in src
        assert "gate_scan_write" not in src

    def test_the_mcp_register_device_tool_is_ungated(self):
        """Same shape as the REST route — one named device, not a sweep."""
        import inspect

        from admz.mcp.server import ADMZMCPServer
        src = inspect.getsource(ADMZMCPServer._register_device)
        assert "gate_scan_write" not in src

    def test_provision_factory_default_itself_carries_no_gate(self):
        """States the design in one assertion: the gate is at the entry points.
        If someone later moves it down here, the three callers above break and
        this test says why."""
        import inspect

        from admz import provisioning
        src = inspect.getsource(provisioning.provision_factory_default)
        assert "create_action_session" not in src and "blocked" not in src


# ── the level is the operator's to choose ────────────────────────────────────
class TestTheLevelIsConfigurable:
    def _level(self, **kw):
        from admz import operations
        return operations.create_action_session(
            action="start_demo_survey", device_id="fleet", payload={},
            reason="r", **kw).confirmation_level

    def test_it_defaults_to_url_only(self, isolate_admz_dirs):
        assert self._level(operator_configurable=True) == "url_only"

    def test_an_operator_can_raise_it(self, isolate_admz_dirs):
        """Now meaningful: the confirmation password is set on this deployment,
        so `url_and_password` is genuinely stronger than `url_only`."""
        from admz.confirm_policy import confirm_level_key
        from admz.fleet_settings import fleet_settings
        fleet_settings.set(confirm_level_key("service-affecting"),
                           "url_and_password")
        assert self._level(operator_configurable=True) == "url_and_password"

    def test_an_operator_can_lower_it(self, isolate_admz_dirs):
        from admz.confirm_policy import confirm_level_key
        from admz.fleet_settings import fleet_settings
        fleet_settings.set(confirm_level_key("service-affecting"), "none")
        assert self._level(operator_configurable=True) == "none"

    def test_the_model_cannot_lower_its_own_gate(self):
        """`confirm_level_*` is a protected setting: MCP and anonymous REST
        callers are refused. Lowering stays an operator act at the console."""
        from admz.confirm_policy import confirm_level_key
        from admz.fleet_settings import is_protected_setting
        assert is_protected_setting(confirm_level_key("service-affecting"))

    def test_existing_adr_0034_actions_are_still_pinned(self, isolate_admz_dirs):
        """ADR-0034 pins actions so fleet overrides cannot soften them. This
        change makes that a default rather than an invariant, opt-in per action
        — so nothing that did not ask for it may move."""
        from admz import operations
        from admz.confirm_policy import confirm_level_key
        from admz.fleet_settings import fleet_settings
        fleet_settings.set(confirm_level_key("service-affecting"), "none")
        for action in ("adopt_demo", "assign_demo_fragment", "delete_device",
                       "accept_baseline", "create_task"):
            s = operations.create_action_session(
                action=action, device_id="d1", payload={}, reason="r")
            assert s.confirmation_level == "url_only", (
                f"{action} was softened by a fleet override")

    def test_no_new_level_was_invented(self):
        """The constraint: join the table, do not extend it."""
        from admz.confirm_policy import VALID_CONFIRMATION_LEVELS
        assert VALID_CONFIRMATION_LEVELS == {
            "url_and_password", "url_only", "llm_confirm", "none"}


# ── approval actually runs the thing ─────────────────────────────────────────
class TestApprovalActuallyRuns:
    def test_the_approved_survey_starts_the_real_core(self, client, ctx,
                                                      monkeypatch):
        """A gate that blocks but whose approval does nothing is worse than no
        gate. The executor must reach `start_survey_core` with the operator's
        own parameters — not defaults."""
        import asyncio

        from admz import operations
        from admz.demos.inference import collect

        seen = {}

        def _fake_start(ctx_, store, **kw):
            seen.update(kw)
            return NS(id="run-x", header=lambda: {"id": "run-x"})
        monkeypatch.setattr(collect, "start_survey_core", _fake_start)

        out = asyncio.run(
            operations._ACTION_EXECUTORS["start_demo_survey"](
                {"action": "start_demo_survey", "register_new": True,
                 "subnet": "10.20.0.0/24", "timeout": 7.0,
                 "include_weak": False, "_confirmed_by": "AXIS\\dnich"},
                ctx.registry))
        assert out["success"] is True and out["started"] is True
        assert seen["subnet"] == "10.20.0.0/24"
        assert seen["register_new"] is True and seen["timeout"] == 7.0
        assert seen["include_weak"] is False
        assert seen["principal"] == "AXIS\\dnich"

    def test_an_approved_survey_that_races_another_fails_cleanly(
            self, client, ctx):
        """Minutes pass between the widget and the click, so the late check is
        the authoritative one — and it reports, never raises."""
        import asyncio

        from admz import operations
        ctx.inference_run_store.start(mode="survey")
        out = asyncio.run(
            operations._ACTION_EXECUTORS["start_demo_survey"](
                {"action": "start_demo_survey"}, ctx.registry))
        assert out["success"] is False and "already running" in out["error"]

    def test_the_approved_register_reaches_onboarding(self, client, ctx,
                                                      monkeypatch):
        """The MCP half: approval must register AND onboard, because onboarding
        is the part that writes to the device."""
        import asyncio

        from admz import operations

        added, onboarded = {}, {}

        async def _creds(*, device_id, registry, catalog, executors):
            onboarded["id"] = device_id
            return {"status": "already_credentialed", "device_id": device_id}
        monkeypatch.setattr("admz.onboarding.onboard_device_credentials", _creds)

        registry = NS(add_device=lambda d, i: added.update(id=d, info=i))
        out = asyncio.run(
            operations._ACTION_EXECUTORS["register_discovered_device"](
                {"action": "register_discovered_device",
                 "device_id": "AABBCCDDEE01",
                 "device_info": {"host": "10.20.0.9"}},
                registry))
        assert out["success"] is True
        assert added["id"] == "AABBCCDDEE01"
        assert onboarded["id"] == "AABBCCDDEE01", (
            "the device was registered but never onboarded — approval must run "
            "the whole operation that was approved")

    def test_an_approved_register_without_a_device_id_reports(self, ctx):
        import asyncio

        from admz import operations
        out = asyncio.run(
            operations._ACTION_EXECUTORS["register_discovered_device"](
                {"action": "register_discovered_device"},
                NS(add_device=lambda *a: pytest.fail("registered nothing"))))
        assert out["success"] is False and "device_id" in out["error"]
