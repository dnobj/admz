"""Per-principal per-day token-usage store + budget + pricing (Phase 5D).

Three concerns:

  - **Usage tracking** — record tokens consumed per principal per
    UTC day. Backed by SQLite (the shared admz.db), keyed by
    (principal, day_utc, model). One row per (principal, day, model).
  - **Budget enforcement** — a fleet-wide setting
    ``chat_daily_token_budget`` caps how many *total* tokens any
    one principal can consume in a single UTC day. Defaults to
    "unlimited" (0). When set, exceeding the budget rejects the
    next chat turn with a budget-exceeded event.
  - **Pricing** — embedded $/M-token rates for the three
    selectable Gemini 3.1 models (May 2026). Used to compute an
    approximate USD cost per turn for the footer telemetry.

The budget is intentionally per-day and per-principal, not
per-organization. The intent is to keep one runaway user from
burning the company's API budget — not to do precise accounting.
For real cost accounting, operators export the audit log.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import admz.fleet_settings as _fs_module

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing table — $ per 1M tokens. Source: ADR-0025 + Gemini API docs
# (May 2026). Keep in sync with admz/chatbot/config.py SELECTABLE_MODELS.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelPricing:
    input_per_million_usd: float
    output_per_million_usd: float


PRICING: dict[str, ModelPricing] = {
    "gemini-3.1-pro": ModelPricing(2.00, 12.00),
    "gemini-3.1-flash": ModelPricing(0.30, 2.00),
    "gemini-3.1-flash-lite": ModelPricing(0.25, 1.50),
}


def estimate_cost_usd(
    model: str, input_tokens: int, output_tokens: int
) -> Optional[float]:
    """Approximate USD cost for a single turn.

    Returns None when the model isn't in our pricing table (e.g.
    operator configured a custom Gemini variant). The displayed
    footer falls back to showing only the token counts in that
    case.
    """
    price = PRICING.get(model)
    if price is None:
        return None
    return (
        input_tokens * price.input_per_million_usd / 1_000_000.0
        + output_tokens * price.output_per_million_usd / 1_000_000.0
    )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_token_usage (
    principal      TEXT NOT NULL,
    day_utc        TEXT NOT NULL,
    model          TEXT NOT NULL,
    input_tokens   INTEGER NOT NULL DEFAULT 0,
    output_tokens  INTEGER NOT NULL DEFAULT 0,
    cost_usd       REAL NOT NULL DEFAULT 0.0,
    turn_count     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (principal, day_utc, model)
);
"""


def _default_db_path() -> Path:
    return Path(
        os.getenv("ADMZ_DB_PATH", str(Path.home() / ".admz" / "admz.db"))
    )


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _fs():
    """Late-bind fleet_settings the way config.py does (tests swap it)."""
    return _fs_module.fleet_settings


@dataclass
class DailyUsage:
    """Per-principal usage summary for one UTC day."""

    principal: str
    day_utc: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    turn_count: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class TokenUsageStore:
    """SQLite-backed per-principal per-day usage store."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        try:
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
                conn.commit()
        except sqlite3.Error as exc:  # pragma: no cover — defensive
            logger.warning("TokenUsageStore table creation failed: %s", exc)

    def record_turn(
        self,
        *,
        principal: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Optional[float] = None,
    ) -> None:
        """Append one turn's usage to today's row for (principal, model)."""
        day = _today_utc()
        cost = cost_usd if cost_usd is not None else 0.0
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO chat_token_usage "
                "(principal, day_utc, model, input_tokens, output_tokens, cost_usd, turn_count) "
                "VALUES (?, ?, ?, ?, ?, ?, 1) "
                "ON CONFLICT(principal, day_utc, model) DO UPDATE SET "
                "    input_tokens  = input_tokens  + excluded.input_tokens, "
                "    output_tokens = output_tokens + excluded.output_tokens, "
                "    cost_usd      = cost_usd      + excluded.cost_usd, "
                "    turn_count    = turn_count    + 1",
                (
                    principal,
                    day,
                    model,
                    int(input_tokens),
                    int(output_tokens),
                    float(cost),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def today_total_tokens(self, principal: str) -> int:
        """Sum of input+output tokens across all models for today."""
        day = _today_utc()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) "
                "FROM chat_token_usage WHERE principal=? AND day_utc=?",
                (principal, day),
            ).fetchone()
        finally:
            conn.close()
        return int(row[0] if row else 0)

    def today_summary(self, principal: str) -> DailyUsage:
        """Aggregated usage for ``principal`` today across all models."""
        day = _today_utc()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT "
                "  COALESCE(SUM(input_tokens), 0), "
                "  COALESCE(SUM(output_tokens), 0), "
                "  COALESCE(SUM(cost_usd), 0.0), "
                "  COALESCE(SUM(turn_count), 0) "
                "FROM chat_token_usage WHERE principal=? AND day_utc=?",
                (principal, day),
            ).fetchone()
        finally:
            conn.close()
        return DailyUsage(
            principal=principal,
            day_utc=day,
            input_tokens=int(row[0] if row else 0),
            output_tokens=int(row[1] if row else 0),
            cost_usd=float(row[2] if row else 0.0),
            turn_count=int(row[3] if row else 0),
        )


# Module-level singleton.
token_usage = TokenUsageStore()


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


_FS_BUDGET_KEY = "chat_daily_token_budget"


def get_daily_budget() -> int:
    """Return the configured per-principal daily token budget.

    A value of 0 (default) means "no budget" — turns aren't
    rejected on token count. The fleet setting is a string from
    the UI; we parse it tolerantly and fall back to 0 on bad input.
    """
    raw = _fs().get(_FS_BUDGET_KEY)
    if raw is None or raw == "":
        return 0
    try:
        value = int(raw)
    except (ValueError, TypeError):
        logger.warning(
            "Invalid %s=%r in fleet settings; treating as unlimited.",
            _FS_BUDGET_KEY,
            raw,
        )
        return 0
    return max(value, 0)


def set_daily_budget(value: int) -> None:
    """Persist the daily token budget. ``0`` disables enforcement."""
    if value < 0:
        raise ValueError("Daily token budget must be >= 0 (0 disables)")
    _fs().set(_FS_BUDGET_KEY, str(int(value)))


@dataclass
class BudgetCheck:
    allowed: bool
    used_today: int
    budget: int  # 0 means unlimited

    @property
    def reason(self) -> str:
        if self.allowed:
            return ""
        return (
            f"Daily chatbot token budget reached "
            f"({self.used_today:,}/{self.budget:,} tokens). "
            f"Resets at 00:00 UTC."
        )


def check_budget(principal: str) -> BudgetCheck:
    """Decide whether ``principal`` may start a new turn today."""
    budget = get_daily_budget()
    if budget == 0:
        return BudgetCheck(allowed=True, used_today=0, budget=0)
    used = token_usage.today_total_tokens(principal)
    return BudgetCheck(
        allowed=used < budget,
        used_today=used,
        budget=budget,
    )
