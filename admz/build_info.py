"""Which build is this? (GH #432, fixed for the service in #434)

When this was written ``__version__`` had read ``2.0.0`` for months, so it could
not answer the question an operator asks after a deploy: *am I looking at the
latest code, or the previous one?* A version names a release line, not a build
(see the last section), so that is still true of a version alone.

READ THE FILES, NOT `git`
------------------------
The first version shelled out to ``git rev-parse``. It worked everywhere it was
tested and returned ``None`` in the one place it was built for.

Production runs as the Windows service ``admz`` under **LocalSystem**, while the
checkout is owned by the operator's account. Git refuses to operate on a
repository owned by another user — *"detected dubious ownership"* — and exits
non-zero, with no ``safe.directory`` configured on this machine. So the service
asked git, git said no, and ``/api/health`` reported ``"build": null``.

Every test passed, because tests run as the user who owns the tree. **"It works
on my machine" for a service means "it works as the service account", and that
is a different machine.**

So the commit is read from ``.git`` directly. A file read has no ownership
opinion, it is faster than a subprocess, and it is a more literal reading of the
principle the first version claimed: observe the artefact, do not ask something
else about it. (Compare #424, which compares atlas *content* rather than
trusting recorded metadata.)

THE DIRTY FLAG STILL NEEDS `git`
--------------------------------
Nothing short of re-implementing index comparison can tell a clean tree from a
modified one, so that half still shells out — and when it cannot answer, it says
``-unverified`` rather than falling through to clean. "Clean" is the reassuring
answer and the wrong one to guess at, which is exactly the mistake that produced
``null`` above: a failure that renders as reassurance.

So in production the marker reads ``fcd22e1-unverified``: the commit is known
and true, and ADMZ is being honest that it cannot check for local edits from
where it stands.

A BUILD NAMES ITSELF (ADR-0075)
-------------------------------
Everything above is about a *checkout*. A site machine has no checkout: it
installs a build, and a build has no ``.git`` to read. So the step that makes a
build writes a stamp, ``admz/_build.json``, into the package, and the stamp
answers first::

    {"build": "2026.11.26.1", "commit": "<40 hex>",
     "catalog_commit": "<40 hex>", "built_at": "2026-11-26T14:03:00Z"}

Two rules, both about not rendering a failure as reassurance:

* **A stamp that cannot be trusted is reported as ``invalid-stamp``.** It does
  not fall back to git. An installed build with a broken stamp is a fault
  somebody has to see, and "the commit, from a ``.git`` that happens to be
  nearby" would hide it.
* **A checkout never carries a stamp.** The file is git-ignored and a test fails
  if one appears in the source tree, because a stray stamp would make every dev
  instance report a build it is not.

The version is the other half. ``__version__`` names the release the source is
working towards, several builds may carry it, and one of them is promoted. So
the full answer to "what is this?" is the pair: ``2.1.0 (2026.11.26.1)``.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

#: The repo root, relative to this file (``admz/build_info.py`` → repo).
_ROOT = Path(__file__).resolve().parents[1]

_SHORT = 7

#: Written into the installed package by the build step. Never in a checkout.
STAMP_NAME = "_build.json"

#: What ``build_id()`` answers for a stamp that exists and cannot be trusted.
INVALID_STAMP = "invalid-stamp"

#: A build id is a date and that day's count: ``2026.11.26.1`` (ADR-0075 §2).
_BUILD_ID = re.compile(r"^\d{4}\.(0[1-9]|1[0-2])\.(0[1-9]|[12]\d|3[01])\.[1-9]\d*$")
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Stamp:
    """What a build step recorded about the build it made."""

    build: str
    commit: str
    catalog_commit: Optional[str] = None
    built_at: Optional[str] = None


def _stamp_path() -> Path:
    """Beside this module, so it travels with the installed package."""
    return Path(__file__).with_name(STAMP_NAME)


def _read_stamp(path: Path):
    """``None`` when there is no stamp, a :class:`Stamp` when there is a good
    one, and :data:`INVALID_STAMP` when one exists and cannot be trusted.

    Three answers, because the third is the one that must not collapse into
    either of the others: a missing stamp means "this is a checkout, ask git",
    and a broken one means "this is an installed build that cannot say what it
    is".
    """
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return INVALID_STAMP
    if not isinstance(raw, dict):
        return INVALID_STAMP
    build, commit = raw.get("build"), raw.get("commit")
    if not isinstance(build, str) or not _BUILD_ID.match(build):
        return INVALID_STAMP
    if not isinstance(commit, str) or not _FULL_SHA.match(commit):
        return INVALID_STAMP
    catalog = raw.get("catalog_commit")
    if catalog is not None and not (isinstance(catalog, str) and _FULL_SHA.match(catalog)):
        return INVALID_STAMP
    built_at = raw.get("built_at")
    if built_at is not None and not isinstance(built_at, str):
        return INVALID_STAMP
    return Stamp(build=build, commit=commit, catalog_commit=catalog, built_at=built_at)


def _common_dir(git_dir: Path) -> Path:
    """Where refs live for ``git_dir``.

    A linked worktree's gitdir holds its own ``HEAD`` but **not** its refs —
    those live in the main repository, named by a ``commondir`` file. Resolving
    refs against the worktree gitdir finds nothing, which is how this returned
    None in every dev worktree while working in production's plain clone.
    """
    try:
        raw = (git_dir / "commondir").read_text(encoding="utf-8").strip()
    except OSError:
        return git_dir
    common = Path(raw)
    return common if common.is_absolute() else (git_dir / common).resolve()


def _read_head(git_dir: Path) -> Optional[str]:
    """The commit ``.git`` points at, without invoking git.

    Three shapes occur here: a detached checkout (production — ``HEAD`` holds
    the sha directly), a branch with a loose ref file, and a branch whose ref is
    packed (a freshly cloned or gc'd repo has no loose file).
    """
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not head.startswith("ref:"):
        return head[:_SHORT] if len(head) >= _SHORT else None

    ref = head.split(":", 1)[1].strip()
    for base in (git_dir, _common_dir(git_dir)):
        try:
            return (base / ref).read_text(encoding="utf-8").strip()[:_SHORT]
        except OSError:
            pass
        try:
            packed = (base / "packed-refs").read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in packed:
            if line.startswith("#") or " " not in line:
                continue
            sha, _, name = line.partition(" ")
            if name.strip() == ref:
                return sha[:_SHORT]
    return None


def _worktree_is_dirty(root: Path) -> Optional[bool]:
    """``True``/``False``, or ``None`` when git cannot be asked.

    ``None`` is a real answer here, not an error to swallow: it is what the
    service gets, and reporting it as "clean" would hide exactly the state the
    flag exists to reveal.
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return bool(r.stdout.strip())


def _git_dir() -> Optional[Path]:
    """The gitdir of the checkout this module sits in, or ``None``."""
    git_dir = _ROOT / ".git"
    if not git_dir.exists():
        return None
    # A worktree's .git is a file containing "gitdir: <path>"; production is a
    # clone, but dev work happens in worktrees and both must resolve.
    if git_dir.is_file():
        try:
            pointer = git_dir.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not pointer.startswith("gitdir:"):
            return None
        git_dir = Path(pointer.split(":", 1)[1].strip())
        if not git_dir.is_absolute():
            git_dir = (_ROOT / git_dir).resolve()
    return git_dir


@functools.lru_cache(maxsize=1)
def build_id() -> Optional[str]:
    """Which build is running.

    **An installed build** answers from its stamp:

    * ``2026.11.26.1`` — the build id the build step recorded.
    * ``invalid-stamp`` — a stamp exists and cannot be trusted. Deliberately not
      a fallback to git (see the module docstring).

    **A checkout** has no stamp and answers with the short commit:

    * ``fcd22e1`` — clean tree.
    * ``fcd22e1-dirty`` — files edited in place. The lab instance is meant to be
      a clean detached checkout, so this is the state that makes a commit alone
      a lie about what is running.
    * ``fcd22e1-unverified`` — the commit is known; git could not be asked about
      local edits. Normal for the service (see the module docstring).

    ``None`` only when there is neither a stamp nor a readable ``.git`` — a bare
    source tarball. ``None`` renders as nothing, while "unknown" would read as
    a fault.
    """
    stamp = _read_stamp(_stamp_path())
    if stamp is INVALID_STAMP:
        return INVALID_STAMP
    if stamp is not None:
        return stamp.build

    git_dir = _git_dir()
    if git_dir is None:
        return None
    build = _read_head(git_dir)
    if not build:
        return None
    dirty = _worktree_is_dirty(_ROOT)
    if dirty is None:
        return f"{build}-unverified"
    return f"{build}-dirty" if dirty else build


@dataclass(frozen=True)
class BuildInfo:
    """The whole answer to "what is this?": a version and a build.

    ``source`` says which of the two answered for the build: ``"stamp"`` for an
    installed build, ``"git"`` for a checkout, ``None`` when neither could.
    ``commit`` is the full commit for a stamped build and the short one for a
    checkout, which is all a checkout's ``HEAD`` is read for.
    """

    version: str
    build: Optional[str]
    commit: Optional[str]
    source: Optional[str]
    catalog_commit: Optional[str] = None
    built_at: Optional[str] = None

    @property
    def label(self) -> str:
        """``2.1.0 (2026.11.26.1)``, or just the version when no build is known."""
        return f"{self.version} ({self.build})" if self.build else self.version


@functools.lru_cache(maxsize=1)
def describe() -> BuildInfo:
    """Version, build, commit and where the answer came from.

    ``build`` is :func:`build_id` itself, so the two can never disagree about
    what is running.
    """
    from admz import __version__

    build = build_id()
    stamp = _read_stamp(_stamp_path())
    if stamp is INVALID_STAMP:
        return BuildInfo(version=__version__, build=build, commit=None, source="stamp")
    if stamp is not None:
        return BuildInfo(
            version=__version__, build=build, commit=stamp.commit, source="stamp",
            catalog_commit=stamp.catalog_commit, built_at=stamp.built_at,
        )
    if build is None:
        return BuildInfo(version=__version__, build=None, commit=None, source=None)
    git_dir = _git_dir()
    commit = _read_head(git_dir) if git_dir is not None else None
    return BuildInfo(version=__version__, build=build, commit=commit, source="git")


def identity_fields() -> dict:
    """The three keys every health answer carries, in one place.

    ``version`` and ``build`` are what a deploy check reads. ``commit`` is
    additive: the full commit for an installed build, the short one for a
    checkout, ``None`` when it is not known.
    """
    info = describe()
    return {"version": info.version, "build": info.build, "commit": info.commit}
