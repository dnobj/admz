"""The ``demo_proposals`` table (#124, slice 3) — one candidate demo.

Sits beside :mod:`admz.demos.inference.runs` and mirrors ``demos/store.py`` the
same way: a table, a dataclass, a thin store with **per-call connections** and an
explicit ``db_path`` constructor argument (the singleton binds lazily on first
use, so importing this module never touches the DB and a test can bind its own
path without polluting the real one).

**A proposal must not live in the ``demos`` table.** Anything in ``demos`` is
enumerated by ``list_demos``, rendered on ``/demos``, rolled into readiness and —
critically — walked by ``fragments.attribution_maps`` on *every* drift check.
A half-believed guess must never participate in drift attribution. Hence a
separate table, and a demo only ever comes into existence through an explicit
confirm.

Two identifiers, on purpose
---------------------------
``id`` is ``sha1(run_id + sorted member ids)[:12]`` — the plan's formula. It is
content-derived, so a given run always mints the same id for the same member
set, and two runs never collide on the primary key while both stay on the
record.

``content_key`` is ``sha1(sorted member ids)`` — **stable across runs**. It is
what "re-running over an unchanged environment reproduces the same proposals"
actually means once every run keeps its own row: the previous run's proposal for
the same devices is marked ``superseded``, and a member set the operator already
**dismissed** or **confirmed** is not proposed again.

Status lifecycle: ``proposed → confirmed | dismissed``, plus ``superseded`` when
a newer run re-proposes the same member set.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STATUS_PROPOSED = "proposed"
STATUS_CONFIRMED = "confirmed"
STATUS_DISMISSED = "dismissed"
STATUS_SUPERSEDED = "superseded"

#: Statuses that record an operator decision — never re-proposed by a later run.
DECIDED_STATUSES = (STATUS_CONFIRMED, STATUS_DISMISSED)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS demo_proposals (
    id                        TEXT PRIMARY KEY,
    run_id                    TEXT NOT NULL DEFAULT '',
    name                      TEXT NOT NULL DEFAULT '',
    purpose                   TEXT NOT NULL DEFAULT '',
    device_ids_json           TEXT NOT NULL DEFAULT '[]',
    roles_json                TEXT NOT NULL DEFAULT '{}',
    rules_json                TEXT NOT NULL DEFAULT '[]',
    evidence_json             TEXT NOT NULL DEFAULT '[]',
    suggested_owned_keys_json TEXT NOT NULL DEFAULT '[]',
    score                     REAL NOT NULL DEFAULT 0,
    confidence                TEXT NOT NULL DEFAULT 'low',
    flags_json                TEXT NOT NULL DEFAULT '[]',
    overlaps_json             TEXT NOT NULL DEFAULT '[]',
    status                    TEXT NOT NULL DEFAULT 'proposed',
    demo_id                   TEXT NOT NULL DEFAULT '',
    created_at                REAL NOT NULL DEFAULT 0,
    decided_at                REAL NOT NULL DEFAULT 0,
    decided_by                TEXT NOT NULL DEFAULT ''
);
"""

