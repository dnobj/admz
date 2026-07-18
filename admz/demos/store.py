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
        self._db_path = str(db_path or _default_db_path())
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        conn = self._connect()
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


demo_store = DemoStore.__new__(DemoStore)  # lazily initialized singleton


def get_store() -> DemoStore:
    """Module singleton, initialized on first use so importing this module never
    touches the DB (keeps the leaf-light import contract)."""
    global demo_store
    if not hasattr(demo_store, "_db_path"):
        demo_store = DemoStore()
    return demo_store
