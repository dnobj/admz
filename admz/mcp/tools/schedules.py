"""MCP Tool definitions: snapshot schedules."""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="create_snapshot_schedule",
        description=(
            "Create a recurring snapshot schedule. Snapshots run "
            "automatically at the specified interval. Use "
            "interval like '30m', '2h', '1d', or '12h'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "schedule_id": {
                    "type": "string",
                    "description": (
                        "Unique ID for this schedule "
                        "(e.g. 'nightly-all', 'hourly-lobby')"
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
                "tag_filter": {
                    "type": "string",
                    "description": (
                        "Only snapshot devices with this tag. "
                        "Omit to snapshot all devices."
                    ),
                },
                "device_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Specific device IDs to snapshot. "
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
