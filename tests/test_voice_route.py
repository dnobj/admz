"""Tests for the realtime-voice WebSocket route (admz/api/routes/voice.py).

VoiceSession is mocked so these don't touch the Gemini Live API — they verify
the WS contract: the ready handshake, event forwarding (audio→binary frames,
everything else→JSON), the typed-input control path, and the
not-configured error.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient


class _FakeVoice:
    """Drop-in for VoiceSession; records input, yields scripted events."""

    instances = []
    events = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.sent_text = []
        self.sent_audio = []
        self.ended = False
        _FakeVoice.instances.append(self)

    @property
    def model_name(self):
        return "fake-voice-model"

    @property
    def voice_name(self):
        return "Puck"

    @property
    def tools_enabled(self):
        return True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send_text(self, text):
        self.sent_text.append(text)

    async def send_audio(self, pcm):
        self.sent_audio.append(pcm)

    async def send_audio_end(self):
        self.ended = True

    async def stream(self):
        # small yield so the from_browser task can process queued input first
        await asyncio.sleep(0.05)
        for ev in _FakeVoice.events:
            yield ev


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    import admz.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_ACTIVE_BACKEND", None)

    _FakeVoice.instances = []
    _FakeVoice.events = []
    import admz.chatbot.voice as voice_mod
    monkeypatch.setattr(voice_mod, "VoiceSession", _FakeVoice)
    monkeypatch.setattr(voice_mod, "voice_available", lambda config: True)

    from admz.api.main import app
    with TestClient(app) as c:
        yield c


def test_ready_handshake(client):
    _FakeVoice.events = [{"type": "turn_complete"}]
    with client.websocket_connect("/api/chat/voice") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["model"] == "fake-voice-model"
        assert ready["tools_enabled"] is True
        assert ready["input_sample_rate"] == 16000
        assert ws.receive_json()["type"] == "turn_complete"


def test_event_forwarding_audio_and_json(client):
    _FakeVoice.events = [
        {"type": "input_transcript", "text": "is the p8815 up?"},
        {"type": "tool_call", "name": "get_device_health", "args": {"device_id": "X"}},
        {"type": "tool_result", "name": "get_device_health", "blocked": False, "success": True},
        {"type": "output_transcript", "text": "Yes, it's online."},
        {"type": "audio", "data": b"\x01\x02\x03\x04"},
        {"type": "turn_complete"},
    ]
    with client.websocket_connect("/api/chat/voice") as ws:
        assert ws.receive_json()["type"] == "ready"
        assert ws.receive_json() == {"type": "input_transcript", "text": "is the p8815 up?"}
        assert ws.receive_json()["type"] == "tool_call"
        assert ws.receive_json()["type"] == "tool_result"
        assert ws.receive_json() == {"type": "output_transcript", "text": "Yes, it's online."}
        assert ws.receive_bytes() == b"\x01\x02\x03\x04"   # audio → binary frame
        assert ws.receive_json()["type"] == "turn_complete"


def test_typed_input_control_drives_send_text(client):
    _FakeVoice.events = [{"type": "turn_complete"}]
    with client.websocket_connect("/api/chat/voice") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "text", "text": "list my devices"})
        assert ws.receive_json()["type"] == "turn_complete"
    # the relay forwarded the typed input to the session
    assert _FakeVoice.instances[-1].sent_text == ["list my devices"]


def test_binary_audio_frame_forwarded(client):
    _FakeVoice.events = [{"type": "turn_complete"}]
    with client.websocket_connect("/api/chat/voice") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_bytes(b"\xaa\xbb\xcc")
        assert ws.receive_json()["type"] == "turn_complete"
    assert _FakeVoice.instances[-1].sent_audio == [b"\xaa\xbb\xcc"]


def test_not_configured_returns_error(client, monkeypatch):
    import admz.chatbot.voice as voice_mod
    monkeypatch.setattr(voice_mod, "voice_available", lambda config: False)
    with client.websocket_connect("/api/chat/voice") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "not configured" in msg["error"].lower()


def test_models_endpoint_lists_voice_models_and_voices(client):
    from admz.chatbot.voice import (
        VOICE_MODELS, DEFAULT_VOICE_MODEL, VOICE_NAMES, DEFAULT_VOICE_NAME,
    )

    r = client.get("/api/chat/voice/models")
    assert r.status_code == 200
    body = r.json()
    assert body["models"] == VOICE_MODELS
    assert body["default"] == DEFAULT_VOICE_MODEL
    assert "gemini-3.1-flash-live-preview" in body["models"]
    assert body["voices"] == VOICE_NAMES
    assert body["default_voice"] == DEFAULT_VOICE_NAME


def test_selected_model_and_voice_passed_to_session(client):
    _FakeVoice.events = [{"type": "turn_complete"}]
    with client.websocket_connect(
        "/api/chat/voice?model=gemini-3.1-flash-live-preview&voice=Kore"
    ) as ws:
        assert ws.receive_json()["type"] == "ready"
        assert ws.receive_json()["type"] == "turn_complete"
    kw = _FakeVoice.instances[-1].kwargs
    assert kw.get("model") == "gemini-3.1-flash-live-preview"
    assert kw.get("voice") == "Kore"
