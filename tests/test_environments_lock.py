"""`tools/environments.py` compares each environment with a lock (FR-DEP-004).

The lab instance ran a starlette outside its declared bound for three months,
and the page whose whole purpose is to report what each environment really is
could not have said so: it printed three watched versions and compared them
with nothing.

These tests observe no real environment. Each one hands ``lock_state`` a
made-up answer in place of asking an interpreter, so the suite does not depend
on the machine it runs on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import environments as env
from tools import lock as locks

REPO = Path(__file__).resolve().parent.parent

MARKERS = {
    "implementation_name": "cpython", "implementation_version": "3.12.4", "os_name": "nt",
    "platform_machine": "AMD64", "platform_python_implementation": "CPython",
    "platform_release": "11", "platform_system": "Windows", "platform_version": "10.0.26100",
    "python_full_version": "3.12.4", "python_version": "3.12", "sys_platform": "win32",
}


def _exactly(lock_name, root=REPO):
    """What an environment holds when it is that lock and nothing else."""
    pins = locks.read_lock(root / lock_name)
    return {pin.name: [pin.version] for pin in pins if locks.marker_applies(pin.marker, MARKERS)}


def _answers(packages):
    return lambda python: (packages, MARKERS)


@pytest.fixture
def spec(tmp_path):
    """An environment with an interpreter file, and a checkout holding no lock."""
    scripts = tmp_path / "venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_bytes(b"")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    return {"venv": str(tmp_path / "venv"), "checkout": str(checkout)}


def _own_lock(spec, lock_name, text=None):
    """Give the environment's checkout its own copy of a lock."""
    target = Path(spec["checkout"], lock_name)
    target.write_text(text if text is not None else (REPO / lock_name).read_text(encoding="utf-8"),
                      encoding="utf-8")
    return target


# ── which lock, and whose copy ──────────────────────────────────────────────

def test_an_environment_without_test_tools_is_compared_with_the_runtime_lock(spec):
    lines, problems = env.lock_state("lab", spec, ask=_answers(_exactly(locks.RUNTIME_LOCK)))
    assert problems == []
    assert len(lines) == 1 and lines[0].startswith(f"is {locks.RUNTIME_LOCK}")
    assert "nothing else" in lines[0]


def test_an_environment_with_test_tools_is_compared_with_the_dev_lock(spec):
    lines, problems = env.lock_state("dev", spec, ask=_answers(_exactly(locks.DEV_LOCK)))
    assert problems == []
    assert lines[0].startswith(f"is {locks.DEV_LOCK}")


def test_a_checkout_without_a_lock_borrows_this_trees_and_says_so(spec):
    lines, _ = env.lock_state("lab", spec, ask=_answers(_exactly(locks.RUNTIME_LOCK)))
    assert "this tree's copy; its own checkout has none" in lines[0]


def test_a_checkout_with_its_own_lock_is_compared_with_that_one(spec):
    """Its own lock is the commit it runs. This tree's may have moved since."""
    _own_lock(spec, locks.RUNTIME_LOCK, f"attrs==1.0 \\\n    --hash=sha256:{'a' * 64}\n")
    lines, problems = env.lock_state("lab", spec, ask=_answers({"attrs": ["1.0"]}))
    assert problems == []
    assert lines == [f"is {locks.RUNTIME_LOCK}: 1 packages at the pinned versions, nothing else"]
    assert "this tree" not in lines[0]


def test_an_environment_with_no_interpreter_has_nothing_to_compare(tmp_path):
    asked = []
    for venv in (None, str(tmp_path / "missing")):
        got = env.lock_state("staging", {"venv": venv, "checkout": str(tmp_path), "locked": True},
                             ask=lambda python: asked.append(python))
        assert got == ([], []), "the venv line already reports a missing interpreter"
    assert asked == []


# ── an environment that is not declared locked ──────────────────────────────

