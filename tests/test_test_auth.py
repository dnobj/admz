"""Test auth mode — the ``dev.test_auth`` advanced capability (GH #140).

An agent verifying the ADMZ web UI cannot complete the Negotiate SSO handshake
``windows-local`` requires, so today it lands on the sign-in page and stops.
``ADMZ_AUTH_BACKEND=none`` is not a workaround either: its principal is
``is_anonymous``, which every ``require_authenticated_principal`` surface
refuses. This capability resolves an otherwise-unauthenticated request to a
fixed synthetic principal instead.

Four properties, in descending order of how much they matter:

1. **It cannot be exposed off-box.** The server refuses to start when the
   capability is active and the bind is not loopback (no override), and the
   backend re-checks the client address on every request so the bypass is
   unreachable even from a bare ``uvicorn`` launch.
2. **It never softens the confirmation gate.** ADR-0034 in full: a ``url_only``
   operation still returns ``blocked: true``. This changes *who* the principal
   is, never *whether* approval is required. Mirrors test 18 of #132.
3. **It is loud.** All five loudness surfaces of the capability registry are
   asserted here one by one rather than assumed to come for free.
4. **It is invisible when off.** Absent ``ADMZ_TEST_AUTH`` the auth chain, the
   chip, ``/api/health`` and the startup lines are byte-identical to today.

Isolation follows the house rule: every store binds its DB path at import, so
anything that reaches a store repoints ``ADMZ_HOME``/``ADMZ_DB_PATH`` at
``tmp_path`` first.

Note on ``TestClient``: Starlette reports the client host as ``"testclient"``
by default, which is not a loopback address and is therefore refused — as it
should be. Tests that exercise the happy path pass an explicit loopback client.
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from admz import auth as auth_module
from admz import capabilities
from admz.auth import (
    TEST_AUTH_DEFAULT_GROUPS,
    TEST_AUTH_DEFAULT_NAME,
    ApiKeyAuth,
    CompositeAuth,
    NoAuth,
    Principal,
    SessionAuth,
    TestAuth,
    build_auth_backend,
)


CAP_ID = "dev.test_auth"
LOOPBACK = ("127.0.0.1", 50000)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_caps(monkeypatch):
    """Unset every capability env var, including conftest's two suppressors.

    Without this, the "nothing is active" assertions would be testing
    ``tests/conftest.py`` rather than the code.
    """
    for cap in capabilities.CAPABILITIES:
        if cap.env_var:
            monkeypatch.delenv(cap.env_var, raising=False)
    for cap in capabilities.CAPABILITIES:
        for companion in cap.companion_env:
            monkeypatch.delenv(companion, raising=False)
    monkeypatch.delenv("ADMZ_AUTH_BACKEND", raising=False)
    return monkeypatch


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """A real FleetSettings backed by a temp DB, wired into the registry."""
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from admz.fleet_settings import FleetSettings

    store = FleetSettings(db_path=str(tmp_path / "admz.db"))
    monkeypatch.setattr(capabilities, "_settings", lambda: store)
    return store


class _Request:
    """The two attributes an auth backend reads off a request."""

    def __init__(self, host="127.0.0.1"):
        self.client = None if host is None else type("C", (), {"host": host})()
        self.headers = {}
        self.cookies = {}


# ---------------------------------------------------------------------------
# The declaration
# ---------------------------------------------------------------------------


class TestTheCapabilityIsDeclared:
    """#140 registers rather than inventing another bespoke env var."""

    def test_the_row_exists(self):
        cap = capabilities.get(CAP_ID)
        assert cap is not None
        assert cap.env_var == "ADMZ_TEST_AUTH"

    def test_it_is_dev_only_and_never_production_appropriate(self):
        cap = capabilities.get(CAP_ID)
        assert cap.danger == "dev-only"
        assert cap.production_appropriate is False

    def test_it_is_env_only_per_the_asymmetry_rule(self):
        """A dev-only capability must never be a click in a browser."""
        cap = capabilities.get(CAP_ID)
        assert cap.enable_via == ("env",)
        assert cap.setting_key == ""
        assert capabilities.is_toggleable(CAP_ID) is False

    def test_a_browser_toggle_is_refused_at_the_registry(self):
        with pytest.raises(capabilities.NotToggleable) as exc:
            capabilities.set_enabled(CAP_ID, True, None, reason="nope")
        assert "ADMZ_TEST_AUTH" in str(exc.value)

    def test_the_companion_inputs_are_documented(self):
        cap = capabilities.get(CAP_ID)
        assert cap.companion_env == ("ADMZ_TEST_AUTH_USER", "ADMZ_TEST_AUTH_GROUPS")

    def test_it_resolves_from_its_env_var(self, clean_caps, isolated_settings):
        assert capabilities.is_active(CAP_ID) is False
        clean_caps.setenv("ADMZ_TEST_AUTH", "1")
        assert capabilities.is_active(CAP_ID) is True
        assert capabilities.source_of(CAP_ID) == "env"


