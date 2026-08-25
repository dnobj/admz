"""MCP Tool definitions: product knowledge + capability lookup."""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="query_knowledge",
        description=(
            "Look up product-specific knowledge and hints for a device. "
            "Returns hints from the product hierarchy (product → series → "
            "product line) about API support, limitations, and device-specific "
            "workflows. Use this to understand device capabilities before "
            "attempting operations."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID to query for",
                },
                "topic": {
                    "type": "string",
                    "description": (
                        "Optional topic to filter by. "
                        "e.g. 'vapix-support', 'poe', 'audio'"
                    ),
                    "default": "",
                },
            },
            "required": ["device_id"],
        },
    ),
    Tool(
        name="check_api_support",
        description=(
            "Check whether a device supports a specific catalog API. Answers "
            "are TRI-STATE and ordered by trust (ADR-0063): a non-stale LOCAL "
            "record of what this device's APIs actually answered wins "
            "(match='local', source='probe'); otherwise the model-level atlas "
            "snapshot at the device's EXACT firmware (match='exact'). "
            "supported=null means NOT KNOWN — no capabilities file for the "
            "model, no snapshot at this firmware, unknown firmware, or local "
            "reads that failed without proof (see notes). Never report null "
            "as 'the device lacks it' — say it could not be verified. An "
            "ATLAS false means 'not in that getApiList snapshot' — legacy "
            "CGIs and SOAP APIs never appear in one, so only a LOCAL row is "
            "device proof either way. Useful for filtering plan steps before "
            "execution. Omit api_id for the full snapshot plus the device's "
            "own recorded capabilities."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID to check",
                },
                "api_id": {
                    "type": "string",
                    "description": (
                        "Catalog api_id (from an _api.yaml file) to check support "
                        "for. Omit to return the full snapshot of supported APIs."
                    ),
                },
            },
            "required": ["device_id"],
        },
    ),
    Tool(
        name="list_device_capabilities",
        description=(
            "What ADMZ has learned about ONE device's actual APIs — the local "
            "capability record (ADR-0063), written by the drift audit's own "
            "reads and by getApiList surveys. Each row: probe_key (catalog "
            "api id), classification (present / absent / absent_unconfirmed), "
            "the firmware it was observed under, source (audit|discovery), "
            "when, and whether the row is stale (firmware changed or lease "
            "expired). This is DEVICE truth: prefer it over check_api_support "
            "(model-level atlas data) when they disagree. 'absent' means the "
            "device answered 'no such API'; 'absent_unconfirmed' means reads "
            "failed without proof — say 'could not verify', never 'the device "
            "lacks it'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID (MAC), from list_devices.",
                },
            },
            "required": ["device_id"],
        },
    ),
]
