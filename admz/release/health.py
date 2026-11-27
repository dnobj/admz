"""Ask a running instance whether it is healthy, and which build is answering.

The second half is the point. A health check that only reads "healthy" passes
when the restart silently did nothing and the old code is still serving, which
is the failure an upgrade most needs to see. So the answer has to carry the
build that was just switched to (FR-DEP-005).

Only the loopback address is ever asked. The command is given a port, never a
URL, so it cannot be pointed at another machine.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

HEALTHY = "healthy"


class HealthError(RuntimeError):
    """No healthy answer came, or the answer could not be read."""


def probe(port: int, *, timeout: float = 10.0, opener: Callable = urllib.request.urlopen) -> dict:
    """One request to ``/api/health`` on this machine. Returns the decoded answer.

    Raises :class:`HealthError` when nothing answers, the answer is not JSON, or
    the status is anything but healthy.
    """
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise HealthError(f"{port!r} is not a port")
    url = f"http://127.0.0.1:{port}/api/health"
    try:
        with opener(url, timeout=timeout) as response:
            raw = response.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise HealthError(f"nothing healthy answered on port {port}: {exc}") from exc
    try:
        answer = json.loads(raw)
    except ValueError as exc:
        raise HealthError(f"port {port} answered, but not with JSON") from exc
    if not isinstance(answer, dict) or answer.get("status") != HEALTHY:
        status = answer.get("status") if isinstance(answer, dict) else answer
        raise HealthError(f"port {port} answered with status {status!r}, not {HEALTHY!r}")
    return answer


def wait_healthy(port: int, *, within: float = 90.0, every: float = 2.0,
                 ask: Callable[[int], dict] = probe,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> dict:
    """Keep asking until a healthy answer comes, or ``within`` seconds have passed.

    A service that has just been started refuses connections for a few seconds,
    so the first failures are expected. The last one is what is reported.
    """
    deadline = clock() + within
    while True:
        try:
            return ask(port)
        except HealthError as exc:
            if clock() >= deadline:
                raise HealthError(f"not healthy within {within:.0f}s: {exc}") from exc
        sleep(every)


def reports_commit(build: Optional[str], commit: str) -> bool:
    """Whether the build a checkout reports is ``commit``, with no local edits.

    A checkout names itself by its short commit (``34df136``). The service
    account often cannot ask git about local edits, and then reports
    ``34df136-unverified``; that is normal and accepted. ``34df136-dirty`` is
    not: it says files were edited in place, so the commit alone does not
    describe what is running.
    """
    if not build or not commit:
        return False
    short, _, suffix = build.partition("-")
    if suffix not in ("", "unverified"):
        return False
    return len(short) >= 7 and commit.startswith(short)
