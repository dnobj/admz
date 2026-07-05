"""Device event **action rules** — create / list / delete over SOAP.

ADMZ does not compose rules itself. The axis-api-atlas rule-builder pillar
(``Atlas.build_rule``) renders the two device-proven SOAP bodies
(``AddActionConfiguration`` + ``AddActionRule``) from a
``(model, condition_id, action_token, param_choices)`` selection, applying the
verified per-model ``ui_to_soap`` value maps and picking the StartEvent-vs-
Conditions trigger shape. This package is the thin **consumer**: it runs the
rendered bodies against a device through the shared VAPIX executor, parses the
``ConfigurationID`` / ``RuleID`` the device returns, and tears rules down.

See ``admz/rules/runner.py`` for the SOAP sequence and ADR-0043 for the design.
"""

from admz.rules.runner import (  # noqa: F401
    RuleRunnerError,
    create_rule,
    delete_rule,
    list_rules,
    parse_rules,
    redact_soap_body,
)
