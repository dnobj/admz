"""Tests for the Gemini transient-error retry wrapper.

Covers:
  - Retryable status codes are retried (429, 500, 502, 503, 504)
  - Non-retryable codes (400, 401, 403, 404) surface immediately
  - Retries are bounded by ADMZ_GEMINI_RETRY_MAX_ATTEMPTS
  - Backoff sleeps grow exponentially (with jitter)
  - Once a chunk has been yielded, the wrapper stops retrying
"""

from unittest.mock import MagicMock

import pytest

from admz.chatbot import client as client_mod


# ---------------------------------------------------------------------------
# _is_retryable_error
# ---------------------------------------------------------------------------


class TestIsRetryableError:
    @pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
    def test_retryable_codes(self, code):
        exc = MagicMock(spec=["code"])
        exc.code = code
        assert client_mod._is_retryable_error(exc) is True

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
    def test_non_retryable_4xx(self, code):
        exc = MagicMock(spec=["code"])
        exc.code = code
        assert client_mod._is_retryable_error(exc) is False

    def test_status_code_attr_also_works(self):
        exc = MagicMock(spec=["status_code"])
        exc.status_code = 503
        assert client_mod._is_retryable_error(exc) is True

    def test_no_code_attribute(self):
        exc = ValueError("plain exception")
        assert client_mod._is_retryable_error(exc) is False


# ---------------------------------------------------------------------------
# Config from env
# ---------------------------------------------------------------------------


class TestRetryConfig:
    def test_default_max_attempts(self, monkeypatch):
        monkeypatch.delenv("ADMZ_GEMINI_RETRY_MAX_ATTEMPTS", raising=False)
        assert client_mod._get_retry_max_attempts() == 3

    def test_env_max_attempts(self, monkeypatch):
        monkeypatch.setenv("ADMZ_GEMINI_RETRY_MAX_ATTEMPTS", "5")
        assert client_mod._get_retry_max_attempts() == 5

    def test_invalid_env_max_attempts_falls_back(self, monkeypatch):
        monkeypatch.setenv("ADMZ_GEMINI_RETRY_MAX_ATTEMPTS", "twelve")
        assert client_mod._get_retry_max_attempts() == 3

    def test_minimum_one_attempt(self, monkeypatch):
        # Even if operator sets 0, we still run once (no retry).
        monkeypatch.setenv("ADMZ_GEMINI_RETRY_MAX_ATTEMPTS", "0")
        assert client_mod._get_retry_max_attempts() == 1

    def test_default_base_delay(self, monkeypatch):
        monkeypatch.delenv("ADMZ_GEMINI_RETRY_BASE_DELAY", raising=False)
        assert client_mod._get_retry_base_delay() == 0.5

    def test_env_base_delay(self, monkeypatch):
        monkeypatch.setenv("ADMZ_GEMINI_RETRY_BASE_DELAY", "1.5")
        assert client_mod._get_retry_base_delay() == 1.5


# ---------------------------------------------------------------------------
# Thinking-budget config (Phase 5E: empty-response mitigation)
# ---------------------------------------------------------------------------


class TestThinkingBudget:
    """Default is dynamic thinking (-1): required for reliable tool use
    (the model otherwise answers device-operation requests from wrong
    training priors instead of calling query_catalog/execute_operation)
    and for the *-pro models. 0 disables; >0 is a fixed budget."""

    def test_default_is_dynamic(self, monkeypatch):
        monkeypatch.delenv("ADMZ_GEMINI_THINKING_BUDGET", raising=False)
        assert client_mod._get_thinking_budget() == -1

    def test_env_override_positive(self, monkeypatch):
        monkeypatch.setenv("ADMZ_GEMINI_THINKING_BUDGET", "5000")
        assert client_mod._get_thinking_budget() == 5000

    def test_env_can_disable_with_zero(self, monkeypatch):
        monkeypatch.setenv("ADMZ_GEMINI_THINKING_BUDGET", "0")
        assert client_mod._get_thinking_budget() == 0

    def test_invalid_env_falls_back_to_dynamic(self, monkeypatch):
        monkeypatch.setenv("ADMZ_GEMINI_THINKING_BUDGET", "lots")
        assert client_mod._get_thinking_budget() == -1

    def test_out_of_range_negative_clamps_to_dynamic(self, monkeypatch):
        monkeypatch.setenv("ADMZ_GEMINI_THINKING_BUDGET", "-100")
        assert client_mod._get_thinking_budget() == -1


# ---------------------------------------------------------------------------
# Backoff schedule (no jitter)
# ---------------------------------------------------------------------------


class TestBackoff:
    def test_exponential_growth(self):
        # Disable jitter for deterministic check.
        d1 = client_mod._compute_retry_delay(1, base=0.5, jitter=0)
        d2 = client_mod._compute_retry_delay(2, base=0.5, jitter=0)
        d3 = client_mod._compute_retry_delay(3, base=0.5, jitter=0)
        assert d1 == 0.5
        assert d2 == 1.0
        assert d3 == 2.0

    def test_jitter_within_range(self):
        # Default jitter is ±25% — should always land in [0.375, 0.625] for base=0.5 attempt=1.
        samples = [
            client_mod._compute_retry_delay(1, base=0.5) for _ in range(50)
        ]
        for s in samples:
            assert 0.375 <= s <= 0.625

    def test_never_negative(self):
        assert client_mod._compute_retry_delay(1, base=0.001) >= 0.0


