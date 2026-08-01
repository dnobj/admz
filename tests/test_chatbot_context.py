"""Tests for the chatbot context preload + smart result capping.

Covers admz.chatbot.context (device roster + catalog-sourced common-ops
reference) and the smart-cap helpers in admz.chatbot.client that keep an
oversized param dump from bloating a turn.
"""

from __future__ import annotations

import json

import pytest

from admz.chatbot import context as ctx
from admz.chatbot import client as cli


# --------------------------------------------------------------------------
# device roster
# --------------------------------------------------------------------------

class _FakeRegistry:
    def __init__(self, devices):
        self._devices = devices

    def list_devices(self):
        return [dict(d) for d in self._devices]


_DEVS = [
    {
        "device_id": "E827250959C6", "model": "C1710",
        "friendly_name": "AXIS C1710", "host": "192.168.1.123",
        "firmware_version": "12.10.68", "tags": ["lab", "speakers"],
    },
    {
        "device_id": "AC11", "model": "P8815-2",
        "friendly_name": "Reception Doorstation", "host": "192.168.1.153",
        "firmware_version": "11.11.205", "tags": ["lab"],
    },
]


def _rec(status="online", sd_status=None, sd_total_kb=None):
    """A stand-in for the DeviceHealthRecord _health_by_id now returns."""
    from types import SimpleNamespace

    return SimpleNamespace(
        status=SimpleNamespace(value=status),
        sd_status=sd_status,
        sd_total_kb=sd_total_kb,
    )


@pytest.fixture(autouse=True)
def _no_health_or_drift(monkeypatch):
    # Deterministic health/drift so roster lines are stable in tests.
    monkeypatch.setattr(ctx, "_health_by_id", lambda: {"E827250959C6": _rec()})
    monkeypatch.setattr(ctx, "_drift_label", lambda d: "in-sync")
    # Clear the per-model-set common-ops cache between tests.
    ctx._common_ops_cache.clear()


class TestDeviceRoster:
    def test_one_line_per_device(self):
        out = ctx.build_device_roster(_FakeRegistry(_DEVS))
        lines = out.splitlines()
        assert len(lines) == 2
        assert all(ln.startswith("- ") for ln in lines)

    def test_line_contains_model_id_ip_tags(self):
        out = ctx.build_device_roster(_FakeRegistry(_DEVS))
        assert "C1710 (E827250959C6)" in out
        assert "192.168.1.123" in out
        assert "fw 12.10.68" in out
        assert "tags: lab, speakers" in out

    def test_health_and_drift_rendered(self):
        out = ctx.build_device_roster(_FakeRegistry(_DEVS))
        assert "online" in out          # from monkeypatched _health_by_id
        assert "in-sync" in out          # from monkeypatched _drift_label
        # the device with no health record falls back to "unknown"
        assert "unknown" in out

    def test_stock_friendly_name_not_shown_as_nickname(self):
        # "AXIS C1710" merely repeats the model -> suppressed.
        out = ctx.build_device_roster(_FakeRegistry([_DEVS[0]]))
        assert '"AXIS C1710"' not in out

    def test_real_nickname_shown(self):
        # "Reception Doorstation" doesn't contain the model -> shown.
        out = ctx.build_device_roster(_FakeRegistry([_DEVS[1]]))
        assert '"Reception Doorstation"' in out

    def test_empty_registry_returns_empty(self):
        assert ctx.build_device_roster(_FakeRegistry([])) == ""

    def test_missing_registry_degrades_to_empty(self, monkeypatch):
        monkeypatch.setattr(ctx, "_resolve_registry", lambda: None)
        assert ctx.build_device_roster() == ""

    def test_registry_error_degrades_to_empty(self):
        class _Boom:
            def list_devices(self):
                raise RuntimeError("db down")

        assert ctx.build_device_roster(_Boom()) == ""


# --------------------------------------------------------------------------
# common-ops reference (catalog-sourced)
# --------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, ops):
        self.operations = ops


class _FakeResolver:
    """Maps an intent substring -> operation_id; records calls."""

    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def resolve(self, *, device_id, intent, family, device_info):
        self.calls.append(intent)
        for needle, opid in self.mapping.items():
            if needle in intent:
                return _FakeResult([{"id": opid, "risk_level": "x"}])
        return _FakeResult([])


