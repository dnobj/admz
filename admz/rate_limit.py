"""Lightweight in-memory rate limiting for the public-facing
``/capture/{token}`` and ``/confirm/{token}`` endpoints.

Tokens are 256-bit single-use, so the practical risk is not brute
force; it's an attacker who knows a token URL repeatedly hitting the
POST handler to overwrite a legitimate user's submission, or
hammering the password field on a ``url_and_password`` confirm.
A per-IP, per-route rate limit closes both.

Design:
- Thread-safe ``TokenBucket`` per (route, ip) key, in-memory.
- Capacity + refill rate are configurable per route.
- ``check_rate()`` returns the bucket result; the caller raises 429
  (FastAPI's ``HTTPException(429)``).
- Buckets are pruned on every check after they've been empty for
  ``_PRUNE_AFTER_S`` seconds — bounded memory regardless of unique-IP
  cardinality.

In-memory is the right place for v1 — single-process by design (see
ADR-0008). If/when ADMZ ever grows to multi-process, a Redis-backed
adapter slots in via the same module-level get/set functions.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Tuple


# Time after the last refill at which an idle bucket is reaped.
_PRUNE_AFTER_S = 300.0


@dataclass
class _Bucket:
    tokens: float
    last_refill: float
    capacity: float
    refill_per_s: float

    def take(self, now: float) -> bool:
        """Consume one token. Returns True if granted."""
        # Refill based on elapsed time
        elapsed = now - self.last_refill
        if elapsed > 0:
            self.tokens = min(
                self.capacity, self.tokens + elapsed * self.refill_per_s
            )
            self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    """Thread-safe per-(route, key) token-bucket rate limiter."""

    def __init__(self):
        self._lock = threading.Lock()
        self._buckets: Dict[Tuple[str, str], _Bucket] = {}
        # Default per-route policy: capacity, refill_per_second
        self._policy: Dict[str, Tuple[float, float]] = {
            # /capture/{token} POST — 10 attempts allowed instantly,
            # then 1 per 6s sustained (10/minute). Plenty for a legit
            # user fat-fingering the password; tight for an attacker.
            "capture": (10, 1.0 / 6.0),
            # /confirm/{token} POST — same shape.
            "confirm": (10, 1.0 / 6.0),
            # /login POST — Windows credential attempts (ADR-0033).
            # 5 instant tries, then 1 per 12s sustained (5/minute):
            # roomy for a typo'd password, hostile to a guesser.
            "login": (5, 1.0 / 12.0),
            # /login/sso GET — Negotiate handshake legs (ADR-0035). One
            # sign-in legitimately makes 2-3 requests (NTLM is multi-leg),
            # so roomier than "login": 15 instant, then 1 per 4s.
            "login-sso": (15, 1.0 / 4.0),
        }

    def configure(self, route: str, capacity: float, refill_per_s: float) -> None:
        """Override the policy for a route. Updates existing buckets for
        that route so the change takes effect immediately for callers
        we've already seen."""
        with self._lock:
            self._policy[route] = (capacity, refill_per_s)
            for (r, _key), bucket in self._buckets.items():
                if r == route:
                    bucket.capacity = capacity
                    bucket.refill_per_s = refill_per_s

    def check(self, route: str, key: str) -> bool:
        """Try to consume one token for (route, key). Returns True if
        granted, False if rate-limited.

        ``key`` is typically the caller's IP address. ``route`` is a
        short string like ``"capture"`` or ``"confirm"``.
        """
        now = time.time()
        with self._lock:
            policy = self._policy.get(route)
            if policy is None:
                # Unconfigured route — no limit
                return True
            capacity, refill = policy
            bucket_key = (route, key)
            bucket = self._buckets.get(bucket_key)
            if bucket is None:
                bucket = _Bucket(
                    tokens=capacity,
                    last_refill=now,
                    capacity=capacity,
                    refill_per_s=refill,
                )
                self._buckets[bucket_key] = bucket

            allowed = bucket.take(now)

            # Opportunistic GC of long-idle buckets — keeps memory
            # bounded under high unique-IP cardinality without a
            # background thread.
            if len(self._buckets) > 256:
                stale = [
                    k for k, b in self._buckets.items()
                    if (now - b.last_refill) > _PRUNE_AFTER_S
                ]
                for k in stale:
                    self._buckets.pop(k, None)

            return allowed

    def reset(self) -> None:
        """Drop all buckets — used by tests for isolation."""
        with self._lock:
            self._buckets.clear()


# Module-level singleton.
rate_limiter = RateLimiter()


def client_key_from_request(request) -> str:
    """Pull the rate-limit key out of a FastAPI Request.

    Uses the proxy-aware ``X-Forwarded-For`` (first hop) when present —
    matches the reverse-proxy deployment topology described in
    DEPLOYMENT_WINDOWS.md. Falls back to ``request.client.host``.

    Returns the literal string ``"unknown"`` if the IP can't be
    determined; treats all such callers as one shared bucket
    (defensive — better one shared bucket than no limit).
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
