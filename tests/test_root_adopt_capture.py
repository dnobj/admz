"""FR-CRED-014 / ADR-0068 — a root password ADMZ is given is used once and
never becomes the device's credential.

The operator is asked for the device's administrator password, ADMZ uses it
ONCE to authenticate, creates its own ``admz`` account, and stores **that**.
The typed password goes to the fleet entry list or nowhere, per the operator's
explicit choice — never to this device's account row.

Most of this file is absences, because the interesting half of the contract is
what must NOT happen. Three properties carry the design:

  * the typed password is never the device credential — asserted against the
    registry AND against the raw database bytes (the NFR-CRED-001 pattern);
  * the device is authenticated BEFORE any write, strictly, so an unproven
    password can never reach ``pwdgrp.cgi:add-user``;
  * storing nothing for the device is the NORMAL outcome, not a 500 — the
    opposite of the account path, which is why they are separate handlers.

``tests/test_entry_promotion.py`` is the control: its ``_token()`` mints a
session with no kind, so it must keep exercising the account path verbatim.
"""

import json
import re
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

import admz.api as api_pkg
from admz import entry_credentials as ec
from admz.api.capture import KIND_ACCOUNT, KIND_ROOT_ADOPT

TEMPLATES = Path(api_pkg.__file__).parent / "templates"
SAME_ORIGIN = {"Origin": "http://testserver"}
TYPED = "operator-typed-root-pw"
FORM = {"username": "root", "password": TYPED, "entry_action": "discard"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from fastapi.testclient import TestClient

    import admz.api.main as main_module
    from admz.api.main import app
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry
    from admz.fleet_settings import fleet_settings

    fresh = SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"),
        key_path=str(tmp_path / "admz.key"),
    )
    monkeypatch.setattr(main_module, "registry", fresh)
    import admz.api.templating as templating
    monkeypatch.setattr(templating, "_registry", lambda: fresh)
    for key in (ec.SETTING_KEY, ec.LEGACY_PASS_KEY, ec.LEGACY_USER_KEY,
                ec.PROMPT_ALWAYS_KEY):
        fleet_settings.delete(key)
    fresh.add_device("cam-1", {"host": "10.0.0.1", "nickname": "Cam", "tags": []})

    with TestClient(app) as c:
        c.registry = fresh
        c.db_path = tmp_path / "admz.db"
        yield c


@pytest.fixture
def audit(monkeypatch):
    rows = []

    def _record(principal, action, *, resource="", details=None, success=True,
                error_message="", log=None):
        who = principal if isinstance(principal, str) or principal is None else getattr(
            principal, "username", type(principal).__name__)
        rows.append({"action": action, "resource": resource,
                     "details": dict(details or {}), "success": success,
                     "principal": who})

    monkeypatch.setattr("admz.api.routes.capture.record_event", _record)
    return rows


@pytest.fixture
def device(monkeypatch):
    """Scriptable stand-ins for the device half.

    Patched at the SOURCE modules, because `_submit_root_adopt` imports them
    inside its body — patching `admz.api.routes.capture.<name>` would bind
    nothing.
    """
    state = {
        "tcp": 4,                       # ms, or None for unreachable
        "confirm": (True, {}, None),    # (ok, facts, learned)
        "adopt": {"success": True, "status": "admz_account_created",
                  "username": "admz"},
        "adopt_calls": [],
        "confirm_calls": [],
    }

    async def _tcp(host, port, timeout):
        return state["tcp"]

    async def _confirm(**kw):
        state["confirm_calls"].append(kw["credentials"])
        return state["confirm"]

    async def _adopt(catalog, executors, registry, *, device_id, host, entry,
                     device_info=None):
        state["adopt_calls"].append(entry)
        out = dict(state["adopt"])
        if out.get("success"):
            # what the real function does: stores `admz`, never the entry
            from admz.provisioning import store_provisioned_creds
            store_provisioned_creds(
                registry, device_id, "admz", "generated-admz-pw",
                purpose="ADMZ's own account, created at adoption (ADR-0061)",
                generated_by_admz=True,
            )
        return out

    monkeypatch.setattr("admz.fleet.health._tcp_probe", _tcp)
    monkeypatch.setattr("admz.fleet.health._confirm_credentials", _confirm)
    monkeypatch.setattr("admz.provisioning.adopt_with_admz_account", _adopt)
    monkeypatch.setattr(
        "admz.api.context.get_context",
        lambda: SimpleNamespace(catalog=object(), executors={"vapix": object()}),
    )
    return state


