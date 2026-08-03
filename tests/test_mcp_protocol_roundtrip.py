"""End-to-end MCP protocol round-trip against a real ``ADMZMCPServer``.

This test did not exist under mcp 1.x, and it exists now because of what the
2.x port costs elsewhere.

Every other MCP test in this suite reaches the handlers through
``tests/mcp_harness.py``, which calls them directly. Under 1.x that reach-through
landed on the SDK's *wrapper*; under 2.x ``Server.get_request_handler`` hands back
ADMZ's own callable, so the harness now skips the runner and passes ``None`` for
the ``ServerRequestContext``. Rather than let that quietly become a suite where
nothing checks that the tools are reachable by an actual client, this test drives
a real ``ClientSession`` over in-memory streams and asserts across the wire.

What only this test can catch:

* handlers registered under a method string no client will ever send,
* a params model that rejects what the protocol legitimately sends,
* a handler that returns something the runner cannot marshal,
* a handler that touches ``ctx`` — which the harness passes as ``None``,
* the initialize handshake failing to advertise the tools capability.
"""

from __future__ import annotations

import json

import anyio
import pytest
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams


def _isolate(tmp_path, monkeypatch):
    """Bind every import-time store to tmp_path before the server is built."""
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")


@pytest.mark.asyncio
async def test_tools_are_reachable_over_a_real_client_session(tmp_path, monkeypatch):
    """A real client can initialize, list tools, and call one.

    Deliberately end-to-end: no handler is looked up by hand anywhere in this
    test. If ``_register_handlers`` registers under the wrong method string, or
    the params model does not match what the protocol sends, this fails where
    the direct-dispatch helpers in ``tests/mcp_harness.py`` cannot.
    """
    _isolate(tmp_path, monkeypatch)

    from admz.mcp.server import ADMZMCPServer

    admz_server = ADMZMCPServer()
    admz_server.registry.add_device("roundtrip-cam", {"host": "192.0.2.10"})

    async with create_client_server_memory_streams() as (client_streams, server_streams):
        client_read, client_write = client_streams
        server_read, server_write = server_streams

        async with anyio.create_task_group() as tg:

            async def _serve():
                await admz_server.server.run(
                    server_read,
                    server_write,
                    admz_server.server.create_initialization_options(),
                    # Surface handler crashes as test failures instead of
                    # letting them become an opaque JSON-RPC error body.
                    raise_exceptions=True,
                )

            tg.start_soon(_serve)

            async with ClientSession(client_read, client_write) as session:
                init = await session.initialize()
                assert init.capabilities.tools is not None, (
                    "server did not advertise the tools capability — no client "
                    "would attempt tools/list against it"
                )

                listed = await session.list_tools()
                names = {t.name for t in listed.tools}
                assert "list_devices" in names
                assert "execute_operation" in names

                # The schema must survive the wire, not just exist in-process.
                # This is the protocol-level companion to the GH #225 guard in
                # tests/test_chatbot_manual_loop.py.
                execute_op = next(
                    t for t in listed.tools if t.name == "execute_operation"
                )
                assert execute_op.input_schema.get("type") == "object"
                assert "device_id" in execute_op.input_schema.get("properties", {})

                result = await session.call_tool("list_devices", {})
                assert result.content, "list_devices returned no content"
                payload = json.loads(result.content[0].text)
                assert payload["success"] is True
                assert any(
                    d.get("device_id") == "roundtrip-cam"
                    or d.get("id") == "roundtrip-cam"
                    for d in payload["devices"]
                ), payload

            tg.cancel_scope.cancel()


@pytest.mark.asyncio
async def test_error_envelope_survives_the_wire(tmp_path, monkeypatch):
    """ADMZ's JSON error envelopes reach the client as ordinary content.

    mcp 2.x dropped the SDK's exception → ``isError`` conversion. ADMZ never
    relied on it — ``call_tool`` catches broadly and returns its own envelope —
    but that is exactly the kind of claim that deserves a test rather than a
    comment. A refusal must arrive as readable content, not as a JSON-RPC error
    that the chatbot's ``content[0].text`` read would blow up on.
    """
    _isolate(tmp_path, monkeypatch)

    from admz.mcp.server import ADMZMCPServer

    admz_server = ADMZMCPServer()

    async with create_client_server_memory_streams() as (client_streams, server_streams):
        client_read, client_write = client_streams
        server_read, server_write = server_streams

        async with anyio.create_task_group() as tg:

            async def _serve():
                await admz_server.server.run(
                    server_read,
                    server_write,
                    admz_server.server.create_initialization_options(),
                )

            tg.start_soon(_serve)

            async with ClientSession(client_read, client_write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "get_device_info", {"device_id": "no-such-device"}
                )
                assert result.content, "expected an error envelope, got no content"
                payload = json.loads(result.content[0].text)
                assert "error" in payload, payload

            tg.cancel_scope.cancel()


@pytest.mark.asyncio
async def test_schema_violation_is_rejected_by_admz_not_the_sdk(tmp_path, monkeypatch):
    """The argument gate the SDK stopped enforcing.

    **mcp 1.x ran ``jsonschema.validate(arguments, tool.inputSchema)`` inside the
    ``@server.call_tool()`` decorator, before every dispatch. 2.x deleted the
    decorator and validates nothing.** ``call_tool`` therefore performs that
    check itself (``server.py``, the ``jsonschema.validate`` block). This is now
    ADMZ's *only* schema enforcement — hand-rolled validation sitting next to a
    schema-aware SDK looks redundant, and it is not. Do not delete it.

    This test exists because the pre-existing ``InvalidInput`` coverage cannot
    catch its removal. ``TestMcpInputValidation`` drives
    ``{"device_id": "../../../etc/passwd"}`` — a *string*, which satisfies the
    schema and is rejected by ``_validate_tool_args`` (the CR-5 identifier
    allow-list), a different control returning the same envelope.

    So the violation here is chosen to be invisible to CR-5: ``_validate_tool_args``
    inspects only ``device_id``/``account_id``/``facet_name``/``device_ids``/``facets``,
    while ``set_fleet_setting``'s ``key`` carries ``enum: [default_password,
    default_username]``. An off-enum ``key`` can *only* be caught by the schema
    gate — delete the ``jsonschema.validate`` block and this test goes red while
    every other InvalidInput test stays green.
    """
    _isolate(tmp_path, monkeypatch)

    from admz.mcp.server import ADMZMCPServer

    admz_server = ADMZMCPServer()

    async with create_client_server_memory_streams() as (client_streams, server_streams):
        client_read, client_write = client_streams
        server_read, server_write = server_streams

        async with anyio.create_task_group() as tg:

            async def _serve():
                await admz_server.server.run(
                    server_read,
                    server_write,
                    admz_server.server.create_initialization_options(),
                    raise_exceptions=True,
                )

            tg.start_soon(_serve)

            async with ClientSession(client_read, client_write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "set_fleet_setting",
                    {"key": "not_a_declared_setting", "value": "x"},
                )
                payload = json.loads(result.content[0].text)

                assert payload["success"] is False, payload
                assert payload["error"] == "InvalidInput", payload
                # Assert on the message shape, not just the error code: the CR-5
                # identifier check returns the same code, so a bare
                # `error == "InvalidInput"` assertion would be satisfied by the
                # wrong control and leave this gate uncovered.
                assert "Input validation error" in payload["message"], payload

            tg.cancel_scope.cancel()
