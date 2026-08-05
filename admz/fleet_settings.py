"""
Fleet-wide settings stored in the shared ADMZ SQLite database.

Provides a simple key-value store for configuration that applies
across all managed devices.  Uses the same database file as the
device registry and capture store.

The full key inventory lives in :mod:`admz.setting_policy`, together with the
allow-set that decides which of them the chat model may write (ADR-0053).
The two it may write are the fleet credential pair:

  - ``default_password``: When set, ``provision_device`` uses this
    password instead of generating a random one per device. Its *value* never
    comes from chat — the model requests an out-of-band capture URL and a
    human types it into a browser (ADR-0009, FR-MCP-008).
  - ``default_username``: Admin username for provisioning (default: "admin").
    Used together with ``default_password`` as the fleet credential pair.

Every other key is refused from MCP; an operator sets it from the web UI or
with ``python -m admz settings set``.

**Secret values are encrypted at rest** (GH #296, ADR-0010). The store — not
each caller — encrypts the keys in
:data:`admz.setting_policy.STORE_ENCRYPTED_SETTING_KEYS`, so every reader and
writer above is unchanged and none of them can forget. Legacy plaintext is
migrated in place on first :meth:`FleetSettings.get`. See
:mod:`admz.setting_crypto`.
"""

import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple

from admz.confirm_policy import (
    _DEFAULT_CONFIRMATION_LEVELS,
    confirm_level_key,
    is_confirm_level_key,
)
from admz.setting_policy import (  # noqa: F401 — re-exported for callers
    KNOWN_SETTING_KEYS,
    LLM_WRITABLE_SETTING_KEYS,
    STORE_ENCRYPTED_SETTING_KEYS,
    is_capture_only,
    is_llm_writable,
    is_store_encrypted,
)

logger = logging.getLogger(__name__)


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


# Every known fleet-setting key that the chat model may NOT write.
#
# **This set no longer decides anything.** :func:`is_protected_setting` does,
# and it consults :func:`admz.setting_policy.is_llm_writable` — a key absent
# from every list here is still refused, because ADR-0053 made refusal the
# default. The set survives, derived, for two reasons:
#
#   1. Nine test sites and five specification documents refer to it by name.
#      Deleting it to make a point would turn nine assertions into assertions
#      about nothing — the exact vacuity GH #152 slipped through.
#   2. "Which keys are protected?" is a real question an operator and a
#      reviewer ask, and it deserves an answer that cannot go stale.
#
# Derived, never hand-maintained: the confirm_level_* names come from the
# policy table (GH #152 — the table grew an ACS Pro `action` risk and this set
# did not, so the LLM could write confirm_level_action=none and remove the
# gate from 68 operations), and everything else is the key inventory minus the
# allow-set. Adding a setting to admz/setting_policy.py updates this for free.
PROTECTED_SETTING_KEYS = {
    *(confirm_level_key(risk) for risk in _DEFAULT_CONFIRMATION_LEVELS),
    *(KNOWN_SETTING_KEYS - LLM_WRITABLE_SETTING_KEYS),
}


def is_protected_setting(key: str) -> bool:
    """Return True if ``key`` may not be written by a low-privilege caller.

    **Deny by default (ADR-0053).** A key is protected unless it is declared
    in :data:`admz.setting_policy.LLM_WRITABLE_SETTING_KEYS`. An unknown key —
    including one added tomorrow and never declared anywhere — is protected,
    which is the failure direction ADR-0020's enumerated deny-list had
    backwards.

    Two overlapping rules, the first now redundant and kept anyway:

    * anything in the ``confirm_level_*`` namespace
      (:func:`admz.confirm_policy.is_confirm_level_key`). Redundant under
      inversion, because those keys are not in the allow-set either. It stays
      because it costs nothing, it can only ever refuse *more*, and it covers
      keys built at runtime — which the static guard in
      ``tests/test_setting_policy.py`` cannot see. A mistaken entry in the
      allow-set therefore still cannot reopen GH #152.
    * not being declared LLM-writable.

    Used by the MCP ``set_fleet_setting`` tool
    (``admz/mcp/server.py::_set_fleet_setting``, the one production caller)
    and by the out-of-band capture write path
    (``admz/api/routes/capture.py``). Authenticated web writers are unaffected;
    an operator sets a protected key from the web UI or with
    ``python -m admz settings set``.
    """
    return is_confirm_level_key(key) or not is_llm_writable(key)


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
    from admz.paths import db_path
    return db_path()


