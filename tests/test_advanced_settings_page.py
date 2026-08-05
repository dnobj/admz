"""The reveal-gated advanced surface: ``/api/capabilities`` + ``/settings/advanced``.

Three properties, in descending order of how much they matter:

1. **The gate model is untouched.** ``TestConfirmationGateStillHolds`` is the
   whole point of the issue's non-goals: with the most dangerous capability
   active, a ``url_only`` operation is *still* blocked. A capability changes
   who may satisfy a gate, never whether one exists (ADR-0034).
2. **Nothing dangerous is a click.** Env-only capabilities refuse a browser
   toggle with a 409 that names the env var; anonymous callers cannot write at
   all; and an authenticated principal outside the reveal groups gets a 403.
3. **The page stays hidden.** No link from ``/settings``, no sidebar entry —
   the only route to it is the chip, which only exists once something is on.

Isolation follows the house rule: every store binds its DB path at import, so
the fixture repoints ``ADMZ_HOME``/``ADMZ_DB_PATH`` at ``tmp_path`` and swaps
the ``fleet_settings`` singleton before the app is built.
"""

# #164: `set()` refuses a declared capability key so no route can
# bypass `capabilities.set_enabled`. These tests arrange LEGACY
# on-disk spellings ("yes", "on", "1") that `set_enabled` cannot
# produce — they exercise the READER's tolerance — so they use the
# private `_raw_set` door deliberately.

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from admz import capabilities
from admz.auth import AuthBackend, Principal, set_active_backend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubBackend(AuthBackend):
    """Returns a configurable Principal for every request."""

    def __init__(self, principal: Principal):
        self.principal = principal

    async def authenticate(self, request):
        return self.principal


def _anon() -> Principal:
    return Principal(
        name="anonymous", display_name="anonymous",
        source="none", is_anonymous=True,
    )


def _windows(name: str, groups=None) -> Principal:
    return Principal(
        name=f"AXIS\\{name}", display_name=name, domain="AXIS",
        groups=list(groups or []), source="windows",
    )


def _admin() -> Principal:
    return _windows("alice", ["Administrators"])


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    monkeypatch.delenv("ADMZ_REVEAL_GROUPS", raising=False)

    from admz import fleet_settings as fs_module

    fresh = fs_module.FleetSettings(str(tmp_path / "admz.db"))
    monkeypatch.setattr(fs_module, "fleet_settings", fresh)

    backend = StubBackend(_anon())
    set_active_backend(backend)

    from admz.api.main import app

    app.state._stub_backend = backend
    try:
        with TestClient(app, follow_redirects=False) as c:
            c.settings_store = fresh
            yield c
    finally:
        from admz.auth import NoAuth

        set_active_backend(NoAuth())


@pytest.fixture
def clean_caps(monkeypatch):
    """Unset every capability env var, including conftest's two suppressors.

    Without this, "no chip" and "no link" assertions would be testing the
    conftest rather than the code.
    """
    for cap in capabilities.CAPABILITIES:
        if cap.env_var:
            monkeypatch.delenv(cap.env_var, raising=False)
    return monkeypatch


def _as(client, principal: Principal) -> None:
    client.app.state._stub_backend.principal = principal


def _toggle(client, cap_id, enabled=True, confirm=None, reason="because"):
    return client.post(
        f"/api/capabilities/{cap_id}",
        json={
            "enabled": enabled,
            "confirm_id": cap_id if confirm is None else confirm,
            "reason": reason,
        },
    )


# ---------------------------------------------------------------------------
# GET /api/capabilities
# ---------------------------------------------------------------------------


