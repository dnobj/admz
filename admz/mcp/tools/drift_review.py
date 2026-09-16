"""MCP Tool definitions: reviewing drift in the chat (ADR-0070 §3).

Four tools give the chat the web UI's per-field drift review. The reads are
``get_drift_review`` and ``list_config_ignore_rules``. The writes are
``revert_drift``, which returns one plan card, and ``ignore_config_keys``,
which returns one action card. Accepting is the existing ``accept_baseline``,
which gained ``note`` and ``ignore_keys``.

The descriptions carry the safety semantics and the order rule, because they
are what the model selects on (FR-MCP-016): triage is a hint and never a
verdict; a revert is its own card and is never followed by ``execute_plan``;
and a revert comes before an accept, with a refreshed review between them.
Accept blesses an observation that already exists, and a revert records none,
so accepting straight after a revert would bless the values it just undid.

Appended after ``device_removal`` in ``MIGRATED_TOOLS``, so the frozen tool
order in ``tests/test_mcp_tool_order.py`` gains these names at its end.
"""

from typing import List

from mcp.types import Tool

#: The order rule, in the words both write tools and accept_baseline use.
ORDER_RULE = (
    "ORDER when a review both reverts and accepts: ignore_keys ride the accept "
    "card; call revert_drift FIRST, wait for the [console] note saying it "
    "executed, then call get_drift_review with refresh=true, and only then "
    "accept_baseline. Accept blesses an observation that already exists and "
    "a revert records none, so accepting before the refresh would bless the "
    "values the revert just undid. If the revert FAILED, stop — accept "
    "nothing on top of it."
)

TRIAGE_CLASSES = [
    "demo_set", "demo_broken", "demo_candidate", "security_sensitive",
    "cosmetic", "firmware_managed", "added_key", "runtime_state", "read_only",
    "service_config", "uncategorized",
]

TOOLS: List[Tool] = [
    Tool(
        name="get_drift_review",
        description=(
            "Read a device's drift as a REVIEW: every drifted field with its "
            "baseline and live values, whether a targeted revert can write it "
            "back, and ADMZ's triage — a class (e.g. cosmetic, "
            "firmware_managed, security_sensitive), an importance and a "
            "recommendation — plus whether the firmware changed since the "
            "baseline, the last accept note, and the ignore rules already in "
            "force. Rows come most important first. Use this, not "
            "check_drift, whenever the user wants to review, accept, revert "
            "or exclude drift. The triage is a HINT, never a verdict: every "
            "row is still drift, and the user decides. By default it reads "
            "the cached review with no device traffic; refresh=true probes "
            "the device now and RECORDS A FRESH OBSERVATION — do that after a "
            "revert has executed and before accepting."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Device ID"},
                "refresh": {
                    "type": "boolean",
                    "description": (
                        "Probe the device now and record a fresh observation "
                        "instead of reading the cached review. Default false."
                    ),
                },
                "classes": {
                    "type": "array",
                    "items": {"type": "string", "enum": TRIAGE_CLASSES},
                    "description": "Only list fields of these triage classes.",
                },
                "include_fields": {
                    "type": "boolean",
                    "description": (
                        "false returns the summary only (counts, classes, "
                        "firmware context). Default true."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Most fields to list. Default 40.",
                },
            },
            "required": ["device_id"],
        },
    ),
    Tool(
        name="revert_drift",
        description=(
            "Revert chosen drifted fields on ONE device back to their baseline "
            "values. Builds a minimal plan from the reviewed diff and returns "
            "ONE approval card for it — blocked:true with a confirm_url; "
            "nothing is written until the user approves that card, and you "
            "must NOT call execute_plan for it. Omit `fields` to revert every "
            "revertable drifted field. Fields ADMZ cannot write back "
            "(read-only, added on the device, owned by an active demo) are "
            "skipped and listed with a reason; fields not in the drift are "
            "listed as not_found. " + ORDER_RULE
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Device ID"},
                "fields": {
                    "type": "array",
                    "maxItems": 200,
                    "items": {
                        "type": "object",
                        "properties": {
                            "facet": {"type": "string"},
                            "path": {"type": "string"},
                        },
                        "required": ["facet", "path"],
                    },
                    "description": (
                        "The fields to revert, as get_drift_review lists them "
                        "({facet, path}). Omit to revert every revertable "
                        "drifted field."
                    ),
                },
                "note": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "Why — shown on the card and in the audit.",
                },
            },
            "required": ["device_id"],
        },
    ),
    Tool(
        name="ignore_config_keys",
        description=(
            "Exclude config keys from drift tracking — the chat's version of "
            "the web UI's eye-slash. Returns ONE approval card naming every "
            "key and the scope; the rules are written only when the user "
            "approves. A global rule silently hides future changes to those "
            "keys on EVERY device until someone removes it in Settings. Use "
            "it only for noise — values the device or the network manages, "
            "or firmware bookkeeping — and NEVER to silence a "
            "security_sensitive or service_config key. Keys already excluded "
            "in that scope open no card. When the user is also accepting, "
            "pass the keys as accept_baseline's ignore_keys instead, so one "
            "card covers both."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 50,
                    "description": (
                        "Canonical keys as get_drift_review lists them (e.g. "
                        "root.Properties.FirmwareManagement.Version), or globs "
                        "(root.Properties.FirmwareManagement.*)."
                    ),
                },
                "scope": {
                    "type": "string",
                    "description": (
                        "'global' (default, every device), 'tag:<tag>' or "
                        "'device:<device_id>'."
                    ),
                },
                "reason": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Why these keys are noise — shown on the card.",
                },
            },
            "required": ["keys"],
        },
    ),
    Tool(
        name="list_config_ignore_rules",
        description=(
            "List the rules that exclude keys from drift tracking — the "
            "shipped defaults and every rule an operator added. Read-only."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "description": (
                        "Only rules with exactly this scope: 'global', "
                        "'tag:<tag>' or 'device:<device_id>'."
                    ),
                },
            },
            "required": [],
        },
    ),
]
