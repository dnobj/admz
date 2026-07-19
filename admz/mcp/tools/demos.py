"""MCP Tool definitions: demos (ADR-0046/0047) — the experience-center unit of
work, managed by conversation.

A demo = named devices (each with a role) + the config that makes it work
(owned *fragment* keys over each device's baseline) + the signals that prove
it's running + the narrative. Reads and metadata edits are direct; the
drift-affecting writes (``assign_demo_fragment``, ``adopt_demo``) return the
standard approval-widget envelope, and ``prepare_demo``/``end_demo`` inherit
the gated config-push plan. Every tool accepts the demo's NAME or id.
"""

from typing import List

from mcp.types import Tool

_DEMO_REF = {
    "type": "string",
    "description": "The demo's name (case-insensitive, must be unique) or id.",
}

TOOLS: List[Tool] = [
    Tool(
        name="list_demos",
        description=(
            "List every demo with its computed READINESS (ready / not_loaded / "
            "blocked / not_ready / empty), blockers, devices, and whether it is "
            "active. Use for 'is the <X> demo ready?' / 'what demos exist?'. "
            "Read-only, cache-backed — never probes a device."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="get_demo",
        description=(
            "Full detail for ONE demo: readiness per device (role, health, "
            "config verdict), the owned config fragment per role, signals with "
            "last-seen, narrative, and activation state. Read-only."
        ),
        inputSchema={
            "type": "object",
            "properties": {"demo": _DEMO_REF},
            "required": ["demo"],
        },
    ),
    Tool(
        name="create_demo",
        description=(
            "Create a demo. Scope its devices by tag (picks up newly-tagged "
            "devices automatically) OR an explicit device_ids list. Metadata "
            "only — nothing is pushed to any device."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Demo name (required)."},
                "narrative": {
                    "type": "string",
                    "description": "What you say while showing it — the story.",
                },
                "tag": {
                    "type": "string",
                    "description": "Scope: every device carrying this tag.",
                },
                "device_ids": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Scope: an explicit device list (ignored when tag is set).",
                },
                "roles": {
                    "type": "object",
                    "description": "device_id -> role (e.g. 'detector', 'responder').",
                    "additionalProperties": {"type": "string"},
                },
                "signals": {
                    "type": "array", "items": {"type": "object"},
                    "description": (
                        "Expected events proving the demo runs: "
                        "[{label, topic|category, device_id?|role?}]."
                    ),
                },
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="update_demo",
        description=(
            "Update a demo's metadata: name, narrative, tag, device_ids, roles, "
            "signals, enabled. Send only the fields to change. Metadata only."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "demo": _DEMO_REF,
                "name": {"type": "string"},
                "narrative": {"type": "string"},
                "tag": {"type": ["string", "null"]},
                "device_ids": {"type": "array", "items": {"type": "string"}},
                "roles": {"type": "object",
                          "additionalProperties": {"type": "string"}},
                "signals": {"type": "array", "items": {"type": "object"}},
                "enabled": {"type": "boolean"},
            },
            "required": ["demo"],
        },
    ),
    Tool(
        name="delete_demo",
        description=(
            "Delete a demo and its owned config fragments (git history keeps "
            "them). Devices and their config are untouched."
        ),
        inputSchema={
            "type": "object",
            "properties": {"demo": _DEMO_REF},
            "required": ["demo"],
        },
    ),
    Tool(
        name="assign_demo_fragment",
        description=(
            "Assign currently-DRIFTED fields to a demo's owned config fragment "
            "(capture). Run check_drift on the device first and pick fields from "
            "that diff — the server re-checks and records the actual live "
            "values. Returns an APPROVAL CARD (blocked + confirm_url): present "
            "it to the user; the assignment happens only after they approve. "
            "Never claim it ran before approval."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "demo": _DEMO_REF,
                "fields": {
                    "type": "array",
                    "description": "Drifted fields to capture, from the drift diff.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "device_id": {"type": "string"},
                            "facet": {"type": "string"},
                            "path": {"type": "string"},
                        },
                        "required": ["device_id", "facet", "path"],
                    },
                },
                "role": {
                    "type": "string",
                    "description": "Optional role the fragment belongs to (default: the device's role in the demo).",
                },
                "mode": {
                    "type": "string",
                    "enum": ["set", "require"],
                    "description": (
                        "'set' (default) — a value the demo PUSHES and owns. "
                        "'require' — a value the demo only ASSERTS at readiness, "
                        "never pushed (for demo-bound drift you can't/won't write, "
                        "e.g. an observed rule or an already-in-place API value)."
                    ),
                },
            },
            "required": ["demo", "fields"],
        },
    ),
    Tool(
        name="adopt_demo",
        description=(
            "Mark a demo ACTIVE without pushing anything: its owned keys stop "
            "counting as drift and join each device's expected state on the "
            "next check. Returns an APPROVAL CARD (blocked + confirm_url) — "
            "present it; adoption happens only after the user approves. Refuses "
            "if another active demo claims the same key, or a device is held by "
            "a legacy scenario."
        ),
        inputSchema={
            "type": "object",
            "properties": {"demo": _DEMO_REF},
            "required": ["demo"],
        },
    ),
    Tool(
        name="deactivate_demo",
        description=(
            "Stop claiming a demo's keys (no push — its config stays on the "
            "devices and reads as plain drift again on the next check). Direct; "
            "only reveals drift, never masks it."
        ),
        inputSchema={
            "type": "object",
            "properties": {"demo": _DEMO_REF},
            "required": ["demo"],
        },
    ),
    Tool(
        name="prepare_demo",
        description=(
            "Load a SIDELINED demo (config_source scenario:<name>) onto its "
            "devices as ONE gated config-push plan. Returns the approval "
            "envelope (blocked + confirm_url) — present it; the push runs on "
            "approval. Refuses for baseline demos (nothing to load) and when a "
            "device is held by another scenario."
        ),
        inputSchema={
            "type": "object",
            "properties": {"demo": _DEMO_REF},
            "required": ["demo"],
        },
    ),
    Tool(
        name="end_demo",
        description=(
            "Snap a SIDELINED demo's devices back to their blessed baseline in "
            "ONE gated plan (approval envelope — present it). Refuses for "
            "baseline demos (they never left their normal state)."
        ),
        inputSchema={
            "type": "object",
            "properties": {"demo": _DEMO_REF},
            "required": ["demo"],
        },
    ),
    Tool(
        name="demo_setup_status",
        description=(
            "READ-ONLY setup checklist for a demo: devices/roles, owned config + "
            "activation, rules (recorded vs observed), signals + last-seen, and "
            "event-capture state — ending in ordered `next_actions` naming the "
            "exact remaining tool calls. Answer 'is the demo set up?' from this "
            "alone (no device probe). Report next_actions to the user in order."
        ),
        inputSchema={
            "type": "object",
            "properties": {"demo": _DEMO_REF},
            "required": ["demo"],
        },
    ),
    Tool(
        name="set_event_ingest",
        description=(
            "Turn fleet event capture on or off (needed so a demo's signals are "
            "recorded). GATED: returns an approval card — present it; capture only "
            "changes after the user approves. OFFER this when demo_setup_status "
            "shows signals but ingest off; never toggle it silently. One global "
            "flag: enabling opens a live stream per WATCHED device."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean",
                            "description": "true to start capture, false to stop"},
            },
            "required": ["enabled"],
        },
    ),
]
