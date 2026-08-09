"""Encrypted-at-rest storage + config accessors for the GitHub App.

The App **private key** is a real secret, so it is stored as Fernet ciphertext
(never plaintext) in ``fleet_settings`` — reusing the one registry key
(``ADMZ_KEY_PATH`` / ``ADMZ_HOME/admz.key``) that already protects device
passwords and the survey PAT. Non-secret facts (app id, slug, installation id,
target repo) are stored plaintext. Mirrors ``admz/survey/secrets.py``.

The **client secret is not stored at all** (#172). GitHub returns one from the
manifest conversion, and this module used to keep it encrypted — but nothing
ever read it: ADMZ authenticates as the App via the private key, and a client
secret is only for OAuth user-to-server flows it does not perform. A credential
held at rest with no reader is attack surface and nothing else.

The setting keys carrying secrets contain ``key``/``secret`` in their name so
``admz/redact.py`` masks them automatically, and they're listed in
``PROTECTED_SETTING_KEYS`` so anonymous / MCP writers are refused.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from pathlib import Path
from typing import Optional

from admz.fleet_settings import fleet_settings

logger = logging.getLogger(__name__)

# --- fleet-setting keys (also registered PROTECTED in fleet_settings) ---
KEY_APP_ID = "github_app_id"
KEY_APP_SLUG = "github_app_slug"
KEY_PRIVATE_KEY = "github_app_private_key"        # stores CIPHERTEXT (secret)
KEY_CLIENT_SECRET = "github_app_client_secret"    # LEGACY (#172): no longer
#: written or read. Retained so `setting_policy` keeps masking and refusing
#: LLM writes to any value an older install still holds; `save_app` deletes it.
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


# Re-exported from admz.setting_crypto, which owns the one Fernet path for
# fleet-setting secrets (#296). This module and admz/survey/secrets.py each had
# an identical private copy; a third was about to appear for default_password,
# so they were collapsed instead. Same key file, same tokens — names and
# behaviour here are unchanged, and existing ciphertext still decrypts.
# ``_key_path`` stays: the signing-key derivation below reads the key bytes.
from admz.setting_crypto import decrypt, encrypt  # noqa: E402,F401


# ---------------------------------------------------------------------------
# App credentials (written by the setup-callback route)
# ---------------------------------------------------------------------------


def save_app(app_id, slug: str, private_key_pem: str) -> None:
    """Persist the App identity + private key (encrypted) after the manifest
    conversion. Does NOT set the installation (that comes from the install
    callback).

    **The client secret is deliberately not stored (GH #172).** GitHub's
    manifest conversion returns one, and this function used to encrypt and keep
    it — but nothing in ADMZ ever read it back: there is no getter, and no
    caller. ADMZ authenticates as the App via the *private key* (JWT →
    installation token); a client secret is only for OAuth **user**-to-server
    flows, which ADMZ does not perform.

    So it was a real credential held at rest, forever, to no purpose — pure
    attack surface. A stored secret with no reader cannot be protected by
    anything except not having it.

    Any value written by an earlier version is **deleted here**, so an install
    that re-runs the App setup is cleaned without a migration. `KEY_CLIENT_SECRET`
    stays in `setting_policy`'s protected and encrypted sets on purpose: an
    install that never re-runs setup still has the old value, and it must stay
    masked and un-writable by the LLM until it is gone.
    """
    fleet_settings.set(KEY_APP_ID, str(app_id))
    fleet_settings.set(KEY_APP_SLUG, slug or "")
    fleet_settings.set(KEY_PRIVATE_KEY, encrypt(private_key_pem))
    # Clear rather than leave: this is the one moment we know the caller is
    # (re)establishing App credentials, so it is the natural cleanup point.
    try:
        fleet_settings.delete(KEY_CLIENT_SECRET)
    except Exception:  # noqa: BLE001 — never fail a setup over a cleanup
        logger.warning("could not clear the legacy %s", KEY_CLIENT_SECRET,
                       exc_info=True)


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
