#!/usr/bin/env python
"""The dependency locks: regenerate them, and compare an environment with one.

    python tools/lock.py                        # after editing a requirements file
    python tools/lock.py --upgrade-package X    # move one package, keep the rest
    python tools/lock.py --check                # are the locks stale?
    python tools/lock.py --verify-installed dev # is this environment the lock?

Only the first two need ``uv``. Everything else here is the standard library,
so it runs on any interpreter, including one that holds nothing but the runtime.

TWO FILES, ONE RESOLUTION (ADR-0075, FR-DEP-003)
------------------------------------------------
``requirements.lock``      every runtime package, exact version, with hashes.
                           A build installs from this and nothing else.
``requirements-dev.lock``  the same pins plus the test tools. CI installs this.

Both are **universal**: one file holds the pins for Windows and for Linux, with
environment markers where they differ (``firebird-driver`` and ``pywin32`` only
on Windows, ``uvloop`` only off it). That is what lets the two CI legs and a
Windows build install the same resolution. The dev lock is compiled with the
runtime lock as a constraint, so the two cannot disagree about a runtime pin,
and ``tests/test_lockfiles.py`` fails if they ever do.

WHY BOTH NEED HASHES
--------------------
pip's hash checking is all or nothing: one ``--hash`` in a requirements file
and every requirement in that install needs one. So the test tools cannot
ride along unhashed next to a hashed runtime. Hence a second, complete file.

WHAT IS NOT IN A LOCK
---------------------
``axis-api-atlas``. It is installed from a pinned git commit (``ATLAS_SHA`` in
``setup.py``), and pip refuses a VCS requirement in hash-checking mode. It is
already pinned more tightly than a version could pin it.

WHY THE LOCKS RECORD THEIR INPUTS
---------------------------------
Each lock carries a hash of the requirement lines it was compiled from. Edit
``requirements.txt`` without re-running this and ``--check`` fails, as does the
test that calls it. Comments are not part of the hash, so rewording a note
does not make a lock stale; changing a bound does.

A plain run keeps every pin that still satisfies the requirement files, because
uv reads the existing lock as its starting point. That is deliberate: locking
should change what you asked it to change.

COMPARING AN ENVIRONMENT WITH A LOCK (FR-DEP-004)
-------------------------------------------------
``--verify-installed`` asks an interpreter what it has installed and reports
every way that differs from a lock: a package missing, at another version, or
present though the lock does not pin it. CI runs it straight after installing,
so "CI tests the lock" is observed on every run and not assumed from the
install command. ``tools/environments.py`` uses the same comparison for the
environments on this machine.

The lock's environment markers are evaluated here, by a small strict reader,
instead of by ``packaging``. A deployed environment holds only the runtime, and
``packaging`` is not part of it; a comparison that needs a test tool could not
run where it matters most. The reader refuses anything it does not understand,
and the tests check it against ``packaging`` on every marker the locks hold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[1]

#: The interpreter line every environment here is on: CI, the lab instance, a build.
PYTHON_VERSION = "3.12"

RUNTIME_LOCK = "requirements.lock"
DEV_LOCK = "requirements-dev.lock"

#: lock file -> (the file uv compiles, every file whose lines feed that lock)
LOCKS = {
    RUNTIME_LOCK: ("requirements.txt", ("requirements.txt",)),
    DEV_LOCK: ("requirements-dev.txt", ("requirements.txt", "requirements-dev.txt")),
}

#: The line this script adds to a lock, recording what it was compiled from.
MARK = "# admz-lock-inputs: sha256="

#: What uv prints as "the command that made this file".
COMPILE_COMMAND = "python tools/lock.py"

#: Installed beside a lock by other means, and deliberately not in one.
OUTSIDE_A_LOCK = {
    "admz": "the application itself",
    "axis-api-atlas": "the catalog, pinned by commit in setup.py",
    "pip": "the installer",
    "setuptools": "the installer's build tool",
    "wheel": "the installer's build tool",
}


class LockError(ValueError):
    """A lock, or a marker in one, that this reader will not guess at."""


# ── are the locks stale ─────────────────────────────────────────────────────

def active_lines(path: Path) -> List[str]:
    """The lines of a requirements file that mean something, in order.

    Comments and blank lines are dropped, so the "installed X" notes can be
    reworded without making a lock stale. ``-r other.txt`` lines are kept: an
    include is part of what the file asks for.
    """
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.append(" ".join(line.split()))
    return out


def inputs_digest(names: Sequence[str], root: Path = REPO) -> str:
    """One hash over the meaningful lines of every input file, in order."""
    h = hashlib.sha256()
    for name in names:
        h.update(name.encode("utf-8") + b"\n")
        for line in active_lines(root / name):
            h.update(line.encode("utf-8") + b"\n")
        h.update(b"--\n")
    return h.hexdigest()


def recorded_digest(lock: Path) -> Optional[str]:
    """The inputs hash a lock says it was compiled from, or ``None``."""
    try:
        for line in lock.read_text(encoding="utf-8").splitlines():
            if line.startswith(MARK):
                return line[len(MARK):].strip()
            if line and not line.startswith("#"):
                return None                     # past the header: no mark
    except OSError:
        return None
    return None


def stamp(lock: Path, digest: str) -> None:
    """Record ``digest`` in the lock's header, replacing any earlier record."""
    lines = [l for l in lock.read_text(encoding="utf-8").splitlines()
             if not l.startswith(MARK)]
    # After uv's own header comment, before the first requirement.
    at = 0
    while at < len(lines) and lines[at].startswith("#"):
        at += 1
    lines.insert(at, MARK + digest)
    lock.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def stale_locks(root: Path = REPO) -> List[str]:
    """One sentence per lock that no longer matches its inputs."""
    problems = []
    for lock_name, (_src, inputs) in LOCKS.items():
        lock = root / lock_name
        if not lock.exists():
            problems.append(f"{lock_name} does not exist. Run: {COMPILE_COMMAND}")
            continue
        want, have = inputs_digest(inputs, root), recorded_digest(lock)
        if have is None:
            problems.append(
                f"{lock_name} does not record what it was compiled from. "
                f"Run: {COMPILE_COMMAND}")
        elif have != want:
            problems.append(
                f"{lock_name} was compiled from different requirement lines than "
                f"{' + '.join(inputs)} now hold. Run: {COMPILE_COMMAND}")
    return problems


