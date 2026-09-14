"""The plan tools' descriptions are the artefact the model selects on (#438).

Same standard as ``TestRegisterDiscoveredDescriptionMatchesBehaviour`` in
tests/test_mcp_tool_order.py (#366): this is not the source-string theatre that
gets removed on sight. There, a string stood in for behaviour; here the string
**is** the artefact — the description is the contract the model reads at
runtime, and production measured the cost of getting it wrong (4 create_plan
calls ever, against 53 confirm.approve).

Two assertions below are deliberately tied to the code the text describes, so
the pair cannot drift apart in *either* direction.
"""

import asyncio
import inspect

from tests import mcp_harness


def _tool(name):
    from admz.mcp.server import ADMZMCPServer
    return asyncio.run(mcp_harness.find_tool(ADMZMCPServer(), name))


def _description(name):
    return _tool(name).description


class TestCreatePlanDescriptionIsATrigger:
    def test_it_says_when_to_use_it(self):
        d = _description("create_plan")
        assert "Use this when" in d
        assert "several device" in d

    def test_the_behaviour_only_wording_is_gone(self):
        """Anti-vacuity: the exact sentence #438 quotes as the defect. Without
        this, the assertions above would still pass if the old text were
        restored alongside them."""
        assert (
            "Submit a list of operations with concrete parameters"
            not in _description("create_plan")
        )

    def test_it_orders_discovery_first_and_states_the_consequence(self):
        """A bare "look the ids up first" is the kind of instruction a model
        skips; the consequence is what makes the ordering non-optional. This is
        the clause a later "tighten the prose" edit would remove first."""
        d = _description("create_plan")
        assert "query_catalog" in d
        assert "search_devices" in d
        assert "rejects the WHOLE plan" in d

    def test_it_names_the_payoff_that_competes_with_card_per_step(self):
        """Without this the description loses to the system prompt's
        "# Compound requests" section, which defines a finished job as a gated
        call — and a card — per part."""
        d = _description("create_plan")
        assert "ONE approval" in d
        assert "card per step" in d

    def test_it_states_the_anti_trigger(self):
        d = _description("create_plan")
        assert "NO data passes between them" in d
        assert "frozen" in d

    def test_the_anti_trigger_still_matches_the_engine(self):
        """Tied to behaviour, not just prose: PlanStep.condition is declared and
        the engine never reads it. When #439 lands, this fails — forcing the
        description to be corrected in the same PR rather than quietly becoming
        false. That is the anti-drift mechanism #438 item 3 asks for."""
        from admz.plans import engine as engine_mod
        assert "condition" not in inspect.getsource(engine_mod)

    def test_it_promises_nothing_the_schema_forbids(self):
        """additionalProperties: False means template/risk_level are hard
        rejections; a description hinting at them would generate guaranteed
        validation errors. (The schema side is already pinned by
        tests/test_risk_vocabulary.py — referenced, not duplicated.)"""
        d = _description("create_plan")
        for forbidden in ("template=", "risk_level"):
            assert forbidden not in d


class TestExecutePlanDescriptionMatchesTheGate:
    def test_the_phantom_reason_is_gone_from_the_description(self):
        assert (
            "plan_contains_dangerous_steps" not in _description("execute_plan")
        )

    def test_the_phantom_reason_is_absent_from_the_code_too(self):
        """Non-vacuity partner. If someone later introduces the reason for real
        without updating the description, the pair still catches the drift —
        which is the direction #366 was missed in."""
        from admz import operations
        assert "plan_contains_dangerous_steps" not in inspect.getsource(operations)

    def test_it_documents_the_url_tier_that_is_the_default(self):
        d = _description("execute_plan")
        assert "confirm_url" in d
        assert "url_and_password" in d
        assert "can never satisfy" in d

    def test_it_is_keyed_on_the_field_the_envelope_carries(self):
        """reason is a slug on one branch and a sentence on the other;
        confirmation_level is on both."""
        assert "confirmation_level" in _description("execute_plan")

    def test_it_documents_llm_confirm_as_the_non_default(self):
        d = _description("execute_plan")
        assert "plan_requires_confirmation" in d
        assert "never the default" in d

    def test_plan_id_provenance_is_not_create_plan_only(self):
        """Seven producers stage plans; the one flow that actually works in
        production is restore_device. The old text told the model its plan_id
        was not a valid argument."""
        schema = _tool("execute_plan").input_schema
        assert "restore_device" in schema["properties"]["plan_id"]["description"]

    def test_confirm_dangerous_states_its_narrow_scope(self):
        schema = _tool("execute_plan").input_schema
        assert "llm_confirm" in schema["properties"]["confirm_dangerous"]["description"]
