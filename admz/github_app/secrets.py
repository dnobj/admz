"""Encrypted-at-rest storage + config accessors for the GitHub App.

The App **private key** and **client secret** are real secrets, so they are
stored as Fernet ciphertext (never plaintext) in ``fleet_settings`` — reusing the
one registry key (``ADMZ_KEY_PATH`` / ``ADMZ_HOME/admz.key``) that already
protects device passwords and the survey PAT. Non-secret facts (app id, slug,
installation id, target repo) are stored plaintext. Mirrors ``admz/survey/secrets.py``.

The setting keys carrying secrets contain ``key``/``secret`` in their name so
``admz/redact.py`` masks them automatically, and they're listed in
``PROTECTED_SETTING_KEYS`` so anonymous / MCP writers are refused.
"""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from typing import Optional

from admz.fleet_settings import fleet_settings

# --- fleet-setting keys (also registered PROTECTED in fleet_settings) ---
KEY_APP_ID = "github_app_id"
KEY_APP_SLUG = "github_app_slug"
KEY_PRIVATE_KEY = "github_app_private_key"        # stores CIPHERTEXT (secret)
KEY_CLIENT_SECRET = "github_app_client_secret"    # stores CIPHERTEXT (secret)
KEY_INSTALLATION_ID = "github_app_installation_id"
KEY_CONFIG_REPO = "github_config_repo"            # "owner/repo"

# Every secret-bearing key above, for the PROTECTED_SETTING_KEYS registration.
SETTING_KEYS = (
    KEY_APP_ID, KEY_APP_SLUG, KEY_PRIVATE_KEY, KEY_CLIENT_SECRET,
    KEY_INSTALLATION_ID, KEY_CONFIG_REPO,
)


def _key_path() -> Path:
    from admz.paths import key_path
    return key_path()


def _fernet():
    # reuse the registry's key helper so there's exactly one key file
    from admz.backends.sqlite_backend import _build_fernet
    return _build_fernet(_key_path())


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


# ---------------------------------------------------------------------------
# App credentials (written by the setup-callback route)
# ---------------------------------------------------------------------------


def save_app(app_id, slug: str, private_key_pem: str,
             client_secret: Optional[str] = None) -> None:
    """Persist the App identity + private key (encrypted) after the manifest
    conversion. Does NOT set the installation (that comes from the install
    callback)."""
    fleet_settings.set(KEY_APP_ID, str(app_id))
    fleet_settings.set(KEY_APP_SLUG, slug or "")
    fleet_settings.set(KEY_PRIVATE_KEY, encrypt(private_key_pem))
    if client_secret:
        fleet_settings.set(KEY_CLIENT_SECRET, encrypt(client_secret))


def get_app_id() -> Optional[str]:
    return fleet_settings.get(KEY_APP_ID) or None


def get_slug() -> Optional[str]:
    return fleet_settings.get(KEY_APP_SLUG) or None


def get_private_key() -> Optional[str]:
    """Decrypted PEM, or None if unset/undecryptable."""
    ct = fleet_settings.get(KEY_PRIVATE_KEY)
    if not ct:
        return None
    try:
        return decrypt(ct)
    except Exception:  # noqa: BLE001 - wrong key / corrupt value
        return None


def set_installation_id(installation_id) -> None:
    fleet_settings.set(KEY_INSTALLATION_ID, str(installation_id))


def get_installation_id() -> Optional[str]:
    return fleet_settings.get(KEY_INSTALLATION_ID) or None


def set_config_repo(owner_repo: str) -> None:
    fleet_settings.set(KEY_CONFIG_REPO, owner_repo)


def get_config_repo() -> Optional[str]:
    return fleet_settings.get(KEY_CONFIG_REPO) or None


def is_connected() -> bool:
    """True once the App is registered AND installed (so tokens can be minted)."""
    return bool(get_app_id() and get_private_key() and get_installation_id())


def status() -> dict:
    """Non-secret connection status for the Settings UI (never returns secrets)."""
    return {
        "app_registered": bool(get_app_id() and get_private_key()),
        "installed": bool(get_installation_id()),
        "connected": is_connected(),
        "slug": get_slug(),
        "config_repo": get_config_repo(),
        "installation_id": get_installation_id(),
    }


def clear() -> None:
    """Forget the App entirely (Disconnect). Removes all stored keys."""
    for key in SETTING_KEYS:
        fleet_settings.delete(key)


# ---------------------------------------------------------------------------
# OAuth-state signing key (ties a callback to the connect request; anti-CSRF)
# ---------------------------------------------------------------------------


def signing_key() -> bytes:
    """A stable per-install HMAC key for signing the OAuth ``state`` param,
    derived from the Fernet key file so it needs no separate secret."""
    p = _key_path()
    seed = p.read_bytes().strip() if p.exists() else b"admz-github-app"
    # domain-separate from any other use of the raw key bytes
    return hmac.new(seed, b"github-app-oauth-state", hashlib.sha256).digest()
