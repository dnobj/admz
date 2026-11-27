"""Upgrade an instance that is a git checkout: the order of the steps, and the way back.

    python -m admz upgrade --tree C:\\path\\to\\instance --home C:\\path\\to\\data --to origin/master
    python -m admz upgrade ... --check        # every check, and nothing changed

This is the checklist of 2026-11-13 (#426) as one command. It was typed by hand
four times before that, and each time the rollback existed only as an intention.

WHAT IT DOES, IN ORDER
----------------------
1.  The tree is at the commit this upgrade was prepared from, and has no local
    changes. The target is ahead of it.
2.  The catalog pin does not move, and the installed packages are exactly the
    target's ``requirements.lock``.
3.  The service is running, and the instance answering on the port reports the
    build of *this* tree.
4.  Every module of the target imports on the instance's own interpreter.
5.  The database and its key are copied, and the copy is checked.
        -- up to here nothing has changed, and any failure is a refusal --
6.  Stop the service, check out the target, start the service.
7.  Wait for a healthy answer that reports the target's build.
8.  If 6 or 7 fails for any reason, go back: stop, check out the old commit,
    start, and wait for a healthy answer from the old build.
9.  One line in the host's deploy log, whichever way it ended.

TWO STAGES, AND WHY
-------------------
The command is started from any checkout that has it. Stage 1 fetches, resolves
the target, makes a throwaway checkout of it, and runs stage 2 from there on the
instance's own interpreter. So the code performing the upgrade is the target's
code, checked by the target's own rules, and it is not replaced under its own
feet when the tree is switched.

Stage 2's arguments are an interface between two versions: an older stage 1
starts a newer stage 2. Arguments may be added to it. None may be renamed or
removed.

WHAT IT DOES NOT DO
-------------------
It installs no packages and no catalog. If the target's lock or its catalog pin
differs from what is installed, it refuses and says what differs. Replacing
packages under a running interpreter on Windows fails on every loaded binary,
and the self-contained build (ADR-0075, FR-DEP-008) carries its packages with
it, which removes the problem instead of working around it.

It never restores the database. Schema changes are additive (ADR-0075 §6), so
the old code starts on the new schema, and restoring a copy would throw away
whatever was written in between. The copy is there for a person to use.

It reads no ``ADMZ_*`` variable. The data folder is an argument, because the
ambient ``ADMZ_HOME`` belongs to whoever opened the shell.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from admz.release import backup as backups
from admz.release import deploylog, health, walk
from admz.release.service import RUNNING, ServiceError, WindowsService

#: Exit codes. ``REFUSED`` changed nothing. ``ROLLED_BACK`` switched and came
#: back. ``ROLLBACK_FAILED`` is the one that needs a person straight away.
OK, ROLLED_BACK, REFUSED, ROLLBACK_FAILED = 0, 1, 2, 3

LOCK_NAME = "requirements.lock"


class GitError(RuntimeError):
    """A git command failed or could not be run."""


class Refused(RuntimeError):
    """A check failed before anything was changed."""


class SwitchFailed(RuntimeError):
    """The instance came up, but not on the build it was switched to."""


def git(tree: Path, *args: str) -> str:
    """Run git in ``tree`` and return what it printed. Raises :class:`GitError`."""
    try:
        done = subprocess.run(["git", "-C", str(tree), *args],
                              capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitError(f"git {' '.join(args)} could not be run: {exc}") from exc
    if done.returncode != 0:
        said = (done.stderr or done.stdout or "").strip().splitlines()
        raise GitError(f"git {' '.join(args)} failed in {tree}: "
                       f"{said[-1] if said else f'exit {done.returncode}'}")
    return (done.stdout or "").strip()


@dataclass(frozen=True)
class Request:
    tree: Path                # the instance's checkout
    home: Path                # the instance's data folder
    source: str               # the full commit the tree is at
    target: str               # the full commit to switch to
    port: int
    check_only: bool = False


@dataclass
class Hands:
    """Everything an upgrade does to the world outside this process.

    Each is a parameter so that a test can stand in for it. No test stops a real
    service, asks a real instance, or opens a real data folder.
    """

    git: Callable[..., str]
    service: object                                   # state(), stop(), start()
    probe: Callable[[], dict]                         # ask once, now
    wait_healthy: Callable[[], dict]                  # keep asking until healthy
    walk: Callable[[], "walk.WalkResult"]
    lock_differences: Callable[[], Optional[List[str]]]   # None: the target has no lock
    back_up: Callable[[str], "backups.Backup"]
    log: Callable[..., dict]


def _short(commit: Optional[str]) -> str:
    return (commit or "none")[:7]


def _describe(exc: BaseException) -> str:
    if isinstance(exc, KeyboardInterrupt):
        return "interrupted from the keyboard"
    return str(exc) or type(exc).__name__


_PIN = re.compile(r'^ATLAS_SHA\s*=\s*"([0-9a-fA-F]{40})"', re.MULTILINE)


def catalog_pin(run_git: Callable[..., str], tree: Path, commit: str) -> Optional[str]:
    """``ATLAS_SHA`` as ``setup.py`` holds it at ``commit``, or ``None``."""
    try:
        found = _PIN.search(run_git(tree, "show", f"{commit}:setup.py"))
    except GitError:
        return None
    return found.group(1).lower() if found else None


def preflight(req: Request, hands: Hands, say: Callable[[str], None]) -> None:
    """Every check that can be made without changing anything. Raises :class:`Refused`."""
    tree = req.tree
    try:
        head = hands.git(tree, "rev-parse", "HEAD")
        if head != req.source:
            raise Refused(
                f"the tree is at {_short(head)}, and this upgrade was prepared from "
                f"{_short(req.source)}. Something moved it in between; start again")
        if head == req.target:
            raise Refused(f"the tree is already at {_short(head)}")
        changes = hands.git(tree, "status", "--porcelain").splitlines()
        if changes:
            raise Refused(
                f"the tree has {len(changes)} local change(s), such as "
                f"{changes[0].strip()!r}. An instance's tree is meant to be exactly its "
                f"commit; find out what changed it before replacing it")
        hands.git(tree, "cat-file", "-e", f"{req.target}^{{commit}}")
    except GitError as exc:
        raise Refused(str(exc)) from exc
    try:
        hands.git(tree, "merge-base", "--is-ancestor", head, req.target)
    except GitError as exc:
        raise Refused(
            f"{_short(req.target)} is not ahead of {_short(head)}. This command only moves "
            f"an instance forward; going back is what its rollback is for") from exc
    say(f"  ok   the tree is clean at {_short(head)}, and {_short(req.target)} is ahead of it")

    old_pin = catalog_pin(hands.git, tree, head)
    new_pin = catalog_pin(hands.git, tree, req.target)
    if old_pin != new_pin:
        raise Refused(
            f"the catalog pin moves from {_short(old_pin)} to {_short(new_pin)}, and this "
            f"command does not install the catalog. The instance would run the new code "
            f"on the old catalog (#424)")
    say(f"  ok   the catalog pin does not move ({_short(new_pin)})")

    differences = hands.lock_differences()
    if differences is None:
        say(f"  --   {_short(req.target)} carries no {LOCK_NAME}; installed packages were not compared")
    elif differences:
        shown = "; ".join(differences[:5])
        more = f"; and {len(differences) - 5} more" if len(differences) > 5 else ""
        raise Refused(
            f"the installed packages are not {_short(req.target)}'s {LOCK_NAME} "
            f"({len(differences)} difference(s)): {shown}{more}. This command does not "
            f"install packages")
    else:
        say(f"  ok   the installed packages are exactly {_short(req.target)}'s {LOCK_NAME}")

    try:
        state = hands.service.state()
    except ServiceError as exc:
        raise Refused(str(exc)) from exc
    if state != RUNNING:
        raise Refused(
            f"the service is {state}, not running. An upgrade is not how a stopped "
            f"service is repaired: its rollback would start something that was down")
    try:
        answer = hands.probe()
    except health.HealthError as exc:
        raise Refused(f"the instance is not healthy before the upgrade: {exc}") from exc
    if not health.reports_commit(answer.get("build"), head):
        raise Refused(
            f"the instance answering on port {req.port} reports build "
            f"{answer.get('build')!r}, and this tree is at {_short(head)}. Either another "
            f"instance is answering there, or this tree was edited in place")
    say(f"  ok   the service is running, and healthy on build {answer.get('build')}")

    try:
        result = hands.walk()
    except walk.WalkError as exc:
        raise Refused(str(exc)) from exc
    if not result.ok:
        shown = "; ".join(f"{name}: {why}" for name, why in result.failures[:5])
        raise Refused(
            f"{len(result.failures)} module(s) of {_short(req.target)} do not import on "
            f"the instance's interpreter: {shown or 'nothing was imported'}")
    say(f"  ok   {len(result.imported)} modules of {_short(req.target)} import on the "
        f"instance's interpreter")


def _switch(req: Request, hands: Hands, say: Callable[[str], None], commit: str,
            *, going_back: bool = False) -> dict:
    """Stop, check out ``commit``, start, and require a healthy answer from it."""
    try:
        hands.service.stop()
    except ServiceError as exc:
        if not going_back:
            raise
        # On the way back the service may have crashed, or never stopped. Either
        # way the old code still has to be put in place and started.
        say(f"  --   the service did not stop cleanly ({exc}); carrying on")
    say("  ..   service stopped")
    # --force only on the way back. The tree was clean before the switch, so
    # anything in the way now is debris of a checkout that failed half way.
    force = ["--force"] if going_back else []
    hands.git(req.tree, "checkout", "--quiet", *force, "--detach", commit)
    say(f"  ..   tree at {_short(commit)}")
    hands.service.start()
    say("  ..   service started, waiting for a healthy answer")
    answer = hands.wait_healthy()
    if not health.reports_commit(answer.get("build"), commit):
        raise SwitchFailed(
            f"the instance is healthy but reports build {answer.get('build')!r}, "
            f"not {_short(commit)}")
    return answer


def upgrade(req: Request, hands: Hands, say: Callable[[str], None] = print,
            clock: Callable[[], float] = time.monotonic) -> int:
    """Run the whole upgrade. Returns one of the exit codes above."""
    began = clock()
    verb = "Checking an upgrade of" if req.check_only else "Upgrading"
    say(f"{verb} the instance in {req.tree}: {_short(req.source)} -> {_short(req.target)}")

    # The log is only ever written into a folder that has shown itself to be an
    # instance's data folder. A mistyped --home must not gain a deployed.log.
    home_is_real = req.home.is_dir() and (req.home / backups.DB_NAME).is_file()

    def finish(outcome: str, code: int, detail: str = "", backup=None) -> int:
        if req.check_only or not home_is_real:
            return code
        try:
            hands.log(action="upgrade", outcome=outcome, source=req.source, target=req.target,
                      detail=detail, tree=str(req.tree),
                      backup=str(backup.folder) if backup else None,
                      seconds=round(clock() - began, 1))
        except Exception as exc:             # the log must never hide how it ended
            say(f"  !!   the deploy log could not be written: {exc}")
        return code

    try:
        if not home_is_real:
            raise Refused(
                f"{req.home} holds no {backups.DB_NAME}; that is not this instance's data folder")
        preflight(req, hands, say)
    except Refused as exc:
        say(f"REFUSED, and nothing was changed: {exc}")
        return finish("refused", REFUSED, str(exc))

    if req.check_only:
        say("Every check passed. Nothing was changed, and nothing was written.")
        return OK

    try:
        backup = hands.back_up(f"{_short(req.source)}-to-{_short(req.target)}")
    except backups.BackupError as exc:
        say(f"REFUSED, and nothing was changed: the backup failed: {exc}")
        return finish("refused", REFUSED, f"the backup failed: {exc}")
    say(f"  ok   database and key copied to {backup.folder}")

    # From here the instance is being changed, and every failure goes back,
    # whatever its kind. That includes Ctrl-C: a half-switched instance with its
    # service stopped is the one state this command must not leave behind.
    try:
        answer = _switch(req, hands, say, req.target)
    except BaseException as exc:
        why = _describe(exc)
        if not isinstance(exc, (ServiceError, GitError, health.HealthError,
                                SwitchFailed, KeyboardInterrupt)):
            say(traceback.format_exc())
        say(f"FAILED after the switch began: {why}")
        say(f"Going back to {_short(req.source)}.")
        try:
            _switch(req, hands, say, req.source, going_back=True)
        except BaseException as again:
            then = _describe(again)
            say("THE ROLLBACK FAILED. The instance is not known to be running.")
            say(f"  first: {why}")
            say(f"  then:  {then}")
            say(f"  by hand: put {req.tree} at {req.source}, start the service, and read its log.")
            say(f"  the copy of the database taken before the switch is in {backup.folder}")
            return finish("rollback-failed", ROLLBACK_FAILED,
                          f"{why}; then the rollback failed: {then}", backup)
        say(f"Rolled back. The instance is healthy on {_short(req.source)} again.")
        return finish("rolled-back", ROLLED_BACK, why, backup)

    say(f"Upgraded. The instance is healthy on build {answer.get('build')}.")
    return finish("ok", OK, "", backup)


# ── stage 2: the real hands ─────────────────────────────────────────────────

def _lock_tool(checkout: Path):
    """``tools/lock.py`` of ``checkout``, loaded from its file.

    Loaded by path and not imported by name: the name ``tools`` is common enough
    that something else in an environment may own it.
    """
    path = checkout / "tools" / "lock.py"
    spec = importlib.util.spec_from_file_location("admz_release_lock_tool", path)
    if spec is None or spec.loader is None or not path.is_file():
        raise Refused(f"{checkout} has a {LOCK_NAME} and no tools/lock.py to read it with")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module          # dataclasses look their module up by name
    spec.loader.exec_module(module)
    return module


def lock_differences(checkout: Path, python: Optional[Path] = None) -> Optional[List[str]]:
    """How the environment of ``python`` differs from ``checkout``'s lock.

    ``None`` when the checkout carries no lock. Raises :class:`Refused` when the
    comparison cannot be made: an upgrade that could not check must not go on.
    """
    lock_file = checkout / LOCK_NAME
    if not lock_file.is_file():
        return None
    tool = _lock_tool(checkout)
    try:
        pins = tool.read_lock(lock_file)
        packages, markers = tool.installed(python)
        return [str(difference) for difference in tool.differences(pins, packages, markers)]
    except (tool.LockError, OSError) as exc:
        raise Refused(f"the installed packages could not be compared with {LOCK_NAME}: {exc}") from exc


def real_hands(req: Request, *, service_name: str, within: float, checkout: Path) -> Hands:
    """The hands of a real upgrade, for the instance described by ``req``."""
    return Hands(
        git=git,
        service=WindowsService(service_name),
        probe=lambda: health.probe(req.port),
        wait_healthy=lambda: health.wait_healthy(req.port, within=within),
        walk=lambda: walk.run(Path(sys.executable), checkout),
        lock_differences=lambda: lock_differences(checkout),
        back_up=lambda label: backups.back_up(req.home, label),
        log=lambda **fields: deploylog.append(req.home, **fields),
    )


def stage2(args, *, say: Callable[[str], None] = print, make_hands=real_hands,
           run_git: Callable[..., str] = git, here: Optional[Path] = None) -> int:
    """Stage 2: runs from a checkout of the target, on the instance's interpreter."""
    checkout = Path(here) if here else Path.cwd()
    # Prove it, instead of trusting how this process was started. If the import
    # path had resolved `admz` to the instance's own tree, the old code would be
    # checking the new commit.
    code = Path(__file__).resolve()
    try:
        at = run_git(checkout, "rev-parse", "HEAD")
    except GitError as exc:
        say(f"REFUSED, and nothing was changed: stage 2 is not running in a checkout: {exc}")
        return REFUSED
    if at != args.to or checkout.resolve() not in code.parents:
        say("REFUSED, and nothing was changed: stage 2 must run from a checkout of the "
            f"target commit. It is running {code} with {checkout} at {_short(at)}, "
            f"and the target is {_short(args.to)}")
        return REFUSED

    req = Request(tree=Path(args.tree), home=Path(args.home), source=args.source,
                  target=args.to, port=args.port, check_only=bool(args.check))
    try:
        hands = make_hands(req, service_name=args.service, within=args.within, checkout=checkout)
    except ServiceError as exc:
        say(f"REFUSED, and nothing was changed: {exc}")
        return REFUSED
    return upgrade(req, hands, say)


