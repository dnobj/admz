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
    """Capped on STORAGE — what the settings page shows is what exists.

    The device-facing loop is bounded separately to the same number (ADR-0064
    slice C, below), so the page can never show six credentials while ADMZ
    tries three.
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
    """Under the bound nothing is trimmed: the stored order, legacy first."""
    isolated_settings.set(ec.LEGACY_PASS_KEY, "legacy")
    ec.add_entry_credential("a", "1")
    assert ec.attempt_order() == ec.list_entry_credentials()
    assert ec.attempt_order()[0].password == "legacy"


def _store_raw(settings, n):
    """What the CLI writer can do: bypass the storage cap entirely."""
    settings.set(ec.SETTING_KEY, json.dumps(
        [{"username": f"u{i}", "password": f"p{i}", "label": f"batch {i}"} for i in range(n)]
    ))


def test_a_pass_tries_at_most_the_bound_when_the_raw_setting_holds_more(isolated_settings, caplog):
    """ADR-0064 slice C: the storage cap is bypassable (`_parse` never
    truncates), so the bound lives where the attempt list is built."""
    _store_raw(isolated_settings, 5)
    assert len(ec.list_entry_credentials()) == 5, "stored: all five"
    with caplog.at_level("WARNING", logger="admz.entry_credentials"):
        tried = ec.attempt_order()
    assert [c.username for c in tried] == ["u0", "u1", "u2"]
    assert len(tried) == ec.MAX_ATTEMPTS_PER_PASS == ec.MAX_STORED
    assert any("tries at most" in r.getMessage() for r in caplog.records)


def test_the_legacy_pair_counts_against_the_bound(isolated_settings):
    isolated_settings.set(ec.LEGACY_PASS_KEY, "legacy")
    _store_raw(isolated_settings, 5)
    tried = ec.attempt_order()
    assert tried[0].password == "legacy"
    assert len(tried) == ec.MAX_ATTEMPTS_PER_PASS


def test_describe_reports_what_is_tried_not_what_is_stored(isolated_settings):
    """`in_use` is the attempt list, so the settings page cannot claim five
    credentials are tried when three are."""
    _store_raw(isolated_settings, 5)
    d = ec.describe()
    assert len(d["stored"]) == 5
    assert len(d["in_use"]) == ec.MAX_ATTEMPTS_PER_PASS


def _bound_warnings(caplog):
    return [r for r in caplog.records if "tries at most" in r.getMessage()]


def test_an_install_at_exactly_the_bound_is_not_warned_about(isolated_settings, caplog):
    """The documented normal state — a full list — is not an over-bound list."""
    _store_raw(isolated_settings, ec.MAX_ATTEMPTS_PER_PASS)
    with caplog.at_level("WARNING", logger="admz.entry_credentials"):
        tried = ec.attempt_order()
    assert len(tried) == ec.MAX_ATTEMPTS_PER_PASS
    assert _bound_warnings(caplog) == []


def test_the_warning_carries_counts_never_credentials(isolated_settings, caplog):
    _store_raw(isolated_settings, 5)
    with caplog.at_level("WARNING", logger="admz.entry_credentials"):
        ec.attempt_order()
    assert len(_bound_warnings(caplog)) == 1
    for i in range(5):
        assert f"p{i}" not in caplog.text and f"u{i}" not in caplog.text
    # and the record's repr cannot leak it into a future %s or a traceback
    assert "s3cret" not in repr(ec.EntryCredential("u", "s3cret", "lab"))


def test_describe_reads_without_warning(isolated_settings, caplog):
    """A settings-page read is not a pass: the WARNING belongs to the pass
    that truncates the list, not to every page view."""
    _store_raw(isolated_settings, 5)
    with caplog.at_level("WARNING", logger="admz.entry_credentials"):
        d = ec.describe()
    assert len(d["in_use"]) == d["max_attempts_per_pass"] == ec.MAX_ATTEMPTS_PER_PASS
    assert _bound_warnings(caplog) == []


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


# ── refusals carry a stable code ────────────────────────────────────────────

def test_every_add_refusal_is_a_ValueError_with_a_code(isolated_settings):
    """A `ValueError`, so the capture form's `except ValueError` is unchanged;
    a code, so an audit row need not match on the message."""
    with pytest.raises(ec.EntryCredentialRefused) as half:
        ec.add_entry_credential("root", "")
    assert isinstance(half.value, ValueError)
    assert half.value.code == ec.REFUSED_INCOMPLETE

    for i in range(ec.MAX_STORED):
        ec.add_entry_credential(f"u{i}", f"p{i}")
    with pytest.raises(ec.EntryCredentialRefused) as cap:
        ec.add_entry_credential("extra", "p")
    assert cap.value.code == ec.REFUSED_CAP

    isolated_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
    with pytest.raises(ec.EntryCredentialRefused) as posture:
        ec.add_entry_credential("root", "p")
    assert posture.value.code == ec.REFUSED_PROMPT_ALWAYS


# ── an unreadable list is never overwritten ─────────────────────────────────

def _foreign_ciphertext():
    """A real Fernet token under a key this install does not hold."""
    from cryptography.fernet import Fernet

    return Fernet(Fernet.generate_key()).encrypt(
        b'[{"username": "u", "password": "p"}]').decode()


def test_an_add_refuses_rather_than_overwrite_an_unreadable_list(isolated_settings):
    """`setting_crypto.read_stored` leaves an undecryptable value in place so
    that restoring the right key recovers it. It reads as empty, and an add
    rewrites the list from what it read — so without the refusal one promotion
    would replace the whole list with a single entry."""
    foreign = _foreign_ciphertext()
    isolated_settings._raw_set(ec.SETTING_KEY, foreign)
    assert isolated_settings.get(ec.SETTING_KEY) is None, "CONTROL: it reads as unset"
    with pytest.raises(ec.EntryCredentialRefused) as exc:
        ec.add_entry_credential("root", "new")
    assert exc.value.code == ec.REFUSED_UNREADABLE
    assert isolated_settings._raw_get(ec.SETTING_KEY) == foreign


def test_an_unset_list_is_not_mistaken_for_an_unreadable_one(isolated_settings):
    """Control for the test above."""
    assert ec.add_entry_credential("root", "new") is True
    assert ec.describe()["unreadable"] is False


def test_describe_says_when_the_list_is_unreadable(isolated_settings):
    isolated_settings._raw_set(ec.SETTING_KEY, _foreign_ciphertext())
    d = ec.describe()
    assert d["unreadable"] is True and d["stored"] == []


@pytest.mark.parametrize("raw", [
    "not json",
    '{"username": "u", "password": "p"}',
    "[1, 2]",
    '[{"username": "u0", "password": "p0"}, {"username": "half"}]',
])
def test_a_list_that_decrypts_but_is_not_complete_pairs_is_unreadable_too(isolated_settings, raw):
    """Readers skip what `_parse` cannot use. Every write rewrites the whole
    list from what it read, so a write would silently drop what was skipped —
    and refuses instead."""
    isolated_settings.set(ec.SETTING_KEY, raw)
    before = isolated_settings._raw_get(ec.SETTING_KEY)
    assert ec.describe()["unreadable"] is True
    with pytest.raises(ec.EntryCredentialRefused) as exc:
        ec.add_entry_credential("root", "new")
    assert exc.value.code == ec.REFUSED_UNREADABLE
    assert isolated_settings._raw_get(ec.SETTING_KEY) == before


@pytest.mark.parametrize("raw", ["", "[]", '[{"username": "u", "password": "p"}]'])
def test_an_empty_or_complete_list_is_readable(isolated_settings, raw):
    """Control for the test above."""
    isolated_settings.set(ec.SETTING_KEY, raw)
    assert ec.describe()["unreadable"] is False


# ── removal ─────────────────────────────────────────────────────────────────

def _three():
    for i in range(3):
        ec.add_entry_credential(f"u{i}", f"p{i}", f"batch {i}")


def test_removal_takes_the_entry_at_the_position_and_keeps_the_order(isolated_settings):
    _three()
    out = ec.remove_entry_credential(1, revision=ec.list_revision())
    assert out == {"username": "u1", "label": "batch 1", "legacy_pair": False}
    assert [c.username for c in ec.list_entry_credentials()] == ["u0", "u2"]


def test_a_revision_from_before_a_write_is_stale(isolated_settings):
    """Including this very removal resubmitted, as a browser reload does: its
    own write moved the revision. By position alone the resubmission would
    remove the entry that moved up into the removed one's place."""
    _three()
    shown = ec.list_revision()
    ec.remove_entry_credential(0, revision=shown)
    with pytest.raises(ec.EntryCredentialRefused) as exc:
        ec.remove_entry_credential(0, revision=shown)
    assert exc.value.code == ec.REFUSED_STALE
    assert [c.username for c in ec.list_entry_credentials()] == ["u1", "u2"]


