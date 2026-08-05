"""Tests for admz.target_guard (#180).

These pin the SAFETY behaviour shared by tests/e2e/conftest.py and
tools/dev_auto_approve.py: refuse — raise, not skip — when the resolved
target is production, unless the escape hatch is set to the *exact* URL
being refused. No network I/O anywhere in this file: every case here is
pure/local, which is the point — the guard's job is to stop before a
request is ever sent, so proving it doesn't need to send one.
"""

import pytest

from admz.target_guard import (
    ESCAPE_HATCH_ENV,
    PRODUCTION_PORT,
    format_refusal,
    refuse_if_production,
    targets_production,
)


# --- targets_production ------------------------------------------------


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:4242",
    "http://localhost:4242",
    "http://127.0.0.1:4242/",
    "http://127.0.0.1:4242/api/health",
    "HTTP://127.0.0.1:4242",  # scheme case shouldn't matter
    "http://LOCALHOST:4242",  # host case shouldn't matter
])
def test_targets_production_true_for_loopback_prod_port(url):
    assert targets_production(url) is True


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:4243",     # staging
    "http://localhost:4243",
    "http://127.0.0.1:8000",     # some other local port
    "http://example.com:4242",   # right port, not loopback
    "http://127.0.0.1",          # no explicit port at all
    "not-a-url",
])
def test_targets_production_false_otherwise(url):
    assert targets_production(url) is False


def test_production_port_is_4242():
    # Pin the constant itself — a future edit that "fixes" this to some
    # other number would otherwise pass every other test silently.
    assert PRODUCTION_PORT == 4242


# --- refuse_if_production ------------------------------------------------


def test_refuses_production_with_no_escape_hatch():
    with pytest.raises(RuntimeError, match="4242"):
        refuse_if_production(
            "http://127.0.0.1:4242", source="test", env={}
        )


@pytest.mark.parametrize("bad_value", ["1", "true", "yes", "on", ""])
def test_refuses_production_when_escape_hatch_is_not_the_exact_url(bad_value):
    """A boolean-shaped value must NOT satisfy the hatch — that's the whole
    point of requiring the exact URL (#180 review: "not the kind of
    variable that lingers in a shell from an earlier session")."""
    env = {ESCAPE_HATCH_ENV: bad_value}
    with pytest.raises(RuntimeError):
        refuse_if_production("http://127.0.0.1:4242", source="test", env=env)


def test_refuses_production_when_escape_hatch_names_a_different_url():
    """A stale hatch pinned to a different target must not carry over."""
    env = {ESCAPE_HATCH_ENV: "http://127.0.0.1:4243"}
    with pytest.raises(RuntimeError):
        refuse_if_production("http://127.0.0.1:4242", source="test", env=env)


def test_escape_hatch_matching_exact_url_passes():
    env = {ESCAPE_HATCH_ENV: "http://127.0.0.1:4242"}
    refuse_if_production("http://127.0.0.1:4242", source="test", env=env)  # no raise


def test_non_production_target_never_raises_regardless_of_env():
    refuse_if_production("http://127.0.0.1:4243", source="test", env={})
    refuse_if_production(
        "http://127.0.0.1:4243", source="test", env={ESCAPE_HATCH_ENV: "garbage"}
    )


def test_default_env_is_os_environ(monkeypatch):
    """No explicit env= means it reads the real process environment —
    this is what makes a leftover shell var actually matter."""
    monkeypatch.delenv(ESCAPE_HATCH_ENV, raising=False)
    with pytest.raises(RuntimeError):
        refuse_if_production("http://127.0.0.1:4242", source="test")

    monkeypatch.setenv(ESCAPE_HATCH_ENV, "http://127.0.0.1:4242")
    refuse_if_production("http://127.0.0.1:4242", source="test")  # no raise


# --- format_refusal --------------------------------------------------------


def test_refusal_message_names_the_url_source_and_hatch():
    msg = format_refusal("http://127.0.0.1:4242", source="ADMZ_E2E_BASE_URL")
    assert "http://127.0.0.1:4242" in msg
    assert "ADMZ_E2E_BASE_URL" in msg
    assert ESCAPE_HATCH_ENV in msg
    assert "#180" in msg
