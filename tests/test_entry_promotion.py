"""FR-CRED-012 / ADR-0064 slice D — captured credentials may be promoted to
the entry list, by the human, from the form, audited, never lossy.

A promotion is a *scope* promotion: the secret becomes something ADMZ will
offer to every device it onboards. So the box is opt-in per submission and
never pre-checked; an MCP caller may only propose; the audit row carries the
username and device ids and never the password; and a refusal (the cap, the
prompt-always posture) leaves the capture that just succeeded exactly as it
was. The Fleet Settings page gains the first operator view of the list.
"""

import json
import re
from pathlib import Path

import pytest

import admz.api as api_pkg
from admz import entry_credentials as ec

TEMPLATES = Path(api_pkg.__file__).parent / "templates"
SAME_ORIGIN = {"Origin": "http://testserver"}
FORM = {"username": "root", "password": "s3cret-pw"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from fastapi.testclient import TestClient
    from admz.api.main import app
    import admz.api.main as main_module
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry
    from admz.fleet_settings import fleet_settings

    fresh = SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"),
        key_path=str(tmp_path / "admz.key"),
    )
    monkeypatch.setattr(main_module, "registry", fresh)
    import admz.api.templating as templating
    monkeypatch.setattr(templating, "_registry", lambda: fresh)
    for key in (ec.SETTING_KEY, ec.LEGACY_PASS_KEY, ec.LEGACY_USER_KEY, ec.PROMPT_ALWAYS_KEY):
        fleet_settings.delete(key)
    fresh.add_device("cam-1", {"host": "10.0.0.1", "nickname": "Cam", "tags": []})

    with TestClient(app) as c:
        c.registry = fresh
        yield c


@pytest.fixture
def audit(monkeypatch):
    """Capture every audit row the capture route records."""
    rows = []

    def _record(principal, action, *, resource="", details=None, success=True, error_message="", log=None):
        # the principal is recorded as text: a string passed directly, else
        # the request principal's name (never the object, so json.dumps works)
        who = principal if isinstance(principal, str) or principal is None else getattr(
            principal, "username", type(principal).__name__)
        rows.append({"action": action, "resource": resource, "details": dict(details or {}),
                     "success": success, "principal": who})

    monkeypatch.setattr("admz.api.routes.capture.record_event", _record)
    return rows


def _token(propose=False):
    from admz.api.capture import capture_store

    return capture_store.create_session(
        device_id="cam-1", account_id="default", account_type="admin",
        purpose="test", propose_promote=propose,
    ).token


