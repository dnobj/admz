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
        name="survey_demo_evidence",
        description=(
            "READ-ONLY: build the demo-inference EVIDENCE GRAPH for the whole "
            "site (#124) and return its summary — every device with its tags and "
            "installed analytics apps, every action rule from BOTH sources (ACS "
            "action rules and device-side rules) with the devices it links, and "
            "the weighted edges between devices with the exact evidence for each "
            "(E1/E2 = ACS rule topology, E3 = a device rule naming another "
            "device, E4 = shared tag, E6 = shared distinctive app, E5 = shared "
            "name token). Use it to answer 'what demos already exist here?', "
            "'what is this device for?' or 'which devices work together?' when "
            "no demo has been defined yet. Also reports unresolved references "
            "and per-rule firing observability. Reads the registry, the last "
            "snapshots and ACS — never probes a device, never writes anything, "
            "and degrades with a reason when ACS isn't connected. It does NOT "
            "propose or create demos."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": ("Return a previous run's graph instead of "
                                    "collecting a fresh one."),
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="infer_demos",
        description=(
            "Read the whole site and PROPOSE the demo inventory (#124): builds "
            "the evidence graph (registry + last snapshots + ACS action rules), "
            "clusters it, and returns scored CANDIDATE demos — each with a "
            "deterministic name, its member devices and roles, the rules that "
            "link them (with firing observability), the exact evidence and "
            "score breakdown behind it, and the config keys it probably owns. "
            "Use for 'what demos already exist here?' or on a fresh install. "
            "Read-only: no device is touched, no ACS write, and NOTHING becomes "
            "a demo until confirm_demo_proposal. Present each proposal with its "
            "evidence and confidence and let the user decide — a low-confidence "
            "proposal is a question, not a finding. Degrades with a reason when "
            "ACS is not connected."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "include_weak": {
                    "type": "boolean",
                    "description": (
                        "Default true. Keep true on most sites: many fleets have "
                        "NO cross-device rule topology at all, so every cluster "
                        "rests on corroborating evidence (shared tag/app/name) "
                        "and is flagged no_topology + capped at low confidence. "
                        "Set false for topology-backed proposals only."),
                },
                "include_acs": {
                    "type": "boolean",
                    "description": "Default true. False skips the ACS read entirely.",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="list_demo_proposals",
        description=(
            "READ-ONLY: the candidate demos a previous infer_demos run produced, "
            "strongest first. Pass `proposal` (name or id) for ONE proposal's "
            "full detail — every evidence item with its weight, the score "
            "breakdown term by term, each linked rule with its observability, "
            "the suggested owned config keys, and any overlap with another "
            "proposal. Never runs inference itself."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "proposal": {
                    "type": "string",
                    "description": "One proposal's name or id — returns full detail.",
                },
                "status": {
                    "type": "string",
                    "description": ("proposed (default) | confirmed | dismissed | "
                                    "superseded | all"),
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="confirm_demo_proposal",
        description=(
            "Turn a proposal into a REAL demo (ADR-0046): creates it with the "
            "member devices, roles, rule membership and auto-derived signals. "
            "Name, purpose, devices and roles are all overridable — correct them "
            "here rather than accepting a guess. The proposed name is a "
            "DETERMINISTIC PLACEHOLDER (top shared name token + a role hint), so "
            "normally you SHOULD pass a better `name` and a `purpose` read off "
            "the evidence; omitting them keeps the placeholder. Writes NO config "
            "fragments: the "
            "demo owns nothing yet, so it changes no drift verdict; the "
            "suggested keys stay evidence until captured the normal way "
            "(check_drift + assign_demo_fragment). Touches no device. ONLY call "
            "after the user has seen the proposal's evidence and said yes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "proposal": {"type": "string",
                             "description": "The proposal's name or id."},
                "name": {"type": "string",
                         "description": "Override the proposed name."},
                "purpose": {"type": "string",
                            "description": ("The demo's narrative — what you say "
                                            "while showing it.")},
                "device_ids": {"type": "array", "items": {"type": "string"},
                               "description": "Override the member device list."},
                "roles": {"type": "object",
                          "description": "Override {device_id: role}."},
                "tag": {"type": "string",
                        "description": ("Scope the demo by tag instead of the "
                                        "explicit device list.")},
            },
            "required": ["proposal"],
        },
    ),
    Tool(
        name="dismiss_demo_proposal",
        description=(
            "Record that a proposal is NOT a demo. Remembered — re-running "
            "inference will not propose those devices again. Nothing is deleted "
            "and no device is touched."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "proposal": {"type": "string",
                             "description": "The proposal's name or id."},
                "reason": {"type": "string",
                           "description": "Why — kept in the audit trail."},
            },
            "required": ["proposal"],
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
