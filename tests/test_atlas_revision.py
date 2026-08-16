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

def test_the_two_parsers_of_ATLAS_SHA_agree():
    """``tools/environments.py`` and the CI script read one literal.

    Two parsers of the same constant is two things to break, and they drift in
    the stale direction. This is the join, not a comment asking people to keep
    them in step.
    """
    script = REPO / ".github" / "scripts" / "assert_atlas_provenance.py"
    src = script.read_text(encoding="utf-8")
    # The CI script's own regex, applied to setup.py exactly as it applies it.
    ci_pattern = re.search(
        r're\.search\(\s*r(["\'])(\^ATLAS_SHA.*?)\1', src, re.DOTALL
    )
    assert ci_pattern, "the CI script no longer contains a recognisable ATLAS_SHA regex"
    setup_src = (REPO / "setup.py").read_text(encoding="utf-8")
    ci_match = re.search(ci_pattern.group(2), setup_src, re.MULTILINE)
    assert ci_match, "the CI script's regex finds no ATLAS_SHA in setup.py"
    assert env.expected_atlas_sha() == ci_match.group(1).lower()


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


def _patch(monkeypatch, python, kind, revision):
    monkeypatch.setattr(env, "install_kind", lambda p: (kind, "file:///somewhere"))
    monkeypatch.setattr(env, "atlas_revision", lambda p: revision)


def test_a_mismatched_copy_install_fails_the_run(monkeypatch, fake_venv):
    venv, python = fake_venv
    _patch(monkeypatch, python, "copy", ("content DOES NOT MATCH pin abc1234", True))
    problem = env.atlas_problem("production", str(venv))
    assert problem is not None
    assert "production" in problem and "DOES NOT MATCH" in problem


def test_a_matching_copy_install_does_not(monkeypatch, fake_venv):
    """Control for the test above — same path, opposite verdict."""
    venv, python = fake_venv
    _patch(monkeypatch, python, "copy", ("content MATCHES pin abc1234 (813 files)", False))
    assert env.atlas_problem("production", str(venv)) is None


def test_a_mismatched_EDITABLE_install_does_not_fail(monkeypatch, fake_venv):
    """The distinction this rule exists for: an editable install points at a
    working tree on purpose, so a mismatch is ordinary atlas development."""
    venv, python = fake_venv
    _patch(monkeypatch, python, "editable", ("content DOES NOT MATCH pin abc1234", True))
    assert env.atlas_problem("dev", str(venv)) is None


def test_cannot_verify_never_fails(monkeypatch, fake_venv):
    """No atlas repo on the machine is a reason to look, not to block."""
    venv, python = fake_venv
    _patch(monkeypatch, python, "copy", ("cannot verify against abc1234 — no atlas repo", False))
    assert env.atlas_problem("production", str(venv)) is None


def test_no_venv_declared_is_not_a_problem(monkeypatch):
    assert env.atlas_problem("staging", None) is None


def test_a_venv_path_that_does_not_exist_is_not_a_problem(tmp_path):
    assert env.atlas_problem("ghost", str(tmp_path / "nope")) is None