#: Columns beyond the plan's documented schema, added the house way — an
#: idempotent try-ALTER per column (``demos/store.py:124-137``), so a DB created
#: from the plan's exact schema upgrades in place with no backfill.
_ADDED_COLUMNS = (
    ("content_key", "TEXT NOT NULL DEFAULT ''"),
    ("score_breakdown_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("devices_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("proposed_name", "TEXT NOT NULL DEFAULT ''"),
)

_COLS = ("id, run_id, name, purpose, device_ids_json, roles_json, rules_json, "
         "evidence_json, suggested_owned_keys_json, score, confidence, "
         "flags_json, overlaps_json, status, demo_id, created_at, decided_at, "
         "decided_by, content_key, score_breakdown_json, devices_json, "
         "proposed_name")

_N_COLS = len(_COLS.split(","))


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


@dataclass
class DemoProposal:
    """One candidate demo — evidence plus a verdict, never a demo."""

    id: str = ""
    run_id: str = ""
    content_key: str = ""
    #: The working name — deterministic at creation, overwritten by whatever the
    #: operator (via the agent) supplies at confirm time.
    name: str = ""
    #: What the deterministic namer produced, written once at creation and
    #: **never overwritten**. ``name`` is a moving target the moment slice 4's
    #: narration lands, and without this the machine's own guess would be gone
    #: for good — so nobody could ever ask "was the heuristic any good, and by
    #: how much did the model improve on it?". That question is the evidence for
    #: keeping, tuning or deleting the naming heuristic, and it is the only part
    #: of this feature that would otherwise be unauditable after the fact.
    #: Empty on rows created before this column existed.
    proposed_name: str = ""
    #: Narrative guess. Agent-written (slice 4) and may stay empty forever — the
    #: deterministic ``name`` is what makes the feature work with no LLM at all.
    purpose: str = ""
    device_ids: List[str] = field(default_factory=list)
    roles: Dict[str, str] = field(default_factory=dict)
    rules: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    #: READ-ONLY evidence (resolved DECISION b) — confirm never writes these as
    #: fragments; the demo is created with an empty fragment set.
    suggested_owned_keys: List[Dict[str, Any]] = field(default_factory=list)
    score: float = 0.0
    confidence: str = "low"
    flags: List[str] = field(default_factory=list)
    overlaps: List[Dict[str, Any]] = field(default_factory=list)
    score_breakdown: Dict[str, Any] = field(default_factory=dict)
    devices: List[Dict[str, Any]] = field(default_factory=list)
    status: str = STATUS_PROPOSED
    demo_id: str = ""
    created_at: float = 0.0
    decided_at: float = 0.0
    decided_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "run_id": self.run_id, "content_key": self.content_key,
            "name": self.name, "proposed_name": self.proposed_name,
            "renamed": bool(self.proposed_name and self.proposed_name != self.name),
            "purpose": self.purpose,
            "device_ids": self.device_ids, "roles": self.roles,
            "rules": self.rules, "evidence": self.evidence,
            "suggested_owned_keys": self.suggested_owned_keys,
            "score": self.score, "confidence": self.confidence,
            "flags": self.flags, "overlaps": self.overlaps,
            "score_breakdown": self.score_breakdown, "devices": self.devices,
            "status": self.status, "demo_id": self.demo_id,
            "created_at": self.created_at, "decided_at": self.decided_at,
            "decided_by": self.decided_by,
        }

    def summary(self) -> Dict[str, Any]:
        """The list-view shape: the verdict without the full evidence dump."""
        return {
            "id": self.id, "run_id": self.run_id, "name": self.name,
            "proposed_name": self.proposed_name,
            "renamed": bool(self.proposed_name and self.proposed_name != self.name),
            "purpose": self.purpose, "score": self.score,
            "confidence": self.confidence, "flags": self.flags,
            "status": self.status, "demo_id": self.demo_id,
            "device_ids": self.device_ids,
            "device_names": [d.get("name") or d.get("device_id")
                             for d in self.devices] or self.device_ids,
            "rule_count": len(self.rules),
            "suggested_key_count": len(self.suggested_owned_keys),
            "overlap_count": len(self.overlaps),
        }


def _row(r) -> DemoProposal:
    """One DB row → a proposal. Corrupt stored JSON degrades that field to its
    default and is logged — a proposal is a suggestion, so a damaged evidence
    blob must not make the whole list unreadable."""
    def _j(raw, default, name):
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (TypeError, ValueError) as exc:
            logger.warning("demo proposal %s: stored %s is corrupt (%s)",
                           r[0], name, exc)
            return default

    return DemoProposal(
        id=r[0], run_id=r[1] or "", name=r[2] or "", purpose=r[3] or "",
        device_ids=_j(r[4], [], "device_ids_json"),
        roles=_j(r[5], {}, "roles_json"),
        rules=_j(r[6], [], "rules_json"),
        evidence=_j(r[7], [], "evidence_json"),
        suggested_owned_keys=_j(r[8], [], "suggested_owned_keys_json"),
        score=float(r[9] or 0.0), confidence=r[10] or "low",
        flags=_j(r[11], [], "flags_json"),
        overlaps=_j(r[12], [], "overlaps_json"),
        status=r[13] or STATUS_PROPOSED, demo_id=r[14] or "",
        created_at=float(r[15] or 0.0), decided_at=float(r[16] or 0.0),
        decided_by=r[17] or "", content_key=r[18] or "",
        score_breakdown=_j(r[19], {}, "score_breakdown_json"),
        devices=_j(r[20], [], "devices_json"),
        proposed_name=r[21] or "",
    )