def _drifted():
    have = _exactly(locks.DEV_LOCK)
    have["starlette"] = ["0.52.1"]
    have["fastapi"] = ["0.129.0"]
    del have["jinja2"]
    have["flask"] = ["3.1.2"]
    return have


def test_differences_are_printed_and_do_not_fail_the_run(spec):
    """A development environment drifts by design. The line is the news."""
    lines, problems = env.lock_state("dev", spec, ask=_answers(_drifted()))
    assert problems == []
    assert lines[0].startswith(f"DIFFERS from {locks.DEV_LOCK}")
    assert "2 at another version, 1 missing, 1 not pinned" in lines[0]
    assert "starlette 0.52.1 is installed; the lock pins 1.3.1" in lines
    assert "flask 3.1.2 is installed, and the lock does not pin it" in lines


def test_a_long_list_is_cut_short_unless_asked_for_in_full(spec):
    have = _exactly(locks.DEV_LOCK)
    moved = sorted(have)[:env.SHOWN_UNLOCKED + 5]
    for name in moved:
        have[name] = ["0.0.0"]
    lines, _ = env.lock_state("dev", spec, ask=_answers(have))
    assert len(lines) == 1 + env.SHOWN_UNLOCKED + 1
    assert lines[-1] == "... and 5 more (--full lists them)"

    lines, _ = env.lock_state("dev", spec, ask=_answers(have), full=True)
    assert len(lines) == 1 + len(moved) and not lines[-1].startswith("...")


def test_packages_that_cannot_be_listed_are_said_and_do_not_fail_an_unlocked_run(spec):
    def broken(python):
        raise locks.LockError("could not ask python what it has installed")

    lines, problems = env.lock_state("dev", spec, ask=broken)
    assert problems == []
    assert lines == ["cannot compare: could not ask python what it has installed"]


# ── an environment declared locked ──────────────────────────────────────────

@pytest.fixture
def locked(spec):
    spec["locked"] = True
    _own_lock(spec, locks.RUNTIME_LOCK)
    return spec


def test_a_locked_environment_that_is_its_lock_has_no_problems(locked):
    lines, problems = env.lock_state("lab", locked, ask=_answers(_exactly(locks.RUNTIME_LOCK)))
    assert problems == []
    assert lines[0].startswith(f"is {locks.RUNTIME_LOCK}:")


def test_every_difference_in_a_locked_environment_fails_the_run(locked):
    have = _exactly(locks.RUNTIME_LOCK)
    have["starlette"] = ["0.52.1"]
    del have["jinja2"]
    have["flask"] = ["3.1.2"]
    lines, problems = env.lock_state("lab", locked, ask=_answers(have))
    assert len(lines) == 1 and lines[0].startswith(f"DIFFERS from {locks.RUNTIME_LOCK}")
    assert problems == [
        f"lab: jinja2 is not installed (the lock pins 3.1.6) ({locks.RUNTIME_LOCK})",
        f"lab: starlette 0.52.1 is installed; the lock pins 1.3.1 ({locks.RUNTIME_LOCK})",
        f"lab: flask 3.1.2 is installed, and the lock does not pin it ({locks.RUNTIME_LOCK})",
    ]


def test_a_locked_environment_is_held_to_the_runtime_lock_even_with_test_tools(locked):
    """A deployment carries no test tools. Finding them must not quietly switch
    the comparison to the lock that allows them."""
    have = _exactly(locks.DEV_LOCK)
    lines, problems = env.lock_state("lab", locked, ask=_answers(have))
    assert lines[0].startswith(f"DIFFERS from {locks.RUNTIME_LOCK}")
    assert any(p.startswith("lab: pytest ") and "does not pin it" in p for p in problems)


