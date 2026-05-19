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


# ---------------------------------------------------------------------------
# Phase 4 stretch: structured (JSON) logging
# ---------------------------------------------------------------------------


import json
from io import StringIO

from admz.logging_config import (
    JsonFormatter,
    configure_logging,
    resolve_log_format,
)


class TestResolveLogFormat:
    def test_default_is_text(self, monkeypatch):
        monkeypatch.delenv("ADMZ_LOG_FORMAT", raising=False)
        assert resolve_log_format() == "text"

    @pytest.mark.parametrize("raw", ["text", "Text", "TEXT", "  text  "])
    def test_text_variants(self, raw):
        assert resolve_log_format(raw) == "text"

    @pytest.mark.parametrize("raw", ["json", "JSON", "Json", "  json  "])
    def test_json_variants(self, raw):
        assert resolve_log_format(raw) == "json"

    def test_unknown_falls_back_to_text(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = resolve_log_format("yaml")
        assert result == "text"
        assert any("yaml" in rec.message for rec in caplog.records)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("ADMZ_LOG_FORMAT", "json")
        assert resolve_log_format() == "json"


class TestJsonFormatter:
    def _make_record(self, msg="hello", level=logging.INFO, **extra):
        record = logging.LogRecord(
            name="admz.test",
            level=level,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        return record

    def test_basic_fields_present(self):
        fmt = JsonFormatter()
        out = fmt.format(self._make_record("startup"))
        parsed = json.loads(out)
        assert parsed["message"] == "startup"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "admz.test"
        assert "timestamp" in parsed

    def test_extra_fields_round_trip(self):
        fmt = JsonFormatter()
        out = fmt.format(self._make_record(
            "credential fetched",
            device_id="cam-01",
            requester="AXIS\alice",
        ))
        parsed = json.loads(out)
        assert parsed["device_id"] == "cam-01"
        assert parsed["requester"] == "AXIS\alice"

    def test_standard_attrs_excluded(self):
        fmt = JsonFormatter()
        out = fmt.format(self._make_record("x"))
        parsed = json.loads(out)
        # No internal/standard attrs leak
        for noisy in ("pathname", "lineno", "filename", "module"):
            assert noisy not in parsed

    def test_exception_info_included(self):
        fmt = JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="admz.test", level=logging.ERROR, pathname=__file__,
            lineno=1, msg="failed", args=(), exc_info=exc_info,
        )
        out = fmt.format(record)
        parsed = json.loads(out)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "boom" in parsed["exception"]

    def test_non_serializable_value_falls_back_to_repr(self):
        fmt = JsonFormatter()
        class Weird:
            def __repr__(self):
                return "<weird>"
        out = fmt.format(self._make_record("x", obj=Weird()))
        parsed = json.loads(out)
        assert parsed["obj"] == "<weird>"


class TestConfigureLoggingFormat:
    def teardown_method(self, method):
        # Reset to a sane default so other test files don't see
        # a JsonFormatter on their root logger.
        configure_logging(level=logging.INFO, fmt="text")

    def test_text_format_default(self, monkeypatch):
        monkeypatch.delenv("ADMZ_LOG_FORMAT", raising=False)
        configure_logging()
        # The root handler's formatter should be a plain Formatter, not JsonFormatter
        root = logging.getLogger()
        assert any(
            not isinstance(h.formatter, JsonFormatter)
            for h in root.handlers
        ) or len(root.handlers) == 0

    def test_json_format_env(self, monkeypatch):
        monkeypatch.setenv("ADMZ_LOG_FORMAT", "json")
        configure_logging()
        root = logging.getLogger()
        assert any(
            isinstance(h.formatter, JsonFormatter) for h in root.handlers
        )

    def test_emit_json_record_round_trips(self, monkeypatch, capsys):
        monkeypatch.setenv("ADMZ_LOG_FORMAT", "json")
        configure_logging()
        # Re-grab the root after configure_logging() reset its handlers
        logging.getLogger("admz.test.emit").info(
            "audit", extra={"action": "get_credentials", "device_id": "cam-01"}
        )
        captured = capsys.readouterr()
        # The record went to stderr (StreamHandler default)
        line = (captured.err or captured.out).strip().splitlines()[-1]
        parsed = json.loads(line)
        assert parsed["message"] == "audit"
        assert parsed["action"] == "get_credentials"
        assert parsed["device_id"] == "cam-01"
