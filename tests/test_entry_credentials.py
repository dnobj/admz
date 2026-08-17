"""Entry credentials — the list ADMZ tries to get INTO a device (FR-CRED-011).

ADR-0061 splits one credential doing two jobs. This is the first half: the
credential that gets ADMZ in. The measurement that motivated it — production's
`default_username` was `operator` while none of its nine stored device accounts
used it — is the shape these tests protect against recurring.
"""

from __future__ import annotations

import json

import pytest

from admz import entry_credentials as ec


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """A throwaway ADMZ_HOME. These tests write credentials; one that reached a
    real store would put test passwords in the operator's fleet settings."""
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    from admz.fleet_settings import fleet_settings

    for key in (ec.SETTING_KEY, ec.LEGACY_USER_KEY, ec.LEGACY_PASS_KEY):
        try:
            fleet_settings.delete(key)
        except Exception:  # noqa: BLE001 — absent is the normal case
            pass
    return fleet_settings


# ── the legacy pair keeps working ───────────────────────────────────────────

def test_the_legacy_pair_is_entry_one(isolated_settings):
    """An install that has never touched this feature must behave as before."""
    isolated_settings.set(ec.LEGACY_USER_KEY, "operator")
    isolated_settings.set(ec.LEGACY_PASS_KEY, "s3cret")
    creds = ec.list_entry_credentials()
    assert [(c.username, c.password) for c in creds] == [("operator", "s3cret")]


def test_the_legacy_username_defaults_to_root(isolated_settings):
    """`default_username` unset with a password set is a real install shape."""
    isolated_settings.set(ec.LEGACY_PASS_KEY, "s3cret")
    assert ec.list_entry_credentials()[0].username == "root"


def test_no_credentials_at_all_is_an_empty_list_not_an_error(isolated_settings):
    assert ec.list_entry_credentials() == []


def test_the_legacy_pair_is_tried_FIRST(isolated_settings):
    """It is the one an operator most recently confirmed by hand."""
    isolated_settings.set(ec.LEGACY_PASS_KEY, "legacy")
    ec.add_entry_credential("root", "added")
    assert ec.list_entry_credentials()[0].password == "legacy"


# ── the list ────────────────────────────────────────────────────────────────

def test_added_credentials_come_back(isolated_settings):
    assert ec.add_entry_credential("root", "one", "batch A") is True
    assert ec.add_entry_credential("admz", "two", "batch B") is True
    got = [(c.username, c.password, c.label) for c in ec.list_entry_credentials()]
    assert got == [("root", "one", "batch A"), ("admz", "two", "batch B")]


def test_an_exact_duplicate_is_not_added_twice(isolated_settings):
    assert ec.add_entry_credential("root", "one") is True
    assert ec.add_entry_credential("root", "one") is False
    assert len(ec.list_entry_credentials()) == 1


def test_a_duplicate_of_the_LEGACY_pair_is_refused(isolated_settings):
    """It would spend one of the capped attempt slots on the credential
    already being tried first."""
    isolated_settings.set(ec.LEGACY_USER_KEY, "operator")
    isolated_settings.set(ec.LEGACY_PASS_KEY, "s3cret")
    assert ec.add_entry_credential("operator", "s3cret") is False
    assert len(ec.list_entry_credentials()) == 1


def test_same_username_different_password_IS_a_distinct_credential(isolated_settings):
    """Control for the two tests above — dedup must not collapse eras.

    A fleet built over time has several `root` passwords; treating them as one
    credential is exactly the single-pair limitation this replaces.
    """
    ec.add_entry_credential("root", "old")
    ec.add_entry_credential("root", "new")
    assert len(ec.list_entry_credentials()) == 2


@pytest.mark.parametrize("user,password", [("", "p"), ("u", ""), ("   ", "p")])
def test_a_half_credential_is_refused(isolated_settings, user, password):
    with pytest.raises(ValueError):
        ec.add_entry_credential(user, password)


# ── the storage cap ─────────────────────────────────────────────────────────

def test_storing_more_than_the_cap_is_refused(isolated_settings):
    """Capped on STORAGE, not on attempts.

    Capping attempts while letting the list grow would be worse than no cap:
    the settings page would show six credentials, ADMZ would try three, and the
    other three would be a lie the operator had no way to see.
    """
    for i in range(ec.MAX_STORED):
        assert ec.add_entry_credential(f"user{i}", f"pass{i}") is True
    with pytest.raises(ValueError, match="at most"):
        ec.add_entry_credential("one-too-many", "p")
    assert len(ec.list_entry_credentials()) == ec.MAX_STORED


def test_under_the_cap_adds_succeed(isolated_settings):
    """Control for the test above."""
    for i in range(ec.MAX_STORED - 1):
        assert ec.add_entry_credential(f"user{i}", f"pass{i}") is True
    assert len(ec.list_entry_credentials()) == ec.MAX_STORED - 1


def test_the_legacy_pair_occupies_a_slot(isolated_settings):
    """It is one of the credentials that gets tried, so it counts."""
    isolated_settings.set(ec.LEGACY_PASS_KEY, "legacy")
    for i in range(ec.MAX_STORED - 1):
        assert ec.add_entry_credential(f"user{i}", f"pass{i}") is True
    with pytest.raises(ValueError, match="at most"):
        ec.add_entry_credential("extra", "p")


