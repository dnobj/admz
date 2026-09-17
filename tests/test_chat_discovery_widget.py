"""ADR-0072 §1, §2, §6 — the console side of the discovery widget.

* The chat route binds a turn's scan to that turn's conversation, and only the
  console's turns tell the model a table is on screen.
* ``chat.js`` renders the widget from the structured result only, writes device
  text as text, keeps Add off until the turn's response has closed, and
  approves through the existing confirm route. There is no JS test runner in
  this repo, so — like ``test_chat_confirm_json.py`` — these pin the source.
"""

from __future__ import annotations

import pathlib
import re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

CHAT_JS = pathlib.Path(__file__).resolve().parents[1] / "admz/api/static/chat.js"
PRINCIPAL = "anonymous"


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
    orig = (fs_module.fleet_settings, sess_module.chat_sessions,
            usage_module.token_usage, cfg_module._bootstrapped)
    fs_module.fleet_settings = fs_module.FleetSettings(db_path)
    sess_module.chat_sessions = sess_module.ChatSessionStore(db_path)
    usage_module.token_usage = usage_module.TokenUsageStore(db_path)
    cfg_module._bootstrapped = False

    from admz.api.main import app

    try:
        with TestClient(app, follow_redirects=False) as c:
            from admz.chatbot.config import set_api_key
            set_api_key("AIza-test")
            yield c
    finally:
        (fs_module.fleet_settings, sess_module.chat_sessions,
         usage_module.token_usage, cfg_module._bootstrapped) = orig


def _stream_with_scan(scan_url, captured, tool="discover_network_devices"):
    from admz.chatbot.events import ChatEvent, ChatEventType, event_done, event_text

    async def stream(**kwargs):
        captured.update(kwargs)
        yield ChatEvent(ChatEventType.TOOL_RESULT, {
            "name": tool, "status": "ok", "call_id": "1",
            "result": {"success": True, "count": 1, "scan_url": scan_url},
        })
        yield event_text("Found 1 Axis device; tick it and press Add.")
        yield event_done(interaction_id="int-1", input_tokens=5, output_tokens=5)

    return stream


def _new_scan(principal=PRINCIPAL):
    from admz.discovery.scan_store import discovery_scans
    return discovery_scans.save_scan(principal=principal, devices=[])


class TestTheTurnBindsItsScan:
    def test_a_console_turn_binds_the_scan_to_its_conversation(self, client):
        from admz.chatbot import sessions as sess_module
        from admz.discovery.scan_store import discovery_scans

        scan = _new_scan()
        captured = {}
        with patch("admz.api.routes.chat.stream_turn",
                   _stream_with_scan(f"/api/discovery/scans/{scan.scan_id}", captured)):
            r = client.post("/chat/stream", data={"message": "discover devices"})
        assert r.status_code == 200
        assert "event: tool_result" in r.text

        conv = sess_module.chat_sessions.get_active_conversation(PRINCIPAL)
        assert conv
        assert discovery_scans.get_scan(scan.scan_id).conversation_id == conv

    def test_a_url_from_another_tool_binds_nothing(self, client):
        from admz.discovery.scan_store import discovery_scans

        scan = _new_scan()
        with patch("admz.api.routes.chat.stream_turn", _stream_with_scan(
                f"/api/discovery/scans/{scan.scan_id}", {}, tool="execute_operation")):
            client.post("/chat/stream", data={"message": "hello"})
        assert discovery_scans.get_scan(scan.scan_id).conversation_id == ""

    def test_another_principals_scan_is_not_bound(self, client):
        from admz.discovery.scan_store import discovery_scans

        scan = _new_scan(principal="bob")
        with patch("admz.api.routes.chat.stream_turn", _stream_with_scan(
                f"/api/discovery/scans/{scan.scan_id}", {})):
            client.post("/chat/stream", data={"message": "discover devices"})
        assert discovery_scans.get_scan(scan.scan_id).conversation_id == ""

    def test_only_the_console_is_told_about_the_table(self, client):
        marker = "# Discovery results in the console"
        console, api = {}, {}
        with patch("admz.api.routes.chat.stream_turn",
                   _stream_with_scan("/nothing", console)):
            client.post("/chat/stream", data={"message": "discover devices"})
        with patch("admz.api.routes.chat.stream_turn",
                   _stream_with_scan("/nothing", api)):
            client.post("/api/chat", json={"message": "discover devices"})
        assert marker in console["system_prompt"]
        assert marker not in api["system_prompt"]

    def test_the_scan_url_pattern_matches_the_browsers(self):
        from admz.api.routes.chat import _SCAN_URL_RE

        js = CHAT_JS.read_text(encoding="utf-8")
        assert "/^\\/api\\/discovery\\/scans\\/([A-Za-z0-9_-]{20,})$/" in js
        assert _SCAN_URL_RE.pattern == r"^/api/discovery/scans/([A-Za-z0-9_-]{20,})$"
        assert _SCAN_URL_RE.match("/api/discovery/scans/short") is None


