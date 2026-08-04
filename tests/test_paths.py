"""admz.paths — centralized data-dir resolution (ADR-0042).

The contract: every resolver is CALL-time (env set after import is honored),
and precedence is  specific override > ADMZ_HOME-derived > ~/.admz default.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

from admz import paths


class TestAdmzHome:
    def test_default_is_profile_dotadmz(self, monkeypatch):
        monkeypatch.delenv("ADMZ_HOME", raising=False)
        assert paths.admz_home() == Path.home() / ".admz"

    def test_env_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ADMZ_HOME", str(tmp_path / "data"))
        assert paths.admz_home() == tmp_path / "data"

    def test_empty_env_falls_back_to_default(self, monkeypatch):
        # A machine env var cleared to "" must not yield Path(".")
        monkeypatch.setenv("ADMZ_HOME", "")
        assert paths.admz_home() == Path.home() / ".admz"

    def test_call_time_resolution(self, monkeypatch, tmp_path):
        """The service wrapper / tests set env vars AFTER admz.paths is
        imported — resolution must happen per call, never at import."""
        monkeypatch.delenv("ADMZ_HOME", raising=False)
        before = paths.admz_home()
        monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
        assert paths.admz_home() == tmp_path != before


class TestDerivedPaths:
    def test_derived_from_admz_home(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
        for name in ("ADMZ_DB_PATH", "ADMZ_KEY_PATH", "ADMZ_CONFIG_REPO_PATH",
                     "ADMZ_REPO_PATH_ROOT", "ADMZ_SURVEY_OUT", "ADMZ_SURVEY_WORK"):
            monkeypatch.delenv(name, raising=False)
        assert paths.db_path() == tmp_path / "admz.db"
        assert paths.key_path() == tmp_path / "admz.key"
        assert paths.config_repo_dir() == tmp_path / "config-repo"
        assert paths.repos_root() == tmp_path / "repos"
        assert paths.schedules_path() == tmp_path / "schedules.json"
        assert paths.firmware_dir() == tmp_path / "firmware"
        assert paths.survey_out_dir() == tmp_path / "survey-out"
        assert paths.survey_work_dir() == tmp_path / "survey-work"
        assert paths.dev_api_key_path() == tmp_path / "dev-api-key.txt"

    def test_specific_overrides_beat_admz_home(self, monkeypatch, tmp_path):
        """~100 existing tests isolate via ADMZ_DB_PATH — it must stay
        authoritative even when a machine-wide ADMZ_HOME is set."""
        monkeypatch.setenv("ADMZ_HOME", str(tmp_path / "home"))
        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "elsewhere.db"))
        monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "elsewhere.key"))
        monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "cr"))
        monkeypatch.setenv("ADMZ_REPO_PATH_ROOT", str(tmp_path / "rr"))
        assert paths.db_path() == tmp_path / "elsewhere.db"
        assert paths.key_path() == tmp_path / "elsewhere.key"
        assert paths.config_repo_dir() == tmp_path / "cr"
        assert paths.repos_root() == tmp_path / "rr"


class TestCallersResolveViaPaths:
    """The consumers that used to bake ~/.admz in at import time."""

    def test_upload_root_honors_env_after_import(self, monkeypatch, tmp_path):
        from admz.executor import vapix
        monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
        monkeypatch.delenv("ADMZ_DB_PATH", raising=False)
        assert vapix._upload_root() == tmp_path / "firmware"
        # the allow-list gate follows the resolved root
        fw = tmp_path / "firmware"
        fw.mkdir(parents=True)
        inside = fw / "fw.bin"
        inside.write_bytes(b"x")
        assert vapix._upload_path_allowed(str(inside)) is True
        outside = tmp_path / "admz.key"
        outside.write_bytes(b"x")
        assert vapix._upload_path_allowed(str(outside)) is False

    def test_firmware_default_dir_honors_env_after_import(self, monkeypatch, tmp_path):
        from admz.firmware import downloader
        monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
        assert downloader._default_firmware_dir() == str(tmp_path / "firmware")

    def test_registry_uses_admz_home(self, monkeypatch, tmp_path):
        from admz.backends.sqlite_backend import SQLiteDeviceRegistry
        monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
        monkeypatch.delenv("ADMZ_DB_PATH", raising=False)
        monkeypatch.delenv("ADMZ_KEY_PATH", raising=False)
        reg = SQLiteDeviceRegistry()
        assert reg._db_path == tmp_path / "admz.db"
        assert reg._key_path == tmp_path / "admz.key"

    def test_registry_explicit_args_still_win(self, monkeypatch, tmp_path):
        from admz.backends.sqlite_backend import SQLiteDeviceRegistry
        monkeypatch.setenv("ADMZ_HOME", str(tmp_path / "ignored"))
        db = tmp_path / "explicit.db"
        reg = SQLiteDeviceRegistry(db_path=str(db), key_path=str(tmp_path / "k.key"))
        assert reg._db_path == db


class TestEnsureAdmzHome:
    """#254 — one authoritative creator for the ADMZ data directory.

    Twenty places used to create it: twelve with an ad-hoc ``mkdir``, and
    eight not at all. The eight went straight to ``sqlite3.connect`` at
    import, so on a machine with no ADMZ_HOME the first one imported killed
    the process. These are the unit tests for the replacement; the
    fresh-install proof is ``TestFreshInstall`` below.

    The two ``sys.platform``-monkeypatched tests carry the weight: they
    exercise BOTH branches on BOTH CI legs, so the POSIX branch is covered
    on windows-latest and the Windows branch on ubuntu-latest. Neither leg
    can reach the other's real behaviour otherwise.
    """

    @staticmethod
    def _spy(monkeypatch):
        calls = []
        monkeypatch.setattr(
            os, "chmod", lambda p, m, *a, **k: calls.append((str(p), m))
        )
        return calls

    def test_creates_a_missing_admz_home(self, monkeypatch, tmp_path):
        home = tmp_path / "brand-new"
        monkeypatch.setenv("ADMZ_HOME", str(home))
        assert not home.exists()
        assert paths.ensure_admz_home() == home
        assert home.is_dir()

    def test_is_idempotent(self, monkeypatch, tmp_path):
        home = tmp_path / "twice"
        monkeypatch.setenv("ADMZ_HOME", str(home))
        paths.ensure_admz_home()
        paths.ensure_admz_home()
        assert home.is_dir()

    def test_creates_nested_parents(self, monkeypatch, tmp_path):
        home = tmp_path / "a" / "b" / "c"
        monkeypatch.setenv("ADMZ_HOME", str(home))
        paths.ensure_admz_home()
        assert home.is_dir()

    def test_ensure_parent_dir_follows_a_specific_override(
        self, monkeypatch, tmp_path
    ):
        """The reason ensure_parent_dir exists at all.

        ADMZ_DB_PATH takes precedence over ADMZ_HOME (ADR-0042), so a
        redirected DB does not live under ADMZ_HOME. Creating ADMZ_HOME
        instead of the real parent would leave the store connecting into a
        directory that still does not exist.
        """
        monkeypatch.setenv("ADMZ_HOME", str(tmp_path / "home"))
        elsewhere = tmp_path / "elsewhere" / "admz.db"
        monkeypatch.setenv("ADMZ_DB_PATH", str(elsewhere))
        assert not elsewhere.parent.exists()
        assert paths.ensure_parent_dir(paths.db_path()) == elsewhere.parent
        assert elsewhere.parent.is_dir()

    # -- the POSIX mode, and the deliberate Windows no-op (#250) ------------

    @pytest.mark.skipif(
        sys.platform == "win32", reason="POSIX mode bits; no-op on Windows"
    )
    def test_admz_home_is_0700_on_posix(self, monkeypatch, tmp_path):
        home = tmp_path / "moded"
        monkeypatch.setenv("ADMZ_HOME", str(home))
        paths.ensure_admz_home()
        assert oct(os.stat(home).st_mode & 0o777) == oct(0o700)

    def test_posix_branch_chmods_0700(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths.sys, "platform", "linux")
        calls = self._spy(monkeypatch)
        paths._restrict_dir(tmp_path)
        assert calls == [(str(tmp_path), 0o700)]

    def test_win32_branch_does_not_chmod(self, tmp_path, monkeypatch):
        """os.chmod on Windows is a measured no-op for access control, so it
        is deliberately not called. See ADR-0042 / #250."""
        monkeypatch.setattr(paths.sys, "platform", "win32")
        calls = self._spy(monkeypatch)
        paths._restrict_dir(tmp_path)
        assert calls == []

    def test_chmod_failure_is_logged_not_swallowed(
        self, tmp_path, monkeypatch, caplog
    ):
        monkeypatch.setattr(paths.sys, "platform", "linux")

        def boom(*a, **k):
            raise OSError(13, "denied")

        monkeypatch.setattr(os, "chmod", boom)
        with caplog.at_level(logging.ERROR, logger=paths.__name__):
            paths._restrict_dir(tmp_path)  # must not raise
        assert "ADMZ data directory" in caplog.text
        assert str(tmp_path) in caplog.text
