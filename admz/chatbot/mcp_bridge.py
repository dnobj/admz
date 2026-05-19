"""ADMZ MCP server bridge for the chatbot.

Provides an async context manager that spawns ``python -m admz mcp``
as a stdio subprocess, performs the MCP handshake, and yields a
``ClientSession`` that ``google-genai`` accepts directly as a tool
source (see :mod:`admz.chatbot.client`).

The Python ``mcp`` SDK is imported lazily so that:

  - ADMZ installs *without* a chatbot configured don't pay the
    import cost on every chat page load
  - tests that don't exercise the MCP integration can mock out
    :func:`open_mcp_session` without standing up subprocesses

Subprocess lifecycle is **per-turn**: the bridge opens a new
subprocess for each chat turn and tears it down at end-of-turn.
That's the simplest model and gives clean process isolation per
call. A subprocess pool keyed by principal is a future optimization
(noted in the requirements doc as KL-CB-006).
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


class McpBridgeError(Exception):
    """Generic failure during MCP subprocess open or handshake."""


class McpBridgeMissing(McpBridgeError):
    """The ``mcp`` Python package isn't installed in this environment."""


@asynccontextmanager
async def open_mcp_session(
    *,
    python_executable: Optional[str] = None,
    extra_env: Optional[dict] = None,
) -> AsyncIterator[Any]:
    """Spawn ``python -m admz mcp`` and yield a ready MCP ClientSession.

    The session is suitable for passing into the ``google-genai``
    SDK as ``config=GenerateContentConfig(tools=[session])``. It
    exposes the same 19 tools that external MCP clients see when
    they connect to the ADMZ MCP server.

    The context manager handles cleanup: when the ``async with``
    block exits, the subprocess is terminated and stdio streams
    are drained.

    Raises:
        McpBridgeMissing: the ``mcp`` SDK isn't installed.
        McpBridgeError: subprocess spawn or handshake failed.
    """
    try:
        from mcp import ClientSession  # type: ignore[import-not-found]
        from mcp.client.stdio import (  # type: ignore[import-not-found]
            StdioServerParameters,
            stdio_client,
        )
    except ImportError as exc:
        raise McpBridgeMissing(
            "The 'mcp' package is not installed. Install via "
            "'pip install mcp' to enable chatbot tool use."
        ) from exc

    py = python_executable or sys.executable
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)

    params = StdioServerParameters(
        command=py,
        args=["-m", "admz", "mcp"],
        env=env,
    )

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                # Handshake — sends an `initialize` request to the
                # spawned server and waits for the capabilities
                # response. After this returns the session is
                # ready for tool calls.
                await session.initialize()
                logger.debug("MCP bridge initialized via 'python -m admz mcp'")
                yield session
    except McpBridgeMissing:
        raise
    except Exception as exc:
        # Wrap so callers can distinguish bridge failures from SDK
        # failures further down the stack.
        raise McpBridgeError(f"Failed to open MCP session: {exc}") from exc
