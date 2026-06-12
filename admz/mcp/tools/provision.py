"""MCP Tool definitions: device provisioning."""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="provision_device",
        description=(
            "Provision credentials on an Axis device. Probes the device first, "
            "then takes the appropriate action based on its state: "
            "(1) Factory-default: creates an admin user with a password. "
            "(2) Legacy default password (root/pass): stores creds, suggests rotation. "
            "(3) Unknown password: returns error — use capture_credentials instead. "
            "Password priority: explicit param > fleet default_password setting > auto-generated. "
            "Generated passwords are stored in the registry and NEVER returned in the response "
            "or exposed to the LLM, and are never displayed in the web UI; ADMZ uses them only "
            "at execution time to reach the device. Rotate via the out-of-band capture flow. "
            "If only host is provided (no device_id), auto-registers the device using "
            "its MAC address (= serial number) as the device_id."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Existing device ID in registry",
                },
                "host": {
                    "type": "string",
                    "description": (
                        "IP/hostname to probe. If device doesn't exist, "
                        "auto-registers using MAC as device_id."
                    ),
                },
                "username": {
                    "type": "string",
                    "description": "Username for the account (default: 'root')",
                    "default": "root",
                },
                "password": {
                    "type": "string",
                    "description": (
                        "Specific password to set. If omitted, uses fleet "
                        "default_password setting, or generates a secure one."
                    ),
                },
                "force_change": {
                    "type": "boolean",
                    "description": (
                        "If true, change the password even if stored creds "
                        "already work. Useful for rotating passwords."
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
    ),
]
