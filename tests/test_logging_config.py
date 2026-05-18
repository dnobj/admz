"""Tests for admz.logging_config."""

import logging

import pytest

from admz.logging_config import resolve_log_level, configure_logging


class TestResolveLogLevel:
    """resolve_log_level: env-string → logging integer level."""

    def test_default_is_info(self):
        assert resolve_log_level(None) in (logging.INFO,)

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("INFO", logging.INFO),
            ("DEBUG", logging.DEBUG),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ],
    )
    def test_valid_levels(self, raw, expected):
        assert resolve_log_level(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("info", logging.INFO),
            ("Debug", logging.DEBUG),
            ("warning  ", logging.WARNING),
            ("  ERROR", logging.ERROR),
        ],
    )
    def test_case_insensitive_and_strips_whitespace(self, raw, expected):
        assert resolve_log_level(raw) == expected

    def test_unknown_value_falls_back_to_info(self, caplog):
        with caplog.at_level(logging.WARNING):
            level = resolve_log_level("VERBOSE")
        assert level == logging.INFO
        # Fallback should produce a visible warning
        assert any(
            "VERBOSE" in rec.message and "INFO" in rec.message
            for rec in caplog.records
        )

    def test_env_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("ADMZ_LOG_LEVEL", raising=False)
        assert resolve_log_level() == logging.INFO

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("ADMZ_LOG_LEVEL", "DEBUG")
        assert resolve_log_level() == logging.DEBUG


class TestConfigureLogging:
    """configure_logging: applies the level to the root logger."""

    def test_default_sets_info(self, monkeypatch):
        monkeypatch.delenv("ADMZ_LOG_LEVEL", raising=False)
        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_env_overrides_root_level(self, monkeypatch):
        monkeypatch.setenv("ADMZ_LOG_LEVEL", "DEBUG")
        configure_logging()
        assert logging.getLogger().level == logging.DEBUG

    def test_explicit_level_argument_wins(self):
        configure_logging(level=logging.WARNING)
        assert logging.getLogger().level == logging.WARNING

    def teardown_method(self, method):
        # Reset root logger to INFO between tests so other test files
        # don't see stray DEBUG/WARNING levels.
        logging.getLogger().setLevel(logging.INFO)
