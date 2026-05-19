"""Tests for admz.chatbot.events — SSE wire format and constructors."""

import json

import pytest

from admz.chatbot.events import (
    ChatEventType,
    event_done,
    event_error,
    event_start,
    event_text,
    event_tool_call,
    event_tool_result,
)


class TestSseWireFormat:
    def test_format_includes_event_and_data_lines(self):
        sse = event_text("hello").to_sse()
        # Two lines plus trailing blank line.
        assert sse.startswith("event: text\n")
        assert "data: " in sse
        assert sse.endswith("\n\n"), "SSE event must terminate in blank line"

    def test_data_is_valid_json(self):
        sse = event_text("hello").to_sse()
        data_line = [
            line for line in sse.splitlines() if line.startswith("data: ")
        ][0]
        payload = json.loads(data_line[len("data: "):])
        assert payload == {"chunk": "hello"}

    def test_each_event_carries_its_type_name(self):
        # SSE consumers dispatch on the ``event:`` line; verify the
        # exact strings match ChatEventType values.
        assert event_start("gemini-3.1-pro").to_sse().startswith("event: start\n")
        assert event_text("x").to_sse().startswith("event: text\n")
        assert event_tool_call("t", "t()").to_sse().startswith("event: tool_call\n")
        assert event_tool_result("t", "ok").to_sse().startswith("event: tool_result\n")
        assert event_done().to_sse().startswith("event: done\n")
        assert event_error("boom").to_sse().startswith("event: error\n")


class TestPayloads:
    def test_start_carries_model(self):
        ev = event_start("gemini-3.1-flash")
        assert ev.payload == {"model": "gemini-3.1-flash"}

    def test_tool_call_omits_call_id_when_none(self):
        ev = event_tool_call("list_devices", "list_devices()")
        assert "call_id" not in ev.payload
        assert ev.payload["name"] == "list_devices"
        assert ev.payload["summary"] == "list_devices()"

    def test_tool_call_includes_call_id_when_given(self):
        ev = event_tool_call("list_devices", "list_devices()", call_id="c-1")
        assert ev.payload["call_id"] == "c-1"

    def test_tool_result_status(self):
        ev = event_tool_result("list_devices", "ok", "12 devices")
        assert ev.payload["status"] == "ok"
        assert ev.payload["summary"] == "12 devices"

    def test_done_metadata_optional(self):
        ev = event_done()
        # All fields present but None — explicit "no usage info" signal.
        assert ev.payload == {
            "interaction_id": None,
            "input_tokens": None,
            "output_tokens": None,
        }

    def test_done_carries_interaction_id_and_usage(self):
        ev = event_done(interaction_id="int-1", input_tokens=10, output_tokens=5)
        assert ev.payload["interaction_id"] == "int-1"
        assert ev.payload["input_tokens"] == 10
        assert ev.payload["output_tokens"] == 5


class TestEventType:
    def test_string_enum_values_stable(self):
        # The browser-side renderer hard-codes these strings;
        # changing them is a wire-protocol break.
        assert ChatEventType.START.value == "start"
        assert ChatEventType.TEXT.value == "text"
        assert ChatEventType.TOOL_CALL.value == "tool_call"
        assert ChatEventType.TOOL_RESULT.value == "tool_result"
        assert ChatEventType.DONE.value == "done"
        assert ChatEventType.ERROR.value == "error"
