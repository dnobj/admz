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
"""


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
            conn.commit()

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
