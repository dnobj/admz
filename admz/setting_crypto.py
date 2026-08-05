"""Fernet encryption for secret values in the fleet-settings table (GH #296 part 1).

ADMZ encrypts every credential it stores *about* a device, but ``default_password``
— the credential it **writes to** devices — sat in ``fleet_settings`` as a plain
value, protected only by the directory ACL from #252. So did ``gemini_api_key``
and ``acs_webhook_token``.

**Recoverable, not hashed.** ADMZ has to send these values somewhere, so they are
encrypted and decrypted, never digested. That is the opposite of
``confirm_password_hash``, which is only ever compared and is deliberately left
alone — #296 calls out copying that pattern here as the mistake to avoid.

**One key, one implementation.** The Fernet key is the registry's own
(``ADMZ_KEY_PATH`` / ``admz.key``) via ``_build_fernet``, so there is a single
key to protect and rotate — the arrangement ``survey/secrets.py`` and
``github_app/secrets.py`` already chose. Those two modules had grown their own
identical ``encrypt``/``decrypt`` pair each; they now delegate here, so one
Fernet path serves every fleet-setting secret instead of a third copy appearing.

**Migration is read-old-write-new**, and it is the part with a real trap. A value
that will not decrypt is not necessarily legacy plaintext — it is also what a
rotated or missing key looks like. Treating that as plaintext would return
ciphertext to a caller as if it were a password *and re-encrypt the garbage*,
destroying the value irrecoverably. So the two cases are distinguished
structurally before anything is written: see :func:`looks_encrypted`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

#: Every Fernet token begins with the urlsafe-base64 encoding of its 0x80
#: version byte plus an 8-byte timestamp, which is invariably ``gAAAAA``.
#: Verified over 800 tokens across 200 keys and payloads from empty to 500
#: bytes: exactly one distinct prefix, minimum length 100.
_TOKEN_PREFIX = "gAAAAA"
_MIN_TOKEN_LEN = 100


def looks_encrypted(value: Optional[str]) -> bool:
    """True if ``value`` has the structural shape of a Fernet token.

    Used to tell "this is legacy plaintext, migrate it" from "this is
    ciphertext I cannot read", which must NOT be migrated — overwriting an
    undecryptable value would destroy a secret recoverable by restoring the
    right key.

    Both tests matter. The prefix alone would misread a short string that
    happens to start with ``gAAAAA``; the length alone would misread any long
    passphrase. A plaintext password that satisfies *both* is not something a
    human types, and even then the outcome is
    ":func:`get_secret` returns None", not data loss.
    """
    return bool(value) and value.startswith(_TOKEN_PREFIX) and len(value) >= _MIN_TOKEN_LEN


def _key_path() -> Path:
    from admz.paths import key_path
    return key_path()


def _fernet():
    # The registry's helper, so there is exactly one key file (ADR-0010).
    from admz.backends.sqlite_backend import _build_fernet
    return _build_fernet(_key_path())


def encrypt(plain: str) -> str:
    """Plaintext → Fernet token."""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    """Fernet token → plaintext. Raises on a wrong key or a corrupt value."""
    return _fernet().decrypt(token.encode()).decode()


def read_stored(key: str, stored: Optional[str]) -> Tuple[Optional[str], bool]:
    """Interpret a stored value. Returns ``(plaintext, needs_migration)``.

    Three outcomes, and keeping them apart is the whole job:

    * **already ciphertext** → ``(plaintext, False)``
    * **legacy plaintext** → ``(value, True)`` — the caller re-writes it encrypted
    * **undecryptable** (rotated/missing key, corruption) → ``(None, False)``

    The third returns None rather than raising, matching
    ``survey.secrets.get_pat``'s existing "None if unset/undecryptable"
    contract. For ``default_password`` that degrades provisioning to generating
    a per-device password, which is the safe direction — and it never
    overwrites the unreadable value, so restoring the correct key recovers it.
    """
    if stored is None or stored == "":
        return None, False
    if not looks_encrypted(stored):
        return stored, True
    try:
        return decrypt(stored), False
    except Exception:  # noqa: BLE001 — wrong key, corrupt value, missing key file
        logger.warning(
            "fleet setting %r could not be decrypted (wrong or missing %s?). "
            "Treating it as unset; the stored value is left untouched so "
            "restoring the correct key recovers it.",
            key, _key_path().name,
        )
        return None, False
