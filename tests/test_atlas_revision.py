"""The atlas revision check in ``tools/environments.py`` (GH #424).

Production installs atlas from a local directory, so PEP 610 records
``dir_info`` and **no commit** — and the CI script's revision check explicitly
skips that shape. Nothing could name the commit production was running, and an
ungated ``pwdgrp.cgi:add-user`` sat live for six days behind that blind spot.

Every test here carries its own control. A check that reports "matches" is
indistinguishable from a check that always reports "matches", so each assertion
that something passes is paired with a mutation proving it can fail.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools import environments as env

REPO = Path(__file__).resolve().parents[1]


# ── the pin is parsed identically in both places ─────────────────────────────

def _ci_module():
    """Load ``assert_atlas_provenance.py`` and return it as a module.

    Importing it rather than re-reading its source is the point. The first
    version of this test extracted the CI script's regex *text* and re-applied
    it with the test's own ``re.MULTILINE`` — so deleting ``re.MULTILINE`` from
    the CI script made its ``_expected_sha()`` return None, silently skipping
    the revision check on every CI run forever, while this test stayed green.
    Calling the real function also exercises its ``SETUP_PY`` path resolution
    and its ``.lower()``, neither of which the text-matching version touched.
    """
    import importlib.util

    path = REPO / ".github" / "scripts" / "assert_atlas_provenance.py"
    spec = importlib.util.spec_from_file_location("_ci_atlas_provenance", path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_two_parsers_of_ATLAS_SHA_agree():
    """``tools/environments.py`` and the CI script read one literal.

    Two parsers of the same constant is two things to break, and they drift in
    the stale direction. This calls both and compares, so a change to either
    that alters the answer fails here.
    """
    ci = _ci_module()
    ci_sha = ci._expected_sha()
    assert ci_sha, "the CI script's own parser finds no ATLAS_SHA in setup.py"
    assert env.expected_atlas_sha() == ci_sha


def test_the_CI_parser_resolves_setup_py_where_it_expects():
    """The CI script computes ``SETUP_PY`` by walking up from its own location.

    If the script moves, that resolution breaks and ``_expected_sha`` returns
    None — the silent-skip path again. Pin the file it actually reads.
    """
    ci = _ci_module()
    assert Path(ci.SETUP_PY).resolve() == (REPO / "setup.py").resolve()


def test_expected_atlas_sha_is_a_real_sha():
    sha = env.expected_atlas_sha()
    assert sha and re.fullmatch(r"[0-9a-f]{40}", sha)


# ── the digest actually discriminates ───────────────────────────────────────

def test_digest_changes_when_one_byte_of_one_file_changes():
    """Positive control: the whole check rests on this being content-sensitive."""
    base = {"a/x.yaml": b"risk_level: normal\n", "b/y.yaml": b"k: v\n"}
    mutated = dict(base, **{"a/x.yaml": b"risk_level: service-affecting\n"})
    assert env._digest(base) != env._digest(mutated)


def test_digest_changes_when_a_file_is_added_or_removed():
    base = {"a/x.yaml": b"k: v\n", "b/y.yaml": b"k: v\n"}
    assert env._digest(base) != env._digest({"a/x.yaml": b"k: v\n"})
    assert env._digest(base) != env._digest(dict(base, **{"c/z.yaml": b"k: v\n"}))


def test_digest_notices_content_moving_between_paths():
    """Same bytes, different names, must not collide."""
    assert env._digest({"a.yaml": b"x"}) != env._digest({"b.yaml": b"x"})


def test_digest_is_order_independent():
    one = {"a.yaml": b"1", "b.yaml": b"2"}
    other = {"b.yaml": b"2", "a.yaml": b"1"}
    assert env._digest(one) == env._digest(other)


# ── line endings: the false-mismatch trap ───────────────────────────────────

def test_crlf_and_lf_of_the_same_content_agree():
    """A git blob holds LF; a Windows checkout writes CRLF, and the installed
    copy comes from a checkout. Without this, every file reads as different on
    this machine — a false mismatch, which is worse than no check because it
    teaches the reader to ignore the line."""
    assert env._digest({"a.yaml": b"k: v\r\nj: w\r\n"}) == env._digest(
        {"a.yaml": b"k: v\nj: w\n"}
    )


def test_the_normalizer_is_doing_that_and_not_something_broader():
    """Control on the control: normalization must not flatten real differences."""
    assert env._digest({"a.yaml": b"k: v\n"}) != env._digest({"a.yaml": b"k: w\n"})


def test_binary_content_survives_normalization():
    raw = b"\x89PNG\r\n\x1a\n\x00\xff"
    assert env._normalize(raw) == raw


# ── which mismatches fail the run ───────────────────────────────────────────

@pytest.fixture
def fake_venv(tmp_path):
    """A directory shaped like a venv, so ``atlas_problem`` gets past its
    existence checks without a real interpreter."""
    python = tmp_path / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")
    return tmp_path, python


def _patch(monkeypatch, kind, revision):
    """Stand in for the two probes that need a real interpreter."""
    monkeypatch.setattr(env, "install_kind", lambda p: (kind, "file:///somewhere"))
    monkeypatch.setattr(env, "atlas_revision", lambda p: revision)


MISMATCH_MSG = ("content DOES NOT MATCH pin abc1234", env.MISMATCH)
MATCH_MSG = ("content MATCHES pin abc1234 (813 files)", env.MATCH)
UNREADABLE_MSG = ("installed data tree is missing, empty or unreadable", env.UNREADABLE)
UNVERIFIABLE_MSG = ("cannot verify against abc1234 - no atlas repo", env.UNVERIFIABLE)
BROKEN_MSG = ("cannot verify against abc1234 - BROKEN: prefix matches nothing", env.BROKEN)


# -- observed kind vs DECLARED kind: the hole #424's review found -------------

def test_an_editable_install_where_copy_is_declared_fails(monkeypatch, fake_venv):
    """The ADR-0054 violation. Production rebuilt with `pip install -e` used to
    exempt itself, because the gate asked the installation what kind it was."""
    venv, _ = fake_venv
    _patch(monkeypatch, "editable", MATCH_MSG)
    problem = env.atlas_problem("production", str(venv), "copy")
    assert problem and "declares atlas 'copy'" in problem and "'editable'" in problem


def test_a_git_install_where_copy_is_declared_fails(monkeypatch, fake_venv):
    """Same hole, different shape: a VCS reinstall at any commit. It used to
    return early on the claim that CI covers it -- CI checks CI's venv."""
    venv, _ = fake_venv
    _patch(monkeypatch, "commit", MATCH_MSG)
    assert env.atlas_problem("production", str(venv), "copy") is not None


