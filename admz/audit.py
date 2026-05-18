"""Audit log of who-did-what for ADMZ.

Closes the long-standing known gap KG-SEC-003: ``DeviceRegistry``
exposes a ``requester`` parameter on ``get_credentials`` for audit
purposes, but no backend has historically recorded anything. With
Phase 4 auth in place, every request now has a real
:class:`admz.auth.Principal` to attribute work to.

Schema (lives in the shared ADMZ SQLite database)::

    audit_log
    ---------
    id            INTEGER PRIMARY KEY AUTOINCREMENT
    timestamp     REAL     -- unix timestamp
    requester     TEXT     -- principal.name, e.g. "AXIS\\alice" or
                           --   "api-key:nightly-bot" or "anonymous"
    auth_source   TEXT     -- principal.source: windows / api-key / none
    action        TEXT     -- short verb-noun string, e.g. "get_credentials"
    resource      TEXT     -- what was acted on, e.g. "device:cam-01/account:default"
    details_json  TEXT     -- structured per-action data
    success       INTEGER  -- 0/1
    error_message TEXT     -- present iff !success

Writes are best-effort. If recording fails (e.g. DB locked), the
inability to audit must not break the underlying operation. The
caller's intent always wins; we log it where we can.

Designed for forward-only append; reads via :func:`list_recent` only
for the future ``/api/audit`` endpoint or operator inspection. No
schema-evolution machinery in v1 — the columns are deliberately
generic to avoid the need.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


_AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     REAL NOT NULL,
    requester     TEXT NOT NULL,
    auth_source   TEXT NOT NULL DEFAULT 'none',
    action        TEXT NOT NULL,
    resource      TEXT NOT NULL DEFAULT '',
    details_json  TEXT NOT NULL DEFAULT '{}',
    success       INTEGER NOT NULL DEFAULT 1,
    error_message TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_requester ON audit_log(requester);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
"""


@dataclass
class AuditEntry:
    id: int
    timestamp: float
    requester: str
    auth_source: str
    action: str
    resource: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: str = ""


def _default_db_path() -> Path:
    return Path(
        os.getenv("ADMZ_DB_PATH", str(Path.home() / ".admz" / "admz.db"))
    )


class AuditLog:
    """SQLite-backed audit log.

    Same connection model as the other ADMZ stores: per-call
    connections, WAL mode. Append is non-blocking-best-effort —
    callers should never have to handle audit-write failures.
    """

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
                conn.executescript(_AUDIT_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:  # pragma: no cover — defensive
            logger.warning("AuditLog table creation failed: %s", e)

    def record(
        self,
        *,
        requester: str,
        action: str,
        auth_source: str = "none",
        resource: str = "",
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: str = "",
    ) -> None:
        """Append one entry. Swallows DB errors with a warning log —
        an audit-write failure must never break the underlying op."""
        try:
            details_json = json.dumps(details or {}, default=str)
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO audit_log "
                    "(timestamp, requester, auth_source, action, resource, "
                    " details_json, success, error_message) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        time.time(),
                        requester or "unknown",
                        auth_source,
                        action,
                        resource,
                        details_json,
                        1 if success else 0,
                        error_message,
                    ),
                )
                conn.commit()
        except (sqlite3.Error, TypeError, ValueError) as e:
            logger.warning(
                "AuditLog.record(%r) failed: %s — skipping audit row",
                action, e,
            )

    def list_recent(
        self,
        *,
        limit: int = 100,
        action: Optional[str] = None,
        requester: Optional[str] = None,
        since: Optional[float] = None,
    ) -> List[AuditEntry]:
        """Read recent entries, newest first. Supports basic filtering."""
        clauses: List[str] = []
        params: List[Any] = []
        if action is not None:
            clauses.append("action = ?")
            params.append(action)
        if requester is not None:
            clauses.append("requester = ?")
            params.append(requester)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            "SELECT id, timestamp, requester, auth_source, action, "
            "resource, details_json, success, error_message "
            f"FROM audit_log {where} ORDER BY id DESC LIMIT ?"
        )
        params.append(limit)
        try:
            with self._connect() as conn:
                rows = conn.execute(sql, tuple(params)).fetchall()
        except sqlite3.Error as e:  # pragma: no cover
            logger.warning("AuditLog.list_recent failed: %s", e)
            return []

        results: List[AuditEntry] = []
        for row in rows:
            try:
                details = json.loads(row[6])
            except (json.JSONDecodeError, TypeError):
                details = {}
            results.append(AuditEntry(
                id=row[0],
                timestamp=row[1],
                requester=row[2],
                auth_source=row[3],
                action=row[4],
                resource=row[5],
                details=details,
                success=bool(row[7]),
                error_message=row[8],
            ))
        return results


# Module-level singleton — like capture_store, confirm_store, etc.
audit_log = AuditLog()


# ---------------------------------------------------------------------------
# Helper for handler code: record from a Principal directly
# ---------------------------------------------------------------------------


def record_event(
    principal,
    action: str,
    *,
    resource: str = "",
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: str = "",
    log: Optional[AuditLog] = None,
) -> None:
    """Convenience wrapper that pulls requester + auth_source from a
    :class:`admz.auth.Principal` and records one audit entry.

    Build a fresh AuditLog for each call to avoid stale-singleton
    problems when tests redirect ADMZ_DB_PATH after import. The store
    is cheap to construct (just a CREATE TABLE IF NOT EXISTS).
    """
    store = log if log is not None else AuditLog()
    requester = getattr(principal, "name", "unknown") if principal else "unknown"
    auth_source = getattr(principal, "source", "none") if principal else "none"
    store.record(
        requester=requester,
        auth_source=auth_source,
        action=action,
        resource=resource,
        details=details,
        success=success,
        error_message=error_message,
    )