def _token(kind=KIND_ROOT_ADOPT, propose=False):
    from admz.api.capture import capture_store

    return capture_store.create_session(
        device_id="cam-1", kind=kind, purpose="test", propose_promote=propose,
    ).token


# --- the invariant --------------------------------------------------------


class TestTheTypedPasswordIsNeverTheDeviceCredential:
    def test_admz_is_stored_and_the_typed_password_is_not(self, client, device):
        r = client.post(f"/capture/{_token()}", data=FORM, headers=SAME_ORIGIN)
        assert r.status_code == 200, r.text
        stored = client.registry.get_credentials("cam-1")
        assert stored["username"] == "admz"
        assert stored["password"] != TYPED

    def test_the_typed_password_is_not_in_the_database_file(self, client, device):
        """The NFR-CRED-001 pattern: assert against the raw bytes, not the API.

        A control first — the generated admz password IS recoverable as
        ciphertext-bearing rows exist — so the absence below is not vacuous.

        The WAL is read with the main file, as ``test_setting_encryption.py``
        does. A fresh write sits in ``-wal`` until a checkpoint, which runs when
        the last connection closes; under parallel CI another connection was
        still open, the main file held only its header, and the control failed
        (#516). A password in the WAL is on disk all the same.
        """
        client.post(f"/capture/{_token()}", data=FORM, headers=SAME_ORIGIN)
        raw = b"".join(
            path.read_bytes()
            for path in (Path(f"{client.db_path}{side}") for side in ("", "-wal", "-shm"))
            if path.exists())
        assert b"cam-1" in raw, "CONTROL: nothing was written at all"
        assert TYPED.encode() not in raw, (
            "the typed root password is recoverable from the database file")

    def test_no_page_audit_row_or_note_carries_either_password(
        self, client, device, audit
    ):
        r = client.post(f"/capture/{_token()}", data=FORM, headers=SAME_ORIGIN)
        assert TYPED not in r.text
        assert "generated-admz-pw" not in r.text
        blob = json.dumps(audit)
        assert TYPED not in blob and "generated-admz-pw" not in blob


# --- authenticate before writing -----------------------------------------


class TestTheDeviceIsProvenBeforeAnyWrite:
    def test_the_confirm_is_strict_and_precedes_the_adopt(self, client, device):
        client.post(f"/capture/{_token()}", data=FORM, headers=SAME_ORIGIN)
        assert device["confirm_calls"] == [{"username": "root", "password": TYPED}]
        assert device["adopt_calls"] == [{"username": "root", "password": TYPED}]

    def test_a_refused_password_never_reaches_the_adopt(self, client, device, audit):
        device["confirm"] = (False, {}, None)
        r = client.post(f"/capture/{_token()}", data=FORM, headers=SAME_ORIGIN)
        assert r.status_code == 200
        assert device["adopt_calls"] == [], "an unproven password reached add-user"
        assert "refused" in r.text.lower()
        assert audit[0]["action"] == "credential_prompt.auth_failed"
        assert audit[0]["success"] is False

    def test_an_unproven_answer_is_not_treated_as_proof(self, client, device):
        """`None` is "the device answered in a way that proves nothing" — a
        lenient read of that once stored a bad password (P3408)."""
        device["confirm"] = (None, {}, None)
        client.post(f"/capture/{_token()}", data=FORM, headers=SAME_ORIGIN)
        assert device["adopt_calls"] == []

    def test_an_unreachable_device_is_not_contacted_further(self, client, device):
        device["tcp"] = None
        r = client.post(f"/capture/{_token()}", data=FORM, headers=SAME_ORIGIN)
        assert r.status_code == 200
        assert device["confirm_calls"] == [] and device["adopt_calls"] == []


# --- the token: live for what did not touch the device -------------------


