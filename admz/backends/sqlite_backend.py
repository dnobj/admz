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
import os
import sqlite3
import time
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any

from admz.device_registry import DeviceRegistry
from admz.exceptions import (
    DeviceNotFoundError,
    AccountNotFoundError,
    BackendError,
    ConfigurationError,
)

# ---------------------------------------------------------------------------
# Encryption helpers — thin wrapper around cryptography.fernet.Fernet
# ---------------------------------------------------------------------------


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
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass

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

-- Slice 1: Organization → Site → Group → Device hierarchy.
-- Per docs/specification/decisions/... the Org is the unit of
-- git-archive isolation: each Org has its own ``repo_path`` +
-- optional ``repo_remote_url``. The SQLite tables here are the
-- cache of current state; the git repos are the temporal
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

CREATE TABLE IF NOT EXISTS device_groups (
    group_id      TEXT PRIMARY KEY,
    site_id       TEXT NOT NULL REFERENCES sites(site_id) ON DELETE RESTRICT,
    name          TEXT NOT NULL,
    purpose       TEXT NOT NULL DEFAULT '',
    created_at    REAL NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_device_groups_site ON device_groups(site_id);

-- N:N device → group membership with at most one row per device
-- marked is_primary=1 (enforced by the partial unique index below).
-- The primary group determines the device's location in its Org's
-- git repo: {repo_path}/{site_id}/{primary_group_id}/{device_id}/
CREATE TABLE IF NOT EXISTS device_group_memberships (
    device_id  TEXT NOT NULL,
    group_id   TEXT NOT NULL REFERENCES device_groups(group_id) ON DELETE CASCADE,
    is_primary INTEGER NOT NULL DEFAULT 0,
    added_at   REAL NOT NULL,
    PRIMARY KEY (device_id, group_id),
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dgm_one_primary
    ON device_group_memberships(device_id) WHERE is_primary = 1;
CREATE INDEX IF NOT EXISTS idx_dgm_group ON device_group_memberships(group_id);
"""

# Columns added to the existing `devices` table via ALTER TABLE
# (SQLite doesn't support IF NOT EXISTS on ADD COLUMN — the backend
# checks existing columns via PRAGMA table_info before ALTERing).
# Both are nullable on add so old rows pre-migration are valid;
# the migration script + bootstrap fill them in. Long-term, code
# that reads these treats NULL as "device belongs to the default
# org/site" so callers don't need null-checks everywhere.
_HIERARCHY_DEVICE_COLUMNS = (
    ("org_id",  "TEXT"),
    ("site_id", "TEXT"),
)


class SQLiteDeviceRegistry(DeviceRegistry):
    """
    Local SQLite backend for device credential management.

    Stores device metadata as JSON in a ``devices`` table and account
    credentials (with encrypted passwords) in an ``accounts`` table.

    Args:
        db_path: Path to the SQLite database file.
                 Defaults to ``~/.admz/admz.db``.
        key_path: Path to the Fernet encryption key file.
                  Defaults to ``~/.admz/admz.key``.

    Environment Variables:
        ADMZ_DB_PATH: Override the database file path.
        ADMZ_KEY_PATH: Override the key file path.

    Example::

        registry = SQLiteDeviceRegistry()              # ~/.admz/admz.db
        registry = SQLiteDeviceRegistry("/tmp/test.db") # custom path
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        key_path: Optional[str] = None,
    ):
        default_dir = Path.home() / ".admz"

        self._db_path = Path(
            db_path or os.getenv("ADMZ_DB_PATH", str(default_dir / "admz.db"))
        )
        self._key_path = Path(
            key_path or os.getenv("ADMZ_KEY_PATH", str(default_dir / "admz.key"))
        )

        # Ensure parent directories exist
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        # Tighten directory permissions on Unix; no-op on Windows.
        try:
            os.chmod(self._db_path.parent, 0o700)
        except OSError:
            pass

        # Initialise encryption
        self._fernet = _build_fernet(self._key_path)

        # Initialise the database with a short-lived connection. All
        # subsequent operations also open short-lived connections via
        # _connect(); this is multi-process-safe under WAL mode and
        # avoids the "connection used across threads" risk that the
        # previous long-lived self._conn pattern created.
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            self._apply_hierarchy_columns(conn)
            conn.commit()

    def _apply_hierarchy_columns(self, conn: sqlite3.Connection) -> None:
        """Idempotently add the Slice-1 hierarchy columns to ``devices``.

        SQLite doesn't support ADD COLUMN IF NOT EXISTS — we check
        ``PRAGMA table_info`` and only ALTER for missing columns.
        Adding nullable columns is fast and non-blocking even on
        large tables; the migration script (Slice 1 follow-up) is
        what actually populates them on existing rows.
        """
        existing = {
            row[1] for row in conn.execute("PRAGMA table_info(devices)")
        }
        for col_name, col_type in _HIERARCHY_DEVICE_COLUMNS:
            if col_name in existing:
                continue
            # Inline-formatted because SQLite refuses ? placeholders
            # in DDL; the values come from our own constants above so
            # there's no injection vector.
            conn.execute(
                f"ALTER TABLE devices ADD COLUMN {col_name} {col_type}"
            )

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
                "SELECT info_json FROM devices WHERE device_id=?", (device_id,)
            ).fetchone()

        info = json.loads(row[0])
        info["device_id"] = device_id
        return info

    def get_device_by_nickname(self, nickname: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT device_id, info_json FROM devices"
            ).fetchall()
        for device_id, raw in rows:
            info = json.loads(raw)
            if info.get("nickname", "").lower() == nickname.lower():
                info["device_id"] = device_id
                return info
        return None

    def list_devices(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT device_id, info_json FROM devices"
            ).fetchall()
        devices = []
        for device_id, raw in rows:
            info = json.loads(raw)
            info["device_id"] = device_id
            devices.append(info)
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

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO devices (device_id, info_json) VALUES (?, ?)",
                (device_id, json.dumps(device_info)),
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
        with self._connect() as conn:
            conn.execute(
                "UPDATE devices SET info_json = ? WHERE device_id = ?",
                (json.dumps(info), device_id),
            )
            conn.commit()

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
            child_groups = conn.execute(
                "SELECT COUNT(*) FROM device_groups WHERE site_id=?",
                (site_id,),
            ).fetchone()[0]
            if child_groups:
                raise BackendError(
                    f"Cannot remove Site '{site_id}': {child_groups} group(s) "
                    "still belong to it."
                )
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

    # -- Device groups -----------------------------------------------

    def add_device_group(
        self,
        group_id: str,
        site_id: str,
        name: str,
        purpose: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        from admz.validators import validate_identifier
        validate_identifier(group_id, "group_id")
        validate_identifier(site_id, "site_id")
        if self.get_site(site_id) is None:
            raise BackendError(f"Parent Site '{site_id}' does not exist")
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO device_groups "
                    "(group_id, site_id, name, purpose, created_at, "
                    " metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        group_id, site_id, name, purpose,
                        time.time(), json.dumps(metadata or {}),
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError as e:
                raise BackendError(
                    f"Group '{group_id}' already exists or violates a "
                    f"constraint: {e}"
                ) from e

    def get_device_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT group_id, site_id, name, purpose, created_at, "
                "metadata_json FROM device_groups WHERE group_id=?",
                (group_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "group_id": row[0], "site_id": row[1], "name": row[2],
            "purpose": row[3], "created_at": row[4],
            "metadata": json.loads(row[5] or "{}"),
        }

    def list_device_groups(
        self, site_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        sql = (
            "SELECT group_id, site_id, name, purpose, created_at, "
            "metadata_json FROM device_groups"
        )
        params: tuple = ()
        if site_id is not None:
            sql += " WHERE site_id=?"
            params = (site_id,)
        sql += " ORDER BY group_id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "group_id": r[0], "site_id": r[1], "name": r[2],
                "purpose": r[3], "created_at": r[4],
                "metadata": json.loads(r[5] or "{}"),
            }
            for r in rows
        ]

    def update_device_group(
        self, group_id: str, updates: Dict[str, Any],
    ) -> None:
        allowed = {"name", "purpose", "metadata"}
        if not (set(updates) & allowed):
            return
        existing = self.get_device_group(group_id)
        if existing is None:
            raise BackendError(f"Group '{group_id}' not found")
        merged_name = updates.get("name", existing["name"])
        merged_purpose = updates.get("purpose", existing["purpose"])
        merged_meta = existing["metadata"]
        if "metadata" in updates:
            merged_meta = dict(merged_meta)
            merged_meta.update(updates["metadata"])
        with self._connect() as conn:
            conn.execute(
                "UPDATE device_groups SET name=?, purpose=?, "
                "metadata_json=? WHERE group_id=?",
                (merged_name, merged_purpose, json.dumps(merged_meta), group_id),
            )
            conn.commit()

    def remove_device_group(self, group_id: str) -> None:
        """Removes the group. Memberships ON DELETE CASCADE so any
        device whose primary group was this one is left without a
        primary — callers must reassign before invoking."""
        with self._connect() as conn:
            still_primary = conn.execute(
                "SELECT COUNT(*) FROM device_group_memberships "
                "WHERE group_id=? AND is_primary=1",
                (group_id,),
            ).fetchone()[0]
            if still_primary:
                raise BackendError(
                    f"Cannot remove Group '{group_id}': it is the primary "
                    f"group for {still_primary} device(s). Reassign each "
                    "device's primary first via set_device_primary_group()."
                )
            conn.execute(
                "DELETE FROM device_groups WHERE group_id=?", (group_id,),
            )
            conn.commit()

    # -- Device group memberships (N:N) ------------------------------

    def add_device_to_group(
        self,
        device_id: str,
        group_id: str,
        is_primary: bool = False,
    ) -> None:
        """Add a device to a group. The device's first group is
        automatically promoted to primary if ``is_primary=True`` is
        not specified; subsequent additions stay non-primary unless
        explicitly requested."""
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        if self.get_device_group(group_id) is None:
            raise BackendError(f"Group '{group_id}' not found")
        with self._connect() as conn:
            # If is_primary, clear the existing primary first to keep
            # the partial unique index happy.
            if is_primary:
                conn.execute(
                    "UPDATE device_group_memberships SET is_primary=0 "
                    "WHERE device_id=? AND is_primary=1",
                    (device_id,),
                )
            try:
                conn.execute(
                    "INSERT INTO device_group_memberships "
                    "(device_id, group_id, is_primary, added_at) "
                    "VALUES (?, ?, ?, ?)",
                    (device_id, group_id, 1 if is_primary else 0, time.time()),
                )
            except sqlite3.IntegrityError:
                # Already a member — no-op the insert, only update
                # is_primary if requested.
                if is_primary:
                    conn.execute(
                        "UPDATE device_group_memberships SET is_primary=1 "
                        "WHERE device_id=? AND group_id=?",
                        (device_id, group_id),
                    )
            conn.commit()

    def remove_device_from_group(
        self, device_id: str, group_id: str,
    ) -> None:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM device_group_memberships "
                "WHERE device_id=? AND group_id=?",
                (device_id, group_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                # Best-effort: no-op when the membership wasn't there.
                # Callers that care can pre-check via list_groups_for_device.
                pass

    def list_groups_for_device(self, device_id: str) -> List[Dict[str, Any]]:
        """Return all groups the device belongs to. ``is_primary`` is
        included on each row so callers can identify the canonical
        group without a second query."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT g.group_id, g.site_id, g.name, g.purpose, "
                "       g.created_at, g.metadata_json, m.is_primary "
                "FROM device_group_memberships m "
                "JOIN device_groups g ON m.group_id = g.group_id "
                "WHERE m.device_id=? "
                "ORDER BY m.is_primary DESC, g.group_id",
                (device_id,),
            ).fetchall()
        return [
            {
                "group_id": r[0], "site_id": r[1], "name": r[2],
                "purpose": r[3], "created_at": r[4],
                "metadata": json.loads(r[5] or "{}"),
                "is_primary": bool(r[6]),
            }
            for r in rows
        ]

    def set_device_primary_group(
        self, device_id: str, group_id: str,
    ) -> None:
        """Designate ``group_id`` as the device's primary group.

        If the device wasn't already a member, it's added. The
        previous primary (if any) is demoted to non-primary in the
        same transaction so the partial unique index stays satisfied.
        """
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        if self.get_device_group(group_id) is None:
            raise BackendError(f"Group '{group_id}' not found")
        with self._connect() as conn:
            conn.execute(
                "UPDATE device_group_memberships SET is_primary=0 "
                "WHERE device_id=? AND is_primary=1",
                (device_id,),
            )
            # INSERT OR REPLACE to handle both the "already a member"
            # and "not yet a member" cases atomically.
            conn.execute(
                "INSERT INTO device_group_memberships "
                "(device_id, group_id, is_primary, added_at) "
                "VALUES (?, ?, 1, ?) "
                "ON CONFLICT(device_id, group_id) DO UPDATE SET "
                "is_primary=1",
                (device_id, group_id, time.time()),
            )
            conn.commit()

    def get_device_primary_group(
        self, device_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Return the primary group dict or None if the device has no
        group memberships yet."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT g.group_id, g.site_id, g.name, g.purpose, "
                "       g.created_at, g.metadata_json "
                "FROM device_group_memberships m "
                "JOIN device_groups g ON m.group_id = g.group_id "
                "WHERE m.device_id=? AND m.is_primary=1",
                (device_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "group_id": row[0], "site_id": row[1], "name": row[2],
            "purpose": row[3], "created_at": row[4],
            "metadata": json.loads(row[5] or "{}"),
        }

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
