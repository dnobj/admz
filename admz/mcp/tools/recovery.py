"""MCP Tool definitions: deferred device recovery (factory-defaulted → re-provision).

These let the chatbot queue a *pre-authorized* follow-up that fires when a device
next reports factory-defaulted (needsetup) — the trigger-based counterpart to the
time-based snapshot schedules. The health-monitor sweep is the evaluator; the
actual re-provision runs only because the operator authorized it here, up front.
"""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="queue_device_recovery",
        description=(
            "Pre-authorize a recovery that runs automatically when a device next "
            "reports factory-defaulted (needsetup). Use this AFTER a factory reset "
            "(or for a device already showing 'Needs setup') so the chat doesn't "
            "have to wait ~1-2 min for the reboot: the queued action fires on the "
            "next health check once the device comes back. Currently supports "
            "intent='reprovision' — re-creates the admin account from the fleet "
            "default password (the password is never shown). The device must be a "
            "registered device_id. This is a deliberate authorization: only queue "
            "it when the operator has asked to recover the device. Returns a "
            "pending_id you can later cancel. Requires an authenticated principal."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": (
                        "Registered device ID (MAC, e.g. 'B8A44F661A2F'), NOT the "
                        "model name."
                    ),
                },
                "intent": {
                    "type": "string",
                    "description": "Recovery to run when it returns. Only 'reprovision' for now.",
                    "enum": ["reprovision"],
                    "default": "reprovision",
                },
                "username": {
                    "type": "string",
                    "description": "Admin username to create on re-provision (default 'root').",
                    "default": "root",
                },
            },
            "required": ["device_id"],
        },
    ),
    Tool(
        name="list_device_recovery",
        description=(
            "List active (pending) deferred recovery actions. Pass a device_id to "
            "scope to one device, or omit it for all devices. Read-only; use it to "
            "tell the user what recovery is queued and its pending_id."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Optional registered device ID to scope the list.",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="cancel_device_recovery",
        description=(
            "Cancel a still-pending deferred recovery by its pending_id (from "
            "queue_device_recovery or list_device_recovery). No-op if it already "
            "fired or doesn't exist."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pending_id": {
                    "type": "string",
                    "description": "The pending action id to cancel.",
                },
            },
            "required": ["pending_id"],
        },
    ),
]