class TestReadApi:

    def test_anonymous_is_refused(self, client):
        _as(client, _anon())
        assert client.get("/api/capabilities").status_code == 403

    def test_any_authenticated_principal_may_read_the_table(self, client):
        _as(client, _windows("bob"))  # no groups: reading is not revealing
        r = client.get("/api/capabilities")
        assert r.status_code == 200
        ids = {row["id"] for row in r.json()["capabilities"]}
        assert ids == {c.id for c in capabilities.CAPABILITIES}

    def test_rows_carry_state_and_provenance(self, client, clean_caps):
        clean_caps.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        _as(client, _windows("bob"))
        body = client.get("/api/capabilities").json()

        row = next(r for r in body["capabilities"] if r["id"] == "dev.auto_approve")
        assert row["enabled"] is True
        assert row["source"] == "env"
        assert row["danger"] == "dev-only"
        assert row["toggleable"] is False
        assert body["active"] == ["dev.auto_approve"]

    def test_env_only_rows_are_marked_untoggleable(self, client):
        _as(client, _windows("bob"))
        rows = client.get("/api/capabilities").json()["capabilities"]
        for row in rows:
            assert row["toggleable"] is ("setting" in row["enable_via"])

    def test_the_auth_backend_is_context_not_a_row(self, client):
        """Master resolution 5: it informs, but it is not a capability — no
        row, no chip, no /api/health entry."""
        _as(client, _windows("bob"))
        body = client.get("/api/capabilities").json()

        assert body["auth_backend"]["backend"] == "none"
        assert body["auth_backend"]["anonymous"] is True
        assert not any(
            "AUTH_BACKEND" in (r["env_var"] or "") for r in body["capabilities"]
        )

    def test_no_setting_values_are_returned(self, client, clean_caps):
        """Knob *names* are inventory; knob *values* are not."""
        clean_caps.setenv("ADMZ_DEV_AUTO_APPROVE", "hunter2")
        _as(client, _windows("bob"))
        assert "hunter2" not in client.get("/api/capabilities").text


# ---------------------------------------------------------------------------
# POST /api/capabilities/{id} — tests 17 and 19
# ---------------------------------------------------------------------------


class TestToggleApi:

    def test_anonymous_cannot_write(self, client):
        """Test 17. The page is readable without an identity; changing what
        the installation is allowed to do is not."""
        _as(client, _anon())
        r = _toggle(client, "events.device_ingest")
        assert r.status_code == 403
        assert "ADMZ_AUTH_BACKEND=none" in r.json()["detail"]
        assert capabilities.is_active("events.device_ingest") is False

    def test_authenticated_but_not_in_a_reveal_group_is_refused(self, client):
        _as(client, _windows("bob", ["Users"]))
        r = _toggle(client, "events.device_ingest")
        assert r.status_code == 403
        assert "Administrators" in r.json()["detail"]

    def test_reveal_principal_can_enable_a_privileged_capability(
        self, client, clean_caps
    ):
        _as(client, _admin())
        r = _toggle(client, "events.device_ingest", reason="demo in the loading bay")

        assert r.status_code == 200
        assert r.json()["enabled"] is True
        assert r.json()["source"] == "setting"
        assert client.settings_store.get("event_ingest_enabled") == "true"

        from admz.events import config as cfg

        assert cfg.event_ingest_enabled() is True

    def test_the_toggle_is_audited_with_the_principal_and_reason(
        self, client, clean_caps, tmp_path
    ):
        _as(client, _admin())
        _toggle(client, "acs.firebird_read", reason="diagnosing rule 14358")

        from admz.audit import AuditLog

        rows = [
            r for r in AuditLog(db_path=str(tmp_path / "admz.db")).list_recent(limit=50)
            if r.action == "capability.enable"
        ]
        assert len(rows) == 1
        assert rows[0].requester == "AXIS\\alice"
        assert rows[0].resource == "capability:acs.firebird_read"
        assert rows[0].details["reason"] == "diagnosing rule 14358"

    def test_disable_round_trips(self, client, clean_caps):
        _as(client, _admin())
        _toggle(client, "events.device_ingest", enabled=True)
        r = _toggle(client, "events.device_ingest", enabled=False, reason="too chatty")
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        assert capabilities.is_active("events.device_ingest") is False

    def test_the_typed_acknowledgement_is_required(self, client, clean_caps):
        _as(client, _admin())
        r = _toggle(client, "events.device_ingest", confirm="")
        assert r.status_code == 400
        assert "events.device_ingest" in r.json()["detail"]
        assert capabilities.is_active("events.device_ingest") is False

    def test_a_mistyped_acknowledgement_is_refused(self, client, clean_caps):
        _as(client, _admin())
        r = _toggle(client, "events.device_ingest", confirm="events.acs_poll")
        assert r.status_code == 400
        assert capabilities.is_active("events.device_ingest") is False

    def test_a_reason_is_required(self, client, clean_caps):
        _as(client, _admin())
        r = _toggle(client, "events.device_ingest", reason="   ")
        assert r.status_code == 400
        assert "audit" in r.json()["detail"]

    @pytest.mark.parametrize(
        "cap_id",
        [c.id for c in capabilities.CAPABILITIES if "setting" not in c.enable_via],
    )
    def test_env_only_capabilities_return_409_naming_the_env_var(
        self, cap_id, client, clean_caps
    ):
        """Test 19. ``dev.auto_approve`` and ``acs.rule_write`` cannot be
        enabled from a web page — by design *and* by test."""
        _as(client, _admin())
        r = _toggle(client, cap_id)

        assert r.status_code == 409
        detail = r.json()["detail"]
        assert capabilities.get(cap_id).env_var in detail
        assert "restart" in detail
        assert capabilities.is_active(cap_id) is False

    def test_unknown_capability_is_404(self, client):
        _as(client, _admin())
        assert _toggle(client, "nope.not_a_thing").status_code == 404

    def test_disabling_an_env_forced_capability_says_it_is_still_on(
        self, client, clean_caps
    ):
        clean_caps.setenv("ADMZ_EVENT_INGEST", "1")
        _as(client, _admin())
        r = _toggle(client, "events.device_ingest", enabled=False, reason="stop it")

        body = r.json()
        assert body["enabled"] is True
        assert body["source"] == "env"
        assert "ADMZ_EVENT_INGEST" in body["note"]


