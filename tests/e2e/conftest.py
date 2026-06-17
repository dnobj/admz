"""Pytest config for the E2E suite.

These tests hit a LIVE running ADMZ server at ``localhost:4242``
and consume real Gemini API credits. They're opt-in:

    pytest tests/e2e --run-e2e

Without the flag they're skipped (so the normal test suite stays
fast + free). The flag also widens timeouts and asserts the server
is reachable before any test starts.
"""

from __future__ import annotations

import functools
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pytest


DEFAULT_BASE_URL = "http://127.0.0.1:4242"


@functools.lru_cache(maxsize=1)
def _auth_headers() -> Dict[str, str]:
    """Bearer header for deployments that require auth (ADR-0033 windows-local
    makes /api/chat reject anonymous). Key resolution, in order:
    ``ADMZ_E2E_API_KEY`` env, ``ADMZ_DEV_API_KEY`` env, then
    ``~/.admz/dev-api-key.txt``. Empty (anonymous) when none is found — so this
    still works against an ``ADMZ_AUTH_BACKEND=none`` server."""
    key = os.getenv("ADMZ_E2E_API_KEY") or os.getenv("ADMZ_DEV_API_KEY")
    if not key:
        f = Path.home() / ".admz" / "dev-api-key.txt"
        if f.exists():
            try:
                key = f.read_text(encoding="utf-8").strip()
            except OSError:
                key = None
    return {"Authorization": f"Bearer {key}"} if key else {}
PER_TEST_BUDGET_SECONDS = 240  # generous: tool calls + Gemini AFC can take time


def pytest_addoption(parser):
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help=(
            "Run live end-to-end tests against the ADMZ server at "
            f"{DEFAULT_BASE_URL}. Consumes real Gemini API credits "
            "(~$0.03-$0.05 per full run as of 2026)."
        ),
    )


def pytest_collection_modifyitems(config, items):
    """Skip everything in tests/e2e/ unless --run-e2e is passed."""
    if config.getoption("--run-e2e"):
        return
    skip_e2e = pytest.mark.skip(reason="needs --run-e2e flag")
    for item in items:
        # Item path is OS-specific (\ on Windows, / elsewhere) — normalize.
        path = str(item.fspath).replace("\\", "/")
        if "/tests/e2e/" in path:
            item.add_marker(skip_e2e)


# ---------------------------------------------------------------------------
# Server liveness + helpers
# ---------------------------------------------------------------------------


def _base_url() -> str:
    return os.getenv("ADMZ_E2E_BASE_URL", DEFAULT_BASE_URL)


def _server_alive() -> bool:
    try:
        r = httpx.get(f"{_base_url()}/api/health", timeout=3.0)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


@pytest.fixture(scope="session", autouse=True)
def _ensure_server_alive(request):
    """Skip the whole suite if no server is reachable."""
    if not request.config.getoption("--run-e2e"):
        return
    if not _server_alive():
        pytest.skip(
            f"E2E tests need a live ADMZ server at {_base_url()}. "
            "Start it with: python -m admz api --host 127.0.0.1 --port 4242"
        )


# ---------------------------------------------------------------------------
# Chat-client helper — wraps POST /api/chat
# ---------------------------------------------------------------------------


class ChatResult:
    """Lightweight wrapper around the JSON body of POST /api/chat that
    gives tests a few useful convenience predicates."""

    def __init__(self, body: Dict[str, Any], elapsed: float):
        self.body = body
        self.elapsed = elapsed
        self.success: bool = body.get("success", False)
        self.error: Optional[str] = body.get("error")
        self.response: str = body.get("response", "") or ""
        self.tool_calls: List[str] = body.get("tool_calls", []) or []
        self.input_tokens: int = body.get("input_tokens", 0) or 0
        self.output_tokens: int = body.get("output_tokens", 0) or 0
        self.model: str = body.get("model", "")
        self.cost_usd: float = body.get("cost_usd") or 0.0

    @property
    def lower(self) -> str:
        return self.response.lower()

    def contains_any(self, *needles: str) -> bool:
        """True if any of the case-insensitive needles appear in the
        response. Useful for tests that want to be tolerant of LLM
        phrasing variation."""
        body = self.lower
        return any(n.lower() in body for n in needles)

    def contains_all(self, *needles: str) -> bool:
        body = self.lower
        return all(n.lower() in body for n in needles)

    def __repr__(self):
        preview = self.response[:200]
        return (
            f"<ChatResult success={self.success} model={self.model} "
            f"tokens={self.input_tokens}/{self.output_tokens} "
            f"elapsed={self.elapsed:.1f}s response={preview!r}>"
        )


def _send_chat(
    message: str,
    *,
    model: Optional[str] = None,
    use_tools: bool = True,
    timeout: float = PER_TEST_BUDGET_SECONDS,
    retries: int = 3,
) -> ChatResult:
    payload: Dict[str, Any] = {"message": message, "use_tools": use_tools}
    if model:
        payload["model"] = model
    last: Optional[ChatResult] = None
    for attempt in range(retries + 1):
        start = time.monotonic()
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{_base_url()}/api/chat", json=payload, headers=_auth_headers()
            )
        elapsed = time.monotonic() - start
        assert resp.status_code == 200, (
            f"/api/chat returned HTTP {resp.status_code}: {resp.text[:500]}"
        )
        result = ChatResult(resp.json(), elapsed)
        # Retry ONLY the transient signature: an empty candidate (success=False,
        # no text, 0 output tokens). This is what a Gemini 503 UNAVAILABLE blip
        # surfaces as — NOT an ADMZ bug. Back off (2/4/6s) to ride out a short
        # service spell. Don't retry successful turns or substantive errors.
        transient = (not result.success) and (not result.response.strip())
        if not transient:
            return result
        last = result
        if attempt < retries:
            time.sleep(2.0 * (attempt + 1))
    return last  # type: ignore[return-value]


