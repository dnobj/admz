"""The ``demo_inference_runs`` table (#124, slice 2) — provenance + the graph.

A direct mirror of ``demos/store.py``: a table, a dataclass, a thin store with
**per-call connections** and an explicit ``db_path`` constructor argument (the
singleton binds its path lazily on first use, so importing this module never
touches the DB and a test can bind its own path without polluting the real one).

The graph is stored because it is the audit trail behind every future proposal,
and because re-inference is a diff against the previous run. ``params_json``
pins the weights in force, so an old run stays explainable after the constants
change.

A run is also this feature's **long-running job record**. ``fast`` mode
completes inside the request; ``survey`` mode (discover → onboard → snapshot →
infer) runs in the background and reports progress through ``status`` / ``phase``
/ ``progress``, mirroring the only progress contract the codebase already has
(``plans/engine.py:508-536``'s ``{status, progress: "n/total"}``) and the
write-terminal-state-back discipline of ``fleet/health.py:934-951``.

**The ``demos`` table is untouched.** A run is evidence, never a demo — nothing
here is enumerated by ``list_demos`` or walked by ``fragments.attribution_maps``.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Job states. ``running`` is the only non-terminal one.
STATUS_RUNNING = "running"
STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"

MODE_FAST = "fast"
MODE_SURVEY = "survey"

#: Ordered survey phases, so a UI can render "3 of 4" without knowing the names.
SURVEY_PHASES = ("discover", "onboard", "snapshot", "collect")

#: A survey still ``running`` after this long belongs to a process that died —
#: it no longer blocks a new one (a restart must never wedge the feature).
SURVEY_STALE_SECONDS = 3600.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS demo_inference_runs (
    id            TEXT PRIMARY KEY,
    started_at    REAL NOT NULL DEFAULT 0,
    finished_at   REAL NOT NULL DEFAULT 0,
    created_by    TEXT NOT NULL DEFAULT '',
    acs_available INTEGER NOT NULL DEFAULT 0,
    acs_reason    TEXT NOT NULL DEFAULT '',
    device_count  INTEGER NOT NULL DEFAULT 0,
    rule_count    INTEGER NOT NULL DEFAULT 0,
    graph_json    TEXT NOT NULL DEFAULT '',
    params_json   TEXT NOT NULL DEFAULT ''
);
"""

#: Columns beyond the plan's documented schema, added the house way — an
#: idempotent try-ALTER per column (``demos/store.py:124-137``), so a DB created
#: from the plan's exact schema upgrades in place with no backfill.
_ADDED_COLUMNS = (
    ("mode", "TEXT NOT NULL DEFAULT 'fast'"),
    ("status", "TEXT NOT NULL DEFAULT 'complete'"),
    ("phase", "TEXT NOT NULL DEFAULT ''"),
    ("progress", "TEXT NOT NULL DEFAULT ''"),
    ("message", "TEXT NOT NULL DEFAULT ''"),
    ("error", "TEXT NOT NULL DEFAULT ''"),
    ("edge_count", "INTEGER NOT NULL DEFAULT 0"),
)

_COLS = ("id, started_at, finished_at, created_by, acs_available, acs_reason, "
         "device_count, rule_count, graph_json, params_json, mode, status, "
         "phase, progress, message, error, edge_count")


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