# ---------------------------------------------------------------------------
# The hidden page — test 9 and the anonymous read-only path (test 17)
# ---------------------------------------------------------------------------


class TestAdvancedPage:

    def test_reveal_principal_gets_the_page_with_controls(self, client):
        _as(client, _admin())
        r = client.get("/settings/advanced")
        assert r.status_code == 200
        assert "cap-toggle-form" in r.text
        assert "events.device_ingest" in r.text

    def test_anonymous_gets_the_page_read_only(self, client):
        """Master resolution 2: the diagnostic value is highest on exactly the
        unauthenticated dev box where these switches get used, so the page
        informs — and refuses to act."""
        _as(client, _anon())
        r = client.get("/settings/advanced")

        assert r.status_code == 200
        assert "cap-toggle-form" not in r.text
        assert "Read-only for this caller" in r.text
        assert "ADMZ_AUTH_BACKEND=none" in r.text

    def test_authenticated_outsider_is_refused_outright(self, client):
        """A real identity that has been checked and refused gets a 403 —
        degrading it to read-only would be a different answer."""
        _as(client, _windows("bob", ["Users"]))
        assert client.get("/settings/advanced").status_code == 403

    def test_env_only_capabilities_render_as_facts_not_controls(self, client):
        _as(client, _admin())
        text = client.get("/settings/advanced").text
        assert "Environment variable only" in text
        assert "ADMZ_DEV_AUTO_APPROVE=1" in text

    def test_the_auth_backend_appears_as_context(self, client):
        _as(client, _admin())
        assert "context, not a capability" in client.get("/settings/advanced").text

    def test_the_page_form_toggles(self, client, clean_caps):
        _as(client, _admin())
        r = client.post(
            "/settings/advanced",
            data={
                "cap_id": "events.acs_poll",
                "enabled": "1",
                "confirm_id": "events.acs_poll",
                "reason": "watching ACS rules",
            },
        )
        assert r.status_code == 200
        assert capabilities.is_active("events.acs_poll") is True

    def test_the_page_form_refuses_an_anonymous_caller(self, client, clean_caps):
        _as(client, _anon())
        r = client.post(
            "/settings/advanced",
            data={
                "cap_id": "events.acs_poll", "enabled": "1",
                "confirm_id": "events.acs_poll", "reason": "sneaking",
            },
        )
        assert r.status_code == 200          # rendered, not raised
        assert "refused" in r.text
        assert capabilities.is_active("events.acs_poll") is False

    def test_the_page_form_surfaces_a_bad_acknowledgement(self, client, clean_caps):
        _as(client, _admin())
        r = client.post(
            "/settings/advanced",
            data={
                "cap_id": "events.acs_poll", "enabled": "1",
                "confirm_id": "", "reason": "no ack",
            },
        )
        assert "refused" in r.text
        assert capabilities.is_active("events.acs_poll") is False

    # -- it stays hidden ----------------------------------------------------

    def test_settings_does_not_link_to_it(self, client, clean_caps):
        """Layer 1 of the hiding: no link, no nav, ever. Asserted on a clean
        install, because the chip legitimately links there once something is
        on — and the chip is the *only* thing that ever should."""
        _as(client, _admin())
        r = client.get("/settings")
        assert r.status_code == 200
        assert "/settings/advanced" not in r.text

    def test_the_sidebar_has_no_advanced_entry(self, client, clean_caps):
        from admz.api.templating import _assemble_nav_sections, _build_nav_data

        class _Req:
            query_params: dict = {}
            cookies: dict = {}
            state = None

        nav = _build_nav_data(_Req())
        keys = {
            item["key"]
            for section in _assemble_nav_sections(nav)
            for item in section["items"]
        }
        assert not any("advanced" in k or "capabilit" in k for k in keys)


