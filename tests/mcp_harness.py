"""Test-side access to the ADMZ MCP server's registered request handlers.

Why this module exists
----------------------
Eleven test modules used to reach into ``server.server.request_handlers`` — the
mcp 1.x low-level ``Server``'s ``{RequestType: handler}`` dict. mcp 2.x deleted
that attribute. Handlers now live in a private ``_request_handlers`` dict keyed
by JSON-RPC *method string* and are read back through the public
``Server.get_request_handler(method)``, which returns a ``HandlerEntry`` of
``(params_type, handler)``.

Keeping the guard as strong as it was
-------------------------------------
The 1.x spelling was drift-proof by accident: tests looked handlers up by the
SDK's own ``ListToolsRequest`` / ``CallToolRequest`` *classes*, so a server that
registered under the wrong key could not be found by the test either — the
lookup and the runtime dispatch shared one source of truth.

A naive 2.x port that writes ``"tools/list"`` as a literal on both sides throws
that away: ``admz/mcp/server.py`` could register under a typo'd method string
and every one of these tests would still pass, while no real client could reach
a single tool. So both sides read the method strings off the SDK's own request
models (see ``_LIST_TOOLS_METHOD`` / ``_CALL_TOOL_METHOD`` in
``admz/mcp/server.py``). Neither side spells the string itself, so the two
cannot disagree.

Likewise, the params model used to build the request is the one the server
actually *registered* (``entry.params_type``), not a constant repeated here —
so registering the wrong params model fails these helpers rather than sliding
past them.

What is genuinely weaker, and what replaces it
----------------------------------------------
Under 1.x, ``request_handlers[CallToolRequest]`` was the SDK's *wrapper* around
ADMZ's handler. Awaiting it ran the SDK's own result marshalling and its
exception → ``isError`` conversion. Under 2.x ``get_request_handler`` returns
ADMZ's callable itself, so invoking it here skips the runner, and the
``ServerRequestContext`` these helpers pass is ``None``.

That is a real reduction, and it is not left uncompensated:

* Argument validation is *parity*, not loss — the 1.x helpers built a real
  ``CallToolRequest``, and these build the real registered params model.
* ``None`` for the context is safe by construction: every ADMZ handler reaches
  shared state through ``self`` and none touches ``ctx``. If one ever does,
  ``test_mcp_protocol_roundtrip.py`` fails rather than this returning a
  plausible-looking result.
* ``test_mcp_protocol_roundtrip.py`` drives a real ``ClientSession`` over
  in-memory streams against a real ``ADMZMCPServer``, so registration, params
  validation, the runner, the real context and the wire encoding are all
  exercised end to end. The 1.x suite never had that test; it is the reason
  this module's shortcuts do not thin the suite's coverage overall.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
)

# Read off the SDK's models, exactly as admz/mcp/server.py does. Do not replace
# these with string literals — see the module docstring.
LIST_TOOLS_METHOD: str = ListToolsRequest.model_fields["method"].default
CALL_TOOL_METHOD: str = CallToolRequest.model_fields["method"].default


def handler_entry(server: Any, method: str):
    """The ``HandlerEntry`` the server registered for ``method``.

    ``server`` is an ``ADMZMCPServer`` (not the low-level ``Server``).
    """
    entry = server.server.get_request_handler(method)
    assert entry is not None, (
        f"no request handler registered for {method!r} — "
        "ADMZMCPServer._register_handlers did not run, or registered "
        "under a different method string"
    )
    return entry


async def list_tools(server: Any) -> List[Tool]:
    """Every ``Tool`` the server advertises, via its real list_tools handler."""
    entry = handler_entry(server, LIST_TOOLS_METHOD)
    # `tools/list` params are all-optional; validating {} is what the runner
    # does for a request that omits `params` entirely.
    params = entry.params_type.model_validate({})
    result = await entry.handler(None, params)
    assert isinstance(result, ListToolsResult), (
        f"list_tools handler returned {type(result).__name__}, "
        "expected ListToolsResult"
    )
    return list(result.tools)


async def tool_names(server: Any) -> List[str]:
    """Advertised tool names, in advertised order."""
    return [t.name for t in await list_tools(server)]


async def find_tool(server: Any, name: str) -> Tool:
    """The advertised ``Tool`` called ``name``; fails loudly if absent."""
    for tool in await list_tools(server):
        if tool.name == name:
            return tool
    raise AssertionError(f"tool {name!r} is not advertised by list_tools")


async def call_tool_result(
    server: Any, name: str, arguments: Optional[Dict[str, Any]] = None
) -> CallToolResult:
    """Dispatch a tool call through the real handler, returning the raw result.

    Arguments go through the params model the server registered, so a call that
    the wire would reject is rejected here too.
    """
    entry = handler_entry(server, CALL_TOOL_METHOD)
    params = entry.params_type.model_validate(
        {"name": name, "arguments": {} if arguments is None else arguments}
    )
    result = await entry.handler(None, params)
    assert isinstance(result, CallToolResult), (
        f"call_tool handler returned {type(result).__name__}, "
        "expected CallToolResult"
    )
    return result


async def call_tool(
    server: Any, name: str, arguments: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Dispatch a tool call and decode its JSON payload.

    Covers both the success envelope and ADMZ's error envelopes — ``call_tool``
    returns both as ordinary text content (it catches broadly and never lets an
    exception reach the SDK), which is unchanged from 1.x.
    """
    result = await call_tool_result(server, name, arguments)
    assert result.content, f"{name} returned no content"
    return json.loads(result.content[0].text)
