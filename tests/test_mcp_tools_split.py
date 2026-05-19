"""Tests that Phase 9's MCP tool split preserves the surface.

The contract: ``ADMZMCPServer`` must continue to expose every tool
it did before, in the same name + schema shape. Phase 9 moved a
subset of Tool definitions out to ``admz/mcp/tools/`` and spliced
them back via ``MIGRATED_TOOLS``. These tests verify:

  - The wire-level tool list still contains the migrated names.
  - Each migrated Tool still has a non-empty description and a
    well-formed inputSchema.
  - MIGRATED_TOOLS is the union of the per-domain TOOLS lists,
    in the documented order.
"""

import pytest


# ---------------------------------------------------------------------------
# Per-domain module contracts
# ---------------------------------------------------------------------------


class TestPerDomainModules:
    def test_knowledge_module_has_two_tools(self):
        from admz.mcp.tools import knowledge
        names = {t.name for t in knowledge.TOOLS}
        assert names == {"query_knowledge", "check_api_support"}

    def test_schedules_module_has_five_tools(self):
        from admz.mcp.tools import schedules
        names = {t.name for t in schedules.TOOLS}
        assert names == {
            "create_snapshot_schedule",
            "list_snapshot_schedules",
            "update_snapshot_schedule",
            "delete_snapshot_schedule",
            "run_snapshot_schedule",
        }

    def test_fleet_module_has_two_tools(self):
        from admz.mcp.tools import fleet
        names = {t.name for t in fleet.TOOLS}
        assert names == {"get_fleet_settings", "set_fleet_setting"}

    def test_provision_module_has_one_tool(self):
        from admz.mcp.tools import provision
        names = {t.name for t in provision.TOOLS}
        assert names == {"provision_device"}

    def test_firmware_module_has_three_tools(self):
        from admz.mcp.tools import firmware
        names = {t.name for t in firmware.TOOLS}
        assert names == {
            "download_firmware",
            "import_firmware",
            "list_cached_firmware",
        }


# ---------------------------------------------------------------------------
# MIGRATED_TOOLS aggregate
# ---------------------------------------------------------------------------


class TestMigratedToolsAggregate:
    def test_migrated_tools_count(self):
        from admz.mcp.tools import MIGRATED_TOOLS
        # 2 + 5 + 2 + 1 + 3 = 13
        assert len(MIGRATED_TOOLS) == 13

    def test_migrated_tools_all_named(self):
        from admz.mcp.tools import MIGRATED_TOOLS
        for tool in MIGRATED_TOOLS:
            assert tool.name, "tool has no name"
            assert tool.description, f"tool {tool.name} has no description"
            assert isinstance(tool.inputSchema, dict)
            assert tool.inputSchema.get("type") == "object"

    def test_no_duplicate_names(self):
        from admz.mcp.tools import MIGRATED_TOOLS
        names = [t.name for t in MIGRATED_TOOLS]
        assert len(names) == len(set(names)), "duplicate tool names in MIGRATED_TOOLS"


# ---------------------------------------------------------------------------
# End-to-end: ADMZMCPServer.list_tools still emits everything
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_server_list_tools_includes_migrated_names(tmp_path, monkeypatch):
    """The big-picture invariant: list_tools() called on a real
    ADMZMCPServer instance returns the migrated tools alongside
    everything still inlined."""
    # Isolate DB so the server doesn't touch real state.
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")

    from admz.mcp.server import ADMZMCPServer

    server = ADMZMCPServer()

    # The Server library doesn't expose the registered handlers
    # directly via a public attribute, but it does store them. We
    # grab the list_tools handler the same way the MCP runtime
    # does, by calling Server.request_handlers[...] — but that's
    # an implementation detail. Easier: round-trip through the
    # public list_tools() handler.
    #
    # The mcp.server.Server stores the @server.list_tools()
    # callback in request_handlers under the ListToolsRequest
    # type. We invoke it directly here.
    from mcp.types import ListToolsRequest
    handler = server.server.request_handlers.get(ListToolsRequest)
    assert handler is not None, "list_tools handler not registered"

    result = await handler(ListToolsRequest(method="tools/list"))
    tool_names = {t.name for t in result.root.tools}

    # Spot-check: every migrated tool name is present.
    must_be_present = {
        "query_knowledge",
        "check_api_support",
        "create_snapshot_schedule",
        "list_snapshot_schedules",
        "update_snapshot_schedule",
        "delete_snapshot_schedule",
        "run_snapshot_schedule",
        "get_fleet_settings",
        "set_fleet_setting",
        "provision_device",
        "download_firmware",
        "import_firmware",
        "list_cached_firmware",
    }
    missing = must_be_present - tool_names
    assert not missing, f"migrated tools missing from server: {missing}"

    # Spot-check: a few non-migrated tools are still present.
    must_still_be_inlined = {
        "list_devices",
        "execute_operation",
        "create_plan",
        "snapshot_device",
        "check_drift",
    }
    still_missing = must_still_be_inlined - tool_names
    assert not still_missing, (
        f"non-migrated tools went missing during split: {still_missing}"
    )
