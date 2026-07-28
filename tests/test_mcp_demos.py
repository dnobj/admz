"""MCP demo tools (ADR-0046/0047) — chat-console demo management.

Exercises the real ADMZMCPServer handlers against an isolated store: reads
return live views, metadata CRUD writes directly, and the drift-affecting
writes (assign fragment, adopt) return the approval envelope WITHOUT mutating.
Name-based addressing is pinned throughout — the chat model says "the speaker
demo", not a hex id.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")

    # The confirm-store/audit singletons bind their DB path at import time —
    # rebind them or the gated-write tests leak sessions into the REAL
    # deployment DB (observed live 2026-07-18: pending cam-1 rows in prod).
    from admz import audit as audit_module
    monkeypatch.setattr(
        audit_module, "audit_log",
        audit_module.AuditLog(db_path=str(tmp_path / "admz.db")))
    import admz.api.confirm_store as cs_module
    monkeypatch.setattr(
        cs_module, "confirm_store",
        cs_module.ConfirmStore(db_path=str(tmp_path / "admz.db")))

    from admz.mcp.server import ADMZMCPServer

    srv = ADMZMCPServer()
    srv.principal = SimpleNamespace(
        name="tester", source="api-key", is_anonymous=False
    )
    repo_path = str(tmp_path / "config-repo")
    for key, val in [("user.email", "t@t"), ("user.name", "T"),
                     ("commit.gpgsign", "false")]:
        subprocess.run(["git", "config", key, val], cwd=repo_path, check=True)
    return srv


def _add_device(srv, device_id, tags=("speakers",)):
    srv.registry.add_device(device_id, {
        "host": "192.0.2.20", "nickname": device_id, "model": "AXIS TEST",
        "tags": list(tags)})


class TestReadTools:
    def test_list_and_get_by_name(self, server):
        assert server._list_demos() == {"success": True, "count": 0, "demos": []}
        server._create_demo({"name": "Speaker demo", "narrative": "The story.",
                             "tag": "speakers"})
        out = server._list_demos()
        assert out["count"] == 1
        assert out["demos"][0]["readiness"]["state"] == "empty"

        got = server._get_demo("speaker demo")     # case-insensitive NAME
        assert got["success"] is True
        assert got["demo"]["narrative"] == "The story."
        assert got["demo"]["fragments"] == {}

    def test_get_missing_and_ambiguous(self, server):
        assert "not found" in server._get_demo("nope")["error"].lower()
        server._create_demo({"name": "Twin"})
        server._create_demo({"name": "twin"})
        err = server._get_demo("TWIN")["error"]
        assert "ambiguous" in err.lower()


class TestMetadataCrud:
    def test_create_update_delete_direct(self, server):
        created = server._create_demo({"name": "Lifecycle"})
        assert created["success"] is True and "blocked" not in created

        upd = server._update_demo({"demo": "Lifecycle", "narrative": "v2"})
        assert upd["success"] is True and upd["demo"]["narrative"] == "v2"

        gone = server._delete_demo("Lifecycle")
        assert gone["success"] is True
        assert server._list_demos()["count"] == 0

    def test_create_requires_name(self, server):
        assert server._create_demo({})["success"] is False

    def test_update_rejects_no_fields(self, server):
        server._create_demo({"name": "X"})
        res = server._update_demo({"demo": "X"})
        assert res["success"] is False and "nothing to update" in res["error"]


class TestGatedWrites:
    def test_assign_fragment_returns_envelope_without_mutating(self, server):
        from admz.demos import fragments as fr

        _add_device(server, "cam-1")
        server._create_demo({"name": "Gated", "tag": "speakers"})
        res = server._assign_demo_fragment({
            "demo": "Gated",
            "fields": [{"device_id": "cam-1", "facet": "other",
                        "path": "Motion.M0.Enabled"}],
        })
        assert res["blocked"] is True and res["success"] is False
        assert res["confirm_url"].startswith("/confirm/")
        # Nothing written until approval.
        demo = server.components.demo_store.list()[0]
        assert fr.load_all_fragments(server.git_repo, demo.id) == {}

        # The held session is the registered action with the payload intact.
        from admz.api.confirm_store import confirm_store
        session = confirm_store.get_session(res["confirm_token"])
        assert session.operation_id == "action:assign_demo_fragment"
        assert session.action["demo"] == demo.id
        assert session.action["fields"][0]["path"] == "Motion.M0.Enabled"

    def test_assign_requires_fields(self, server):
        server._create_demo({"name": "Empty gate"})
        res = server._assign_demo_fragment({"demo": "Empty gate", "fields": []})
        assert res["success"] is False and "blocked" not in res

    def test_adopt_returns_envelope_without_mutating(self, server):
        server._create_demo({"name": "Adoptable"})
        res = server._adopt_demo("Adoptable")
        assert res["blocked"] is True and res["confirm_token"]
        assert server.components.demo_store.list()[0].active is False

    def test_adopt_already_active_short_circuits(self, server):
        server._create_demo({"name": "Live one"})
        demo = server.components.demo_store.list()[0]
        demo.active = True
        server.components.demo_store.update(demo)
        res = server._adopt_demo("Live one")
        assert res["success"] is True and "blocked" not in res

    def test_deactivate_is_direct(self, server):
        server._create_demo({"name": "Downshift"})
        demo = server.components.demo_store.list()[0]
        demo.active = True
        server.components.demo_store.update(demo)
        res = server._deactivate_demo("Downshift")
        assert res["success"] is True and "blocked" not in res
        assert server.components.demo_store.get(demo.id).active is False


class TestPrepareEnd:
    @pytest.mark.asyncio
    async def test_prepare_refuses_baseline_demo(self, server):
        _add_device(server, "cam-1")
        server._create_demo({"name": "Baseline demo", "tag": "speakers"})
        res = await server._prepare_demo("Baseline demo")
        assert res["success"] is False
        # ADR-0050 Phase A reworded this toward capture (a demo owning no config
        # is steered to capture some, or told it runs on the baseline).
        assert "Capture some first" in res["error"]

    @pytest.mark.asyncio
    async def test_end_refuses_baseline_demo(self, server):
        _add_device(server, "cam-1")
        server._create_demo({"name": "Baseline demo", "tag": "speakers"})
        res = await server._end_demo("Baseline demo")
        assert res["success"] is False and "nothing to end" in res["error"]


class TestSetupStatusAndIngest:
    def test_setup_status_shape_and_next_actions(self, server):
        _add_device(server, "cam-1")
        server._create_demo({"name": "Speaker demo", "device_ids": ["cam-1"]})
        res = server._demo_setup_status("Speaker demo")
        assert res["success"] is True
        assert res["demo_name"] == "Speaker demo"
        for key in ("devices", "fragments", "rules", "signals", "ingest", "next_actions"):
            assert key in res
        assert len(res["next_actions"]) >= 1
        # a demo owning no config yet is steered toward capture or rules.
        assert any("Capture config" in a or "Create the demo's rules" in a
                   for a in res["next_actions"])

    def test_setup_status_unknown_demo(self, server):
        assert server._demo_setup_status("nope")["success"] is False

    @pytest.mark.asyncio
    async def test_set_event_ingest_is_gated(self, server):
        res = await server._set_event_ingest(True)
        # returns an approval envelope; nothing flips until approval.
        assert res.get("success") is False
        assert res.get("confirm_url") or res.get("blocked") or res.get("confirm_token")

    @pytest.mark.asyncio
    async def test_prepare_by_name_resolves(self, server):
        res = await server._prepare_demo("does-not-exist")
        assert res["success"] is False and "not found" in res["error"].lower()


class TestDispatchWiring:
    def test_all_demo_tools_have_handlers_and_schemas(self, server):
        from admz.mcp.dispatch import TOOL_HANDLERS
        from admz.mcp.tools.demos import TOOLS

        names = {t.name for t in TOOLS}
        assert names == {
            "list_demos", "get_demo", "create_demo", "update_demo",
            "delete_demo", "assign_demo_fragment", "adopt_demo",
            "deactivate_demo", "prepare_demo", "end_demo",
            # ADR-0050 Phase C
            "demo_setup_status", "set_event_ingest",
            # #124 slice 2 — the demo-inference evidence graph (read-only)
            "survey_demo_evidence",
        }
        for n in names:
            assert n in TOOL_HANDLERS