# ── stage 1: prepare, and hand over ─────────────────────────────────────────

def instance_python(tree: Path) -> Optional[Path]:
    for tail in (("Scripts", "python.exe"), ("bin", "python")):
        candidate = Path(tree, ".venv", *tail)
        if candidate.is_file():
            return candidate
    return None


def launch(python: Path, checkout: Path, argv: List[str]) -> int:
    """Run stage 2 from ``checkout`` on ``python``, with a clean environment.

    The working directory is what makes ``-m admz`` import the target's code:
    Python puts it first on the search path.
    """
    env = walk.clean_environment()
    for name in ("PYTHONSAFEPATH", "PYTHONSTARTUP", "PYTHONUSERBASE"):
        env.pop(name, None)                  # PYTHONSAFEPATH would take the checkout off the path
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([str(python), "-m", "admz", "upgrade", "--stage2", *argv],
                          cwd=str(checkout), env=env).returncode


def prepare(args, *, say: Callable[[str], None] = print, run_git: Callable[..., str] = git,
            start: Callable[[Path, Path, List[str]], int] = launch) -> int:
    """Stage 1: fetch, resolve the target, make a throwaway checkout, start stage 2."""
    tree = Path(args.tree).resolve()
    if not (tree / ".git").exists():
        say(f"REFUSED, and nothing was changed: {tree} is not a git checkout")
        return REFUSED
    python = Path(args.python) if args.python else instance_python(tree)
    if python is None or not python.is_file():
        say(f"REFUSED, and nothing was changed: no interpreter found for the instance "
            f"({python or tree / '.venv'}); name it with --python")
        return REFUSED
    try:
        if not args.no_fetch:
            run_git(tree, "fetch", "--quiet", "origin")
        target = run_git(tree, "rev-parse", "--verify", "--quiet", f"{args.to}^{{commit}}")
        source = run_git(tree, "rev-parse", "HEAD")
    except GitError as exc:
        say(f"REFUSED, and nothing was changed: {exc}")
        return REFUSED
    if not target:
        say(f"REFUSED, and nothing was changed: {args.to!r} does not name a commit in {tree}")
        return REFUSED

    holder = Path(tempfile.mkdtemp(prefix="admz-upgrade-"))
    checkout = holder / "target"
    try:
        try:
            run_git(tree, "worktree", "add", "--quiet", "--detach", str(checkout), target)
        except GitError as exc:
            say(f"REFUSED, and nothing was changed: {exc}")
            return REFUSED
        argv = ["--tree", str(tree), "--home", str(Path(args.home).resolve()),
                "--to", target, "--from", source,
                "--service", args.service, "--port", str(args.port),
                "--within", str(args.within)]
        if args.check:
            argv.append("--check")
        return start(python, checkout, argv)
    finally:
        try:
            run_git(tree, "worktree", "remove", "--force", str(checkout))
        except GitError:
            pass                               # prune below clears whatever is left
        shutil.rmtree(holder, ignore_errors=True)
        try:
            run_git(tree, "worktree", "prune")
        except GitError:
            pass


