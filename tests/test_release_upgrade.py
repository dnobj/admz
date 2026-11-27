"""The upgrade of an instance: the order of the steps, and the way back.

No test here stops a real service, asks a real instance, or opens a real data
folder. ``World`` stands in for the tree, the service and the instance behind
the port, and records everything that was asked of it. The end-to-end tests at
the bottom use real git against temporary repositories, a stub service, and a
data folder made for the test.

The property the whole command exists for is stated twice below and worth
finding first: ``test_nothing_is_changed_when_a_check_fails`` and
``test_every_failure_after_the_switch_goes_back``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from admz.release import backup as backups
from admz.release import deploylog, health, upgrade, walk
from admz.release.service import ServiceError

REPO = Path(__file__).resolve().parent.parent
A, B, C = "a" * 40, "b" * 40, "c" * 40
PIN = "6" * 40
GOOD_WALK = walk.WalkResult(["admz", "admz.api", "admz.api.main"], [])


@pytest.fixture
def home(tmp_path):
    """A data folder that looks like an instance's: a database and a key."""
    folder = tmp_path / "data"
    folder.mkdir()
    conn = sqlite3.connect(str(folder / backups.DB_NAME))
    conn.execute("CREATE TABLE devices (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO devices (name) VALUES ('cam-1')")
    conn.commit()
    conn.close()
    (folder / backups.KEY_NAME).write_bytes(b"k" * 44)
    return folder


class World:
    """The tree, the service and the instance behind the port, as one fake."""

    def __init__(self, home, tree="C:/instance"):
        self.home, self.tree = home, Path(tree)
        self.head = A                      # where the tree is
        self.serving = A                   # the commit the running service loaded
        self.state_now = "running"
        self.dirty = ""
        self.known = {A, B}
        self.ahead = {(A, B)}              # (older, newer) pairs
        self.pins = {A: PIN, B: PIN}
        self.lock = []                     # differences from the target's lock; None = no lock
        self.walked = GOOD_WALK
        self.never_healthy = set()         # commits that do not come up
        self.sick_after_stop = set()       # commits that ran fine until the service was stopped
        self.reports = {}                  # commit -> the build it claims, when it lies
        self.fail = {}                     # "stop" / "start" / "checkout:<commit>" -> exception
        self.did = []                      # what was done, in order
        self.said = []
        self.logged = []
        self.backups = []

    # git ------------------------------------------------------------------
    def git(self, tree, *args):
        assert Path(tree) == self.tree, "git is only ever run in the instance's tree"
        if args == ("rev-parse", "HEAD"):
            return self.head
        if args == ("status", "--porcelain"):
            return self.dirty
        if args[0] == "cat-file":
            if args[2].split("^")[0] not in self.known:
                raise upgrade.GitError("fatal: not a valid object name")
            return ""
        if args[0] == "merge-base":
            if (args[2], args[3]) not in self.ahead:
                raise upgrade.GitError("git merge-base failed: exit 1")
            return ""
        if args[0] == "show":
            pin = self.pins.get(args[1].split(":")[0])
            return f'ATLAS_SHA = "{pin}"\n' if pin else "# no pin here\n"
        if args[0] == "checkout":
            commit = args[-1]
            self.did.append("checkout " + " ".join(a for a in args[1:-1] if a != "--quiet")
                            + " " + commit[:1])
            self._maybe_fail("checkout:" + commit)
            self.head = commit
            return ""
        raise AssertionError(f"unexpected git {args}")

    def _maybe_fail(self, what):
        failure = self.fail.get(what)
        if isinstance(failure, list):
            failure = failure.pop(0) if failure else None
        if failure:
            raise failure

    # the service ----------------------------------------------------------
    def state(self):
        if isinstance(self.state_now, Exception):
            raise self.state_now
        return self.state_now

    def stop(self):
        self.did.append("stop")
        self._maybe_fail("stop")
        self.state_now = "stopped"
        self.never_healthy |= self.sick_after_stop

    def start(self):
        self.did.append("start")
        self._maybe_fail("start")
        self.state_now, self.serving = "running", self.head

    # the instance behind the port -----------------------------------------
    def probe(self):
        if self.state_now != "running":
            raise health.HealthError("connection refused")
        if self.serving in self.never_healthy:
            raise health.HealthError("status 'starting'")
        return {"status": "healthy", "build": self.reports.get(self.serving, self.serving[:7])}

    def wait_healthy(self):
        self.did.append("wait")
        self._maybe_fail("wait")
        try:
            return self.probe()
        except health.HealthError as exc:
            raise health.HealthError(f"not healthy within 90s: {exc}") from exc

    # the rest ---------------------------------------------------------------
    def back_up(self, label):
        self.did.append("backup")
        self._maybe_fail("backup")
        taken = backups.Backup(folder=self.home / "backups" / label, files=[{"name": "admz.db"}])
        self.backups.append(taken)
        return taken

    def log(self, **fields):
        self._maybe_fail("log")
        self.logged.append(fields)
        return fields

    def hands(self):
        return upgrade.Hands(
            git=self.git, service=self, probe=self.probe, wait_healthy=self.wait_healthy,
            walk=lambda: self.walked, lock_differences=lambda: self.lock,
            back_up=self.back_up, log=self.log)

    def run(self, **changes):
        req = upgrade.Request(tree=self.tree, home=self.home, source=A, target=B, port=4242,
                              **changes)
        ticks = iter(range(0, 10_000, 4))
        return upgrade.upgrade(req, self.hands(), say=self.said.append, clock=lambda: next(ticks))

    @property
    def text(self):
        return "\n".join(self.said)


