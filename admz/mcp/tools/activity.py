"""MCP Tool definitions: search the live device-event stream (ADR-0041).

``search_activity`` queries the event store that the ingest supervisor fills from
each device's VAPIX WebSocket — motion, object detection, I/O, PTZ, tampering,
storage, and system events. Read-only; this is the agent's window onto what
devices are actually *doing* (vs ``search_audit_log``, which is what *operators*
did).
"""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="search_activity",
        description=(
            "Search the live device-event feed — the stream of things devices "
            "report happening: motion, object detection, I/O port changes, PTZ "
            "moves, tampering, storage and system events, streamed from each "
            "device over WebSocket. Use it to answer 'what's device X been doing?', "
            "'has there been motion on the lobby cameras today?', 'did any I/O "
            "port fire in the last hour?', 'show recent PTZ activity'. Read-only.\n\n"
            "This is distinct from `search_audit_log` (who-did-what operator "
            "actions) and `get_drift_alerts` (config drift). Narrow with `device` "
            "(device-name substring) or `device_id` (exact MAC), `type` (ONVIF "
            "topic substring, e.g. 'Motion', 'IO/Port', 'PTZController'), and "
            "`within` (e.g. '1h', '24h') to keep results relevant. Ingest must be "
            "on for new events to arrive (the Activity page toggles it); this tool "
            "reads whatever has already been captured."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device": {
                    "type": "string",
                    "description": "Device-name substring (case-insensitive).",
                },
                "device_id": {
                    "type": "string",
                    "description": "Exact device MAC.",
                },
                "type": {
                    "type": "string",
                    "description": "ONVIF topic substring (e.g. 'Motion', 'VMD', "
                                   "'IO/Port', 'PTZController', 'Casing', 'Storage').",
                },
                "within": {
                    "type": "string",
                    "description": "Relative time window ending now: '30m', '2h', "
                                   "'24h', '7d'. Strongly recommended.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max events, newest first (default 50, max 500).",
                },
            },
            "required": [],
        },
    ),
]
