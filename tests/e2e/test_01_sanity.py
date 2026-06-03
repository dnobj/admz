"""Sanity check: /api/chat responds, no-tool turn works."""

from __future__ import annotations


def test_no_tool_turn_returns_response(chat, cost_recorder):
    """A bare text-generation turn (use_tools=False) succeeds + returns
    measurable tokens. Catches: chat endpoint dead, Gemini API key not
    configured, SDK regression, basic streaming/SSE broken."""
    result = chat(
        "Respond with exactly the word: alive",
        use_tools=False,
    )
    cost_recorder(result)
    assert result.success, f"chat failed: {result.error!r}"
    assert result.response.strip(), f"empty response: {result!r}"
    assert result.output_tokens > 0, (
        f"output_tokens=0 — possible 'AFC empty response' regression "
        f"(see CR-22). Full result: {result!r}"
    )
    assert result.error is None
    # Sanity on the model field.
    assert result.model.startswith("gemini-"), f"unexpected model {result.model!r}"


def test_tools_enabled_turn_does_not_block(chat, cost_recorder):
    """A simple tool-enabled turn should respond in reasonable time
    (well under our 240s timeout). Catches: MCP pool dead, hang on
    tool list, the 'silent stall' bug we built the SSE timeout for."""
    result = chat("How many devices do I have? Reply with just the number.")
    cost_recorder(result)
    assert result.success, f"chat failed: {result.error!r}"
    assert result.response.strip()
    assert result.elapsed < 90, (
        f"tool-enabled turn took {result.elapsed:.0f}s — "
        f"a tool-bounded reply that takes >90s is almost always a hang. "
        f"{result!r}"
    )
