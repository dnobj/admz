"""Per-key settings write handlers refuse anonymous and leave a trail (GH #351).

`POST /settings/chat` and `POST /settings/survey` bound a principal and never
checked it, while writing keys that ``is_protected_setting`` returns True for
— including two live credentials, ``gemini_api_key`` and ``survey_github_pat``,
both stored encrypted at rest precisely because they are credentials. Neither
handler wrote an audit row, so a replaced Gemini key or a repointed survey
repository left no record of who did it.

This was #164 item 2. #329 fixed items 1 and 4 (the *capability* writes on
these same routes now go through ``capabilities.set_enabled``) and closed the
issue; the setting half was never done, and the setting half is where the
secrets are.

Why the survey route is the sharper half: ``action=run_now`` passes
``respect_enabled=False``, so it surveys the fleet and can open a GitHub PR
against whatever ``survey_repo`` currently says — bypassing the contributor
toggle. Setting the PAT, pointing the repo and triggering the run were three
ungated, unaudited steps in one handler.

This file pins, for both routes:
  - an anonymous principal is refused (403) and nothing is written
  - an authenticated principal succeeds and the write is attributed
  - the audit row never carries the secret VALUE — attribution, not a second
    copy of the credential in a second store
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from admz.auth import AuthBackend, NoAuth, Principal, set_active_backend


GEMINI_KEY = "AIza-test-key-351-do-not-log"
SURVEY_PAT = "ghp_survey_pat_351_do_not_log"


class StubBackend(AuthBackend):
    def __init__(self, principal: Principal):
        self.principal = principal

    async def authenticate(self, request):
        return self.principal


def _anon() -> Principal:
    return Principal(name="anonymous", display_name="anonymous",
                     source="none", is_anonymous=True)


def _windows(name: str, groups=None) -> Principal:
    return Principal(name=f"AXIS\\{name}", display_name=name, domain="AXIS",
                     groups=list(groups or []), source="windows")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    from admz import fleet_settings as fs_module
    from admz.api.routes import devices as devices_route
    from admz.api.routes import survey as survey_route
    from admz.api.routes import web as web_route

    fresh_fs = fs_module.FleetSettings(str(tmp_path / "admz.db"))
    # All module-level references move together — a partial repoint leaves one
    # route reading a different store than another writes to, which shows up
    # only when test files share a session (learned the hard way in #350).
    originals = [
        (fs_module, "fleet_settings", fs_module.fleet_settings),
        (devices_route, "fleet_settings", devices_route.fleet_settings),
        (web_route, "fleet_settings", web_route.fleet_settings),
        (survey_route, "fleet_settings", survey_route.fleet_settings),
    ]
    for mod, attr, _ in originals:
        setattr(mod, attr, fresh_fs)

    backend = StubBackend(_anon())
    set_active_backend(backend)

    from admz.api.main import app
    app.state._stub_backend = backend
    try:
        with TestClient(app, follow_redirects=False) as c:
            yield c
    finally:
        for mod, attr, val in originals:
            setattr(mod, attr, val)
        set_active_backend(NoAuth())


def _set_principal(client, principal: Principal) -> None:
    from admz.api.main import app
    app.state._stub_backend.principal = principal


def _audit_rows(action: str):
    from admz.audit import AuditLog
    return AuditLog().list_recent(action=action, limit=20)


# ---------------------------------------------------------------------------
# POST /settings/chat
# ---------------------------------------------------------------------------


class TestChatSettingsWriteGate:
    def test_anonymous_refused_and_nothing_written(self, client):
        from admz.fleet_settings import fleet_settings

        r = client.post("/settings/chat",
                        data={"action": "set_api_key", "api_key": GEMINI_KEY})
        assert r.status_code == 403
        assert fleet_settings.get("gemini_api_key") is None

    def test_anonymous_cannot_clear_the_key_either(self, client):
        """Clearing is the denial-of-service half: it takes the console down
        without needing to know any secret."""
        from admz.chatbot.config import set_api_key
        set_api_key(GEMINI_KEY)

        r = client.post("/settings/chat", data={"action": "clear_api_key"})
        assert r.status_code == 403

        from admz.chatbot.config import get_chatbot_config
        assert get_chatbot_config().api_key == GEMINI_KEY

    def test_authenticated_write_succeeds(self, client):
        _set_principal(client, _windows("alice", ["Administrators"]))
        r = client.post("/settings/chat",
                        data={"action": "set_api_key", "api_key": GEMINI_KEY})
        assert r.status_code == 200

        from admz.chatbot.config import get_chatbot_config
        assert get_chatbot_config().api_key == GEMINI_KEY

    def test_write_is_attributed(self, client):
        _set_principal(client, _windows("alice", ["Administrators"]))
        client.post("/settings/chat",
                    data={"action": "set_api_key", "api_key": GEMINI_KEY})

        rows = _audit_rows("fleet_setting.write")
        assert rows, "the Gemini API key write left no audit row"
        assert any("gemini_api_key" in (row.resource or "") for row in rows)

    def test_audit_row_does_not_contain_the_secret(self, client):
        """Attribution, not a second copy of the credential. The key is
        encrypted at rest in fleet_settings; an audit store that recorded the
        plaintext would undo that one table over."""
        _set_principal(client, _windows("alice", ["Administrators"]))
        client.post("/settings/chat",
                    data={"action": "set_api_key", "api_key": GEMINI_KEY})

        for row in _audit_rows("fleet_setting.write"):
            assert GEMINI_KEY not in repr(row)

    def test_a_non_secret_branch_is_audited_too(self, client):
        _set_principal(client, _windows("alice", ["Administrators"]))
        from admz.chatbot.config import SELECTABLE_MODELS
        client.post("/settings/chat",
                    data={"action": "set_default_model",
                          "default_model": sorted(SELECTABLE_MODELS)[0]})

        rows = _audit_rows("fleet_setting.write")
        assert any("gemini_default_model" in (row.resource or "") for row in rows)


# ---------------------------------------------------------------------------
# POST /settings/survey
# ---------------------------------------------------------------------------


class TestSurveySettingsWriteGate:
    def test_anonymous_refused_on_pat(self, client):
        from admz.survey import secrets

        r = client.post("/settings/survey",
                        data={"action": "set_pat", "github_pat": SURVEY_PAT})
        assert r.status_code == 403
        assert not secrets.has_pat()

    def test_anonymous_refused_on_save_config(self, client):
        from admz.fleet_settings import fleet_settings
        from admz.survey import secrets

        r = client.post("/settings/survey",
                        data={"action": "save_config", "repo": "attacker/repo"})
        assert r.status_code == 403
        assert fleet_settings.get(secrets.KEY_REPO) is None

    def test_anonymous_refused_on_run_now(self, client):
        """`run_now` passes respect_enabled=False, so the contributor toggle is
        not a second brake — this handler is the only gate on a fleet survey
        that can open a GitHub PR."""
        r = client.post("/settings/survey", data={"action": "run_now"})
        assert r.status_code == 403

    def test_the_403_is_not_swallowed_into_a_rendered_error(self, client):
        """The handler wraps its actions in `except Exception` to keep the page
        from 500ing. The gate is deliberately OUTSIDE that block: swallowed
        into it, a refused write would render a friendly 200 page and look
        like a UI hiccup rather than a refusal."""
        r = client.post("/settings/survey", data={"action": "set_pat",
                                                  "github_pat": SURVEY_PAT})
        assert r.status_code == 403
        assert "Survey" not in r.text or "403" in r.text

    def test_authenticated_pat_write_succeeds_and_is_attributed(self, client):
        from admz.survey import secrets

        _set_principal(client, _windows("alice", ["Administrators"]))
        r = client.post("/settings/survey",
                        data={"action": "set_pat", "github_pat": SURVEY_PAT})
        assert r.status_code == 200
        assert secrets.has_pat()

        rows = _audit_rows("fleet_setting.write")
        assert any(secrets.KEY_PAT in (row.resource or "") for row in rows)

    def test_pat_audit_row_does_not_contain_the_pat(self, client):
        _set_principal(client, _windows("alice", ["Administrators"]))
        client.post("/settings/survey",
                    data={"action": "set_pat", "github_pat": SURVEY_PAT})

        for row in _audit_rows("fleet_setting.write"):
            assert SURVEY_PAT not in repr(row)

    def test_partial_application_is_named_in_the_failure_row(self, client, monkeypatch):
        """Each write in save_config commits on its own, so a failure partway
        through leaves real changes. A bare "action failed" row would read as
        "nothing happened" — the wrong thing to believe about a repointed
        survey repo."""
        from admz.api.routes import survey as survey_route

        def _boom(ctx, **kwargs):
            raise RuntimeError("scheduler unavailable")

        monkeypatch.setattr(survey_route, "_sync_survey_schedule", _boom)

        _set_principal(client, _windows("alice", ["Administrators"]))
        r = client.post("/settings/survey",
                        data={"action": "save_config", "repo": "someone/elsewhere"})
        assert r.status_code == 200  # the page renders the error, by design

        from admz.fleet_settings import fleet_settings
        from admz.survey import secrets
        assert fleet_settings.get(secrets.KEY_REPO) == "someone/elsewhere"

        rows = _audit_rows("survey.action")
        assert rows, "a failed save_config left no row at all"
        row = rows[0]
        assert row.success is False
        assert (row.details or {}).get("partial") is True
        assert secrets.KEY_REPO in (row.details or {}).get("applied", [])

    def test_repo_target_is_recorded(self, client):
        """Pointing the survey at a different repository is the step that turns
        a contribution into an exfiltration, and it was the write with no
        trace at all."""
        _set_principal(client, _windows("alice", ["Administrators"]))
        client.post("/settings/survey",
                    data={"action": "save_config", "repo": "someone/elsewhere"})

        rows = _audit_rows("fleet_setting.write")
        assert any((row.details or {}).get("repo") == "someone/elsewhere"
                   for row in rows), "the repo target was not recorded"


# ---------------------------------------------------------------------------
# POST /api/acs/config — the neighbour the first draft missed
# ---------------------------------------------------------------------------


class TestAcsConfigWriteGate:
    """`save_acs_config` writes the `acs_pro` fleet key, which
    ``is_protected_setting`` returns True for. It sat ungated while the two
    routes #351 named were being fixed — found by the review of this PR's
    first draft, which is the same protection-on-one-path-not-its-neighbour
    shape as #158/#350, caught before merge this time.
    """

    def test_anonymous_refused_and_nothing_written(self, client):
        from admz.modules.acs_pro.config import FLEET_KEY
        from admz.fleet_settings import fleet_settings

        r = client.post("/api/acs/config",
                        json={"enabled": True, "server_url": "https://attacker:29204",
                              "verify_tls": False})
        assert r.status_code == 403
        assert fleet_settings.get(FLEET_KEY) is None

    def test_authenticated_write_succeeds_and_is_audited(self, client):
        _set_principal(client, _windows("alice", ["Administrators"]))
        r = client.post("/api/acs/config",
                        json={"enabled": True, "server_url": "https://acs.local",
                              "port": 29204, "verify_tls": True})
        assert r.status_code == 200

        rows = _audit_rows("fleet_setting.write")
        assert any(row.resource == "acs_pro" for row in rows)
        row = next(r_ for r_ in rows if r_.resource == "acs_pro")
        assert (row.details or {}).get("server_url") == "https://acs.local"

    def test_the_key_really_is_protected(self):
        """If this ever goes False the gate above is arguing for itself."""
        from admz.fleet_settings import is_protected_setting
        from admz.modules.acs_pro.config import FLEET_KEY
        assert is_protected_setting(FLEET_KEY) is True
