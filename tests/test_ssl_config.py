"""Tests for admz.ssl_config — the ADMZ_VERIFY_SSL env-var policy."""

import logging

import pytest

from admz.ssl_config import verify_ssl_default


class TestVerifySslDefault:
    """Policy: backward-compatible default is False; opt-in via env var."""

    def test_unset_env_returns_false(self, monkeypatch):
        monkeypatch.delenv("ADMZ_VERIFY_SSL", raising=False)
        assert verify_ssl_default() is False

    def test_empty_string_returns_false(self):
        assert verify_ssl_default("") is False

    @pytest.mark.parametrize(
        "raw",
        ["true", "TRUE", "True", "1", "yes", "YES", "on", "y", "t"],
    )
    def test_truthy_values(self, raw):
        assert verify_ssl_default(raw) is True

    @pytest.mark.parametrize(
        "raw",
        ["false", "FALSE", "False", "0", "no", "off", "n", "f"],
    )
    def test_falsey_values(self, raw):
        assert verify_ssl_default(raw) is False

    def test_whitespace_is_trimmed(self):
        assert verify_ssl_default("  true  ") is True
        assert verify_ssl_default("\tfalse\n") is False

    def test_unknown_value_falls_back_to_false_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = verify_ssl_default("maybe")
        assert result is False
        assert any(
            "maybe" in rec.message and "False" in rec.message
            for rec in caplog.records
        )

    def test_env_var_is_read_when_no_arg(self, monkeypatch):
        monkeypatch.setenv("ADMZ_VERIFY_SSL", "true")
        assert verify_ssl_default() is True
        monkeypatch.setenv("ADMZ_VERIFY_SSL", "false")
        assert verify_ssl_default() is False


class TestExecutorHonorsEnv:
    """The VapixExecutor's default verify_ssl behavior tracks ADMZ_VERIFY_SSL."""

    def test_executor_default_is_env_driven(self, monkeypatch):
        from admz.executor.vapix import VapixExecutor
        monkeypatch.setenv("ADMZ_VERIFY_SSL", "true")
        executor = VapixExecutor()
        assert executor._verify_ssl is True

    def test_executor_default_unset_is_false(self, monkeypatch):
        from admz.executor.vapix import VapixExecutor
        monkeypatch.delenv("ADMZ_VERIFY_SSL", raising=False)
        executor = VapixExecutor()
        assert executor._verify_ssl is False

    def test_executor_explicit_arg_wins_over_env(self, monkeypatch):
        from admz.executor.vapix import VapixExecutor
        monkeypatch.setenv("ADMZ_VERIFY_SSL", "true")
        executor = VapixExecutor(verify_ssl=False)
        assert executor._verify_ssl is False
