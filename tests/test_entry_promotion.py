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
        rows.append({"action": action, "resource": resource, "details": dict(details or {}),
                     "success": success})

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


class TestTheOperatorCanSeeTheList:
    def test_fleet_settings_renders_the_list_redacted(self, client):
        from admz.fleet_settings import fleet_settings

        fleet_settings.set(ec.LEGACY_PASS_KEY, "legacy-pw")
        fleet_settings.set(ec.LEGACY_USER_KEY, "operator")
        ec.add_entry_credential("batch-a", "batch-pw", "batch A")
        page = client.get("/fleet-settings")
        assert page.status_code == 200
        assert "Entry credentials" in page.text
        assert "operator" in page.text and "batch-a" in page.text and "batch A" in page.text
        assert "legacy-pw" not in page.text and "batch-pw" not in page.text
        assert f"2 of {ec.MAX_STORED}" in page.text

    def test_fleet_settings_says_when_the_posture_is_on(self, client):
        from admz.fleet_settings import fleet_settings

        fleet_settings.set(ec.PROMPT_ALWAYS_KEY, "true")
        page = client.get("/fleet-settings")
        assert "Prompt-always posture is on" in page.text
