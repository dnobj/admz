"""Asking a running instance whether it is healthy, and which build answered.

No test here opens a socket. The request is replaced by a function that says
what the instance would have answered.
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from admz.release import health

COMMIT = "34df136c0ffee" + "0" * 27


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


def _answers(payload, seen=None):
    def opener(url, timeout=None):
        if seen is not None:
            seen.append((url, timeout))
        return Response(payload if isinstance(payload, bytes) else json.dumps(payload).encode())
    return opener


def test_a_healthy_answer_is_returned_whole():
    seen = []
    answer = health.probe(4242, timeout=7, opener=_answers(
        {"status": "healthy", "version": "2.1.0", "build": "34df136"}, seen))
    assert answer == {"status": "healthy", "version": "2.1.0", "build": "34df136"}
    assert seen == [("http://127.0.0.1:4242/api/health", 7)], "this machine, and nowhere else"


@pytest.mark.parametrize("payload,said", [
    ({"status": "degraded", "build": "34df136"}, "status 'degraded'"),
    ({"build": "34df136"}, "status None"),
    (["healthy"], "not 'healthy'"),
    (b"<html>502</html>", "not with JSON"),
    (b"", "not with JSON"),
])
def test_anything_but_healthy_json_is_not_healthy(payload, said):
    with pytest.raises(health.HealthError, match=said):
        health.probe(4242, opener=_answers(payload))


@pytest.mark.parametrize("failure", [
    urllib.error.URLError("connection refused"), ConnectionResetError("reset"), TimeoutError("slow")])
def test_nothing_answering_is_not_healthy(failure):
    def opener(url, timeout=None):
        raise failure

    with pytest.raises(health.HealthError, match="nothing healthy answered on port 4242"):
        health.probe(4242, opener=opener)


@pytest.mark.parametrize("port", [0, -1, 65536, "4242", 4242.0, None, True])
def test_only_a_port_number_is_asked(port):
    with pytest.raises(health.HealthError, match="is not a port"):
        health.probe(port, opener=lambda *a, **k: pytest.fail("a request was made"))


class Clock:
    def __init__(self):
        self.now, self.slept = 0.0, []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def test_waiting_keeps_asking_until_the_instance_answers():
    """A service that was just started refuses connections for a few seconds."""
    clock, asked = Clock(), []

    def ask(port):
        asked.append(port)
        if len(asked) < 4:
            raise health.HealthError("connection refused")
        return {"status": "healthy", "build": "34df136"}

    answer = health.wait_healthy(4242, within=90, every=2, ask=ask, sleep=clock.sleep, clock=clock)
    assert answer["build"] == "34df136"
    assert asked == [4242] * 4 and clock.slept == [2, 2, 2]


def test_waiting_gives_up_after_the_time_allowed_and_says_what_it_last_saw():
    clock, asked = Clock(), []

    def ask(port):
        asked.append(port)
        raise health.HealthError(f"attempt {len(asked)} refused")

    with pytest.raises(health.HealthError, match=r"not healthy within 10s: attempt 6 refused"):
        health.wait_healthy(4242, within=10, every=2, ask=ask, sleep=clock.sleep, clock=clock)
    assert len(asked) == 6, "asked at 0, 2, 4, 6, 8 and 10 seconds, then stopped"


def test_an_instance_that_is_healthy_at_once_is_not_waited_for():
    clock = Clock()
    health.wait_healthy(4242, ask=lambda port: {"status": "healthy"}, sleep=clock.sleep, clock=clock)
    assert clock.slept == []


@pytest.mark.parametrize("build,expected", [
    ("34df136", True),                    # a clean checkout
    ("34df136-unverified", True),         # the service account could not ask git; normal
    ("34df136c0ffee", True),              # a longer abbreviation of the same commit
    ("34df136-dirty", False),             # edited in place: the commit is not what runs
    ("b91cbff", False),                   # another commit: the restart did nothing
    ("b91cbff-unverified", False),
    ("34df13", False),                    # too short to name a commit
    ("", False), (None, False),
    ("invalid-stamp", False),
    ("34df136-unverified-dirty", False),
])
def test_which_reported_builds_count_as_this_commit(build, expected):
    assert health.reports_commit(build, COMMIT) is expected


def test_no_commit_matches_nothing():
    assert health.reports_commit("34df136", "") is False