@pytest.fixture
def world(home):
    return World(home)


# ── the upgrade that works ──────────────────────────────────────────────────

def test_an_upgrade_backs_up_stops_switches_starts_and_waits(world):
    assert world.run() == upgrade.OK
    assert world.did == ["backup", "stop", "checkout --detach b", "start", "wait"], (
        "the copy is taken while the instance still runs, and the tree is only "
        "switched while it is stopped")
    assert world.head == B and world.serving == B and world.state_now == "running"
    assert "Upgraded. The instance is healthy on build bbbbbbb." in world.text


def test_a_successful_upgrade_leaves_one_line_in_the_deploy_log(world):
    world.run()
    assert len(world.logged) == 1
    record = world.logged[0]
    assert (record["action"], record["outcome"], record["source"], record["target"]) == (
        "upgrade", "ok", A, B)
    assert record["backup"] == str(world.home / "backups" / "aaaaaaa-to-bbbbbbb")
    assert record["tree"] == str(world.tree) and record["seconds"] > 0


def test_each_check_is_said_as_it_passes(world):
    world.run()
    for line in ("the tree is clean at aaaaaaa, and bbbbbbb is ahead of it",
                 "the catalog pin does not move (6666666)",
                 "the installed packages are exactly bbbbbbb's requirements.lock",
                 "the service is running, and healthy on build aaaaaaa",
                 "3 modules of bbbbbbb import on the instance's interpreter",
                 "database and key copied to"):
        assert any(line in said for said in world.said), line


def test_a_target_from_before_the_locks_is_upgraded_with_a_note(world):
    world.lock = None
    assert world.run() == upgrade.OK
    assert "carries no requirements.lock; installed packages were not compared" in world.text


def test_a_service_account_that_cannot_ask_git_is_normal(world):
    world.reports = {A: "aaaaaaa-unverified", B: "bbbbbbb-unverified"}
    assert world.run() == upgrade.OK


# ── checks that refuse, before anything is changed ──────────────────────────

def _moved(w):
    w.head = C
    w.known.add(C)


def _already(w):
    w.head = B


