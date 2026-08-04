"""Centralized filesystem path resolution (ADR-0042).

All ADMZ state lives under ONE base directory — ``ADMZ_HOME`` — instead of
ad-hoc ``~/.admz`` expressions scattered across the codebase:

* default: ``~/.admz`` (dev installs unchanged),
* deployment: set ``ADMZ_HOME`` (e.g. ``C:\\ProgramData\\admz``) so ADMZ can run
  as a Windows service (LocalSystem has no usable profile) and server state
  isn't coupled to whichever admin first launched it.

Every resolver here is **call-time** — nothing may read the environment at
import time (an env var set between import and use, as tests and service
wrappers do, must be honored). Precedence per path:

    specific override (ADMZ_DB_PATH, ...)  >  ADMZ_HOME-derived  >  ~/.admz

The specific overrides predate ADMZ_HOME and stay authoritative: ~100 tests
isolate via ``monkeypatch.setenv("ADMZ_DB_PATH", tmp)`` and keep working
unchanged even when a machine-wide ADMZ_HOME is set.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def admz_home() -> Path:
    """The ADMZ data directory (``ADMZ_HOME`` env, default ``~/.admz``)."""
    return Path(os.getenv("ADMZ_HOME") or (Path.home() / ".admz"))


def db_path() -> Path:
    """SQLite database (``ADMZ_DB_PATH`` else ``ADMZ_HOME/admz.db``)."""
    return Path(os.getenv("ADMZ_DB_PATH") or (admz_home() / "admz.db"))


def key_path() -> Path:
    """Fernet encryption key (``ADMZ_KEY_PATH`` else ``ADMZ_HOME/admz.key``)."""
    return Path(os.getenv("ADMZ_KEY_PATH") or (admz_home() / "admz.key"))


def config_repo_dir() -> Path:
    """Default Org's git config repo (``ADMZ_CONFIG_REPO_PATH`` else
    ``ADMZ_HOME/config-repo``)."""
    return Path(os.getenv("ADMZ_CONFIG_REPO_PATH") or (admz_home() / "config-repo"))


def repos_root() -> Path:
    """Root under which non-default Org repos auto-create
    (``ADMZ_REPO_PATH_ROOT`` else ``ADMZ_HOME/repos``)."""
    return Path(os.getenv("ADMZ_REPO_PATH_ROOT") or (admz_home() / "repos"))


def schedules_path() -> Path:
    """Legacy ``schedules.json`` (read once by the ADR-0037 migration)."""
    return admz_home() / "schedules.json"


def firmware_dir() -> Path:
    """Firmware cache — also the executor's upload allow-list root."""
    return admz_home() / "firmware"


def survey_out_dir() -> Path:
    """Survey bundle output (``ADMZ_SURVEY_OUT`` else ``ADMZ_HOME/survey-out``)."""
    return Path(os.getenv("ADMZ_SURVEY_OUT") or (admz_home() / "survey-out"))


def survey_work_dir() -> Path:
    """Survey working dir (``ADMZ_SURVEY_WORK`` else ``ADMZ_HOME/survey-work``)."""
    return Path(os.getenv("ADMZ_SURVEY_WORK") or (admz_home() / "survey-work"))


def dev_api_key_path() -> Path:
    """The dev agent's Bearer key file (plaintext lives ONLY here; never
    logged, echoed, or committed)."""
    return admz_home() / "dev-api-key.txt"


