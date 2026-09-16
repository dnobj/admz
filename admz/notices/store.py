"""The notices store (ADR-0071 §1).

One table in ``admz.db``. A notice is keyed by ``subject_key`` —
``drift:<device_id>`` or ``event:<task_id>:<device_id|fleet>`` — and a partial
unique index allows at most one LIVE (open or snoozed) row per subject. A
producer that fires again therefore updates the row it already raised instead
of stacking a second one, and ``created_at`` keeps saying when the subject was
first seen.

What a row may hold is the other half of the contract: identifiers, counts,
class names and timestamps — never a parameter value, and never a
device-written name. A review note built from a row is a trusted ``[console]``
row (§4). The one free-text column, ``title``, holds ADMZ's own wording or an
operator's sanitized detection message, and the review note never quotes it.

Like every store here, construction does no I/O and the database path is
resolved at call time (#254/#258).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

KIND_DRIFT = "drift"
KIND_EVENT = "event"
KINDS = (KIND_DRIFT, KIND_EVENT)

STATUS_OPEN = "open"
STATUS_SNOOZED = "snoozed"
STATUS_HANDLED = "handled"
STATUS_EXPIRED = "expired"
STATUSES = (STATUS_OPEN, STATUS_SNOOZED, STATUS_HANDLED, STATUS_EXPIRED)
LIVE_STATUSES = (STATUS_OPEN, STATUS_SNOOZED)

#: The triage importance names (ADR-0070 §1), reused as notice severities.
SEVERITIES = ("low", "medium", "high")

#: An open notice nobody touched for this long expires.
EXPIRE_OPEN_AFTER_SECONDS = 30 * 86400
#: A closed notice is purged after this long; ``drift_alerts`` keeps the history.
PURGE_CLOSED_AFTER_SECONDS = 90 * 86400
#: Reads run the sweep at most this often, per process.
SWEEP_INTERVAL_SECONDS = 60.0

_LIVE_SQL = "('open', 'snoozed')"

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS notices (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    kind                    TEXT NOT NULL,
    subject_key             TEXT NOT NULL,
    severity                TEXT NOT NULL DEFAULT 'medium',
    title                   TEXT NOT NULL DEFAULT '',
    summary                 TEXT NOT NULL DEFAULT '{{}}',
    device_id               TEXT NOT NULL DEFAULT '',
    status                  TEXT NOT NULL DEFAULT 'open',
    source                  TEXT NOT NULL DEFAULT '',
    task_id                 TEXT NOT NULL DEFAULT '',
    occurrences             INTEGER NOT NULL DEFAULT 1,
    created_at              REAL NOT NULL,
    updated_at              REAL NOT NULL,
    snoozed_until           REAL,
    handled_at              REAL,
    handled_by              TEXT NOT NULL DEFAULT '',
    resolution              TEXT NOT NULL DEFAULT '',
    review_conversation_id  TEXT NOT NULL DEFAULT '',
    reviewed_at             REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_notices_live_subject
    ON notices(subject_key) WHERE status IN {_LIVE_SQL};
CREATE INDEX IF NOT EXISTS idx_notices_status_updated
    ON notices(status, updated_at);
"""

_COLS = (
    "id", "kind", "subject_key", "severity", "title", "summary", "device_id",
    "status", "source", "task_id", "occurrences", "created_at", "updated_at",
    "snoozed_until", "handled_at", "handled_by", "resolution",
    "review_conversation_id", "reviewed_at",
)
_SELECT = f"SELECT {', '.join(_COLS)} FROM notices"


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


@dataclass
class Notice:
    """One row of the attention queue."""

    id: int
    kind: str
    subject_key: str
    severity: str = "medium"
    title: str = ""
    summary: Dict[str, Any] = field(default_factory=dict)
    device_id: str = ""
    status: str = STATUS_OPEN
    source: str = ""
    task_id: str = ""
    occurrences: int = 1
    created_at: float = 0.0
    updated_at: float = 0.0
    snoozed_until: Optional[float] = None
    handled_at: Optional[float] = None
    handled_by: str = ""
    resolution: str = ""
    review_conversation_id: str = ""
    reviewed_at: Optional[float] = None

    @property
    def is_live(self) -> bool:
        return self.status in LIVE_STATUSES

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _row_to_notice(row: tuple) -> Notice:
    d = dict(zip(_COLS, row))
    try:
        summary = json.loads(d["summary"] or "{}")
    except (TypeError, ValueError):
        summary = {}
    return Notice(
        id=int(d["id"]),
        kind=d["kind"],
        subject_key=d["subject_key"],
        severity=d["severity"] or "medium",
        title=d["title"] or "",
        summary=summary if isinstance(summary, dict) else {},
        device_id=d["device_id"] or "",
        status=d["status"],
        source=d["source"] or "",
        task_id=d["task_id"] or "",
        occurrences=int(d["occurrences"] or 1),
        created_at=float(d["created_at"] or 0),
        updated_at=float(d["updated_at"] or 0),
        snoozed_until=d["snoozed_until"],
        handled_at=d["handled_at"],
        handled_by=d["handled_by"] or "",
        resolution=d["resolution"] or "",
        review_conversation_id=d["review_conversation_id"] or "",
        reviewed_at=d["reviewed_at"],
    )


