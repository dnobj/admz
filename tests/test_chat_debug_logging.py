"""Tests for DEBUG-level conversation logging in the chat routes.

When ADMZ_LOG_LEVEL=DEBUG (or any DEBUG configuration on the chat
route's logger), the user message + assistant response should
appear in the logs. At INFO and above, they must not — that's the
default privacy posture.
"""

import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("ADMZ_GEMINI_API_KEY", raising=False)

    from admz import fleet_settings as fs_module
    from admz.chatbot import config as cfg_module
    from admz.chatbot import sessions as sess_module
    from admz.chatbot import usage as usage_module

    db_path = str(tmp_path / "admz.db")
    orig_fs = fs_module.fleet_settings
    orig_sess = sess_module.chat_sessions
    orig_usage = usage_module.token_usage
    orig_boot = cfg_module._bootstrapped

    fs_module.fleet_settings = fs_module.FleetSettings(db_path)
    sess_module.chat_sessions = sess_module.ChatSessionStore(db_path)
    usage_module.token_usage = usage_module.TokenUsageStore(db_path)
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
        fs_module.fleet_settings = orig_fs
        sess_module.chat_sessions = orig_sess
        usage_module.token_usage = orig_usage
        cfg_module._bootstrapped = orig_boot


def _fake_stream(answer="hello world", input_tokens=10, output_tokens=5):
    from admz.chatbot.events import event_done, event_text

    async def stream(**kwargs):
        yield event_text(answer)
        yield event_done(
            interaction_id="int-1",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    return stream


# ---------------------------------------------------------------------------
# Streaming path
# ---------------------------------------------------------------------------


class TestStreamDebugLogging:
    def test_user_message_logged_at_debug(self, client, caplog):
        from admz.chatbot.config import set_api_key
        set_api_key("AIza-x")

        with caplog.at_level(logging.DEBUG, logger="admz.api.routes.chat"):
            with patch("admz.api.routes.chat.stream_turn", side_effect=_fake_stream()):
                client.post(
                    "/chat/stream",
                    data={"message": "secret prompt 42", "model": "gemini-2.5-flash"},
                )

        debug_messages = [
            r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG
        ]
        # The opening log line has the user message.
        assert any("secret prompt 42" in m for m in debug_messages), (
            f"user message not in DEBUG logs: {debug_messages!r}"
        )

    def test_assistant_response_logged_at_debug(self, client, caplog):
        from admz.chatbot.config import set_api_key
        set_api_key("AIza-x")

        with caplog.at_level(logging.DEBUG, logger="admz.api.routes.chat"):
            with patch(
                "admz.api.routes.chat.stream_turn",
                side_effect=_fake_stream(answer="distinctive_response_token_xyz"),
            ):
                client.post(
                    "/chat/stream",
                    data={"message": "hi", "model": "gemini-2.5-flash"},
                )

        debug_messages = [
            r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG
        ]
        assert any(
            "distinctive_response_token_xyz" in m for m in debug_messages
        ), f"assistant response not in DEBUG logs: {debug_messages!r}"

    def test_no_message_content_at_info_level(self, client, caplog):
        """The whole point of the privacy posture: at INFO, the
        message bodies must not leak into logs."""
        from admz.chatbot.config import set_api_key
        set_api_key("AIza-x")

        with caplog.at_level(logging.INFO, logger="admz.api.routes.chat"):
            with patch(
                "admz.api.routes.chat.stream_turn",
                side_effect=_fake_stream(answer="private_response"),
            ):
                client.post(
                    "/chat/stream",
                    data={
                        "message": "private_user_message",
                        "model": "gemini-2.5-flash",
                    },
                )

        all_messages = [r.getMessage() for r in caplog.records]
        for m in all_messages:
            assert "private_user_message" not in m, (
                f"user message leaked at INFO: {m!r}"
            )
            assert "private_response" not in m, (
                f"assistant response leaked at INFO: {m!r}"
            )


# ---------------------------------------------------------------------------
# Non-streaming path (POST /chat fallback)
# ---------------------------------------------------------------------------


class TestNonStreamDebugLogging:
    def test_user_and_assistant_logged_at_debug(self, client, caplog):
        from admz.chatbot.client import TurnResult
        from admz.chatbot.config import set_api_key
        set_api_key("AIza-x")

        async def fake_run_turn(**kwargs):
            return TurnResult(
                text="nonstream_distinctive_answer",
                model=kwargs["model"],
                interaction_id="int-1",
                input_tokens=10,
                output_tokens=5,
            )

        with caplog.at_level(logging.DEBUG, logger="admz.api.routes.chat"):
            with patch("admz.api.routes.chat.run_turn", side_effect=fake_run_turn):
                client.post(
                    "/chat",
                    data={
                        "message": "nonstream_user_prompt",
                        "model": "gemini-2.5-flash",
                    },
                )

        debug_messages = [
            r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG
        ]
        assert any("nonstream_user_prompt" in m for m in debug_messages)
        assert any("nonstream_distinctive_answer" in m for m in debug_messages)

    def test_no_content_at_info_level_for_post(self, client, caplog):
        from admz.chatbot.client import TurnResult
        from admz.chatbot.config import set_api_key
        set_api_key("AIza-x")

        async def fake_run_turn(**kwargs):
            return TurnResult(
                text="private_answer_post",
                model=kwargs["model"],
                interaction_id=None,
            )

        with caplog.at_level(logging.INFO, logger="admz.api.routes.chat"):
            with patch("admz.api.routes.chat.run_turn", side_effect=fake_run_turn):
                client.post(
                    "/chat",
                    data={
                        "message": "private_prompt_post",
                        "model": "gemini-2.5-flash",
                    },
                )

        all_messages = [r.getMessage() for r in caplog.records]
        for m in all_messages:
            assert "private_prompt_post" not in m
            assert "private_answer_post" not in m
