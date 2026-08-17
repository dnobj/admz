"""Model profiles and the dialect adapter (ADR-0060, FR-CB-015, GH #407).

The adapter is the reason this subsystem exists: ``gemini-3.7-flash`` replaced
``thinking_budget`` with ``thinking_level``, and the old key cannot simply be
dropped because 2.5 still needs it. Every test asserting one key is present
also asserts the OTHER IS ABSENT — "3.7 gets thinking_level" passes just as
well if the adapter emits nothing at all.
"""

from __future__ import annotations

import datetime as dt

import pytest

from admz.chatbot import models as m


# ── the dialect adapter ─────────────────────────────────────────────────────

def test_a_37_model_gets_thinking_level_and_NOT_thinking_budget():
    cfg = m.thinking_config("gemini-3.7-flash")
    assert cfg == {"thinking_config": {"thinking_level": "medium"}}
    assert "thinking_budget" not in cfg["thinking_config"], (
        "3.7 removed the numeric parameter; sending it is the 'selectable and "
        "broken' failure this table exists to prevent"
    )


def test_a_25_model_gets_thinking_budget_and_NOT_thinking_level():
    """Control for the test above — the other direction must also hold."""
    cfg = m.thinking_config("gemini-2.5-flash")
    assert cfg == {"thinking_config": {"thinking_budget": -1}}
    assert "thinking_level" not in cfg["thinking_config"]


@pytest.mark.parametrize("model_id", ["gemini-3.7-flash", "gemini-3.6-flash"])
def test_every_level_family_member_uses_the_level_dialect(model_id):
    assert "thinking_level" in m.thinking_config(model_id)["thinking_config"]


@pytest.mark.parametrize(
    "model_id",
    ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-pro-preview",
     "gemini-3.1-flash-lite", "gemini-2.5-pro", "gemini-2.5-flash",
     "gemini-2.5-flash-lite"],
)
def test_every_budget_family_member_uses_the_budget_dialect(model_id):
    assert "thinking_budget" in m.thinking_config(model_id)["thinking_config"]


def test_default_reasoning_is_DYNAMIC_on_the_budget_dialect():
    """-1 is load-bearing, not a default nobody chose.

    client.py records that with thinking disabled, 2.5-flash answers device
    questions from wrong training priors instead of calling query_catalog, and
    the -pro models reject a budget of 0 outright.
    """
    assert m.thinking_config("gemini-2.5-flash")["thinking_config"]["thinking_budget"] == -1


def test_off_and_hard_map_to_both_dialects():
    assert m.thinking_config("gemini-2.5-flash", m.REASONING_OFF) == {
        "thinking_config": {"thinking_budget": 0}}
    assert m.thinking_config("gemini-3.7-flash", m.REASONING_OFF) == {
        "thinking_config": {"thinking_level": "low"}}
    assert m.thinking_config("gemini-3.7-flash", m.REASONING_HARD) == {
        "thinking_config": {"thinking_level": "high"}}


def test_a_budget_override_applies_to_the_budget_dialect_only():
    """ADMZ_GEMINI_THINKING_BUDGET and the empty-retry's fixed budget.

    A number means nothing on 3.7, so it must not leak there — silently
    accepting one would put an unknown parameter on the wire.
    """
    assert m.thinking_config("gemini-2.5-flash", budget_override=1024) == {
        "thinking_config": {"thinking_budget": 1024}}
    assert m.thinking_config("gemini-3.7-flash", budget_override=1024) == {
        "thinking_config": {"thinking_level": "medium"}}


def test_a_live_audio_model_gets_no_thinking_parameter_at_all():
    assert m.thinking_config("gemini-3.1-flash-live-preview") == {}


def test_an_unknown_model_falls_back_to_the_budget_dialect():
    """A guess either way; guessing the older form means an unknown model
    behaves like the nine before it rather than like the one that changed."""
    assert "thinking_budget" in m.thinking_config("gemini-99-nonexistent")["thinking_config"]


# ── the table is the single source ──────────────────────────────────────────

def test_selectable_models_comes_from_the_table():
    from admz.chatbot import config

    assert config.SELECTABLE_MODELS == m.selectable_models()


def test_the_new_models_are_actually_offered():
    """The point of #407 for the operator: these were researched, planned, and
    then not selectable, because ADR-0060 shipped the decision without them."""
    from admz.chatbot import config

    for model_id in ("gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"):
        assert model_id in config.SELECTABLE_MODELS


def test_pricing_comes_from_the_table_and_covers_every_selectable_model():
    from admz.chatbot import usage

    for model_id in m.selectable_models():
        assert model_id in usage.PRICING, f"{model_id} is offered with no price"
        assert usage.estimate_cost_usd(model_id, 1_000_000, 0) is not None


def test_voice_models_come_from_the_table():
    from admz.chatbot import voice

    assert voice.VOICE_MODELS == m.live_audio_models()
    assert voice.DEFAULT_VOICE_MODEL in voice.VOICE_MODELS


def test_no_live_audio_model_is_offered_in_the_chat_picker():
    """They take audio, not a chat turn — offering one would be a dead option."""
    assert not set(m.selectable_models()) & set(m.live_audio_models())


# ── prices expire ───────────────────────────────────────────────────────────

def test_an_expired_price_is_reported(monkeypatch):
    """gemini-3.7-flash's rate is introductory and ends 2026-12-31.

    Driven with a fixed clock rather than trusting the check to fire on the
    day — a date-dependent assertion that only becomes true in January is one
    nobody will see fail.
    """
    assert "gemini-3.7-flash" in m.stale_prices(dt.date(2027, 1, 1))


def test_the_same_price_is_NOT_reported_before_it_expires():
    """Control for the test above."""
    assert "gemini-3.7-flash" not in m.stale_prices(dt.date(2026, 8, 16))


def test_a_model_with_no_expiry_never_goes_stale():
    assert "gemini-2.5-flash" not in m.stale_prices(dt.date(2099, 1, 1))


def test_every_profile_declares_a_known_dialect():
    known = {m.DIALECT_BUDGET, m.DIALECT_LEVEL, m.DIALECT_NONE}
    wrong = [p.id for p in m.PROFILES if p.dialect not in known]
    assert not wrong, f"unknown dialect on {wrong}"


# ── the contract test that would have caught #436 ───────────────────────────

@pytest.mark.parametrize("profile", [p for p in m.PROFILES], ids=lambda p: p.id)
def test_every_profiles_config_is_accepted_by_the_SDK(profile):
    """The adapter's output must satisfy the object that consumes it.

    #436: the REST API documents `thinking_level` in the generation config, so
    the adapter emitted it as a top-level key. google-genai's
    GenerateContentConfig forbids extra fields, so every gemini-3.7 turn died
    with `extra_forbidden` — in production, on the first real use. The field
    had been on ThinkingConfig since 2.5.0; only the envelope was wrong.

    The unit tests could not catch it: they asserted the adapter returned what
    I believed the shape to be, which is the same belief that was wrong. This
    asserts against the SDK instead of against my reading of the docs.
    """
    types = pytest.importorskip("google.genai.types")
    for reasoning in (m.REASONING_DEFAULT, m.REASONING_OFF, m.REASONING_HARD):
        cfg = m.thinking_config(profile.id, reasoning)
        types.GenerateContentConfig(**cfg)


def test_a_budget_override_also_produces_a_valid_config():
    """The env override and the empty-retry's fixed budget travel the same path."""
    types = pytest.importorskip("google.genai.types")
    for model_id in m.selectable_models():
        types.GenerateContentConfig(**m.thinking_config(model_id, budget_override=1024))
