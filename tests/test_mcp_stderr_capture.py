"""The MCP subprocess's stderr reaches the ADMZ log (#296 — diagnostic).

`stdio_client` defaults `errlog` to the PARENT's `sys.stderr`. Under the
Shawl-supervised service that is not the ADMZ log, so a subprocess dying during
`list_tools()` took its traceback with it and production could only report
"Connection closed".

Vacuity note: "we now capture stderr" is worth nothing unless something proves a
real child's real traceback actually arrives. `TestAgainstARealSubprocess` spawns
a process through the REAL `stdio_client` with the REAL pipe and asserts a
distinctive marker lands in `caplog` — it is the test that would fail if
`errlog` were plumbed to something anyio cannot use as a pipe target, which is
exactly what a logger-shim implementation would have been.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys

import pytest

MARKER = "ZZ-CHILD-TRACEBACK-MARKER-ZZ"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ── the pump itself ──────────────────────────────────────────────────────────
class TestStderrPump:
    def test_it_relays_lines_to_the_log_and_keeps_a_tail(self, caplog):
        from admz.chatbot.mcp_stderr import StderrPump
        pump = StderrPump()
        with caplog.at_level(logging.INFO, logger="admz.chatbot.mcp_stderr"):
            pump.writer.write("first line\nsecond line\n")
            tail = pump.close()
        assert tail == ["first line", "second line"]
        msgs = "\n".join(r.getMessage() for r in caplog.records)
        assert "first line" in msgs and "second line" in msgs

    def test_close_drains_before_returning(self, caplog):
        """The whole point: a child writes its traceback and exits immediately.
        Without the join in close(), the tail can come back empty purely because
        the reader thread had not been scheduled yet."""
        from admz.chatbot.mcp_stderr import StderrPump
        pump = StderrPump()
        pump.writer.write(f"Traceback (most recent call last):\n{MARKER}\n")
        tail = pump.close()          # no sleep anywhere — close() must guarantee it
        assert MARKER in "\n".join(tail)

    def test_the_tail_is_bounded(self):
        from admz.chatbot.mcp_stderr import StderrPump
        pump = StderrPump(tail_lines=5)
        for i in range(50):
            pump.writer.write(f"line {i}\n")
        tail = pump.close()
        assert len(tail) == 5 and tail[-1] == "line 49"

    def test_close_is_idempotent(self):
        """`open_mcp_session` closes on the except arm AND in finally."""
        from admz.chatbot.mcp_stderr import StderrPump
        pump = StderrPump()
        pump.writer.write("only line\n")
        assert pump.close() == ["only line"]
        assert pump.close() == ["only line"]      # must not raise

    def test_log_tail_is_loud_and_says_so_when_empty(self, caplog):
        from admz.chatbot.mcp_stderr import log_tail
        with caplog.at_level(logging.ERROR, logger="admz.chatbot.mcp_stderr"):
            log_tail([MARKER], reason="boom")
            log_tail([], reason="boom")
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 2
        joined = "\n".join(r.getMessage() for r in errors)
        assert MARKER in joined
        assert "wrote nothing to stderr" in joined     # absence stated, not implied


# ── the integration that matters ─────────────────────────────────────────────
class TestAgainstARealSubprocess:
    def test_a_real_child_writing_to_stderr_reaches_the_log(self, caplog):
        """A real OS process, a real inherited pipe, a real reader thread.

        This is what proves the `errlog` object is usable as a subprocess stderr
        target. A `TextIOBase` shim that only implements write() would fail here
        — `mcp/client/stdio.py` passes errlog straight to
        `anyio.open_process(..., stderr=errlog)`, which needs a real fileno().
        """
        from admz.chatbot.mcp_stderr import StderrPump
        pump = StderrPump()
        code = (f"import sys; sys.stderr.write('Traceback (most recent call last):\\n');"
                f"sys.stderr.write('{MARKER}\\n'); sys.stderr.flush(); sys.exit(3)")
        with caplog.at_level(logging.INFO, logger="admz.chatbot.mcp_stderr"):
            proc = subprocess.Popen([sys.executable, "-c", code],
                                    stderr=pump.writer, stdout=subprocess.DEVNULL)
            rc = proc.wait(timeout=60)
            tail = pump.close()
        assert rc == 3
        assert MARKER in "\n".join(tail), "the child's stderr never reached the pump"
        assert MARKER in "\n".join(r.getMessage() for r in caplog.records)

    @pytest.mark.skipif(os.getenv("ADMZ_SKIP_MCP_SPAWN") == "1",
                        reason="subprocess spawn disabled in this environment")
    def test_the_real_stdio_client_accepts_our_errlog(self, caplog):
        """End-to-end through the REAL mcp `stdio_client`.

        The child is not an MCP server, so the handshake fails — which is the
        scenario: a subprocess that dies without speaking the protocol. What
        must survive is its stderr.
        """
        mcp_stdio = pytest.importorskip("mcp.client.stdio")
        from admz.chatbot.mcp_stderr import StderrPump

        pump = StderrPump()
        params = mcp_stdio.StdioServerParameters(
            command=sys.executable,
            args=["-c", f"import sys; sys.stderr.write('{MARKER}\\n'); "
                        "sys.stderr.flush(); sys.exit(1)"],
            env=dict(os.environ),
        )

        async def _drive():
            try:
                async with mcp_stdio.stdio_client(params, errlog=pump.writer):
                    await asyncio.sleep(0.2)
            except Exception:
                pass          # the failure is expected; the stderr is the point

        with caplog.at_level(logging.INFO, logger="admz.chatbot.mcp_stderr"):
            _run(_drive())
            tail = pump.close()
        assert MARKER in "\n".join(tail), (
            "stdio_client did not route the child's stderr into our pipe")


# ── the bridge wires it in ───────────────────────────────────────────────────
class TestBridgeWiring:
    def test_it_passes_errlog_and_logs_the_tail_when_the_session_fails(
            self, monkeypatch, caplog):
        """Pins both halves: `errlog=` is actually handed to `stdio_client`, and
        a failure re-emits the captured tail at ERROR so it survives an operator
        running at WARNING."""
        import admz.chatbot.mcp_bridge as B

        seen = {}

        class _FakeCM:
            def __init__(self, params, errlog=None):
                seen["errlog"] = errlog
                self._errlog = errlog

            async def __aenter__(self):
                # Behave like a child that writes a traceback and dies.
                self._errlog.write(f"{MARKER}\n")
                self._errlog.flush()
                raise RuntimeError("Connection closed")

            async def __aexit__(self, *a):
                return False

        import mcp.client.stdio as real_stdio
        monkeypatch.setattr(real_stdio, "stdio_client",
                            lambda params, errlog=None: _FakeCM(params, errlog))

        async def _go():
            async with B.open_mcp_session():
                pass

        with caplog.at_level(logging.ERROR, logger="admz.chatbot.mcp_stderr"):
            with pytest.raises(B.McpBridgeError):
                _run(_go())

        assert seen.get("errlog") is not None, "stdio_client was called without errlog"
        errors = "\n".join(r.getMessage() for r in caplog.records
                           if r.levelno == logging.ERROR)
        assert MARKER in errors, "the child's stderr was not logged on failure"

    def test_the_spawn_parameters_are_unchanged(self, monkeypatch):
        """This change is diagnostic. Same command, same args, same env."""
        import admz.chatbot.mcp_bridge as B

        captured = {}

        class _FakeCM:
            def __init__(self, params, errlog=None):
                captured["params"] = params

            async def __aenter__(self):
                raise RuntimeError("stop here — the params are what matter")

            async def __aexit__(self, *a):
                return False

        import mcp.client.stdio as real_stdio
        monkeypatch.setattr(real_stdio, "stdio_client",
                            lambda params, errlog=None: _FakeCM(params, errlog))

        async def _go():
            async with B.open_mcp_session(extra_env={"ADMZ_MARKER": MARKER}):
                pass

        with pytest.raises(B.McpBridgeError):
            _run(_go())

        p = captured["params"]
        assert p.command == sys.executable
        assert p.args == ["-m", "admz", "mcp"]
        assert p.env["ADMZ_MARKER"] == MARKER      # extra_env still merged
