"""Tests for admz.chatbot.system_prompt — principal context injection."""

from admz.chatbot.system_prompt import build_system_prompt


class TestBuildSystemPrompt:
    def test_basic_principal(self):
        prompt = build_system_prompt("alice")
        assert "alice" in prompt
        assert "ADMZ" in prompt
        # Safety language must be present — the LLM sees this on every turn.
        assert "audit" in prompt.lower()
        assert "dangerous" in prompt.lower()
        assert "snapshot" in prompt.lower()

    def test_with_display_name(self):
        prompt = build_system_prompt(
            "AXIS\\alice", display_name="Alice Andersson"
        )
        assert "Alice Andersson" in prompt
        assert "AXIS\\alice" in prompt

    def test_display_name_equal_to_name_renders_once(self):
        # When display_name == name we shouldn't see "alice (alice)".
        prompt = build_system_prompt("alice", display_name="alice")
        assert prompt.count("alice") == 1

    def test_groups_rendered_sorted(self):
        prompt = build_system_prompt(
            "alice",
            display_name="Alice",
            groups=["ops-team", "admins", "ops-team"],
        )
        # Deduplicated + sorted in the user line.
        assert "admins, ops-team" in prompt
        # The "Authenticated user:" line should mention each unique group once.
        user_line = [
            ln for ln in prompt.splitlines() if ln.startswith("Authenticated user:")
        ][0]
        assert user_line.count("ops-team") == 1
        assert user_line.count("admins") == 1

    def test_no_groups_omits_group_line(self):
        prompt = build_system_prompt("alice", display_name="Alice")
        assert "groups:" not in prompt

    def test_credential_safety_in_prompt(self):
        prompt = build_system_prompt("alice")
        # The LLM must be told not to ask for passwords in chat.
        assert "capture" in prompt.lower()

    def test_device_id_guidance_in_prompt(self):
        """When listing devices, the LLM must surface device_id —
        it's the canonical identifier for follow-up commands."""
        prompt = build_system_prompt("alice")
        assert "device_id" in prompt.lower() or "device id" in prompt.lower()
        # Mention MAC to clarify the format.
        assert "mac" in prompt.lower()

    # The next four tests target the specific bugs we saw in
    # multi-turn smoke testing (see tools/chat_multiturn_test.py).
    # If anyone trims the system prompt later, these break the
    # build so the regression is visible.

    def test_model_name_vs_mac_guidance(self):
        """Bug 1: LLM was passing 'C1710' (model name) where device_id (MAC) is required."""
        prompt = build_system_prompt("alice").lower()
        assert "model name" in prompt
        assert "never" in prompt or "do not" in prompt or "don't" in prompt

    def test_no_fabricated_success_guidance(self):
        """Bug 2: LLM claimed it had snapshotted a device without firing the tool."""
        prompt = build_system_prompt("alice").lower()
        assert "never claim" in prompt or "don't fabricate" in prompt or "fabricate" in prompt

    def test_capability_discovery_guidance(self):
        """Bug 4: LLM said it couldn't reboot devices despite the catalog supporting it."""
        prompt = build_system_prompt("alice").lower()
        assert "query_catalog" in prompt
        assert "execute_operation" in prompt

    def test_no_permission_for_reads_guidance(self):
        """Bug 6: LLM kept asking permission to run read-only queries."""
        prompt = build_system_prompt("alice").lower()
        # Should explicitly tell the LLM not to ask for read-only ops.
        assert "never ask permission" in prompt or "without asking" in prompt or (
            "read-only" in prompt and "just call" in prompt
        )

    def test_dont_invent_op_ids_guidance(self):
        """LLM was guessing 'systemready.cgi:restart' (non-existent) after
        a real op call failed for a schema reason. Prompt should forbid
        this."""
        prompt = build_system_prompt("alice").lower()
        assert "never invent operation" in prompt or "do not guess" in prompt or (
            "operation id" in prompt and "guess" in prompt
        )

    def test_dont_trust_prior_failures_guidance(self):
        """LLM was reading its own earlier wrong answers from chat history
        and repeating them ("as I mentioned before, X doesn't exist"). The
        prompt should tell it to re-attempt rather than trust prior
        failure conclusions."""
        prompt = build_system_prompt("alice").lower()
        # Must mention either "don't trust prior failures" or equivalent.
        assert "prior failure" in prompt or "repeat" in prompt or (
            "history" in prompt and "fresh" in prompt
        )

    def test_confirm_token_followthrough_guidance(self):
        """When user has already consented, the LLM must IMMEDIATELY call
        confirm_dangerous_operation rather than re-asking. Live log
        showed the LLM dutifully re-asking after the user said 'yes'."""
        prompt = build_system_prompt("alice").lower()
        assert "confirm_dangerous_operation" in prompt
        # Should describe the "already consented" follow-through.
        assert "already" in prompt or "immediately" in prompt or (
            "consent" in prompt and "yes" in prompt
        )

    def test_query_catalog_before_execute_guidance(self):
        """LLM was inventing operation IDs (system.cgi:restart,
        systemready.cgi:restart) instead of querying the catalog. The
        prompt should make 'query_catalog before execute_operation'
        mandatory for any op_id not produced by a prior tool call."""
        prompt = build_system_prompt("alice").lower()
        # Mandatory directive somewhere about query_catalog before execute
        assert "mandatory" in prompt or "always call" in prompt or "always query" in prompt
        # Mentions both tool names
        assert "query_catalog" in prompt
        assert "execute_operation" in prompt
