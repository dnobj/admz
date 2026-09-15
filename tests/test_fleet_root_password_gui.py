"""The break-glass root password can be set from the Fleet Settings page.

FR-CRED-014 / ADR-0068. Until this route existed the only way to set
``fleet_root_password`` was ``python -m admz settings set``, which takes the
value as a command-line argument — so it lands in PowerShell's history file and
in the process list. A form typed by a human in the browser has neither.

The route is a per-key web write handler following ``POST /confirm-settings``,
and this file pins the four places it deliberately departs from that
precedent, because each is a place a later "make it consistent" edit would
quietly weaken it:

  * the gate is REVEAL-group membership, not merely an authenticated caller —
    whoever sets the value knows it, so setting must need at least the
    permission revealing needs, or it is a back door to reveal;
  * same-origin is checked before any side effect;
  * an empty submission is refused, never read as "remove" — clearing the value
    turns off provisioning for the whole fleet;
  * refused attempts are audited.

Plus the invariants every secret-writing handler here carries: the value is
never echoed, never in an audit row, and stored encrypted at rest.

The ``client`` fixture repoints every module-level ``fleet_settings`` reference
at once, copied from ``test_settings_write_authz.py``: a partial repoint leaves
one route reading a different store than another writes to, which surfaces only
when test files share a session (#350).
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from admz.auth import AuthBackend, NoAuth, Principal, set_active_backend

KEY = "fleet_root_password"
SECRET = "BreakGlass-Root-gui-7f3a"
SAME_ORIGIN = {"Origin": "http://testserver"}
FORM = {"root_password": SECRET, "confirm_root_password": SECRET}


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
    monkeypatch.delenv("ADMZ_REVEAL_GROUPS", raising=False)

    from admz import fleet_settings as fs_module
    from admz.api.routes import devices as devices_route
    from admz.api.routes import survey as survey_route
    from admz.api.routes import web as web_route

    fresh_fs = fs_module.FleetSettings(str(tmp_path / "admz.db"))
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
            c.fs = fresh_fs
            c.db_path = tmp_path / "admz.db"
            yield c
    finally:
        for mod, attr, val in originals:
            setattr(mod, attr, val)
        set_active_backend(NoAuth())


def _as(principal: Principal) -> None:
    from admz.api.main import app
    app.state._stub_backend.principal = principal


def _admin():
    """In the default reveal group."""
    return _windows("alice", ["Administrators"])


def _rows():
    from admz.audit import AuditLog
    return [r for r in AuditLog().list_recent(action="fleet_setting.write", limit=50)
            if (r.resource or "") == KEY]


def _post(client, data=FORM, headers=SAME_ORIGIN):
    return client.post("/fleet-settings/root-password", data=data, headers=headers)


# --- who may set it -------------------------------------------------------


class TestTheGate:
    def test_anonymous_is_refused_and_nothing_is_written(self, client):
        r = _post(client)
        assert r.status_code == 403
        assert client.fs.get(KEY) is None

    def test_authenticated_but_not_in_a_reveal_group_is_refused(self, client):
        """THE case this route exists to get right. Merely authenticated is the
        bar `/confirm-settings` uses — and here it would let someone who may not
        REVEAL the break-glass password set it, and so know it."""
        _as(_windows("bob", groups=[]))
        r = _post(client)
        assert r.status_code == 403
        assert client.fs.get(KEY) is None

    def test_a_reveal_group_member_may_set_it(self, client):
        _as(_admin())
        r = _post(client)
        assert r.status_code == 200, r.text
        assert client.fs.get(KEY) == SECRET

    def test_the_403_is_not_swallowed_into_a_rendered_page(self, client):
        """A refusal that rendered a friendly 200 page would look like a UI
        hiccup rather than a refusal."""
        _as(_windows("bob", groups=[]))
        r = _post(client)
        assert r.status_code == 403
        assert "Break-glass root password" not in r.text

    def test_a_refused_attempt_is_audited_without_the_value(self, client):
        _as(_windows("bob", groups=[]))
        _post(client)
        rows = _rows()
        assert rows, "a refused attempt to set the break-glass password left no row"
        assert rows[0].success is False
        assert "reveal-denied" in (rows[0].error_message or "")
        assert SECRET not in repr(rows)


class TestCrossOrigin:
    def test_a_cross_site_post_is_refused_before_any_side_effect(self, client):
        """Checked first — so a forged request cannot even write a refusal row."""
        _as(_admin())
        r = _post(client, headers={"Origin": "http://evil.example"})
        assert r.status_code == 403
        assert client.fs.get(KEY) is None
        assert _rows() == [], "a cross-site request reached the audit log"


# --- what it accepts ------------------------------------------------------


class TestValidation:
    def test_an_empty_submission_is_refused_not_treated_as_clear(self, client):
        """`/confirm-settings` removes its password on an empty submit. Doing the
        same here would silently turn off provisioning fleet-wide."""
        _as(_admin())
        _post(client)                                   # set a real value first
        r = _post(client, data={"root_password": "", "confirm_root_password": ""})
        assert r.status_code == 200
        assert 'data-flash="error"' in r.text
        assert client.fs.get(KEY) == SECRET, "an empty submit cleared the value"

    def test_mismatched_passwords_are_refused(self, client):
        _as(_admin())
        r = _post(client, data={"root_password": SECRET,
                                "confirm_root_password": SECRET + "x"})
        assert 'data-flash="error"' in r.text
        assert "do not match" in r.text
        assert client.fs.get(KEY) is None

    def test_surrounding_whitespace_is_refused_not_stripped(self, client):
        """Stripping would store a value the operator did not type, and they
        would find out at a camera's login prompt."""
        _as(_admin())
        padded = " " + SECRET
        r = _post(client, data={"root_password": padded,
                                "confirm_root_password": padded})
        assert 'data-flash="error"' in r.text
        assert client.fs.get(KEY) is None

    def test_a_short_password_is_refused(self, client):
        _as(_admin())
        r = _post(client, data={"root_password": "short",
                                "confirm_root_password": "short"})
        assert 'data-flash="error"' in r.text
        assert client.fs.get(KEY) is None

    def test_every_refusal_is_audited_as_a_failure(self, client):
        _as(_admin())
        _post(client, data={"root_password": SECRET, "confirm_root_password": "nope"})
        rows = _rows()
        assert rows and rows[0].success is False
        assert rows[0].error_message == "mismatch"