def test_atlas_missing_entirely_where_copy_is_declared_fails(monkeypatch, fake_venv):
    """`unknown` came from PackageNotFoundError -- a venv with no atlas at all
    used to pass the atlas check clean."""
    venv, _ = fake_venv
    _patch(monkeypatch, "unknown", MATCH_MSG)
    assert env.atlas_problem("production", str(venv), "copy") is not None


def test_an_index_install_fails_and_says_so(monkeypatch, fake_venv):
    """#179: the name is unregistered on PyPI, so an index install is someone
    else's code inside the venv the service runs as LocalSystem."""
    venv, _ = fake_venv
    _patch(monkeypatch, "index", MATCH_MSG)
    problem = env.atlas_problem("production", str(venv), "copy")
    assert problem and "INDEX" in problem


def test_a_copy_install_where_editable_is_declared_also_fails(monkeypatch, fake_venv):
    """Both directions. A dev box silently holding a frozen copy is drift too."""
    venv, _ = fake_venv
    _patch(monkeypatch, "copy", MATCH_MSG)
    assert env.atlas_problem("dev", str(venv), "editable") is not None


def test_the_declared_kind_matching_is_the_only_reason_those_passed(monkeypatch, fake_venv):
    """Control for all five above: same inputs, correct declaration, no problem."""
    venv, _ = fake_venv
    _patch(monkeypatch, "editable", MATCH_MSG)
    assert env.atlas_problem("dev", str(venv), "editable") is None


