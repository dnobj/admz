"""MCP Tool definitions: device event **action rules** (create / list / delete).

High-level tools so the model never hand-assembles the multi-call SOAP rule
choreography (which blew the tool-iteration cap in the past). The atlas composes
the rule; ADMZ gates and runs it. See ADR-0043.
"""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="list_rule_capabilities",
        description=(
            "Discover what device automation RULES a device supports, and list "
            "its current rules. Call this FIRST when the user wants to create, "
            "change, or remove an event rule (e.g. 'play a sound when input 2 "
            "activates', 'flash the LED when motion is detected'). Returns the "
            "event CONDITIONS (triggers) and ACTIONS available for the device's "
            "model — each with its id/token, human label, parameter choices, and "
            "`notes` (survey caveats — READ them when choosing between similar "
            "conditions) — plus `current_rules` (rule_id + name) and "
            "`device_applications` (which analytics ACAPs actually run on this "
            "unit). Prefer conditions published by a Running application; a "
            "condition whose app is absent or stopped never fires. Pick a "
            "`condition_id` and `action_token` from this result, then call "
            "create_action_rule. If the model isn't surveyed, `available` is "
            "false with a reason — tell the user rather than guessing. Read-only."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device whose rule capabilities + current rules to list",
                },
            },
            "required": ["device_id"],
        },
    ),
    Tool(
        name="create_action_rule",
        description=(
            "Create a device event rule that runs an action whenever a trigger "
            "fires (e.g. input port 2 activates → play an audio clip). The rule "
            "is composed for you from the device's survey — do NOT hand-assemble "
            "SOAP or call action-service operations directly. Choose `condition_id` "
            "and `action_token` from list_rule_capabilities, and pass "
            "`param_choices` keyed by the parameter's label or SOAP name (e.g. "
            "{'Clip':'ding dong'} or {'color':'green,none'}). This is a GATED "
            "action: it returns a confirmation card for the user to approve; the "
            "rule is only created after approval. If the action needs recipient "
            "credentials (an HTTP/SMTP notification), a secure prompt collects "
            "them — NEVER ask the user for a password in chat. Surface any "
            "prerequisites/warnings from the result to the user."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Target device"},
                "condition_id": {
                    "type": "string",
                    "description": "Trigger id from list_rule_capabilities.conditions[].id",
                },
                "action_token": {
                    "type": "string",
                    "description": "Action id from list_rule_capabilities.actions[].token",
                },
                "param_choices": {
                    "type": "object",
                    "description": (
                        "Parameter values keyed by the param's label or SOAP name. "
                        "Omit a param to accept its device default. Do NOT include "
                        "secret values (login/password) — those are captured securely."
                    ),
                    "additionalProperties": {"type": "string"},
                },
                "rule_name": {
                    "type": "string",
                    "description": "Short human name for the rule (e.g. 'ding-dong on input 2')",
                },
            },
            "required": ["device_id", "condition_id", "action_token"],
        },
    ),
    Tool(
        name="delete_action_rule",
        description=(
            "Remove an event rule from a device by its rule_id (get the id from "
            "list_rule_capabilities.current_rules). The linked action "
            "configuration is removed too. GATED: returns a confirmation card; "
            "the rule is removed only after the user approves."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Device the rule is on"},
                "rule_id": {
                    "type": "string",
                    "description": "RuleID to remove (from list_rule_capabilities.current_rules)",
                },
            },
            "required": ["device_id", "rule_id"],
        },
    ),
]