def test_attempt_order_is_the_stored_list(isolated_settings):
    """Nothing is trimmed at try-time, because nothing over-large is stored."""
    isolated_settings.set(ec.LEGACY_PASS_KEY, "legacy")
    ec.add_entry_credential("a", "1")
    assert ec.attempt_order() == ec.list_entry_credentials()
    assert ec.attempt_order()[0].password == "legacy"


# ── the "store none, prompt every time" posture ─────────────────────────────

def test_prompt_always_yields_no_credentials(isolated_settings):
    """A decision, not a state. Turning it on stops ADMZ using a stored
    credential immediately, with nothing to delete first."""
    ec.add_entry_credential("root", "stored")
    assert len(ec.list_entry_credentials()) == 1
    isolated_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
    assert ec.list_entry_credentials() == []
    assert ec.attempt_order() == []


def test_prompt_always_does_not_destroy_what_was_stored(isolated_settings):
    """Turning the posture off restores them — which is why nothing is deleted
    on the operator's behalf."""
    ec.add_entry_credential("root", "stored")
    isolated_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
    assert ec.list_entry_credentials() == []
    isolated_settings.set(ec.PROMPT_ALWAYS_KEY, "false")
    assert [c.password for c in ec.list_entry_credentials()] == ["stored"]


def test_prompt_always_refuses_new_credentials(isolated_settings):
    """Otherwise it would be a state the next add silently overturns."""
    isolated_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
    with pytest.raises(ValueError, match="stores no entry credentials"):
        ec.add_entry_credential("root", "p")


def test_prompt_always_also_ignores_the_LEGACY_pair(isolated_settings):
    """The legacy pair is read from different keys; the posture must cover it
    too, or 'store none' would quietly still try one."""
    isolated_settings.set(ec.LEGACY_PASS_KEY, "legacy")
    isolated_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
    assert ec.list_entry_credentials() == []


@pytest.mark.parametrize("raw,expected", [
    ("true", True), ("1", True), ("yes", True), ("on", True), ("TRUE", True),
    ("false", False), ("0", False), ("", False), ("maybe", False),
])
def test_the_posture_flag_parses_conservatively(isolated_settings, raw, expected):
    """An unrecognised value means OFF — the posture must be chosen, never
    arrived at by a typo."""
    isolated_settings.set(ec.PROMPT_ALWAYS_KEY, raw)
    assert ec.prompt_always() is expected


def test_describe_distinguishes_stored_from_in_use(isolated_settings):
    """An operator reading '0 credentials' should know whether that is a policy
    or an empty box."""
    ec.add_entry_credential("root", "stored", "batch A")
    isolated_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
    d = ec.describe()
    assert d["prompt_always"] is True
    assert len(d["stored"]) == 1 and d["in_use"] == []
    assert "stored" not in json.dumps(d["stored"])  # the password, not the key


# ── stored encrypted, never leaked ──────────────────────────────────────────

def test_the_list_is_encrypted_at_rest(isolated_settings, tmp_path):
    """ADR-0061 makes these the only route back into a fleet after a database
    loss — recovery material, not merely sensitive."""
    import sqlite3

    ec.add_entry_credential("root", "PLAINTEXT-CANARY")
    from admz.paths import db_path

    with sqlite3.connect(str(db_path())) as conn:
        raw = conn.execute(
            "SELECT value FROM fleet_settings WHERE key=?", (ec.SETTING_KEY,)
        ).fetchone()[0]
    assert "PLAINTEXT-CANARY" not in raw, "the entry list is sitting in plaintext"
    assert raw.startswith("gAAAAA"), "expected Fernet ciphertext"


def test_the_key_is_recognised_as_sensitive():
    """The predicate gap that let `pwd` through in #336, arriving by a new
    route: none of password/passwd/secret/token/api_key appears in
    'entry_credentials'."""
    from admz.redact import is_sensitive_key

    assert is_sensitive_key(ec.SETTING_KEY)


def test_describe_never_returns_a_password(isolated_settings):
    ec.add_entry_credential("root", "PLAINTEXT-CANARY", "batch A")
    blob = json.dumps(ec.describe())
    assert "PLAINTEXT-CANARY" not in blob
    assert "root" in blob and "batch A" in blob


def test_redacted_never_returns_a_password():
    cred = ec.EntryCredential("root", "PLAINTEXT-CANARY", "note")
    assert "PLAINTEXT-CANARY" not in json.dumps(cred.redacted())


# ── malformed storage degrades, never raises ────────────────────────────────

@pytest.mark.parametrize("raw", ["not json", "{}", "[1,2,3]", '[{"username":"u"}]', ""])
def test_malformed_storage_reads_as_empty(isolated_settings, raw):
    """A corrupt setting must not break every device adoption. An entry missing
    half a pair cannot authenticate anything and would burn an attempt slot."""
    isolated_settings.set(ec.SETTING_KEY, raw)
    assert ec.list_entry_credentials() == []
