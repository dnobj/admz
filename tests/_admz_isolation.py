"""Point the test suite's ``ADMZ_HOME`` at a throwaway directory, and refuse
to run if anything still resolves somewhere real (#257).

**Why this is not a fixture.** ``tests/conftest.py`` calls
:func:`redirect_to_throwaway` at *module level*, before pytest collects
anything. That is deliberate and it is the only thing early enough. Several
ADMZ stores construct a module-level singleton at **import** and bind their DB
path in ``__init__`` (``tasks_store``, ``capture_store``, ``confirm_store``,
``chat_sessions``, ``fleet_settings``, and the audit log — see #254). By the
time any fixture runs — even a session-scoped autouse one — the test modules
have already been imported, those singletons already exist, and they are
already pointed at whatever ``ADMZ_HOME`` said at import time. A fixture cannot
retroactively unbind them.

**Why it matters here specifically.** On the reference deployment ``ADMZ_HOME``
is a *Machine*-scoped environment variable set to ``C:\\ProgramData\\admz`` —
the live production data directory. Every process on that box inherits it,
including ``pytest``. The documented ``python -m pytest -q`` therefore resolved
to production for the ~141 test files that do not isolate themselves. CI never
saw it: runners set their own ``ADMZ_HOME`` under the runner temp, so CI is
green and silent about this and always would be.

**The redirect protects today's test files; the guard protects the next one.**
The redirect makes the *default* safe, so a new test file that forgets to
isolate inherits a throwaway directory instead of production. The guard exists
for the case where the redirect itself fails or is clobbered — a machine-level
``ADMZ_DB_PATH``, a plugin, a future conftest — and it fails the session closed
rather than letting it run against a real path.

Note that redirecting ``ADMZ_HOME`` alone is *not* sufficient. Per ADR-0042 the
specific overrides (``ADMZ_DB_PATH`` and friends) take precedence over it, so a
machine-level ``ADMZ_DB_PATH`` would still aim the suite at a real database.
They are cleared too, and the guard verifies the resolved result rather than
trusting the clear.

What is deliberately NOT done here: ``HOME`` / ``USERPROFILE`` are left alone.
Repointing them would isolate ``Path.home()``, but ~27 test files shell out to
git and ~10 run ``git commit``; git finds ``user.name``/``user.email`` via
``$HOME/.gitconfig``, and CI sets that with ``git config --global``. Moving
``HOME`` breaks those for an unrelated reason. It is unnecessary anyway:
``paths.admz_home()`` only consults ``Path.home()`` when ``ADMZ_HOME`` is unset,
and this module always sets it.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, MutableMapping, Optional, Tuple

ENV_VAR = "ADMZ_HOME"

#: Specific path overrides from ``admz/paths.py``. These take PRECEDENCE over
#: ``ADMZ_HOME`` (ADR-0042), so leaving one set would defeat the redirect.
#: Tests that isolate via ``monkeypatch.setenv("ADMZ_DB_PATH", ...)`` are
#: unaffected — monkeypatch runs per-test, long after this module-level clear.
SPECIFIC_OVERRIDES: Tuple[str, ...] = (
    "ADMZ_DB_PATH",
    "ADMZ_KEY_PATH",
    "ADMZ_CONFIG_REPO_PATH",
    "ADMZ_REPO_PATH_ROOT",
    "ADMZ_SURVEY_OUT",
    "ADMZ_SURVEY_WORK",
)


def redirect_to_throwaway(
    environ: Optional[MutableMapping[str, str]] = None,
) -> Tuple[str, Optional[str], Dict[str, str]]:
    """Create a throwaway ADMZ_HOME and point the environment at it.

    Returns ``(new_home, previous_admz_home, cleared_overrides)`` so the
    caller can report what it displaced. Callers must treat the returned
    directory as the only legitimate ADMZ_HOME for the session.
    """
    env = os.environ if environ is None else environ
    previous = env.get(ENV_VAR)
    cleared = {n: env[n] for n in SPECIFIC_OVERRIDES if n in env}

    home = tempfile.mkdtemp(prefix="admz-test-home-")
    env[ENV_VAR] = home
    for name in cleared:
        env.pop(name, None)
    return home, previous, cleared


def resolve_all() -> Dict[str, Path]:
    """Every path ``admz.paths`` can produce, resolved now.

    Imported lazily: ``admz.paths`` is pure (ADR-0042 requires call-time
    resolution and no import-time environment reads), so importing it here is
    safe and does not drag in a store.
    """
    from admz import paths

    return {
        "admz_home": paths.admz_home(),
        "db_path": paths.db_path(),
        "key_path": paths.key_path(),
        "config_repo_dir": paths.config_repo_dir(),
        "repos_root": paths.repos_root(),
        "schedules_path": paths.schedules_path(),
        "firmware_dir": paths.firmware_dir(),
        "survey_out_dir": paths.survey_out_dir(),
        "survey_work_dir": paths.survey_work_dir(),
        "dev_api_key_path": paths.dev_api_key_path(),
    }


def _is_within(candidate: Path, root: Path) -> bool:
    c = Path(os.path.realpath(str(candidate)))
    r = Path(os.path.realpath(str(root)))
    return c == r or r in c.parents


def violations(resolved: Mapping[str, Path], expected_home: str) -> List[str]:
    """Names+paths that fall outside the throwaway home.

    An allowlist, not a denylist. Checking "is it under ``C:\\ProgramData``"
    would pass anything else that happens to be real — the operator's
    ``~/.admz``, a UNC share, a second install. Requiring everything to sit
    under the directory this session created is the property that is actually
    wanted, and it holds identically on Windows, Linux and CI.
    """
    return [
        f"{name} -> {path}"
        for name, path in sorted(resolved.items())
        if not _is_within(path, Path(expected_home))
    ]


def format_refusal(
    bad: List[str], expected_home: str, previous: Optional[str],
    cleared: Optional[Mapping[str, str]] = None,
) -> str:
    lines = [
        "",
        "ADMZ test isolation FAILED - refusing to run the suite (#257).",
        "",
        "These paths resolve outside the throwaway ADMZ_HOME this session",
        "created, so running would read or write a real data directory:",
        "",
    ]
    lines += [f"    {item}" for item in bad]
    lines += ["", f"  expected everything under : {expected_home}"]
    if previous:
        lines.append(f"  inherited ADMZ_HOME was  : {previous}")
    for name, value in sorted((cleared or {}).items()):
        lines.append(f"  inherited {name:<22}: {value}")
    lines += [
        "",
        "Something re-pointed ADMZ_HOME (or a specific override) after",
        "tests/conftest.py redirected it. Fix that rather than deleting this",
        "check: the suite writes device credentials, tasks and audit rows.",
        "",
    ]
    return "\n".join(lines)


def assert_isolated(
    expected_home: str,
    previous: Optional[str] = None,
    cleared: Optional[Mapping[str, str]] = None,
    resolved: Optional[Mapping[str, Path]] = None,
) -> None:
    """Raise :class:`RuntimeError` unless every ADMZ path is throwaway."""
    resolved = resolve_all() if resolved is None else resolved
    bad = violations(resolved, expected_home)
    if bad:
        raise RuntimeError(format_refusal(bad, expected_home, previous, cleared))
