"""MCP Tool definitions: fleet-wide settings."""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="get_fleet_settings",
        description=(
            "List all fleet-wide settings. Returns key-value pairs "
            "for configuration that applies across all managed devices."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="set_fleet_setting",
        description=(
            "Set a fleet-wide setting. Known keys: "
            "'default_password' — password used by provision_device "
            "instead of generating a random one. "
            "Set value to empty string to delete the setting. "
            "For password settings, omit 'value' to generate a "
            "secure capture URL where the user can enter the "
            "password outside the chat (never touches LLM context)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Setting key (e.g. 'default_password')",
                },
                "value": {
                    "type": "string",
                    "description": (
                        "Setting value. Empty string deletes the key. "
                        "Omit for password keys to get a capture URL instead."
                    ),
                },
            },
            "required": ["key"],
        },
    ),
]
