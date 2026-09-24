"""MCP Tool definitions: deferred device recovery (factory-defaulted → setup notice).

These let the chatbot queue a follow-up that fires when a device next reports
factory-defaulted (needsetup) — the trigger-based counterpart to the time-based
snapshot schedules. The health-monitor sweep is the evaluator. Since ADR-0068 the
follow-up never provisions unattended: it raises a Console notice so a person
onboards the device, behind the usual approval.
"""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="queue_device_recovery",
        description=(
            "Queue a follow-up for when a device next reports factory-defaulted "
            "(needsetup). Use it AFTER a factory reset, so the chat doesn't have to "
            "wait ~1-2 min for the reboot. When the device comes back, the next health "
            "check raises a Console notice ('Factory-reset — onboard it to set it "
            "up'); reviewing that notice brings the device back to the chat to be "
            "onboarded with onboard_device, behind the usual approval. It does NOT "
            "set the device up by itself: since ADR-0068 ADMZ never writes the fleet "
            "root password unattended. For a device ALREADY showing 'Needs setup', "
            "don't queue anything — call onboard_device now. The only intent is "
            "'reprovision' (the name is historical). The device must be a "
            "registered device_id. Returns a pending_id you can later cancel. "
            "Requires an authenticated principal."
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
                    "description": "What to do when it returns. Only 'reprovision', which raises a setup notice.",
                    "enum": ["reprovision"],
                    "default": "reprovision",
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
