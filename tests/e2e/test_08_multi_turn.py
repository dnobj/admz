"""Multi-turn — conversation context carries between requests.

Each /api/chat call is independent at the HTTP level but the route
reads chat_history per principal and includes prior turns in the
prompt. This test pins that behavior.
"""

from __future__ import annotations


def test_followup_references_prior_turn(chat, cost_recorder):
    """Turn 1: ask about a specific device, with a directive prompt
    so the LLM definitely looks it up. Turn 2: refer to the same
    device only as 'that device'. The LLM should know which one we
    mean from the prior turn's history."""
    # Turn 1: be directive so Gemini calls the tool rather than
    # hallucinating that the device doesn't exist.
    turn1 = chat(
        "Use the get_device tool to look up B8A44FD0257C "
        "(an AXIS P3748-PLVE that's registered in my system). "
        "Then tell me its model in one short sentence."
    )
    cost_recorder(turn1)
    assert turn1.success
    assert "p3748" in turn1.lower, (
        f"turn 1 didn't surface the model — multi-turn test is "
        f"compromised. {turn1!r}"
    )

    # Turn 2 uses pronoun reference. If history isn't being threaded,
    # the LLM will say "which device?" or give a generic answer.
    turn2 = chat(
        "What's its IP address? Just the IP, nothing else."
    )
    cost_recorder(turn2)
    assert turn2.success

    # Either we get a 192.168.x.x address, or the LLM clearly
    # references the device we just asked about (suggesting it
    # tried to look it up).
    import re
    has_ip = bool(re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", turn2.response))
    has_device_ref = "b8a44fd0257c" in turn2.lower or "p3748" in turn2.lower
    assert has_ip or has_device_ref, (
        f"turn 2 didn't carry the device context from turn 1 — "
        f"chat_history threading appears broken. turn2: {turn2!r}"
    )
    # And it shouldn't ask "which device" — that would mean it
    # totally lost the context.
    assert not turn2.contains_any(
        "which device", "what device", "specify the device",
        "no device referenced", "no device specified",
    ), (
        f"turn 2 asks which device — context wasn't preserved. {turn2!r}"
    )