class TestTokenLifetime:
    def test_a_wrong_password_leaves_the_token_usable(self, client, device):
        token = _token()
        device["confirm"] = (False, {}, None)
        assert client.post(f"/capture/{token}", data=FORM,
                           headers=SAME_ORIGIN).status_code == 200
        # corrected password on the SAME token
        device["confirm"] = (True, {}, None)
        r = client.post(f"/capture/{token}", data=FORM, headers=SAME_ORIGIN)
        assert r.status_code == 200
        assert client.registry.get_credentials("cam-1")["username"] == "admz"

    def test_the_token_is_consumed_once_the_write_is_attempted(self, client, device):
        token = _token()
        client.post(f"/capture/{token}", data=FORM, headers=SAME_ORIGIN)
        again = client.post(f"/capture/{token}", data=FORM, headers=SAME_ORIGIN)
        assert again.status_code == 410


# --- storing nothing is normal here, not a 500 ---------------------------


class TestAFailedAdoptStoresNothingAndIsNotAnError:
    def test_adopt_failed_is_200_with_nothing_stored(self, client, device, audit):
        device["adopt"] = {"success": False, "error": "device said no"}
        r = client.post(f"/capture/{_token()}", data=FORM, headers=SAME_ORIGIN)
        assert r.status_code == 200, "storing nothing is not an error for this kind"
        assert 'data-outcome="adopt_failed"' in r.text
        assert "device said no" in r.text
        with pytest.raises(Exception):
            client.registry.get_credentials("cam-1")
        assert audit[-1]["success"] is False
        assert TYPED not in r.text

    def test_the_done_page_never_says_saved(self, client, device):
        for adopt in ({"success": True, "username": "admz"},
                      {"success": False, "error": "nope"}):
            device["adopt"] = adopt
            r = client.post(f"/capture/{_token()}", data=FORM, headers=SAME_ORIGIN)
            low = r.text.lower()
            assert "credentials saved" not in low
            assert "stored securely" not in low


# --- the two-way choice --------------------------------------------------


class TestTheOperatorsTwoChoices:
    def test_discard_promotes_nothing(self, client, device, audit):
        client.post(f"/capture/{_token()}",
                    data={**FORM, "entry_action": "discard"}, headers=SAME_ORIGIN)
        assert ec.list_entry_credentials() == []
        assert not any(r["action"].startswith("entry_credential.") for r in audit)

    def test_add_to_fleet_list_promotes_and_audits_without_the_password(
        self, client, device, audit
    ):
        client.post(f"/capture/{_token()}",
                    data={**FORM, "entry_action": "add_to_fleet_list"},
                    headers=SAME_ORIGIN)
        assert [(c.username, c.password) for c in ec.list_entry_credentials()] == [
            ("root", TYPED)]
        promo = [r for r in audit if r["action"] == "entry_credential.promoted"]
        assert promo and promo[0]["details"]["username"] == "root"
        assert TYPED not in json.dumps(audit)

    def test_promotion_is_gated_on_authentication_not_on_the_adopt(
        self, client, device
    ):
        """A refused password promotes nothing — promoting an unproven secret
        would spend two failed authentications against every future device. A
        PROVEN one whose admz write then failed DOES promote: it demonstrably
        works, the operator asked, and the entry list is the route to retry."""
        device["confirm"] = (False, {}, None)
        client.post(f"/capture/{_token()}",
                    data={**FORM, "entry_action": "add_to_fleet_list"},
                    headers=SAME_ORIGIN)
        assert ec.list_entry_credentials() == [], "an unproven password was promoted"

        device["confirm"] = (True, {}, None)
        device["adopt"] = {"success": False, "error": "nope"}
        client.post(f"/capture/{_token()}",
                    data={**FORM, "entry_action": "add_to_fleet_list"},
                    headers=SAME_ORIGIN)
        assert [c.username for c in ec.list_entry_credentials()] == ["root"]


# --- the form ------------------------------------------------------------


def _flat(html: str) -> str:
    """Collapse whitespace so a prose assertion survives a re-wrap.

    The template wraps its sentences across lines, so ``device's credential``
    renders with a newline inside it and a naive substring check fails on
    formatting rather than on meaning. Matching the *words* keeps these guards
    strict about the claim and indifferent to the line breaks — otherwise the
    next copy edit that reflows a paragraph breaks a test for no reason, which
    is how a guard earns a reputation for crying wolf and gets deleted.
    """
    return re.sub(r"\s+", " ", html)


