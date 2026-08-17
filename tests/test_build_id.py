"""The build marker (GH #432).

``__version__`` is ``2.0.0`` and has been for months, so nothing distinguished
two builds of the same version — on screen or in ``/api/health``. After a deploy
the operator's question is "am I looking at the latest code?", and the honest
answer has to come from the checkout rather than from a note someone attached to
it (the same reasoning as #424's content comparison).
"""

from __future__ import annotations

import subprocess

from admz import build_info


def _fresh():
    """A cache-free call — build_id is lru_cached, so a test that changes the
    world underneath it would otherwise assert against the first answer."""
    build_info.build_id.cache_clear()
    try:
        return build_info.build_id()
    finally:
        build_info.build_id.cache_clear()


def test_in_a_git_checkout_it_reports_a_short_sha():
    build = _fresh()
    assert build, "this test tree is a git checkout, so a build id must resolve"
    sha = build.split("-")[0]
    assert 6 <= len(sha) <= 12 and all(c in "0123456789abcdef" for c in sha)


def test_it_matches_what_git_actually_says():
    """Control: the value is the real HEAD, not a plausible-looking string."""
    expected = subprocess.run(
        ["git", "-C", str(build_info._ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    assert _fresh().split("-")[0] == expected


def test_a_modified_tree_is_marked_dirty(monkeypatch):
    """Production is meant to be a clean detached checkout. ``-dirty`` means
    someone edited files in place, which is exactly the state that makes the
    commit alone a lie about what is running."""
    monkeypatch.setattr(
        build_info.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, stdout=("abc1234\n" if "rev-parse" in cmd else " M admz/x.py\n"), stderr=""),
    )
    assert _fresh() == "abc1234-dirty"


def test_a_clean_tree_is_not_marked(monkeypatch):
    """Control for the test above — same path, empty status."""
    monkeypatch.setattr(
        build_info.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, stdout=("abc1234\n" if "rev-parse" in cmd else ""), stderr=""),
    )
    assert _fresh() == "abc1234"


def test_a_failed_status_check_says_unverified_not_clean(monkeypatch):
    """'Clean' is the reassuring answer and the wrong one to guess at."""
    def fake(cmd, **kw):
        if "rev-parse" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="abc1234\n", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")
    monkeypatch.setattr(build_info.subprocess, "run", fake)
    assert _fresh() == "abc1234-unverified"


def test_outside_a_git_checkout_it_reports_nothing(monkeypatch, tmp_path):
    """An installed wheel or a container layer is a real deployment shape.

    None renders as nothing; 'unknown' would read as a fault.
    """
    monkeypatch.setattr(build_info, "_ROOT", tmp_path)
    assert _fresh() is None


def test_a_git_failure_reports_nothing_rather_than_raising(monkeypatch):
    """A page render must not 500 because git is missing."""
    def boom(*a, **kw):
        raise OSError("git not found")
    monkeypatch.setattr(build_info.subprocess, "run", boom)
    assert _fresh() is None


def test_it_is_cached_so_a_page_render_does_not_shell_out(monkeypatch):
    calls = []
    real = build_info.subprocess.run

    def counting(cmd, **kw):
        calls.append(cmd)
        return real(cmd, **kw)

    build_info.build_id.cache_clear()
    monkeypatch.setattr(build_info.subprocess, "run", counting)
    build_info.build_id()
    first = len(calls)
    for _ in range(5):
        build_info.build_id()
    assert len(calls) == first, "build_id must resolve once, not per call"
    build_info.build_id.cache_clear()


def test_health_reports_the_build():
    """The machine-readable half — this is what a deploy check would read."""
    from fastapi.testclient import TestClient
    from admz.api.main import app

    with TestClient(app) as client:
        body = client.get("/api/health").json()
    assert "build" in body, "/api/health must say which build answered"
    assert body["build"] == build_info.build_id()


def test_every_page_gets_the_build_global():
    """A Jinja global, not a per-route key: a route that forgot to pass it would
    render nothing, which reads as 'no build info' rather than 'route bug'."""
    from admz.api.routes.web import templates

    assert "build_id" in templates.env.globals