# ---------------------------------------------------------------------------
# Off by default — byte-identical behaviour when absent
# ---------------------------------------------------------------------------


class TestOffByDefault:
    """Asserted, not assumed: an installation without the env var behaves
    exactly as it did before #140."""

    def test_the_default_backend_is_untouched(self, clean_caps, isolated_settings):
        assert isinstance(build_auth_backend("none"), NoAuth)

    def test_windows_local_chain_is_untouched(self, clean_caps, isolated_settings):
        backend = build_auth_backend("windows-local")
        assert isinstance(backend, CompositeAuth)
        assert [type(b) for b in backend.backends] == [ApiKeyAuth, SessionAuth]

    def test_composite_chain_is_untouched(self, clean_caps, isolated_settings):
        backend = build_auth_backend("composite")
        assert isinstance(backend, CompositeAuth)
        assert not any(isinstance(b, TestAuth) for b in backend.backends)

    @pytest.mark.parametrize("raw", ["0", "false", "", "no"])
    def test_off_spellings_do_not_activate_it(
        self, raw, clean_caps, isolated_settings
    ):
        clean_caps.setenv("ADMZ_TEST_AUTH", raw)
        assert capabilities.is_active(CAP_ID) is False
        assert isinstance(build_auth_backend("none"), NoAuth)

    def test_nothing_is_reported_active(self, clean_caps, isolated_settings):
        assert capabilities.active_ids() == []
        assert capabilities.startup_lines() == [
            (logging.INFO, "advanced capabilities: none")
        ]

    def test_test_auth_is_not_selectable_as_an_auth_backend(
        self, clean_caps, isolated_settings
    ):
        """A dev-only bypass belongs in the registry, not in the list of
        backends an operator can name — otherwise it could be selected without
        the registry ever knowing it was on."""
        assert "test" not in auth_module._VALID_BACKENDS
        assert isinstance(build_auth_backend("test"), NoAuth)


# ---------------------------------------------------------------------------
# The backend, when active
# ---------------------------------------------------------------------------


class TestBackendWiring:

    def test_it_replaces_noauth(self, clean_caps, isolated_settings):
        """Anonymous mode is exactly what the capability exists to stop handing
        out (#140), and NoAuth never fails — appending would be dead code."""
        clean_caps.setenv("ADMZ_TEST_AUTH", "1")
        assert isinstance(build_auth_backend("none"), TestAuth)

    def test_it_goes_last_in_a_real_chain(self, clean_caps, isolated_settings):
        """A real credential still wins, so the audit log keeps saying who
        actually called."""
        clean_caps.setenv("ADMZ_TEST_AUTH", "1")
        backend = build_auth_backend("windows-local")
        assert isinstance(backend, CompositeAuth)
        assert [type(b) for b in backend.backends] == [
            ApiKeyAuth, SessionAuth, TestAuth,
        ]

    def test_the_chain_is_flattened_not_nested(self, clean_caps, isolated_settings):
        clean_caps.setenv("ADMZ_TEST_AUTH", "1")
        backend = build_auth_backend("composite")
        assert not any(isinstance(b, CompositeAuth) for b in backend.backends)

    def test_a_non_composite_backend_is_wrapped(self, clean_caps, isolated_settings):
        clean_caps.setenv("ADMZ_TEST_AUTH", "1")
        backend = build_auth_backend("api-key")
        assert isinstance(backend, CompositeAuth)
        assert [type(b) for b in backend.backends] == [ApiKeyAuth, TestAuth]

    @pytest.mark.asyncio
    async def test_a_real_credential_still_wins(self, clean_caps, isolated_settings):
        clean_caps.setenv("ADMZ_TEST_AUTH", "1")

        class _Real(auth_module.AuthBackend):
            async def authenticate(self, request):
                return Principal(name="AXIS\\alice", display_name="alice",
                                 source="windows")

        chain = CompositeAuth([_Real(), TestAuth()])
        principal = await chain.authenticate(_Request())
        assert principal.name == "AXIS\\alice"
        assert principal.source == "windows"


