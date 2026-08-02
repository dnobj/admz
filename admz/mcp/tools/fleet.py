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
            "Set the fleet default credentials used when provisioning "
            "devices. Only two keys can be set here: 'default_password' "
            "and 'default_username'. Every other fleet setting is "
            "protected and must be changed by an operator from the web UI "
            "or the admz CLI — do not attempt them, and tell the user to "
            "make the change themselves. "
            "For 'default_password', ALWAYS omit 'value': that returns a "
            "one-time capture URL the user opens to type the password "
            "outside the chat, so it never enters the conversation. "
            "Passing a password as 'value' is refused. "
            "Set value to an empty string to delete 'default_username'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "enum": ["default_password", "default_username"],
                    "description": (
                        "Setting key. Only 'default_password' and "
                        "'default_username' are writable."
                    ),
                },
                "value": {
                    "type": "string",
                    "description": (
                        "Setting value, for 'default_username' only. Empty "
                        "string deletes the key. Must be omitted for "
                        "'default_password' — omitting it returns a capture "
                        "URL instead."
                    ),
                },
            },
            "required": ["key"],
        },
    ),
]
