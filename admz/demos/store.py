"""SQLite store for demos (ADR-0046).

Mirrors the shape of ``admz/events/detections.py``: a table + a dataclass + a
thin store with per-call connections. Deliberately forward-compatible — ``roles``
and ``signals`` are JSON so Layer 4 can grow an ordered sequence + window
(``0041:76``) without a migration, and ``config_source`` is a string so a demo can
later reference something other than baseline/scenario.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS demos (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL DEFAULT '',
    narrative       TEXT NOT NULL DEFAULT '',
    tag             TEXT,
    device_ids_json TEXT NOT NULL DEFAULT '[]',
    roles_json      TEXT NOT NULL DEFAULT '{}',
    config_source   TEXT NOT NULL DEFAULT 'baseline',
    signals_json    TEXT NOT NULL DEFAULT '[]',
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_by      TEXT NOT NULL DEFAULT '',
    created_at      REAL NOT NULL DEFAULT 0,
    active          INTEGER NOT NULL DEFAULT 0
);
"""


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


@dataclass
class Demo:
    id: str
    name: str = ""
    narrative: str = ""
    # Scope: a tag OR an explicit device list (tag wins when both are set).
    tag: Optional[str] = None
    device_ids: List[str] = field(default_factory=list)
    # device_id -> role ("detector", "responder", …). Free-form on purpose.
    roles: Dict[str, str] = field(default_factory=dict)
    # "baseline" (the norm) | "scenario:<name>" (a sidelined demo).
    config_source: str = "baseline"
    # Expected signals: [{"device_id"|"role", "category"|"topic"}]. Unordered in
    # phase 1; Layer 4 adds order + window.
    signals: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True
    # ADR-0047: an ACTIVE demo's owned fragment counts toward each device's
    # expected state (drift attribution). Activation state is *intent* —
    # adopting marks active without pushing anything.
    active: bool = False
    # ADR-0050 Phase B: rules this demo created, as membership entries
    # {device_id, rule_id, rule_name, condition_id, condition_topic, created_at}.
    # SYSTEM-managed (not in DEMO_FIELDS) — mutated only by attach/detach, so a
    # metadata update never clobbers it.
    rules: List[Dict[str, Any]] = field(default_factory=list)
    created_by: str = ""
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "narrative": self.narrative,
            "tag": self.tag, "device_ids": self.device_ids, "roles": self.roles,
            "config_source": self.config_source, "signals": self.signals,
            "enabled": self.enabled, "active": self.active, "rules": self.rules,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }


def _row_to_demo(r) -> Demo:
    def _j(raw, default):
        try:
            return json.loads(raw) if raw else default
        except (TypeError, ValueError):
            return default
    return Demo(
        id=r[0], name=r[1], narrative=r[2], tag=r[3],
        device_ids=_j(r[4], []), roles=_j(r[5], {}),
        config_source=r[6] or "baseline", signals=_j(r[7], []),
        enabled=bool(r[8]), created_by=r[9], created_at=r[10],
        active=bool(r[11]), rules=_j(r[12] if len(r) > 12 else None, []),
    )


_SELECT = (
    "SELECT id, name, narrative, tag, device_ids_json, roles_json, "
    "config_source, signals_json, enabled, created_by, created_at, active, "
    "rules_json "
    "FROM demos"
)


class DemoStore:
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

        Two ALTER TABLE ADD COLUMN (ADR-0047's `active`, ADR-0050's
        `rules_json`), swallow-on-duplicate, byte-identical to before.
        """
        conn = sqlite3.connect(path)
        try:
            conn.executescript(_SCHEMA)
            # ADR-0047: activation flag, added after the table first shipped.
            try:
                conn.execute(
                    "ALTER TABLE demos ADD COLUMN active INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # column already exists
            # ADR-0050 Phase B: rule-membership list, added after first ship.
            try:
                conn.execute(
                    "ALTER TABLE demos ADD COLUMN rules_json TEXT NOT NULL DEFAULT '[]'"
                )
            except sqlite3.OperationalError:
                pass
            conn.commit()
        finally:
            conn.close()

    def _ensure_table(self) -> None:
        """Retained for callers that reach for it by name; ensuring now
        happens inside :meth:`_connect`."""
        self._connect().close()
    def list(self) -> List[Demo]:
        conn = self._connect()
        try:
            rows = conn.execute(_SELECT + " ORDER BY name COLLATE NOCASE").fetchall()
        finally:
            conn.close()
        return [_row_to_demo(r) for r in rows]

    def get(self, demo_id: str) -> Optional[Demo]:
        conn = self._connect()
        try:
            row = conn.execute(_SELECT + " WHERE id = ?", (demo_id,)).fetchone()
        finally:
            conn.close()
        return _row_to_demo(row) if row else None

    def create(self, demo: Demo) -> Demo:
        demo.id = demo.id or uuid.uuid4().hex[:12]
        demo.created_at = demo.created_at or time.time()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO demos (id, name, narrative, tag, device_ids_json, "
                "roles_json, config_source, signals_json, enabled, created_by, "
                "created_at, active, rules_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (demo.id, demo.name, demo.narrative, demo.tag,
                 json.dumps(demo.device_ids), json.dumps(demo.roles),
                 demo.config_source, json.dumps(demo.signals),
                 1 if demo.enabled else 0, demo.created_by, demo.created_at,
                 1 if demo.active else 0, json.dumps(demo.rules or [])),
            )
            conn.commit()
        finally:
            conn.close()
        return demo

    def update(self, demo: Demo) -> Demo:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE demos SET name=?, narrative=?, tag=?, device_ids_json=?, "
                "roles_json=?, config_source=?, signals_json=?, enabled=?, "
                "active=?, rules_json=? WHERE id=?",
                (demo.name, demo.narrative, demo.tag, json.dumps(demo.device_ids),
                 json.dumps(demo.roles), demo.config_source,
                 json.dumps(demo.signals), 1 if demo.enabled else 0,
                 1 if demo.active else 0, json.dumps(demo.rules or []), demo.id),
            )
            conn.commit()
        finally:
            conn.close()
        return demo

    def delete(self, demo_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM demos WHERE id = ?", (demo_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


# Plain module-level singleton (#258).
#
# This used to be ``DemoStore.__new__(DemoStore)`` -- an instance created WITHOUT
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
# ``get_store()`` stays as the accessor most call sites use.
demo_store = DemoStore()


def get_store() -> DemoStore:
    """The module singleton. Construction does no I/O; the database is opened
    on first use inside ``_connect``."""
    return demo_store
