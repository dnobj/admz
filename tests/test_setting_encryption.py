"""GH #296 part 1: fleet-setting secrets are encrypted at rest.

``default_password`` is the credential ADMZ *writes to* devices. Every credential
it stores *about* a device already went through Fernet; this one did not, and
neither did ``gemini_api_key`` or ``acs_webhook_token``.

**The vacuity shape this file is built around.** "The stored value is not the
password" is trivially true if nothing was stored, and "the plaintext is gone
from the file" is trivially true if it was never there. So the on-disk test
below asserts a CONTROL first — that the plaintext IS findable in the raw .db
before migration — and only then that it is absent afterwards. Without that
control the migration proof is worthless.

**Recoverable, not hashed.** These values must come back out; they are encrypted,
never digested. ``confirm_password_hash`` is the opposite and is deliberately
excluded — see ``test_the_partition_covers_every_sensitive_key``.
"""

import sqlite3
from pathlib import Path

import pytest

from admz import setting_crypto
from admz.fleet_settings import FleetSettings, mask_settings_for_display
from admz.setting_policy import (
    KNOWN_SETTING_KEYS,
    MODULE_ENCRYPTED_SETTING_KEYS,
    NOT_ENCRYPTED_SENSITIVE_KEYS,
    STORE_ENCRYPTED_SETTING_KEYS,
)

SECRET = "SuperSecretFleetPw-9f3a1c"


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A settings store on its own DB, with its own Fernet key.

    ``ADMZ_KEY_PATH`` is redirected so no test can reach the operator's real
    ``admz.key`` — and so that the rotated-key test can swap it.
    """
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    return FleetSettings(db_path=str(tmp_path / "admz.db"))


def _raw(store, key):
    """What is physically in the row, bypassing decryption."""
    conn = sqlite3.connect(store._db_path)
    try:
        row = conn.execute(
            "SELECT value FROM fleet_settings WHERE key=?", (key,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


# --- round trip ------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(STORE_ENCRYPTED_SETTING_KEYS))
def test_round_trips_and_is_not_stored_in_the_clear(store, key):
    store.set(key, SECRET)

    # The control: something WAS stored. Without this the next assertion passes
    # for a store that silently dropped the write.
    raw = _raw(store, key)
    assert raw, "nothing was stored at all — the assertions below prove nothing"

    assert raw != SECRET, f"{key} was stored in the clear"
    assert setting_crypto.looks_encrypted(raw)
    assert store.get(key) == SECRET, "the value did not survive the round trip"


def test_recoverable_not_hashed(store):
    """The distinction #296 warns about: this must decrypt, not merely compare."""
    store.set("default_password", SECRET)
    assert setting_crypto.decrypt(_raw(store, "default_password")) == SECRET


def test_each_write_produces_a_distinct_token(store):
    """Fernet embeds a timestamp and IV, so identical plaintexts differ at rest."""
    store.set("default_password", SECRET)
    first = _raw(store, "default_password")
    store.set("default_password", SECRET)
    assert _raw(store, "default_password") != first
    assert store.get("default_password") == SECRET


def test_non_secret_keys_are_untouched(store):
    store.set("default_username", "admin")
    assert _raw(store, "default_username") == "admin"
    assert store.get("default_username") == "admin"


def test_empty_value_is_not_encrypted(store):
    """An empty string is the 'cleared' marker; encrypting it would make a
    cleared setting indistinguishable from a set one at rest."""
    store.set("default_password", "")
    assert _raw(store, "default_password") == ""
    assert store.get("default_password") is None


def test_missing_key_returns_none(store):
    assert store.get("default_password") is None


# --- migration -------------------------------------------------------------


def _plant_plaintext(store, key, value):
    """Write a legacy plaintext row, as a pre-#296 install would have."""
    conn = sqlite3.connect(store._db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS fleet_settings "
                     "(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT OR REPLACE INTO fleet_settings VALUES (?,?)", (key, value))
        conn.commit()
    finally:
        conn.close()