@pytest.mark.parametrize("position,revision", [
    (3, None), (-1, None), (0, "0" * 32), (0, ""), (0, "ünïcödé"),
])
def test_removal_refuses_a_position_or_revision_the_page_never_had(
        isolated_settings, position, revision):
    _three()
    with pytest.raises(ec.EntryCredentialRefused) as exc:
        ec.remove_entry_credential(
            position, revision=ec.list_revision() if revision is None else revision)
    assert exc.value.code == ec.REFUSED_STALE
    assert len(ec.list_entry_credentials()) == 3


def test_the_revision_moves_on_every_write_and_holds_across_reads(isolated_settings):
    """Rewriting an identical list still moves it — it covers the stored
    ciphertext, so it is no function of the passwords — and so does setting the
    legacy pair, whose presence shifts every position by one."""
    raw = json.dumps([{"username": "u", "password": "p"}])
    isolated_settings.set(ec.SETTING_KEY, raw)
    first = ec.list_revision()
    ec.list_entry_credentials()
    ec.describe()
    assert ec.list_revision() == first, "a read must not make an open page stale"
    isolated_settings.set(ec.SETTING_KEY, raw)
    second = ec.list_revision()
    assert second != first
    isolated_settings.set(ec.LEGACY_PASS_KEY, "legacy")
    assert ec.list_revision() != second