# --- what happens to the value ----------------------------------------------


class TestTheValue:
    def test_it_is_encrypted_at_rest(self, client):
        """Asserted against the raw row, not through `get()` — which would decrypt
        and prove nothing about what is on disk."""
        _as(_admin())
        _post(client)
        con = sqlite3.connect(client.db_path)
        try:
            raw = con.execute("SELECT value FROM fleet_settings WHERE key=?",
                              (KEY,)).fetchone()
        finally:
            con.close()
        assert raw is not None, "CONTROL: nothing was stored at all"
        assert raw[0] != SECRET
        assert SECRET not in raw[0]
        from admz import setting_crypto
        assert setting_crypto.looks_encrypted(raw[0])

    def test_it_is_never_echoed_back(self, client):
        _as(_admin())
        r = _post(client)
        assert SECRET not in r.text

    def test_the_page_shows_set_or_unset_but_never_the_value(self, client):
        _as(_admin())
        before = client.get("/fleet-settings").text
        assert 'data-root-password="unset"' in before
        _post(client)
        after = client.get("/fleet-settings").text
        assert 'data-root-password="set"' in after
        assert SECRET not in after

    def test_a_write_is_attributed_and_never_carries_the_value(self, client):
        _as(_admin())
        _post(client)
        rows = _rows()
        assert rows and rows[0].success is True
        assert (rows[0].details or {}).get("op") == "set"
        assert SECRET not in repr(rows)

    def test_a_second_write_is_recorded_as_a_replacement(self, client):
        _as(_admin())
        _post(client)
        other = SECRET + "-v2"
        _post(client, data={"root_password": other, "confirm_root_password": other})
        assert client.fs.get(KEY) == other
        assert (_rows()[0].details or {}).get("op") == "replace"


# --- what the operator is told -------------------------------------------


class TestThePageSaysWhatMatters:
    def test_it_says_changing_it_does_not_touch_provisioned_devices(self, client):
        """The operationally surprising fact: rotating the break-glass password
        leaves every already-provisioned device on the OLD value."""
        page = " ".join(client.get("/fleet-settings").text.split())
        assert "does not change devices ADMZ has already provisioned" in page

    def test_the_unset_state_says_provisioning_will_not_happen(self, client):
        page = " ".join(client.get("/fleet-settings").text.split())
        assert "will not be provisioned" in page.replace("<strong>", "").replace("</strong>", "")

    def test_the_fields_do_not_invite_browser_autofill(self, client):
        """`autocomplete="off"` is ignored on password fields by browsers; an
        autofilled saved login would silently set the wrong break-glass value."""
        import re

        page = client.get("/fleet-settings").text
        fields = re.findall(r"<input[^>]*type=\"password\"[^>]*>", page)
        root_fields = [f for f in fields if "root_password" in f]
        assert len(root_fields) == 2
        for f in root_fields:
            assert 'autocomplete="new-password"' in f