# ---------------------------------------------------------------------------
# The principal it produces
# ---------------------------------------------------------------------------


class TestSyntheticPrincipal:
    """It must be a *real* principal of the same shape the other backends
    produce — that is the entire point (#140: anonymous mode has none)."""

    @pytest.mark.asyncio
    async def test_it_is_a_principal_and_not_anonymous(self):
        principal = await TestAuth().authenticate(_Request())
        assert isinstance(principal, Principal)
        assert principal.is_anonymous is False

    @pytest.mark.asyncio
    async def test_the_default_identity_is_obviously_synthetic(self):
        principal = await TestAuth().authenticate(_Request())
        assert principal.name == TEST_AUTH_DEFAULT_NAME == "test\\agent"
        assert principal.display_name == "agent"
        assert principal.domain == "test"

    @pytest.mark.asyncio
    async def test_the_source_names_the_backend(self):
        """So an audit row can tell a test principal from a real Windows one."""
        principal = await TestAuth().authenticate(_Request())
        assert principal.source == "test"

    @pytest.mark.asyncio
    async def test_it_satisfies_require_authenticated_principal(self):
        from admz.authz import require_authenticated_principal

        require_authenticated_principal(await TestAuth().authenticate(_Request()))

    @pytest.mark.asyncio
    async def test_reveal_denied_by_default(self):
        """The synthetic principal is authenticated but UNPRIVILEGED.

        This is the security property of the default, not an accident of it:
        an unattended verification run needs *a principal*, not an
        *administrator*. Granting reveal groups by default would let a
        synthetic, unauthenticated-by-design caller read plaintext device
        credentials — and a staging instance typically carries a copy of the
        real ones. If someone ever restores a permissive default, this fails.
        """
        from admz.authz import principal_can_reveal, require_reveal_permission
        from fastapi import HTTPException

        principal = await TestAuth().authenticate(_Request())
        assert principal.groups == list(TEST_AUTH_DEFAULT_GROUPS) == []

        allowed, reason = principal_can_reveal(principal)
        assert allowed is False
        assert reason == "no-groups"

        with pytest.raises(HTTPException) as exc:
            require_reveal_permission(principal)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_groups_can_be_granted_explicitly_when_needed(self, clean_caps):
        """The escape hatch works: an authz path that must be exercised gets
        membership deliberately and visibly, rather than by default."""
        from admz.authz import principal_can_reveal

        clean_caps.setenv("ADMZ_TEST_AUTH_GROUPS", "Administrators")
        principal = TestAuth.from_env().principal()
        allowed, _reason = principal_can_reveal(principal)
        assert allowed is True

    def test_the_identity_is_configurable(self, clean_caps):
        clean_caps.setenv("ADMZ_TEST_AUTH_USER", "LAB\\robot")
        clean_caps.setenv("ADMZ_TEST_AUTH_GROUPS", "ADMZ-Admins, Operators")
        principal = TestAuth.from_env().principal()
        assert principal.name == "LAB\\robot"
        assert principal.display_name == "robot"
        assert principal.domain == "LAB"
        assert principal.groups == ["ADMZ-Admins", "Operators"]

    def test_an_empty_group_list_means_no_groups(self, clean_caps):
        """Set-but-empty is distinguishable from unset, so "authenticated but
        unprivileged" is testable."""
        from admz.authz import principal_can_reveal

        clean_caps.setenv("ADMZ_TEST_AUTH_GROUPS", "")
        principal = TestAuth.from_env().principal()
        assert principal.groups == []
        allowed, reason = principal_can_reveal(principal)
        assert allowed is False
        assert reason == "no-groups"

    def test_unset_companions_fall_back_to_the_defaults(self, clean_caps):
        principal = TestAuth.from_env().principal()
        assert principal.name == TEST_AUTH_DEFAULT_NAME
        assert principal.groups == list(TEST_AUTH_DEFAULT_GROUPS)

    def test_a_bare_username_still_yields_a_principal(self, clean_caps):
        clean_caps.setenv("ADMZ_TEST_AUTH_USER", "agent")
        principal = TestAuth.from_env().principal()
        assert principal.name == "agent"
        assert principal.display_name == "agent"
        assert principal.domain is None


# ---------------------------------------------------------------------------
# It is unreachable from off-box — per request
# ---------------------------------------------------------------------------


