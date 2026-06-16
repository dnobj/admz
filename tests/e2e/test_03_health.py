"""Fleet health — get_fleet_health, get_device_health."""

from __future__ import annotations


def test_fleet_health_summary(chat, cost_recorder):
    """LLM can summarize the fleet's reachability state.

    HISTORY: this prompt used to flake — on a COLD conversation (the suite
    clears history per test) gemini-2.5-flash returns an empty candidate
    (finish_reason=STOP, 0 parts, 0 output) at a high rate for fleet-summary
    prompts. Root cause: the DYNAMIC thinking budget (-1) lets the model think
    0 tokens and emit 0 output. Fixed in client._run_manual_tool_loop, which
    now re-asks an empty response with a FIXED thinking budget (verified cold
    10/10). Left here as a live guard that the fix holds."""
    result = chat(
        "Give me a brief fleet health summary. How many devices are "
        "online vs unreachable? Just the counts."
    )
    cost_recorder(result)
    assert result.success
    # The response should mention numbers + at least one of the
    # status states. Don't assert WHICH numbers (depends on real
    # state at test time).
    import re
    has_a_number = bool(re.search(r"\b\d+\b", result.response))
    assert has_a_number, f"expected numeric counts in response: {result!r}"
    assert result.contains_any(
        "online", "unreachable", "reachable", "responsive", "alive",
        "down", "offline", "healthy",
    ), f"no health-state language in response: {result!r}"


def test_single_device_health(chat, cost_recorder):
    """LLM can report on one specific device's reachability."""
    result = chat(
        "Is device B8A44FD0257C currently online or unreachable? "
        "One word answer."
    )
    cost_recorder(result)
    assert result.success
    assert result.contains_any(
        "online", "unreachable", "reachable", "offline", "down",
        "alive", "responsive", "no record",
    ), f"no clear online/offline answer: {result!r}"
