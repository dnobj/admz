"""The ACS webhook token is never handed out by the page (GH #350).

`acs_webhook_token` authenticates ``POST /api/acs/rule-fired``, which is in
``_EXEMPT_PATH_PREFIXES`` — so whoever reads the value can forge rule firings
into the event store and detection evaluator with no ADMZ session at all.
Every other surface treats it accordingly: the fleet-settings JSON masks it,
the fleet-settings page never puts it in template context (#158), and
``/api/fleet/settings/{key}/reveal`` demands reveal-group membership and
writes an audit row.

`GET /acs` did not. It rendered the live value into the HTML for any principal
that could load the page — ``type="password"`` masks the glyphs in a browser
and nothing else — and, because ``get_token()`` defaults to ``create=True``,
loading the page could also MINT and PERSIST a protected setting with no
principal and no audit row.

This file pins all three properties:
  - the page never contains the token value, revealed or masked
  - the page never creates a token as a side effect of being viewed
  - regenerate — whose response body carries the credential — requires
    reveal-group membership, not merely an authenticated identity, so it
    cannot be used as a read gate with one extra click
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from admz.auth import AuthBackend, NoAuth, Principal, set_active_backend


TOKEN_VALUE = "acs-webhook-secret-value-350"


class StubBackend(AuthBackend):
    """Returns a configurable principal; rotate via ``backend.principal``."""

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
    from admz.api.routes import web as web_route
    from admz.modules.acs_pro import routes as acs_routes
    from admz.modules.acs_pro import webhook as wh_module

    db_path = str(tmp_path / "admz.db")
    fresh_fs = fs_module.FleetSettings(db_path)
    # All THREE module references, repointed and restored together. Route
    # modules did `from admz.fleet_settings import fleet_settings`, so each
    # holds its own binding; repointing a subset leaves the survivors reading
    # a different store, and a later file that WRITES through one reference
    # and READS through another sees an empty result. That is a cross-file
    # failure with no local symptom — it cost a run here before the set was
    # completed, and it is why the other suites repoint all three.
    originals = [
        (fs_module, "fleet_settings", fs_module.fleet_settings),
        (devices_route, "fleet_settings", devices_route.fleet_settings),
        (web_route, "fleet_settings", web_route.fleet_settings),
    ]
    fs_module.fleet_settings = fresh_fs
    devices_route.fleet_settings = fresh_fs
    web_route.fleet_settings = fresh_fs
    # webhook.py resolves the store through a helper, so repoint that too —
    # otherwise get_token() would read the operator's real database.
    monkeypatch.setattr(wh_module, "_settings", lambda: fresh_fs)

    # The ACS module is off by default and the page redirects when disabled;
    # turn it on and stub the two live calls the page makes.
    monkeypatch.setattr(acs_routes, "acs_config",
                        lambda: {"enabled": True, "server_url": "https://acs:29204"})

    async def _fake_op(catalog, executors, op, params):
        if op.endswith("GetApiVersion"):
            return {"success": True, "data": {"Version": "6.5"}}
        return {"success": True, "data": {"Cameras": []}}

    monkeypatch.setattr(acs_routes, "run_acs_op", _fake_op)

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


def _seed_token(client) -> None:
    from admz.fleet_settings import fleet_settings
    fleet_settings.set("acs_webhook_token", TOKEN_VALUE)


# ---------------------------------------------------------------------------
# The page never carries the value
# ---------------------------------------------------------------------------


class TestPageDoesNotRenderTheToken:
    def test_anonymous_page_load_has_no_token(self, client):
        _seed_token(client)
        r = client.get("/acs")
        assert r.status_code == 200
        assert TOKEN_VALUE not in r.text

    def test_reveal_group_member_page_load_also_has_no_token(self, client):
        # Even for a principal who IS allowed to reveal, the page does not
        # pre-load the secret — reading it stays an explicit, audited act.
        _seed_token(client)
        _set_principal(client, _windows("alice", ["Administrators"]))
        r = client.get("/acs")
        assert r.status_code == 200
        assert TOKEN_VALUE not in r.text

    def test_page_reports_configured_state_without_the_value(self, client):
        _seed_token(client)
        r = client.get("/acs")
        # The operator can still tell a token exists, and the reveal control
        # is offered — it just fetches through the gate.
        assert "wh-token" in r.text
        assert "/reveal" in r.text

    def test_unconfigured_page_offers_creation_not_a_blank_secret(self, client):
        r = client.get("/acs")
        assert r.status_code == 200
        assert "Create token" in r.text


class TestPageDoesNotMintAToken:
    def test_viewing_the_page_does_not_create_a_token(self, client):
        """`get_token()` defaults to create=True and PERSISTS what it mints.

        The page must pass create=False: a GET by an unauthenticated visitor
        writing a protected fleet setting — with no principal and no audit
        row — is a write where the operator expects a read.
        """
        from admz.fleet_settings import fleet_settings
        assert fleet_settings.get("acs_webhook_token") is None

        r = client.get("/acs")
        assert r.status_code == 200

        assert fleet_settings.get("acs_webhook_token") is None, (
            "loading /acs minted and persisted a webhook token"
        )


# ---------------------------------------------------------------------------
# Regenerate hands over a credential, so it takes the reveal gate
# ---------------------------------------------------------------------------


class TestRegenerateRequiresRevealGroup:
    def test_anonymous_refused(self, client):
        r = client.post("/api/acs/webhook-token/regenerate")
        assert r.status_code == 403

    def test_authenticated_but_not_in_reveal_group_refused(self, client):
        # The pre-#350 gate (require_authenticated_principal) would have let
        # this through and returned the credential in the body — making the
        # reveal gate bypassable with one extra click.
        _set_principal(client, _windows("carol", ["Users"]))
        r = client.post("/api/acs/webhook-token/regenerate")
        assert r.status_code == 403
        assert "token" not in r.json()

    def test_reveal_group_member_allowed(self, client):
        _set_principal(client, _windows("alice", ["Administrators"]))
        r = client.post("/api/acs/webhook-token/regenerate")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True and body["token"]

        from admz.fleet_settings import fleet_settings
        assert fleet_settings.get("acs_webhook_token") == body["token"]

    def test_refusal_does_not_rotate_the_token(self, client):
        """A 403 must leave ACS working — a refused caller that still rotated
        would be a denial-of-service on every configured ACS rule."""
        _seed_token(client)
        _set_principal(client, _windows("carol", ["Users"]))
        client.post("/api/acs/webhook-token/regenerate")

        from admz.fleet_settings import fleet_settings
        assert fleet_settings.get("acs_webhook_token") == TOKEN_VALUE

    def test_success_is_audited_with_the_decision(self, client):
        _set_principal(client, _windows("alice", ["Administrators"]))
        assert client.post("/api/acs/webhook-token/regenerate").status_code == 200

        from admz.audit import AuditLog
        entries = AuditLog().list_recent(action="acs.webhook_token.regenerate", limit=5)
        assert entries
        assert entries[0].success is True
        assert entries[0].resource == "acs:webhook"


# ---------------------------------------------------------------------------
# The reveal endpoint remains the one read path, and it is gated
# ---------------------------------------------------------------------------


class TestRevealEndpointIsTheOnlyReadPath:
    def test_non_member_cannot_read_it_there_either(self, client):
        _seed_token(client)
        _set_principal(client, _windows("carol", ["Users"]))
        r = client.get("/api/fleet/settings/acs_webhook_token/reveal")
        assert r.status_code == 403
        assert TOKEN_VALUE not in r.text

    def test_member_can(self, client):
        _seed_token(client)
        _set_principal(client, _windows("alice", ["Administrators"]))
        r = client.get("/api/fleet/settings/acs_webhook_token/reveal")
        assert r.status_code == 200
        assert r.json()["value"] == TOKEN_VALUE