class ProposalStore:
    """Thin SQLite store. Per-call connections (the app is multi-threaded)."""

    def __init__(self, db_path: Optional[str] = None):
        """No I/O here -- constructing a store must not touch the filesystem
        (#254/#258)."""
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set = set()
        self._ready_lock = threading.Lock()

    @property
    def _db_path(self) -> str:
        """Resolved at CALL time, not cached at construction (#258).

        Stays a ``str`` -- tests read this attribute and hand it straight to
        ``sqlite3.connect()``.
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

        _ADDED_COLUMNS onto demo_proposals. The non-duplicate re-raise is
        preserved: only 'already there' is swallowed.
        """
        conn = sqlite3.connect(path)
        try:
            conn.executescript(_SCHEMA)
            for name, decl in _ADDED_COLUMNS:
                try:
                    conn.execute(
                        f"ALTER TABLE demo_proposals ADD COLUMN {name} {decl}")
                except sqlite3.OperationalError as exc:
                    # Only "already there" is expected. A locked DB or a damaged
                    # schema would otherwise be swallowed here and reappear as an
                    # inexplicable missing column later.
                    if "duplicate column name" not in str(exc).lower():
                        raise
            conn.commit()
        finally:
            conn.close()

    def _ensure_table(self) -> None:
        """Retained for callers that reach for it by name; ensuring now
        happens inside :meth:`_connect`."""
        self._connect().close()
    def upsert(self, proposal: DemoProposal) -> DemoProposal:
        proposal.created_at = proposal.created_at or time.time()
        # Written once, at creation. A caller that only sets `name` (every
        # pre-slice-4 call site, and every test fixture) still gets its
        # deterministic guess preserved rather than an empty audit trail.
        proposal.proposed_name = proposal.proposed_name or proposal.name
        conn = self._connect()
        try:
            conn.execute(
                f"INSERT OR REPLACE INTO demo_proposals ({_COLS}) VALUES ("
                + ",".join("?" * _N_COLS) + ")",
                (proposal.id, proposal.run_id, proposal.name, proposal.purpose,
                 json.dumps(proposal.device_ids), json.dumps(proposal.roles),
                 json.dumps(proposal.rules, default=str),
                 json.dumps(proposal.evidence, default=str),
                 json.dumps(proposal.suggested_owned_keys, default=str),
                 float(proposal.score), proposal.confidence,
                 json.dumps(proposal.flags), json.dumps(proposal.overlaps),
                 proposal.status, proposal.demo_id, proposal.created_at,
                 proposal.decided_at, proposal.decided_by, proposal.content_key,
                 json.dumps(proposal.score_breakdown, default=str),
                 json.dumps(proposal.devices, default=str),
                 proposal.proposed_name),
            )
            conn.commit()
        finally:
            conn.close()
        return proposal

    def decide(self, proposal_id: str, status: str, *, decided_by: str = "",
               demo_id: str = "", name: Optional[str] = None,
               purpose: Optional[str] = None) -> Optional[DemoProposal]:
        """Record a terminal decision (or a supersede) on one proposal.

        ``name`` may be rewritten here (the operator's better name at confirm
        time); ``proposed_name`` is deliberately NOT in the SET list and must
        never be added to it — it is the record of what ADMZ itself guessed.
        """
        sets = ["status = ?", "decided_at = ?", "decided_by = ?"]
        vals: List[Any] = [status, time.time(), decided_by]
        if demo_id:
            sets.append("demo_id = ?")
            vals.append(demo_id)
        if name is not None:
            sets.append("name = ?")
            vals.append(name)
        if purpose is not None:
            sets.append("purpose = ?")
            vals.append(purpose)
        vals.append(proposal_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE demo_proposals SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
        finally:
            conn.close()
        return self.get(proposal_id)

    def supersede_open(self, content_key: str, *, except_id: str = "") -> int:
        """Mark still-open proposals for the same member set as ``superseded``.

        Only ``proposed`` rows move: a confirmed or dismissed proposal is an
        operator decision and stays exactly as decided.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE demo_proposals SET status = ? WHERE content_key = ? "
                "AND status = ? AND id <> ?",
                (STATUS_SUPERSEDED, content_key, STATUS_PROPOSED, except_id))
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def reopen_for_demo(self, demo_id: str) -> List[str]:
        """Undo the confirm of every proposal that became ``demo_id`` (#201).

        Called when that demo is deleted. Without it the row stays ``confirmed``
        forever, so :meth:`decided_content_keys` skips its member set on every
        future inference run and the cluster can never be proposed again — while
        ``dismiss`` refuses it with *"delete the demo instead"*, advice the
        operator has by then already taken.

        The row goes back to ``proposed`` rather than being deleted, so the
        evidence and score survive and **both** exits reopen: re-confirm with a
        corrected device list, or dismiss. ``demo_id``/``decided_at``/
        ``decided_by`` are cleared because a re-opened row has no current
        decision; the audit log keeps the history of the one it had.

        Returns the ids it re-opened, so the caller can record them.
        """
        if not demo_id:
            return []
        conn = self._connect()
        try:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM demo_proposals WHERE demo_id = ? AND status = ?",
                (demo_id, STATUS_CONFIRMED)).fetchall()]
            if ids:
                conn.execute(
                    "UPDATE demo_proposals SET status = ?, demo_id = '', "
                    "decided_at = 0, decided_by = '' "
                    "WHERE demo_id = ? AND status = ?",
                    (STATUS_PROPOSED, demo_id, STATUS_CONFIRMED))
                conn.commit()
            return ids
        finally:
            conn.close()

    def delete(self, proposal_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM demo_proposals WHERE id = ?",
                               (proposal_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    # ── reads ───────────────────────────────────────────────────────────────

    def get(self, proposal_id: str) -> Optional[DemoProposal]:
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT {_COLS} FROM demo_proposals WHERE id = ?",
                (proposal_id,)).fetchone()
        finally:
            conn.close()
        return _row(row) if row else None

    def list(self, *, status: Optional[str] = STATUS_PROPOSED,
             run_id: Optional[str] = None, limit: int = 200) -> List[DemoProposal]:
        """Proposals, strongest first. ``status=None`` returns every status."""
        sql = f"SELECT {_COLS} FROM demo_proposals"
        where: List[str] = []
        args: List[Any] = []
        if status:
            where.append("status = ?")
            args.append(status)
        if run_id:
            where.append("run_id = ?")
            args.append(run_id)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY score DESC, name COLLATE NOCASE LIMIT ?"
        args.append(int(limit))
        conn = self._connect()
        try:
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
        return [_row(r) for r in rows]

    def by_content_key(self, content_key: str) -> List[DemoProposal]:
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT {_COLS} FROM demo_proposals WHERE content_key = ? "
                "ORDER BY created_at DESC", (content_key,)).fetchall()
        finally:
            conn.close()
        return [_row(r) for r in rows]

    def decided_content_keys(self) -> Dict[str, DemoProposal]:
        """``{content_key: the decision}`` for every confirmed/dismissed member
        set — the memory that stops a re-run re-proposing what a human already
        answered."""
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT {_COLS} FROM demo_proposals WHERE status IN (?, ?) "
                "AND content_key <> '' ORDER BY decided_at ASC",
                DECIDED_STATUSES).fetchall()
        finally:
            conn.close()
        return {r[18]: _row(r) for r in rows}


# Plain module-level singleton (#258).
#
# This used to be ``ProposalStore.__new__(ProposalStore)`` -- an instance created WITHOUT
# running __init__ -- plus a ``hasattr(..., "_db_path")`` probe in the accessor
# to detect "not initialised yet" and construct it for real on first use. That
# shape existed for one reason: __init__ opened the database, so binding the
# name at import would have touched the filesystem, breaking the leaf-light
# import contract.
#
# Constructing a store is now free, so nothing needs deferring and the hack is
# gone. It was also about to become quietly wrong: with ``_db_path`` a property
# on the class, ``hasattr`` on an uninitialised instance only returns False
# because the getter raises AttributeError -- correct by accident, not by
# design.
#
# ``get_proposal_store()`` stays as the accessor most call sites use.
proposal_store = ProposalStore()


def get_proposal_store() -> ProposalStore:
    """The module singleton. Construction does no I/O; the database is opened
    on first use inside ``_connect``."""
    return proposal_store