# ---------------------------------------------------------------------------
# Test 10 — the topbar chip
# ---------------------------------------------------------------------------


class TestTopbarChip:

    def _page(self, client):
        _as(client, _admin())
        return client.get("/settings").text

    def test_absent_on_a_clean_install(self, client, clean_caps):
        assert "advanced-capability-chip" not in self._page(client)

    def test_red_for_a_capability_that_is_not_production_appropriate(
        self, client, clean_caps
    ):
        clean_caps.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        text = self._page(client)
        assert 'id="advanced-capability-chip"' in text
        assert 'data-severity="red"' in text
        assert "/settings/advanced" in text

    def test_amber_for_a_privileged_install_profile(self, client, clean_caps):
        clean_caps.setenv("ADMZ_EVENT_INGEST", "1")
        text = self._page(client)
        assert 'data-severity="amber"' in text

    def test_red_wins_when_both_kinds_are_active(self, client, clean_caps):
        clean_caps.setenv("ADMZ_EVENT_INGEST", "1")
        clean_caps.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        text = self._page(client)
        assert 'data-severity="red"' in text
        assert "Advanced · 2" in text

    def test_internal_capabilities_never_chip(self, client, clean_caps):
        """Chip fatigue is a real failure mode: ``runtime.no_scheduler`` is a
        role marker ADMZ sets for its own subprocesses, and badging it would
        train operators to ignore the badge."""
        clean_caps.setenv("ADMZ_MCP_NO_SCHEDULER", "1")
        assert capabilities.is_active("runtime.no_scheduler") is True
        assert "advanced-capability-chip" not in self._page(client)

    def test_a_setting_enabled_capability_chips_too(self, client, clean_caps):
        client.settings_store._raw_set("survey_mode_enabled", "true")
        text = self._page(client)
        assert 'data-severity="amber"' in text
        assert "survey.contributor" in text

    def test_the_chip_survives_a_broken_settings_store(
        self, client, clean_caps, monkeypatch
    ):
        """The nav must render even when config is unreachable."""
        monkeypatch.setattr(
            capabilities, "active_capabilities",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert self._page(client)  # renders, chip simply absent


# ---------------------------------------------------------------------------
# Test 18 — the confirmation gate is untouched
# ---------------------------------------------------------------------------


class TestConfirmationGateStillHolds:
    """The single most important test in #132.

    ADR-0034 removed flat refusals: every destructive action routes through the
    link/widget gate. An advanced capability that *lowered* a gate would be
    reversing an ADR written after a real incident. ``dev.auto_approve`` only
    changes **who may satisfy** a gate — the approver posts to the same
    endpoint a human's browser does. It never changes **whether** approval is
    required, and this proves it at the boundary.
    """

    def test_url_only_still_blocks_with_dev_auto_approve_on(
        self, client, clean_caps, monkeypatch
    ):
        from admz import operations

        clean_caps.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        # Guard against a green test for the wrong reason.
        assert capabilities.is_active("dev.auto_approve") is True

        monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_only")
        r = client.post(
            "/api/catalog/execute",
            json={
                "device_id": "dev",
                "operation_id": "restart.cgi:restart",
                "params": {},
            },
        )

        assert r.status_code == 200
        body = r.json()
        assert body["blocked"] is True
        assert body["confirmation_level"] == "url_only"
        assert body["confirm_url"].startswith("/confirm/")
        assert body["confirm_token"]

    def test_the_hardest_gate_is_also_unchanged(
        self, client, clean_caps, monkeypatch
    ):
        from admz import operations

        clean_caps.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        monkeypatch.setattr(
            operations, "resolve_confirmation", lambda r: "url_and_password"
        )
        body = client.post(
            "/api/catalog/execute",
            json={
                "device_id": "dev",
                "operation_id": "factorydefault.cgi:reset",
                "params": {},
            },
        ).json()

        assert body["blocked"] is True
        assert body["confirmation_level"] == "url_and_password"

    def test_no_capability_declares_itself_as_relaxing_a_gate(self):
        """A structural reading of the table: nothing in it is allowed to be
        about approval policy. The confirm levels live in fleet settings and
        are not capabilities."""
        for cap in capabilities.CAPABILITIES:
            assert not cap.setting_key.startswith("confirm_level")
            assert cap.setting_key != "confirm_password_hash"
