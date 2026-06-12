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


def is_sensitive_setting_key(key: str) -> bool:
    """Return True if the setting's value should be masked when displayed.

    Used to keep passwords and other secrets out of any surface that returns
    fleet-settings to a caller — both the MCP ``get_fleet_settings`` tool and
    the REST ``GET /api/fleet/settings`` endpoint use this. Rules live in
    :mod:`admz.redact` (D-2), shared with the audit sanitizer and the chat
    display layer. (Note: ``pat`` now matches only as a discrete token —
    ``github_pat`` yes, a hypothetical ``*_path`` setting no.)
    """
    from admz.redact import is_sensitive_key

    return is_sensitive_key(key)


# ---------------------------------------------------------------------------
# Protected setting keys (CR-3)
# ---------------------------------------------------------------------------


# Fleet-setting keys that are protected from anonymous / MCP writes.
# Originally lived in admz/api/confirm_store.py — relocated here so the
# concept of "this is a sensitive fleet setting" lives next to the rest
# of fleet-settings policy. The confirm_store module re-exports the set
# under its original name for backward compatibility.
#
# Writes from MCP tools and from unauthenticated REST callers must
# refuse keys in this set. Writes from an authenticated principal
# (Windows IWA / API-key) are allowed — those callers are accountable
# via audit log.
PROTECTED_SETTING_KEYS = {
    "confirm_level_dangerous",
    "confirm_level_service-affecting",
    "confirm_level_normal",
    "confirm_level_read-only",
    "confirm_password_hash",
    "tool_get_credentials_enabled",
    # Chatbot provider API key. Set only via /settings/chat admin page;
    # MCP set_fleet_setting must never read or change it. See ADR-0025.
    "gemini_api_key",
    "gemini_default_model",
    # Device health monitor: opt-in background poller. Protected
    # because letting the LLM toggle a background loop that contacts
    # devices would be a sneak path around the safety gates.
    "health_monitor_enabled",
    "health_check_interval_seconds",
    "health_check_timeout_seconds",
    # Daily per-principal token budget (Phase 5D). Letting MCP rewrite
    # the budget through chat-driven tool calls would defeat the
    # purpose. Set only via the web UI.
    "chat_daily_token_budget",
    # Survey / contributor mode (opt-in, default OFF). The PAT is a real
    # secret stored encrypted; the rest gate a background loop that contacts
    # devices and opens GitHub PRs. Set only via the web UI, never MCP.
    "survey_mode_enabled",
    "survey_github_pat",
    "survey_repo",
    "survey_redaction_profile",
    "survey_validation_tier",
    "survey_schedule_seconds",
    "survey_contributor",
}


def is_protected_setting(key: str) -> bool:
    """Return True if ``key`` is in :data:`PROTECTED_SETTING_KEYS`.

    Used by REST handlers and the MCP ``set_fleet_setting`` tool to
    refuse writes to security-sensitive keys from low-privilege
    callers.
    """
    return key in PROTECTED_SETTING_KEYS


def mask_setting_value(value: str) -> str:
    """Return a display-safe placeholder for a sensitive setting value.

    Shows up to 8 asterisks plus a length hint. Empty values are returned
    as a fixed marker so the masking is unambiguous.
    """
    if not value:
        return "(empty)"
    return f"{'*' * min(len(value), 8)} ({len(value)} chars)"


def mask_settings_for_display(settings: Dict[str, str]) -> Dict[str, str]:
    """Return a copy of ``settings`` with sensitive values masked."""
    return {
        k: (mask_setting_value(v) if is_sensitive_setting_key(k) else v)
        for k, v in settings.items()
    }


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
