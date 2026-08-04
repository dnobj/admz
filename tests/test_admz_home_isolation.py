"""#257 — the suite must never resolve ADMZ_HOME to a real data directory.

Read the vacuity note before adding to this file.

A test that merely asserts "the suite isn't pointed at production" is
**trivially green**, because after ``tests/conftest.py`` runs the redirect it
is pointed at a temp directory no matter what. Asserting that proves the
redirect happened; it proves nothing about the guard, which is the half that
protects test file 168.

So the guard is tested by *constructing the bad condition and asserting the
refusal* — both at the function level and, in ``TestRefusesToRun``, by running
a real pytest process and checking it exits non-zero with a message naming the
offending path.

What each group proves:

* ``TestGuardLogic``      — the allowlist itself: which paths are rejected.
* ``TestThisSessionIsIsolated`` — the redirect took effect in *this* process.
* ``TestRefusesToRun``    — the wiring: a failing guard actually stops pytest.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# tests/ is a package (tests/__init__.py), so siblings import via `tests.`.
# Importing tests.conftest here does NOT re-run its module body: pytest has
# already imported it under exactly that name, so this is a sys.modules hit.
from tests._admz_isolation import (
    SPECIFIC_OVERRIDES,
    assert_isolated,
    format_refusal,
    redirect_to_throwaway,
    resolve_all,
    violations,
)
from tests.conftest import TEST_ADMZ_HOME

# A production-shaped path. Never touched — only ever compared as a string.
PRODUCTION = r"C:\ProgramData\admz" if sys.platform == "win32" else "/var/lib/admz"


def _resolved(home: str) -> dict:
    """The shape resolve_all() returns, for an arbitrary base."""
    base = Path(home)
    return {
        "admz_home": base,
        "db_path": base / "admz.db",
        "key_path": base / "admz.key",
    }


class TestGuardLogic:
    """The allowlist. Pure — no environment mutation, runs everywhere."""

    def test_production_path_is_a_violation(self):
        bad = violations(_resolved(PRODUCTION), TEST_ADMZ_HOME)
        assert bad, "the guard must reject a production ADMZ_HOME"
        assert any(PRODUCTION in item for item in bad)

    def test_throwaway_home_is_clean(self):
        assert violations(_resolved(TEST_ADMZ_HOME), TEST_ADMZ_HOME) == []

    def test_real_user_home_is_a_violation(self):
        """Not just ProgramData. ``~/.admz`` is the dev default and is just as
        real — which is why this is an allowlist and not a denylist."""
        bad = violations(_resolved(str(Path.home() / ".admz")), TEST_ADMZ_HOME)
        assert bad

    def test_a_different_temp_dir_is_still_a_violation(self):
        """The load-bearing case for allowlist-vs-denylist.

        A denylist ("not under ProgramData") would accept any other temp
        directory. The property actually wanted is "under the directory THIS
        session created", so a sibling temp dir must be rejected.
        """
        other = tempfile.mkdtemp(prefix="admz-not-ours-")
        try:
            assert violations(_resolved(other), TEST_ADMZ_HOME)
        finally:
            os.rmdir(other)

    def test_subdirectories_of_the_throwaway_home_are_allowed(self):
        nested = {"firmware_dir": Path(TEST_ADMZ_HOME) / "firmware" / "x"}
        assert violations(nested, TEST_ADMZ_HOME) == []

    def test_assert_isolated_raises_and_names_the_path(self):
        with pytest.raises(RuntimeError) as exc:
            assert_isolated(
                TEST_ADMZ_HOME,
                previous=PRODUCTION,
                resolved=_resolved(PRODUCTION),
            )
        message = str(exc.value)
        assert PRODUCTION in message, "refusal must name the offending path"
        assert "#257" in message

    def test_assert_isolated_is_silent_when_clean(self):
        assert_isolated(TEST_ADMZ_HOME, resolved=_resolved(TEST_ADMZ_HOME))

    def test_refusal_message_reports_the_inherited_override(self):
        msg = format_refusal(
            ["db_path -> " + PRODUCTION], TEST_ADMZ_HOME, PRODUCTION,
            {"ADMZ_DB_PATH": PRODUCTION + r"\admz.db"},
        )
        assert "ADMZ_DB_PATH" in msg and PRODUCTION in msg


class TestThisSessionIsIsolated:
    """The redirect, verified in the running process."""

    def test_every_admz_path_is_under_the_throwaway_home(self):
        assert violations(resolve_all(), TEST_ADMZ_HOME) == []

    def test_admz_home_is_not_the_inherited_one(self):
        from admz import paths

        resolved = str(paths.admz_home())
        assert resolved == TEST_ADMZ_HOME
        assert "ProgramData" not in resolved

    def test_specific_overrides_are_cleared(self):
        """ADMZ_DB_PATH and friends take PRECEDENCE over ADMZ_HOME (ADR-0042),
        so redirecting ADMZ_HOME alone would not be enough."""
        assert [n for n in SPECIFIC_OVERRIDES if n in os.environ] == []

    def test_redirect_clears_a_hostile_specific_override(self):
        env = {"ADMZ_HOME": PRODUCTION, "ADMZ_DB_PATH": PRODUCTION + "/admz.db"}
        home, previous, cleared = redirect_to_throwaway(env)
        try:
            assert env["ADMZ_HOME"] == home
            assert "ADMZ_DB_PATH" not in env
            assert previous == PRODUCTION
            assert cleared == {"ADMZ_DB_PATH": PRODUCTION + "/admz.db"}
        finally:
            os.rmdir(home)


class TestRefusesToRun:
    """The wiring: does a failing guard actually stop pytest?

    The clobber is synthetic — nothing reachable from outside can re-point
    ADMZ_HOME between the real conftest's redirect and its ``pytest_configure``
    (the redirect clears every override and runs before collection). So the
    generated conftest below reproduces the real one's guard block *verbatim*,
    importing the real ``_admz_isolation``, and only the clobber is fabricated.
    That is the smallest possible piece of pretend.
    """

    @staticmethod
    def _run(tmp_path: Path, clobber: bool) -> subprocess.CompletedProcess:
        isolation = (
            Path(__file__).parent / "_admz_isolation.py"
        ).as_posix()
        conftest = f'''
import importlib.util, os, pytest
spec = importlib.util.spec_from_file_location("_iso", r"{isolation}")
iso = importlib.util.module_from_spec(spec); spec.loader.exec_module(iso)

HOME, PREV, CLEARED = iso.redirect_to_throwaway()
CLOBBER = {clobber!r}
if CLOBBER:
    os.environ["ADMZ_HOME"] = r"{PRODUCTION}"

def pytest_configure(config):
    try:
        iso.assert_isolated(HOME, previous=PREV, cleared=CLEARED)
    except RuntimeError as exc:
        raise pytest.UsageError(str(exc)) from exc
'''
        (tmp_path / "conftest.py").write_text(conftest, encoding="utf-8")
        (tmp_path / "test_trivial.py").write_text(
            "def test_ok():\n    assert True\n", encoding="utf-8"
        )
        env = dict(os.environ)
        env["ADMZ_HOME"] = PRODUCTION
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        return subprocess.run(
            [sys.executable, "-m", "pytest", str(tmp_path), "-q", "--no-cov",
             "-p", "no:cacheprovider", "-p", "no:randomly"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path),
            timeout=300,
        )

    def test_pytest_refuses_when_admz_home_is_production(self, tmp_path):
        result = self._run(tmp_path, clobber=True)
        combined = result.stdout + result.stderr
        assert result.returncode != 0, f"pytest should have refused:\n{combined}"
        assert "ADMZ test isolation FAILED" in combined
        assert PRODUCTION in combined
        assert "test_ok" not in combined, "no test may run after a refusal"

    def test_pytest_runs_normally_when_isolated(self, tmp_path):
        """The control. Without this, the test above could pass because pytest
        was broken for some unrelated reason."""
        result = self._run(tmp_path, clobber=False)
        combined = result.stdout + result.stderr
        assert result.returncode == 0, combined
        assert "ADMZ test isolation FAILED" not in combined
        assert "1 passed" in combined

    def test_real_suite_ignores_a_hostile_inherited_admz_home(self, tmp_path):
        """End-to-end on the REAL tests/conftest.py: hand a pytest process an
        ADMZ_HOME pointing at a directory that must not be touched, and prove
        it is neither used nor created."""
        forbidden = tmp_path / "pretend-production"
        assert not forbidden.exists()

        env = dict(os.environ)
        env["ADMZ_HOME"] = str(forbidden)
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-m", "pytest",
             "tests/test_admz_home_isolation.py::TestThisSessionIsIsolated",
             "-q", "--no-cov", "-p", "no:cacheprovider"],
            capture_output=True, text=True, env=env, cwd=str(repo), timeout=600,
        )
        combined = result.stdout + result.stderr
        assert result.returncode == 0, combined
        assert "redirected to" in combined
        assert not forbidden.exists(), (
            "the inherited ADMZ_HOME was created — the redirect did not hold"
        )