def test_removing_the_legacy_pair_deletes_both_of_its_settings(isolated_settings):
    isolated_settings.set(ec.LEGACY_USER_KEY, "operator")
    isolated_settings.set(ec.LEGACY_PASS_KEY, "legacy")
    ec.add_entry_credential("u0", "p0", "batch 0")
    out = ec.remove_entry_credential(0, revision=ec.list_revision())
    assert out == {"username": "operator", "label": ec.LEGACY_LABEL, "legacy_pair": True}
    assert isolated_settings.get(ec.LEGACY_PASS_KEY) is None
    assert isolated_settings.get(ec.LEGACY_USER_KEY) is None
    assert [(c.username, c.password) for c in ec.list_entry_credentials()] == [("u0", "p0")]


def test_positions_after_the_legacy_pair_count_it(isolated_settings):
    """The position is the settings page's order, where the legacy pair is #1."""
    isolated_settings.set(ec.LEGACY_PASS_KEY, "legacy")
    ec.add_entry_credential("u0", "p0", "batch 0")
    ec.remove_entry_credential(1, revision=ec.list_revision())
    assert [c.password for c in ec.list_entry_credentials()] == ["legacy"]


def test_removal_is_allowed_under_prompt_always(isolated_settings):
    """It narrows what is tried; only widening is refused."""
    ec.add_entry_credential("u0", "p0", "batch 0")
    isolated_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
    ec.remove_entry_credential(0, revision=ec.list_revision())
    assert ec.describe()["stored"] == []


def test_removal_refuses_an_unreadable_list(isolated_settings):
    foreign = _foreign_ciphertext()
    isolated_settings._raw_set(ec.SETTING_KEY, foreign)
    with pytest.raises(ec.EntryCredentialRefused) as exc:
        ec.remove_entry_credential(0, revision=ec.list_revision())
    assert exc.value.code == ec.REFUSED_UNREADABLE
    assert isolated_settings._raw_get(ec.SETTING_KEY) == foreign


# ── what describe() marks as tried ──────────────────────────────────────────

def test_an_exact_duplicate_is_marked_tried_once(isolated_settings):
    """It is tried once, so of two identical-looking rows only the first is
    live — and the distinct credential after them IS tried. Matching on
    username and label got both of those wrong."""
    isolated_settings.set(ec.SETTING_KEY, json.dumps([
        {"username": "root", "password": "p1"},
        {"username": "root", "password": "p1"},
        {"username": "root", "password": "p2"},
    ]))
    assert ec.describe()["stored_tried"] == [True, False, True]


def test_an_entry_duplicating_the_legacy_pair_is_not_marked_tried(isolated_settings):
    isolated_settings.set(ec.LEGACY_PASS_KEY, "legacy")
    isolated_settings.set(ec.SETTING_KEY, json.dumps([{"username": "root", "password": "legacy"}]))
    assert ec.describe()["stored_tried"] == [True, False]


def test_nothing_is_marked_tried_under_prompt_always(isolated_settings):
    ec.add_entry_credential("u0", "p0")
    isolated_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
    assert ec.describe()["stored_tried"] == [False]


# ── ADMZ's break-glass attempt ──────────────────────────────────────────────

def test_the_break_glass_attempt_is_root_whatever_default_username_says(isolated_settings):
    """Provisioning writes the break-glass value to `root`. `default_username`
    belongs to an unrelated legacy entry credential — `operator` on the fleet
    ADR-0061 measured — and paired with it the attempt could never log in."""
    isolated_settings.set(ec.LEGACY_USER_KEY, "operator")
    isolated_settings.set("fleet_root_password", "BreakGlass-ec-1")
    last = ec.attempt_order()[-1]
    assert (last.username, last.password) == ("root", "BreakGlass-ec-1")


def test_describe_reports_the_break_glass_attempt_apart(isolated_settings):
    ec.add_entry_credential("u0", "p0")
    assert ec.describe()["break_glass_last"] is False
    isolated_settings.set("fleet_root_password", "BreakGlass-ec-2")
    d = ec.describe()
    assert d["break_glass_last"] is True
    assert len(d["in_use"]) == 2, "in_use still reports every attempt"
