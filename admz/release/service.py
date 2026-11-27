"""The Windows service an instance runs as: its state, stopping it, starting it.

One small shape, so the upgrade can be driven in tests by a fake that records
what was asked of it. No test here touches a real service.

``sc.exe`` is used instead of PowerShell or pywin32. It ships with Windows, it
needs nothing from the environment being upgraded, and its exit codes and state
numbers are fixed, where the words around them are translated.

Stopping and starting the lab instance's service needs no elevation. Changing
its definition does, and nothing here does that: an upgrade never edits the
service (FR-DEP-009).
"""

from __future__ import annotations

import re
import subprocess
import time
from typing import Callable, Optional

RUNNING = "running"
STOPPED = "stopped"

#: ``sc.exe query`` prints the state as a number and a constant. The number is
#: what is read; the label before it changes with the display language.
_STATES = {
    "1": STOPPED,
    "2": "start-pending",
    "3": "stop-pending",
    "4": RUNNING,
    "5": "continue-pending",
    "6": "pause-pending",
    "7": "paused",
}
_STATE_LINE = re.compile(
    r":\s*([1-7])\s+(STOPPED|START_PENDING|STOP_PENDING|RUNNING|"
    r"CONTINUE_PENDING|PAUSE_PENDING|PAUSED)\b")
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

#: "The service has not been started", when asked to stop one that is stopped.
_NOT_ACTIVE = 1062
#: "An instance of the service is already running", when asked to start one.
_ALREADY_RUNNING = 1056


class ServiceError(RuntimeError):
    """The service could not be read, or did not reach the state it was asked for."""


class WindowsService:
    """A service by name, through ``sc.exe``."""

    def __init__(self, name: str, *, run: Callable = subprocess.run,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        if not _NAME.match(name or ""):
            raise ServiceError(f"{name!r} is not a service name this command will pass to sc.exe")
        self.name = name
        self._run, self._sleep, self._clock = run, sleep, clock

    def _sc(self, verb: str):
        try:
            return self._run(["sc.exe", verb, self.name],
                             capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ServiceError(f"sc.exe {verb} {self.name} could not be run: {exc}") from exc

    def state(self) -> str:
        done = self._sc("query")
        found = _STATE_LINE.search(done.stdout or "")
        if done.returncode != 0 or not found:
            said = ((done.stdout or "") + (done.stderr or "")).strip().splitlines()
            raise ServiceError(
                f"the state of service {self.name!r} could not be read "
                f"(sc.exe exit {done.returncode}): {said[0] if said else 'no output'}")
        return _STATES[found.group(1)]

    def _wait_for(self, wanted: str, timeout: float) -> None:
        deadline = self._clock() + timeout
        seen: Optional[str] = None
        while True:
            seen = self.state()
            if seen == wanted:
                return
            if self._clock() >= deadline:
                raise ServiceError(
                    f"service {self.name!r} is {seen} after {timeout:.0f}s; it was asked to be {wanted}")
            self._sleep(1.0)

    def stop(self, timeout: float = 60.0) -> None:
        """Stop it and wait until it has stopped. Stopping a stopped service is fine."""
        if self.state() == STOPPED:
            return
        done = self._sc("stop")
        if done.returncode not in (0, _NOT_ACTIVE):
            raise ServiceError(f"sc.exe stop {self.name} failed with exit {done.returncode}")
        self._wait_for(STOPPED, timeout)

    def start(self, timeout: float = 60.0) -> None:
        """Start it and wait until Windows reports it running.

        Running here means the wrapper process is up. Whether the application
        inside it came up is a different question, and the health check asks it.
        """
        done = self._sc("start")
        if done.returncode not in (0, _ALREADY_RUNNING):
            raise ServiceError(f"sc.exe start {self.name} failed with exit {done.returncode}")
        self._wait_for(RUNNING, timeout)