def _widget_source() -> str:
    js = CHAT_JS.read_text(encoding="utf-8")
    start = js.index("// ── Discovery widget (ADR-0072)")
    end = js.index("// Conversation history drawer", start)
    return js[start:end]


class TestTheWidgetSource:
    def test_it_renders_only_from_the_discovery_tool_result(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        switch = js[js.index('case "tool_result":'):js.index('case "done":')]
        assert "maybeRenderDiscoveryWidget(assistantBubble, parsed.data)" in switch
        src = _widget_source()
        assert 'data.name !== "discover_network_devices"' in src
        assert "SCAN_URL_RE.exec(String(result.scan_url" in src
        assert "seenScans" in src

    def test_add_waits_for_the_response_to_close(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        # Both the typed turn and the continuation finish their widgets when
        # their fetch settles — after the server has bound the scan.
        assert js.count("finishTurnWidgets(assistantBubble);") == 2
        src = _widget_source()
        assert "!state.turnDone" in src
        assert re.search(r"addBtn\.disabled = [^;]*!state\.turnDone", src)

    def test_approval_goes_through_the_existing_confirm_route(self):
        src = _widget_source()
        assert '"/api/discovery/scans/" + encodeURIComponent(scanId) + "/add"' in src
        assert 'fetch("/api/chat/confirm/" + encodeURIComponent(token)' in src
        assert 'params.set("confirm_password"' in src
        # One click, then the continuation the console note is owed.
        assert "maybeResumeConversation()" in src

    def test_a_retry_reuses_the_token(self):
        """The password lockout counts per token; a fresh session per attempt
        would reset it."""
        src = _widget_source()
        assert "if (state.token && state.tokenKey === key) return Promise.resolve(state.token);" in src

    def test_device_text_is_written_as_text(self):
        src = _widget_source()
        # Device-supplied fields reach the DOM through textContent only.
        for field in ("d.friendly_name", "d.hostname", "d.firmware_version",
                      "why", "outcome.message"):
            for line in src.splitlines():
                if field in line and "innerHTML" in line:
                    raise AssertionError(f"{field} written through innerHTML: {line}")
        assert "name.textContent = d.friendly_name" in src
        assert "td.textContent = v;" in src
        assert "note.textContent = why;" in src

    def test_a_widget_failure_cannot_stop_the_stream(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert ("try { maybeRenderDiscoveryWidget(assistantBubble, parsed.data); }"
                " catch (_) {}") in js

    def test_device_names_are_not_scanned_as_model_links(self):
        """A device named /confirm/<20+ chars> is not an invented approval."""
        js = CHAT_JS.read_text(encoding="utf-8")
        done = js[js.index('case "done":'):js.index('case "error":')]
        assert 'querySelectorAll(".discovery-widget")' in done
        assert "flagUnbackedLinks(blocksCopy.textContent" in done

    def test_a_gone_session_is_checked_before_saying_nothing_ran(self):
        src = _widget_source()
        assert 'fetch("/api/confirm/" + encodeURIComponent(token) + "/status")' in src
        assert 'st.status === "completed"' in src
        assert "return explainGone(state.token);" in src

    def test_a_raised_level_or_wrong_password_refreshes_the_policy(self):
        src = _widget_source()
        assert 'resp.body.confirmation_level === "url_and_password"' in src
        assert 'if (body.status === "wrong_password") fetchScan();' in src

    def test_nothing_is_preselected(self):
        src = _widget_source()
        assert "selected: new Set()" in src
        assert 'state = {\n      scan: null, filter: "axis"' in src

    def test_the_widget_is_styled_with_the_theme_tokens(self):
        css = (CHAT_JS.parent / "css" / "admz.css").read_text(encoding="utf-8")
        block = css[css.index("/* ── Discovery widget (ADR-0072)"):
                    css.index("/* ── Pending-action widget")]
        assert "#" not in re.sub(r"/\*.*?\*/", "", block, flags=re.S), (
            "a literal colour in the widget CSS would ignore the light theme")