class TestPromotionFromTheForm:
    def test_the_box_promotes_and_is_audited_without_the_password(self, client, audit):
        r = client.post(f"/capture/{_token()}", data={**FORM, "promote": "on"}, headers=SAME_ORIGIN)
        assert r.status_code == 200, r.text
        assert 'data-promotion="promoted"' in r.text
        assert [(c.username, c.password) for c in ec.list_entry_credentials()] == [("root", "s3cret-pw")]
        # the device credential was saved too — promotion comes after it
        assert client.registry.get_credentials("cam-1")["password"] == "s3cret-pw"
        assert [row["action"] for row in audit] == ["entry_credential.promoted"]
        assert audit[0]["details"]["username"] == "root"
        assert audit[0]["details"]["device_ids"] == ["cam-1"]
        assert audit[0]["details"]["label"] == "promoted from cam-1"
        assert "s3cret-pw" not in json.dumps(audit)

    def test_without_the_box_nothing_is_promoted(self, client, audit):
        r = client.post(f"/capture/{_token()}", data=FORM, headers=SAME_ORIGIN)
        assert r.status_code == 200
        assert ec.list_entry_credentials() == []
        assert audit == []
        assert "data-promotion" not in r.text

    def test_a_proposal_is_not_consent(self, client, audit):
        """The #411 acceptance criterion: a session minted with the proposal
        and a form submitted WITHOUT the box promotes nothing — the flag
        reaching the store requires the human's submission."""
        r = client.post(f"/capture/{_token(propose=True)}", data=FORM, headers=SAME_ORIGIN)
        assert r.status_code == 200
        assert ec.list_entry_credentials() == []
        assert audit == []

    def test_the_form_shows_the_hint_only_when_proposed_and_never_pre_checks(self, client):
        plain = client.get(f"/capture/{_token()}").text
        proposed = client.get(f"/capture/{_token(propose=True)}").text
        assert 'name="promote"' in plain and 'name="promote"' in proposed
        assert "suggested promoting" not in plain
        assert "suggested promoting" in proposed
        for page in (plain, proposed):
            box = re.search(r"<input[^>]*name=\"promote\"[^>]*>", page).group(0)
            assert "checked" not in box

    def test_a_cap_refusal_keeps_the_capture_and_is_audited(self, client, audit):
        from admz.fleet_settings import fleet_settings

        fleet_settings.set(ec.SETTING_KEY, json.dumps(
            [{"username": f"u{i}", "password": f"p{i}"} for i in range(ec.MAX_STORED)]))
        r = client.post(f"/capture/{_token()}", data={**FORM, "promote": "on"}, headers=SAME_ORIGIN)
        assert r.status_code == 200, r.text
        assert 'data-promotion="refused"' in r.text
        assert client.registry.get_credentials("cam-1")["password"] == "s3cret-pw", "the capture stands"
        assert len(ec.list_entry_credentials()) == ec.MAX_STORED
        assert [row["action"] for row in audit] == ["entry_credential.promotion_refused"]
        assert audit[0]["success"] is False
        assert "at most" in r.text, "the cap's own reason reaches the done page"
        assert "s3cret-pw" not in json.dumps(audit)

    def test_the_prompt_always_posture_refuses_too(self, client, audit):
        from admz.fleet_settings import fleet_settings

        fleet_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
        r = client.post(f"/capture/{_token()}", data={**FORM, "promote": "on"}, headers=SAME_ORIGIN)
        assert r.status_code == 200
        assert 'data-promotion="refused"' in r.text
        assert [row["action"] for row in audit] == ["entry_credential.promotion_refused"]

    def test_a_duplicate_is_reported_not_re_added(self, client, audit):
        ec.add_entry_credential("root", "s3cret-pw", "already")
        r = client.post(f"/capture/{_token()}", data={**FORM, "promote": "on"}, headers=SAME_ORIGIN)
        assert r.status_code == 200
        assert 'data-promotion="duplicate"' in r.text
        assert len(ec.list_entry_credentials()) == 1
        assert audit == []


class TestTheProposalTravels:
    def test_the_session_persists_the_proposal(self, client):
        from admz.api.capture import capture_store

        assert capture_store.get_session(_token(propose=True)).propose_promote is True
        assert capture_store.get_session(_token()).propose_promote is False

    @pytest.mark.asyncio
    async def test_the_mcp_tool_may_propose_and_defaults_to_not(self, client):
        from types import SimpleNamespace

        from admz.api.capture import capture_store
        from admz.mcp.server import ADMZMCPServer

        srv = SimpleNamespace(registry=client.registry)
        out = await ADMZMCPServer._capture_credentials(srv, {"device_id": "cam-1", "propose_promote": True})
        assert out["propose_promote"] is True
        assert capture_store.get_session(out["token"]).propose_promote is True
        out2 = await ADMZMCPServer._capture_credentials(srv, {"device_id": "cam-1"})
        assert out2["propose_promote"] is False
        assert capture_store.get_session(out2["token"]).propose_promote is False
        # an LLM client may send string booleans: "false" is not a proposal
        out3 = await ADMZMCPServer._capture_credentials(
            srv, {"device_id": "cam-1", "propose_promote": "false"})
        assert out3["propose_promote"] is False
        out4 = await ADMZMCPServer._capture_credentials(
            srv, {"device_id": "cam-1", "propose_promote": "true"})
        assert out4["propose_promote"] is True