# ── reading a lock ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Pin:
    """One package in a lock."""

    name: str                 # canonical: lower case, runs of -_. folded to -
    version: str
    marker: str               # "" when the pin applies everywhere
    hashes: Tuple[str, ...]   # "sha256:<hex>", one per file the index offers


_PIN_LINE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)\s*(?:;\s*(.+?))?\s*\\?$")
_HASH_LINE = re.compile(r"^--hash=([a-z0-9]+:[0-9a-f]+)\s*\\?$")


def canonical(name: str) -> str:
    """A package name as an index compares it (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(path: Path) -> List[Pin]:
    """Every pin in a lock, in file order.

    Strict on purpose. A line that is not a comment, a pin or a hash raises.
    An editable install, a URL, an index option or an unpinned name is exactly
    what a lock must not hold, and a reader that skipped such a line would hide
    it from every check built on this function.
    """
    pins: List[Pin] = []
    head: Optional[Tuple[str, str, str]] = None
    hashes: List[str] = []

    def close() -> None:
        if head is not None:
            pins.append(Pin(head[0], head[1], head[2], tuple(hashes)))

    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        found = _HASH_LINE.match(line)
        if found:
            if head is None:
                raise LockError(f"{path.name}:{number}: a hash with no pin above it")
            hashes.append(found.group(1))
            continue
        found = _PIN_LINE.match(line)
        if not found:
            raise LockError(
                f"{path.name}:{number}: not a comment, a pin or a hash: {line!r}")
        close()
        head = (canonical(found.group(1)), found.group(2), (found.group(3) or "").strip())
        hashes = []
    close()
    return pins


# ── environment markers ─────────────────────────────────────────────────────

#: Marker variables whose values are versions, compared number by number.
_VERSION_VARS = {"python_version", "python_full_version", "implementation_version"}

_TOKEN = re.compile(
    r"""\s*(?:
        (?P<paren>[()])
      | (?P<op>===|==|!=|<=|>=|~=|<|>)
      | '(?P<single>[^']*)'
      | "(?P<double>[^"]*)"
      | (?P<word>[A-Za-z_][A-Za-z0-9_.]*)
    )""",
    re.VERBOSE,
)
_DOTTED = re.compile(r"^\d+(\.\d+)*$")


def _tokens(marker: str) -> List[Tuple[str, str]]:
    out, at = [], 0
    while marker[at:].strip():
        found = _TOKEN.match(marker, at)
        if not found:
            raise LockError(f"cannot read the marker {marker!r} at {marker[at:].strip()!r}")
        at = found.end()
        if found.group("paren"):
            out.append(("paren", found.group("paren")))
        elif found.group("op"):
            out.append(("op", found.group("op")))
        elif found.group("single") is not None:
            out.append(("text", found.group("single")))
        elif found.group("double") is not None:
            out.append(("text", found.group("double")))
        elif found.group("word") in ("and", "or", "in", "not"):
            out.append(("keyword", found.group("word")))
        else:
            out.append(("var", found.group("word")))
    return out


def _release(text: str, marker: str) -> Tuple[int, ...]:
    if not _DOTTED.match(text):
        raise LockError(
            f"the marker {marker!r} compares the version {text!r}, which is not "
            f"plain dotted numbers; this reader does not guess at it")
    return tuple(int(part) for part in text.split("."))


def _compare(left: Tuple[str, str], op: str, right: Tuple[str, str],
             env: Mapping[str, str], marker: str) -> bool:
    def value(side: Tuple[str, str]) -> str:
        kind, text = side
        if kind == "text":
            return text
        if text not in env:
            raise LockError(
                f"the marker {marker!r} names {text!r}, which the environment did not report")
        return env[text]

    lhs, rhs = value(left), value(right)
    versions = any(kind == "var" and text in _VERSION_VARS for kind, text in (left, right))
    if versions and op in ("==", "!=", "<", "<=", ">", ">="):
        a, b = _release(lhs, marker), _release(rhs, marker)
        width = max(len(a), len(b))
        a, b = a + (0,) * (width - len(a)), b + (0,) * (width - len(b))
        return {"==": a == b, "!=": a != b, "<": a < b,
                "<=": a <= b, ">": a > b, ">=": a >= b}[op]
    if op == "==":
        return lhs == rhs
    if op == "!=":
        return lhs != rhs
    if op == "in":
        return lhs in rhs
    if op == "not in":
        return lhs not in rhs
    raise LockError(f"the marker {marker!r} uses {op!r} in a way this reader does not support")


def marker_applies(marker: str, env: Mapping[str, str]) -> bool:
    """Whether a pin carrying ``marker`` belongs in the environment ``env``.

    ``env`` maps PEP 508's marker variables to that environment's values, as
    :func:`installed` reports them. Supports what a universal lock contains:
    comparisons joined by ``and`` / ``or``, with brackets. Anything else raises
    :class:`LockError`. A wrong guess here would report a healthy environment as
    broken, or a broken one as healthy.
    """
    if not marker.strip():
        return True
    tokens = _tokens(marker)
    at = 0

    def peek() -> Tuple[str, str]:
        return tokens[at] if at < len(tokens) else ("end", "")

    def take() -> Tuple[str, str]:
        nonlocal at
        token = peek()
        at += 1
        return token

    def operand() -> Tuple[str, str]:
        token = take()
        if token[0] not in ("var", "text"):
            raise LockError(f"the marker {marker!r} has {token[1]!r} where a value belongs")
        return token

    def comparison() -> bool:
        if peek() == ("paren", "("):
            take()
            result = either()
            if take() != ("paren", ")"):
                raise LockError(f"the marker {marker!r} has an unclosed bracket")
            return result
        left = operand()
        kind, text = take()
        if kind == "op":
            op = text
        elif (kind, text) == ("keyword", "in"):
            op = "in"
        elif (kind, text) == ("keyword", "not") and take() == ("keyword", "in"):
            op = "not in"
        else:
            raise LockError(f"the marker {marker!r} has {text!r} where a comparison belongs")
        return _compare(left, op, operand(), env, marker)

    def both() -> bool:
        result = comparison()
        while peek() == ("keyword", "and"):
            take()
            result = comparison() and result    # read every term, even when already false
        return result

    def either() -> bool:
        result = both()
        while peek() == ("keyword", "or"):
            take()
            result = both() or result
        return result

    result = either()
    if at != len(tokens):
        raise LockError(f"the marker {marker!r} has {peek()[1]!r} left over")
    return result


# ── what an environment holds ───────────────────────────────────────────────

#: Run inside the environment being asked. Standard library only.
_PROBE = r"""
import importlib.metadata as m, json, os, platform, sys
found = {}
for dist in m.distributions():
    try:
        name = dist.metadata["Name"]
    except Exception:
        name = None
    if name:
        found.setdefault(name, []).append(dist.version)