# ---------------------------------------------------------------------------
# Directory creation (#254) — THE ONLY NON-PURE CODE IN THIS MODULE.
#
# Everything above is a pure resolver: call-time, side-effect-free, safe to
# call from anywhere. The two ``ensure_*`` functions below deliberately break
# that, and it is worth saying why they live here anyway.
#
# Before this, twenty places created the ADMZ data directory — twelve with an
# ad-hoc ``mkdir(parents=True, exist_ok=True)``, and eight not at all. The
# eight were the bug: they went straight to ``sqlite3.connect`` at import, so
# on a machine where ADMZ_HOME did not yet exist the first one imported killed
# the process with ``unable to open database file``. Measured on a fresh home:
# ``python -m admz mcp`` (the README's documented MCP quickstart) exits 1, as
# does ``admz api`` and ``admz maintenance migrate`` — while ``admz api-key
# list`` and ``admz settings list`` work *and* create the directory, because
# they happen to route through one of the twelve. That inconsistency, not the
# crash, is the real defect: nobody could tell which behaviour was intended.
#
# A *single* creation point is not achievable, and that is structural rather
# than a lack of effort. Nothing runs before the imports except
# ``admz/__init__.py``, and putting a mkdir there would give ``import admz`` a
# filesystem side effect firing in every test, every ``--help``, and every
# tooling import. So this is one authoritative *implementation* called from
# many places — the creation policy has an owner even though the call sites do
# not. Making the stores lazy so that nothing touches the filesystem at import
# is the real fix, and it is #258.
#
# This is where it lives because ADR-0042 names ``paths.py`` as the owner of
# all data paths, so it is where the next person looks. A separate
# ``admz/bootstrap.py`` would preserve this module's purity and buy a module
# nobody finds.
# ---------------------------------------------------------------------------


def _restrict_dir(dir_path: Path) -> None:
    """Tighten an ADMZ data directory's permissions — **POSIX only** (#250).

    On POSIX, ``chmod 0o700``. On Windows this deliberately does nothing, and
    the absence is the decision (ADR-0042). ``os.chmod`` there is a complete
    no-op for access control — it never touches the DACL, and because ``0o700``
    carries the owner-write bit it clears ``FILE_ATTRIBUTE_READONLY`` rather
    than setting it — so calling it would only imply a protection that does not
    exist.

    Setting a real DACL here was investigated in #250 and rejected: a
    file-shaped DACL applied to a directory collapses the ACL of everything
    inside it (measured: ``admz.db`` from 4 ACEs to 0, which denies everyone
    including SYSTEM), and the code cannot know the operator account to grant,
    since a non-elevated administrator's UAC-filtered token does not even carry
    ``BUILTIN\\Administrators``. ``setup-admz-service.ps1`` owns that.

    Moved here from ``admz/backends/sqlite_backend.py`` in #254: a path-level
    policy does not belong in one storage backend, and it now applies to every
    creator rather than to whichever one happened to run first.

    Failure is logged, never swallowed and never fatal.
    """
    if sys.platform == "win32":
        return
    try:
        os.chmod(dir_path, 0o700)
    except OSError:
        logger.error(
            "Could not chmod 0o700 the ADMZ data directory %s — it may be "
            "readable by other users.",
            dir_path,
            exc_info=True,
        )


def ensure_admz_home() -> Path:
    """Create ``ADMZ_HOME`` if absent, restrict it on POSIX, and return it.

    Idempotent and safe to call from anywhere, as often as you like.
    """
    home = admz_home()
    home.mkdir(parents=True, exist_ok=True)
    _restrict_dir(home)
    return home


def ensure_parent_dir(file_path: Path | str) -> Path:
    """Create the directory *file_path* will live in, and return it.

    Callers that open a database want ``ensure_parent_dir(self._db_path)``
    rather than :func:`ensure_admz_home`, and the difference is load-bearing:
    the specific overrides (``ADMZ_DB_PATH`` and friends) take precedence over
    ``ADMZ_HOME`` (ADR-0042), so a redirected DB does **not** live under
    ADMZ_HOME. Creating ADMZ_HOME instead of the actual parent would leave such
    a store connecting into a directory that still does not exist — the very
    failure this is fixing, moved rather than removed.

    The directory is restricted the same way regardless of where the override
    points. That matches what ``sqlite_backend`` already did unconditionally
    before this change; it is not a new behaviour class, just a consistent one.
    """
    parent = Path(file_path).parent
    parent.mkdir(parents=True, exist_ok=True)
    _restrict_dir(parent)
    return parent
