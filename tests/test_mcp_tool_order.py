"""Frozen wire-order snapshot for the MCP ``list_tools`` surface.

The tool list is consumed by LLMs and e2e fixtures that have learned the
existing order; the modularization (PR1) re-drives ``list_tools`` from the
module registry, so this snapshot guards against an accidental reorder or a
dropped/added tool while the dispatch is rewired. If a tool is intentionally
added/removed/reordered, update ``EXPECTED_TOOL_ORDER`` in the same commit.
"""

import asyncio

import pytest

from admz.mcp.server import ADMZMCPServer


# The canonical 52-tool order as shipped on master @ a39bf26 (clean base for
# the platform/modules extraction). Captured directly from a live server.
EXPECTED_TOOL_ORDER = [
    "list_devices",
    "get_device",
    "get_device_health",
    "get_fleet_health",
    "await_device_recovery",
    "search_devices",
    "list_accounts",
    "register_device",
    "add_account",
    "update_device",
    "update_device_tags",
    "delete_device",
    "delete_account",
    "capture_credentials",
    "check_capture_status",
    "query_catalog",
    "execute_operation",
    "confirm_dangerous_operation",
    "create_plan",
    "execute_plan",
    "get_plan_status",
    "snapshot_device",
    "snapshot_fleet",
    "restore_device",
    "accept_baseline",
    "diff_device",
    "check_drift",
    "get_drift_alerts",
    "test_device_credentials",
    "discover_network_devices",
    "register_discovered_device",
    "reconcile_device_addresses",
    "create_temp_credentials",
    "cleanup_temp_credentials",
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
    "queue_device_recovery",
    "list_device_recovery",
    "cancel_device_recovery",
    "list_tasks",
    "search_audit_log",
    "download_firmware",
    "import_firmware",
    "list_cached_firmware",
]


def _live_tool_order():
    srv = ADMZMCPServer()
    handler = None
    for req_type, h in srv.server.request_handlers.items():
        if req_type.__name__ == "ListToolsRequest":
            handler = h
            break
    assert handler is not None, "list_tools handler not registered"

    from mcp.types import ListToolsRequest

    res = asyncio.new_event_loop().run_until_complete(
        handler(ListToolsRequest(method="tools/list"))
    )
    return [t.name for t in res.root.tools]


def test_list_tools_order_is_frozen():
    assert _live_tool_order() == EXPECTED_TOOL_ORDER


def test_list_tools_has_no_duplicates():
    names = _live_tool_order()
    assert len(names) == len(set(names)), "duplicate tool name in list_tools"


def test_dispatch_table_matches_list_tools():
    """Every advertised tool must have a dispatch handler, and vice-versa.

    The P2 refactor split the schema list (list_tools) from the dispatch table
    (TOOL_HANDLERS). This guards against the two drifting — a tool advertised
    but unhandled (or handled but unadvertised) is a bug.
    """
    from admz.mcp.dispatch import TOOL_HANDLERS

    advertised = set(_live_tool_order())
    handled = set(TOOL_HANDLERS)
    assert advertised == handled, {
        "advertised_only": sorted(advertised - handled),
        "handled_only": sorted(handled - advertised),
    }