# ── the command line ────────────────────────────────────────────────────────

def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tree", required=True,
                        help="the instance's git checkout")
    parser.add_argument("--home", required=True,
                        help="the instance's data folder (the ADMZ_HOME its service runs "
                             "with). Never taken from the environment")
    parser.add_argument("--to", required=True,
                        help="the commit to upgrade to, as the instance's own clone names "
                             "it: a commit id, a tag, or a ref such as origin/master")
    parser.add_argument("--service", default="admz",
                        help="the Windows service the instance runs as (default: admz)")
    parser.add_argument("--port", type=int, default=4242,
                        help="the port the instance listens on, on this machine (default: 4242)")
    parser.add_argument("--within", type=float, default=90.0,
                        help="seconds to wait for a healthy answer after a start (default: 90)")
    parser.add_argument("--python",
                        help="the instance's interpreter (default: .venv in its tree)")
    parser.add_argument("--no-fetch", action="store_true",
                        help="do not fetch from origin first; the target must already be "
                             "in the instance's clone")
    parser.add_argument("--check", action="store_true",
                        help="run every check, change nothing, and write nothing")
    # Stage 2 only. Set by stage 1; see the module docstring before changing them.
    parser.add_argument("--stage2", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--from", dest="source", help=argparse.SUPPRESS)


def main(args) -> int:
    if args.stage2:
        if not args.source:
            print("REFUSED, and nothing was changed: stage 2 was started without --from")
            return REFUSED
        return stage2(args)
    return prepare(args)
