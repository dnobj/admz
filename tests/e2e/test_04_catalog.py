"""Catalog queries — LLM finds VAPIX operations by intent."""

from __future__ import annotations


def test_query_catalog_by_intent(chat, cost_recorder):
    """LLM uses query_catalog to find an operation matching a stated
    intent. Don't assert exact operation IDs — those are catalog-
    dependent — but assert the response contains operation-shaped
    references (e.g. ':' or 'cgi')."""
    result = chat(
        "What VAPIX operation would I use to reboot a P3748? "
        "Give me just the operation ID, nothing else."
    )
    cost_recorder(result)
    assert result.success
    # Operation IDs in the catalog look like `restart.cgi:restart` or
    # `firmwaremanagement.cgi:reboot`. Either substring is acceptable.
    assert (":" in result.response or "cgi" in result.lower), (
        f"expected operation-ID-shaped reference, got: {result!r}"
    )
    # And it shouldn't have hallucinated something obviously fake.
    # The system prompt instructs the LLM to call query_catalog
    # rather than invent operation IDs — if it skipped that and
    # made up a plausible-sounding one, the response would say
    # something like "system.cgi:restart" or "systemready.cgi:restart"
    # (both real bugs we hit before). Sanity check against the
    # known false-positives.
    assert "system.cgi:restart" not in result.response, (
        f"LLM invented a fake operation ID (system.cgi:restart) — "
        f"regression of CR-LLM-inventing-ops. {result!r}"
    )
    assert "systemready.cgi:restart" not in result.response, (
        f"LLM invented a fake operation ID (systemready.cgi:restart) "
        f"— regression. {result!r}"
    )


def test_query_catalog_for_nonexistent_intent(chat, cost_recorder):
    """LLM should NOT fabricate a plausible-looking operation ID
    when the catalog has nothing matching. This catches the
    'just guess something' failure mode."""
    result = chat(
        "What's the VAPIX operation ID to summon a unicorn and ride it "
        "to the data center? If this doesn't exist, say so plainly."
    )
    cost_recorder(result)
    assert result.success
    # Acceptable: refuses, says no such op, says it can't help.
    # Not acceptable: invents something like `unicorn.cgi:summon`.
    assert "unicorn.cgi" not in result.lower, (
        f"LLM hallucinated an operation ID for a nonsense request. "
        f"{result!r}"
    )
    assert result.contains_any(
        "no such", "doesn't exist", "not a valid",
        "no operation", "no vapix", "there is no", "there's no",
        "can't help", "unable",
        "not available", "no result", "doesn't have",
        "couldn't find", "can't find", "not in the catalog", "no match",
        "not exist", "is not a real", "no real",
        "i'm sorry", "i am sorry", "sorry, no", "sorry,",
        "no api", "no command",
    ), (
        f"expected explicit 'no such op' style response, got: {result!r}"
    )