class NoticeStore:
    """SQLite-backed attention queue (shares ``admz.db``)."""

    def __init__(self, db_path: Optional[str] = None):
        """No I/O: this class backs a module-level singleton (#254/#258)."""
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set = set()
        self._ready_lock = threading.Lock()
        self._last_sweep: Dict[str, float] = {}

    @property
    def _db_path(self) -> str:
        """Resolved at CALL time, never cached at construction (#258)."""
        return self._explicit_db_path or str(_default_db_path())

    def _connect(self) -> sqlite3.Connection:
        """An autocommit connection: writes that read first take the write
        lock explicitly with ``BEGIN IMMEDIATE``."""
        path = self._db_path
        if path not in self._ready:
            with self._ready_lock:
                if path not in self._ready:
                    from admz.paths import ensure_parent_dir

                    ensure_parent_dir(path)
                    self._create_schema(path)
                    self._ready.add(path)
        conn = sqlite3.connect(path, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _create_schema(self, path: str) -> None:
        conn = sqlite3.connect(path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ writes
    def raise_notice(
        self,
        *,
        kind: str,
        subject_key: str,
        title: str = "",
        summary: Optional[Dict[str, Any]] = None,
        device_id: str = "",
        severity: str = "medium",
        source: str = "",
        task_id: str = "",
        now: Optional[float] = None,
    ) -> Notice:
        """Open a notice, or refresh the live one for ``subject_key``.

        A refresh counts another occurrence, reopens a snoozed row (a new
        transition is new information) and keeps ``created_at``.
        """
        if kind not in KINDS:
            raise ValueError(f"unknown notice kind: {kind!r}")
        if severity not in SEVERITIES:
            raise ValueError(f"unknown notice severity: {severity!r}")
        if not subject_key:
            raise ValueError("a notice needs a subject_key")
        now = time.time() if now is None else float(now)
        payload = json.dumps(summary or {}, sort_keys=True, default=str)
        values = (kind, severity, title or "", payload, device_id or "",
                  source or "", task_id or "")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    f"SELECT id FROM notices WHERE subject_key=? AND status IN {_LIVE_SQL}",
                    (subject_key,),
                ).fetchone()
                if row is not None:
                    notice_id = int(row[0])
                    conn.execute(
                        "UPDATE notices SET kind=?, severity=?, title=?, summary=?, "
                        "device_id=?, source=?, task_id=?, status='open', "
                        "snoozed_until=NULL, occurrences=occurrences+1, "
                        "updated_at=? WHERE id=?",
                        (*values, now, notice_id),
                    )
                else:
                    cur = conn.execute(
                        "INSERT INTO notices (kind, severity, title, summary, "
                        "device_id, source, task_id, subject_key, status, "
                        "occurrences, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', 1, ?, ?)",
                        (*values, subject_key, now, now),
                    )
                    notice_id = int(cur.lastrowid)
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()
        return self.get(notice_id)  # type: ignore[return-value]

    def _close_live(self, where: str, args: tuple, *, status: str,
                    resolution: str, by: str, now: Optional[float]) -> Optional[Notice]:
        now = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    f"SELECT id FROM notices WHERE {where} AND status IN {_LIVE_SQL}",
                    args,
                ).fetchone()
                if row is None:
                    conn.execute("COMMIT")
                    return None
                conn.execute(
                    "UPDATE notices SET status=?, handled_at=?, handled_by=?, "
                    "resolution=?, snoozed_until=NULL WHERE id=?",
                    (status, now, by or "", resolution, row[0]),
                )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()
        return self.get(int(row[0]))

    def resolve(self, subject_key: str, resolution: str, by: str = "",
                now: Optional[float] = None) -> Optional[Notice]:
        """Close the live notice for ``subject_key`` (``cleared``,
        ``accepted``). None when nothing was live."""
        return self._close_live("subject_key=?", (subject_key,),
                                status=STATUS_HANDLED, resolution=resolution,
                                by=by, now=now)

    def handle(self, notice_id: int, resolution: str, by: str = "",
               now: Optional[float] = None) -> Optional[Notice]:
        """Close one live notice by id (``dismissed``). None when it is
        unknown or already closed."""
        return self._close_live("id=?", (int(notice_id),),
                                status=STATUS_HANDLED, resolution=resolution,
                                by=by, now=now)

    def snooze(self, notice_id: int, until: float) -> Optional[Notice]:
        """Hide a live notice until ``until``. Not new information about the
        subject, so ``updated_at`` stays. None when unknown or closed."""
        conn = self._connect()
        try:
            cur = conn.execute(
                f"UPDATE notices SET status='snoozed', snoozed_until=? "
                f"WHERE id=? AND status IN {_LIVE_SQL}",
                (float(until), int(notice_id)),
            )
            changed = cur.rowcount
        finally:
            conn.close()
        return self.get(int(notice_id)) if changed else None

    def mark_reviewed(self, notice_id: int, conversation_id: str,
                      now: Optional[float] = None) -> None:
        """Record which conversation a notice was opened into."""
        now = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE notices SET review_conversation_id=?, reviewed_at=? WHERE id=?",
                (conversation_id or "", now, int(notice_id)),
            )
        finally:
            conn.close()

    # ------------------------------------------------------------------- reads
    def get(self, notice_id: int) -> Optional[Notice]:
        conn = self._connect()
        try:
            row = conn.execute(f"{_SELECT} WHERE id=?", (int(notice_id),)).fetchone()
        finally:
            conn.close()
        return _row_to_notice(row) if row else None

    def get_live(self, subject_key: str) -> Optional[Notice]:
        conn = self._connect()
        try:
            row = conn.execute(
                f"{_SELECT} WHERE subject_key=? AND status IN {_LIVE_SQL}",
                (subject_key,),
            ).fetchone()
        finally:
            conn.close()
        return _row_to_notice(row) if row else None

    def has_any(self, subject_key: str) -> bool:
        """Whether any row, in any status, exists for ``subject_key``."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM notices WHERE subject_key=? LIMIT 1", (subject_key,),
            ).fetchone()
        finally:
            conn.close()
        return row is not None

    def list(
        self,
        *,
        status: Optional[str] = STATUS_OPEN,
        kind: Optional[str] = None,
        device_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Notice]:
        """Notices, most recently updated first. ``status`` is one status,
        ``"live"`` (open or snoozed), or None for every row."""
        self._maybe_sweep()
        clauses: List[str] = []
        args: List[Any] = []
        if status == "live":
            clauses.append(f"status IN {_LIVE_SQL}")
        elif status:
            clauses.append("status=?")
            args.append(status)
        if kind:
            clauses.append("kind=?")
            args.append(kind)
        if device_id:
            clauses.append("device_id=?")
            args.append(device_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        conn = self._connect()
        try:
            rows = conn.execute(
                f"{_SELECT}{where} ORDER BY updated_at DESC, id DESC LIMIT ?",
                (*args, max(1, int(limit))),
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_notice(r) for r in rows]

    def count_open(self) -> int:
        self._maybe_sweep()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM notices WHERE status='open'").fetchone()
        finally:
            conn.close()
        return int(row[0] if row else 0)

    # ------------------------------------------------------------------- sweep
    def sweep(self, now: Optional[float] = None) -> Dict[str, int]:
        """Wake past-due snoozes, expire open rows idle for 30 days, purge
        closed rows after 90."""
        now = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            woken = conn.execute(
                "UPDATE notices SET status='open', snoozed_until=NULL "
                "WHERE status='snoozed' AND snoozed_until <= ?",
                (now,),
            ).rowcount
            expired = conn.execute(
                "UPDATE notices SET status='expired', handled_at=?, "
                "resolution='expired' WHERE status='open' AND updated_at < ?",
                (now, now - EXPIRE_OPEN_AFTER_SECONDS),
            ).rowcount
            purged = conn.execute(
                "DELETE FROM notices WHERE status IN ('handled', 'expired') "
                "AND COALESCE(handled_at, updated_at) < ?",
                (now - PURGE_CLOSED_AFTER_SECONDS,),
            ).rowcount
        finally:
            conn.close()
        return {"woken": woken, "expired": expired, "purged": purged}

    def _maybe_sweep(self) -> None:
        path = self._db_path
        now = time.time()
        if now - self._last_sweep.get(path, 0.0) < SWEEP_INTERVAL_SECONDS:
            return
        self._last_sweep[path] = now
        self.sweep(now)


notices_store = NoticeStore()
