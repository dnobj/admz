"""Tests for /chat and /settings/chat routes + the home redirect."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolate_admz_dirs(tmp_path, monkeypatch):
    """Each test gets a fresh DB + temp HOME (mirrors test_api_routes.py)."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("ADMZ_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ADMZ_GEMINI_DEFAULT_MODEL", raising=False)


@pytest.fixture
def client(isolate_admz_dirs, tmp_path):
    """Build a TestClient. Disable redirect-following so we can assert on 302s.

    We repoint the fleet_settings + chat_sessions singletons at a
    tmp-path DB and **restore them on teardown** so downstream tests
    don't read from a deleted tmp directory. Without the restore,
    test_rate_limit (which uses the global fleet_settings singleton)
    would inherit our pointer to a no-longer-existing tmp path.
    """
    from admz import fleet_settings as fs_module
    from admz.chatbot import config as cfg_module
    from admz.chatbot import sessions as sess_module

    db_path = str(tmp_path / "admz.db")

    # Save originals
    _orig_fs = fs_module.fleet_settings
    _orig_sessions = sess_module.chat_sessions
    _orig_bootstrapped = cfg_module._bootstrapped

    # Install tmp-path singletons
    fs_module.fleet_settings = fs_module.FleetSettings(db_path)
    sess_module.chat_sessions = sess_module.ChatSessionStore(db_path)
    cfg_module._bootstrapped = False

    from admz.api.main import app

    try:
        with TestClient(app, follow_redirects=False) as c:
            import subprocess
            repo_path = str(tmp_path / "config-repo")
            for key, val in [
                ("user.email", "test@test.com"),
                ("user.name", "Test"),
                ("commit.gpgsign", "false"),
            ]:
                subprocess.run(
                    ["git", "config", key, val], cwd=repo_path, check=True
                )
            yield c
    finally:
        # Restore — critical: downstream tests share these singletons.
        fs_module.fleet_settings = _orig_fs
        sess_module.chat_sessions = _orig_sessions
        cfg_module._bootstrapped = _orig_bootstrapped


# ---------------------------------------------------------------------------
# Home redirect
# ---------------------------------------------------------------------------


class TestHomeRedirect:
    def test_root_redirects_to_chat(self, client):
        r = client.get("/")
        assert r.status_code == 302
        assert r.headers["location"] == "/chat"

    def test_devices_still_accessible(self, client):
        r = client.get("/devices")
        assert r.status_code == 200
        assert b"Device List" in r.content or b"devices" in r.content.lower()


# ---------------------------------------------------------------------------
# /chat page render
# ---------------------------------------------------------------------------


class TestChatPage:
    def test_chat_page_renders_when_unconfigured(self, client):
        r = client.get("/chat")
        assert r.status_code == 200
        body = r.text
        assert "Chat" in body
        # Friendly "not configured" message must appear.
        assert "not configured" in body.lower()
        assert "/settings/chat" in body

    def test_chat_page_renders_when_configured(self, client):
        from admz.chatbot.config import set_api_key
        set_api_key("AIza-test-key")

        r = client.get("/chat")
        assert r.status_code == 200
        body = r.text
        # The chat surface was renamed to "Console" in the Axis Signal redesign.
        assert "Console" in body
        # No "not configured" warning now.
        assert "not configured" not in body.lower()
        # Model selector populated.
        assert "gemini-2.5-pro" in body
        assert "gemini-2.5-flash-lite" in body

    def test_chat_post_returns_503_when_unconfigured(self, client):
        r = client.post("/chat", data={"message": "hi"})
        assert r.status_code == 503
        assert "not configured" in r.text.lower()

    def test_chat_post_invokes_client_when_configured(self, client):
        from admz.chatbot.config import set_api_key
        set_api_key("AIza-test-key")

        async def fake_run_turn(**kwargs):
            from admz.chatbot.client import TurnResult
            assert kwargs["api_key"] == "AIza-test-key"
            assert kwargs["user_message"] == "hello chatbot"
            return TurnResult(
                text="hi from gemini",
                model=kwargs["model"],
                interaction_id="int-fresh",
                input_tokens=10,
                output_tokens=5,
            )

        with patch("admz.api.routes.chat.run_turn", side_effect=fake_run_turn):
            r = client.post(
                "/chat",
                data={"message": "hello chatbot", "model": "gemini-2.5-pro"},
            )
        assert r.status_code == 200
        assert "hi from gemini" in r.text
        assert "hello chatbot" in r.text

        # The interaction_id should be persisted for the principal.
        from admz.chatbot.sessions import chat_sessions
        # In tests we run as anonymous (no auth middleware backend).
        assert chat_sessions.get_interaction_id("anonymous") == "int-fresh"

    def test_chat_post_invalid_model_falls_back_to_default(self, client):
        from admz.chatbot.config import set_api_key
        set_api_key("AIza-test-key")

        captured = {}

        async def capture_model(**kwargs):
            from admz.chatbot.client import TurnResult
            captured["model"] = kwargs["model"]
            return TurnResult(
                text="ok", model=kwargs["model"], interaction_id=None
            )

        with patch("admz.api.routes.chat.run_turn", side_effect=capture_model):
            r = client.post(
                "/chat",
                data={"message": "x", "model": "gemini-totally-fake"},
            )
        assert r.status_code == 200
        assert captured["model"] == "gemini-2.5-flash"  # DEFAULT_MODEL

    def test_chat_clear_resets_session(self, client):
        from admz.chatbot.sessions import chat_sessions
        chat_sessions.set_interaction_id("anonymous", "int-old", "gemini-2.5-pro")

        r = client.post("/chat/clear")
        assert r.status_code == 303
        assert r.headers["location"] == "/chat"
        assert chat_sessions.get_interaction_id("anonymous") is None


