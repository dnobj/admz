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