v = sys.implementation.version
impl = "%d.%d.%d" % (v.major, v.minor, v.micro)
if v.releaselevel != "final":
    impl += v.releaselevel[0] + str(v.serial)
print(json.dumps({"packages": found, "markers": {
    "implementation_name": sys.implementation.name,
    "implementation_version": impl,
    "os_name": os.name,
    "platform_machine": platform.machine(),
    "platform_python_implementation": platform.python_implementation(),
    "platform_release": platform.release(),
    "platform_system": platform.system(),
    "platform_version": platform.version(),
    "python_full_version": platform.python_version(),
    "python_version": ".".join(platform.python_version_tuple()[:2]),
    "sys_platform": sys.platform,
}}))
"""


def installed(python: Optional[Path] = None) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    """``(packages, markers)`` for the environment of ``python``.

    ``packages`` maps each installed distribution to every version found for it;
    more than one means leftovers of an earlier install, which is worth saying.
    ``markers`` is that interpreter's PEP 508 environment.

    ``-I`` keeps the answer to the environment itself: without it the current
    directory joins the search path, and a build directory lying there would be
    reported as installed.
    """
    exe = str(python) if python else sys.executable
    try:
        run = subprocess.run([exe, "-I", "-c", _PROBE],
                             capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise LockError(f"could not ask {exe} what it has installed: {exc}") from exc
    if run.returncode != 0:
        tail = (run.stderr or "").strip().splitlines()[-1:] or ["no output"]
        raise LockError(f"{exe} could not list what it has installed: {tail[0]}")
    try:
        data = json.loads(run.stdout)
        return data["packages"], data["markers"]
    except (ValueError, KeyError, TypeError) as exc:
        raise LockError(f"{exe} gave an answer that could not be read: {exc}") from exc


@dataclass(frozen=True)
class Difference:
    """One way an environment departs from a lock."""

    kind: str                 # "missing" | "version" | "twice" | "unpinned" | "lock"
    name: str
    installed: str = ""
    pinned: str = ""

    def __str__(self) -> str:
        if self.kind == "missing":
            return f"{self.name} is not installed (the lock pins {self.pinned})"
        if self.kind == "version":
            return f"{self.name} {self.installed} is installed; the lock pins {self.pinned}"
        if self.kind == "twice":
            return (f"{self.name} is installed more than once ({self.installed}); "
                    f"the lock pins {self.pinned}")
        if self.kind == "unpinned":
            return f"{self.name} {self.installed} is installed, and the lock does not pin it"
        return f"{self.name}: the lock pins it more than once for this platform ({self.pinned})"


def differences(pins: Sequence[Pin], packages: Mapping[str, Sequence[str]],
                markers: Mapping[str, str]) -> List[Difference]:
    """Every way an environment departs from a lock. Empty means it *is* the lock.

    Three things are compared, and all three matter. A pinned package that is
    missing or at another version is the obvious one. A package that is
    installed though no pin names it is the quiet one: it is a version nobody
    chose, running. :data:`OUTSIDE_A_LOCK` lists the few that are meant to be
    there.
    """
    wanted: Dict[str, List[str]] = {}
    for pin in pins:
        if marker_applies(pin.marker, markers):
            wanted.setdefault(pin.name, []).append(pin.version)
    have: Dict[str, List[str]] = {}
    for name, versions in packages.items():
        have.setdefault(canonical(name), []).extend(versions)

    out: List[Difference] = []
    for name in sorted(wanted):
        pinned = sorted(set(wanted[name]))
        if len(pinned) > 1:
            out.append(Difference("lock", name, pinned=", ".join(pinned)))
            continue
        got = sorted(set(have.get(name, ())))
        if not got:
            out.append(Difference("missing", name, pinned=pinned[0]))
        elif len(got) > 1:
            out.append(Difference("twice", name, ", ".join(got), pinned[0]))
        elif got[0].lower() != pinned[0].lower():
            out.append(Difference("version", name, got[0], pinned[0]))
    for name in sorted(set(have) - set(wanted) - set(OUTSIDE_A_LOCK)):
        out.append(Difference("unpinned", name, ", ".join(sorted(set(have[name])))))
    return out


def applicable(pins: Sequence[Pin], markers: Mapping[str, str]) -> int:
    """How many of a lock's pins belong in an environment with these markers."""
    return sum(1 for pin in pins if marker_applies(pin.marker, markers))


