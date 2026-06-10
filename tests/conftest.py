"""Shared pytest fixtures / test-isolation guards.

Several suites exercise the *global, in-memory* rate limiter
(`admz.rate_limit.rate_limiter`) and the per-token confirm-password lockout
dict (`admz.api.routes.confirm._PW_ATTEMPTS`). Both are process-wide singletons,
so a test that drains the ``confirm`` token bucket (or leaves a token locked
out) can make a *later* confirm test fail with an unexpected 429 — purely as a
function of test order. This was latent for a long time and surfaced when new
test files shifted the collection order.

The autouse fixture below resets that shared state before every test, making
the confirm/rate-limit tests order-independent. Tests that configure their own
bucket policy still work — they configure after this reset.
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_shared_inmemory_state():
    """Reset process-wide rate-limit + lockout state before each test."""
    try:
        from admz.rate_limit import rate_limiter
        rate_limiter.reset()  # clears token buckets; keeps configured policy
    except Exception:
        pass
    try:
        from admz.api.routes.confirm import _PW_ATTEMPTS, _PW_ATTEMPTS_LOCK
        with _PW_ATTEMPTS_LOCK:
            _PW_ATTEMPTS.clear()
    except Exception:
        pass
    yield
