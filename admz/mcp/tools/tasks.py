"""MCP Tool definitions: unified Tasks view (ADR-0037).

A single read across both task kinds — time-based **schedules** (snapshot /
drift_audit / survey) and trigger-based **detection** tasks (e.g. re-provision
when a device returns factory-defaulted). Creating/managing tasks still uses the
per-kind tools (``create_snapshot_schedule`` …, ``queue_device_recovery`` …),
which now share the same underlying store.
"""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="list_tasks",
        description=(
            "List ALL automated tasks in one view: time-based schedules "
            "(recurring snapshot / drift_audit / survey jobs) AND trigger-based "
            "detection tasks (one-shot, fire when a device's state matches — e.g. "
            "re-provision when it returns factory-defaulted). Use this for "
            "questions like 'what's scheduled or queued?'. Optionally filter by "
            "device_id (tasks targeting that device) or kind ('schedule' or "
            "'detection'). Read-only."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Optional: only tasks targeting this device.",
                },
                "kind": {
                    "type": "string",
                    "description": "Optional filter: 'schedule' or 'detection'.",
                    "enum": ["schedule", "detection"],
                },
            },
            "required": [],
        },
    ),
]