class FleetSettings:
    """
    SQLite-backed key-value store for fleet-wide settings.

    Uses the same database file as the device registry so that both
    the MCP server and the API server see the same settings.
    """

    def __init__(self, db_path: Optional[str] = None):
        """No I/O here — see ADR-0042's call-time contract and #258.

        This class backs the ``fleet_settings`` module singleton below, which
        is imported at module scope by ~15 modules in ``admz/`` and reached
        from ~120 sites overall. Anything done here therefore happens during
        *their* import, which is how a fresh install used to die before it
        started and how the suite could reach a real database.
        """
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set = set()
        self._ready_lock = threading.Lock()

    @property
    def _db_path(self) -> str:
        """Resolved at CALL time, not cached at construction.

        Caching in ``__init__`` is what froze the path — an ``ADMZ_HOME`` or
        ``ADMZ_DB_PATH`` set afterwards was ignored for the life of the
        process. Deferring construction does not fix that: measured, the
        stores that were already lazy froze identically, just later.

        Stays a ``str`` — tests read this attribute and pass it straight to
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
        """Open our own connection — routing through ``_connect`` would recurse.

        ``_ready`` is keyed by path rather than being a boolean, so a rebind
        runs the schema against the new file instead of assuming the previous
        one's tables exist. Failures propagate, as they did when this ran from
        ``__init__``; only the moment moved.
        """
        conn = sqlite3.connect(path)
        try:
            conn.executescript(_SETTINGS_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _ensure_table(self):
        """Retained for callers that reach for it by name; ensuring now happens
        inside :meth:`_connect`."""
        self._connect().close()

    def _raw_get(self, key: str) -> Optional[str]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT value FROM fleet_settings WHERE key=?", (key,)
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row else None

    def get(self, key: str) -> Optional[str]:
        """Get a setting value by key. Returns None if not set.

        Secrets (GH #296) are decrypted here rather than at each call site.
        ``default_password`` alone has three readers with no accessor between
        them, and they already share this one path — so this is where a caller
        cannot forget to decrypt. Callers see plaintext and are unchanged.

        A legacy plaintext value is **migrated in place on first read**: it is
        re-written encrypted before being returned, so the plaintext stops
        existing rather than merely being superseded. Migration failure is
        swallowed — a read-only or locked DB must not break a read that
        otherwise succeeded; the value is simply migrated on a later read.

        That last sentence is also the gap GH #307 found: "on a later read"
        assumes a later read happens. A key nothing reads — the ACS webhook
        token is only touched when ACS fires or an operator opens its settings
        page — can sit in plaintext indefinitely even though it is declared
        encrypted. See :meth:`migrate_encrypted_settings` for the eager sweep
        that closes that gap; it shares this method's migration logic rather
        than reimplementing it.
        """
        plain, _ = self._get_with_migration_flag(key)
        return plain

    def _get_with_migration_flag(self, key: str) -> Tuple[Optional[str], bool]:
        """Do what :meth:`get` does, and also report whether migration ran.

        Split out so :meth:`migrate_encrypted_settings` (GH #307) can drive
        the exact same read/decrypt/migrate-in-place path — including the
        undecryptable-vs-legacy-plaintext distinction and the swallow-on-
        write-failure behavior — without a second copy of this logic to keep
        in sync. ``get()`` is unchanged for its ~120 existing call sites.
        """
        raw = self._raw_get(key)
        if not is_store_encrypted(key):
            return raw, False
        from admz import setting_crypto

        plain, needs_migration = setting_crypto.read_stored(key, raw)
        migrated = False
        if needs_migration:
            try:
                self._raw_set(key, setting_crypto.encrypt(plain or ""))
                migrated = True
                logger.info(
                    "Migrated fleet setting %r to encrypted storage (#296).", key)
            except Exception:  # noqa: BLE001 — a read must still succeed
                logger.warning(
                    "Could not migrate fleet setting %r to encrypted storage; "
                    "it stays plaintext and will be retried on the next read.",
                    key, exc_info=True)
        return plain, migrated

    def migrate_encrypted_settings(self) -> Dict[str, int]:
        """Eagerly convert every declared secret key still at legacy plaintext.

        GH #307: :meth:`get` only migrates a key when something reads it, so a
        cold key stays plaintext forever if nothing ever does — measured on the
        live database, where ``default_password`` and ``gemini_api_key`` (read
        constantly) converted and ``acs_webhook_token`` (read only when ACS
        fires a rule, or an operator opens its settings page) did not. This
        makes "declared encrypted" and "stored encrypted" the same claim for
        *every* key in :data:`admz.setting_policy.STORE_ENCRYPTED_SETTING_KEYS`,
        not just the popular ones.

        Calls :meth:`_get_with_migration_flag` once per declared key — the same
        path an ordinary read already takes, so there is no second migration
        implementation to drift from the tested one. A key whose read or write
        fails (locked DB, missing key file) is counted and logged, never
        raised: intended to run unattended at startup, where one bad key must
        not block the others or the process coming up. Idempotent — running it
        again finds nothing left to convert.

        Returns a summary dict (``checked`` / ``migrated`` / ``failed`` counts)
        for the caller to log; see ``admz/api/main.py::lifespan``.
        """
        checked = 0
        migrated = 0
        failed = 0
        for key in sorted(STORE_ENCRYPTED_SETTING_KEYS):
            checked += 1
            try:
                _, was_migrated = self._get_with_migration_flag(key)
            except Exception:  # noqa: BLE001 — one bad key must not stop the sweep
                failed += 1
                logger.warning(
                    "eager encryption sweep (#307): could not check %r",
                    key, exc_info=True)
                continue
            if was_migrated:
                migrated += 1
        return {"checked": checked, "migrated": migrated, "failed": failed}

    def _raw_set(self, key: str, value: str) -> None:
        conn = self._connect()
        try:
            # ON CONFLICT DO UPDATE rewrites the row's value in place. Measured
            # on the real file: a plaintext value present in the .db before this
            # runs is absent afterwards (the ciphertext is always longer, so the
            # record is rewritten rather than partially overwritten). That is
            # what makes migration "gone", not merely "superseded".
            conn.execute(
                "INSERT INTO fleet_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            conn.commit()
        finally:
            conn.close()

    def set(self, key: str, value: str) -> None:
        """Set a setting value. Creates or updates the key.

        Secret keys are encrypted here, so every writer — the out-of-band
        capture form, the settings UI, ``python -m admz settings set`` and the
        MCP tool — stores ciphertext without knowing it needs to.
        """
        if is_store_encrypted(key) and value:
            from admz import setting_crypto

            value = setting_crypto.encrypt(value)
        self._raw_set(key, value)

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
        """Return all settings as a dict, secrets decrypted.

        Decrypting here keeps this consistent with :meth:`get` — every caller
        masks via ``mask_settings_for_display`` before showing anything, and
        that mask reports a length, which would otherwise describe the
        ciphertext rather than the secret.

        Does **not** migrate: a bulk listing is a display path, and a settings
        page render is the wrong moment to start rewriting rows. Migration
        happens on :meth:`get`, which is the path that actually uses a value.
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT key, value FROM fleet_settings ORDER BY key"
            ).fetchall()
        finally:
            conn.close()
        from admz import setting_crypto

        out: Dict[str, str] = {}
        for k, v in rows:
            if is_store_encrypted(k):
                plain, _ = setting_crypto.read_stored(k, v)
                out[k] = plain if plain is not None else ""
            else:
                out[k] = v
        return out


# Module-level singleton.
fleet_settings = FleetSettings()
