"""#254 — a machine with no ADMZ_HOME must not kill ADMZ at import.

Before this, twenty places created the data directory: twelve with an ad-hoc
``mkdir(parents=True, exist_ok=True)`` and eight not at all. The eight went
straight to ``sqlite3.connect`` in a module-level singleton's ``__init__``, so
on a fresh machine the first one imported raised::

    sqlite3.OperationalError: unable to open database file

Measured before the fix: ``python -m admz mcp`` — the README's documented MCP
quickstart — exited 1, as did ``admz api`` and ``admz maintenance migrate``.
Meanwhile ``admz api-key list`` and ``admz settings list`` worked *and* created
the directory, because they happen to route through one of the twelve. That
inconsistency was the real defect; the crash was just its most visible face.

**Why these are subprocess tests.** The thing under test is import-time
behaviour. By the time pytest has collected anything, every singleton in this
interpreter already exists and the directory already exists with it. There is
no in-process way to observe a fresh install — the only honest harness is a
clean interpreter with a clean environment. ``tests/test_api_import_isolation``
uses the same shape for the same reason.

**The vacuity trap, which is the whole risk here.** A test that points
ADMZ_HOME at ``tmp_path`` proves nothing: ``tmp_path`` already exists, so every
one of these imports succeeds with or without the fix. Each test below points
at a *non-existent subpath* and asserts it is absent first. Without that
assertion this file would be decoration.

``HOME``/``USERPROFILE`` are pinned too: ``paths.admz_home()`` falls back to
``Path.home() / ".admz"`` when ADMZ_HOME is unset, and on a developer box that
is a real directory that already exists — which would mask the failure exactly
the same way.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Modules whose import previously died on a fresh ADMZ_HOME. The first two are
#: the entry points a user actually runs; the rest are the individual
#: singletons, listed separately so a regression in any ONE of them fails on
#: its own case rather than hiding behind another.
IMPORTS_THAT_MUST_SURVIVE = [
    "admz.api.main",          # `admz api` — the Windows service
    "admz.mcp.server",        # `admz mcp` — the README's MCP quickstart
    "admz.tasks.store",       # first to fail in the web process
    "admz.api.capture",       # first to fail in the MCP subprocess
    "admz.api.confirm_store",
    "admz.chatbot.sessions",
    "admz.fleet_settings",
    # A few of the twelve that already created it, as a regression guard.
    "admz.events.store",
    "admz.audit",
    "admz.api_keys",
]


def _run(statement: str, home: Path) -> subprocess.CompletedProcess:
    """Execute *statement* in a clean interpreter with *home* as ADMZ_HOME."""
    env = dict(os.environ)
    env["ADMZ_HOME"] = str(home)
    env["HOME"] = str(home.parent)
    env["USERPROFILE"] = str(home.parent)
    env["PYTHONPATH"] = str(REPO_ROOT)
    for name in ("ADMZ_DB_PATH", "ADMZ_KEY_PATH", "ADMZ_CONFIG_REPO_PATH",
                 "ADMZ_REPO_PATH_ROOT", "ADMZ_SURVEY_OUT", "ADMZ_SURVEY_WORK"):
        env.pop(name, None)
    return subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True, text=True, env=env, timeout=300,
    )


class TestFreshInstall:
    @pytest.mark.parametrize("module", IMPORTS_THAT_MUST_SURVIVE)
    def test_import_survives_a_missing_admz_home(self, module, tmp_path):
        home = tmp_path / "never-created"
        assert not home.exists(), "the fixture must start with NO ADMZ_HOME"

        result = _run(f"import {module}", home)

        assert result.returncode == 0, (
            f"importing {module} on a fresh ADMZ_HOME failed:\n{result.stderr}"
        )
        assert "unable to open database file" not in result.stderr

    def test_importing_the_app_no_longer_creates_the_directory(self, tmp_path):
        """CONTRACT CHANGE, #254 -> #258.

        This used to assert that importing ``admz.api.main`` CREATED
        ADMZ_HOME. That was #254's contract: every store called
        ``ensure_parent_dir`` from ``__init__``, so import did filesystem I/O
        and the directory appeared as a side effect of loading the app.

        #258 removed exactly that. Stores now resolve their path at call time
        and create nothing until first use, so import is inert. The
        surrounding tests still prove a fresh install *works* -- see
        ``test_a_store_can_actually_be_used_not_merely_imported`` below, which
        is the assertion that matters and is unchanged.

        Kept rather than deleted because the inversion is the record of the
        contract moving.
        """
        home = tmp_path / "never-created"
        assert not home.exists()
        result = _run("import admz.api.main", home)
        assert result.returncode == 0, result.stderr
        assert not home.exists(), (
            "importing the app created ADMZ_HOME -- a store is doing I/O at "
            "import again (#258)"
        )

    def test_ensure_admz_home_is_what_creates_it(self, tmp_path):
        """Not just 'something made a directory' — the shared helper did."""
        home = tmp_path / "never-created"
        assert not home.exists()
        result = _run(
            "from admz import paths; "
            "print('BEFORE', paths.admz_home().exists()); "
            "print('RESULT', paths.ensure_admz_home()); "
            "print('AFTER', paths.admz_home().exists())",
            home,
        )
        assert result.returncode == 0, result.stderr
        assert "BEFORE False" in result.stdout
        assert "AFTER True" in result.stdout
        assert home.is_dir()

    def test_a_store_can_actually_be_used_not_merely_imported(self, tmp_path):
        """Import is the symptom; the point is that the store works."""
        home = tmp_path / "never-created"
        assert not home.exists()
        result = _run(
            "from admz.fleet_settings import fleet_settings; "
            "fleet_settings.set('x', 'y'); "
            "print('VALUE', fleet_settings.get('x'))",
            home,
        )
        assert result.returncode == 0, result.stderr
        assert "VALUE y" in result.stdout
        assert (home / "admz.db").is_file()

    def test_a_lazy_store_also_survives(self, tmp_path):
        """The three demo stores are constructed on first use rather than at
        import, so they crash later rather than sooner. Same defect."""
        home = tmp_path / "never-created"
        assert not home.exists()
        result = _run(
            "from admz.demos.store import get_store; "
            "print('ROWS', len(get_store().list()))",
            home,
        )
        assert result.returncode == 0, result.stderr
        assert "ROWS" in result.stdout
