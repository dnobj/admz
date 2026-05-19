"""Tests for admz.chatbot.client — SDK adapter behavior.

We patch ``admz.chatbot.client._invoke`` rather than the real
google-genai SDK so the tests don't need the dependency. The
adapter is the surface under test; the SDK isn't.
"""

import sys
from unittest.mock import MagicMock

import pytest

from admz.chatbot import client as client_mod


# ---------------------------------------------------------------------------
# Dependency-missing path
# ---------------------------------------------------------------------------


class TestDependencyMissing:
    def test_run_turn_raises_when_genai_absent(self, monkeypatch):
        # Force the lazy import to fail.
        monkeypatch.setitem(sys.modules, "google.genai", None)
        monkeypatch.setattr(
            client_mod,
            "_import_genai",
            lambda: (_ for _ in ()).throw(
                client_mod.ChatbotDependencyMissing("simulated")
            ),
        )
        with pytest.raises(client_mod.ChatbotDependencyMissing):
            import asyncio
            asyncio.run(
                client_mod.run_turn(
                    user_message="hi",
                    api_key="AIza-x",
                    model="gemini-2.5-pro",
                    system_prompt="sys",
                )
            )


# ---------------------------------------------------------------------------
# Happy path with a patched _invoke
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, text="hello", id_="int-123", usage=None):
        self.text = text
        self.id = id_
        self.usage = usage or {"input_tokens": 12, "output_tokens": 7}


@pytest.mark.asyncio
async def test_run_turn_returns_text_and_interaction_id(monkeypatch):
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    async def fake_invoke(client, kwargs):
        # Sanity: the model + key flowed through.
        assert kwargs["model"] == "gemini-2.5-pro"
        assert kwargs["system_instruction"] == "sys"
        assert kwargs["contents"] == "hi"
        return _FakeResponse(text="pong", id_="int-xyz")

    monkeypatch.setattr(client_mod, "_invoke", fake_invoke)

    result = await client_mod.run_turn(
        user_message="hi",
        api_key="AIza-good",
        model="gemini-2.5-pro",
        system_prompt="sys",
    )
    assert result.text == "pong"
    assert result.interaction_id == "int-xyz"
    assert result.input_tokens == 12
    assert result.output_tokens == 7
    assert result.model == "gemini-2.5-pro"


@pytest.mark.asyncio
async def test_run_turn_threads_previous_interaction(monkeypatch):
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    captured = {}

    async def fake_invoke(client, kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(client_mod, "_invoke", fake_invoke)

    await client_mod.run_turn(
        user_message="hi",
        api_key="AIza-x",
        model="gemini-2.5-flash",
        system_prompt="sys",
        previous_interaction_id="int-prev",
    )
    assert captured["previous_interaction_id"] == "int-prev"


@pytest.mark.asyncio
async def test_empty_key_raises_not_configured(monkeypatch):
    monkeypatch.setattr(client_mod, "_import_genai", lambda: MagicMock())
    with pytest.raises(client_mod.ChatbotNotConfigured):
        await client_mod.run_turn(
            user_message="hi",
            api_key="",
            model="gemini-2.5-pro",
            system_prompt="sys",
        )


@pytest.mark.asyncio
async def test_invoke_failure_wrapped_in_turn_error(monkeypatch):
    fake_genai = MagicMock()
    fake_genai.Client.return_value = MagicMock()
    monkeypatch.setattr(client_mod, "_import_genai", lambda: fake_genai)

    async def boom(client, kwargs):
        raise RuntimeError("api rate-limited")

    monkeypatch.setattr(client_mod, "_invoke", boom)

    with pytest.raises(client_mod.ChatbotTurnError) as excinfo:
        await client_mod.run_turn(
            user_message="hi",
            api_key="AIza-x",
            model="gemini-2.5-pro",
            system_prompt="sys",
        )
    assert "api rate-limited" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Response normalization
# ---------------------------------------------------------------------------


class TestResultFromResponse:
    def test_prefers_text_attr(self):
        resp = MagicMock(text="abc", id="id-1", usage=None)
        result = client_mod._result_from_response(resp, "gemini-2.5-pro")
        assert result.text == "abc"

    def test_falls_back_to_output_text(self):
        resp = MagicMock(spec=["output_text", "id"])
        resp.output_text = "from output_text"
        resp.id = "id-2"
        result = client_mod._result_from_response(resp, "gemini-2.5-pro")
        assert result.text == "from output_text"

    def test_handles_dict_usage(self):
        resp = MagicMock(text="t", id="id", usage={"prompt_tokens": 5, "completion_tokens": 3})
        result = client_mod._result_from_response(resp, "gemini-2.5-pro")
        assert result.input_tokens == 5
        assert result.output_tokens == 3

    def test_missing_usage_returns_none(self):
        resp = MagicMock(spec=["text", "id"])
        resp.text = "t"
        resp.id = "id"
        result = client_mod._result_from_response(resp, "gemini-2.5-pro")
        assert result.input_tokens is None
        assert result.output_tokens is None
