"""MCP Tool definitions: device provisioning."""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="provision_device",
        description=(
            "Provision credentials on a FACTORY-DEFAULTED (needsetup) Axis device "
            "— first-time setup or post-factory-reset recovery ONLY. Registers the "
            "device if you gave only a host, then runs the same credential "
            "resolution onboard_device does, so the outcome and the statuses are "
            "identical to that tool. "
            "A factory-defaulted device gets TWO accounts: 'root' set to the fleet "
            "root password, then ADMZ's own 'admz' account with a "
            "generated password — and ONLY the admz password is stored. A root "
            "credential is never stored per device (ADR-0068). If no fleet root "
            "password is configured it writes nothing and says so. "
            "Creating an account is gated: expect an approval card. "
            "Do NOT use this to set/change/rotate the password on a healthy, "
            "already-managed device — that is the out-of-band capture flow "
            "(capture_credentials). "
            "You cannot choose any password here, and there is no argument for one: "
            "root's comes from the fleet setting, admz's is generated and must stay "
            "unknown, and the fleet default_password is an entry credential that is "
            "never written to a device (FR-CRED-007). Stored passwords are NEVER "
            "returned in the response or exposed to the LLM, and are never displayed "
            "in the web UI; ADMZ uses them only at execution time to reach the "
            "device. For human login mint a short-lived account with "
            "create_temp_credentials. "
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
                        "auto-registers using MAC as device_id. Ignored when "
                        "device_id names a registered device — the registry is "
                        "authoritative for the address."
                    ),
                },
            },
            "required": [],
        },
    ),
]
