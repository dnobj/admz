"""admz.paths — centralized data-dir resolution (ADR-0042).

The contract: every resolver is CALL-time (env set after import is honored),
and precedence is  specific override > ADMZ_HOME-derived > ~/.admz default.
"""

from __future__ import annotations

from pathlib import Path

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