# ---------------------------------------------------------------------------
# /settings/chat admin page
# ---------------------------------------------------------------------------


class TestChatSettingsPage:
    def test_settings_page_renders_unconfigured(self, client):
        r = client.get("/settings/chat")
        assert r.status_code == 200
        assert "Chat Settings" in r.text
        assert "not configured" in r.text

    def test_set_api_key_persists(self, client):
        r = client.post(
            "/settings/chat",
            data={"action": "set_api_key", "api_key": "AIza-from-form"},
        )
        assert r.status_code == 200
        from admz.chatbot.config import get_chatbot_config
        assert get_chatbot_config().api_key == "AIza-from-form"

    def test_empty_api_key_is_rejected(self, client):
        r = client.post(
            "/settings/chat",
            data={"action": "set_api_key", "api_key": "   "},
        )
        assert r.status_code == 200
        from admz.chatbot.config import get_chatbot_config
        assert get_chatbot_config().api_key is None
        assert "cannot be empty" in r.text.lower()

    def test_clear_api_key(self, client):
        from admz.chatbot.config import set_api_key
        set_api_key("AIza-x")

        r = client.post(
            "/settings/chat", data={"action": "clear_api_key"}
        )
        assert r.status_code == 200
        from admz.chatbot.config import get_chatbot_config
        assert get_chatbot_config().api_key is None

    def test_set_default_model(self, client):
        r = client.post(
            "/settings/chat",
            data={
                "action": "set_default_model",
                "default_model": "gemini-2.5-flash-lite",
            },
        )
        assert r.status_code == 200
        from admz.chatbot.config import get_chatbot_config
        assert get_chatbot_config().default_model == "gemini-2.5-flash-lite"

    def test_set_unknown_model_rejected(self, client):
        r = client.post(
            "/settings/chat",
            data={"action": "set_default_model", "default_model": "gemini-fake"},
        )
        assert r.status_code == 200
        assert "Invalid model" in r.text or "invalid" in r.text.lower()


# ---------------------------------------------------------------------------
# gemini_api_key is on PROTECTED_SETTING_KEYS — MCP can't write it
# ---------------------------------------------------------------------------


class TestProtectedKeysIncludeGeminiKey:
    def test_gemini_api_key_is_protected(self):
        from admz.api.confirm_store import PROTECTED_SETTING_KEYS
        assert "gemini_api_key" in PROTECTED_SETTING_KEYS

    def test_gemini_default_model_is_protected(self):
        from admz.api.confirm_store import PROTECTED_SETTING_KEYS
        assert "gemini_default_model" in PROTECTED_SETTING_KEYS