_OP_MAP = {
    "reboot": "restart.cgi:restart",
    "factory reset": "factorydefault.cgi:factory-reset",
    "device information": "basicdeviceinfo.cgi:getAllProperties",
    "list installed acap": "applications-list.cgi:list",
}


class TestCommonOpsReference:
    def test_resolves_real_op_ids(self):
        reg = _FakeRegistry(_DEVS)
        res = _FakeResolver(_OP_MAP)
        out = ctx.build_common_ops_reference(resolver=res, registry=reg)
        assert "restart.cgi:restart" in out
        assert "factorydefault.cgi:factory-reset" in out
        assert "basicdeviceinfo.cgi:getAllProperties" in out
        assert "applications-list.cgi:list" in out
        assert out.count("\n") == 3  # 4 lines

    def test_deduplicates_repeated_op_ids(self):
        reg = _FakeRegistry(_DEVS)
        # Every intent resolves to the same op -> only one line.
        res = _FakeResolver({"": "restart.cgi:restart"})
        out = ctx.build_common_ops_reference(resolver=res, registry=reg)
        assert out.count("restart.cgi:restart") == 1

    def test_cached_per_model_set(self):
        reg = _FakeRegistry(_DEVS)
        res = _FakeResolver(_OP_MAP)
        ctx.build_common_ops_reference(resolver=res, registry=reg)
        n = len(res.calls)
        # Second call (same fleet models) must hit the cache, not re-resolve.
        ctx.build_common_ops_reference(resolver=res, registry=reg)
        assert len(res.calls) == n

    def test_empty_registry_returns_empty(self):
        res = _FakeResolver(_OP_MAP)
        assert ctx.build_common_ops_reference(resolver=res, registry=_FakeRegistry([])) == ""

    def test_resolver_error_degrades_gracefully(self):
        class _Boom:
            def resolve(self, **kw):
                raise RuntimeError("catalog down")

        out = ctx.build_common_ops_reference(resolver=_Boom(), registry=_FakeRegistry(_DEVS))
        assert out == ""  # every intent failed -> no lines


# --------------------------------------------------------------------------
# demo-inference live state (ADR-0051) — the switch the narration section
# rides on: "" here means the whole prompt section vanishes.
# --------------------------------------------------------------------------

class _FakeProposalStore:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def list(self, status=None, limit=200):
        return self._rows[:limit]


class _FakeRunStore:
    def __init__(self, run=None):
        self._run = run

    def latest(self):
        return self._run


class _FakeCtx:
    def __init__(self, proposals=(), run=None):
        self.proposal_store = _FakeProposalStore(proposals)
        self.inference_run_store = _FakeRunStore(run)


def _prop(pid="ab12", name="Activation demo", devices=("d1", "d2"),
          confidence="low", flags=("no_topology", "acap_only")):
    from admz.demos.inference.proposals import DemoProposal

    return DemoProposal(id=pid, name=name, device_ids=list(devices),
                        confidence=confidence, flags=list(flags))


def _run(run_id="r1", **kw):
    from admz.demos.inference.runs import InferenceRun

    return InferenceRun(id=run_id, mode="fast", status="complete",
                        device_count=11, rule_count=26, edge_count=10,
                        started_at=kw.pop("started_at", 0.0), **kw)


@pytest.fixture
def _wire(monkeypatch):
    """Point build_inference_section at fakes for the app ctx + the ACS flag."""
    def _apply(*, proposals=(), run=None, acs=False):
        import admz.api.context as api_ctx
        import admz.modules.acs_pro.config as acs_config

        monkeypatch.setattr(api_ctx, "get_context",
                            lambda: _FakeCtx(proposals, run))
        monkeypatch.setattr(acs_config, "acs_enabled", lambda: acs)
    return _apply