class TestTheFormDoesNotMislead:
    def test_it_never_claims_the_typed_password_is_stored(self, client):
        page = _flat(client.get(f"/capture/{_token()}").text)
        assert "stored encrypted" not in page
        assert "not saved as this device's credential" in page
        # the positive half of the promise, too: the operator is told their own
        # password keeps working, which is the thing they will most worry about
        assert "never changes, disables or deletes it" in page

    def test_the_radios_have_no_default_and_are_required(self, client):
        page = client.get(f"/capture/{_token()}").text
        radios = re.findall(r"<input[^>]*name=\"entry_action\"[^>]*>", page)
        assert len(radios) == 2, radios
        for box in radios:
            assert "checked" not in box
            assert "required" in box

    def test_the_submit_button_names_the_write(self, client):
        """It IS the ADR-0059 approval (ADR-0068 §9), so the wording is
        load-bearing rather than cosmetic."""
        page = client.get(f"/capture/{_token()}").text
        assert "Log in and create ADMZ's own account" in page

    def test_no_account_row_is_shown(self, client):
        """`Account: default` beside a root-password field invites "I am setting
        the default account's password" — the opposite of what happens."""
        page = client.get(f"/capture/{_token()}").text
        assert ">Account<" not in page

    def test_the_account_form_is_untouched(self, client):
        """The control: an `account` session still gets the original form, with
        its original (true, for that kind) storage promise."""
        page = client.get(f"/capture/{_token(kind=KIND_ACCOUNT)}").text
        assert "stored encrypted" in page
        assert 'name="promote"' in page
        assert "entry_action" not in page


# --- fail closed ---------------------------------------------------------


class TestAnUnknownKindFailsClosed:
    def test_a_row_with_an_unknown_kind_is_refused_not_stored(self, client, device):
        token = _token()
        conn = sqlite3.connect(client.db_path)
        conn.execute("UPDATE capture_sessions SET kind='from_the_future' "
                     "WHERE token=?", (token,))
        conn.commit()
        conn.close()

        assert client.get(f"/capture/{token}").status_code == 410
        assert client.post(f"/capture/{token}", data=FORM,
                           headers=SAME_ORIGIN).status_code == 410
        with pytest.raises(Exception):
            client.registry.get_credentials("cam-1")


# --- the surfaces that used to assert storage ---------------------------


class TestTheStatusSurfacesTellTheTruth:
    def test_the_rest_status_carries_kind_and_outcome(self, client, device):
        token = _token()
        client.post(f"/capture/{token}", data=FORM, headers=SAME_ORIGIN)
        body = client.get(f"/api/capture/{token}/status").json()
        assert body["kind"] == KIND_ROOT_ADOPT
        assert body["outcome"] == "adopted"

    def test_a_revisited_spent_token_does_not_claim_the_password_was_saved(
        self, client, device
    ):
        token = _token()
        client.post(f"/capture/{token}", data=FORM, headers=SAME_ORIGIN)
        page = client.get(f"/capture/{token}").text
        assert "Credentials Saved" not in page
        assert "stored securely" not in page
        assert "ADMZ now has its own account" in page


# --- the chat note ------------------------------------------------------


class TestTheChatNote:
    def test_only_a_terminal_outcome_writes_a_note(self, client, device, monkeypatch):
        """`pop_action_link` is fetch-and-delete and there is one note per
        session, so a note on a mistyped password would consume the link and the
        REAL outcome would produce none — and under ADR-0066 that note is what
        fires the model's continuation turn."""
        notes = []
        monkeypatch.setattr(
            "admz.chatbot.sessions.chat_sessions.pop_action_link",
            lambda token: {"principal": "p", "conversation_id": "c"})
        monkeypatch.setattr(
            "admz.chatbot.sessions.chat_sessions.append_event",
            lambda principal, conversation_id, text: notes.append(text))

        token = _token()
        device["confirm"] = (False, {}, None)
        client.post(f"/capture/{token}", data=FORM, headers=SAME_ORIGIN)
        assert notes == [], "a non-terminal failure consumed the chat link"

        device["confirm"] = (True, {}, None)
        client.post(f"/capture/{token}", data=FORM, headers=SAME_ORIGIN)
        assert len(notes) == 1
        assert "NOT stored" in notes[0]
        assert TYPED not in notes[0]
