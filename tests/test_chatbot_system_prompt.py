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