class TestTheOperatorCanSeeTheList:
    def test_fleet_settings_renders_the_list_redacted(self, client):
        from admz.fleet_settings import fleet_settings

        fleet_settings.set(ec.LEGACY_PASS_KEY, "legacy-pw")
        fleet_settings.set(ec.LEGACY_USER_KEY, "operator")
        ec.add_entry_credential("batch-a", "batch-pw", "batch A")
        page = client.get("/fleet-settings")
        assert page.status_code == 200
        # within the entry-list section: the generic settings table also
        # renders `default_username`, so the page as a whole proves nothing
        section = page.text.split('id="entry-credentials"')[1].split("</table>")[0]
        assert "operator" in section and "batch-a" in section and "batch A" in section
        assert section.count('data-entry="tried"') == 2
        assert "legacy-pw" not in page.text and "batch-pw" not in page.text
        assert f"2 of {ec.MAX_STORED}" in page.text

    def test_fleet_settings_says_when_the_posture_is_on(self, client):
        from admz.fleet_settings import fleet_settings

        fleet_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
        page = client.get("/fleet-settings")
        assert "Prompt-always posture is on" in page.text


class TestPromotionNeverBreaksTheCapture:
    def test_an_internal_failure_is_a_refusal_not_a_500(self, client, audit, monkeypatch):
        """The capture has already succeeded and consumed its token when the
        promotion runs, so a store-side failure is logged and reported as a
        refusal — the operator still gets the done page, and the fixed reason
        text carries nothing from the exception."""
        def boom(*args, **kwargs):
            raise RuntimeError("store exploded while holding s3cret-pw")

        monkeypatch.setattr("admz.api.routes.capture.entry_credentials.add_entry_credential", boom)
        token = _token()
        r = client.post(f"/capture/{token}", data={**FORM, "promote": "on"}, headers=SAME_ORIGIN)
        assert r.status_code == 200
        assert 'data-promotion="refused"' in r.text
        assert client.registry.get_credentials("cam-1")["password"] == "s3cret-pw"
        assert [row["action"] for row in audit] == ["entry_credential.promotion_refused"]
        assert audit[0]["success"] is False
        assert "store exploded" not in r.text and "store exploded" not in json.dumps(audit)
        assert "s3cret-pw" not in json.dumps(audit)
        # the token was consumed by the capture that succeeded
        assert client.post(f"/capture/{token}", data=FORM, headers=SAME_ORIGIN).status_code == 410

    def test_nothing_is_promoted_when_the_device_save_fails(self, client, audit, monkeypatch):
        """Ordering, pinned: no device credential stored → no promotion and no
        audit row; the form's storage error is the only thing that happens."""
        from admz.exceptions import BackendError

        def boom(*args, **kwargs):
            raise BackendError("disk full")

        monkeypatch.setattr(type(client.registry), "add_account", boom)
        monkeypatch.setattr(type(client.registry), "update_account", boom)
        r = client.post(f"/capture/{_token()}", data={**FORM, "promote": "on"}, headers=SAME_ORIGIN)
        assert r.status_code == 500
        assert ec.list_entry_credentials() == []
        assert audit == []

    def test_off_and_false_are_not_consent(self, client, audit):
        for value in ("off", "false", "0"):
            r = client.post(f"/capture/{_token()}", data={**FORM, "promote": value}, headers=SAME_ORIGIN)
            assert r.status_code == 200, value
            assert "data-promotion" not in r.text, value
        assert ec.list_entry_credentials() == []
        assert audit == []

    def test_the_audit_row_names_the_principal_and_the_batch(self, client, audit):
        from admz.api.routes.capture import _promote_if_asked

        out = _promote_if_asked(True, "root", "batch-pw", ["cam-1", "cam-2"], principal="alice")
        assert out["result"] == "promoted"
        assert audit[0]["principal"] == "alice"
        assert audit[0]["details"]["label"] == "promoted from cam-1 (+1)"
        assert [c.label for c in ec.list_entry_credentials()] == ["promoted from cam-1 (+1)"]

    def test_the_chat_note_says_what_happened_to_the_promotion(self, monkeypatch):
        from admz.api.routes.capture import _note_capture_to_chat

        notes = []
        monkeypatch.setattr("admz.chatbot.sessions.chat_sessions.pop_action_link",
                            lambda token: {"principal": "p", "conversation_id": "c"})
        monkeypatch.setattr("admz.chatbot.sessions.chat_sessions.append_event",
                            lambda principal, conversation_id, text: notes.append(text))
        _note_capture_to_chat("tok", ["cam-1"], {"result": "promoted", "username": "root", "reason": ""})
        _note_capture_to_chat("tok", ["cam-1"], {"result": "refused", "username": "root",
                                                 "reason": "at most 3 entry credentials"})
        _note_capture_to_chat("tok", ["cam-1"], None)
        assert "entry list" in notes[0] and "refused" in notes[1] and "entry list" not in notes[2]
        assert all("root" not in n and "s3cret" not in n for n in notes), "device ids only"