# ── regenerating ────────────────────────────────────────────────────────────

def find_uv() -> Optional[List[str]]:
    exe = shutil.which("uv")
    if exe:
        return [exe]
    probe = subprocess.run([sys.executable, "-m", "uv", "--version"],
                           capture_output=True, text=True)
    return [sys.executable, "-m", "uv"] if probe.returncode == 0 else None


def compile_lock(uv: List[str], src: str, out: str, *, constraints: Sequence[str],
                 upgrade: bool, upgrade_packages: Sequence[str]) -> int:
    cmd = [*uv, "pip", "compile", src,
           "--universal", "--generate-hashes",
           "--python-version", PYTHON_VERSION,
           "--custom-compile-command", COMPILE_COMMAND,
           "--quiet",
           "-o", out]
    for c in constraints:
        cmd += ["-c", c]
    if upgrade:
        cmd.append("--upgrade")
    for name in upgrade_packages:
        cmd += ["--upgrade-package", name]
    return subprocess.run(cmd, cwd=REPO).returncode


def write_locks(uv: List[str], *, align_to: Optional[str] = None,
                dev_align_to: Optional[str] = None, upgrade: bool = False,
                upgrade_packages: Sequence[str] = ()) -> int:
    """Compile the runtime lock, then the dev lock constrained by it."""
    rc = compile_lock(uv, LOCKS[RUNTIME_LOCK][0], RUNTIME_LOCK,
                      constraints=[align_to] if align_to else [],
                      upgrade=upgrade, upgrade_packages=upgrade_packages)
    if rc != 0:
        return rc
    stamp(REPO / RUNTIME_LOCK, inputs_digest(LOCKS[RUNTIME_LOCK][1]))

    rc = compile_lock(uv, LOCKS[DEV_LOCK][0], DEV_LOCK,
                      constraints=[RUNTIME_LOCK] + ([dev_align_to] if dev_align_to else []),
                      upgrade=upgrade, upgrade_packages=upgrade_packages)
    if rc != 0:
        return rc
    stamp(REPO / DEV_LOCK, inputs_digest(LOCKS[DEV_LOCK][1]))
    return 0


