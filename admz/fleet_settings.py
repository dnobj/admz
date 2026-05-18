"""
Fleet-wide settings stored in the shared ADMZ SQLite database.

Provides a simple key-value store for configuration that applies
across all managed devices.  Uses the same database file as the
device registry and capture store.

Known keys:
  - ``default_password``: When set, ``provision_device`` uses this
    password instead of generating a random one per device.
  - ``default_username``: Admin username for provisioning (default: "admin").
    Used together with ``default_password`` as the fleet credential pair.
"""

import os
import sqlite3
from pathlib import Path
from typing import Dict, Optional


_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS fleet_settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""


def _default_db_path() -> Path:
    """Resolve the shared ADMZ SQLite database path."""
    return Path(
        os.getenv("ADMZ_DB_PATH", str(Path.home() / ".admz" / "admz.db"))
    )


class FleetSettings:
    """
    SQLite-backed key-value store for fleet-wide settings.

    Uses the same database file as the device registry so that both
    the MCP server and the API server see the same settings.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self):
        conn = self._connect()
        try:
            conn.executescript(_SETTINGS_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def get(self, key: str) -> Optional[str]:
        """Get a setting value by key. Returns None if not set."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT value FROM fleet_settings WHERE key=?", (key,)
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        """Set a setting value. Creates or updates the key."""
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO fleet_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, key: str) -> bool:
        """Delete a setting. Returns True if the key existed."""
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM fleet_settings WHERE key=?", (key,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def list_all(self) -> Dict[str, str]:
        """Return all settings as a dict."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT key, value FROM fleet_settings ORDER BY key"
            ).fetchall()
        finally:
            conn.close()
        return {k: v for k, v in rows}


# Module-level singleton.
fleet_settings = FleetSettings()
