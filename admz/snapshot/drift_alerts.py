"""Drift-detection alerts — diff-against-last-known signature.

Closes the alerting half of KL-DRF-004. The DriftDetector
(``admz/snapshot/drift.py``) is pull-based — operators or
schedules invoke ``check_drift`` and get a snapshot of the
device's current diff against git. This module adds the
*alerting* half: persist the last-known drift signature per
device, and when a check runs, decide whether something has
*changed* compared to the previous check.

Three transition events are emitted:

  - ``appeared`` — device was in sync; drift fields appeared.
  - ``changed`` — device was already drifted; the set of drifted
    fields changed (new fields, removed fields, or different
    values for the same fields).
  - ``cleared`` — device was drifted; drift is now gone.

Each transition becomes a row in ``drift_alerts``:

    drift_alerts
    ------------
    id               INTEGER PRIMARY KEY AUTOINCREMENT
    timestamp        REAL    -- unix time
    device_id        TEXT
    transition       TEXT    -- "appeared" | "changed" | "cleared"
    previous_count   INTEGER -- field count before
    current_count    INTEGER -- field count after
    signature        TEXT    -- sha256 of the current drift set
    summary          TEXT    -- short human description

Operators query via the MCP tool ``list_drift_alerts(since=...)``
or the REST endpoint ``GET /api/drift/alerts``. The scheduler
invokes ``process_report(device_id, report)`` after every drift
sweep so alerts get recorded automatically.

Notes:

  - We persist a hash of the *fields* (facet+path+expected+actual),
    not the report itself, so signature equality is cheap.
  - "appeared" doesn't fire for a device's *first* drift check;
    we need a known baseline before we can claim drift "appeared".
    The first call sets the baseline; subsequent calls compare.
  - The DriftDetector is unchanged. This module is a separate
    consumer of its output.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from admz.snapshot.models import DriftReport

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass
class DriftAlert:
    """One transition row from the drift_alerts table."""

    id: int
    timestamp: float
    device_id: str
    transition: str  # "appeared" | "changed" | "cleared"
    previous_count: int
    current_count: int
    signature: str
    summary: str

    @property
    def timestamp_iso(self) -> str:
        return datetime.fromtimestamp(
            self.timestamp, tz=timezone.utc
        ).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp_iso"] = self.timestamp_iso
        return d


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


_SCHEMA = """
CREATE TABLE IF NOT EXISTS drift_signatures (
    device_id      TEXT PRIMARY KEY,
    signature      TEXT NOT NULL,
    field_count    INTEGER NOT NULL,
    updated_at     REAL NOT NULL,
    attributed     TEXT
);

CREATE TABLE IF NOT EXISTS drift_alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       REAL NOT NULL,
    device_id       TEXT NOT NULL,
    transition      TEXT NOT NULL,
    previous_count  INTEGER NOT NULL,
    current_count   INTEGER NOT NULL,
    signature       TEXT NOT NULL,
    summary         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_drift_alerts_ts ON drift_alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_drift_alerts_device ON drift_alerts(device_id);