def verify_installed(which: str, python: Optional[str]) -> int:
    lock_name = RUNTIME_LOCK if which == "runtime" else DEV_LOCK
    try:
        pins = read_lock(REPO / lock_name)
        packages, markers = installed(Path(python) if python else None)
        found = differences(pins, packages, markers)
        count = applicable(pins, markers)
    except (LockError, OSError) as exc:
        print(f"cannot compare with {lock_name}: {exc}", file=sys.stderr)
        return 2
    if found:
        print(f"this environment is NOT {lock_name}:")
        for difference in found:
            print(f"  ! {difference}")
        return 1
    print(f"this environment is {lock_name}: {count} packages at the pinned "
          f"versions, and nothing the lock does not pin")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--check", action="store_true",
                    help="report whether the locks match the requirement files; change nothing")
    ap.add_argument("--verify-installed", choices=("runtime", "dev"), metavar="runtime|dev",
                    help="report every way an environment differs from that lock; change nothing")
    ap.add_argument("--python", metavar="PATH",
                    help="with --verify-installed: the interpreter of the environment to ask "
                         "(default: the one running this)")
    ap.add_argument("--upgrade", action="store_true",
                    help="let every package move to the newest version its bound allows")
    ap.add_argument("--upgrade-package", action="append", default=[], metavar="NAME",
                    help="let this one package move; repeatable")
    ap.add_argument("--align-to", metavar="FREEZE",
                    help="a `pip list --format=freeze` of an environment to pin the runtime to "
                         "(how the first lock was aligned to the lab instance)")
    ap.add_argument("--dev-align-to", metavar="FREEZE",
                    help="the same, for packages that only the dev lock holds")
    args = ap.parse_args(argv)

    if args.check:
        problems = stale_locks()
        for p in problems:
            print("STALE:", p)
        if not problems:
            print("locks match the requirement files")
        return 1 if problems else 0

    if args.verify_installed:
        return verify_installed(args.verify_installed, args.python)

    uv = find_uv()
    if uv is None:
        print("uv is needed to regenerate the locks, and only for that.\n"
              "    pip install uv        (anywhere on PATH; not into this environment)\n"
              "Installing from a lock, --check and --verify-installed need nothing but pip.",
              file=sys.stderr)
        return 2

    rc = write_locks(uv, align_to=args.align_to, dev_align_to=args.dev_align_to,
                     upgrade=args.upgrade, upgrade_packages=args.upgrade_package)
    if rc == 0 and (args.align_to or args.dev_align_to):
        # uv notes every constraint file beside the pins it touched ("# via -c
        # <path>"), and an alignment file lives on one person's machine. A
        # second, plain pass keeps every pin, because uv starts from the lock
        # that is already there, and writes the notes without that path.
        rc = write_locks(uv)
    if rc != 0:
        return rc

    print(f"wrote {RUNTIME_LOCK} and {DEV_LOCK}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