def test_a_locked_environment_whose_checkout_has_no_lock_fails_closed(spec):
    """Otherwise it would be compared with this tree's lock, and reported as
    wrong every time a pin moved here before the deployment was upgraded."""
    spec["locked"] = True
    lines, problems = env.lock_state("lab", spec, ask=_answers(_exactly(locks.RUNTIME_LOCK)))
    assert lines[0].startswith(f"is {locks.RUNTIME_LOCK} (this tree's copy")
    assert len(problems) == 1
    assert problems[0].startswith(f"lab: declared locked, but its checkout has no {locks.RUNTIME_LOCK}")


def test_a_locked_environment_whose_packages_cannot_be_listed_fails_closed(locked):
    def broken(python):
        raise locks.LockError("could not ask python what it has installed")

    lines, problems = env.lock_state("lab", locked, ask=broken)
    assert lines[0].startswith("cannot compare")
    assert len(problems) == 1 and "could not be listed" in problems[0]


def test_a_locked_environment_whose_lock_cannot_be_read_fails_closed(locked):
    _own_lock(locked, locks.RUNTIME_LOCK, "-e .\n")
    lines, problems = env.lock_state("lab", locked, ask=_answers({"attrs": ["1.0"]}))
    assert lines[0].startswith(f"cannot compare with {locks.RUNTIME_LOCK}")
    assert len(problems) == 1 and "could not be read" in problems[0]


def test_an_unlocked_environment_with_an_unreadable_lock_is_said_and_does_not_fail(spec):
    _own_lock(spec, locks.RUNTIME_LOCK, "-e .\n")
    lines, problems = env.lock_state("dev", spec, ask=_answers({"attrs": ["1.0"]}))
    assert problems == []
    assert lines[0].startswith(f"cannot compare with {locks.RUNTIME_LOCK}")


# ── the report ──────────────────────────────────────────────────────────────

def test_the_interpreter_is_found_in_either_layout(tmp_path):
    assert env._interpreter(None) is None
    assert env._interpreter(str(tmp_path)) is None
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "python").write_bytes(b"")
    assert env._interpreter(str(tmp_path)) == tmp_path / "bin" / "python"
    (tmp_path / "Scripts").mkdir()
    (tmp_path / "Scripts" / "python.exe").write_bytes(b"")
    assert env._interpreter(str(tmp_path)) == tmp_path / "Scripts" / "python.exe"


def test_an_unknown_argument_is_refused_before_anything_is_observed(monkeypatch, capsys):
    monkeypatch.setattr(env, "load_declaration", lambda: pytest.fail("observed before refusing"))
    assert env.main(["--fulll"]) == 2
    assert "--full" in capsys.readouterr().err


def test_the_report_prints_a_lock_line_and_fails_on_a_locked_difference(monkeypatch, capsys, locked):
    """End to end through ``main``, with every observation replaced."""
    have = _exactly(locks.RUNTIME_LOCK)
    have["starlette"] = ["0.52.1"]
    declared = {"lab": dict(locked, port=None, admz_home=None, atlas="none",
                            expect_listening=False, touch="never")}
    monkeypatch.setattr(env, "load_declaration", lambda: declared)
    monkeypatch.setattr(env, "listening_ports", lambda: {})
    monkeypatch.setattr(env, "checkout_state", lambda path: "abc1234")
    monkeypatch.setattr(env, "venv_state", lambda venv: "present")
    monkeypatch.setattr(env, "atlas_problem", lambda name, venv, kind: None)
    monkeypatch.setattr(env, "audit_launch_configs", lambda roots: [])
    monkeypatch.setattr(env.locks, "installed", _answers(have))

    assert env.main([]) == 1
    out = capsys.readouterr().out
    assert f"    lock       : DIFFERS from {locks.RUNTIME_LOCK}: 1 at another version" in out
    assert f"  ! lab: starlette 0.52.1 is installed; the lock pins 1.3.1 ({locks.RUNTIME_LOCK})" in out

    have["starlette"] = ["1.3.1"]
    assert env.main([]) == 0
    assert f"    lock       : is {locks.RUNTIME_LOCK}:" in capsys.readouterr().out
