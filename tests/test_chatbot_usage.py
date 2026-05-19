"""Tests for admz.chatbot.usage — pricing, store, budget."""

import pytest

from admz.chatbot import usage as usage_mod
from admz.chatbot.usage import (
    DailyUsage,
    PRICING,
    TokenUsageStore,
    check_budget,
    estimate_cost_usd,
    get_daily_budget,
    set_daily_budget,
)


@pytest.fixture(autouse=True)
def isolate_db(tmp_path, monkeypatch):
    """Each test gets a fresh DB + the fleet_settings + token_usage
    singletons pointed at it, with originals restored on teardown."""
    db_path = str(tmp_path / "admz.db")
    monkeypatch.setenv("ADMZ_DB_PATH", db_path)

    from admz import fleet_settings as fs_module

    _orig_fs = fs_module.fleet_settings
    _orig_usage = usage_mod.token_usage

    fs_module.fleet_settings = fs_module.FleetSettings(db_path)
    usage_mod.token_usage = TokenUsageStore(db_path)

    try:
        yield
    finally:
        fs_module.fleet_settings = _orig_fs
        usage_mod.token_usage = _orig_usage


# ---------------------------------------------------------------------------
# Pricing table + cost estimator
# ---------------------------------------------------------------------------


class TestPricing:
    def test_pricing_covers_selectable_models(self):
        from admz.chatbot.config import SELECTABLE_MODELS
        for model in SELECTABLE_MODELS:
            assert model in PRICING, f"missing pricing for {model}"

    def test_pro_more_expensive_than_flash_lite(self):
        # Sanity: Pro > Flash > Flash-Lite on both axes
        assert (
            PRICING["gemini-2.5-pro"].input_per_million_usd
            > PRICING["gemini-2.5-flash-lite"].input_per_million_usd
        )
        assert (
            PRICING["gemini-2.5-pro"].output_per_million_usd
            > PRICING["gemini-2.5-flash-lite"].output_per_million_usd
        )

    def test_cost_for_pro(self):
        # 1M in + 1M out on 2.5-pro = $1.25 + $10.00 = $11.25
        cost = estimate_cost_usd("gemini-2.5-pro", 1_000_000, 1_000_000)
        assert cost == pytest.approx(11.25, rel=1e-6)

    def test_cost_for_flash_lite_typical_turn(self):
        # 1000 in + 200 out on Flash-Lite
        # = 1000 × 0.10/1M + 200 × 0.40/1M
        # = 0.0001 + 0.00008 = 0.00018
        cost = estimate_cost_usd("gemini-2.5-flash-lite", 1000, 200)
        assert cost == pytest.approx(0.00018, rel=1e-3)

    def test_cost_for_unknown_model_is_none(self):
        assert estimate_cost_usd("gemini-99-fake", 1000, 200) is None

    def test_zero_tokens_zero_cost(self):
        assert estimate_cost_usd("gemini-2.5-pro", 0, 0) == 0.0


# ---------------------------------------------------------------------------
# TokenUsageStore: append / aggregate
# ---------------------------------------------------------------------------


class TestUsageStore:
    def test_record_turn_creates_row(self):
        usage_mod.token_usage.record_turn(
            principal="AXIS\\alice",
            model="gemini-2.5-pro",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0008,
        )
        summary = usage_mod.token_usage.today_summary("AXIS\\alice")
        assert summary.input_tokens == 100
        assert summary.output_tokens == 50
        assert summary.total_tokens == 150
        assert summary.turn_count == 1
        assert summary.cost_usd == pytest.approx(0.0008)

    def test_record_turn_aggregates_same_model(self):
        for _ in range(3):
            usage_mod.token_usage.record_turn(
                principal="alice",
                model="gemini-2.5-pro",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.0001,
            )
        summary = usage_mod.token_usage.today_summary("alice")
        assert summary.input_tokens == 30
        assert summary.output_tokens == 15
        assert summary.turn_count == 3

    def test_record_turn_aggregates_across_models(self):
        usage_mod.token_usage.record_turn(
            principal="alice",
            model="gemini-2.5-pro",
            input_tokens=100,
            output_tokens=50,
        )
        usage_mod.token_usage.record_turn(
            principal="alice",
            model="gemini-2.5-flash-lite",
            input_tokens=200,
            output_tokens=100,
        )
        summary = usage_mod.token_usage.today_summary("alice")
        assert summary.total_tokens == 450
        assert summary.turn_count == 2

    def test_two_principals_are_isolated(self):
        usage_mod.token_usage.record_turn(
            principal="alice",
            model="gemini-2.5-pro",
            input_tokens=100,
            output_tokens=50,
        )
        usage_mod.token_usage.record_turn(
            principal="bob",
            model="gemini-2.5-pro",
            input_tokens=999,
            output_tokens=999,
        )
        assert usage_mod.token_usage.today_summary("alice").total_tokens == 150
        assert usage_mod.token_usage.today_summary("bob").total_tokens == 1998

    def test_unknown_principal_returns_zeros(self):
        summary = usage_mod.token_usage.today_summary("nobody")
        assert summary.total_tokens == 0
        assert summary.turn_count == 0
        assert summary.cost_usd == 0.0


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


class TestBudget:
    def test_default_budget_is_unlimited(self):
        assert get_daily_budget() == 0  # 0 means unlimited

    def test_unlimited_check_always_allows(self):
        # No matter how much was already used, budget=0 lets through.
        usage_mod.token_usage.record_turn(
            principal="alice",
            model="gemini-2.5-pro",
            input_tokens=10_000_000,
            output_tokens=10_000_000,
        )
        result = check_budget("alice")
        assert result.allowed is True

    def test_set_then_get(self):
        set_daily_budget(50_000)
        assert get_daily_budget() == 50_000

    def test_set_zero_disables(self):
        set_daily_budget(50_000)
        set_daily_budget(0)
        assert get_daily_budget() == 0

    def test_negative_budget_rejected(self):
        with pytest.raises(ValueError):
            set_daily_budget(-1)

    def test_invalid_persisted_value_treated_as_unlimited(self):
        from admz.fleet_settings import fleet_settings as fs
        fs.set("chat_daily_token_budget", "not-an-int")
        assert get_daily_budget() == 0

    def test_check_under_budget_allows(self):
        set_daily_budget(1000)
        usage_mod.token_usage.record_turn(
            principal="alice",
            model="gemini-2.5-pro",
            input_tokens=100,
            output_tokens=50,
        )
        result = check_budget("alice")
        assert result.allowed is True
        assert result.used_today == 150
        assert result.budget == 1000

    def test_check_at_budget_blocks(self):
        set_daily_budget(150)
        usage_mod.token_usage.record_turn(
            principal="alice",
            model="gemini-2.5-pro",
            input_tokens=100,
            output_tokens=50,
        )
        result = check_budget("alice")
        # used == budget → blocked (next turn would push over).
        assert result.allowed is False
        assert "150" in result.reason

    def test_check_over_budget_blocks(self):
        set_daily_budget(100)
        usage_mod.token_usage.record_turn(
            principal="alice",
            model="gemini-2.5-pro",
            input_tokens=500,
            output_tokens=200,
        )
        result = check_budget("alice")
        assert result.allowed is False
        assert "700" in result.reason
        assert "00:00 UTC" in result.reason

    def test_check_isolated_per_principal(self):
        set_daily_budget(100)
        usage_mod.token_usage.record_turn(
            principal="alice",
            model="gemini-2.5-pro",
            input_tokens=500,
            output_tokens=0,
        )
        # Bob hasn't used anything.
        assert check_budget("alice").allowed is False
        assert check_budget("bob").allowed is True