class TestLoopbackOnlyPerRequest:
    """Belt to the startup guard's braces: a startup check goes stale the
    moment the launch path changes, so the address is re-checked per request
    (the same reasoning as NFR-AUTH-005)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost", "127.0.0.53"])
    async def test_loopback_clients_are_authenticated(self, host):
        principal = await TestAuth().authenticate(_Request(host))
        assert principal.name == TEST_AUTH_DEFAULT_NAME

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "host", ["10.0.0.5", "192.168.1.7", "0.0.0.0", "testclient", None],
    )
    async def test_everything_else_is_refused(self, host):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await TestAuth().authenticate(_Request(host))
        assert exc.value.status_code == 401

    def test_is_loopback_rejects_unparseable_addresses(self):
        assert auth_module._is_loopback("not-an-address") is False
        assert auth_module._is_loopback("") is False
        assert auth_module._is_loopback(None) is False
        assert auth_module._is_loopback("[::1]") is True


# ---------------------------------------------------------------------------
# The refuse-to-start guard
# ---------------------------------------------------------------------------


class TestStartupRefusal:
    """The safety-critical half of #140. Modelled on the existing
    ``ADMZ_AUTH_INSECURE_BIND_OK`` refusal, minus the override."""

    def _check(self, host):
        from admz.__main__ import _check_test_auth_bind

        return _check_test_auth_bind(host)

    @pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
    def test_loopback_with_the_capability_active_starts(
        self, host, clean_caps, isolated_settings
    ):
        clean_caps.setenv("ADMZ_TEST_AUTH", "1")
        assert capabilities.is_active(CAP_ID) is True  # not green for the wrong reason
        self._check(host)  # does not raise

    @pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "::"])
    def test_non_loopback_with_the_capability_active_refuses(
        self, host, clean_caps, isolated_settings, capsys
    ):
        clean_caps.setenv("ADMZ_TEST_AUTH", "1")
        with pytest.raises(SystemExit) as exc:
            self._check(host)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "dev.test_auth" in err
        assert host in err
        assert "ADMZ_TEST_AUTH" in err

    @pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20"])
    def test_non_loopback_is_fine_when_the_capability_is_off(
        self, host, clean_caps, isolated_settings
    ):
        self._check(host)  # does not raise

    def test_there_is_no_override_env_var(
        self, clean_caps, isolated_settings, capsys
    ):
        """Unlike ADMZ_AUTH_INSECURE_BIND_OK there is deliberately no escape
        hatch — nothing legitimately needs a synthetic principal off-box."""
        clean_caps.setenv("ADMZ_TEST_AUTH", "1")
        clean_caps.setenv("ADMZ_AUTH_INSECURE_BIND_OK", "true")
        with pytest.raises(SystemExit):
            self._check("0.0.0.0")
        assert "no override" in capsys.readouterr().err

    def test_the_api_server_runs_the_check(self, clean_caps, isolated_settings):
        """Wired in, not merely defined."""
        import inspect

        from admz import __main__ as main_module

        source = inspect.getsource(main_module.run_api_server)
        assert "_check_test_auth_bind(args.host)" in source


# ---------------------------------------------------------------------------
# Loudness — the registry's five surfaces, one by one
# ---------------------------------------------------------------------------


@pytest.fixture
def active(clean_caps, isolated_settings):
    """The capability on, with a clean environment around it."""
    clean_caps.setenv("ADMZ_TEST_AUTH", "1")
    assert capabilities.is_active(CAP_ID) is True
    return clean_caps


class TestLoudnessSurfaces:

    # 1 ── startup WARNING on admz.security
    def test_startup_emits_a_warning_naming_the_capability(self, active, caplog):
        with caplog.at_level(logging.INFO, logger="admz.security"):
            capabilities.log_startup_lines(logging.getLogger("admz.security"))
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert CAP_ID in warnings[0].message
        assert "dev-only" in warnings[0].message
        assert "not appropriate for a production installation" in warnings[0].message

    # 2 ── the capability.active boot-audit row
    def test_boot_audit_writes_a_row(self, active, tmp_path, monkeypatch):
        """An env-enabled capability has no enable-time actor, so "it was on at
        boot" attributed to ``system`` is the only honest audit answer."""
        from admz.audit import AuditLog

        monkeypatch.setattr(capabilities, "_BOOT_AUDIT_DONE", False)
        capabilities.record_boot_audit()

        rows = [
            r for r in AuditLog(db_path=str(tmp_path / "admz.db")).list_recent(limit=50)
            if r.resource == f"capability:{CAP_ID}"
        ]
        assert len(rows) == 1
        assert rows[0].action == "capability.active"
        assert rows[0].requester == "system"
        assert rows[0].details["danger"] == "dev-only"
        assert rows[0].details["source"] == "env"

    def test_it_is_boot_auditable(self):
        """dev-only is not the test-suppressor exemption."""
        cap = capabilities.get(CAP_ID)
        assert capabilities._boot_auditable(cap) is True

    # 3 ── the topbar chip
    def test_the_chip_appears_and_is_red(self, active):
        from admz.api.templating import _advanced_chip

        chip = _advanced_chip()
        assert chip is not None
        assert chip["severity"] == "red"
        assert CAP_ID in chip["ids"]

    def test_the_chip_is_absent_when_off(self, clean_caps, isolated_settings):
        from admz.api.templating import _advanced_chip

        assert _advanced_chip() is None

    # 4 ── /api/health
    def test_health_lists_the_id(self, active):
        from admz.api.main import _advanced_capability_ids

        assert CAP_ID in _advanced_capability_ids()

    def test_health_never_leaks_the_env_var_name(self, active):
        from admz.api.main import _advanced_capability_ids

        ids = _advanced_capability_ids()
        assert not any("ADMZ_" in i for i in ids)

    # 5 ── /settings/advanced
    def test_the_advanced_page_row_reports_it_active(self, active):
        from admz.api.routes.capabilities import _row

        row = _row(capabilities.get(CAP_ID))
        assert row["enabled"] is True
        assert row["source"] == "env"
        assert row["severity"] == "red"
        assert row["toggleable"] is False


