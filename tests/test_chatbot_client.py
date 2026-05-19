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


# ---------------------------------------------------------------------------
# Stream-chunk translation: real Gemini 2.x shape
# ---------------------------------------------------------------------------
#
# google-genai 2.x yields GenerateContentResponse-like chunks where
# text lives at candidates[0].content.parts[0].text. The original
# translator only probed chunk.text, so a response that didn't
# expose that flat attribute returned empty. These tests cover the
# nested-shape extraction.


class _FakePart:
    def __init__(self, *, text=None, function_call=None):
        if text is not None:
            self.text = text
        if function_call is not None:
            self.function_call = function_call


class _FakeFunctionCall:
    def __init__(self, name):
        self.name = name


class _FakeContent:
    def __init__(self, parts):
        self.parts = parts


class _FakeCandidate:
    def __init__(self, parts):
        self.content = _FakeContent(parts)


class _FakeUsageMetadata:
    def __init__(self, prompt=None, candidates=None):
        if prompt is not None:
            self.prompt_token_count = prompt
        if candidates is not None:
            self.candidates_token_count = candidates


class _FakeStreamChunk:
    """Mimics google-genai 2.x GenerateContentResponse streaming chunk."""

    def __init__(self, *, candidates=None, usage_metadata=None, response_id=None):
        if candidates is not None:
            self.candidates = candidates
        if usage_metadata is not None:
            self.usage_metadata = usage_metadata
        if response_id is not None:
            self.response_id = response_id


class TestExtractTextFromChunk:
    def test_flat_text_attr(self):
        chunk = MagicMock(spec=["text"])
        chunk.text = "hello"
        assert client_mod._extract_text_from_chunk(chunk) == "hello"

    def test_nested_candidates_parts(self):
        chunk = _FakeStreamChunk(
            candidates=[_FakeCandidate([_FakePart(text="hello world")])]
        )
        assert client_mod._extract_text_from_chunk(chunk) == "hello world"

    def test_multiple_parts_joined(self):
        chunk = _FakeStreamChunk(
            candidates=[
                _FakeCandidate(
                    [_FakePart(text="hello "), _FakePart(text="world")]
                )
            ]
        )
        assert client_mod._extract_text_from_chunk(chunk) == "hello world"

    def test_empty_chunk_returns_none(self):
        chunk = _FakeStreamChunk(candidates=[])
        assert client_mod._extract_text_from_chunk(chunk) is None

    def test_function_call_only_returns_none(self):
        """A chunk that's a function_call (no text) should yield None."""
        chunk = _FakeStreamChunk(
            candidates=[
                _FakeCandidate(
                    [_FakePart(function_call=_FakeFunctionCall("list_devices"))]
                )
            ]
        )
        assert client_mod._extract_text_from_chunk(chunk) is None


class TestExtractFunctionCallFromChunk:
    def test_nested_function_call(self):
        chunk = _FakeStreamChunk(
            candidates=[
                _FakeCandidate(
                    [_FakePart(function_call=_FakeFunctionCall("list_devices"))]
                )
            ]
        )
        assert client_mod._extract_function_call_from_chunk(chunk) == "list_devices"

    def test_no_function_call_returns_none(self):
        chunk = _FakeStreamChunk(
            candidates=[_FakeCandidate([_FakePart(text="hi")])]
        )
        assert client_mod._extract_function_call_from_chunk(chunk) is None


class TestExtractUsageFromChunk:
    def test_usage_metadata_shape(self):
        chunk = _FakeStreamChunk(
            usage_metadata=_FakeUsageMetadata(prompt=42, candidates=87)
        )
        in_t, out_t = client_mod._extract_usage_from_chunk(chunk)
        assert in_t == 42
        assert out_t == 87

    def test_legacy_dict_usage(self):
        chunk = MagicMock(spec=["usage"])
        chunk.usage = {"input_tokens": 10, "output_tokens": 20}
        in_t, out_t = client_mod._extract_usage_from_chunk(chunk)
        assert in_t == 10
        assert out_t == 20

    def test_no_usage(self):
        chunk = _FakeStreamChunk()
        assert client_mod._extract_usage_from_chunk(chunk) == (None, None)


class TestTranslateStreamChunk:
    def test_yields_text_event_for_nested_text(self):
        """The Gemini 2.x case that broke the chat — nested parts."""
        chunk = _FakeStreamChunk(
            candidates=[_FakeCandidate([_FakePart(text="real response")])]
        )
        ev = client_mod._translate_stream_chunk(chunk)
        assert ev is not None
        assert ev.type.value == "text"
        assert ev.payload["chunk"] == "real response"

    def test_yields_tool_call_for_nested_function_call(self):
        chunk = _FakeStreamChunk(
            candidates=[
                _FakeCandidate(
                    [_FakePart(function_call=_FakeFunctionCall("list_devices"))]
                )
            ]
        )
        ev = client_mod._translate_stream_chunk(chunk)
        assert ev is not None
        assert ev.type.value == "tool_call"
        assert ev.payload["name"] == "list_devices"

    def test_yields_done_for_terminal_chunk_with_usage_metadata(self):
        chunk = _FakeStreamChunk(
            usage_metadata=_FakeUsageMetadata(prompt=100, candidates=50),
            response_id="resp-1",
        )
        ev = client_mod._translate_stream_chunk(chunk)
        assert ev is not None
        assert ev.type.value == "done"
        assert ev.payload["input_tokens"] == 100
        assert ev.payload["output_tokens"] == 50
        assert ev.payload["interaction_id"] == "resp-1"

    def test_empty_chunk_returns_none(self):
        chunk = _FakeStreamChunk(candidates=[_FakeCandidate([])])
        assert client_mod._translate_stream_chunk(chunk) is None
