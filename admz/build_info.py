"""Which build is this? (GH #432, fixed for the service in #434)

``__version__`` is ``2.0.0`` and has been for months, so it cannot answer the
question an operator asks after a deploy: *am I looking at the latest code, or
the previous one?*

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
"""

from __future__ import annotations

import functools
import subprocess
from pathlib import Path
from typing import Optional

#: The repo root, relative to this file (``admz/build_info.py`` → repo).
_ROOT = Path(__file__).resolve().parents[1]

_SHORT = 7


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


@functools.lru_cache(maxsize=1)
def build_id() -> Optional[str]:
    """Short commit of the running code, with a suffix when relevant.

    * ``fcd22e1`` — clean tree.
    * ``fcd22e1-dirty`` — files edited in place. Production is meant to be a
      clean detached checkout, so this is the state that makes a commit alone a
      lie about what is running.
    * ``fcd22e1-unverified`` — the commit is known; git could not be asked about
      local edits. Normal for the service (see the module docstring).

    ``None`` only when there is no readable ``.git`` at all — an installed
    wheel, a container layer, a source tarball. Those are real deployment
    shapes, and ``None`` renders as nothing while "unknown" would read as a
    fault.
    """
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

    build = _read_head(git_dir)
    if not build:
        return None
    dirty = _worktree_is_dirty(_ROOT)
    if dirty is None:
        return f"{build}-unverified"
    return f"{build}-dirty" if dirty else build
