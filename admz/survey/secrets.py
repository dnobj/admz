"""
Encrypt/decrypt the GitHub PAT (and any survey secret) at rest.

The PAT is a real secret, so it is **not** stored as plaintext in the fleet-
settings table. We reuse the same Fernet key the SQLite registry uses for device
passwords (``ADMZ_KEY_PATH`` / ``~/.admz/admz.key``), so there's a single key to
protect and rotate. Storage still goes through ``fleet_settings`` — but only the
ciphertext lands there.

Survey config helpers also live here so routes/scheduler share one source of
truth for the setting keys.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from admz.fleet_settings import fleet_settings

# --- fleet-setting keys (also registered PROTECTED in fleet_settings) ---
KEY_ENABLED = "survey_mode_enabled"
KEY_PAT = "survey_github_pat"               # stores CIPHERTEXT
KEY_REPO = "survey_repo"
KEY_REDACTION = "survey_redaction_profile"  # hash-serial | keep-serial
KEY_VALIDATION_TIER = "survey_validation_tier"   # "0" | "1"
KEY_SCHEDULE_SECONDS = "survey_schedule_seconds"
KEY_CONTRIBUTOR = "survey_contributor"      # opt-in handle / site label

DEFAULT_REPO = "mrdnlabs/axis-api-atlas"
DEFAULT_REDACTION = "hash-serial"


def _key_path() -> Path:
    from admz.paths import key_path
    return key_path()


# Re-exported from admz.setting_crypto, which owns the one Fernet path for
# fleet-setting secrets (#296). This module and admz/github_app/secrets.py each
# had an identical private copy; a third was about to appear for
# default_password, so they were collapsed instead. Same key file, same tokens —
# names and behaviour here are unchanged, and existing ciphertext still
# decrypts. ``_key_path`` stays because ``hmac_key`` below reads the key bytes.
from admz.setting_crypto import decrypt, encrypt  # noqa: E402,F401


# ---------------------------------------------------------------------------
# PAT storage
# ---------------------------------------------------------------------------


def set_pat(plain_pat: str) -> None:
    """Store the PAT encrypted. Empty string clears it."""
    if not plain_pat:
        fleet_settings.delete(KEY_PAT)
        return
    fleet_settings.set(KEY_PAT, encrypt(plain_pat))


def get_pat() -> Optional[str]:
    """Return the decrypted PAT, or None if unset/undecryptable."""
    token = fleet_settings.get(KEY_PAT)
    if not token:
        return None
    try:
        return decrypt(token)
    except Exception:  # noqa: BLE001 - wrong key / corrupt value
        return None


def has_pat() -> bool:
    return bool(fleet_settings.get(KEY_PAT))


# ---------------------------------------------------------------------------
# config accessors
# ---------------------------------------------------------------------------


def is_enabled() -> bool:
    """True when survey/contributor mode is on for this installation.

    Delegates to the advanced-capability registry (GH #132) so survey mode is
    declared in the same table as every other privileged switch, shows in
    ``/api/health`` and the topbar chip, and can be stopped from
    ``/settings/advanced`` without a restart. Name, signature, and the
    ``survey_mode_enabled`` setting are unchanged — ``ADMZ_SURVEY_MODE`` is an
    additive env alias that wins when set, matching every other hybrid flag.
    """
    from admz import capabilities

    return capabilities.is_active("survey.contributor")


def get_repo() -> str:
    return fleet_settings.get(KEY_REPO) or DEFAULT_REPO


def get_redaction_profile() -> str:
    return fleet_settings.get(KEY_REDACTION) or DEFAULT_REDACTION


def get_validation_tier() -> int:
    try:
        return int(fleet_settings.get(KEY_VALIDATION_TIER) or "0")
    except ValueError:
        return 0


def get_contributor() -> str:
    return fleet_settings.get(KEY_CONTRIBUTOR) or ""


def hmac_key() -> bytes:
    """A stable per-install key for hashing serials (derived from the Fernet key)."""
    return _key_path().read_bytes().strip() if _key_path().exists() else b"admz-survey"