@dataclass
class InferenceRun:
    id: str = ""
    mode: str = MODE_FAST
    status: str = STATUS_RUNNING
    phase: str = ""
    progress: str = ""
    message: str = ""
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    created_by: str = ""
    acs_available: bool = False
    acs_reason: str = ""
    device_count: int = 0
    rule_count: int = 0
    edge_count: int = 0
    graph: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)

    def header(self) -> Dict[str, Any]:
        """The run without its graph — what a list view renders."""
        return {
            "id": self.id, "mode": self.mode, "status": self.status,
            "phase": self.phase, "progress": self.progress,
            "message": self.message, "error": self.error,
            "started_at": self.started_at, "finished_at": self.finished_at,
            "created_by": self.created_by,
            "acs": {"available": self.acs_available, "reason": self.acs_reason},
            "device_count": self.device_count, "rule_count": self.rule_count,
            "edge_count": self.edge_count,
            "summary": (self.graph or {}).get("summary"),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {**self.header(), "graph": self.graph, "params": self.params}


def _row(r) -> InferenceRun:
    """One DB row → a run.

    Corrupt stored JSON is **reported, not smoothed over**: the graph is this
    feature's audit trail, so a row whose ``graph_json`` will not parse has lost
    it, and a run that silently reads back as "complete, no graph" would hide
    that. The damage lands in ``error`` (and, for the graph itself, flips the
    run to ``failed``) so every reader — REST, MCP and the page — sees it.
    """
    corrupt: List[str] = []

    def _j(raw, default, field_name):
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (TypeError, ValueError) as exc:
            logger.warning("demo inference run %s: stored %s_json is corrupt (%s)",
                           r[0], field_name, exc)
            corrupt.append(field_name)
            return default

    run = InferenceRun(
        id=r[0], started_at=r[1], finished_at=r[2], created_by=r[3],
        acs_available=bool(r[4]), acs_reason=r[5] or "", device_count=r[6] or 0,
        rule_count=r[7] or 0, graph=_j(r[8], {}, "graph"),
        params=_j(r[9], {}, "params"),
        mode=r[10] or MODE_FAST, status=r[11] or STATUS_COMPLETE,
        phase=r[12] or "", progress=r[13] or "", message=r[14] or "",
        error=r[15] or "", edge_count=r[16] or 0,
    )
    if corrupt:
        note = ("stored " + " and ".join(corrupt) + " JSON is corrupt and could "
                "not be read — this run's record is damaged")
        run.error = f"{run.error}; {note}" if run.error else note
        if "graph" in corrupt:
            # Without its graph the run produced nothing usable, whatever the
            # status column still claims.
            run.status = STATUS_FAILED
    return run


class InferenceRunStore:
    """Thin SQLite store. Per-call connections (the app is multi-threaded)."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        from admz.paths import ensure_parent_dir
        ensure_parent_dir(self._db_path)
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            for name, decl in _ADDED_COLUMNS:
                try:
                    conn.execute(
                        f"ALTER TABLE demo_inference_runs ADD COLUMN {name} {decl}")
                except sqlite3.OperationalError as exc:
                    # Only "already there" is expected. A locked DB, a read-only
                    # file or a damaged schema would otherwise be swallowed here
                    # and reappear as an inexplicable missing column later.
                    if "duplicate column name" not in str(exc).lower():
                        raise
            conn.commit()
        finally:
            conn.close()

    # ── writes ──────────────────────────────────────────────────────────────

    def start(self, *, mode: str, created_by: str = "",
              message: str = "") -> InferenceRun:
        run = InferenceRun(
            id=uuid.uuid4().hex[:12], mode=mode, status=STATUS_RUNNING,
            phase=(SURVEY_PHASES[0] if mode == MODE_SURVEY else "collect"),
            progress=(f"0/{len(SURVEY_PHASES)}" if mode == MODE_SURVEY else "0/1"),
            message=message, started_at=time.time(), created_by=created_by,
        )
        conn = self._connect()
        try:
            conn.execute(
                f"INSERT INTO demo_inference_runs ({_COLS}) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run.id, run.started_at, 0.0, run.created_by, 0, "", 0, 0, "", "",
                 run.mode, run.status, run.phase, run.progress, run.message, "", 0),
            )
            conn.commit()
        finally:
            conn.close()
        return run

    def progress(self, run_id: str, *, phase: str, message: str = "",
                 step: Optional[int] = None, total: Optional[int] = None) -> None:
        """Record a phase transition. Best-effort: progress must never break a run."""
        prog = f"{step}/{total}" if step is not None and total else None
        sets = ["phase = ?"]
        vals: List[Any] = [phase]
        if message:
            sets.append("message = ?")
            vals.append(message)
        if prog:
            sets.append("progress = ?")
            vals.append(prog)
        vals.append(run_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE demo_inference_runs SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
        finally:
            conn.close()

    def finish(self, run_id: str, graph: Dict[str, Any], *,
               message: str = "") -> Optional[InferenceRun]:
        acs = (graph or {}).get("acs") or {}
        summary = (graph or {}).get("summary") or {}
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE demo_inference_runs SET status=?, phase=?, progress=?, "
                "finished_at=?, acs_available=?, acs_reason=?, device_count=?, "
                "rule_count=?, edge_count=?, graph_json=?, params_json=?, "
                "message=?, error='' WHERE id=?",
                (STATUS_COMPLETE, "done", "done", time.time(),
                 1 if acs.get("available") else 0, str(acs.get("reason") or ""),
                 int(summary.get("device_count") or 0),
                 int(summary.get("rule_count") or 0),
                 int(summary.get("edge_count") or 0),
                 json.dumps(graph, default=str),
                 json.dumps((graph or {}).get("params") or {}, default=str),
                 message, run_id),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get(run_id)

    def fail(self, run_id: str, error: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE demo_inference_runs SET status=?, finished_at=?, error=? "
                "WHERE id=?",
                (STATUS_FAILED, time.time(), str(error)[:500], run_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ── reads ───────────────────────────────────────────────────────────────

    def get(self, run_id: str) -> Optional[InferenceRun]:
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT {_COLS} FROM demo_inference_runs WHERE id = ?",
                (run_id,)).fetchone()
        finally:
            conn.close()
        return _row(row) if row else None

    def list(self, limit: int = 25) -> List[InferenceRun]:
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT {_COLS} FROM demo_inference_runs "
                "ORDER BY started_at DESC LIMIT ?", (int(limit),)).fetchall()
        finally:
            conn.close()
        return [_row(r) for r in rows]

    def latest(self) -> Optional[InferenceRun]:
        runs = self.list(limit=1)
        return runs[0] if runs else None

    def running(self, mode: Optional[str] = None,
                max_age: Optional[float] = None) -> List[InferenceRun]:
        """In-flight runs — the guard against two tabs starting the same survey.

        ``max_age`` (seconds) ignores rows left ``running`` by a process that
        died mid-survey; without it one crash would block deep surveys forever.
        """
        sql = (f"SELECT {_COLS} FROM demo_inference_runs WHERE status = ?")
        args: List[Any] = [STATUS_RUNNING]
        if mode:
            sql += " AND mode = ?"
            args.append(mode)
        if max_age:
            sql += " AND started_at > ?"
            args.append(time.time() - float(max_age))
        conn = self._connect()
        try:
            rows = conn.execute(sql + " ORDER BY started_at DESC", args).fetchall()
        finally:
            conn.close()
        return [_row(r) for r in rows]


run_store = InferenceRunStore.__new__(InferenceRunStore)  # lazy singleton


def get_run_store() -> InferenceRunStore:
    """Module singleton, initialized on first use so importing this module never
    touches the DB (the leaf-light import contract ``demos/store.py`` keeps)."""
    global run_store
    if not hasattr(run_store, "_db_path"):
        run_store = InferenceRunStore()
    return run_store