# -- content verdicts, given the kind is as declared --------------------------

def test_a_mismatched_copy_install_fails_the_run(monkeypatch, fake_venv):
    venv, _ = fake_venv
    _patch(monkeypatch, "copy", MISMATCH_MSG)
    problem = env.atlas_problem("production", str(venv), "copy")
    assert problem and "production" in problem and "DOES NOT MATCH" in problem


def test_a_matching_copy_install_does_not(monkeypatch, fake_venv):
    """Control for the test above -- same path, opposite verdict."""
    venv, _ = fake_venv
    _patch(monkeypatch, "copy", MATCH_MSG)
    assert env.atlas_problem("production", str(venv), "copy") is None


def test_a_mismatched_EDITABLE_install_does_not_fail(monkeypatch, fake_venv):
    """An editable install points at a working tree on purpose, so a content
    mismatch is ordinary atlas development."""
    venv, _ = fake_venv
    _patch(monkeypatch, "editable", MISMATCH_MSG)
    assert env.atlas_problem("dev", str(venv), "editable") is None


def test_an_unreadable_tree_on_a_copy_install_fails(monkeypatch, fake_venv):
    """For a deployment, "I cannot read what is on disk" is at least as alarming
    as "it is the wrong thing". This used to pass silently."""
    venv, _ = fake_venv
    _patch(monkeypatch, "copy", UNREADABLE_MSG)
    assert env.atlas_problem("production", str(venv), "copy") is not None


def test_an_unreadable_tree_on_an_editable_install_does_not(monkeypatch, fake_venv):
    venv, _ = fake_venv
    _patch(monkeypatch, "editable", UNREADABLE_MSG)
    assert env.atlas_problem("dev", str(venv), "editable") is None


def test_unverifiable_never_fails_either_kind(monkeypatch, fake_venv):
    """No atlas repo on this machine is a reason to look, not to block."""
    venv, _ = fake_venv
    _patch(monkeypatch, "copy", UNVERIFIABLE_MSG)
    assert env.atlas_problem("production", str(venv), "copy") is None
    _patch(monkeypatch, "editable", UNVERIFIABLE_MSG)
    assert env.atlas_problem("dev", str(venv), "editable") is None


def test_a_BROKEN_check_fails_even_on_an_editable_install(monkeypatch, fake_venv):
    """BROKEN means the mechanism itself cannot run -- an atlas layout change
    would otherwise disable it permanently while blaming a missing repo."""
    venv, _ = fake_venv
    _patch(monkeypatch, "copy", BROKEN_MSG)
    assert env.atlas_problem("production", str(venv), "copy") is not None
    _patch(monkeypatch, "editable", BROKEN_MSG)
    assert env.atlas_problem("dev", str(venv), "editable") is not None


def test_declared_none_skips_the_check(monkeypatch, fake_venv):
    """Staging declares no atlas; it has no venv of its own."""
    venv, _ = fake_venv
    _patch(monkeypatch, "index", BROKEN_MSG)
    assert env.atlas_problem("staging", str(venv), "none") is None


def test_no_venv_declared_is_not_a_problem(monkeypatch):
    assert env.atlas_problem("staging", None, "copy") is None


def test_a_venv_path_that_does_not_exist_is_not_a_problem(tmp_path):
    assert env.atlas_problem("ghost", str(tmp_path / "nope"), "copy") is None


# ── the REAL atlas_revision, not the mock ───────────────────────────────────
#
# The tests above patch `atlas_revision` wholesale, so they prove the dispatch
# in `atlas_problem` and nothing about the function that produces the verdict.
# The review of #425 caught that: flipping the cannot-verify branch's status
# would not have failed a single test. These drive the real function and patch
# only the two probes that need an interpreter and a git repo.

