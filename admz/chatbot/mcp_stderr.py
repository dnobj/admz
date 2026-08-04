"""Bridge the MCP subprocess's stderr into the ADMZ log (#296 — diagnostic).

``stdio_client(params)`` defaults ``errlog`` to the **parent's** ``sys.stderr``.
That is not "nowhere", but on the reference deployment it may as well be: ADMZ
runs as a Shawl-supervised Windows service under LocalSystem with no console, so
the parent's ``sys.stderr`` is whatever Shawl attached — not the ADMZ log the
operator actually reads. When the subprocess dies mid-``list_tools()`` the
traceback that would explain it lands somewhere nobody looks.

**Why this is a pipe and not a logger shim.** ``errlog`` is not a Python-level
sink: ``mcp/client/stdio.py`` passes it straight to
``anyio.open_process(..., stderr=errlog)`` on both the POSIX and Windows paths.
It therefore has to be a real OS-level file with a ``fileno()``; a
``TextIOBase`` subclass that merely implements ``write()`` would break the spawn
rather than capture anything. So we hand the child one end of an ``os.pipe()``
and pump the other end into ``logging`` from a reader thread.

**Levels, deliberately split.** The child is an ADMZ process whose own root
handler is a ``StreamHandler`` on stderr, so this stream carries its ordinary
INFO log as well as any crash. Promoting all of that to WARNING would misreport
routine startup as a problem; leaving a crash at INFO would hide it from anyone
running at WARNING. So: each line is relayed at **INFO**, and a bounded tail is
kept so the *caller* can re-emit it at **ERROR** when the session actually fails.
The diagnostic case is loud without the routine case being noisy.

**On secrets** (checked, not assumed): the child writes its ADMZ log here, whose
default level is INFO. A grep of ``logger.info/warning/error`` calls across
``admz/`` for password/secret/token/api_key arguments returns one hit —
``github_app/push.py:46``, which logs a token-mint *failure message*, not a
token. Python tracebacks do not include local variables. So nothing routinely
written to this stream is sensitive; that is a property of today's call sites,
not a guarantee, which is why the tail is bounded and prefixed rather than
mirrored verbatim into an unrelated sink.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import deque
from typing import Deque, List, Optional, TextIO

logger = logging.getLogger(__name__)

#: Lines of child stderr retained for the failure path. Bounded because this is
#: a diagnostic buffer held for the life of a chat session, not a log.
TAIL_LINES = 60

#: How long :meth:`StderrPump.close` waits for the reader to drain after the
#: write end is closed. The reader is at EOF by then, so this is a deadlock
#: backstop, not a timing assumption.
JOIN_TIMEOUT_SECONDS = 5.0


class StderrPump:
    """Owns an ``os.pipe()`` whose write end is handed to ``errlog``.

    Not reusable: one pump per spawned subprocess. Always close it — the reader
    thread only sees EOF once **every** copy of the write end is closed, and
    this process holds one.
    """

    def __init__(self, *, prefix: str = "mcp-subprocess",
                 tail_lines: int = TAIL_LINES) -> None:
        self._prefix = prefix
        self._tail: Deque[str] = deque(maxlen=tail_lines)
        self._closed = False
        read_fd, write_fd = os.pipe()
        # errors="replace": a half-written multibyte char at the moment the
        # child dies must not raise inside the reader and lose the traceback.
        self._writer: TextIO = os.fdopen(write_fd, "w", encoding="utf-8",
                                         errors="replace", buffering=1)
        self._reader: TextIO = os.fdopen(read_fd, "r", encoding="utf-8",
                                         errors="replace")
        self._thread = threading.Thread(
            target=self._pump, name="mcp-stderr-pump", daemon=True)
        self._thread.start()

    @property
    def writer(self) -> TextIO:
        """The file object to pass as ``stdio_client(..., errlog=...)``."""
        return self._writer

    def _pump(self) -> None:
        try:
            for line in self._reader:          # blocks until EOF
                # Per-line handling is guarded INSIDE the loop, deliberately.
                # If a logging failure could break out of the drain, the pipe
                # would fill (~64 KB) and the child would then BLOCK writing to
                # stderr — turning a diagnostic aid into a new way to hang the
                # subprocess. The old code path could not hang, and this one
                # must not either: keep draining no matter what.
                try:
                    text = line.rstrip("\r\n")
                    if not text:
                        continue
                    self._tail.append(text)
                    logger.info("[%s] %s", self._prefix, text)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001 — reader died; nothing left to drain
            logger.debug("MCP stderr pump stopped early", exc_info=True)
        finally:
            try:
                self._reader.close()
            except Exception:  # noqa: BLE001
                pass

    def tail(self) -> List[str]:
        """The most recent lines seen, oldest first."""
        return list(self._tail)

    def close(self, *, timeout: float = JOIN_TIMEOUT_SECONDS) -> List[str]:
        """Close the write end, drain the reader, and return the tail.

        Closing is what produces EOF, and draining before returning is what
        makes a dying child's traceback usable: it is written and the process
        exits, so without the join the caller can read an empty tail purely
        because the reader thread had not been scheduled yet.
        """
        if not self._closed:
            self._closed = True
            try:
                self._writer.flush()
            except Exception:  # noqa: BLE001
                pass
            try:
                self._writer.close()
            except Exception:  # noqa: BLE001
                pass
        if self._thread.is_alive():
            self._thread.join(timeout=timeout)
        return self.tail()


def log_tail(tail: List[str], *, reason: str,
             log: Optional[logging.Logger] = None) -> None:
    """Re-emit a captured tail at ERROR, for when the session actually failed.

    Separate from the INFO relay on purpose: this is the copy that survives an
    operator running at WARNING, which is the case #296 exists to serve.
    """
    out = log or logger
    if not tail:
        out.error("%s — the subprocess wrote nothing to stderr.", reason)
        return
    out.error("%s — last %d line(s) of subprocess stderr:\n%s",
              reason, len(tail), "\n".join(tail))
