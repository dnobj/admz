"""Import every module on the interpreter that is about to run them.

This is the check that would have caught 2026-08-04, when code needing ``mcp``
2.x was merged into a tree whose environment held 1.26. The service kept
serving on what it had loaded hours earlier, and any restart would have ended
in an import error and a restart loop (ADR-0054). An environment is complete
for a commit when every module of that commit imports on it. Nothing else
answers that, and the test suite cannot run there: a deployment has no pytest.

Three things here were learned the hard way and are easy to undo by accident.

IT DOES ITS OWN DESCENT. ``pkgutil.walk_packages`` imports each package to look
inside it, and swallows an ImportError raised there unless it is given an
``onerror`` hook: a broken package is skipped and the walk reports success. The
deploy of 2026-11-13 found that. With the hook it still imports a failing
package twice, and an exit raised at import escapes it altogether. So this lists
one level at a time, imports each name exactly once, and looks inside a package
only after its own import has succeeded.

THE WALK REFUSES A DATA FOLDER IT WAS NOT HANDED ON PURPOSE. Importing is meant
to have no side effects, and a module that breaks that rule must not be able to
reach a real database. So the walk runs in its own process, with every
``ADMZ_*`` variable removed and ``ADMZ_HOME`` set to a new empty folder. The
child checks that for itself before it imports anything from the package: the
variable must name the folder it was told to use, and that folder must hold no
database and no key.

THE CHILD IS RUN AS A FILE, NOT WITH ``-m``. ``python -m admz.release.walk``
would import ``admz`` before a single line here ran, and the check above would
come second. Run as a file, this module needs only the standard library until
the check has passed. That is why it imports nothing from ``admz`` at the top.

It also checks where the package was imported from. An environment can hold an
installed copy of the same package, and a walk that quietly imported that one
would be vouching for code nobody asked about.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import pkgutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

#: Files whose presence means a folder is somebody's data, not a throwaway.
_DATA_FILES = ("admz.db", "admz.key")


class WalkError(RuntimeError):
    """The walk could not be run at all. Different from a module failing to import."""


@dataclass(frozen=True)
class WalkResult:
    imported: List[str]
    failures: List[Tuple[str, str]]          # (module, one-line reason)

    @property
    def ok(self) -> bool:
        return bool(self.imported) and not self.failures


def _reason(exc: BaseException) -> str:
    last = traceback.extract_tb(exc.__traceback__)[-1:] if exc.__traceback__ else []
    where = f" ({Path(last[0].filename).name}:{last[0].lineno})" if last else ""
    return f"{type(exc).__name__}: {exc}{where}"


def _names(paths, prefix: str):
    """Module names under ``paths``, each package before what it contains.

    A generator on purpose. The caller imports each name before asking for the
    next, so by the time a package's contents are listed its own import has
    been tried. One that failed has no entry in ``sys.modules``, and its
    contents are not guessed at.
    """
    for info in pkgutil.iter_modules(paths, prefix):
        yield info.name
        if info.ispkg:
            below = getattr(sys.modules.get(info.name), "__path__", None)
            if below:
                yield from _names(below, info.name + ".")


def walk(package: str = "admz", *, source: Optional[Path] = None) -> WalkResult:
    """Import ``package`` and everything under it, in this process.

    With ``source``, the package must have been imported from under that
    folder; anything else is reported as a failure of the package itself.

    ``SystemExit`` raised at import is a failure like any other. An interrupt
    from the keyboard is not caught: it means stop.
    """
    imported: List[str] = []
    failures: List[Tuple[str, str]] = []
    try:
        root = importlib.import_module(package)
    except (Exception, SystemExit) as exc:
        return WalkResult([], [(package, _reason(exc))])

    if source is not None:
        origin = Path(getattr(root, "__file__", None) or ".").resolve()
        if Path(source).resolve() not in origin.parents:
            return WalkResult([], [(package, (
                f"was imported from {origin.parent}, not from {source}; "
                f"the walk would be vouching for the wrong code"))])
    imported.append(package)

    for name in _names(getattr(root, "__path__", None) or [], package + "."):
        try:
            importlib.import_module(name)
            imported.append(name)
        except (Exception, SystemExit) as exc:
            failures.append((name, _reason(exc)))
    return WalkResult(imported, failures)


def check_home(home: Path, environ=os.environ) -> Optional[str]:
    """Why this process must not import against ``home``, or ``None`` if it may."""
    given = environ.get("ADMZ_HOME")
    if not given:
        return "ADMZ_HOME is not set, so anything that reads it would fall back to a real folder"
    if Path(given).resolve() != Path(home).resolve():
        return f"ADMZ_HOME is {given}, not the folder this walk was told to use ({home})"
    if not Path(home).is_dir():
        return f"{home} is not a folder"
    held = [name for name in _DATA_FILES if (Path(home) / name).exists()]
    if held:
        return f"{home} holds {' and '.join(held)}: that is a data folder, not a throwaway"
    others = sorted(k for k in environ if k.startswith("ADMZ_") and k != "ADMZ_HOME")
    if others:
        return (f"{', '.join(others)} set in this process; an override could point a "
                f"module at a real path")
    return None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Import every module of a package and report.")
    ap.add_argument("--home", required=True,
                    help="the throwaway folder ADMZ_HOME was set to for this walk")
    ap.add_argument("--source", required=True,
                    help="the folder the package is to be imported from")
    ap.add_argument("--package", default="admz")
    args = ap.parse_args(argv)

    refusal = check_home(Path(args.home))
    if refusal:
        print(json.dumps({"refused": refusal}))
        return 2

    # Only now may the package be imported. Run as a file, Python put this
    # file's own folder on the path, where `health`, `backup` and `service`
    # would answer as top-level modules. It goes, and the source goes first.
    here = Path(__file__).resolve().parent
    source = Path(args.source).resolve()
    sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != here]
    sys.path.insert(0, str(source))

    result = walk(args.package, source=source)
    print(json.dumps({"imported": result.imported,
                      "failures": [list(pair) for pair in result.failures]}))
    return 0 if result.ok else 1


def clean_environment(environ=os.environ) -> dict:
    """A copy of the environment with nothing that could steer the walk.

    Every ``ADMZ_*`` variable goes: on the development machine the ambient
    ``ADMZ_HOME`` is the lab instance's data folder. So do the variables that
    add to Python's search path, because the question is what *this*
    environment can import.
    """
    return {k: v for k, v in environ.items()
            if not k.startswith("ADMZ_") and k not in ("PYTHONPATH", "PYTHONHOME")}


def run(python: Path, source: Path, *, package: str = "admz",
        runner: Callable = subprocess.run, timeout: float = 600.0) -> WalkResult:
    """Walk ``package`` from ``source`` on the interpreter ``python``, in its own process.

    ``-I`` leaves out the operator's own site-packages. The service runs under
    another account and does not have them, so a module that imports only
    because of them must fail here.
    """
    with tempfile.TemporaryDirectory(prefix="admz-walk-home-") as home:
        env = clean_environment()
        env["ADMZ_HOME"] = home
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        command = [str(python), "-I", str(Path(__file__).resolve()),
                   "--home", home, "--source", str(source), "--package", package]
        try:
            done = runner(command, cwd=str(source), env=env,
                          capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            raise WalkError(f"the import walk could not be run on {python}: {exc}") from exc
    lines = [line for line in (done.stdout or "").splitlines() if line.strip()]
    try:
        answer = json.loads(lines[-1])
    except (IndexError, ValueError) as exc:
        tail = (done.stderr or "").strip().splitlines()[-1:] or ["no output"]
        raise WalkError(f"the import walk gave no readable answer (exit {done.returncode}): "
                        f"{tail[0]}") from exc
    if not isinstance(answer, dict):
        raise WalkError("the import walk's answer is not an object")
    if "refused" in answer:
        raise WalkError(f"the import walk refused to run: {answer['refused']}")
    try:
        return WalkResult([str(name) for name in answer["imported"]],
                          [(str(name), str(why)) for name, why in answer["failures"]])
    except (KeyError, TypeError, ValueError) as exc:
        raise WalkError(f"the import walk's answer is missing a field: {exc}") from exc


if __name__ == "__main__":
    sys.exit(main())