REFUSALS = {
    "the tree moved since the upgrade was prepared": (_moved, "Something moved it in between"),
    "the tree has local changes": (
        lambda w: setattr(w, "dirty", " M admz/api/main.py\n?? notes.txt"),
        "has 2 local change(s), such as 'M admz/api/main.py'"),
    "the target is not in the clone": (lambda w: w.known.discard(B), "not a valid object name"),
    "the target is not ahead": (lambda w: w.ahead.clear(), "is not ahead of aaaaaaa"),
    "the catalog pin moves": (
        lambda w: w.pins.update({B: "7" * 40}),
        "the catalog pin moves from 6666666 to 7777777"),
    "the target drops the catalog pin": (lambda w: w.pins.pop(B), "from 6666666 to none"),
    "the packages are not the lock": (
        lambda w: setattr(w, "lock", [f"pkg-{n} 1.0 is installed; the lock pins 2.0" for n in range(7)]),
        "(7 difference(s)): pkg-0 1.0 is installed; the lock pins 2.0"),
    "the service is stopped": (lambda w: setattr(w, "state_now", "stopped"), "the service is stopped, not running"),
    "the service cannot be read": (
        lambda w: setattr(w, "state_now", ServiceError("the state of service 'admz' could not be read")),
        "could not be read"),
    "the instance is not healthy": (
        lambda w: w.never_healthy.add(A), "is not healthy before the upgrade"),
    "another instance answers on the port": (
        lambda w: w.reports.update({A: "ccccccc"}),
        "reports build 'ccccccc', and this tree is at aaaaaaa"),
    "the running code was edited in place": (
        lambda w: w.reports.update({A: "aaaaaaa-dirty"}), "reports build 'aaaaaaa-dirty'"),
    "a module does not import": (
        lambda w: setattr(w, "walked", walk.WalkResult(
            ["admz"], [("admz.mcp.server", "AttributeError: no attribute 'list_tools'")])),
        "1 module(s) of bbbbbbb do not import on the instance's interpreter: "
        "admz.mcp.server: AttributeError"),
    "the walk imported nothing": (
        lambda w: setattr(w, "walked", walk.WalkResult([], [])), "nothing was imported"),
    "the backup fails": (
        lambda w: w.fail.update({"backup": backups.BackupError("disk full")}),
        "the backup failed: disk full"),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_nothing_is_changed_when_a_check_fails(world, case):
    """Every refusal, one property: the tree, the service and the instance are
    exactly as they were, and the log says why."""
    break_it, said = REFUSALS[case]
    break_it(world)
    before = (world.head, world.serving, world.state_now)

    assert world.run() == upgrade.REFUSED

    assert (world.head, world.serving, world.state_now) == before
    assert [step for step in world.did if step != "backup"] == [], (
        "the service was not stopped or started, and the tree was not switched")
    assert "REFUSED, and nothing was changed" in world.text and said in world.text
    assert [r["outcome"] for r in world.logged] == ["refused"]
    assert said in world.logged[0]["detail"]
    assert world.logged[0]["backup"] is None


def test_an_upgrade_to_where_the_tree_already_is_is_refused(world):
    _already(world)
    req = upgrade.Request(tree=world.tree, home=world.home, source=B, target=B, port=4242)
    assert upgrade.upgrade(req, world.hands(), say=world.said.append) == upgrade.REFUSED
    assert "the tree is already at bbbbbbb" in world.text and world.did == []


def test_the_walk_that_cannot_run_refuses(world):
    def broken():
        raise walk.WalkError("the import walk refused to run: ADMZ_HOME is not set")

    hands = world.hands()
    hands.walk = broken
    req = upgrade.Request(tree=world.tree, home=world.home, source=A, target=B, port=4242)
    assert upgrade.upgrade(req, hands, say=world.said.append) == upgrade.REFUSED
    assert "refused to run" in world.text and world.did == []


def test_a_long_list_of_package_differences_is_cut_short_with_a_count(world):
    world.lock = [f"pkg-{n} differs" for n in range(7)]
    world.run()
    assert "pkg-4 differs; and 2 more" in world.text and "pkg-5" not in world.text


@pytest.mark.parametrize("make", [
    lambda home: home / "typo",                         # does not exist
    lambda home: home.parent,                           # exists, and is not a data folder
])
def test_a_folder_that_is_not_the_instances_data_gets_no_log(world, make):
    """A mistyped ``--home`` must not gain a ``deployed.log``."""
    world.home = make(world.home)
    assert world.run() == upgrade.REFUSED
    assert "holds no admz.db; that is not this instance's data folder" in world.text
    assert world.logged == [] and world.did == []


# ── --check ─────────────────────────────────────────────────────────────────

def test_check_runs_every_check_and_changes_nothing(world):
    assert world.run(check_only=True) == upgrade.OK
    assert world.did == [] and world.logged == [] and world.backups == []
    assert "Every check passed. Nothing was changed, and nothing was written." in world.text
    assert "3 modules of bbbbbbb import" in world.text


def test_a_failed_check_is_reported_and_still_writes_nothing(world):
    world.dirty = " M setup.py"
    assert world.run(check_only=True) == upgrade.REFUSED
    assert world.did == [] and world.logged == []


# ── failures after the switch began: the way back ───────────────────────────

FAILURES = {
    "the service will not stop": (
        lambda w: w.fail.update({"stop": [ServiceError("is stop-pending after 60s")]}),
        "is stop-pending after 60s"),
    "the checkout fails": (
        lambda w: w.fail.update({"checkout:" + B: upgrade.GitError("unable to unlink old file")}),
        "unable to unlink old file"),
    "the service will not start": (
        lambda w: w.fail.update({"start": [ServiceError("sc.exe start admz failed with exit 5")]}),
        "failed with exit 5"),
    "the new build never becomes healthy": (
        lambda w: w.never_healthy.add(B), "not healthy within 90s"),
    "the instance comes up on the wrong build": (
        lambda w: w.reports.update({B: "aaaaaaa"}),
        "healthy but reports build 'aaaaaaa', not bbbbbbb"),
    "the new build was edited in place": (
        lambda w: w.reports.update({B: "bbbbbbb-dirty"}), "reports build 'bbbbbbb-dirty'"),
    "the operator presses ctrl-c while it waits": (
        lambda w: w.fail.update({"wait": [KeyboardInterrupt()]}), "interrupted from the keyboard"),
    "something nobody expected": (
        lambda w: w.fail.update({"start": [RuntimeError("a bug in this command")]}),
        "a bug in this command"),
}


@pytest.mark.parametrize("case", sorted(FAILURES))
def test_every_failure_after_the_switch_goes_back(world, case):
    """Whatever breaks once the service has been touched, the instance ends up
    running the old commit again, healthy, and the log says what happened."""
    break_it, said = FAILURES[case]
    break_it(world)

    assert world.run() == upgrade.ROLLED_BACK

    assert world.head == A and world.serving == A and world.state_now == "running"
    assert "checkout --force --detach a" in world.did
    assert world.did[-2:] == ["start", "wait"], "the old build was started and asked"
    assert f"FAILED after the switch began: " in world.text and said in world.text
    assert "Rolled back. The instance is healthy on aaaaaaa again." in world.text
    assert [r["outcome"] for r in world.logged] == ["rolled-back"]
    assert said in world.logged[0]["detail"]
    assert world.logged[0]["backup"], "the log names the copy that was taken first"


def test_only_the_way_back_forces_the_checkout(world):
    """Going forward the tree is known to be clean, and a checkout that would
    overwrite something must fail. Going back, whatever is in the way is debris
    of the failed switch."""
    world.never_healthy.add(B)
    world.run()
    checkouts = [step for step in world.did if step.startswith("checkout")]
    assert checkouts == ["checkout --detach b", "checkout --force --detach a"]


def test_an_unexpected_error_is_shown_in_full_before_going_back(world):
    world.fail["start"] = [RuntimeError("a bug in this command")]
    world.run()
    assert "Traceback" in world.text and "RuntimeError: a bug in this command" in world.text


def test_a_service_that_will_not_stop_cleanly_does_not_block_the_way_back(world):
    """The first stop fails, which is why we are going back. The second fails
    too. The old code is still put in place and started."""
    world.fail["stop"] = [ServiceError("timeout"), ServiceError("still stuck")]
    assert world.run() == upgrade.ROLLED_BACK
    assert "the service did not stop cleanly (still stuck); carrying on" in world.text
    assert world.head == A and world.serving == A


# ── the way back fails too ──────────────────────────────────────────────────

ROLLBACK_FAILURES = {
    "the old build does not come up either": lambda w: (
        w.never_healthy.add(B), w.sick_after_stop.add(A)),
    "the service will not start again": lambda w: (
        w.never_healthy.add(B), w.fail.update({"start": [None, ServiceError("exit 1053")]})),
    "the old commit cannot be checked out": lambda w: (
        w.never_healthy.add(B), w.fail.update({"checkout:" + A: upgrade.GitError("index locked")})),
    "the operator presses ctrl-c during the rollback": lambda w: (
        w.never_healthy.add(B), w.fail.update({"wait": [None, KeyboardInterrupt()]})),
}


@pytest.mark.parametrize("case", sorted(ROLLBACK_FAILURES))
def test_a_failed_rollback_is_loud_and_says_what_to_do(world, case):
    ROLLBACK_FAILURES[case](world)

    assert world.run() == upgrade.ROLLBACK_FAILED

    assert "THE ROLLBACK FAILED. The instance is not known to be running." in world.text
    assert f"by hand: put {world.tree} at {A}" in world.text
    assert str(world.backups[0].folder) in world.text, "where the copy of the database is"
    assert [r["outcome"] for r in world.logged] == ["rollback-failed"]
    assert "then the rollback failed" in world.logged[0]["detail"]


def test_the_exit_codes_tell_the_four_endings_apart():
    assert len({upgrade.OK, upgrade.ROLLED_BACK, upgrade.REFUSED, upgrade.ROLLBACK_FAILED}) == 4
    assert upgrade.OK == 0


def test_a_log_that_cannot_be_written_does_not_change_how_it_ended(world):
    world.fail["log"] = OSError("access denied")
    assert world.run() == upgrade.OK
    assert "the deploy log could not be written: access denied" in world.text
    world.fail["log"] = OSError("access denied")
    world.head = world.serving = A
    world.never_healthy.add(B)
    assert world.run() == upgrade.ROLLED_BACK


# ── small pieces ────────────────────────────────────────────────────────────

def test_the_catalog_pin_is_read_from_setup_py_at_a_commit():
    asked = []

    def run_git(tree, *args):
        asked.append(args)
        return 'import os\nATLAS_SHA = "635C395D1AFBAAC9BD89ED22324EF2D91B5E6C88"\n'

    assert upgrade.catalog_pin(run_git, Path("t"), A) == "635c395d1afbaac9bd89ed22324ef2d91b5e6c88"
    assert asked == [("show", f"{A}:setup.py")]


def test_a_commit_without_a_pin_or_without_setup_py_has_none():
    def missing(tree, *args):
        raise upgrade.GitError("path 'setup.py' does not exist")

    assert upgrade.catalog_pin(lambda tree, *a: "ATLAS_SHA = 'short'\n", Path("t"), A) is None
    assert upgrade.catalog_pin(missing, Path("t"), A) is None


def test_git_returns_what_was_printed_and_raises_with_gits_last_line(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert upgrade.git(tmp_path, "rev-parse", "--is-inside-work-tree") == "true"
    with pytest.raises(upgrade.GitError, match="git rev-parse --verify nope failed in"):
        upgrade.git(tmp_path, "rev-parse", "--verify", "nope")


def test_the_instances_interpreter_is_found_in_its_tree(tmp_path):
    assert upgrade.instance_python(tmp_path) is None
    scripts = tmp_path / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_bytes(b"")
    assert upgrade.instance_python(tmp_path) == scripts / "python.exe"


# ── comparing with the target's lock ────────────────────────────────────────

LOCK_LINE = "attrs==0.0.1 \\\n    --hash=sha256:" + "a" * 64 + "\n"


def _checkout(tmp_path, lock_text=LOCK_LINE, with_tool=True):
    checkout = tmp_path / "checkout"
    (checkout / "tools").mkdir(parents=True)
    if lock_text is not None:
        (checkout / upgrade.LOCK_NAME).write_text(lock_text, encoding="utf-8")
    if with_tool:
        shutil.copy(REPO / "tools" / "lock.py", checkout / "tools" / "lock.py")
    return checkout


def test_a_checkout_without_a_lock_has_nothing_to_compare(tmp_path):
    assert upgrade.lock_differences(_checkout(tmp_path, lock_text=None)) is None


def test_the_comparison_is_made_with_the_targets_own_tool(tmp_path):
    """This interpreter is asked what it holds, and the answer is compared with
    a lock that pins one package at a version nobody has."""
    found = upgrade.lock_differences(_checkout(tmp_path))
    assert any(line.startswith("attrs ") and "the lock pins 0.0.1" in line for line in found)
    assert any("pytest" in line and "does not pin it" in line for line in found)


def test_a_lock_with_no_tool_to_read_it_refuses(tmp_path):
    with pytest.raises(upgrade.Refused, match="no tools/lock.py to read it with"):
        upgrade.lock_differences(_checkout(tmp_path, with_tool=False))


def test_a_lock_that_cannot_be_read_refuses(tmp_path):
    with pytest.raises(upgrade.Refused, match="could not be compared"):
        upgrade.lock_differences(_checkout(tmp_path, lock_text="-e .\n"))


def test_an_interpreter_that_cannot_be_asked_refuses(tmp_path):
    with pytest.raises(upgrade.Refused, match="could not be compared"):
        upgrade.lock_differences(_checkout(tmp_path), python=tmp_path / "no-python.exe")


# ── stage 2 ─────────────────────────────────────────────────────────────────

def _parse(argv):
    parser = argparse.ArgumentParser()
    upgrade.add_arguments(parser)
    return parser.parse_args(argv)


def _stage2_args(world, *extra):
    return _parse(["--stage2", "--tree", str(world.tree), "--home", str(world.home),
                   "--to", B, "--from", A, "--port", "4250", "--within", "30",
                   "--service", "admz-lab", *extra])


def test_stage_two_builds_the_request_from_what_stage_one_passed(world):
    seen = {}

    def make_hands(req, **kwargs):
        seen["req"], seen["kwargs"] = req, kwargs
        return world.hands()

    code = upgrade.stage2(_stage2_args(world), say=world.said.append, make_hands=make_hands,
                          run_git=lambda tree, *args: B, here=REPO)
    assert code == upgrade.OK and world.head == B
    assert seen["req"] == upgrade.Request(tree=world.tree, home=world.home, source=A, target=B,
                                          port=4250, check_only=False)
    assert seen["kwargs"] == {"service_name": "admz-lab", "within": 30.0, "checkout": REPO}


def test_stage_two_passes_check_through(world):
    code = upgrade.stage2(_stage2_args(world, "--check"), say=world.said.append,
                          make_hands=lambda req, **kw: world.hands(),
                          run_git=lambda tree, *args: B, here=REPO)
    assert code == upgrade.OK and world.did == [] and world.head == A


def test_stage_two_refuses_to_run_from_a_checkout_of_another_commit(world):
    """If the import path had found the instance's own tree, the old code would
    be checking the new commit."""
    code = upgrade.stage2(_stage2_args(world), say=world.said.append,
                          make_hands=lambda req, **kw: pytest.fail("hands were made"),
                          run_git=lambda tree, *args: C, here=REPO)
    assert code == upgrade.REFUSED
    assert "stage 2 must run from a checkout of the target commit" in world.text


def test_stage_two_refuses_when_its_code_is_not_in_that_checkout(world, tmp_path):
    code = upgrade.stage2(_stage2_args(world), say=world.said.append,
                          make_hands=lambda req, **kw: pytest.fail("hands were made"),
                          run_git=lambda tree, *args: B, here=tmp_path)
    assert code == upgrade.REFUSED and world.did == []


def test_stage_two_refuses_outside_a_checkout(world, tmp_path):
    def run_git(tree, *args):
        raise upgrade.GitError("not a git repository")

    code = upgrade.stage2(_stage2_args(world), say=world.said.append, run_git=run_git, here=tmp_path)
    assert code == upgrade.REFUSED and "not running in a checkout" in world.text


def test_stage_two_refuses_a_service_name_it_will_not_pass_on(world):
    args = _stage2_args(world)
    args.service = "admz & calc"
    code = upgrade.stage2(args, say=world.said.append, run_git=lambda tree, *a: B, here=REPO)
    assert code == upgrade.REFUSED and "not a service name" in world.text


def test_stage_two_without_where_it_came_from_is_refused(capsys):
    args = _parse(["--stage2", "--tree", "t", "--home", "h", "--to", B])
    assert upgrade.main(args) == upgrade.REFUSED
    assert "without --from" in capsys.readouterr().out


def test_the_real_hands_point_at_this_instance_and_no_other(world, monkeypatch, tmp_path):
    req = upgrade.Request(tree=world.tree, home=world.home, source=A, target=B, port=4250)
    calls = []
    monkeypatch.setattr(upgrade.health, "probe", lambda port: calls.append(("probe", port)) or {})
    monkeypatch.setattr(upgrade.health, "wait_healthy",
                        lambda port, within: calls.append(("wait", port, within)) or {})
    monkeypatch.setattr(upgrade.walk, "run",
                        lambda python, source: calls.append(("walk", python, source)) or GOOD_WALK)
    monkeypatch.setattr(upgrade.backups, "back_up",
                        lambda home, label: calls.append(("backup", home, label)))
    monkeypatch.setattr(upgrade.deploylog, "append",
                        lambda home, **fields: calls.append(("log", home, fields)) or fields)
    monkeypatch.setattr(upgrade, "lock_differences", lambda checkout: calls.append(("lock", checkout)) or [])

    hands = upgrade.real_hands(req, service_name="admz-lab", within=45.0, checkout=tmp_path)
    hands.probe(), hands.wait_healthy(), hands.walk(), hands.lock_differences()
    hands.back_up("label"), hands.log(outcome="ok")
    assert calls == [
        ("probe", 4250), ("wait", 4250, 45.0),
        ("walk", Path(sys.executable), tmp_path), ("lock", tmp_path),
        ("backup", world.home, "label"), ("log", world.home, {"outcome": "ok"}),
    ]
    assert hands.service.name == "admz-lab" and hands.git is upgrade.git


# ── stage 1 and the whole thing, with real git ──────────────────────────────

def _git(cwd, *args):
    done = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
        cwd=str(cwd), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _commit(work, marker):
    (work / "setup.py").write_text(f'ATLAS_SHA = "{PIN}"\n', encoding="utf-8")
    (work / "marker.txt").write_text(marker, encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", marker)
    return _git(work, "rev-parse", "HEAD")


@pytest.fixture
def repos(tmp_path):
    """An origin with two commits, and an instance tree cloned at the first."""
    origin, work, tree = tmp_path / "origin.git", tmp_path / "work", tmp_path / "instance"
    _git(tmp_path, "init", "-q", "--bare", "-b", "master", str(origin))
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    first = _commit(work, "one")
    _git(work, "push", "-q", "origin", "HEAD:master")
    _git(tmp_path, "clone", "-q", str(origin), str(tree))
    _git(tree, "checkout", "-q", "--detach", first)
    second = _commit(work, "two")
    _git(work, "push", "-q", "origin", "HEAD:master")       # the tree has not fetched this
    interpreter = tree / ".venv" / "Scripts"
    interpreter.mkdir(parents=True)
    (interpreter / "python.exe").write_bytes(b"")
    (tree / ".git" / "info" / "exclude").write_text(".venv/\n", encoding="utf-8")
    return {"tree": tree, "work": work, "first": first, "second": second}


class StubInstance:
    """A service and an instance whose build is whatever the tree held at start."""

    def __init__(self, tree, never_healthy=()):
        self.tree, self.never_healthy = tree, set(never_healthy)
        self.state_now = "running"
        self.serving = _git(tree, "rev-parse", "HEAD")
        self.did = []

    def state(self):
        return self.state_now

    def stop(self):
        self.did.append("stop")
        self.state_now = "stopped"

    def start(self):
        self.did.append("start")
        self.state_now, self.serving = "running", _git(self.tree, "rev-parse", "HEAD")

    def probe(self):
        if self.state_now != "running" or self.serving in self.never_healthy:
            raise health.HealthError("not healthy")
        return {"status": "healthy", "build": self.serving[:7]}


def _end_to_end(repos, home, *extra, never_healthy=(), said=None):
    """Stage 1 for real, handing over to the real orchestration in this process."""
    said = said if said is not None else []
    instance = StubInstance(repos["tree"], never_healthy)
    seen = {}

    def start(python, checkout, argv):
        seen["python"], seen["checkout"], seen["argv"] = python, checkout, argv
        seen["checkout_head"] = _git(checkout, "rev-parse", "HEAD")
        seen["checkout_marker"] = (checkout / "marker.txt").read_text(encoding="utf-8")
        args = _parse(["--stage2", *argv])
        req = upgrade.Request(tree=Path(args.tree), home=Path(args.home), source=args.source,
                              target=args.to, port=args.port, check_only=args.check)
        hands = upgrade.Hands(
            git=upgrade.git, service=instance, probe=instance.probe, wait_healthy=instance.probe,
            walk=lambda: GOOD_WALK, lock_differences=lambda: None,
            back_up=lambda label: backups.back_up(req.home, label),
            log=lambda **fields: deploylog.append(req.home, **fields))
        return upgrade.upgrade(req, hands, say=said.append)

    args = _parse(["--tree", str(repos["tree"]), "--home", str(home), *extra])
    code = upgrade.prepare(args, say=said.append, start=start)
    return code, instance, seen, said


def _head(tree):
    return _git(tree, "rev-parse", "HEAD")


def test_end_to_end_an_upgrade_moves_the_tree_and_records_it(repos, home):
    code, instance, seen, said = _end_to_end(repos, home, "--to", "origin/master")

    assert code == upgrade.OK, "\n".join(said)
    assert _head(repos["tree"]) == repos["second"], "fetched, resolved and checked out"
    assert _git(repos["tree"], "status", "--porcelain") == ""
    assert instance.did == ["stop", "start"] and instance.serving == repos["second"]

    # Stage 2 was handed a checkout of the target, and it is gone afterwards.
    assert seen["checkout_head"] == repos["second"] and seen["checkout_marker"] == "two"
    assert seen["python"] == repos["tree"] / ".venv" / "Scripts" / "python.exe"
    assert not seen["checkout"].exists() and not seen["checkout"].parent.exists()
    assert len(_git(repos["tree"], "worktree", "list").splitlines()) == 1

    record, = deploylog.read(home)
    assert (record["outcome"], record["from"], record["to"]) == (
        "ok", repos["first"], repos["second"])
    assert backups.verify(Path(record["backup"])) == []


def test_end_to_end_a_build_that_never_comes_up_is_rolled_back(repos, home):
    code, instance, _, said = _end_to_end(repos, home, "--to", "origin/master",
                                          never_healthy={repos["second"]})

    assert code == upgrade.ROLLED_BACK, "\n".join(said)
    assert _head(repos["tree"]) == repos["first"]
    assert _git(repos["tree"], "status", "--porcelain") == ""
    assert instance.did == ["stop", "start", "stop", "start"] and instance.serving == repos["first"]
    record, = deploylog.read(home)
    assert record["outcome"] == "rolled-back" and "not healthy" in record["detail"]
    assert len(_git(repos["tree"], "worktree", "list").splitlines()) == 1


def test_end_to_end_check_changes_nothing_at_all(repos, home):
    before = sorted(p.name for p in home.iterdir())
    code, instance, seen, _ = _end_to_end(repos, home, "--to", "origin/master", "--check")
    assert code == upgrade.OK and "--check" in seen["argv"]
    assert _head(repos["tree"]) == repos["first"] and instance.did == []
    assert sorted(p.name for p in home.iterdir()) == before, "no backup and no log"


def test_end_to_end_local_changes_in_the_tree_refuse(repos, home):
    (repos["tree"] / "marker.txt").write_text("edited in place", encoding="utf-8")
    code, instance, _, said = _end_to_end(repos, home, "--to", "origin/master")
    assert code == upgrade.REFUSED and instance.did == []
    assert "local change(s)" in "\n".join(said)
    assert (repos["tree"] / "marker.txt").read_text(encoding="utf-8") == "edited in place"
    assert deploylog.read(home)[0]["outcome"] == "refused"


def test_without_a_fetch_a_commit_the_clone_has_not_seen_is_unknown(repos, home):
    said = []
    code, _, seen, _ = _end_to_end(repos, home, "--to", repos["second"], "--no-fetch", said=said)
    assert code == upgrade.REFUSED and seen == {}, "stage 2 was never started"
    assert "REFUSED, and nothing was changed" in "\n".join(said)
    assert deploylog.read(home) == []


@pytest.mark.parametrize("to", ["no-such-ref", "HEAD:marker.txt"])
def test_a_target_that_is_not_a_commit_is_refused(repos, home, to):
    code, _, seen, _ = _end_to_end(repos, home, "--to", to)
    assert code == upgrade.REFUSED and seen == {}


def test_a_folder_that_is_not_a_checkout_is_refused(tmp_path, home):
    said = []
    args = _parse(["--tree", str(tmp_path), "--home", str(home), "--to", "origin/master"])
    assert upgrade.prepare(args, say=said.append,
                           start=lambda *a: pytest.fail("stage 2 was started")) == upgrade.REFUSED
    assert "is not a git checkout" in said[0]


def test_an_instance_with_no_interpreter_is_refused(repos, home):
    shutil.rmtree(repos["tree"] / ".venv")
    said = []
    args = _parse(["--tree", str(repos["tree"]), "--home", str(home), "--to", "origin/master"])
    assert upgrade.prepare(args, say=said.append,
                           start=lambda *a: pytest.fail("stage 2 was started")) == upgrade.REFUSED
    assert "no interpreter found for the instance" in said[0] and "--python" in said[0]


def test_the_throwaway_checkout_is_removed_even_when_stage_two_blows_up(repos, home):
    seen = {}

    def start(python, checkout, argv):
        seen["checkout"] = checkout
        raise RuntimeError("stage 2 crashed")

    args = _parse(["--tree", str(repos["tree"]), "--home", str(home), "--to", "origin/master"])
    with pytest.raises(RuntimeError, match="stage 2 crashed"):
        upgrade.prepare(args, say=lambda line: None, start=start)
    assert not seen["checkout"].exists()
    assert len(_git(repos["tree"], "worktree", "list").splitlines()) == 1
    assert _head(repos["tree"]) == repos["first"]


def test_stage_two_is_started_on_the_instances_interpreter_from_the_target(monkeypatch, tmp_path):
    seen = {}

    class Done:
        returncode = 7

    def run(command, **kwargs):
        seen["command"], seen["kwargs"] = command, kwargs
        return Done()

    monkeypatch.setattr(upgrade.subprocess, "run", run)
    for name in ("ADMZ_HOME", "ADMZ_AUTH_BACKEND", "PYTHONPATH", "PYTHONSAFEPATH"):
        monkeypatch.setenv(name, "ambient")
    code = upgrade.launch(Path("inst/python.exe"), tmp_path, ["--tree", "t", "--to", B])

    assert code == 7, "the outcome of stage 2 is the outcome of the command"
    assert seen["command"] == [str(Path("inst/python.exe")), "-m", "admz", "upgrade", "--stage2",
                               "--tree", "t", "--to", B]
    assert seen["kwargs"]["cwd"] == str(tmp_path), "the working directory is what puts the target's code first"
    env = seen["kwargs"]["env"]
    assert not [k for k in env if k.startswith("ADMZ_")], "no ambient data folder reaches stage 2"
    assert "PYTHONPATH" not in env and "PYTHONSAFEPATH" not in env
    assert "capture_output" not in seen["kwargs"], "the operator sees each step as it happens"


# ── the command line ────────────────────────────────────────────────────────

def _cli(*argv, tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ADMZ_")}
    env["ADMZ_HOME"] = str(tmp_path)
    return subprocess.run([sys.executable, "-m", "admz", "upgrade", *argv],
                          cwd=str(REPO), env=env, capture_output=True, text=True, timeout=120)


def test_the_command_explains_itself_and_hides_its_second_stage(tmp_path):
    done = _cli("--help", tmp_path=tmp_path)
    assert done.returncode == 0, done.stderr
    for flag in ("--tree", "--home", "--to", "--check", "--service", "--port", "--no-fetch"):
        assert flag in done.stdout
    assert "--stage2" not in done.stdout and "--from" not in done.stdout
    assert "Never taken from the environment" in " ".join(done.stdout.split())


def test_the_command_will_not_guess_the_tree_the_data_folder_or_the_target(tmp_path):
    done = _cli(tmp_path=tmp_path)
    assert done.returncode == 2
    assert "--tree" in done.stderr and "--home" in done.stderr and "--to" in done.stderr


def test_the_command_reaches_the_upgrade_and_reports_its_refusal(tmp_path):
    """The whole path from ``python -m admz`` to a refusal, with nothing to
    upgrade: the folder named as the tree is not a checkout."""
    not_a_tree = tmp_path / "empty"
    not_a_tree.mkdir()
    done = _cli("--tree", str(not_a_tree), "--home", str(tmp_path), "--to", "origin/master",
                tmp_path=tmp_path)
    assert done.returncode == upgrade.REFUSED, done.stderr
    assert "REFUSED, and nothing was changed" in done.stdout
    assert "is not a git checkout" in done.stdout


def test_the_ambient_data_folder_is_never_the_default(tmp_path):
    """On the development machine ``ADMZ_HOME`` is the lab instance's. The
    command must be told which data folder it is working on."""
    args = _parse(["--tree", "t", "--home", "given", "--to", "x"])
    assert args.home == "given"
    with pytest.raises(SystemExit):
        _parse(["--tree", "t", "--to", "x"])