def _clear_history() -> None:
    """POST /chat/clear so the next test starts with no prior turns
    in chat_history. All tests run as the anonymous principal so
    history is shared between them without isolation — this avoids
    cross-test pollution + balloon-y prompts."""
    try:
        with httpx.Client(timeout=10.0) as client:
            # Follow redirects=False so the 303 from /chat/clear
            # doesn't trigger a GET /chat round-trip.
            client.post(
                f"{_base_url()}/chat/clear", follow_redirects=False,
                headers=_auth_headers(),
            )
    except (httpx.ConnectError, httpx.TimeoutException):
        pass  # liveness fixture would have already skipped


@pytest.fixture(autouse=True)
def _isolate_chat_history(request):
    """Clear chat_history before every E2E test so they don't see
    each other's turns. The multi-turn test does its own consecutive
    calls within a single test function — those still share state,
    which is the whole point."""
    if not request.config.getoption("--run-e2e"):
        return
    _clear_history()


@pytest.fixture
def chat():
    """Yields a callable: ``chat(message, **kwargs) -> ChatResult``.

    Each call POSTs to /api/chat and returns a ChatResult with the
    parsed body + a few convenience methods. Tests should assert on
    ``result.success``, ``result.response``, etc.
    """
    return _send_chat


@pytest.fixture
def api():
    """REST helper for non-chat endpoints (auth-aware, no Gemini cost):

        resp = api("GET", "/api/snapshot/drift?device_id=...")
        resp = api("POST", "/api/config/ignore-rules", json={...})

    Returns the raw httpx.Response so tests assert on status + body."""
    def _call(method: str, path: str, **kw) -> httpx.Response:
        with httpx.Client(timeout=60.0) as client:
            return client.request(
                method, f"{_base_url()}{path}", headers=_auth_headers(), **kw
            )
    return _call


@pytest.fixture
def api_anon():
    """Like ``api`` but with NO auth — for asserting destructive endpoints
    reject anonymous callers."""
    def _call(method: str, path: str, **kw) -> httpx.Response:
        with httpx.Client(timeout=30.0) as client:
            return client.request(method, f"{_base_url()}{path}", **kw)
    return _call


@pytest.fixture
def a_device(registered_ids):
    """The first registered device_id (sorted), or None so tests can skip."""
    return next(iter(sorted(registered_ids)), None)


@pytest.fixture
def registered_ids() -> set:
    """The device_ids the live registry currently knows. Tests that target a
    specific fixture device skip when it's absent (homelab inventory drifts)."""
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{_base_url()}/api/devices", headers=_auth_headers())
        if r.status_code == 200:
            data = r.json()
            devices = data if isinstance(data, list) else data.get("devices", [])
            return {
                d.get("device_id") for d in devices if isinstance(d, dict)
            }
    except (httpx.ConnectError, httpx.TimeoutException):
        pass
    return set()


# ---------------------------------------------------------------------------
# Cost reporter — sums up the cost of every test in the run.
# ---------------------------------------------------------------------------


class _CostReporter:
    def __init__(self):
        self.tests: List[Dict[str, Any]] = []

    def record(self, nodeid: str, result: ChatResult):
        self.tests.append({
            "test": nodeid,
            "tokens_in": result.input_tokens,
            "tokens_out": result.output_tokens,
            "cost_usd": result.cost_usd,
            "elapsed_s": result.elapsed,
        })

    def total_cost(self) -> float:
        return sum(t["cost_usd"] for t in self.tests)


_COST_REPORTER = _CostReporter()


@pytest.fixture
def cost_recorder(request):
    """Record each test's cost so the session can print a summary."""

    def _record(result: ChatResult):
        _COST_REPORTER.record(request.node.nodeid, result)

    return _record


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not config.getoption("--run-e2e"):
        return
    if not _COST_REPORTER.tests:
        return
    tr = terminalreporter
    tr.section("E2E Gemini API Cost Summary")
    total_in = sum(t["tokens_in"] for t in _COST_REPORTER.tests)
    total_out = sum(t["tokens_out"] for t in _COST_REPORTER.tests)
    total_cost = _COST_REPORTER.total_cost()
    total_time = sum(t["elapsed_s"] for t in _COST_REPORTER.tests)
    tr.write_line(
        f"  Tests recorded: {len(_COST_REPORTER.tests)} | "
        f"Input tokens: {total_in:,} | Output tokens: {total_out:,} | "
        f"Total cost: ${total_cost:.4f} | "
        f"Total Gemini wall time: {total_time:.1f}s"
    )
    if total_cost > 0.50:
        tr.write_line(
            f"  Note: total cost exceeded $0.50 — review tests for "
            f"unexpected token consumption."
        )
