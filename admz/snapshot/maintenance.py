"""Snapshot repo maintenance — disk-usage reporting + safe git gc.

Closes KL-SNP-004: ``~/.admz/configs/`` grows monotonically as
snapshots accumulate. A fleet of 500 devices snapshotted daily for
a year produces a large repo. This module gives operators tooling
to (a) see how big it's gotten and (b) run a non-destructive
``git gc`` to reclaim space without touching history.

What we **do not** do:

  - Rewrite history (squash old commits, ``git filter-repo``, etc.).
    That's a deliberate human-led operation; ADMZ won't drop
    operator-visible commits behind their back.
  - Touch the remote. ``git gc`` is purely local.

Schedules can call :func:`run_gc` periodically to keep loose
object overhead bounded. The default is **off** — operators
explicitly enable via the ``snapshot_gc_enabled`` fleet setting.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from admz.snapshot.git_repo import GitRepo

logger = logging.getLogger(__name__)


@dataclass
class RepoStats:
    """Disk-usage and commit-count summary for the config repo."""

    repo_path: str
    total_bytes: int
    git_bytes: int
    fleet_bytes: int
    commit_count: int
    oldest_commit_iso: Optional[str] = None
    newest_commit_iso: Optional[str] = None

    @property
    def total_mb(self) -> float:
        return self.total_bytes / (1024 * 1024)

    @property
    def git_mb(self) -> float:
        return self.git_bytes / (1024 * 1024)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["total_mb"] = round(self.total_mb, 2)
        d["git_mb"] = round(self.git_mb, 2)
        return d


@dataclass
class GcResult:
    """Outcome of one ``git gc`` run."""

    ran: bool
    before_bytes: int
    after_bytes: int
    saved_bytes: int
    error: Optional[str] = None

    @property
    def saved_mb(self) -> float:
        return self.saved_bytes / (1024 * 1024)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["saved_mb"] = round(self.saved_mb, 2)
        return d


def _dir_size(path: Path) -> int:
    """Recursive directory size in bytes. Returns 0 for missing paths."""
    if not path.exists():
        return 0
    total = 0
    for sub in path.rglob("*"):
        try:
            if sub.is_file():
                total += sub.stat().st_size
        except OSError:
            # Permissions, vanished symlinks — skip silently.
            continue
    return total


def get_repo_stats(repo: GitRepo) -> RepoStats:
    """Inspect the config repo for size + commit history.

    Reads via ``git log`` for commit counts and dates so we don't
    have to walk the object database manually. Returns a
    populated :class:`RepoStats`; missing/empty repos report zeros
    rather than raising.
    """
    repo_path = repo.repo_path
    git_dir = repo_path / ".git"
    fleet_dir = repo_path / "fleet"

    git_bytes = _dir_size(git_dir)
    fleet_bytes = _dir_size(fleet_dir)
    total_bytes = _dir_size(repo_path)

    commit_count = 0
    oldest_iso: Optional[str] = None
    newest_iso: Optional[str] = None
    try:
        # %cI is committer date in strict ISO 8601.
        result = repo._run_git(
            "log", "--pretty=format:%cI", check=False
        )
        if result.returncode == 0:
            lines = [
                line.strip() for line in result.stdout.splitlines() if line.strip()
            ]
            commit_count = len(lines)
            if lines:
                # git log emits newest first.
                newest_iso = lines[0]
                oldest_iso = lines[-1]
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("get_repo_stats: git log failed: %s", exc)

    return RepoStats(
        repo_path=str(repo_path),
        total_bytes=total_bytes,
        git_bytes=git_bytes,
        fleet_bytes=fleet_bytes,
        commit_count=commit_count,
        oldest_commit_iso=oldest_iso,
        newest_commit_iso=newest_iso,
    )


def run_gc(repo: GitRepo, *, aggressive: bool = False) -> GcResult:
    """Run ``git gc`` against the config repo and report disk savings.

    Non-destructive: only packs loose objects, never drops commits.
    ``aggressive=True`` passes ``--aggressive`` for a slower but
    tighter pack — typically run as part of a weekly schedule.

    Returns a :class:`GcResult` carrying before/after byte counts.
    A failed gc is reported via ``error`` (non-raising) so callers
    in schedulers can surface the failure without aborting the
    rest of the maintenance run.
    """
    repo_path = repo.repo_path
    git_dir = repo_path / ".git"

    if not git_dir.exists():
        return GcResult(
            ran=False,
            before_bytes=0,
            after_bytes=0,
            saved_bytes=0,
            error="No .git directory at this path",
        )

    before = _dir_size(git_dir)

    args = ["gc"]
    if aggressive:
        args.append("--aggressive")
    # --prune=now drops unreachable loose objects older than this
    # invocation. Safe — we don't dangle objects on purpose.
    args.append("--prune=now")

    try:
        result = repo._run_git(*args, check=False)
        if result.returncode != 0:
            return GcResult(
                ran=False,
                before_bytes=before,
                after_bytes=before,
                saved_bytes=0,
                error=f"git {' '.join(args)} failed: {result.stderr.strip()}",
            )
    except Exception as exc:  # pragma: no cover — defensive
        return GcResult(
            ran=False,
            before_bytes=before,
            after_bytes=before,
            saved_bytes=0,
            error=str(exc),
        )

    after = _dir_size(git_dir)
    saved = max(before - after, 0)
    logger.info(
        "Snapshot repo gc complete: %.2f MB → %.2f MB (saved %.2f MB)",
        before / (1024 * 1024),
        after / (1024 * 1024),
        saved / (1024 * 1024),
    )
    return GcResult(
        ran=True,
        before_bytes=before,
        after_bytes=after,
        saved_bytes=saved,
    )


# ---------------------------------------------------------------------------
# Fleet-settings helpers
# ---------------------------------------------------------------------------

import admz.fleet_settings as _fs_module


_FS_GC_ENABLED = "snapshot_gc_enabled"
_FS_GC_AGGRESSIVE = "snapshot_gc_aggressive"


def _fs():
    return _fs_module.fleet_settings


def is_gc_enabled() -> bool:
    """Returns True when the operator has opted in to scheduled gc."""
    val = _fs().get(_FS_GC_ENABLED)
    if val is None:
        return False
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def set_gc_enabled(enabled: bool) -> None:
    _fs().set(_FS_GC_ENABLED, "true" if enabled else "false")


def is_gc_aggressive() -> bool:
    val = _fs().get(_FS_GC_AGGRESSIVE)
    if val is None:
        return False
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def set_gc_aggressive(aggressive: bool) -> None:
    _fs().set(_FS_GC_AGGRESSIVE, "true" if aggressive else "false")
