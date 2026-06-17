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

    def test_renders_without_stray_format_placeholders(self):
        """Regression: the prompt is rendered via str.format(user_line=...),
        so any literal brace (e.g. the confirm URL '/confirm/{token}') must be
        escaped as '{{...}}'. An unescaped brace raises KeyError at runtime and
        the chat stream silently returns empty. Building the prompt must not
        raise, and the rendered confirm-URL pattern must survive intact."""
        prompt = build_system_prompt("alice")  # must not raise KeyError
        assert "/confirm/{token}" in prompt

    def test_execute_operation_before_confirm_guidance(self):
        """Live bug: the model resolved an op via query_catalog, then asked in
        text and called confirm_dangerous_operation WITHOUT ever calling
        execute_operation — so no confirm_token was minted and confirm failed
        with 'Invalid or expired confirmation token'. The prompt must make
        execute_operation the first write step (it is gated/safe) and forbid
        calling the confirm tool without a token from a blocked
        execute_operation response."""
        prompt = build_system_prompt("alice").lower()
        # execute_operation is framed as safe-to-call / the way to request a write
        assert "safe to call" in prompt or "always safe" in prompt or "is how you request a write" in prompt
        # Never call the confirm tool without a real token
        assert "never call" in prompt and "confirm_dangerous_operation" in prompt
        assert "confirm_token" in prompt

    def test_device_recovery_guidance(self):
        """GH #49 v1: after an approved reboot (or "is it up yet?"), the LLM
        should call await_device_recovery, and re-call with the returned
        baseline_bootid on still_waiting instead of guessing or using the
        lagging health cache."""
        prompt = build_system_prompt("alice")
        assert "await_device_recovery" in prompt
        assert "still_waiting" in prompt
        assert "baseline_bootid" in prompt

    def test_resolve_device_id_yourself_guidance(self):
        """Live bug: user said "make the D4200 flash white" and the LLM
        replied "I need the device_id (MAC address) for the D4200 ...
        can you please provide it" — stalling instead of resolving the
        model reference itself. The prompt must tell the LLM to resolve
        device_ids via search_devices/list_devices and NOT ask the user
        for the MAC."""
        prompt = build_system_prompt("alice").lower()
        # Names the resolution tool(s).
        assert "search_devices" in prompt
        assert "list_devices" in prompt
        # Frames resolution as the LLM's own job ("resolve it yourself").
        assert "resolve it yourself" in prompt or "your job" in prompt
        # Explicitly forbids asking the user for the device_id / MAC.
        assert (
            "never ask the user to give you the device_id" in prompt
            or "never ask the user for the device_id" in prompt
            or ("never ask the user" in prompt and "mac address" in prompt)
        )

    def test_narrow_param_read_guidance(self):
        """Latency fix: a bare param.cgi:list dumps the whole tree (~150k-token
        turns). The prompt must steer the LLM to discover the group index then
        narrow with group=, not blind-guess subgroups."""
        prompt = build_system_prompt("alice").lower()
        assert "group=" in prompt
        assert "discover, then narrow" in prompt or "group index" in prompt
        # The Axis-structure hint that fixed the volume-hunt failure.
        assert "root.audiosource" in prompt


class TestPreloadedContext:
    """device_roster / common_ops preload (admz.chatbot.context)."""

    _ROSTER = "- C1710 (E827250959C6) · 192.168.1.123 · online · tags: lab"
    _OPS = "- Reboot / restart the device: `restart.cgi:restart`"

    def test_roster_omitted_by_default(self):
        prompt = build_system_prompt("alice")
        assert "# Current fleet" not in prompt
        assert "# Common operations" not in prompt

    def test_roster_injected_when_provided(self):
        prompt = build_system_prompt("alice", device_roster=self._ROSTER)
        assert "# Current fleet" in prompt
        assert "E827250959C6" in prompt
        # The framing must tell the model NOT to call a tool to resolve.
        assert "do not call" in prompt.lower()

    def test_common_ops_injected_when_provided(self):
        prompt = build_system_prompt("alice", common_ops=self._OPS)
        assert "# Common operations" in prompt
        assert "restart.cgi:restart" in prompt

    def test_empty_strings_inject_nothing(self):
        prompt = build_system_prompt("alice", device_roster="  ", common_ops="")
        assert "# Current fleet" not in prompt
        assert "# Common operations" not in prompt

    def test_preload_preserves_safety_mandate(self):
        """Preloading context must NOT drop the query_catalog mandate or the
        device-id guidance."""
        prompt = build_system_prompt(
            "alice", device_roster=self._ROSTER, common_ops=self._OPS
        )
        low = prompt.lower()
        assert "query_catalog" in low and "execute_operation" in low
        assert "mandatory" in low or "always call" in low
        # common_ops must still tell the model to verify params via query_catalog
        assert "query_catalog" in prompt  # section text references it

    def test_renders_without_stray_placeholders_with_preload(self):
        prompt = build_system_prompt(
            "alice", device_roster=self._ROSTER, common_ops=self._OPS
        )
        assert "/confirm/{token}" in prompt  # escaped brace survived
        assert "{device_roster}" not in prompt
        assert "{fleet_section}" not in prompt
        assert "{common_ops_section}" not in prompt
