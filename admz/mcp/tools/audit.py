"""MCP Tool definitions: audit-log search (who-did-what)."""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="search_audit_log",
        description=(
            "Search the ADMZ audit log — the who-did-what record of every "
            "operation, approval, schedule run, recovery, login, and config "
            "change. Use it to answer questions like 'who factory-defaulted "
            "device X?', 'who approved the reboot of Y?', 'what did <user> "
            "change today?', 'what failed in the last day?', or 'what's "
            "happened to device X this week?'. Read-only.\n\n"
            "ALWAYS narrow with a time range so results stay relevant: pass "
            "`within` (e.g. '24h', '7d') or explicit `since`/`before`. Combine "
            "with `device_id` (matches the device anywhere in the entry), "
            "`actor` (who), `action` (substring, e.g. 'execute_operation', "
            "'confirm.approve', 'recovery', 'snapshot'), `query` (free text), "
            "and `success`. The definitive 'who did the destructive thing' "
            "row is usually `confirm.approve` (it carries the approver + the "
            "device + the operation, and for a rule create/delete the rule id "
            "and config id it acted on — so 'who created rule 175?' is "
            "answerable by id rather than by matching a rule name).\n\n"
            "For drift-over-time ('has device Y drifted in the past week') use "
            "`get_drift_alerts` instead — that history lives in a separate "
            "drift table, not the audit log."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Only entries that touched this device (MAC).",
                },
                "actor": {
                    "type": "string",
                    "description": "Who did it — substring of the requester "
                                   "(e.g. 'alice', 'chat', 'scheduler').",
                },
                "action": {
                    "type": "string",
                    "description": "Action substring (e.g. 'execute_operation', "
                                   "'confirm.approve', 'recovery', 'snapshot', "
                                   "'login', 'delete').",
                },
                "query": {
                    "type": "string",
                    "description": "Free-text substring across action / resource / "
                                   "details / error (e.g. 'factorydefault', 'reboot').",
                },
                "within": {
                    "type": "string",
                    "description": "Relative time window ending now: '30m', '2h', "
                                   "'24h', '7d', '1w'. Preferred way to limit results.",
                },
                "since": {
                    "type": "string",
                    "description": "Lower time bound — ISO-8601 or a unix timestamp. "
                                   "Use instead of `within` for an explicit start.",
                },
                "before": {
                    "type": "string",
                    "description": "Upper time bound — ISO-8601 or a unix timestamp.",
                },
                "success": {
                    "type": "boolean",
                    "description": "true = only successes, false = only failures.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows, newest first (default 30, max 200).",
                },
            },
            "required": [],
        },
    ),
]
