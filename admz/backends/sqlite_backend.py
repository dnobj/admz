"""
SQLite backend for local device credential storage.

Zero-config local storage — no external server required.  Passwords are
encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256).  On first
run a random encryption key is generated and written to a key file next
to the database.

Storage layout (two tables):

    devices
    -------
    device_id   TEXT PRIMARY KEY
    info_json   TEXT                -- JSON blob of device metadata

    accounts
    --------
    device_id   TEXT
    account_id  TEXT
    data_json   TEXT                -- JSON blob with encrypted password
    PRIMARY KEY (device_id, account_id)
"""

import json
import logging
import os
import sqlite3
import sys
import time
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any

from admz.device_registry import DeviceRegistry, canonical_mac
from admz.exceptions import (
    DeviceNotFoundError,
    AccountNotFoundError,
    BackendError,
    ConfigurationError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Encryption helpers — thin wrapper around cryptography.fernet.Fernet
# ---------------------------------------------------------------------------


def _restrict_key_file(key_path: Path) -> None:
    """Restrict a freshly-created Fernet key file to its owner (#207).

    Two genuinely different mechanisms, because the platforms are not
    variations on a theme:

    * **POSIX** — ``chmod 0o600``. Correct and sufficient.
    * **Windows** — an explicit, *protected* (non-inheriting) DACL via
      :mod:`admz.win_acl`. ``os.chmod`` is deliberately NOT called here:
      on Windows it is a complete no-op for access-control purposes. It
      never touches the DACL, and since ``0o600`` carries the owner-write
      bit it clears ``FILE_ATTRIBUTE_READONLY`` rather than setting it.
      Calling it would only imply a protection that does not exist.

    Failure is logged, never swallowed and never fatal. The previous
    ``except OSError: pass`` meant a failure to protect the key that
    encrypts every device credential in the fleet was completely silent.
    Startup still proceeds: an unprotected key is bad, but a service that
    refuses to boot on an exotic filesystem is worse, and the operator now
    has a log line naming the file.
    """
    if sys.platform == "win32":
        from admz.win_acl import WinAclError, harden_secret_file

        try:
            sddl = harden_secret_file(key_path)
        except (WinAclError, OSError):
            logger.error(
                "Could not set an owner-only ACL on the new Fernet master "
                "key %s — it may be readable by other local users. See "
                "ADR-0010.",
                key_path,
                exc_info=True,
            )
        else:
            logger.info(
                "Created Fernet master key %s with owner-only ACL (%s)",
                key_path,
                sddl,
            )
    else:
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            logger.error(
                "Could not chmod 0o600 the new Fernet master key %s — it "
                "may be readable by other users.",
                key_path,
                exc_info=True,
            )


def _restrict_data_dir(dir_path: Path) -> None:
    """Tighten the ADMZ data directory's permissions — **POSIX only** (#250).

    On POSIX, ``chmod 0o700`` is correct and is applied.

    On Windows this deliberately does **nothing**, and the absence is the
    decision. It is not an omission to be tidied up later — see ADR-0042.
    Three measured reasons, in the order they rule the alternative out:

    1. **The obvious fix collapses the DACL of everything inside.** The
       key-file helper in :mod:`admz.win_acl` emits ACEs with no
       inheritance flags, which is right for a file and wrong for a
       container. ``SetNamedSecurityInfo`` re-propagates inheritance to
       existing children, so a parent with no inheritable ACEs strips
       theirs: measured, ``admz.db`` went from 4 ACEs to 0 — an empty
       DACL, which denies everyone including SYSTEM.
    2. **This code cannot know the right principals.** The ``admz``
       service runs as LocalSystem, so a service-created directory would
       be owned by ``S-1-5-18``. Granting SYSTEM + Administrators is not
       enough for the operator: a non-elevated admin's UAC-filtered token
       does not carry ``S-1-5-32-544`` at all, and such a file is measured
       unreadable. ``setup-admz-service.ps1`` therefore grants the
       operator's account explicitly — something only setup knows.
    3. **This is not the creation path.** Twelve sites create ADMZ_HOME;
       in the web/service process ``admz/events/store.py`` wins at import,
       long before the registry is built in the FastAPI lifespan. A DACL
       applied here would land on a directory someone else created, and
       would propagate into the existing ``admz.key`` — which is #183, an
       open operator decision.

    Hardening ADMZ_HOME on Windows belongs to ``setup-admz-service.ps1``
    (ADR-0042), which ADR-0054 plans to bring into ``scripts/``.

    The precedent for this shape is ``admz/snapshot/git_repo.py``, which
    already guards its ``chmod`` on ``sys.platform``.
    """
    if sys.platform == "win32":
        return
    try:
        os.chmod(dir_path, 0o700)
    except OSError:
        logger.error(
            "Could not chmod 0o700 the ADMZ data directory %s — it may be "
            "readable by other users.",
            dir_path,
            exc_info=True,
        )


def _build_fernet(key_path: Path):
    """Build a Fernet instance from a key file, creating the file if needed."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ConfigurationError(
            "The 'cryptography' package is required for the SQLite backend. "
            "Install with: pip install cryptography"
        )

    if key_path.exists():
        key = key_path.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(key)
        _restrict_key_file(key_path)

    return Fernet(key)


def _encrypt(plain: str, fernet) -> str:
    """Encrypt a string and return url-safe base64."""
    return fernet.encrypt(plain.encode()).decode()


def _decrypt(token: str, fernet) -> str:
    """Decrypt an encrypted token back to plaintext."""
    return fernet.decrypt(token.encode()).decode()


# ---------------------------------------------------------------------------
# SQLite Device Registry
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    device_id   TEXT PRIMARY KEY,
    info_json   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    device_id   TEXT NOT NULL,
    account_id  TEXT NOT NULL,
    data_json   TEXT NOT NULL,
    PRIMARY KEY (device_id, account_id),
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
);

-- Org → Site → Device hierarchy (ADR-0032: the former Group level was
-- removed — operational grouping is done with device TAGS instead).
-- The Org is the unit of git-archive isolation: each Org has its own
-- ``repo_path`` + optional ``repo_remote_url``. The SQLite tables here
-- are the cache of current state; the git repos are the temporal
-- source of truth.

CREATE TABLE IF NOT EXISTS organizations (
    org_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    repo_path       TEXT NOT NULL,
    repo_remote_url TEXT NOT NULL DEFAULT '',
    created_at      REAL NOT NULL,
    metadata_json   TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS sites (
    site_id       TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES organizations(org_id) ON DELETE RESTRICT,
    name          TEXT NOT NULL,
    location      TEXT NOT NULL DEFAULT '',
    created_at    REAL NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_sites_org ON sites(org_id);

-- Named config baselines (alternate configurations) per device: a name -> a
-- git commit that holds a saved full config for the device. The ACTIVE one is
-- whichever commit_sha == devices.baseline_sha (no separate flag). Kept in a
-- dedicated table (not info_json) so health/facts churn can't clobber it,
-- mirroring the baseline_sha pointer columns.
CREATE TABLE IF NOT EXISTS device_baselines (
    device_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    commit_sha  TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    created_by  TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (device_id, name),
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
);
"""

# ADR-0032: the device_groups / device_group_memberships tables are gone —
# dropped idempotently on open. They only ever held the bootstrap
# "ungrouped" row plus memberships pointing at it (no operator-authored
# groups existed before the removal), so the drop is safe.
_DROPPED_TABLES = ("device_group_memberships", "device_groups")

# Columns added to the existing `devices` table via ALTER TABLE
# (SQLite doesn't support IF NOT EXISTS on ADD COLUMN — the backend
# checks existing columns via PRAGMA table_info before ALTERing).
# All nullable on add so rows that predate a column stay valid:
#   - org_id/site_id: NULL means "the default org/site".
#   - created_at: Unix epoch seconds, stamped on add_device. NULL means
#     the row predates this column (creation time unknown — fall back to
#     insertion order / rowid).
#   - baseline_sha/latest_observed_sha/last_observed_at: config-baseline
#     pointers into the git config repo (the single source of truth for
#     config bytes — see ADR-0014/0031). NULL until the device is
#     snapshotted (baseline) or audited (observed).
_DEVICE_EXTRA_COLUMNS = (
    ("org_id",              "TEXT"),
    ("site_id",             "TEXT"),
    ("created_at",          "REAL"),
    ("baseline_sha",        "TEXT"),
    ("latest_observed_sha", "TEXT"),
    ("last_observed_at",    "REAL"),
    # ADR-0044: the named alternate config ("scenario") currently pushed to the
    # device, or NULL when the device is on its baseline. Set on scenario
    # activation, cleared on return-to-baseline. The baseline pointer does NOT
    # move when a scenario is active.
    ("active_scenario",     "TEXT"),
)

# Subset of the extra columns surfaced into the device-info dict on read
# (NULL -> key omitted). org_id/site_id are deliberately excluded — the
# hierarchy layer queries them directly; they aren't device_info fields.
_DEVICE_INFO_EXTRA_COLUMNS = (
    "created_at",
    "baseline_sha",
    "latest_observed_sha",
    "last_observed_at",
    "active_scenario",
)
_DEVICE_INFO_EXTRA_SELECT = ", ".join(_DEVICE_INFO_EXTRA_COLUMNS)


def _merge_info_extras(info: Dict[str, Any], extras) -> Dict[str, Any]:
    """Attach non-null extra-column values to a device-info dict, by position
    (matching ``_DEVICE_INFO_EXTRA_COLUMNS`` / ``_DEVICE_INFO_EXTRA_SELECT``)."""
    for name, val in zip(_DEVICE_INFO_EXTRA_COLUMNS, extras):
        if val is not None:
            info[name] = val
    return info


class SQLiteDeviceRegistry(DeviceRegistry):
    """
    Local SQLite backend for device credential management.

    Stores device metadata as JSON in a ``devices`` table and account
    credentials (with encrypted passwords) in an ``accounts`` table.

    Args:
        db_path: Path to the SQLite database file.
                 Defaults to ``ADMZ_HOME/admz.db`` (``~/.admz/admz.db``).
        key_path: Path to the Fernet encryption key file.
                  Defaults to ``ADMZ_HOME/admz.key`` (``~/.admz/admz.key``).

    Environment Variables:
        ADMZ_HOME: Override the data directory (ADR-0042).
        ADMZ_DB_PATH: Override the database file path.
        ADMZ_KEY_PATH: Override the key file path.

    Example::

        registry = SQLiteDeviceRegistry()              # ADMZ_HOME/admz.db
        registry = SQLiteDeviceRegistry("/tmp/test.db") # custom path
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        key_path: Optional[str] = None,
    ):
        from admz import paths

        self._db_path = Path(db_path) if db_path else paths.db_path()
        self._key_path = Path(key_path) if key_path else paths.key_path()

        # Ensure parent directories exist
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        _restrict_data_dir(self._db_path.parent)

        # Initialise encryption
        self._fernet = _build_fernet(self._key_path)

        # Initialise the database with a short-lived connection. All
        # subsequent operations also open short-lived connections via
        # _connect(); this is multi-process-safe under WAL mode and
        # avoids the "connection used across threads" risk that the
        # previous long-lived self._conn pattern created.
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            self._apply_device_extra_columns(conn)
            self._drop_removed_tables(conn)
            conn.commit()

    def _apply_device_extra_columns(self, conn: sqlite3.Connection) -> None:
        """Idempotently add the extra ``devices`` columns (hierarchy +
        created_at).

        SQLite doesn't support ADD COLUMN IF NOT EXISTS — we check
        ``PRAGMA table_info`` and only ALTER for missing columns.
        Adding nullable columns is fast and non-blocking even on
        large tables; rows added before a column existed read it as NULL.
        """
        existing = {
            row[1] for row in conn.execute("PRAGMA table_info(devices)")
        }
        for col_name, col_type in _DEVICE_EXTRA_COLUMNS:
            if col_name in existing:
                continue
            # Inline-formatted because SQLite refuses ? placeholders
            # in DDL; the values come from our own constants above so
            # there's no injection vector.
            conn.execute(
                f"ALTER TABLE devices ADD COLUMN {col_name} {col_type}"
            )

    def _drop_removed_tables(self, conn: sqlite3.Connection) -> None:
        """Idempotently drop tables removed from the schema (ADR-0032).

        The Group level of the hierarchy was replaced by device tags;
        its two tables only ever held the bootstrap "ungrouped" row +
        memberships pointing at it, so dropping them loses nothing an
        operator authored. DROP TABLE IF EXISTS makes this a no-op on
        every subsequent open.
        """
        for table in _DROPPED_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")

    def _connect(self) -> sqlite3.Connection:
        """Open a fresh SQLite connection with WAL + foreign-keys enabled."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def close(self) -> None:
        """Compatibility no-op. Connections are short-lived per call now;
        nothing to close. Kept so that callers (FastAPI lifespan shutdown,
        tests) can call .close() without breaking."""
        return None

    # -- helpers -----------------------------------------------------------

    def _store_account_data(self, data: Dict[str, Any]) -> str:
        """Serialise account data to JSON, encrypting the password field."""
        data = dict(data)
        if "password" in data:
            data["password"] = _encrypt(data["password"], self._fernet)
            data["_encrypted"] = True
        return json.dumps(data)

    def _load_account_data(self, raw: str, include_password: bool = True) -> Dict[str, Any]:
        """Deserialise account data, decrypting the password if present."""
        data = json.loads(raw)
        if data.pop("_encrypted", False) and "password" in data:
            if include_password:
                data["password"] = _decrypt(data["password"], self._fernet)
            else:
                data.pop("password", None)
        elif not include_password:
            data.pop("password", None)
        return data

    # -- read operations ---------------------------------------------------

    def get_credentials(
        self,
        device_id: str,
        account_id: str = "default",
        requester: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        if not self.account_exists(device_id, account_id):
            raise AccountNotFoundError(
                f"Account '{account_id}' not found for device '{device_id}'"
            )

        with self._connect() as conn:
            row = conn.execute(
                "SELECT data_json FROM accounts WHERE device_id=? AND account_id=?",
                (device_id, account_id),
            ).fetchone()

        credentials = self._load_account_data(row[0], include_password=True)

        # Include host from device_info for convenience
        device_info = self.get_device_info(device_id)
        credentials["host"] = device_info.get("host")
        return credentials

    def get_device_info(self, device_id: str) -> Dict[str, Any]:
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        with self._connect() as conn:
            row = conn.execute(
                f"SELECT info_json, {_DEVICE_INFO_EXTRA_SELECT} "
                "FROM devices WHERE device_id=?",
                (device_id,),
            ).fetchone()

        info = json.loads(row[0])
        info["device_id"] = device_id
        return _merge_info_extras(info, row[1:])

    def get_device_by_nickname(self, nickname: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT device_id, info_json, {_DEVICE_INFO_EXTRA_SELECT} "
                "FROM devices"
            ).fetchall()
        for row in rows:
            device_id, raw = row[0], row[1]
            info = json.loads(raw)
            if info.get("nickname", "").lower() == nickname.lower():
                info["device_id"] = device_id
                return _merge_info_extras(info, row[2:])
        return None

    def list_devices(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT device_id, info_json, {_DEVICE_INFO_EXTRA_SELECT} "
                "FROM devices"
            ).fetchall()
        devices = []
        for row in rows:
            device_id, raw = row[0], row[1]
            info = json.loads(raw)
            info["device_id"] = device_id
            devices.append(_merge_info_extras(info, row[2:]))
        return devices

    def list_accounts(self, device_id: str) -> List[Dict[str, str]]:
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT account_id, data_json FROM accounts WHERE device_id=?",
                (device_id,),
            ).fetchall()

        accounts = []
        for account_id, raw in rows:
            data = self._load_account_data(raw, include_password=False)
            data["account_id"] = account_id
            accounts.append(data)
        return accounts

    def device_exists(self, device_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM devices WHERE device_id=?", (device_id,)
            ).fetchone()
        return row is not None

    def account_exists(self, device_id: str, account_id: str) -> bool:
        if not self.device_exists(device_id):
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM accounts WHERE device_id=? AND account_id=?",
                (device_id, account_id),
            ).fetchone()
        return row is not None

    # -- write operations --------------------------------------------------

    def add_device(
        self,
        device_id: str,
        device_info: Dict[str, Any],
        accounts: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        if self.device_exists(device_id):
            raise BackendError(f"Device '{device_id}' already exists")
        # Slot/unit (ADR-0036): if the slot's device_id is a MAC (the
        # auto-registration default) and no installed-unit MAC was given,
        # record it so discovery-reconcile/collision key on `mac_address`.
        if not device_info.get("mac_address") and len(canonical_mac(device_id)) == 12:
            device_info = {**device_info, "mac_address": device_id}
        self._assert_no_mac_collision(device_id, device_info)

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO devices (device_id, info_json, created_at) "
                "VALUES (?, ?, ?)",
                (device_id, json.dumps(device_info), time.time()),
            )
            conn.commit()

        if accounts:
            for account_id, account_data in accounts.items():
                self.add_account(device_id, account_id, account_data)

    def update_device(
        self,
        device_id: str,
        updates: Dict[str, Any],
    ) -> None:
        info = self.get_device_info(device_id)
        info.update(updates)
        # created_at + config pointers live in their own columns — don't let
        # the enriched read values leak into the info_json blob (they'd shadow
        # / diverge from the columns).
        for _col in _DEVICE_INFO_EXTRA_COLUMNS:
            info.pop(_col, None)
        with self._connect() as conn:
            conn.execute(
                "UPDATE devices SET info_json = ? WHERE device_id = ?",
                (json.dumps(info), device_id),
            )
            conn.commit()

    def set_config_pointers(
        self,
        device_id: str,
        *,
        baseline_sha: Optional[str] = None,
        latest_observed_sha: Optional[str] = None,
        last_observed_at: Optional[float] = None,
    ) -> None:
        """Update the git config-baseline pointer columns for a device.

        Only non-None arguments are written, so callers can advance the
        observed pointer without touching the baseline (and vice versa).
        These are discrete columns, not part of the ``info_json`` blob.
        """
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        assignments = []
        values: List[Any] = []
        if baseline_sha is not None:
            assignments.append("baseline_sha = ?")
            values.append(baseline_sha)
        if latest_observed_sha is not None:
            assignments.append("latest_observed_sha = ?")
            values.append(latest_observed_sha)
        if last_observed_at is not None:
            assignments.append("last_observed_at = ?")
            values.append(last_observed_at)
        if not assignments:
            return
        values.append(device_id)
        with self._connect() as conn:
            conn.execute(
                # Column names are our own constants (no injection); values
                # are parameterized.
                f"UPDATE devices SET {', '.join(assignments)} "
                "WHERE device_id = ?",
                values,
            )
            conn.commit()

    def set_active_scenario(
        self, device_id: str, scenario_name: Optional[str] = None
    ) -> None:
        """Mark which named alternate config ("scenario") is currently pushed to
        the device, or ``None`` to clear it (device is back on its baseline).

        This does NOT move ``baseline_sha`` — a scenario is a temporary push;
        the blessed baseline stays put so returning to it is a clean snap-back
        (ADR-0044)."""
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        with self._connect() as conn:
            conn.execute(
                "UPDATE devices SET active_scenario = ? WHERE device_id = ?",
                (scenario_name, device_id),
            )
            conn.commit()

    # ── Named config baselines (alternate configurations) ──────────────────
    def save_named_baseline(
        self,
        device_id: str,
        name: str,
        commit_sha: str,
        *,
        note: str = "",
        created_by: str = "",
    ) -> None:
        """Save (or overwrite) a named full-config baseline — a name pointing
        at a git commit that holds a saved config for the device. The ACTIVE
        baseline is whichever name's ``commit_sha`` equals the device's
        ``baseline_sha`` (no separate flag)."""
        import time
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO device_baselines "
                "(device_id, name, commit_sha, note, created_at, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(device_id, name) DO UPDATE SET "
                "commit_sha=excluded.commit_sha, note=excluded.note, "
                "created_at=excluded.created_at, created_by=excluded.created_by",
                (device_id, name, commit_sha, note or "", time.time(), created_by or ""),
            )
            conn.commit()

    def list_named_baselines(self, device_id: str) -> List[Dict[str, Any]]:
        """All named baselines for a device (newest first)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, commit_sha, note, created_at, created_by "
                "FROM device_baselines WHERE device_id=? ORDER BY created_at DESC",
                (device_id,),
            ).fetchall()
        return [
            {"name": r[0], "commit_sha": r[1], "note": r[2],
             "created_at": r[3], "created_by": r[4]}
            for r in rows
        ]

    def delete_named_baseline(self, device_id: str, name: str) -> bool:
        """Remove a named baseline (the underlying commit stays in git
        history). Returns True if a row was actually removed."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM device_baselines WHERE device_id=? AND name=?",
                (device_id, name),
            )
            conn.commit()
            return cur.rowcount > 0

    def remove_device(self, device_id: str) -> None:
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        # Foreign key cascade deletes accounts
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM devices WHERE device_id=?", (device_id,)
            )
            conn.commit()

    def add_account(
        self, device_id: str, account_id: str, account_data: Dict[str, Any]
    ) -> None:
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        if self.account_exists(device_id, account_id):
            raise BackendError(
                f"Account '{account_id}' already exists for device '{device_id}'"
            )

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO accounts (device_id, account_id, data_json) VALUES (?, ?, ?)",
                (device_id, account_id, self._store_account_data(account_data)),
            )
            conn.commit()

    def update_device_info(
        self, device_id: str, updates: Dict[str, Any]
    ) -> None:
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        with self._connect() as conn:
            row = conn.execute(
                "SELECT info_json FROM devices WHERE device_id=?", (device_id,)
            ).fetchone()
            info = json.loads(row[0])
            info.update(updates)
            conn.execute(
                "UPDATE devices SET info_json=? WHERE device_id=?",
                (json.dumps(info), device_id),
            )
            conn.commit()

    def remove_account(self, device_id: str, account_id: str) -> None:
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        if not self.account_exists(device_id, account_id):
            raise AccountNotFoundError(
                f"Account '{account_id}' not found for device '{device_id}'"
            )

        with self._connect() as conn:
            conn.execute(
                "DELETE FROM accounts WHERE device_id=? AND account_id=?",
                (device_id, account_id),
            )
            conn.commit()

    def update_account(
        self,
        device_id: str,
        account_id: str,
        updates: Dict[str, Any],
    ) -> None:
        """Partially update an account (merge *updates* into existing data).

        Atomic: the row is rewritten in a single SQL UPDATE — the account
        is never observably absent during the change (unlike the legacy
        ``remove_account`` + ``add_account`` pattern, which had a brief
        window where the account didn't exist and a concurrent reader
        would see AccountNotFound).

        Re-encrypts the merged data via ``_store_account_data``, so a
        password update gets a fresh Fernet ciphertext + IV — handy
        for tests that inspect the encrypted bytes at rest.
        """
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        if not self.account_exists(device_id, account_id):
            raise AccountNotFoundError(
                f"Account '{account_id}' not found for device '{device_id}'"
            )

        with self._connect() as conn:
            # Load existing decrypted data, merge, re-encrypt, write back —
            # all under one transaction so partial failures roll back.
            row = conn.execute(
                "SELECT data_json FROM accounts "
                "WHERE device_id=? AND account_id=?",
                (device_id, account_id),
            ).fetchone()
            current = self._load_account_data(row[0], include_password=True)
            current.update(updates)
            conn.execute(
                "UPDATE accounts SET data_json=? "
                "WHERE device_id=? AND account_id=?",
                (self._store_account_data(current), device_id, account_id),
            )
            conn.commit()

    # ---------------------------------------------------------------
    # Slice 1: Org / Site / Group CRUD
    # ---------------------------------------------------------------

    def add_organization(
        self,
        org_id: str,
        name: str,
        repo_path: str,
        repo_remote_url: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert a new Organization row.

        ``repo_path`` is the absolute filesystem path of this Org's
        git config repo. ``build_components()`` is responsible for
        deriving it from ``ADMZ_REPO_PATH_ROOT`` and actually
        running ``git init`` on disk; this method only writes the
        SQLite row.
        """
        from admz.validators import validate_identifier
        validate_identifier(org_id, "org_id")
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO organizations "
                    "(org_id, name, repo_path, repo_remote_url, "
                    " created_at, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        org_id, name, repo_path, repo_remote_url,
                        time.time(), json.dumps(metadata or {}),
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError as e:
                raise BackendError(
                    f"Organization '{org_id}' already exists or violates a "
                    f"constraint: {e}"
                ) from e

    def get_organization(self, org_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT org_id, name, repo_path, repo_remote_url, "
                "created_at, metadata_json FROM organizations "
                "WHERE org_id=?",
                (org_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "org_id": row[0], "name": row[1], "repo_path": row[2],
            "repo_remote_url": row[3], "created_at": row[4],
            "metadata": json.loads(row[5] or "{}"),
        }

    def list_organizations(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT org_id, name, repo_path, repo_remote_url, "
                "created_at, metadata_json FROM organizations "
                "ORDER BY org_id"
            ).fetchall()
        return [
            {
                "org_id": r[0], "name": r[1], "repo_path": r[2],
                "repo_remote_url": r[3], "created_at": r[4],
                "metadata": json.loads(r[5] or "{}"),
            }
            for r in rows
        ]

    def update_organization(
        self, org_id: str, updates: Dict[str, Any],
    ) -> None:
        """Merge ``updates`` into the Org row.

        Only ``name``, ``repo_remote_url``, and ``metadata`` may be
        changed via this path. ``org_id`` (PK) and ``repo_path``
        (filesystem-bound) are immutable in v1 — renaming them would
        require a coordinated git tree move, which is out of scope.
        """
        allowed = {"name", "repo_remote_url", "metadata"}
        if not (set(updates) & allowed):
            return
        with self._connect() as conn:
            existing = self.get_organization(org_id)
            if existing is None:
                raise BackendError(f"Organization '{org_id}' not found")
            merged_name = updates.get("name", existing["name"])
            merged_remote = updates.get(
                "repo_remote_url", existing["repo_remote_url"]
            )
            merged_meta = existing["metadata"]
            if "metadata" in updates:
                merged_meta = dict(merged_meta)
                merged_meta.update(updates["metadata"])
            conn.execute(
                "UPDATE organizations SET name=?, repo_remote_url=?, "
                "metadata_json=? WHERE org_id=?",
                (merged_name, merged_remote, json.dumps(merged_meta), org_id),
            )
            conn.commit()

    def remove_organization(self, org_id: str) -> None:
        """Refuse if any Sites still reference this Org. Soft-delete
        is the operator's job — this method just unlinks the row."""
        with self._connect() as conn:
            child_sites = conn.execute(
                "SELECT COUNT(*) FROM sites WHERE org_id=?", (org_id,),
            ).fetchone()[0]
            if child_sites:
                raise BackendError(
                    f"Cannot remove Org '{org_id}': {child_sites} site(s) "
                    "still belong to it. Remove or reparent the sites first."
                )
            child_devices = conn.execute(
                "SELECT COUNT(*) FROM devices WHERE org_id=?", (org_id,),
            ).fetchone()[0]
            if child_devices:
                raise BackendError(
                    f"Cannot remove Org '{org_id}': {child_devices} device(s) "
                    "still belong to it."
                )
            conn.execute("DELETE FROM organizations WHERE org_id=?", (org_id,))
            conn.commit()

    # -- Sites -------------------------------------------------------

    def add_site(
        self,
        site_id: str,
        org_id: str,
        name: str,
        location: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        from admz.validators import validate_identifier
        validate_identifier(site_id, "site_id")
        validate_identifier(org_id, "org_id")
        if self.get_organization(org_id) is None:
            raise BackendError(f"Parent Org '{org_id}' does not exist")
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO sites "
                    "(site_id, org_id, name, location, created_at, "
                    " metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        site_id, org_id, name, location,
                        time.time(), json.dumps(metadata or {}),
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError as e:
                raise BackendError(
                    f"Site '{site_id}' already exists or violates a "
                    f"constraint: {e}"
                ) from e

    def get_site(self, site_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT site_id, org_id, name, location, created_at, "
                "metadata_json FROM sites WHERE site_id=?",
                (site_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "site_id": row[0], "org_id": row[1], "name": row[2],
            "location": row[3], "created_at": row[4],
            "metadata": json.loads(row[5] or "{}"),
        }

    def list_sites(self, org_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = (
            "SELECT site_id, org_id, name, location, created_at, "
            "metadata_json FROM sites"
        )
        params: tuple = ()
        if org_id is not None:
            sql += " WHERE org_id=?"
            params = (org_id,)
        sql += " ORDER BY site_id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "site_id": r[0], "org_id": r[1], "name": r[2],
                "location": r[3], "created_at": r[4],
                "metadata": json.loads(r[5] or "{}"),
            }
            for r in rows
        ]

    def update_site(self, site_id: str, updates: Dict[str, Any]) -> None:
        allowed = {"name", "location", "metadata"}
        if not (set(updates) & allowed):
            return
        existing = self.get_site(site_id)
        if existing is None:
            raise BackendError(f"Site '{site_id}' not found")
        merged_name = updates.get("name", existing["name"])
        merged_location = updates.get("location", existing["location"])
        merged_meta = existing["metadata"]
        if "metadata" in updates:
            merged_meta = dict(merged_meta)
            merged_meta.update(updates["metadata"])
        with self._connect() as conn:
            conn.execute(
                "UPDATE sites SET name=?, location=?, metadata_json=? "
                "WHERE site_id=?",
                (merged_name, merged_location, json.dumps(merged_meta), site_id),
            )
            conn.commit()

    def remove_site(self, site_id: str) -> None:
        with self._connect() as conn:
            child_devices = conn.execute(
                "SELECT COUNT(*) FROM devices WHERE site_id=?", (site_id,),
            ).fetchone()[0]
            if child_devices:
                raise BackendError(
                    f"Cannot remove Site '{site_id}': {child_devices} device(s) "
                    "still belong to it."
                )
            conn.execute("DELETE FROM sites WHERE site_id=?", (site_id,))
            conn.commit()

    # -- Device org/site assignment ----------------------------------

    def set_device_org_site(
        self, device_id: str, org_id: str, site_id: str,
    ) -> None:
        """Set the device's org_id + site_id columns. Both must exist."""
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        if self.get_organization(org_id) is None:
            raise BackendError(f"Org '{org_id}' not found")
        site = self.get_site(site_id)
        if site is None:
            raise BackendError(f"Site '{site_id}' not found")
        if site["org_id"] != org_id:
            raise BackendError(
                f"Site '{site_id}' belongs to Org '{site['org_id']}', "
                f"not '{org_id}'"
            )
        with self._connect() as conn:
            conn.execute(
                "UPDATE devices SET org_id=?, site_id=? WHERE device_id=?",
                (org_id, site_id, device_id),
            )
            conn.commit()

    def get_device_org_site(
        self, device_id: str,
    ) -> Optional[Dict[str, str]]:
        """Return ``{"org_id": ..., "site_id": ...}`` or None if both
        columns are NULL (pre-migration row)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT org_id, site_id FROM devices WHERE device_id=?",
                (device_id,),
            ).fetchone()
        if row is None or (row[0] is None and row[1] is None):
            return None
        return {"org_id": row[0], "site_id": row[1]}
