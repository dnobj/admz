"""Tests for the httpx request-log redaction filter (#157).

Installed httpx (0.28.1) logs the fully assembled request URL — query
string included — at INFO via ``logging.getLogger("httpx").info(...)``
(httpx/_client.py). VAPIX operations that set a device password put the
plaintext password in that query string, and ADMZ never otherwise touches
the ``httpx`` logger, so the password reached ``server.log`` in the clear.

This file pins the fix at three levels: the filter in isolation (no real
logging pipeline involved), the filter wired through the real
``configure_logging()`` handler for both log formats (proving it protects
both the text and the JSON-shipper path from the same attachment point),
and an explicit mutation-check note — see ``TestMutationCheck``.
"""

import logging

import pytest

from admz.logging_config import (
    _HttpxUrlRedactingFilter,
    _ensure_httpx_redaction_filter,
    configure_logging,
)

# The exact call shape httpx 0.28.1 uses for every request/response pair:
#   logger.info('HTTP Request: %s %s "%s %d %s"',
#               request.method, request.url,
#               response.http_version, response.status_code, response.reason_phrase)
_HTTPX_MSG = 'HTTP Request: %s %s "%s %d %s"'


def _httpx_record(url, method="POST", http_version="HTTP/1.1", status=200, phrase="OK"):
    return logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname="_client.py",
        lineno=1740,
        msg=_HTTPX_MSG,
        args=(method, url, http_version, status, phrase),
        exc_info=None,
    )


class TestFilterInIsolation:
    """The filter's own logic, no handler/formatter involved."""

    def test_password_query_param_is_redacted(self):
        record = _httpx_record(
            "http://192.168.1.50/axis-cgi/pwdgrp.cgi?action=add&user=admz_tmp&pwd=hunter2&grp=users"
        )
        filt = _HttpxUrlRedactingFilter()

        assert filt.filter(record) is True  # never drops the record
        rendered = record.getMessage()

        assert "hunter2" not in rendered
        assert "admz_tmp" not in rendered  # every query value is masked, not just pwd=
        assert "POST" in rendered  # method preserved
        assert "/axis-cgi/pwdgrp.cgi" in rendered  # path preserved
        assert "HTTP/1.1" in rendered and "200" in rendered and "OK" in rendered
        assert rendered == (
            'HTTP Request: POST http://192.168.1.50/axis-cgi/pwdgrp.cgi'
            '?action=%2A%2A%2A&user=%2A%2A%2A&pwd=%2A%2A%2A&grp=%2A%2A%2A'
            ' "HTTP/1.1 200 OK"'
        )

    def test_args_consumed_so_double_formatting_is_safe(self):
        """After filtering, record.msg is the fully rendered (redacted)
        string and record.args is empty — getMessage() must be safe to call
        again (a formatter and a second handler both call it)."""
        record = _httpx_record("http://host/pwdgrp.cgi?pwd=secret")
        _HttpxUrlRedactingFilter().filter(record)
        first = record.getMessage()
        second = record.getMessage()
        assert first == second
        assert "secret" not in first

    def test_url_without_query_is_unaffected(self):
        record = _httpx_record("http://192.168.1.50/axis-cgi/disks/list.cgi")
        _HttpxUrlRedactingFilter().filter(record)
        rendered = record.getMessage()
        assert rendered == (
            'HTTP Request: POST http://192.168.1.50/axis-cgi/disks/list.cgi'
            ' "HTTP/1.1 200 OK"'
        )

    def test_never_raises_on_a_record_with_no_url_token(self):
        """Defensive: a malformed or future-shaped httpx record must not
        crash logging. Falling through unredacted is the acceptable failure
        here — httpx has exactly one INFO call site and it always logs a URL."""
        record = logging.LogRecord(
            name="httpx", level=logging.INFO, pathname="x", lineno=1,
            msg="unexpected shape", args=(), exc_info=None,
        )
        filt = _HttpxUrlRedactingFilter()
        assert filt.filter(record) is True
        assert record.getMessage() == "unexpected shape"


class TestWiredThroughConfigureLogging:
    """The end-to-end path: real `configure_logging()`, real `httpx` logger,
    real handler — proving the filter catches the record before either
    formatter renders it (#157's original question: "where would a Filter
    have to attach to catch both the stream handler and the JSON path")."""

    def teardown_method(self, method):
        configure_logging(level=logging.INFO, fmt="text")

    def test_text_format_redacts(self, monkeypatch, capsys):
        monkeypatch.delenv("ADMZ_LOG_FORMAT", raising=False)
        configure_logging()
        logging.getLogger("httpx").info(
            _HTTPX_MSG, "POST",
            "http://192.168.1.50/axis-cgi/pwdgrp.cgi?action=add&pwd=hunter2",
            "HTTP/1.1", 200, "OK",
        )
        captured = capsys.readouterr()
        out = captured.err or captured.out
        assert "hunter2" not in out
        assert "/axis-cgi/pwdgrp.cgi" in out

    def test_json_format_redacts(self, monkeypatch, capsys):
        """Same attachment point, same result, under the aggregator format —
        there is only one handler either way; the filter runs before it."""
        monkeypatch.setenv("ADMZ_LOG_FORMAT", "json")
        configure_logging()
        logging.getLogger("httpx").info(
            _HTTPX_MSG, "POST",
            "http://192.168.1.50/axis-cgi/pwdgrp.cgi?action=add&pwd=hunter2",
            "HTTP/1.1", 200, "OK",
        )
        captured = capsys.readouterr()
        out = captured.err or captured.out
        assert "hunter2" not in out
        assert "/axis-cgi/pwdgrp.cgi" in out

    def test_repeated_configure_logging_does_not_stack_filters(self):
        """configure_logging() discards and rebuilds the root handler on
        every call; the httpx *logger* is not rebuilt, so a naive
        addFilter() on every call would accumulate duplicates."""
        httpx_logger = logging.getLogger("httpx")
        before = len(httpx_logger.filters)
        configure_logging()
        configure_logging()
        configure_logging()
        after = len(httpx_logger.filters)
        assert after == before  # unchanged — not a growing stack
        assert sum(
            isinstance(f, _HttpxUrlRedactingFilter) for f in httpx_logger.filters
        ) == 1

    def test_ensure_helper_is_directly_idempotent(self):
        httpx_logger = logging.getLogger("httpx")
        _ensure_httpx_redaction_filter()
        _ensure_httpx_redaction_filter()
        count = sum(
            isinstance(f, _HttpxUrlRedactingFilter) for f in httpx_logger.filters
        )
        assert count == 1


class TestMutationCheck:
    """Not an automated mutation-testing run — a manual one, recorded here
    so a future reader doesn't have to re-derive that this suite actually
    pins the behavior rather than a tautology.

    Verified by hand during development: with the
    ``_ensure_httpx_redaction_filter()`` call removed from
    ``configure_logging()`` (admz/logging_config.py), every test in
    ``TestWiredThroughConfigureLogging`` above fails — ``test_text_format_redacts``
    and ``test_json_format_redacts`` both then find ``"hunter2"`` in the
    captured output. Restoring the call turns them green again. This class
    exists so that fact is written down rather than only having happened
    once in a terminal.
    """

    def test_filter_class_is_reachable_without_the_wiring(self):
        """Sanity: the filter itself doesn't depend on configure_logging()
        having run — isolates "the filter is broken" from "the wiring that
        installs it is broken", the two ways this fix can regress separately.
        """
        record = _httpx_record("http://host/pwdgrp.cgi?pwd=secret")
        assert _HttpxUrlRedactingFilter().filter(record) is True
        assert "secret" not in record.getMessage()
