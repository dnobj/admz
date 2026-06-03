"""MCP Tool definitions: snapshot schedules."""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="create_snapshot_schedule",
        description=(
            "Create a recurring scheduled job. Despite the legacy "
            "name, this can schedule any registered job type — set "
            "`job_type` to 'snapshot' (default) or 'drift_audit' "
            "(periodic config-audit). Jobs run automatically at the "
            "specified interval. Use interval like '30m', '2h', '1d', "
            "or '12h'. See FR-SCH-010..014 and ADR-0026."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "schedule_id": {
                    "type": "string",
                    "description": (
                        "Unique ID for this schedule "
                        "(e.g. 'nightly-all', 'hourly-lobby', "
                        "'daily-drift-audit')"
                    ),
                },
                "description": {
                    "type": "string",
                    "description": (
                        "Human-readable description"
                    ),
                },
                "interval": {
                    "type": "string",
                    "description": (
                        "How often to run. Examples: "
                        "'30m', '2h', '1d', '12h'"
                    ),
                },
                "job_type": {
                    "type": "string",
                    "enum": ["snapshot", "drift_audit"],
                    "default": "snapshot",
                    "description": (
                        "Which kind of job to run. 'snapshot' (default) "
                        "captures device config to git on a cadence. "
                        "'drift_audit' runs check_fleet_drift and emits "
                        "transition alerts when drift state changes. "
                        "Both honor tag_filter / device_ids."
                    ),
                },
                "tag_filter": {
                    "type": "string",
                    "description": (
                        "Only operate on devices with this tag. "
                        "Omit to operate on all devices."
                    ),
                },
                "device_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Specific device IDs to operate on. "
                        "Omit to use tag_filter or all devices."
                    ),
                },
            },
            "required": ["schedule_id", "description", "interval"],
        },
    ),
    Tool(
        name="list_snapshot_schedules",
        description=(
            "List all configured snapshot schedules with their "
            "status, last run time, and next run time."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="update_snapshot_schedule",
        description=(
            "Update an existing schedule. Can change interval, "
            "enable/disable, change tag filter, etc."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "schedule_id": {
                    "type": "string",
                    "description": "Schedule ID to update",
                },
                "interval": {
                    "type": "string",
                    "description": "New interval (e.g. '1h')",
                },
                "enabled": {
                    "type": "boolean",
                    "description": "Enable or disable",
                },
                "tag_filter": {
                    "type": "string",
                    "description": "New tag filter",
                },
                "description": {
                    "type": "string",
                    "description": "New description",
                },
            },
            "required": ["schedule_id"],
        },
    ),
    Tool(
        name="delete_snapshot_schedule",
        description="Delete a snapshot schedule.",
        inputSchema={
            "type": "object",
            "properties": {
                "schedule_id": {
                    "type": "string",
                    "description": "Schedule ID to delete",
                },
            },
            "required": ["schedule_id"],
        },
    ),
    Tool(
        name="run_snapshot_schedule",
        description=(
            "Manually trigger a scheduled snapshot right now, "
            "without waiting for the next interval."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "schedule_id": {
                    "type": "string",
                    "description": "Schedule ID to run",
                },
            },
            "required": ["schedule_id"],
        },
    ),
]
