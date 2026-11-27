"""The Windows service behind one small shape (ADR-0075).

No test here touches a real service. ``sc.exe`` is replaced by a script of
answers, and what was asked of it is recorded.
"""

from __future__ import annotations

import pytest

from admz.release.service import RUNNING, STOPPED, ServiceError, WindowsService

QUERY = """
SERVICE_NAME: admz
        TYPE               : 10  WIN32_OWN_PROCESS
        STATE              : {number}  {word}
                                (STOPPABLE, NOT_PAUSABLE, ACCEPTS_SHUTDOWN)
        WIN32_EXIT_CODE    : 0  (0x0)
"""


class Done:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class Sc:
    """Stands in for sc.exe. ``states`` is what each successive query reports."""

    def __init__(self, states, *, stop_exit=0, start_exit=0):
        self.states = list(states)
        self.stop_exit, self.start_exit = stop_exit, start_exit
        self.asked = []

    def __call__(self, command, **kwargs):
        assert isinstance(command, list) and command[0] == "sc.exe", "never a shell string"
        assert "shell" not in kwargs
        self.asked.append(command[1:])
        verb = command[1]
        if verb == "query":
            number, word = self.states.pop(0) if len(self.states) > 1 else self.states[0]
            return Done(0, QUERY.format(number=number, word=word))
        return Done(self.stop_exit if verb == "stop" else self.start_exit)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def _service(sc, clock=None):
    clock = clock or Clock()
    return WindowsService("admz", run=sc, sleep=clock.sleep, clock=clock)


@pytest.mark.parametrize("number,word,expected", [
    (1, "STOPPED", STOPPED), (2, "START_PENDING", "start-pending"),
    (3, "STOP_PENDING", "stop-pending"), (4, "RUNNING", RUNNING), (7, "PAUSED", "paused"),
])
def test_the_state_is_read_from_the_number(number, word, expected):
    sc = Sc([(number, word)])
    assert _service(sc).state() == expected
    assert sc.asked == [["query", "admz"]]


def test_the_state_is_read_when_the_label_is_in_another_language():
    def sc(command, **kwargs):
        return Done(0, "DIENSTNAME: admz\n        TYP    : 10  WIN32_OWN_PROCESS\n"
                       "        STATUS : 4  RUNNING\n")

    assert WindowsService("admz", run=sc).state() == RUNNING


def test_a_service_that_does_not_exist_is_an_error_with_what_sc_said():
    def sc(command, **kwargs):
        return Done(1060, "[SC] EnumQueryServicesStatus:OpenService FAILED 1060:\n\n"
                          "The specified service does not exist as an installed service.\n")

    with pytest.raises(ServiceError, match="could not be read.*1060.*OpenService FAILED"):
        WindowsService("nope", run=sc).state()


def test_output_with_no_state_in_it_is_an_error_not_a_guess():
    with pytest.raises(ServiceError, match="could not be read"):
        WindowsService("admz", run=lambda command, **kw: Done(0, "something else\n")).state()


def test_sc_that_cannot_be_run_is_an_error():
    def missing(command, **kwargs):
        raise FileNotFoundError("sc.exe")

    with pytest.raises(ServiceError, match="could not be run"):
        WindowsService("admz", run=missing).state()


@pytest.mark.parametrize("name", ["", "admz & calc", "a b", "admz;x", "../admz", "x" * 65, None])
def test_only_a_plain_service_name_reaches_sc(name):
    with pytest.raises(ServiceError, match="not a service name"):
        WindowsService(name, run=lambda *a, **k: pytest.fail("sc.exe was run"))


def test_stop_asks_and_then_waits_until_it_has_stopped():
    sc = Sc([(4, "RUNNING"), (3, "STOP_PENDING"), (3, "STOP_PENDING"), (1, "STOPPED")])
    clock = Clock()
    _service(sc, clock).stop()
    assert sc.asked == [["query", "admz"], ["stop", "admz"],
                        ["query", "admz"], ["query", "admz"], ["query", "admz"]]
    assert clock.now == 2.0, "it waited between questions instead of spinning"


def test_stopping_a_stopped_service_asks_nothing_of_it():
    sc = Sc([(1, "STOPPED")])
    _service(sc).stop()
    assert sc.asked == [["query", "admz"]]


def test_a_service_that_stopped_by_itself_in_between_is_fine():
    sc = Sc([(4, "RUNNING"), (1, "STOPPED")], stop_exit=1062)
    _service(sc).stop()


def test_a_refused_stop_is_an_error():
    sc = Sc([(4, "RUNNING")], stop_exit=5)
    with pytest.raises(ServiceError, match="sc.exe stop admz failed with exit 5"):
        _service(sc).stop()


def test_a_service_that_never_stops_is_an_error_naming_where_it_is_stuck():
    sc = Sc([(4, "RUNNING"), (3, "STOP_PENDING")])
    clock = Clock()
    with pytest.raises(ServiceError, match="is stop-pending after 30s; it was asked to be stopped"):
        _service(sc, clock).stop(timeout=30)
    assert 30 <= clock.now <= 31, "it gave up when the time it was given had passed"


def test_start_asks_and_then_waits_until_it_is_running():
    sc = Sc([(2, "START_PENDING"), (4, "RUNNING")])
    _service(sc).start()
    assert sc.asked == [["start", "admz"], ["query", "admz"], ["query", "admz"]]


def test_starting_a_service_that_is_already_running_is_fine():
    sc = Sc([(4, "RUNNING")], start_exit=1056)
    _service(sc).start()


def test_a_refused_start_is_an_error():
    sc = Sc([(1, "STOPPED")], start_exit=5)
    with pytest.raises(ServiceError, match="sc.exe start admz failed with exit 5"):
        _service(sc).start()


def test_a_service_that_starts_and_falls_over_is_an_error():
    sc = Sc([(2, "START_PENDING"), (1, "STOPPED")])
    with pytest.raises(ServiceError, match="is stopped after 20s; it was asked to be running"):
        _service(sc).start(timeout=20)
