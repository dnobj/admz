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
import threading
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

-- Full drift DIFF cache (one row per device). The signature/count above is a
-- cheap alerting hash; this holds the complete DriftReport.to_summary() so the
-- diff can be inspected / accepted / reverted instantly, without re-probing the
-- device. Written on every check_drift, so the background audit warms it. A
-- cached report may be stale (further drift can occur after it was computed) —
-- that's accepted by design and reconciled by the next audit.
CREATE TABLE IF NOT EXISTS drift_reports (
    device_id     TEXT PRIMARY KEY,
    report_json   TEXT NOT NULL,
    observed_sha  TEXT,
    signature     TEXT,
    computed_at   REAL NOT NULL
);
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
    # ADR-0063: a baseline facet the device is now known to lack is drift
    # with no fields. Fold it in ONLY when non-empty — unconditionally
    # appending would change every stored signature on deploy and fire a
    # fleet-wide "changed" storm for nothing.
    absent = sorted(getattr(report, "facets_absent", None) or [])
    if absent:
        blob += "|absent:" + json.dumps(absent, separators=(",", ":"))
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
    # ADR-0063: baseline facets the device is known to lack — drift with no
    # fields. Kept beside the bucket counts so the previous check's state is
    # recoverable for the transition decision.
    absent = sorted(getattr(report, "facets_absent", None) or [])
    if absent:
        counts["facets_absent"] = absent
    return counts


def _build_summary(
    transition: str, prev: int, curr: int, absent: Optional[List[str]] = None
) -> str:
    tail = ""
    if absent:
        tail = f" {len(absent)} baselined facet(s) absent: {', '.join(absent)}."
    if transition == "appeared":
        return f"Drift detected: {curr} field(s) now out of sync.{tail}"
    if transition == "cleared":
        return f"Drift cleared: device is back in sync (was {prev} field(s))."
    return f"Drift changed: {prev} → {curr} field(s).{tail}"


class DriftAlertStore:
    """SQLite-backed last-known-signature store + alert log."""

    def __init__(self, db_path: Optional[str] = None):
        """No I/O here -- constructing a store must not touch the filesystem,
        because this class backs a module-level singleton and anything done
        here happens at *import* (#254/#258)."""
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set = set()
        self._ready_lock = threading.Lock()

    @property
    def _db_path(self) -> str:
        """Resolved at CALL time, not cached at construction (#258).

        Caching in ``__init__`` is what froze the path: an ``ADMZ_HOME`` or
        ``ADMZ_DB_PATH`` set afterwards was ignored for the life of the
        process. Stays a ``str`` -- tests read this attribute and hand it
        straight to ``sqlite3.connect()``.
        """
        return self._explicit_db_path or str(_default_db_path())

    def _connect(self) -> sqlite3.Connection:
        path = self._db_path
        if path not in self._ready:  # fast path: no lock once warm
            with self._ready_lock:
                if path not in self._ready:  # double-checked
                    from admz.paths import ensure_parent_dir

                    ensure_parent_dir(path)
                    self._create_schema(path)
                    self._ready.add(path)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _create_schema(self, path: str) -> None:
        """Open our own connection -- via ``_connect`` this would recurse.

        ``_ready`` is keyed by path rather than a boolean, so a rebind runs
        the schema and its migrations against the new file instead of
        assuming the previous one's columns exist.

        Adds ADR-0047's `attributed` column to drift_signatures if absent.
        Swallowed exactly as before.
        """
        try:
            conn = sqlite3.connect(path)
            try:
                conn.executescript(_SCHEMA)
                # ADR-0047: attributed-counts column, added after first ship.
                try:
                    conn.execute(
                        "ALTER TABLE drift_signatures ADD COLUMN attributed TEXT"
                    )
                except sqlite3.OperationalError:
                    pass  # column already exists
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:  # pragma: no cover - defensive
            logger.warning("DriftAlertStore table creation failed: %s", exc)

    def _ensure_table(self) -> None:
        """Retained for callers that reach for it by name; ensuring now
        happens inside :meth:`_connect`."""
        self._connect().close()
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
        # Cache the full diff on every check (warms from the background audit) so
        # inspect/accept/revert can read it without re-probing the device.
        self.store_report(report)
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

        # Transition: decide which kind. "Drifted" means fields out of sync
        # OR a baselined facet the device is known to lack (ADR-0063) — the
        # latter has no fields, and without this a device whose only drift
        # is an absent facet would report "changed: 0 → 0 field(s)".
        absent_now = attributed.get("facets_absent") or []
        prev_attr = (previous.get("attributed") or {}) if previous else {}
        absent_before = bool(prev_attr.get("facets_absent"))
        drifted_now = current_count > 0 or bool(absent_now)
        drifted_before = prev_count > 0 or absent_before
        if not drifted_before and drifted_now:
            transition = "appeared"
        elif drifted_before and not drifted_now:
            transition = "cleared"
        else:
            transition = "changed"

        summary = _build_summary(transition, prev_count, current_count, absent_now)
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

    # ------------------------------------------------------------------
    # Full-report cache (the drift DIFF, for instant inspect/accept/revert)
    # ------------------------------------------------------------------

    def store_report(self, report: DriftReport) -> None:
        """Cache the complete drift report for a device (the full field-level
        diff), keyed by device_id. Called on every check_drift via
        :meth:`process_report`, so the background audit/health sweep warms it and
        an inspect can render the diff with no live device probe. Best-effort — a
        cache write must never break drift detection."""
        try:
            payload = json.dumps(report.to_summary(), separators=(",", ":"), default=str)
        except (TypeError, ValueError) as exc:  # pragma: no cover — defensive
            logger.warning("store_report: could not serialize %s: %s", report.device_id, exc)
            return
        try:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO drift_reports "
                    "(device_id, report_json, observed_sha, signature, computed_at) "
                    "VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(device_id) DO UPDATE SET "
                    "    report_json = excluded.report_json, "
                    "    observed_sha = excluded.observed_sha, "
                    "    signature = excluded.signature, "
                    "    computed_at = excluded.computed_at",
                    (report.device_id, payload, report.observed_sha,
                     _signature_for(report), time.time()),
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:  # pragma: no cover — defensive
            logger.warning("store_report failed for %s: %s", report.device_id, exc)

    def get_report(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Return the cached drift report, or None. Shape:
        ``{"report": <to_summary dict>, "observed_sha", "signature", "computed_at"}``.
        The report may be stale — ``computed_at`` is the freshness stamp."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT report_json, observed_sha, signature, computed_at "
                "FROM drift_reports WHERE device_id=?",
                (device_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        try:
            report = json.loads(row[0])
        except (TypeError, ValueError):
            return None
        return {
            "report": report,
            "observed_sha": row[1],
            "signature": row[2],
            "computed_at": row[3],
        }

    def clear_report(self, device_id: str) -> bool:
        """Drop a device's cached drift report (e.g. after a baseline change, so
        the next check recomputes). Returns True if a row existed."""
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM drift_reports WHERE device_id=?", (device_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

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
            existed = cursor.rowcount > 0
        finally:
            conn.close()
        # The cached diff is now stale (the next check will recompute) — drop it.
        self.clear_report(device_id)
        return existed


# Module-level singleton.
drift_alerts = DriftAlertStore()
