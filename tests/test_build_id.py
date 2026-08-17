"""The build marker (GH #432), and the reason it reported null in production (#434).

``__version__`` is ``2.0.0``, so nothing distinguished two builds of the same
version. The first implementation shelled out to ``git rev-parse`` — which
works for the user who owns the checkout and **fails for the service**, because
production runs as LocalSystem against a tree owned by the operator and git
refuses with "dubious ownership".

Every test passed, because tests run as the owner. The fix reads ``.git``
directly for the commit and keeps git only for the dirty flag, which nothing
else can answer.
"""

from __future__ import annotations

import subprocess

from admz import build_info


def _fresh():
    """A cache-free call — ``build_id`` is lru_cached, so a test that changes
    the world underneath it would otherwise assert against the first answer."""
    build_info.build_id.cache_clear()
    try:
        return build_info.build_id()
    finally:
        build_info.build_id.cache_clear()


# ── against this real checkout ──────────────────────────────────────────────

def test_in_a_git_checkout_it_reports_a_short_sha():
    build = _fresh()
    assert build, "this test tree is a git checkout, so a build id must resolve"
    sha = build.split("-")[0]
    assert len(sha) == 7 and all(c in "0123456789abcdef" for c in sha)


def test_it_matches_what_git_actually_says():
    """Control: the value is the real HEAD, not a plausible-looking string."""
    expected = subprocess.run(
        ["git", "-C", str(build_info._ROOT), "rev-parse", "--short=7", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    assert _fresh().split("-")[0] == expected


# ── the bug this fixes ──────────────────────────────────────────────────────

def test_when_git_cannot_be_asked_the_commit_still_resolves(monkeypatch):
    """THE DEFECT (#434).

    The service runs as LocalSystem against a checkout owned by the operator,
    so git exits non-zero with "dubious ownership". The first version shelled
    out for the commit too, so the whole marker collapsed to None and
    /api/health reported "build": null — in the one environment the feature
    was built for.
    """
    monkeypatch.setattr(build_info, "_read_head", lambda d: "abc1234")
    monkeypatch.setattr(build_info, "_worktree_is_dirty", lambda r: None)
    got = _fresh()
    assert got == "abc1234-unverified"
    assert got is not None, "a build id must not vanish because git said no"


def test_a_failing_git_status_reports_unverified_not_clean(monkeypatch):
    """Through the real ``_worktree_is_dirty``. 'Clean' is the reassuring answer
    and the wrong one to guess at — guessing reassurance is what produced the
    null in the first place."""
    monkeypatch.setattr(build_info, "_read_head", lambda d: "abc1234")
    monkeypatch.setattr(
        build_info.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 128, stdout="", stderr="detected dubious ownership"),
    )
    assert _fresh() == "abc1234-unverified"


def test_a_git_failure_does_not_raise(monkeypatch):
    """A page render must not 500 because git is missing — and must still
    report the commit, which now comes from the file."""
    def boom(*a, **kw):
        raise OSError("git not found")
    monkeypatch.setattr(build_info, "_read_head", lambda d: "abc1234")
    monkeypatch.setattr(build_info.subprocess, "run", boom)
    got = _fresh()
    assert got == "abc1234-unverified"


# ── dirty / clean ───────────────────────────────────────────────────────────

def test_a_modified_tree_is_marked_dirty(monkeypatch):
    """Production is meant to be a clean detached checkout, so ``-dirty`` is
    the state that makes a commit alone a lie about what is running."""
    monkeypatch.setattr(build_info, "_read_head", lambda d: "abc1234")
    monkeypatch.setattr(build_info, "_worktree_is_dirty", lambda r: True)
    assert _fresh() == "abc1234-dirty"


def test_a_clean_tree_is_not_marked(monkeypatch):
    """Control for the test above — same path, opposite answer."""
    monkeypatch.setattr(build_info, "_read_head", lambda d: "abc1234")
    monkeypatch.setattr(build_info, "_worktree_is_dirty", lambda r: False)
    assert _fresh() == "abc1234"


# ── reading .git without git ────────────────────────────────────────────────

def test_a_detached_HEAD_is_read_straight_from_the_file(tmp_path):
    """Production's shape: HEAD holds the sha, no ref indirection."""
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("fcd22e1ab374476c1500bad904c2356353ea39a0\n")
    assert build_info._read_head(git) == "fcd22e1"


def test_a_branch_HEAD_follows_the_loose_ref(tmp_path):
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/master\n")
    (git / "refs" / "heads" / "master").write_text(
        "1234567890abcdef1234567890abcdef12345678\n")
    assert build_info._read_head(git) == "1234567"


def test_a_branch_HEAD_falls_back_to_packed_refs(tmp_path):
    """A freshly cloned or gc'd repo has no loose ref file."""
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/master\n")
    (git / "packed-refs").write_text(
        "# pack-refs with: peeled fully-peeled sorted\n"
        "abcdef1234567890abcdef1234567890abcdef12 refs/heads/master\n"
    )
    assert build_info._read_head(git) == "abcdef1"


def test_an_unresolvable_ref_reports_nothing(tmp_path):
    """Control for the three above: the reader must be able to fail."""
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/nope\n")
    assert build_info._read_head(git) is None


def test_a_worktrees_git_FILE_is_followed(tmp_path, monkeypatch):
    """Dev work happens in worktrees, where .git is a file pointing elsewhere."""
    real = tmp_path / "realgit"
    real.mkdir()
    (real / "HEAD").write_text("aaaaaaa1111111111111111111111111111111111\n")
    root = tmp_path / "wt"
    root.mkdir()
    (root / ".git").write_text(f"gitdir: {real}\n")
    monkeypatch.setattr(build_info, "_ROOT", root)
    monkeypatch.setattr(build_info, "_worktree_is_dirty", lambda r: False)
    assert _fresh() == "aaaaaaa"


def test_outside_a_git_checkout_it_reports_nothing(monkeypatch, tmp_path):
    """An installed wheel or container layer is a real deployment shape.
    None renders as nothing; 'unknown' would read as a fault."""
    monkeypatch.setattr(build_info, "_ROOT", tmp_path)
    assert _fresh() is None


# ── wiring ──────────────────────────────────────────────────────────────────

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
    """The machine-readable half — what a deploy check would read."""
    from fastapi.testclient import TestClient
    from admz.api.main import app

    with TestClient(app) as client:
        body = client.get("/api/health").json()
    assert "build" in body
    assert body["build"] == build_info.build_id()


def test_every_page_gets_the_build_global():
    from admz.api.routes.web import templates

    assert "build_id" in templates.env.globals


def test_a_linked_worktrees_refs_resolve_via_commondir(tmp_path, monkeypatch):
    """The second half of #434, found while fixing the first.

    A linked worktree's gitdir holds its own HEAD but NOT its refs — those live
    in the main repository, named by a `commondir` file. Resolving against the
    worktree gitdir alone finds nothing, so the marker was blank in every dev
    worktree while working in production's plain clone. Opposite blind spot to
    the ownership bug, same class: verified in one layout, shipped to another.
    """
    main = tmp_path / "main" / ".git"
    (main / "refs" / "heads").mkdir(parents=True)
    (main / "refs" / "heads" / "topic").write_text(
        "beefbeef1111111111111111111111111111111\n")

    wt_git = tmp_path / "main" / ".git" / "worktrees" / "wt"
    wt_git.mkdir(parents=True)
    (wt_git / "HEAD").write_text("ref: refs/heads/topic\n")
    (wt_git / "commondir").write_text("../..\n")

    assert build_info._read_head(wt_git) == "beefbee"