# ---------------------------------------------------------------------------
# Through the app: the acceptance criteria
# ---------------------------------------------------------------------------


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    """An isolated ADMZ_HOME with ``windows-local`` + test auth active.

    ``windows-local`` is the deployment posture (ADR-0033/0035) and the reason
    the capability exists: a headless client cannot complete its handshake.
    """
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "windows-local")
    monkeypatch.delenv("ADMZ_REVEAL_GROUPS", raising=False)
    for cap in capabilities.CAPABILITIES:
        for companion in cap.companion_env:
            monkeypatch.delenv(companion, raising=False)

    from admz import fleet_settings as fs_module

    fresh = fs_module.FleetSettings(str(tmp_path / "admz.db"))
    monkeypatch.setattr(fs_module, "fleet_settings", fresh)
    return monkeypatch


def _client(*, test_auth: bool, app_env) -> TestClient:
    if test_auth:
        app_env.setenv("ADMZ_TEST_AUTH", "1")
    else:
        app_env.delenv("ADMZ_TEST_AUTH", raising=False)
    auth_module.set_active_backend(build_auth_backend())

    from admz.api.main import app

    return TestClient(app, follow_redirects=False, client=LOOPBACK)


@pytest.fixture
def restore_backend():
    yield
    auth_module.set_active_backend(NoAuth())