class TestInferenceSection:
    def test_inactive_surface_returns_empty(self, _wire):
        """No ACS, no run, no proposal -> the section (and the narration
        guidance riding on it) is absent entirely."""
        _wire(acs=False)
        assert ctx.build_inference_section() == ""

    def test_acs_connected_activates_it_before_any_run(self, _wire):
        _wire(acs=True)
        out = ctx.build_inference_section()
        assert "ACS Pro is connected" in out
        assert "No inference run has happened yet" in out
        assert "infer_demos" in out

    def test_a_past_run_activates_it_without_acs(self, _wire):
        _wire(acs=False, run=_run())
        out = ctx.build_inference_section()
        # The degradation must be named, not silently implied.
        assert "ACS Pro is NOT connected" in out and "acs_absent" in out
        assert "`r1`" in out and "11 device(s)" in out and "10 edge(s)" in out

    def test_open_proposals_are_listed_with_confidence_and_flags(self, _wire):
        _wire(acs=True, run=_run(), proposals=[_prop()])
        out = ctx.build_inference_section()
        assert "1 proposal(s) awaiting a decision" in out
        assert "Activation demo (ab12) — low" in out
        assert "flags: no_topology, acap_only" in out
        # The point of the whole slice: the stored name is a placeholder.
        assert "DETERMINISTIC placeholder" in out
        # And re-reading is not re-running.
        assert "do NOT re-run inference" in out

    def test_proposal_list_is_bounded(self, _wire):
        rows = [_prop(pid=f"p{i}", name=f"Demo {i}") for i in range(12)]
        _wire(acs=True, run=_run(), proposals=rows)
        out = ctx.build_inference_section()
        assert out.count("\n- ") == ctx._MAX_INFERENCE_PROPOSALS + 1  # +1 = the "…and more" line
        assert "…and more" in out
        assert "8+ proposal(s)" in out

    def test_no_open_proposals_says_so(self, _wire):
        _wire(acs=True, run=_run())
        assert "No proposal is open" in ctx.build_inference_section()

    def test_store_failure_degrades_to_empty(self, monkeypatch):
        import admz.api.context as api_ctx

        def _boom():
            raise RuntimeError("db locked")

        monkeypatch.setattr(api_ctx, "get_context", _boom)
        assert ctx.build_inference_section() == ""


# --------------------------------------------------------------------------
# advanced capabilities (ADR-0052 / GH #132 slice 3)
# --------------------------------------------------------------------------


class _EmptySettings:
    """A fleet-settings stand-in where nothing is set."""

    def get(self, key, default=None):
        return default


@pytest.fixture
def _no_caps(monkeypatch):
    """Unset every capability env var, and read settings from an empty store.

    ``tests/conftest.py`` sets the two test-suppressors process-wide, and both
    are ``production_appropriate=False`` — so without this, "an ordinary
    install sees nothing" would be testing the conftest rather than the code.
    The settings stub keeps the assertion off the developer's real DB too.
    """
    from admz import capabilities

    for cap in capabilities.CAPABILITIES:
        if cap.env_var:
            monkeypatch.delenv(cap.env_var, raising=False)
    monkeypatch.setattr(capabilities, "_settings", _EmptySettings)
    return monkeypatch


