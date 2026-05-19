"""Chat stream event types.

The streaming chat route emits a sequence of these events over
SSE. Defining them as a small typed surface keeps the wire
protocol explicit and lets the client renderer dispatch by type.

Wire format (server-sent events):

    event: <type>
    data: <json>

    event: <type>
    data: <json>

The browser-side consumer reads chunks, splits on blank lines,
parses each ``data:`` line as JSON, and dispatches on ``event:``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ChatEventType(str, Enum):
    """Names match the SSE ``event:`` field."""

    START = "start"          # turn begins; carries the model name
    TEXT = "text"            # incremental text chunk
    TOOL_CALL = "tool_call"  # LLM invoked a tool — name + arg summary
    TOOL_RESULT = "tool_result"  # tool returned — status + summary
    DONE = "done"            # turn complete — final interaction_id + usage
    ERROR = "error"          # unrecoverable error mid-stream


@dataclass
class ChatEvent:
    """One event in the chat stream."""

    type: ChatEventType
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        """Serialize this event in the SSE wire format.

        Returns a string ready to be written to the response body.
        Includes the trailing blank line that terminates the event.
        """
        data = json.dumps(self.payload, default=str)
        return f"event: {self.type.value}\ndata: {data}\n\n"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type.value, **asdict(self)}


# ---------------------------------------------------------------------------
# Constructors — keep the route + client code from naming string literals
# ---------------------------------------------------------------------------


def event_start(model: str) -> ChatEvent:
    return ChatEvent(ChatEventType.START, {"model": model})


def event_text(chunk: str) -> ChatEvent:
    return ChatEvent(ChatEventType.TEXT, {"chunk": chunk})


def event_tool_call(name: str, args_summary: str, call_id: Optional[str] = None) -> ChatEvent:
    """args_summary is a short, display-friendly rendering — not the raw JSON.

    Raw args are *not* sent to the browser. The LLM may pass
    credentials, device IDs, or other sensitive values that don't
    belong in a chat transcript. The summary is something like
    ``"list_devices"`` or ``"snapshot_device(cam-01)"``.
    """
    payload: Dict[str, Any] = {"name": name, "summary": args_summary}
    if call_id is not None:
        payload["call_id"] = call_id
    return ChatEvent(ChatEventType.TOOL_CALL, payload)


def event_tool_result(
    name: str,
    status: str,
    summary: str = "",
    call_id: Optional[str] = None,
) -> ChatEvent:
    """status is one of ``"ok"`` / ``"error"`` / ``"skipped"``."""
    payload: Dict[str, Any] = {"name": name, "status": status, "summary": summary}
    if call_id is not None:
        payload["call_id"] = call_id
    return ChatEvent(ChatEventType.TOOL_RESULT, payload)


def event_done(
    interaction_id: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
) -> ChatEvent:
    return ChatEvent(
        ChatEventType.DONE,
        {
            "interaction_id": interaction_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    )


def event_error(message: str) -> ChatEvent:
    return ChatEvent(ChatEventType.ERROR, {"message": message})
