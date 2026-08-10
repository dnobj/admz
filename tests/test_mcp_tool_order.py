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
from tests import mcp_harness


# The canonical core-tool order. Baseline was the 52 tools shipped on master @
# a39bf26 (clean base for the platform/modules extraction); ``search_activity``
# (ADR-0041 layer 3) was appended at the end of the migrated section.
EXPECTED_TOOL_ORDER = [
    "list_devices",
    "get_device",
    "get_device_health",
    "get_fleet_health",
    "await_device_recovery",
    "search_devices",
    "list_accounts",
    "register_device",
    "onboard_device",
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
    "search_activity",
    "list_rule_capabilities",
    "create_action_rule",
    "delete_action_rule",
    "list_demos",
    "get_demo",
    "create_demo",
    "update_demo",
    "delete_demo",
    "assign_demo_fragment",
    "adopt_demo",
    "deactivate_demo",
    "prepare_demo",
    "end_demo",
    "demo_setup_status",
    "survey_demo_evidence",
    # #124 slice 3 — the inference tools sit together, right after the evidence
    # graph they consume.
    "infer_demos",
    "list_demo_proposals",
    "confirm_demo_proposal",
    "dismiss_demo_proposal",
    "set_event_ingest",
    # GH #132 slice 3 — the advanced-capability inventory. Appended at the very
    # end so the frozen prefix above is untouched. Read-only, and deliberately
    # alone: there is no set_advanced_capability and there never should be
    # (admz/mcp/tools/capabilities.py explains why).
    "get_advanced_capabilities",
]


def _live_tool_order():
    srv = ADMZMCPServer()
    return asyncio.new_event_loop().run_until_complete(
        mcp_harness.tool_names(srv)
    )


def test_device_tool_order_is_frozen():
    """The core device/platform tools are a frozen, ordered PREFIX.

    Enabled platform modules (e.g. ACS Pro) append their tools after, so we
    assert the prefix — this keeps the test independent of which modules happen
    to be enabled in the live config.
    """
    names = _live_tool_order()
    assert names[: len(EXPECTED_TOOL_ORDER)] == EXPECTED_TOOL_ORDER


def test_list_tools_has_no_duplicates():
    names = _live_tool_order()
    assert len(names) == len(set(names)), "duplicate tool name in list_tools"


def test_dispatch_table_matches_device_tools():
    """The static dispatch table is exactly the frozen device tools.

    list_tools (schemas) and TOOL_HANDLERS (dispatch) must not drift for the
    device surface. Module tools are advertised too but dispatched via the
    module registry, so they're not in TOOL_HANDLERS.
    """
    from admz.mcp.dispatch import TOOL_HANDLERS

    assert set(TOOL_HANDLERS) == set(EXPECTED_TOOL_ORDER), {
        "table_only": sorted(set(TOOL_HANDLERS) - set(EXPECTED_TOOL_ORDER)),
        "expected_only": sorted(set(EXPECTED_TOOL_ORDER) - set(TOOL_HANDLERS)),
    }
    # Every device tool is actually advertised by list_tools.
    assert set(TOOL_HANDLERS) <= set(_live_tool_order())


class TestRegisterDiscoveredDescriptionMatchesBehaviour:
    """GH #366. The tool description the model reads at runtime said the device
    "will be created without credentials — use capture_credentials", while the
    handler registers **and onboards** (its own comment says "Register, then
    onboard"). `docs/MCP_TOOLS_REFERENCE.md` had it right; only the string the
    LLM actually consumes was wrong.

    Asserting on this string is not the source-string theatre I have removed
    four times this session. There the string was *source code* standing in for
    behaviour; here the string **is the artefact** — the tool description is the
    contract the model selects on, so its content is the thing under test.
    """

    def _description(self):
        import inspect
        from admz.mcp import server
        src = inspect.getsource(server)
        i = src.index('name="register_discovered_device"')
        j = src.index("inputSchema", i)
        return src[i:j]

    def test_it_does_not_claim_the_device_is_left_without_credentials(self):
        """The specific falsehood: onboarding resolves credentials, and on a
        factory-defaulted unit it creates an admin account."""
        assert "without credentials" not in self._description()

    def test_it_says_onboarding_happens(self):
        d = self._description().lower()
        assert "onboard" in d

    def test_it_names_the_approval_outcome(self):
        """A model that does not expect `approval_required` treats it as a
        failure and retries — the exact behaviour #214 corrected in the docs."""
        assert "approval_required" in self._description()

    def test_it_points_at_the_register_only_route(self):
        """The answer to #366: the separated path exists, and the tool should
        say where."""
        assert "/api/discovery/register" in self._description()