# ---------------------------------------------------------------------------
# _invoke_stream_with_retry: actual retry behavior
# ---------------------------------------------------------------------------


class _FakeServerError(Exception):
    """Mimics google.genai.errors.ServerError with a .code attribute."""

    def __init__(self, code, message="transient"):
        super().__init__(message)
        self.code = code


def _make_chunk(text=""):
    """Cheap stand-in for a streaming chunk — just an object."""
    c = MagicMock(spec=["text"])
    c.text = text
    return c


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    """Use a tiny base delay so the test suite isn't slow."""
    monkeypatch.setenv("ADMZ_GEMINI_RETRY_BASE_DELAY", "0.001")


@pytest.mark.asyncio
async def test_503_is_retried_and_succeeds(monkeypatch):
    """First attempt raises 503; second attempt yields chunks."""
    monkeypatch.setenv("ADMZ_GEMINI_RETRY_MAX_ATTEMPTS", "3")

    attempt_count = {"n": 0}

    async def fake_invoke(client, kwargs, *, mcp_session=None):
        attempt_count["n"] += 1
        if attempt_count["n"] == 1:
            raise _FakeServerError(503)
        yield _make_chunk("hello")
        yield _make_chunk(" world")

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke)

    chunks = []
    async for c in client_mod._invoke_stream_with_retry(
        MagicMock(), {"model": "x"}
    ):
        chunks.append(c.text)

    assert chunks == ["hello", " world"]
    assert attempt_count["n"] == 2  # one fail + one success


@pytest.mark.asyncio
async def test_persistent_503_eventually_raises(monkeypatch):
    """All attempts fail with 503 — final attempt re-raises."""
    monkeypatch.setenv("ADMZ_GEMINI_RETRY_MAX_ATTEMPTS", "3")

    attempt_count = {"n": 0}

    async def fake_invoke(client, kwargs, *, mcp_session=None):
        attempt_count["n"] += 1
        raise _FakeServerError(503, "still down")
        yield  # pragma: no cover — unreachable

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke)

    with pytest.raises(_FakeServerError) as excinfo:
        async for _ in client_mod._invoke_stream_with_retry(
            MagicMock(), {"model": "x"}
        ):
            pass

    assert excinfo.value.code == 503
    assert attempt_count["n"] == 3  # exhausted all attempts


@pytest.mark.asyncio
async def test_non_retryable_400_surfaces_immediately(monkeypatch):
    """A 400 must NOT be retried — it's the caller's fault."""
    monkeypatch.setenv("ADMZ_GEMINI_RETRY_MAX_ATTEMPTS", "5")

    attempt_count = {"n": 0}

    async def fake_invoke(client, kwargs, *, mcp_session=None):
        attempt_count["n"] += 1
        raise _FakeServerError(400, "bad request")
        yield  # pragma: no cover

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke)

    with pytest.raises(_FakeServerError):
        async for _ in client_mod._invoke_stream_with_retry(
            MagicMock(), {"model": "x"}
        ):
            pass

    assert attempt_count["n"] == 1


@pytest.mark.asyncio
async def test_error_after_chunk_yielded_is_not_retried(monkeypatch):
    """Once we've yielded text to the user, we can't un-yield. The next
    failure must surface immediately even if it's a 503."""
    monkeypatch.setenv("ADMZ_GEMINI_RETRY_MAX_ATTEMPTS", "5")

    attempt_count = {"n": 0}

    async def fake_invoke(client, kwargs, *, mcp_session=None):
        attempt_count["n"] += 1
        yield _make_chunk("partial ")
        raise _FakeServerError(503, "died mid-stream")

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke)

    chunks = []
    with pytest.raises(_FakeServerError):
        async for c in client_mod._invoke_stream_with_retry(
            MagicMock(), {"model": "x"}
        ):
            chunks.append(c.text)

    # Got the partial output, but no retry attempted.
    assert chunks == ["partial "]
    assert attempt_count["n"] == 1


@pytest.mark.asyncio
async def test_429_is_retried(monkeypatch):
    monkeypatch.setenv("ADMZ_GEMINI_RETRY_MAX_ATTEMPTS", "3")

    attempt_count = {"n": 0}

    async def fake_invoke(client, kwargs, *, mcp_session=None):
        attempt_count["n"] += 1
        if attempt_count["n"] < 2:
            raise _FakeServerError(429, "rate limited")
        yield _make_chunk("ok")

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke)

    chunks = []
    async for c in client_mod._invoke_stream_with_retry(
        MagicMock(), {"model": "x"}
    ):
        chunks.append(c.text)

    assert chunks == ["ok"]
    assert attempt_count["n"] == 2


@pytest.mark.asyncio
async def test_max_attempts_one_disables_retry(monkeypatch):
    """ADMZ_GEMINI_RETRY_MAX_ATTEMPTS=1 means try once, fail once."""
    monkeypatch.setenv("ADMZ_GEMINI_RETRY_MAX_ATTEMPTS", "1")

    attempt_count = {"n": 0}

    async def fake_invoke(client, kwargs, *, mcp_session=None):
        attempt_count["n"] += 1
        raise _FakeServerError(503)
        yield  # pragma: no cover

    monkeypatch.setattr(client_mod, "_invoke_stream", fake_invoke)

    with pytest.raises(_FakeServerError):
        async for _ in client_mod._invoke_stream_with_retry(
            MagicMock(), {"model": "x"}
        ):
            pass

    assert attempt_count["n"] == 1
