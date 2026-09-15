"""MCP Tool definitions: removing several devices with one approval (ADR-0069).

One tool. ``delete_device`` removes one device behind one approval card, so a
request to remove eleven devices was eleven cards — and on 2026-09-15 that
chain broke after the first. ADR-0067's one approval for a batch covers catalog
operations only, and registry removal is not one, so it can never be a plan
step. ``delete_devices`` is its batch path instead.

The handler (``ADMZMCPServer._delete_devices``) and the executor
(``operations._action_delete_devices``) carry the decisions: every id checked
before anything is created, single removal's gate unchanged, and each device
removed through single removal's own executor. This module is the schema the
model selects on, which is why its description leads with when to use it.

Appended after ``capabilities`` in ``MIGRATED_TOOLS``, so the frozen tool order
in ``tests/test_mcp_tool_order.py`` gains one name at its end.
"""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="delete_devices",
        description=(
            "Use this when the user wants MORE THAN ONE device removed from "
            "the registry ('remove all devices', 'delete these three "
            "cameras'). It requests removing every listed device behind ONE "
            "approval card for the whole batch, instead of a card per device "
            "from repeated delete_device calls. Returns blocked:true with one "
            "confirm_url; nothing is removed until the user approves that "
            "card, and then every listed device is removed along with its "
            "stored information and accounts. The physical devices are "
            "untouched and their git config history is retained.\n\n"
            "Every id must be a registered device_id: ONE unknown id rejects "
            "the WHOLE request and creates nothing, so take the ids from "
            "list_devices or search_devices first. Registry removal is not a "
            "catalog operation, so it can never be a create_plan step; this "
            "tool is the batch path for it."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": (
                        "Every device ID to remove, as returned by "
                        "list_devices or search_devices"
                    ),
                },
            },
            "required": ["device_ids"],
        },
    ),
]
