"""A copy of the database and its key, taken before anything is switched.

FR-DEP-007. Before this, an upgrade of the lab instance had no backup step at
all, and the newest copy of its database anywhere was five months old
(review-2026-11-09, O-1). Since ADR-0068 the per-device password exists only in
that database, so a bad upgrade could cost the fleet's credentials.

THE DATABASE IS COPIED WITH SQLITE'S BACKUP API, NEVER AS A FILE. The service is
running while this happens and the database is in WAL mode: the newest
transactions sit in a second file beside it. A file copy takes the main file
without them, or half way through a checkpoint, and the result can open cleanly
and still be missing writes. The backup API reads through SQLite and gives one
consistent snapshot. The copy is then opened and checked before it is trusted.

The source is opened read-only. A backup must not be able to change what it is
protecting.

What this is not: scheduled backups, the config history, or a tested restore.
Those stay with #534. This is the copy an upgrade takes so that the upgrade
itself cannot be the thing that loses the database.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

DB_NAME = "admz.db"
KEY_NAME = "admz.key"
BACKUPS_DIR = "backups"
MANIFEST_NAME = "manifest.json"


class BackupError(RuntimeError):
    """The backup could not be taken or could not be trusted. Nothing was switched."""


@dataclass(frozen=True)
class Backup:
    folder: Path
    files: List[dict]            # {"name", "bytes", "sha256"}, one per file copied


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _copy_database(source: Path, dest: Path) -> None:
    try:
        src = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error as exc:
        raise BackupError(f"could not open {source} read-only: {exc}") from exc
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    except sqlite3.Error as exc:
        raise BackupError(f"could not copy {source.name}: {exc}") from exc
    finally:
        src.close()

    # Trust the copy only after SQLite has read every page of it.
    try:
        check = sqlite3.connect(str(dest))
        try:
            verdict = [row[0] for row in check.execute("PRAGMA integrity_check")]
        finally:
            check.close()
    except sqlite3.Error as exc:
        raise BackupError(f"the copy of {source.name} cannot be read back: {exc}") from exc
    if verdict != ["ok"]:
        raise BackupError(f"the copy of {source.name} fails SQLite's integrity check: "
                          f"{'; '.join(str(v) for v in verdict[:3])}")


def back_up(home: Path, label: str, *, now: Optional[datetime] = None) -> Backup:
    """Copy every database in ``home`` and its key into a new folder under
    ``home/backups``, and write a manifest of sizes and hashes.

    Every ``*.db`` at the top of the data folder is taken, not only ``admz.db``,
    so a store that one day keeps its own file is not silently left out.

    The folder is built under a ``.partial`` name and renamed at the end, so a
    folder without that suffix is always a complete backup. Raises
    :class:`BackupError` on any failure, and leaves no partial folder behind.
    """
    home = Path(home)
    databases = sorted(p for p in home.glob("*.db") if p.is_file())
    if not (home / DB_NAME).is_file():
        raise BackupError(f"{home} holds no {DB_NAME}; that is not an instance's data folder")
    key = home / KEY_NAME
    if not key.is_file():
        raise BackupError(
            f"{home} holds no {KEY_NAME}. The database cannot be read without its key, "
            f"so a backup without it would not be one")

    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-") or "backup"
    final = home / BACKUPS_DIR / f"{stamp}-{safe}"
    partial = final.with_name(final.name + ".partial")
    if final.exists() or partial.exists():
        raise BackupError(f"{final} already exists; a backup is never written over another")

    try:
        partial.mkdir(parents=True)
        for database in databases:
            _copy_database(database, partial / database.name)
        shutil.copy2(key, partial / KEY_NAME)

        files = []
        for path in sorted(partial.iterdir()):
            if path.is_file():
                files.append({"name": path.name, "bytes": path.stat().st_size,
                              "sha256": _sha256(path)})
        names = {entry["name"] for entry in files}
        wanted = {d.name for d in databases} | {KEY_NAME}
        if names != wanted:
            raise BackupError(f"the backup holds {sorted(names)}, expected {sorted(wanted)}")
        manifest = {
            "created_at": stamp,
            "label": label,
            "source": str(home),
            "files": files,
        }
        (partial / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        partial.rename(final)
    except BackupError:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    except OSError as exc:
        shutil.rmtree(partial, ignore_errors=True)
        raise BackupError(f"could not write the backup under {home / BACKUPS_DIR}: {exc}") from exc
    return Backup(folder=final, files=files)


def verify(folder: Path) -> List[str]:
    """Problems with a backup folder; empty when every file matches its manifest."""
    folder = Path(folder)
    try:
        manifest = json.loads((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
        entries = manifest["files"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"{folder} has no readable manifest: {exc}"]
    problems = []
    for entry in entries:
        path = folder / entry["name"]
        if not path.is_file():
            problems.append(f"{entry['name']} is missing")
        elif path.stat().st_size != entry["bytes"]:
            problems.append(f"{entry['name']} is {path.stat().st_size} bytes, "
                            f"the manifest says {entry['bytes']}")
        elif _sha256(path) != entry["sha256"]:
            problems.append(f"{entry['name']} does not match the hash in the manifest")
    return problems
