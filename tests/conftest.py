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

import os

import pytest

# Credential onboarding runs network probes after a device add (TCP
# preflight + systemready + basicdeviceinfo). Unit tests register devices
# with fabricated LAN addresses — without this guard every create would
# probe whatever network the test box sits on. test_onboarding.py deletes
# the var and mocks the probes to exercise the flow itself.
os.environ.setdefault("ADMZ_DISABLE_ONBOARDING_PROBES", "1")

# Same class of leak on the push path: the GitHub App connection lives in the
# machine's secret store (ADR-0045), so on a developer's *connected* box the
# git-push tests would mint a real installation token over the network and push
# with auth args a clean box never sees. Pin them to the unauthenticated path.
# tests/test_github_app*.py exercise the token machinery directly instead.
os.environ.setdefault("ADMZ_DISABLE_GITHUB_APP_PUSH", "1")


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
