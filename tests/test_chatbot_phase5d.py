"""End-to-end tests for Phase 5D: budget gating + usage + audit + cost.

Exercises the /chat/stream route with the stream_turn function
mocked, asserting that the route layer:
  - blocks turns when the principal is over budget
  - records token usage after a successful turn
  - emits an audit-log entry per turn (success and failure)
  - augments the 'done' SSE event with cost_usd + model
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Common fixture: TestClient with the chatbot singletons isolated to tmp_path.
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("ADMZ_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ADMZ_GEMINI_DEFAULT_MODEL", raising=False)

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


def _seed_api_key():
    from admz.chatbot.config import set_api_key
    set_api_key("AIza-test")


def _fake_stream_with_usage(input_tokens=100, output_tokens=50):
    """Build a fake stream_turn that yields some text + a done event."""
    from admz.chatbot.events import event_done, event_text

    async def fake_stream(**kwargs):
        yield event_text("hello ")
        yield event_text("world")
        yield event_done(
            interaction_id="int-1",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    return fake_stream


# ---------------------------------------------------------------------------
# Budget gate
# ---------------------------------------------------------------------------


class TestBudgetGate:
    def test_unlimited_budget_lets_turn_through(self, client):
        _seed_api_key()
        with patch(
            "admz.api.routes.chat.stream_turn",
            side_effect=_fake_stream_with_usage(),
        ):
            r = client.post(
                "/chat/stream",
                data={"message": "hi", "model": "gemini-2.5-pro"},
            )
        assert r.status_code == 200
        assert "event: text" in r.text
        assert "event: done" in r.text

    def test_over_budget_blocks_with_error_event(self, client):
        _seed_api_key()
        # Set a budget of 100 tokens.
        from admz.chatbot.usage import set_daily_budget, token_usage
        set_daily_budget(100)
        # Pre-seed today's usage *over* the budget.
        token_usage.record_turn(
            principal="anonymous",
            model="gemini-2.5-pro",
            input_tokens=200,
            output_tokens=0,
        )

        # The turn should be rejected before the SDK is called.
        called = {"count": 0}

        async def fake_stream(**kwargs):
            called["count"] += 1
            if False:
                yield  # pragma: no cover

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake_stream):
            r = client.post(
                "/chat/stream",
                data={"message": "hi", "model": "gemini-2.5-pro"},
            )

        assert r.status_code == 200
        assert "event: error" in r.text
        assert "budget" in r.text.lower()
        # Critically: stream_turn must not have been invoked.
        assert called["count"] == 0


# ---------------------------------------------------------------------------
# Usage recording
# ---------------------------------------------------------------------------


class TestUsageRecording:
    def test_successful_turn_records_tokens(self, client):
        _seed_api_key()
        with patch(
            "admz.api.routes.chat.stream_turn",
            side_effect=_fake_stream_with_usage(input_tokens=120, output_tokens=80),
        ):
            client.post(
                "/chat/stream",
                data={"message": "hi", "model": "gemini-2.5-pro"},
            )

        from admz.chatbot.usage import token_usage
        summary = token_usage.today_summary("anonymous")
        assert summary.input_tokens == 120
        assert summary.output_tokens == 80
        assert summary.turn_count == 1
        assert summary.cost_usd > 0  # Pro pricing is non-zero

    def test_zero_token_turn_does_not_record(self, client):
        """If the SDK reports no tokens (e.g. error mid-stream),
        skip the record to avoid polluting the daily total with
        empty rows."""
        _seed_api_key()

        from admz.chatbot.events import event_done, event_text

        async def fake_stream(**kwargs):
            yield event_text("partial")
            # Done event has no usage info.
            yield event_done()

        with patch("admz.api.routes.chat.stream_turn", side_effect=fake_stream):
            client.post(
                "/chat/stream",
                data={"message": "hi", "model": "gemini-2.5-pro"},
            )

        from admz.chatbot.usage import token_usage
        summary = token_usage.today_summary("anonymous")
        assert summary.turn_count == 0


# ---------------------------------------------------------------------------
# Audit log emission
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_successful_turn_emits_audit_entry(self, client):
        _seed_api_key()
        with patch(
            "admz.api.routes.chat.stream_turn",
            side_effect=_fake_stream_with_usage(),
        ):
            client.post(
                "/chat/stream",
                data={"message": "hi", "model": "gemini-2.5-pro"},
            )

        from admz.audit import AuditLog
        import os
        log = AuditLog(os.environ["ADMZ_DB_PATH"])
        entries = log.list_recent(limit=10)
        chat_turns = [e for e in entries if e.action == "chat_turn"]
        assert len(chat_turns) == 1
        entry = chat_turns[0]
        assert entry.requester == "anonymous"
        assert entry.success is True
        assert entry.details.get("via_chatbot") is True
        assert entry.details.get("model") == "gemini-2.5-pro"
        assert entry.details.get("input_tokens") == 100
        assert entry.details.get("output_tokens") == 50

    def test_budget_rejection_emits_audit_entry(self, client):
        _seed_api_key()
        from admz.chatbot.usage import set_daily_budget, token_usage
        set_daily_budget(50)
        token_usage.record_turn(
            principal="anonymous",
            model="gemini-2.5-pro",
            input_tokens=100,
            output_tokens=0,
        )

        client.post(
            "/chat/stream",
            data={"message": "hi", "model": "gemini-2.5-pro"},
        )

        from admz.audit import AuditLog
        import os
        log = AuditLog(os.environ["ADMZ_DB_PATH"])
        entries = log.list_recent(limit=10)
        rejections = [
            e for e in entries if e.action == "chat_budget_exceeded"
        ]
        assert len(rejections) == 1
        entry = rejections[0]
        assert entry.success is False
        assert entry.details.get("via_chatbot") is True
        assert entry.details.get("budget") == 50


# ---------------------------------------------------------------------------
# Cost in the done event
# ---------------------------------------------------------------------------


class TestDoneEventEnrichment:
    def test_done_event_carries_cost_and_model(self, client):
        _seed_api_key()
        with patch(
            "admz.api.routes.chat.stream_turn",
            side_effect=_fake_stream_with_usage(input_tokens=1000, output_tokens=500),
        ):
            r = client.post(
                "/chat/stream",
                data={"message": "hi", "model": "gemini-2.5-pro"},
            )

        body = r.text
        import json
        # Find the done event's data line.
        done_data = None
        in_done = False
        for line in body.splitlines():
            if line.strip() == "event: done":
                in_done = True
            elif in_done and line.startswith("data: "):
                done_data = json.loads(line[len("data: "):])
                break
        assert done_data is not None
        assert done_data["model"] == "gemini-2.5-pro"
        # 1000 in + 500 out on 2.5-pro:
        # 1000 * 1.25/1M + 500 * 10/1M = 0.00125 + 0.005 = 0.00625
        assert done_data["cost_usd"] == pytest.approx(0.00625, rel=1e-3)


# ---------------------------------------------------------------------------
# Settings page surfaces budget + usage
# ---------------------------------------------------------------------------


class TestSettingsPageBudget:
    def test_set_daily_budget_via_form(self, client):
        r = client.post(
            "/settings/chat",
            data={"action": "set_daily_token_budget", "daily_token_budget": "25000"},
        )
        assert r.status_code == 200
        from admz.chatbot.usage import get_daily_budget
        assert get_daily_budget() == 25000

    def test_set_budget_to_zero_disables(self, client):
        from admz.chatbot.usage import set_daily_budget
        set_daily_budget(10000)
        r = client.post(
            "/settings/chat",
            data={"action": "set_daily_token_budget", "daily_token_budget": "0"},
        )
        assert r.status_code == 200
        from admz.chatbot.usage import get_daily_budget
        assert get_daily_budget() == 0

    def test_set_invalid_budget_shows_error(self, client):
        r = client.post(
            "/settings/chat",
            data={"action": "set_daily_token_budget", "daily_token_budget": "nope"},
        )
        assert r.status_code == 200
        assert "Invalid budget" in r.text or "invalid" in r.text.lower()

    def test_set_negative_budget_rejected(self, client):
        r = client.post(
            "/settings/chat",
            data={"action": "set_daily_token_budget", "daily_token_budget": "-5"},
        )
        assert r.status_code == 200
        assert "Invalid budget" in r.text or ">= 0" in r.text


# ---------------------------------------------------------------------------
# Protected keys still include chat_daily_token_budget
# ---------------------------------------------------------------------------


class TestProtected:
    def test_budget_key_is_protected(self):
        from admz.api.confirm_store import PROTECTED_SETTING_KEYS
        assert "chat_daily_token_budget" in PROTECTED_SETTING_KEYS