@pytest.fixture
def real_revision(monkeypatch):
    """Drive the real ``atlas_revision`` with controlled probe results.

    Clears the lru_cache around each use — otherwise the second call in a test
    (or the next test, keyed on the same Path) returns the first verdict and the
    assertion passes for the wrong reason.
    """
    def drive(*, kind="copy", installed=("aaa", 813), pinned=("aaa", 813, None), sha="a" * 40):
        env.atlas_revision.cache_clear()
        env.install_kind.cache_clear()
        monkeypatch.setattr(env, "expected_atlas_sha", lambda: sha)
        monkeypatch.setattr(env, "install_kind", lambda p: (kind, "file:///x"))
        monkeypatch.setattr(env, "installed_atlas_digest", lambda p: installed)
        monkeypatch.setattr(env, "atlas_digest_at", lambda s: pinned)
        return env.atlas_revision(Path("/fake/python"))
    yield drive
    # Defensively: by teardown these attributes may still be the monkeypatched
    # lambdas, which have no cache to clear.
    for fn in (env.atlas_revision, env.install_kind):
        clear = getattr(fn, "cache_clear", None)
        if clear is not None:
            clear()


def test_real_equal_digests_report_MATCH(real_revision):
    message, status = real_revision(installed=("same", 813), pinned=("same", 813, None))
    assert status == env.MATCH and "MATCHES" in message


def test_real_differing_digests_report_MISMATCH(real_revision):
    """Control for the test above — one field changed, opposite verdict."""
    message, status = real_revision(installed=("one", 813), pinned=("other", 812, None))
    assert status == env.MISMATCH and "DOES NOT MATCH" in message


def test_real_unreadable_installed_tree_reports_UNREADABLE(real_revision):
    _, status = real_revision(installed=(None, 0))
    assert status == env.UNREADABLE


def test_real_missing_repo_reports_UNVERIFIABLE_not_a_mismatch(real_revision):
    """The branch the previous test suite could not see at all."""
    message, status = real_revision(pinned=(None, 0, "no atlas repo beside this one"))
    assert status == env.UNVERIFIABLE
    assert "no atlas repo" in message


def test_real_BROKEN_reason_is_promoted_to_BROKEN_status(real_revision):
    """A reason prefixed BROKEN must not be filed under 'cannot verify' — that
    is how an atlas layout change would disable the check permanently."""
    _, status = real_revision(pinned=(None, 0, "BROKEN: prefix matches nothing"))
    assert status == env.BROKEN


def test_real_unreadable_pin_reports_UNVERIFIABLE(real_revision):
    _, status = real_revision(sha=None)
    assert status == env.UNVERIFIABLE


def test_real_git_install_at_the_wrong_commit_is_a_MISMATCH(monkeypatch):
    """A VCS install records its commit, so compare it directly rather than
    assuming CI covers it — CI checks CI's venv, not this machine."""
    env.atlas_revision.cache_clear()
    monkeypatch.setattr(env, "expected_atlas_sha", lambda: "b" * 40)
    monkeypatch.setattr(env, "install_kind", lambda p: ("commit", "c" * 40))
    message, status = env.atlas_revision(Path("/fake/python2"))
    assert status == env.MISMATCH and "but the pin is" in message
    env.atlas_revision.cache_clear()


def test_real_git_install_at_the_right_commit_is_a_MATCH(monkeypatch):
    """Control for the test above."""
    env.atlas_revision.cache_clear()
    monkeypatch.setattr(env, "expected_atlas_sha", lambda: "b" * 40)
    monkeypatch.setattr(env, "install_kind", lambda p: ("commit", "B" * 40))  # case-insensitive
    _, status = env.atlas_revision(Path("/fake/python3"))
    assert status == env.MATCH
    env.atlas_revision.cache_clear()
