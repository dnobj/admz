"""Which build is this? (GH #432)

``__version__`` is ``2.0.0`` and has been for months, so it cannot answer the
question an operator actually asks after a deploy: *am I looking at the latest
code, or the previous one?* Nothing on screen or in ``/api/health`` distinguished
two builds of the same version.

This is the third form of that question in this project, and the other two each
cost something:

* #424 — which **atlas** commit is production running? Nothing could say, and an
  ungated ``pwdgrp.cgi:add-user`` sat live for six days behind that gap.
* #426 — there is no written deploy procedure, so "did the deploy work?" had no
  defined answer either.

READ FROM THE CHECKOUT, NOT A BUILD STAMP
-----------------------------------------
ADR-0054 gives production its own clone, detached at a pinned commit, so the
commit is already on disk and true by construction. A stamp written at deploy
time would instead record what a deploy *intended* — and there is no deploy
script to write one (#426). Same reasoning as #424's content comparison: observe
the artefact, do not trust a note attached to it.

The dirty flag matters more than it looks. Production is supposed to be a clean
detached checkout; ``abc1234-dirty`` means someone edited files in place, which
is exactly the state that makes "which build is this?" unanswerable from the
commit alone.

Resolved once and cached — a page render must not shell out to git, and the
answer cannot change without a restart.
"""

from __future__ import annotations

import functools
import subprocess
from pathlib import Path
from typing import Optional

#: The repo root, relative to this file (``admz/build_info.py`` → repo).
_ROOT = Path(__file__).resolve().parents[1]


@functools.lru_cache(maxsize=1)
def build_id() -> Optional[str]:
    """Short commit of the running code, ``-dirty`` if the tree is modified.

    ``None`` when this is not a git checkout — an installed wheel, a container
    layer, a source tarball. That is a real deployment shape, so callers render
    nothing rather than "unknown", which would read as a fault.
    """
    if not (_ROOT / ".git").exists():
        return None
    try:
        sha = subprocess.run(
            ["git", "-C", str(_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if sha.returncode != 0 or not sha.stdout.strip():
            return None
        build = sha.stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(_ROOT), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        # A failed status check must not silently claim the tree is clean —
        # "clean" is the reassuring answer and the one it would be wrong to
        # guess at.
        if status.returncode != 0:
            return f"{build}-unverified"
        if status.stdout.strip():
            build += "-dirty"
        return build
    except (OSError, subprocess.SubprocessError):
        return None
