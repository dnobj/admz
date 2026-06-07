"""Unit tests for the in-ADMZ manual function-calling loop (AFC replacement).

These drive `client._run_manual_tool_loop` directly with a fake `models` object
(async `generate_content`) and a fake MCP session (async `list_tools`/`call_tool`),
then translate the yielded chunks through the real `_translate_stream_chunk` to
assert the event contract. No network / no SDK calls (the loop only uses
`google.genai.types` for Content/Part construction, which is available locally).

Regression coverage for the gemini-3.x empty-turn fix: the loop must execute the
tool, append the model's Content verbatim (thought_signature round-trip), continue
to a final text answer, sum tokens across calls, and never bypass the confirm gate.
"""

from __future__ import annotations

import json

import pytest

import admz.chatbot.client as client
from admz.chatbot.events import ChatEventType


# --- fakes -----------------------------------------------------------------


class _FC:
    def __init__(self, name, args, fc_id=None):
        self.name = name
        self.args = args
        self.id = fc_id


class _UM:
    def __init__(self, i, o):
        self.prompt_token_count = i
        self.candidates_token_count = o


class _Cand:
    def __init__(self, content):
        self.content = content


class _Resp:
    """Stand-in for a generate_content response."""

    def __init__(self, *, function_calls=None, text=None, content=None, usage=(0, 0), rid=None):
        self.function_calls = list(function_calls or [])
        self.text = text
        self._content = content if content is not None else object()
        self.usage_metadata = _UM(*usage)
        self.id = rid

    @property
    def candidates(self):
        return [_Cand(self._content)]


class _FakeModels:
    def __init__(self, responses):
        self._responses = list(responses)
        self.call_contents = []  # snapshot of `contents` at each call

    async def generate_content(self, *, model, contents, config):
        self.call_contents.append(list(contents))
        return self._responses.pop(0)


class _ToolText:
    def __init__(self, text):
        self.text = text


class _CallResult:
    def __init__(self, payload):
        self.content = [_ToolText(json.dumps(payload))]


class _FakeTool:
    name = "execute_operation"
    description = "Execute a VAPIX op."
    inputSchema = {"type": "object", "properties": {"device_id": {"type": "string"}}}


class _Listed:
    tools = [_FakeTool()]


class _FakeSession:
    def __init__(self, results):
        # results: list of payload dicts returned by successive call_tool calls
        self._results = list(results)
        self.calls = []

    async def list_tools(self):
        return _Listed()

    async def call_tool(self, name, args):
        self.calls.append((name, dict(args or {})))
        return _CallResult(self._results.pop(0))


async def _run(models, session, contents="do the thing"):
    chunks = []
    async for ch in client._run_manual_tool_loop(
        models, "gemini-2.5-flash", contents, "sys", session
    ):
        chunks.append(ch)
    return chunks


def _events(chunks):
    out = []
    for ch in chunks:
        e = client._translate_stream_chunk(ch)
        if e is not None:
            out.append(e)
    return out


# --- tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_turn_executes_appends_content_verbatim_and_continues():
    sentinel_content = object()  # identity-checked: must be appended verbatim
    models = _FakeModels([
        _Resp(function_calls=[_FC("execute_operation", {"device_id": "ABC"})],
              content=sentinel_content, usage=(100, 10)),
        _Resp(text="Done — magnification set.", usage=(30, 3)),
    ])
    session = _FakeSession([{"success": True, "data": {}}])

    chunks = await _run(models, session)
    events = _events(chunks)

    # tool executed exactly once with the model's args
    assert session.calls == [("execute_operation", {"device_id": "ABC"})]
    # the raw model Content was appended VERBATIM before the 2nd call
    assert sentinel_content in models.call_contents[1]
    # event contract: TOOL_CALL -> TEXT -> DONE
    types_seq = [e.type for e in events]
    assert types_seq[0] == ChatEventType.TOOL_CALL
    assert events[0].payload["name"] == "execute_operation"
    assert ChatEventType.TEXT in types_seq
    assert types_seq[-1] == ChatEventType.DONE
    assert "Done" in "".join(
        e.payload.get("chunk", "") for e in events if e.type == ChatEventType.TEXT
    )


@pytest.mark.asyncio
async def test_multi_tool_turn_sums_tokens_across_calls():
    models = _FakeModels([
        _Resp(function_calls=[_FC("execute_operation", {"n": 1})], content=object(), usage=(100, 10)),
        _Resp(function_calls=[_FC("execute_operation", {"n": 2})], content=object(), usage=(50, 5)),
        _Resp(text="All set.", usage=(30, 3)),
    ])
    session = _FakeSession([{"ok": 1}, {"ok": 2}])

    events = _events(await _run(models, session))
    done = events[-1]
    assert done.type == ChatEventType.DONE
    assert done.payload["input_tokens"] == 180   # 100+50+30
    assert done.payload["output_tokens"] == 18   # 10+5+3
    assert len(session.calls) == 2


@pytest.mark.asyncio
async def test_confirm_gate_not_bypassed():
    # execute_operation returns a blocked/confirm dict; the loop must forward it
    # and let the model ask the user — it must NOT auto-call any confirm tool.
    models = _FakeModels([
        _Resp(function_calls=[_FC("execute_operation", {"op": "reboot"})], content=object(), usage=(10, 2)),
        _Resp(text="This will reboot the device. Do you want to proceed?", usage=(8, 4)),
    ])
    session = _FakeSession([
        {"blocked": True, "confirm_token": "tok-1",
         "confirmation_level": "llm_confirm", "message": "ask for consent"},
    ])

    events = _events(await _run(models, session))
    # only the original tool was called — never a confirm tool
    assert [c[0] for c in session.calls] == ["execute_operation"]
    text = "".join(e.payload.get("chunk", "") for e in events if e.type == ChatEventType.TEXT)
    assert "proceed" in text.lower()


@pytest.mark.asyncio
async def test_parallel_calls_all_executed():
    models = _FakeModels([
        _Resp(function_calls=[_FC("execute_operation", {"a": 1}), _FC("execute_operation", {"b": 2})],
              content=object(), usage=(20, 4)),
        _Resp(text="Both done.", usage=(5, 1)),
    ])
    session = _FakeSession([{"ok": "a"}, {"ok": "b"}])
    events = _events(await _run(models, session))
    assert len(session.calls) == 2
    tool_events = [e for e in events if e.type == ChatEventType.TOOL_CALL]
    assert len(tool_events) == 2


@pytest.mark.asyncio
async def test_safety_cap_stops_and_reports():
    # model always wants a tool — loop must stop at the cap with a visible message
    import os
    os.environ["ADMZ_GEMINI_MAX_TOOL_ITERATIONS"] = "3"
    try:
        models = _FakeModels([
            _Resp(function_calls=[_FC("execute_operation", {})], content=object(), usage=(1, 1))
            for _ in range(3)
        ])
        session = _FakeSession([{"ok": 1}, {"ok": 2}, {"ok": 3}])
        events = _events(await _run(models, session))
    finally:
        del os.environ["ADMZ_GEMINI_MAX_TOOL_ITERATIONS"]
    assert len(session.calls) == 3
    text = "".join(e.payload.get("chunk", "") for e in events if e.type == ChatEventType.TEXT)
    assert "Stopped after 3 tool calls" in text
    assert events[-1].type == ChatEventType.DONE


@pytest.mark.asyncio
async def test_mcp_declarations_built_from_list_tools():
    session = _FakeSession([])
    from google.genai import types
    tools = await client._mcp_declarations(session, types)
    assert len(tools) == 1
    decls = tools[0].function_declarations
    assert decls[0].name == "execute_operation"
