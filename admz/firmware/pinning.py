"""Artifact pinning for the firmware cache (GH #188, part 2).

#325 gated the *door* into the firmware cache. This records what came through
it, so a file that changes afterwards is detected before its bytes reach a
device.

What this is, said plainly
--------------------------
**Trust on first use. It is not firmware verification.**

* Where a digest is published upstream — Axis ships ``.bin.sha256`` sidecars for
  the oldest PACS models only, "not observed" for MPQT per the 2026-02-15 crawl
  in ``docs/AXIS_FTP_STRUCTURE.md`` — the artifact is checked against it and
  recorded :data:`STATE_UPSTREAM_VERIFIED`.
* Everywhere else — which is essentially the whole fleet — ADMZ records the
  digest of what it first saw and recorded :data:`STATE_PINNED`. That detects
  **substitution after entry** and nothing else. A malicious file imported on
  day one is pinned as authentic.

**None of this is what stops malicious firmware flashing.** The device enforces
a mandatory digital signature (VAPIX ``422``), and that belongs to the device.
ADMZ's contribution is catching substitution, silent downgrade to a
genuine-but-older signed image, and non-firmware content — before a maintenance
window is spent.

Why the digest is in SQLite and not a sidecar
---------------------------------------------
A ``.sha256`` file next to the artifact would live **in the directory the threat
model says the attacker can write**. Anyone able to swap ``X.bin`` can swap
``X.bin.sha256`` beside it, so a sidecar defends against accidental corruption
and not against the substitution this exists to catch. A trust anchor must not
sit inside the zone it vouches for.

It would also sit inside the directory ``executor/vapix.py::_upload_path_allowed``
vouches for, making the anchor itself uploadable.

The database is a different file, is where every other piece of ADMZ provenance
already lives (registry, audit, tasks, temp credentials since #314), and writing
a valid row into it is a materially higher bar than writing 65 bytes next to a
file. It is not an unbreakable anchor — nothing on the same host is — but it is
the stronger of the two available choices, chosen deliberately.

Pre-existing artifacts
----------------------
An install upgrading into this has a cache full of files with no record.
Refusing them would break a working install for no security gain — ADMZ has no
idea whether they are good, and saying "no" asserts knowledge it does not have.
They are :data:`STATE_UNPINNED`, allowed, logged loudly, and **adopted** on
first read so later reads are protected. An adopted record carries
``source='adopted'`` for exactly one reason: so nothing can later claim the
artifact was verified when all ADMZ did was write down what was already there.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

#: Checked against a digest Axis published. The only state that means "this is
#: the artifact the vendor shipped".
STATE_UPSTREAM_VERIFIED = "upstream_verified"

#: ADMZ recorded the bytes as they entered the cache. Detects later
#: substitution; asserts nothing about provenance.
STATE_PINNED = "pinned"

#: Present before pinning existed, or otherwise unrecorded. Allowed, never
#: claimed as anything.
STATE_UNPINNED = "unpinned"

SOURCE_DOWNLOAD = "download"
SOURCE_IMPORT = "import"
SOURCE_ADOPTED = "adopted"

_CHUNK = 65536


class FirmwareIntegrityError(Exception):
    """A cached artifact's bytes do not match what ADMZ recorded for it."""


def new_hasher():
    """A fresh SHA-256, so callers hash *as they write* rather than re-reading.

    Re-reading the file after writing it would compute a digest of whatever is
    on disk a moment later, which is the very substitution this is meant to
    catch. Every writer must feed this the same bytes it hands the filesystem.
    """
    return hashlib.sha256()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: str | Path) -> str:
    """Digest a file already on disk. Only for *adoption* of a pre-existing
    artifact, where there are no write-time bytes to hash by definition."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS firmware_artifacts (
    filename      TEXT PRIMARY KEY,
    sha256        TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    state         TEXT NOT NULL,
    source        TEXT NOT NULL,
    first_seen    REAL NOT NULL,
    last_verified REAL
);
"""


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