def test_existing_plaintext_still_works(store):
    """The upgrade must not lock an operator out of their own fleet password."""
    _plant_plaintext(store, "default_password", SECRET)
    assert store.get("default_password") == SECRET


def test_reading_migrates_in_place(store):
    _plant_plaintext(store, "default_password", SECRET)
    assert _raw(store, "default_password") == SECRET      # control: plaintext at rest

    store.get("default_password")

    raw = _raw(store, "default_password")
    assert raw != SECRET, "the row still holds the plaintext"
    assert setting_crypto.looks_encrypted(raw)
    assert store.get("default_password") == SECRET, "migration broke the value"


def test_migration_leaves_no_plaintext_in_the_database_file(store):
    """'Gone', not merely 'superseded'.

    A row rewritten by ``ON CONFLICT DO UPDATE`` could in principle leave the
    old bytes in a free page — SQLite does not zero freed space by default. So
    this greps the raw file, and asserts the CONTROL first: the plaintext must
    be findable before migration, or the post-migration assertion is vacuous.
    """
    _plant_plaintext(store, "default_password", SECRET)
    db = Path(store._db_path)

    assert SECRET.encode() in db.read_bytes(), (
        "CONTROL FAILED: the plaintext was not in the file to begin with, so "
        "its absence below would prove nothing")

    store.get("default_password")          # migrate

    assert SECRET.encode() not in db.read_bytes(), (
        "the plaintext is still recoverable from the database file")
    for side in ("-wal", "-shm"):
        f = Path(str(db) + side)
        if f.exists():
            assert SECRET.encode() not in f.read_bytes(), f"plaintext left in {side}"


def test_migration_is_idempotent(store):
    _plant_plaintext(store, "default_password", SECRET)
    store.get("default_password")
    once = _raw(store, "default_password")
    assert store.get("default_password") == SECRET
    assert _raw(store, "default_password") == once, "re-encrypted an already-encrypted value"


def test_a_failed_migration_still_returns_the_value(store, monkeypatch):
    """A read-only or locked DB must not break a read that otherwise worked."""
    _plant_plaintext(store, "default_password", SECRET)

    def _boom(*a, **k):
        raise sqlite3.OperationalError("attempt to write a readonly database")

    monkeypatch.setattr(FleetSettings, "_raw_set", _boom)
    assert store.get("default_password") == SECRET


# --- the trap: undecryptable is not the same as legacy plaintext -----------


def test_undecryptable_value_is_not_overwritten(store, tmp_path, monkeypatch):
    """A rotated key must not destroy the secret.

    If ciphertext-that-will-not-decrypt were treated as legacy plaintext, the
    store would hand the caller a Fernet token as if it were a password AND
    re-encrypt it, making the real value unrecoverable even with the right key
    restored.
    """
    store.set("default_password", SECRET)
    original = _raw(store, "default_password")

    from cryptography.fernet import Fernet
    (tmp_path / "admz.key").write_bytes(Fernet.generate_key())   # rotate
    setting_crypto._fernet.cache_clear() if hasattr(
        setting_crypto._fernet, "cache_clear") else None

    assert store.get("default_password") is None, "returned garbage as a password"
    assert _raw(store, "default_password") == original, (
        "the unreadable value was overwritten — it is now unrecoverable")


@pytest.mark.parametrize("value,expected", [
    ("hunter2", False),
    ("", False),
    (None, False),
    ("gAAAAA", False),                       # right prefix, far too short
    ("gAAAAA" + "x" * 200, True),            # prefix + plausible length
    ("x" * 300, False),                      # long, wrong prefix
])
def test_looks_encrypted(value, expected):
    assert setting_crypto.looks_encrypted(value) is expected


def test_looks_encrypted_accepts_a_real_token(store):
    assert setting_crypto.looks_encrypted(setting_crypto.encrypt("x"))


# --- the sweep: no secret may be silently left in plaintext ----------------


