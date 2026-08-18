"""Table-driven MCP tool dispatch (ADR-0039, PR1-P2).

``call_tool``'s outer wrapper in ``server.py`` (validate → anonymous-gate →
try/except/finally-audit) stays byte-identical; only the inner 52-arm
``if/elif name ==`` chain is replaced by a single lookup into
``TOOL_HANDLERS`` here.

Handlers are **free async functions** ``(ToolCtx, args) -> result dict``. In
this phase they are thin SHIMS that delegate to the bound
``ADMZMCPServer._method`` implementations (reached via ``ctx.server``), so this
is a pure refactor — no behavior change. Decoupling the handler from the bound
method is what makes the per-tool body relocation in P4 clean: a device tool's
body moves into ``admz/modules/devices/`` and only its entry here changes.

The handler key set is asserted equal to ``list_tools()`` by the order/coverage
snapshot test, so the schema list and the dispatch table can never drift.

NOTE: the five recovery/audit tools (``queue/list/cancel_device_recovery``,
``list_tasks``, ``search_audit_log``) are *synchronous* on the server; their
shims call without ``await`` exactly as the old chain did.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from admz.modules.contract import ToolHandler


@dataclass
class ToolCtx:
    """What a tool handler needs to run.

    In the shim phase the only field is ``server`` (the ``ADMZMCPServer``), so
    handlers reach the existing implementations via ``ctx.server._method(...)``.
    As bodies relocate to modules, this context grows the concrete dependencies
    (registry, catalog, executors, principal) the moved handlers consume.
    """

    server: Any


# --- Device registry / fleet -------------------------------------------------
async def _list_devices(ctx, a):
    return await ctx.server._list_devices()


async def _get_device(ctx, a):
    return await ctx.server._get_device(a["device_id"])


async def _get_device_health(ctx, a):
    return await ctx.server._get_device_health(a["device_id"])


async def _get_fleet_health(ctx, a):
    return await ctx.server._get_fleet_health()


async def _await_device_recovery(ctx, a):
    return await ctx.server._await_device_recovery(a)


async def _search_devices(ctx, a):
    return await ctx.server._search_devices(a)


async def _list_accounts(ctx, a):
    return await ctx.server._list_accounts(a["device_id"])


async def _onboard_device(ctx, a):
    return await ctx.server._onboard_device(a["device_id"], adopt=bool(a.get("adopt", False)))


async def _register_device(ctx, a):
    return await ctx.server._register_device(
        a["device_id"], a["device_info"], a.get("accounts")
    )


async def _add_account(ctx, a):
    return await ctx.server._add_account(
        a["device_id"], a["account_id"], a["account_data"]
    )


async def _update_device(ctx, a):
    return await ctx.server._update_device(a["device_id"], a["updates"])


async def _update_device_tags(ctx, a):
    return await ctx.server._update_device_tags(
        a["device_id"], a.get("add") or [], a.get("remove") or []
    )


async def _delete_device(ctx, a):
    return await ctx.server._delete_device(a["device_id"])


async def _delete_account(ctx, a):
    return await ctx.server._delete_account(a["device_id"], a["account_id"])


# --- Credentials capture -----------------------------------------------------
async def _capture_credentials(ctx, a):
    return await ctx.server._capture_credentials(a)


async def _check_capture_status(ctx, a):
    return await ctx.server._check_capture_status(a["token"])


# --- Catalog / knowledge / execution -----------------------------------------
async def _query_catalog(ctx, a):
    return await ctx.server._query_catalog(
        a["device_id"], a["intent"], a.get("family", "vapix")
    )


async def _query_knowledge(ctx, a):
    return await ctx.server._query_knowledge(a["device_id"], a.get("topic", ""))


async def _check_api_support(ctx, a):
    return await ctx.server._check_api_support(a["device_id"], a.get("api_id"))


async def _execute_operation(ctx, a):
    return await ctx.server._execute_operation(
        a["device_id"],
        a["operation_id"],
        a.get("params", {}),
        a.get("family", "vapix"),
    )


async def _confirm_dangerous_operation(ctx, a):
    return await ctx.server._confirm_dangerous(a["confirm_token"])


# --- Plans -------------------------------------------------------------------
async def _create_plan(ctx, a):
    return await ctx.server._create_plan(
        a["description"], a["steps"], a.get("on_failure", "stop")
    )


async def _execute_plan(ctx, a):
    return await ctx.server._execute_plan(
        a["plan_id"], a.get("confirm_dangerous", False)
    )


async def _get_plan_status(ctx, a):
    return await ctx.server._get_plan_status(a["plan_id"])


# --- Snapshot / restore / drift ----------------------------------------------
async def _snapshot_device(ctx, a):
    return await ctx.server._snapshot_device(a["device_id"], a.get("message"))


async def _snapshot_fleet(ctx, a):
    return await ctx.server._snapshot_fleet(a.get("tag_filter"), a.get("message"))


async def _restore_device(ctx, a):
    return await ctx.server._restore_device(
        a["device_id"], a.get("ref"), a.get("facets")
    )


async def _accept_baseline(ctx, a):
    return await ctx.server._accept_baseline(a["device_id"], a.get("commit_sha"))


async def _diff_device(ctx, a):
    return await ctx.server._diff_device(
        a["device_id"], a.get("ref_a", "HEAD~1"), a.get("ref_b", "HEAD")
    )


async def _check_drift(ctx, a):
    return await ctx.server._check_drift(a.get("device_id"), a.get("tag_filter"))


async def _get_drift_alerts(ctx, a):
    return await ctx.server._get_drift_alerts(a)


# --- Credential probe --------------------------------------------------------
async def _test_device_credentials(ctx, a):
    return await ctx.server._test_credentials(a)


# --- Discovery ---------------------------------------------------------------
async def _discover_network_devices(ctx, a):
    return await ctx.server._discover_network_devices(a)


async def _register_discovered_device(ctx, a):
    return await ctx.server._register_discovered_device(a)


async def _reconcile_device_addresses(ctx, a):
    return await ctx.server._reconcile_device_addresses(a)


# --- Schedules ---------------------------------------------------------------
async def _create_snapshot_schedule(ctx, a):
    return await ctx.server._create_snapshot_schedule(
        a["schedule_id"],
        a["description"],
        a["interval"],
        a.get("tag_filter"),
        a.get("device_ids"),
        a.get("job_type") or "snapshot",
    )


async def _list_snapshot_schedules(ctx, a):
    return await ctx.server._list_snapshot_schedules()


async def _update_snapshot_schedule(ctx, a):
    return await ctx.server._update_snapshot_schedule(a["schedule_id"], a)


async def _delete_snapshot_schedule(ctx, a):
    return await ctx.server._delete_snapshot_schedule(a["schedule_id"])


async def _run_snapshot_schedule(ctx, a):
    return await ctx.server._run_snapshot_schedule(a["schedule_id"])


# --- Fleet settings ----------------------------------------------------------
async def _get_fleet_settings(ctx, a):
    return await ctx.server._get_fleet_settings()


async def _set_fleet_setting(ctx, a):
    return await ctx.server._set_fleet_setting(a["key"], a.get("value"))


# --- Provisioning ------------------------------------------------------------
async def _provision_device(ctx, a):
    return await ctx.server._provision_device(a)


# --- Deferred recovery + tasks + audit (server methods are SYNC) -------------
async def _queue_device_recovery(ctx, a):
    return ctx.server._queue_device_recovery(a)


async def _list_device_recovery(ctx, a):
    return ctx.server._list_device_recovery(a)


async def _cancel_device_recovery(ctx, a):
    return ctx.server._cancel_device_recovery(a)


async def _list_tasks(ctx, a):
    return ctx.server._list_tasks(a)


async def _search_audit_log(ctx, a):
    return ctx.server._search_audit_log(a)


async def _search_activity(ctx, a):
    return ctx.server._search_activity(a)


# --- Firmware ----------------------------------------------------------------
async def _download_firmware(ctx, a):
    return await ctx.server._download_firmware(a)


async def _import_firmware(ctx, a):
    return await ctx.server._import_firmware(a)


async def _list_cached_firmware(ctx, a):
    return await ctx.server._list_cached_firmware()


# --- Device event action rules ----------------------------------------------
async def _list_rule_capabilities(ctx, a):
    return await ctx.server._list_rule_capabilities(a["device_id"])


async def _create_action_rule(ctx, a):
    return await ctx.server._create_action_rule(
        a["device_id"], a["condition_id"], a["action_token"],
        a.get("param_choices"), a.get("rule_name"), a.get("demo"),
    )


async def _delete_action_rule(ctx, a):
    return await ctx.server._delete_action_rule(a["device_id"], a["rule_id"])


# --- Demos (ADR-0046/0047) ---------------------------------------------------
async def _list_demos(ctx, a):
    return ctx.server._list_demos()


async def _get_demo(ctx, a):
    return ctx.server._get_demo(a["demo"])


async def _create_demo(ctx, a):
    return ctx.server._create_demo(a)


async def _update_demo(ctx, a):
    return ctx.server._update_demo(a)


async def _delete_demo(ctx, a):
    return ctx.server._delete_demo(a["demo"])


async def _assign_demo_fragment(ctx, a):
    return ctx.server._assign_demo_fragment(a)


async def _adopt_demo(ctx, a):
    return ctx.server._adopt_demo(a["demo"])


async def _deactivate_demo(ctx, a):
    return ctx.server._deactivate_demo(a["demo"])


async def _prepare_demo(ctx, a):
    return await ctx.server._prepare_demo(a["demo"])


async def _end_demo(ctx, a):
    return await ctx.server._end_demo(a["demo"])


async def _demo_setup_status(ctx, a):
    return ctx.server._demo_setup_status(a["demo"])


async def _survey_demo_evidence(ctx, a):
    return await ctx.server._survey_demo_evidence(a.get("run_id"))


async def _infer_demos(ctx, a):
    return await ctx.server._infer_demos(
        include_weak=bool(a.get("include_weak", True)),
        include_acs=bool(a.get("include_acs", True)))


async def _list_demo_proposals(ctx, a):
    return ctx.server._list_demo_proposals(a.get("proposal"), a.get("status"))


async def _confirm_demo_proposal(ctx, a):
    return ctx.server._confirm_demo_proposal(a)


async def _dismiss_demo_proposal(ctx, a):
    return ctx.server._dismiss_demo_proposal(a["proposal"], a.get("reason") or "")


async def _set_event_ingest(ctx, a):
    return await ctx.server._set_event_ingest(bool(a.get("enabled")))


# --- Advanced capabilities (GH #132, ADR-0052) -------------------------------
# READ ONLY, and this stays a table of one. See admz/mcp/tools/capabilities.py
# for why there is no set_advanced_capability beside it: an LLM that can enable
# its own approver is not gated at all. set_fleet_setting refuses every
# capability setting_key too — since ADR-0053 that needs no per-key upkeep,
# because it refuses everything outside the two-key allow-set.
async def _get_advanced_capabilities(ctx, a):
    return ctx.server._get_advanced_capabilities()


# --- Temporary credentials ---------------------------------------------------
async def _create_temp_credentials(ctx, a):
    return await ctx.server._create_temp_credentials(a)


async def _cleanup_temp_credentials(ctx, a):
    return await ctx.server._cleanup_temp_credentials(a)


# Name → handler. Keys MUST equal the list_tools() name set (snapshot-tested).
TOOL_HANDLERS: Dict[str, ToolHandler] = {
    "list_devices": _list_devices,
    "get_device": _get_device,
    "get_device_health": _get_device_health,
    "get_fleet_health": _get_fleet_health,
    "await_device_recovery": _await_device_recovery,
    "search_devices": _search_devices,
    "list_accounts": _list_accounts,
    "register_device": _register_device,
    "onboard_device": _onboard_device,
    "add_account": _add_account,
    "update_device": _update_device,
    "update_device_tags": _update_device_tags,
    "delete_device": _delete_device,
    "delete_account": _delete_account,
    "capture_credentials": _capture_credentials,
    "check_capture_status": _check_capture_status,
    "query_catalog": _query_catalog,
    "query_knowledge": _query_knowledge,
    "check_api_support": _check_api_support,
    "execute_operation": _execute_operation,
    "confirm_dangerous_operation": _confirm_dangerous_operation,
    "create_plan": _create_plan,
    "execute_plan": _execute_plan,
    "get_plan_status": _get_plan_status,
    "snapshot_device": _snapshot_device,
    "snapshot_fleet": _snapshot_fleet,
    "restore_device": _restore_device,
    "accept_baseline": _accept_baseline,
    "diff_device": _diff_device,
    "check_drift": _check_drift,
    "get_drift_alerts": _get_drift_alerts,
    "test_device_credentials": _test_device_credentials,
    "discover_network_devices": _discover_network_devices,
    "register_discovered_device": _register_discovered_device,
    "reconcile_device_addresses": _reconcile_device_addresses,
    "create_snapshot_schedule": _create_snapshot_schedule,
    "list_snapshot_schedules": _list_snapshot_schedules,
    "update_snapshot_schedule": _update_snapshot_schedule,
    "delete_snapshot_schedule": _delete_snapshot_schedule,
    "run_snapshot_schedule": _run_snapshot_schedule,
    "get_fleet_settings": _get_fleet_settings,
    "set_fleet_setting": _set_fleet_setting,
    "provision_device": _provision_device,
    "queue_device_recovery": _queue_device_recovery,
    "list_device_recovery": _list_device_recovery,
    "cancel_device_recovery": _cancel_device_recovery,
    "list_tasks": _list_tasks,
    "search_audit_log": _search_audit_log,
    "search_activity": _search_activity,
    "download_firmware": _download_firmware,
    "import_firmware": _import_firmware,
    "list_cached_firmware": _list_cached_firmware,
    "list_rule_capabilities": _list_rule_capabilities,
    "create_action_rule": _create_action_rule,
    "delete_action_rule": _delete_action_rule,
    "list_demos": _list_demos,
    "get_demo": _get_demo,
    "create_demo": _create_demo,
    "update_demo": _update_demo,
    "delete_demo": _delete_demo,
    "assign_demo_fragment": _assign_demo_fragment,
    "adopt_demo": _adopt_demo,
    "deactivate_demo": _deactivate_demo,
    "demo_setup_status": _demo_setup_status,
    "survey_demo_evidence": _survey_demo_evidence,
    "infer_demos": _infer_demos,
    "list_demo_proposals": _list_demo_proposals,
    "confirm_demo_proposal": _confirm_demo_proposal,
    "dismiss_demo_proposal": _dismiss_demo_proposal,
    "set_event_ingest": _set_event_ingest,
    "prepare_demo": _prepare_demo,
    "end_demo": _end_demo,
    "create_temp_credentials": _create_temp_credentials,
    "cleanup_temp_credentials": _cleanup_temp_credentials,
    "get_advanced_capabilities": _get_advanced_capabilities,
}