class TestTheSessionColumnMigrates:
    def test_a_store_created_before_the_column_migrates_and_reads_old_rows_as_not_proposed(self, tmp_path):
        import sqlite3
        import time

        from admz.api.capture import CaptureStore

        path = tmp_path / "old.db"
        conn = sqlite3.connect(path)
        conn.executescript(
            "CREATE TABLE capture_sessions (token TEXT PRIMARY KEY, device_id TEXT NOT NULL,"
            " account_id TEXT NOT NULL, account_type TEXT NOT NULL DEFAULT 'service',"
            " purpose TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,"
            " ttl REAL NOT NULL DEFAULT 600.0, status TEXT NOT NULL DEFAULT 'pending');"
            "CREATE TABLE capture_session_devices (token TEXT NOT NULL, device_id TEXT NOT NULL,"
            " PRIMARY KEY (token, device_id));"
        )
        conn.execute("INSERT INTO capture_sessions VALUES (?,?,?,?,?,?,?,?)",
                     ("tok-old", "cam-1", "default", "admin", "p", time.time(), 600.0, "pending"))
        conn.commit()
        conn.close()

        store = CaptureStore(db_path=str(path))
        old = store.get_session("tok-old")
        assert old is not None and old.propose_promote is False
        new = store.create_session(device_id="cam-1", account_id="default", account_type="admin",
                                   purpose="p", propose_promote=True)
        assert store.get_session(new.token).propose_promote is True
        cols = {r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(capture_sessions)")}
        assert "propose_promote" in cols

    def test_a_fresh_store_declares_the_column_without_the_migration(self, tmp_path):
        """A fresh file must not depend on the ALTER succeeding."""
        import sqlite3

        from admz.api import capture as capture_mod

        store = capture_mod.CaptureStore(db_path=str(tmp_path / "fresh.db"))
        store.create_session(device_id="cam-1", account_id="default", account_type="admin", purpose="p")
        cols = {r[1] for r in sqlite3.connect(tmp_path / "fresh.db").execute(
            "PRAGMA table_info(capture_sessions)")}
        assert "propose_promote" in cols
        assert "propose_promote" in capture_mod._CAPTURE_SCHEMA


class TestTheOperatorSeesWhatIsTried:
    def test_fleet_settings_distinguishes_tried_from_stored_never_tried(self, client):
        from admz.fleet_settings import fleet_settings

        fleet_settings.set(ec.SETTING_KEY, json.dumps(
            [{"username": f"u{i}", "password": f"zz-secret-{i}", "label": f"batch {i}"} for i in range(5)]))
        page = client.get("/fleet-settings").text
        assert page.count('data-entry="tried"') == ec.MAX_ATTEMPTS_PER_PASS
        assert page.count('data-entry="never-tried"') == 5 - ec.MAX_ATTEMPTS_PER_PASS
        assert f"(at most {ec.MAX_ATTEMPTS_PER_PASS})" in page
        assert "zz-secret" not in page

    def test_fleet_settings_shows_the_posture_leaving_everything_untried(self, client):
        from admz.fleet_settings import fleet_settings

        ec.add_entry_credential("batch-a", "batch-pw", "batch A")
        fleet_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
        page = client.get("/fleet-settings").text
        assert "Prompt-always posture is on" in page
        assert page.count('data-entry="never-tried"') == 1 and 'data-entry="tried"' not in page

    def test_fleet_settings_survives_the_list_being_unreadable(self, client, monkeypatch):
        def boom():
            raise RuntimeError("fernet said no")

        monkeypatch.setattr("admz.entry_credentials.describe", boom)
        page = client.get("/fleet-settings")
        assert page.status_code == 200
        assert "Entry list unavailable" in page.text and "fernet said no" not in page.text