class TestCapabilitiesSection:

    def test_ordinary_install_renders_nothing(self, _no_caps):
        assert ctx.build_capabilities_section() == ""

    def test_a_loud_capability_names_itself_its_class_and_its_knob(self, _no_caps):
        _no_caps.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        out = ctx.build_capabilities_section()
        assert "`dev.auto_approve` [dev-only]" in out
        assert "ON via env (ADMZ_DEV_AUTO_APPROVE)" in out

    def test_test_auth_warns_against_the_waiting_for_you_narration(self, _no_caps):
        """The specific confusion this section exists to prevent: a script may
        be approving, so "waiting for your approval" is a false statement."""
        _no_caps.setenv("ADMZ_TEST_AUTH", "1")
        out = ctx.build_capabilities_section()
        assert "waiting for your approval" in out
        assert "may be a SCRIPT" in out
        # And the unprivileged synthetic principal is explained, not mystifying.
        assert "no group membership" in out

    def test_auto_approve_says_the_gate_still_fires(self, _no_caps):
        _no_caps.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        out = ctx.build_capabilities_section()
        assert "The gate still fires" in out
        assert "WHO may satisfy it" in out

    def test_a_suppressor_explains_the_symptom_it_causes(self, _no_caps):
        _no_caps.setenv("ADMZ_DISABLE_ONBOARDING_PROBES", "1")
        out = ctx.build_capabilities_section()
        assert "`test.no_onboarding_probes` [test-suppressor]" in out
        assert "credentials_needed" in out

    def test_production_appropriate_capabilities_stay_silent(self, _no_caps):
        """A survey/ingest install is a legitimate profile. Narrating it every
        turn is the alarm fatigue the chip rules already avoid."""
        _no_caps.setenv("ADMZ_EVENT_INGEST", "1")
        _no_caps.setenv("ADMZ_MCP_NO_SCHEDULER", "1")
        assert ctx.build_capabilities_section() == ""

    def test_a_loud_capability_wins_over_a_quiet_one(self, _no_caps):
        _no_caps.setenv("ADMZ_EVENT_INGEST", "1")
        _no_caps.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        out = ctx.build_capabilities_section()
        assert "dev.auto_approve" in out
        assert "events.device_ingest" not in out

    def test_every_line_is_one_bullet_per_capability(self, _no_caps):
        _no_caps.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        _no_caps.setenv("ADMZ_TEST_AUTH", "1")
        out = ctx.build_capabilities_section()
        assert out.count("\n- ") + 1 == 2  # two capabilities, two bullets

    def test_registry_failure_degrades_to_empty(self, monkeypatch):
        from admz import capabilities

        monkeypatch.setattr(
            capabilities, "active_capabilities",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert ctx.build_capabilities_section() == ""

    def test_a_capability_without_a_note_still_renders_its_description(
        self, _no_caps
    ):
        """The fallback is the registry's own sentence, so a capability added
        later is described rather than silently unexplained."""
        from admz import capabilities

        _no_caps.setenv("ADMZ_ACS_RULE_WRITE", "1")
        out = ctx.build_capabilities_section()
        cap = capabilities.get("acs.rule_write")
        assert cap.id not in ctx._NARRATION_NOTES
        assert cap.description in out


# --------------------------------------------------------------------------
# smart result capping (client.py)
# --------------------------------------------------------------------------

def _param_blob():
    lines = []
    for grp, n in [("Audio", 40), ("Image", 220), ("Network", 130)]:
        for i in range(n):
            lines.append(f"root.{grp}.X{i}.Value=val{i}")
    return "\n".join(lines)


class TestSmartCap:
    def test_small_result_passes_through_unchanged(self):
        small = {"success": True, "operation_id": "param.cgi:update", "data": "OK"}
        assert cli._smart_cap_tool_result("execute_operation", small, []) is small

    def test_big_param_dump_becomes_group_index(self):
        payload = {"success": True, "operation_id": "param.cgi:list",
                   "data": _param_blob()}
        capped = cli._smart_cap_tool_result("execute_operation", payload, [])
        data = capped["data"]
        assert data.get("_truncated") is True
        assert data["total_params"] == 390
        assert "root.Image" in data["groups"]
        # The whole thing is now tiny.
        assert len(json.dumps(capped)) < 4000

    def test_recent_groups_scope_the_dump(self):
        payload = {"success": True, "operation_id": "param.cgi:list",
                   "data": _param_blob()}
        capped = cli._smart_cap_tool_result(
            "execute_operation", payload, ["root.Audio"]
        )
        data = capped["data"]
        assert data.get("_scoped") is True
        kept = data["data"].splitlines()
        assert len(kept) == 40
        assert all(ln.startswith("root.Audio") for ln in kept)

    def test_generic_big_result_trims_fattest_field(self):
        payload = {"success": True, "blob": "x" * 20000, "small": "ok"}
        capped = cli._smart_cap_tool_result("some_tool", payload, [])
        assert capped["small"] == "ok"
        assert "truncated" in capped["blob"]
        assert len(capped["blob"]) < 20000

    def test_looks_like_param_dump(self):
        assert cli._looks_like_param_dump("root.A.B=1\nroot.A.C=2\nroot.A.D=3\n"
                                          "root.A.E=4\nroot.A.F=5")
        assert not cli._looks_like_param_dump("just some prose with no equals")
        assert not cli._looks_like_param_dump({"not": "a string"})

    def test_extract_param_groups_handles_shapes(self):
        assert cli._extract_param_groups({"parameter_groups": ["root.Audio.", "root.Image"]}) == [
            "root.Audio", "root.Image"
        ]
        assert cli._extract_param_groups(
            {"parameter_groups": [{"group": "root.Network"}, {"prefix": "root.Time"}]}
        ) == ["root.Network", "root.Time"]
        assert cli._extract_param_groups({}) == []
        assert cli._extract_param_groups("nope") == []