class ArtifactStore:
    """SQLite record of what entered the firmware cache.

    Keyed by **filename**, not absolute path: the artifact is identified by its
    name within the cache, so moving ``ADMZ_HOME`` does not orphan every record.

    Same connection model as the other ADMZ stores — no I/O in ``__init__``,
    path resolved at call time, short-lived connections, WAL (#258).
    """

    def __init__(self, db_path: Optional[str] = None):
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set = set()
        self._ready_lock = threading.Lock()

    @property
    def _db_path(self) -> str:
        return self._explicit_db_path or str(_default_db_path())

    def _connect(self) -> sqlite3.Connection:
        path = self._db_path
        if path not in self._ready:
            with self._ready_lock:
                if path not in self._ready:
                    from admz.paths import ensure_parent_dir

                    ensure_parent_dir(path)
                    self._create_schema(path)
                    self._ready.add(path)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _create_schema(self, path: str) -> None:
        conn = sqlite3.connect(path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # --- reads -------------------------------------------------------------

    def get(self, filename: str) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT filename, sha256, size_bytes, state, source, "
                "first_seen, last_verified FROM firmware_artifacts "
                "WHERE filename=?", (filename,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return {
            "filename": row[0], "sha256": row[1], "size_bytes": row[2],
            "state": row[3], "source": row[4], "first_seen": row[5],
            "last_verified": row[6],
        }

    def list_all(self) -> list:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT filename, sha256, size_bytes, state, source, "
                "first_seen, last_verified FROM firmware_artifacts "
                "ORDER BY filename").fetchall()
        finally:
            conn.close()
        return [{
            "filename": r[0], "sha256": r[1], "size_bytes": r[2],
            "state": r[3], "source": r[4], "first_seen": r[5],
            "last_verified": r[6],
        } for r in rows]

    # --- writes ------------------------------------------------------------

    def record(self, filename: str, sha256: str, size_bytes: int, *,
               state: str, source: str) -> None:
        """Record (or replace) an artifact's digest.

        Replacement is correct here: re-importing or re-downloading the same
        filename genuinely produces a new artifact, and its new digest is what
        subsequent reads must match. The *verification* decision happens at the
        read, against whatever this holds at that moment.
        """
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO firmware_artifacts (filename, sha256, size_bytes, "
                "state, source, first_seen, last_verified) VALUES (?,?,?,?,?,?,NULL) "
                "ON CONFLICT(filename) DO UPDATE SET sha256=excluded.sha256, "
                "size_bytes=excluded.size_bytes, state=excluded.state, "
                "source=excluded.source, first_seen=excluded.first_seen, "
                "last_verified=NULL",
                (filename, sha256, int(size_bytes), state, source, time.time()),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_verified(self, filename: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE firmware_artifacts SET last_verified=? WHERE filename=?",
                (time.time(), filename))
            conn.commit()
        finally:
            conn.close()


#: Module singleton, mirroring the other stores.
artifact_store = ArtifactStore()


def record_entry(path: str | Path, sha256: str, *, state: str,
                 source: str, store: Optional[ArtifactStore] = None) -> None:
    """Pin an artifact that has just been written into the cache."""
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError:
        size = 0
    (store or artifact_store).record(
        p.name, sha256, size, state=state, source=source)
    logger.info("Pinned firmware artifact %s (%s, source=%s) sha256=%s",
                p.name, state, source, sha256[:16])


def verify_bytes(path: str | Path, data: bytes, *,
                 store: Optional[ArtifactStore] = None) -> Tuple[str, str]:
    """Verify ``data`` against the record for ``path``.

    ``data`` must be **the exact bytes the caller is about to send**, not a
    re-read of the file — that is the whole point of doing this at the read
    rather than at approval time (``executor/vapix.py`` checks containment at
    one place and opens the file 130 lines later, with the human approval before
    both).

    Returns ``(state, digest)``. Raises :class:`FirmwareIntegrityError` on a
    mismatch.

    An artifact with no record is **adopted** rather than refused: an install
    upgrading into this has a cache full of unrecorded files, and refusing them
    would break a working install while asserting knowledge ADMZ does not have.
    The record is written with ``source='adopted'`` so nothing can later mistake
    "we wrote down what was already there" for "we verified it".
    """
    st = store or artifact_store
    p = Path(path)
    digest = hash_bytes(data)
    rec = st.get(p.name)

    if rec is None:
        st.record(p.name, digest, len(data),
                  state=STATE_UNPINNED, source=SOURCE_ADOPTED)
        logger.warning(
            "Firmware artifact %s had no recorded digest — ADMZ did not see it "
            "enter the cache, so it cannot be verified. Adopting sha256=%s so "
            "later reads are checked; this run is NOT verified (#188).",
            p.name, digest[:16],
        )
        return STATE_UNPINNED, digest

    if rec["sha256"] != digest:
        raise FirmwareIntegrityError(
            f"Firmware artifact {p.name} does not match what ADMZ recorded for "
            f"it: expected sha256 {rec['sha256'][:16]}…, found {digest[:16]}… "
            f"({rec['size_bytes']} bytes recorded, {len(data)} now). The file "
            "has changed since it entered the cache. DO NOT flash it. "
            "Re-import or re-download it from Axis and try again; if you did "
            "not replace it yourself, treat this host as suspect — the cache is "
            "the directory ADMZ trusts for uploads (#188)."
        )

    st.mark_verified(p.name)
    return rec["state"], digest