def test_the_partition_covers_every_sensitive_key():
    """A new secret setting must be declared, or CI fails.

    This is the guard against the #200 shape — encrypting one key of several and
    reading as done. Adding a sensitive-looking key to ``KNOWN_SETTING_KEYS``
    without deciding how it is stored breaks here rather than sitting in
    plaintext until somebody notices.
    """
    from admz.redact import is_sensitive_key

    sensitive = {k for k in KNOWN_SETTING_KEYS if is_sensitive_key(k)}
    declared = (STORE_ENCRYPTED_SETTING_KEYS
                | MODULE_ENCRYPTED_SETTING_KEYS
                | NOT_ENCRYPTED_SENSITIVE_KEYS)

    assert sensitive - declared == set(), (
        f"undeclared sensitive setting(s): {sorted(sensitive - declared)} — "
        "decide whether each is store-encrypted, module-encrypted, or "
        "deliberately plaintext, and say why")
    assert declared - sensitive == set(), (
        f"declared but not sensitive: {sorted(declared - sensitive)}")


def test_the_three_tiers_are_disjoint():
    """A key encrypted by both the store and its module would be double-encrypted."""
    assert not (STORE_ENCRYPTED_SETTING_KEYS & MODULE_ENCRYPTED_SETTING_KEYS)
    assert not (STORE_ENCRYPTED_SETTING_KEYS & NOT_ENCRYPTED_SENSITIVE_KEYS)
    assert not (MODULE_ENCRYPTED_SETTING_KEYS & NOT_ENCRYPTED_SENSITIVE_KEYS)


def test_module_encrypted_keys_are_not_double_encrypted(store):
    """survey/github_app encrypt before calling set; the store must not re-encrypt."""
    token = setting_crypto.encrypt(SECRET)
    store.set("survey_github_pat", token)
    assert _raw(store, "survey_github_pat") == token
    assert setting_crypto.decrypt(store.get("survey_github_pat")) == SECRET


def test_one_fernet_implementation(store):
    """survey and github_app delegate here rather than keeping their own copies.

    Three identical private implementations of one crypto path is the drift of
    #255/#274; a token from any of them must decrypt with any other.
    """
    from admz.github_app import secrets as gh
    from admz.survey import secrets as sv

    assert gh.encrypt is setting_crypto.encrypt
    assert sv.encrypt is setting_crypto.encrypt
    assert setting_crypto.decrypt(gh.encrypt(SECRET)) == SECRET
    assert gh.decrypt(sv.encrypt(SECRET)) == SECRET


# --- display surfaces ------------------------------------------------------


def test_list_all_returns_plaintext_and_masks_correctly(store):
    store.set("default_password", SECRET)
    store.set("default_username", "admin")

    allv = store.list_all()
    assert allv["default_password"] == SECRET, "list_all leaked ciphertext to callers"

    masked = mask_settings_for_display(allv)
    assert SECRET not in masked["default_password"]
    # The mask reports a length; it must describe the secret, not the token.
    assert f"({len(SECRET)} chars)" in masked["default_password"]
    assert masked["default_username"] == "admin"


def test_list_all_does_not_migrate(store):
    """A settings page render is the wrong moment to start rewriting rows."""
    _plant_plaintext(store, "default_password", SECRET)
    assert store.list_all()["default_password"] == SECRET
    assert _raw(store, "default_password") == SECRET, "list_all migrated a row"


# --- policy interaction (ADR-0053) -----------------------------------------


def test_encryption_does_not_change_who_may_write(store):
    """#219 put default_password in the LLM-writable allow-set; encrypting the
    value at rest must not quietly alter that, in either direction."""
    from admz.fleet_settings import is_protected_setting
    from admz.setting_policy import is_capture_only, is_llm_writable

    assert is_llm_writable("default_password") is True
    assert is_protected_setting("default_password") is False
    # ...and its value still may not come from chat (ADR-0009 capture flow).
    assert is_capture_only("default_password") is True