class TestAgentCanSelfAuthenticate:
    """The issue's acceptance criteria, at the HTTP boundary."""

    def test_without_it_an_agent_is_bounced_to_the_sign_in_page(
        self, app_env, restore_backend
    ):
        """The problem statement, asserted so the fix is not a coincidence."""
        with _client(test_auth=False, app_env=app_env) as c:
            r = c.get("/demos", headers={"accept": "text/html"})
        assert r.status_code == 303
        assert r.headers["location"].startswith("/login")

    def test_with_it_an_unauthenticated_agent_gets_the_demos_page(
        self, app_env, restore_backend
    ):
        with _client(test_auth=True, app_env=app_env) as c:
            r = c.get("/demos", headers={"accept": "text/html"})
        assert r.status_code == 200
        assert "Sign in" not in r.text

    def test_a_principal_requiring_endpoint_works(self, app_env, restore_backend):
        """``/api/capabilities`` is ``require_authenticated_principal`` — the
        exact class of surface that 403s under ADMZ_AUTH_BACKEND=none."""
        with _client(test_auth=True, app_env=app_env) as c:
            r = c.get("/api/capabilities")
        assert r.status_code == 200
        assert CAP_ID in r.json()["active"]

    def test_demo_crud_works(self, app_env, restore_backend):
        """Demo CRUD gates on ``_principal`` — a real identity or 403."""
        with _client(test_auth=True, app_env=app_env) as c:
            r = c.post("/api/demos", json={"name": "verification rig"})
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True

    def test_demo_crud_is_403_without_it(self, app_env, restore_backend):
        """Anonymous mode really is not a workaround (#140's premise)."""
        app_env.setenv("ADMZ_AUTH_BACKEND", "none")
        with _client(test_auth=False, app_env=app_env) as c:
            r = c.post("/api/demos", json={"name": "verification rig"})
        assert r.status_code == 403

    def test_whoami_reports_the_synthetic_identity(self, app_env, restore_backend):
        with _client(test_auth=True, app_env=app_env) as c:
            body = c.get("/api/whoami").json()
        assert body["name"] == TEST_AUTH_DEFAULT_NAME
        assert body["source"] == "test"
        assert body["is_anonymous"] is False

    def test_the_chip_renders_on_the_page(self, app_env, restore_backend):
        """Loudness surface 3, at the boundary rather than the helper."""
        with _client(test_auth=True, app_env=app_env) as c:
            html = c.get("/demos", headers={"accept": "text/html"}).text
        assert "advanced-capability-chip" in html

    def test_health_reports_it_unauthenticated(self, app_env, restore_backend):
        """Loudness surface 4, at the boundary."""
        with _client(test_auth=True, app_env=app_env) as c:
            body = c.get("/api/health").json()
        assert CAP_ID in body["advanced_capabilities"]

    def test_the_advanced_page_is_reveal_gated_from_the_test_principal(
        self, app_env, restore_backend
    ):
        """The unprivileged default is refused by the reveal gate, even here.

        /settings/advanced is reveal-gated, so the no-groups default cannot
        read it. That is correct — and worth pinning, because it means the
        loudness surface below is only observable when membership has been
        granted deliberately.
        """
        with _client(test_auth=True, app_env=app_env) as c:
            r = c.get("/settings/advanced")
        assert r.status_code == 403
        assert "no-groups" in r.text

    def test_the_advanced_page_lists_it_as_active(self, app_env, restore_backend):
        """Loudness surface 5, at the boundary — with reveal granted explicitly.

        Exercising this surface needs membership, which is exactly what
        ADMZ_TEST_AUTH_GROUPS is for. Granting it here (rather than defaulting
        it on) keeps the privilege visible at the point of use.
        """
        app_env.setenv("ADMZ_TEST_AUTH_GROUPS", "Administrators")
        with _client(test_auth=True, app_env=app_env) as c:
            html = c.get("/settings/advanced").text
        assert CAP_ID in html

    def test_an_off_box_caller_is_still_refused(self, app_env, restore_backend):
        """The per-request half of the guard, through the middleware."""
        app_env.setenv("ADMZ_TEST_AUTH", "1")
        auth_module.set_active_backend(build_auth_backend())
        from admz.api.main import app

        with TestClient(
            app, follow_redirects=False, client=("203.0.113.9", 40000)
        ) as c:
            r = c.get("/api/capabilities")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# The gate still gates — test 18, for this capability
# ---------------------------------------------------------------------------


class TestConfirmationGateStillHolds:
    """ADR-0034 removed flat refusals: every destructive action routes through
    the link/widget gate. ``dev.test_auth`` changes *who the principal is*; it
    must never change *whether approval is required*. Mirrors test 18 of #132.
    """

    def test_url_only_still_blocks(self, app_env, restore_backend, monkeypatch):
        from admz import operations

        monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_only")
        with _client(test_auth=True, app_env=app_env) as c:
            assert capabilities.is_active(CAP_ID) is True
            r = c.post(
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
        assert body["confirm_token"]

    def test_the_hardest_gate_is_also_unchanged(
        self, app_env, restore_backend, monkeypatch
    ):
        from admz import operations

        monkeypatch.setattr(
            operations, "resolve_confirmation", lambda r: "url_and_password"
        )
        with _client(test_auth=True, app_env=app_env) as c:
            body = c.post(
                "/api/catalog/execute",
                json={
                    "device_id": "dev",
                    "operation_id": "factorydefault.cgi:reset",
                    "params": {},
                },
            ).json()

        assert body["blocked"] is True
        assert body["confirmation_level"] == "url_and_password"

    def test_the_capability_declares_nothing_about_approval(self):
        """A structural reading: the row is about identity, not gate levels."""
        cap = capabilities.get(CAP_ID)
        assert cap.setting_key == ""
        assert "confirm" not in cap.env_var.lower()
