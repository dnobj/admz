"""Tests for admz.chatbot.config — fleet-setting bootstrap and key access."""

import pytest

from admz import chatbot
from admz.chatbot import config as cfg_mod
from admz.fleet_settings import fleet_settings


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch, tmp_path):
    """Each test gets a fresh DB + bootstrap flag.

    Reassigns the fleet_settings + chat_sessions singletons against
    a tmp-path DB, and **restores them on teardown** so downstream
    tests in other files don't inherit a pointer to a deleted tmp
    directory.
    """
    db_path = tmp_path / "admz.db"
    monkeypatch.setenv("ADMZ_DB_PATH", str(db_path))

    from admz import fleet_settings as fs_module
    from admz.chatbot import sessions as sess_module

    _orig_fs = fs_module.fleet_settings
    _orig_sessions = sess_module.chat_sessions
    _orig_bootstrapped = cfg_mod._bootstrapped

    fs_module.fleet_settings = fs_module.FleetSettings(str(db_path))
    sess_module.chat_sessions = sess_module.ChatSessionStore(str(db_path))
    cfg_mod._bootstrapped = False

    try:
        yield
    finally:
        fs_module.fleet_settings = _orig_fs
        sess_module.chat_sessions = _orig_sessions
        cfg_mod._bootstrapped = _orig_bootstrapped


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_model_is_gemini_3_1_pro(self):
        assert cfg_mod.DEFAULT_MODEL == "gemini-3.1-pro"

    def test_default_model_is_in_selectable(self):
        assert cfg_mod.DEFAULT_MODEL in cfg_mod.SELECTABLE_MODELS

    def test_selectable_has_three_tiers(self):
        # Pro, Flash, Flash-Lite — ADR-0025.
        assert len(cfg_mod.SELECTABLE_MODELS) == 3
        assert "gemini-3.1-flash-lite" in cfg_mod.SELECTABLE_MODELS

    def test_unconfigured_when_no_key(self, monkeypatch):
        monkeypatch.delenv("ADMZ_GEMINI_API_KEY", raising=False)
        config = cfg_mod.get_chatbot_config()
        assert config.configured is False
        assert config.api_key is None


# ---------------------------------------------------------------------------
# Env-var bootstrap
# ---------------------------------------------------------------------------


class TestEnvBootstrap:
    def test_seeds_api_key_from_env_when_empty(self, monkeypatch):
        monkeypatch.setenv("ADMZ_GEMINI_API_KEY", "AIza-test-key")
        config = cfg_mod.get_chatbot_config()
        assert config.api_key == "AIza-test-key"
        assert config.configured is True
        # Persisted into fleet settings
        from admz.fleet_settings import fleet_settings as fs
        assert fs.get("gemini_api_key") == "AIza-test-key"

    def test_env_does_not_overwrite_persisted_key(self, monkeypatch):
        from admz.fleet_settings import fleet_settings as fs
        fs.set("gemini_api_key", "already-here")

        monkeypatch.setenv("ADMZ_GEMINI_API_KEY", "would-overwrite")
        config = cfg_mod.get_chatbot_config()
        assert config.api_key == "already-here"

    def test_bootstrap_runs_only_once(self, monkeypatch):
        monkeypatch.setenv("ADMZ_GEMINI_API_KEY", "first-value")
        cfg_mod.get_chatbot_config()

        # Change env, clear the persisted key, re-read.
        # Bootstrap should not re-seed.
        monkeypatch.setenv("ADMZ_GEMINI_API_KEY", "second-value")
        from admz.fleet_settings import fleet_settings as fs
        fs.delete("gemini_api_key")

        config = cfg_mod.get_chatbot_config()
        assert config.api_key is None  # bootstrap didn't re-fire

    def test_seeds_default_model_from_env(self, monkeypatch):
        monkeypatch.setenv("ADMZ_GEMINI_DEFAULT_MODEL", "gemini-3.1-flash-lite")
        config = cfg_mod.get_chatbot_config()
        assert config.default_model == "gemini-3.1-flash-lite"

    def test_invalid_env_model_falls_back(self, monkeypatch):
        monkeypatch.setenv("ADMZ_GEMINI_DEFAULT_MODEL", "gemini-99-superduper")
        config = cfg_mod.get_chatbot_config()
        assert config.default_model == cfg_mod.DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Fleet-setting overrides take precedence
# ---------------------------------------------------------------------------


class TestPersistedOverrides:
    def test_fleet_setting_overrides_default_model(self):
        from admz.fleet_settings import fleet_settings as fs
        fs.set("gemini_default_model", "gemini-3.1-flash")
        config = cfg_mod.get_chatbot_config()
        assert config.default_model == "gemini-3.1-flash"

    def test_invalid_persisted_default_falls_back(self):
        from admz.fleet_settings import fleet_settings as fs
        fs.set("gemini_default_model", "gemini-totally-fake")
        config = cfg_mod.get_chatbot_config()
        assert config.default_model == cfg_mod.DEFAULT_MODEL

    def test_set_api_key_persists(self):
        cfg_mod.set_api_key("AIza-fresh")
        assert cfg_mod.get_chatbot_config().api_key == "AIza-fresh"

    def test_set_api_key_strips_whitespace(self):
        cfg_mod.set_api_key("  AIza-padded   ")
        assert cfg_mod.get_chatbot_config().api_key == "AIza-padded"

    def test_clear_api_key_removes(self):
        cfg_mod.set_api_key("AIza-x")
        cfg_mod.clear_api_key()
        assert cfg_mod.get_chatbot_config().api_key is None

    def test_set_default_model_rejects_unknown(self):
        with pytest.raises(ValueError):
            cfg_mod.set_default_model("gemini-not-a-real-model")


# ---------------------------------------------------------------------------
# Masking
# ---------------------------------------------------------------------------


class TestMasking:
    def test_mask_empty(self):
        assert cfg_mod.mask_api_key(None) == "(not configured)"
        assert cfg_mod.mask_api_key("") == "(not configured)"

    def test_mask_shows_length_and_tail(self):
        masked = cfg_mod.mask_api_key("AIzaSyABCDEF12345678")
        assert "configured" in masked
        assert "5678" in masked  # last 4 chars
        assert "AIza" not in masked  # head not exposed


# ---------------------------------------------------------------------------
# is_chatbot_configured convenience
# ---------------------------------------------------------------------------


class TestIsConfigured:
    def test_false_when_no_key(self, monkeypatch):
        monkeypatch.delenv("ADMZ_GEMINI_API_KEY", raising=False)
        assert chatbot.is_chatbot_configured() is False

    def test_true_when_key_set(self):
        cfg_mod.set_api_key("AIza-test")
        assert chatbot.is_chatbot_configured() is True