"""


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


def _signature_for(report: DriftReport) -> str:
    """Stable hash of a report's drift-field set.

    Sorted on (facet, path) so the same set in different field
    order produces the same hash. Includes expected/actual values
    so a value-only change still counts as 'changed', and the
    attribution bucket/owner (ADR-0047) so adopting or deactivating
    a demo registers as one deliberate transition — not silence.
    """
    rows = sorted(
        (f.facet, f.path, f.expected, f.actual, f.bucket, f.owner or "")
        for f in report.fields
    )
    blob = json.dumps(rows, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _attributed_counts(report: DriftReport) -> Dict[str, Any]:
    """Per-bucket rollup of a report's fields (ADR-0047).

    ``by_demo`` counts demo_broken keys per owning demo — "is demo X's
    fragment intact on this device" — with names for display.
    """
    counts: Dict[str, Any] = {
        "unclaimed": 0, "candidate": 0, "demo_set": 0,
        "by_demo": {}, "demo_names": {},
    }
    for f in report.fields:
        if f.bucket == "demo_set":
            counts["demo_set"] += 1
        elif f.bucket == "candidate":
            counts["candidate"] += 1
        elif f.bucket == "demo_broken" and f.owner:
            counts["by_demo"][f.owner] = counts["by_demo"].get(f.owner, 0) + 1
        else:
            counts["unclaimed"] += 1
        if f.owner:
            counts["demo_names"][f.owner] = f.owner_name or f.owner
    return counts


def _build_summary(transition: str, prev: int, curr: int) -> str:
    if transition == "appeared":
        return f"Drift detected: {curr} field(s) now out of sync."
    if transition == "cleared":
        return f"Drift cleared: device is back in sync (was {prev} field(s))."
    return f"Drift changed: {prev} → {curr} field(s)."


class DriftAlertStore:
    """SQLite-backed last-known-signature store + alert log."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        try:
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
                # ADR-0047: attributed-counts column, added after first ship.
                try:
                    conn.execute(
                        "ALTER TABLE drift_signatures ADD COLUMN attributed TEXT"
                    )
                except sqlite3.OperationalError:
                    pass  # column already exists
                conn.commit()
        except sqlite3.Error as exc:  # pragma: no cover — defensive
            logger.warning("DriftAlertStore table creation failed: %s", exc)

    # ------------------------------------------------------------------
    # Signature bookkeeping
    # ------------------------------------------------------------------

    def get_last_signature(
        self, device_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the last-known signature row for ``device_id`` or None.

        Used internally by :meth:`process_report` to compute the
        transition. Exposed for tests + the future REST status
        endpoint.
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT signature, field_count, updated_at, attributed "
                "FROM drift_signatures WHERE device_id=?",
                (device_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        attributed = None
        if row[3]:
            try:
                attributed = json.loads(row[3])
            except (TypeError, ValueError):
                attributed = None
        return {
            "signature": row[0],
            "field_count": row[1],
            "updated_at": row[2],
            "attributed": attributed,
        }

    def _record_signature(
        self, device_id: str, signature: str, field_count: int,
        attributed: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = time.time()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO drift_signatures "
                "(device_id, signature, field_count, updated_at, attributed) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(device_id) DO UPDATE SET "
                "    signature   = excluded.signature, "
                "    field_count = excluded.field_count, "
                "    updated_at  = excluded.updated_at, "
                "    attributed  = excluded.attributed",
                (device_id, signature, field_count, now,
                 json.dumps(attributed) if attributed is not None else None),
            )
            conn.commit()
        finally:
            conn.close()

    def _record_alert(
        self,
        *,
        device_id: str,
        transition: str,
        previous_count: int,
        current_count: int,
        signature: str,
        summary: str,
    ) -> DriftAlert:
        now = time.time()
        conn = self._connect()
        try:
            cursor = conn.execute(
                "INSERT INTO drift_alerts "
                "(timestamp, device_id, transition, previous_count, "
                " current_count, signature, summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    now,
                    device_id,
                    transition,
                    previous_count,
                    current_count,
                    signature,
                    summary,
                ),
            )
            conn.commit()
            alert_id = cursor.lastrowid
        finally:
            conn.close()
        return DriftAlert(
            id=int(alert_id) if alert_id is not None else 0,
            timestamp=now,
            device_id=device_id,
            transition=transition,
            previous_count=previous_count,
            current_count=current_count,
            signature=signature,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    def process_report(self, report: DriftReport) -> Optional[DriftAlert]:
        """Compare ``report`` against the last-known signature.

        Updates the last-known signature in all cases. Emits an
        alert (and returns it) on a real transition. Returns
        ``None`` when nothing changed compared to last time.
        """
        device_id = report.device_id
        # field_count counts REAL drift only (ADR-0047): keys an active demo
        # deliberately set don't make the roster cry "drifted". The full
        # per-bucket breakdown rides in ``attributed``.
        current_count = len(report.real_fields)
        signature = _signature_for(report)
        attributed = _attributed_counts(report)

        previous = self.get_last_signature(device_id)
        prev_signature = previous["signature"] if previous else None
        prev_count = previous["field_count"] if previous else 0

        if previous is None:
            # First-ever observation: set baseline, no alert.
            self._record_signature(device_id, signature, current_count, attributed)
            return None

        if signature == prev_signature:
            # No change. Refresh the timestamp so age queries reflect
            # "we've seen this state recently" not "we haven't looked".
            self._record_signature(device_id, signature, current_count, attributed)
            return None

        # Transition: decide which kind.
        if prev_count == 0 and current_count > 0:
            transition = "appeared"
        elif prev_count > 0 and current_count == 0:
            transition = "cleared"
        else:
            transition = "changed"

        summary = _build_summary(transition, prev_count, current_count)
        alert = self._record_alert(
            device_id=device_id,
            transition=transition,
            previous_count=prev_count,
            current_count=current_count,
            signature=signature,
            summary=summary,
        )
        self._record_signature(device_id, signature, current_count, attributed)
        logger.info(
            "Drift alert recorded: %s/%s (%s)",
            device_id,
            transition,
            summary,
        )
        return alert

    def list_alerts(
        self,
        *,
        since: Optional[float] = None,
        device_id: Optional[str] = None,
        transitions: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[DriftAlert]:
        """Query alerts, newest first.

        ``since``: unix timestamp lower bound (inclusive).
        ``device_id``: filter to a single device.
        ``transitions``: any of "appeared" / "changed" / "cleared".
        """
        clauses: List[str] = []
        params: List[Any] = []
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        if device_id is not None:
            clauses.append("device_id = ?")
            params.append(device_id)
        if transitions:
            placeholders = ",".join("?" for _ in transitions)
            clauses.append(f"transition IN ({placeholders})")
            params.extend(transitions)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            "SELECT id, timestamp, device_id, transition, "
            "       previous_count, current_count, signature, summary "
            "FROM drift_alerts "
            f"{where} "
            "ORDER BY timestamp DESC "
            "LIMIT ?"
        )
        params.append(int(limit))

        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [
            DriftAlert(
                id=r[0],
                timestamp=r[1],
                device_id=r[2],
                transition=r[3],
                previous_count=r[4],
                current_count=r[5],
                signature=r[6],
                summary=r[7],
            )
            for r in rows
        ]

    def clear_baseline(self, device_id: str) -> bool:
        """Remove a device's last-known signature.

        Used when an operator wants the *next* drift check to
        re-establish the baseline (e.g. after intentionally
        accepting a change). Returns True if a row existed.
        """
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM drift_signatures WHERE device_id=?",
                (device_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


# Module-level singleton.
drift_alerts = DriftAlertStore()
