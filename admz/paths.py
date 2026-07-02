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

import os
from pathlib import Path


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
