"""Smoke tests for the FastAPI routes — verify they mount and respond."""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolate_admz_dirs(tmp_path, monkeypatch):
    """Point ADMZ env vars at a temp dir so tests don't touch real state."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    # Schedule path — os.path.expanduser("~") uses HOME on Unix and USERPROFILE on Windows
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


@pytest.fixture
def client(isolate_admz_dirs, tmp_path):
    """Build a TestClient with a fresh app. Configure git for the temp repo."""
    # Need to import here so env vars take effect
    from admz.api.main import app

    with TestClient(app) as c:
        # Configure git for the test config repo
        import subprocess
        repo_path = str(tmp_path / "config-repo")
        for key, val in [
            ("user.email", "test@test.com"),
            ("user.name", "Test"),
            ("commit.gpgsign", "false"),
        ]:
            subprocess.run(
                ["git", "config", key, val],
                cwd=repo_path, check=True,
            )
        yield c


class TestHealth:

    def test_health(self, client):
        """Liveness probe: 200 if the process is up."""
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert body["service"] == "admz"
        assert "version" in body

    def test_api_health_when_registry_works(self, client):
        """Readiness probe: 200 + 'connected' when registry.list_devices() succeeds."""
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert body["registry"] == "connected"

    def test_api_health_when_registry_broken(self, client, monkeypatch):
        """Readiness probe: 503 + error detail when registry.list_devices() raises."""
        import admz.api.main as main_mod

        class _BrokenRegistry:
            def list_devices(self):
                raise RuntimeError("simulated backend failure")

        monkeypatch.setattr(main_mod, "registry", _BrokenRegistry())
        r = client.get("/api/health")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "unhealthy"
        assert body["registry"] == "error"
        assert "simulated backend failure" in body["error"]


class TestDevices:

    def test_list_devices_empty(self, client):
        r = client.get("/api/devices")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_and_list_device(self, client):
        r = client.post(
            "/api/devices",
            json={
                "device_id": "cam-01",
                "host": "192.168.1.100",
                "model": "AXIS P3245-V",
                "location": "Lobby",
            },
        )
        assert r.status_code in (200, 201)

        r = client.get("/api/devices")
        devices = r.json()
        assert len(devices) == 1
        assert devices[0]["device_id"] == "cam-01"

    def test_update_device_preserves_other_fields(self, client):
        client.post(
            "/api/devices",
            json={
                "device_id": "cam-01",
                "host": "192.168.1.100",
                "model": "AXIS P3245-V",
                "location": "Lobby",
            },
        )
        r = client.put(
            "/api/devices/cam-01",
            json={"location": "Conference Room"},
        )
        assert r.status_code == 200
        # model should still be there
        r = client.get("/api/devices/cam-01")
        device = r.json()
        assert device["location"] == "Conference Room"
        assert device["model"] == "AXIS P3245-V"


@pytest.fixture
def as_console_operator(monkeypatch):
    """Task/schedule writes gate for non-interactive principals; these
    legacy tests exercise the direct (console-operator) path. The gate is
    covered in tests/test_tasks_routes.py::TestTaskWriteGate."""
    import admz.tasks.gated as gated
    monkeypatch.setattr(gated, "is_interactive", lambda p: True)


@pytest.mark.usefixtures("as_console_operator")
class TestSchedules:

    def test_list_schedules_fresh_install_has_only_the_seed(self, client):
        r = client.get("/api/schedules")
        assert r.status_code == 200
        # Not empty: ADR-0063 S2 seeds the 30-day capability-survey cadence.
        assert r.json()["count"] == 1
        assert r.json()["schedules"][0]["id"] == "capability-survey"

    def test_create_schedule(self, client):
        r = client.post(
            "/api/schedules",
            json={
                "schedule_id": "nightly",
                "description": "Nightly backup",
                "interval": "1d",
                "tag_filter": "lobby",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "nightly"
        assert body["interval_seconds"] == 86400

    def test_create_schedule_invalid_interval(self, client):
        r = client.post(
            "/api/schedules",
            json={
                "schedule_id": "bad",
                "description": "Bad",
                "interval": "never",
            },
        )
        assert r.status_code == 400

    def test_update_schedule(self, client):
        client.post(
            "/api/schedules",
            json={
                "schedule_id": "s1",
                "description": "S1",
                "interval": "1h",
            },
        )
        r = client.patch(
            "/api/schedules/s1",
            json={"interval": "30m", "enabled": False},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["interval_seconds"] == 1800
        assert body["enabled"] is False

    def test_delete_schedule(self, client):
        client.post(
            "/api/schedules",
            json={
                "schedule_id": "s1",
                "description": "S1",
                "interval": "1h",
            },
        )
        r = client.delete("/api/schedules/s1")
        assert r.status_code == 200
        r = client.get("/api/schedules")
        # Only the seeded capability-survey cadence remains (ADR-0063 S2).
        remaining = [s["id"] for s in r.json()["schedules"]]
        assert remaining == ["capability-survey"]


class TestCatalog:

    def test_query_catalog(self, client):
        # Register a device first so query has someone to ask about
        client.post(
            "/api/devices",
            json={
                "device_id": "cam-01",
                "host": "192.168.1.100",
                "model": "AXIS P3245-V",
            },
        )
        r = client.post(
            "/api/catalog/query",
            json={
                "device_id": "cam-01",
                "intent": "change resolution",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert "operations" in body
        assert "parameter_groups" in body

    def test_query_catalog_unknown_device_still_works(self, client):
        """The resolver should still return catalog info even if device isn't registered."""
        r = client.post(
            "/api/catalog/query",
            json={
                "device_id": "unknown",
                "intent": "list parameters",
            },
        )
        assert r.status_code == 200


class TestPlans:

    def test_create_plan(self, client):
        # Need a device
        client.post(
            "/api/devices",
            json={"device_id": "cam-01", "host": "192.168.1.100"},
        )
        r = client.post(
            "/api/plans",
            json={
                "description": "Test plan",
                "steps": [{
                    "operation_id": "param.cgi:list",
                    "device_id": "cam-01",
                    "params": {"group": "root.Image"},
                }],
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["step_count"] == 1
        assert "plan_id" in body

    def test_get_plan_status(self, client):
        client.post(
            "/api/devices",
            json={"device_id": "cam-01", "host": "192.168.1.100"},
        )
        r = client.post(
            "/api/plans",
            json={
                "description": "Test",
                "steps": [{
                    "operation_id": "param.cgi:list",
                    "device_id": "cam-01",
                    "params": {},
                }],
            },
        )
        plan_id = r.json()["plan_id"]
        r = client.get(f"/api/plans/{plan_id}")
        assert r.status_code == 200

    def test_get_plan_status_404(self, client):
        r = client.get("/api/plans/does-not-exist")
        assert r.status_code == 404


class TestSnapshot:

    def test_snapshot_device_404(self, client):
        r = client.post(
            "/api/snapshot/device",
            json={"device_id": "nonexistent"},
        )
        assert r.status_code == 404

    def test_drift_404_for_unknown_device(self, client):
        r = client.get("/api/snapshot/drift?device_id=nonexistent")
        assert r.status_code == 404


class TestDiscovery:

    def test_register_discovered(self, client):
        r = client.post(
            "/api/discovery/register",
            json={
                "device_id": "newcam-01",
                "ip_address": "192.168.1.250",
                "model": "AXIS P3245-V",
                "hostname": "lobby-discovered",
                "device_type": "camera",
                "tags": ["discovered", "indoor"],
            },
        )
        assert r.status_code == 200
        # Verify it appears in the registry
        r = client.get("/api/devices/newcam-01")
        assert r.status_code == 200
        device = r.json()
        assert device["model"] == "AXIS P3245-V"


class TestRoutesAreMounted:
    """Verify every expected route path exists."""

    def test_expected_routes(self, client):
        from admz.api.main import app
        from tests.route_inventory import mounted_paths
        paths = mounted_paths(app)
        assert paths, "route table introspection returned nothing"
        expected = {
            # Devices
            "/api/devices",
            "/api/devices/{device_id}",
            "/api/devices/{device_id}/accounts",
            "/api/devices/{device_id}/accounts/{account_id}",
            # Catalog
            "/api/catalog/query",
            "/api/catalog/execute",
            "/api/catalog/confirm",
            # Plans
            "/api/plans",
            "/api/plans/{plan_id}",
            "/api/plans/{plan_id}/execute",
            # Snapshot
            "/api/snapshot/device",
            "/api/snapshot/fleet",
            "/api/snapshot/restore",
            "/api/snapshot/diff/{device_id}",
            "/api/snapshot/drift",
            # Discovery
            "/api/discovery/scan",
            "/api/discovery/register",
            # Schedules
            "/api/schedules",
            "/api/schedules/{schedule_id}",
            "/api/schedules/{schedule_id}/run",
            # Capture
            "/api/capture",
            "/api/capture/{token}/status",
            "/capture/{token}",
            # Health
            "/health",
            "/api/health",
        }
        missing = expected - paths
        assert not missing, f"Missing routes: {missing}"


class TestFleetSettingsMasking:
    """Phase 2A: passwords in fleet settings must be masked on the REST surface,
    matching the MCP get_fleet_settings tool."""

    def _set_setting(self, client, key, value):
        # Use the underlying fleet_settings singleton directly, since
        # /api/fleet/settings only exposes GET endpoints here.
        from admz.fleet_settings import fleet_settings as fs
        fs.set(key, value)

    def test_password_value_is_masked_in_list(self, client):
        self._set_setting(client, "default_password", "supersecret123")
        self._set_setting(client, "default_username", "admin")
        r = client.get("/api/fleet/settings")
        assert r.status_code == 200
        body = r.json()
        assert "supersecret123" not in str(body)
        assert body["default_password"].startswith("*")
        assert "(14 chars)" in body["default_password"]
        # Non-password key still readable
        assert body["default_username"] == "admin"

    def test_password_value_is_masked_in_single_get(self, client):
        self._set_setting(client, "default_password", "rotated99")
        r = client.get("/api/fleet/settings/default_password")
        assert r.status_code == 200
        assert "rotated99" not in r.json()["value"]
        assert r.json()["value"].startswith("*")

    def test_non_password_value_passes_through_in_single_get(self, client):
        self._set_setting(client, "default_username", "operator")
        r = client.get("/api/fleet/settings/default_username")
        assert r.status_code == 200
        assert r.json()["value"] == "operator"

    # -- #158: /fleet-settings (the HTML page) used its own hand-rolled
    # "password" in key.lower() test instead of is_sensitive_setting_key, so
    # a sensitive key not literally named "password" — gemini_api_key,
    # acs_webhook_token — rendered in plaintext directly in the HTML with no
    # gate at all (worse than the JSON siblings above, which were already
    # correct: they call mask_settings_for_display / is_sensitive_setting_key).

    def test_html_page_masks_non_password_sensitive_keys(self, client):
        self._set_setting(client, "gemini_api_key", "AIzaSyLIVE_KEY_MATERIAL")
        self._set_setting(client, "acs_webhook_token", "webhook-secret-value")
        r = client.get("/fleet-settings")
        assert r.status_code == 200
        assert "AIzaSyLIVE_KEY_MATERIAL" not in r.text
        assert "webhook-secret-value" not in r.text

    def test_html_page_still_masks_password_keys(self, client):
        """The pre-existing behavior for literally-named password keys
        must survive the predicate swap."""
        self._set_setting(client, "default_password", "supersecret123")
        r = client.get("/fleet-settings")
        assert r.status_code == 200
        assert "supersecret123" not in r.text

    def test_html_page_still_shows_non_sensitive_values(self, client):
        self._set_setting(client, "default_username", "operator")
        r = client.get("/fleet-settings")
        assert r.status_code == 200
        assert "operator" in r.text


class TestCredentialsEndpointRemoved:
    """The device-credential reveal endpoint (GET
    /api/devices/{id}/credentials) was removed: device-account passwords
    are never displayed through any web/REST surface. ADMZ reads them from
    the secrets backend only at execution time; the LLM path
    (`get_credentials` MCP tool) and `create_temp_credentials` are
    separate and unaffected."""

    def _register_device_with_creds(self, client):
        client.post(
            "/api/devices",
            json={
                "device_id": "cam-01",
                "host": "192.168.1.10",
                "model": "AXIS P3245-V",
                "location": "Lobby",
            },
        )
        client.post(
            "/api/devices/cam-01/accounts",
            json={
                "account_id": "default",
                "username": "root",
                "password": "topsecret",
            },
        )

    def test_endpoint_is_not_mounted(self):
        # assert_not_mounted refuses to pass against an empty/blind route table.
        # Before #223 this was `{r.path for r in app.routes if hasattr(r, "path")}`,
        # which under FastAPI >= 0.130 saw almost nothing and made this negative
        # assertion vacuous. See tests/route_inventory.py.
        from admz.api.main import app
        from tests.route_inventory import assert_not_mounted
        assert_not_mounted(app, "/api/devices/{device_id}/credentials")

    def test_endpoint_returns_404(self, client):
        # The web/REST reveal of a device password does not exist — the
        # password never leaks here. (This test used to also flip the
        # tool_get_credentials_enabled flag; that flag was removed, #151.)
        self._register_device_with_creds(client)
        r = client.get("/api/devices/cam-01/credentials")
        assert r.status_code == 404
        assert "topsecret" not in r.text


class TestConfirmTokenUnification:
    """Phase 2E: tokens issued by either MCP or REST should live in the
    same SQLite ConfirmStore. This test verifies the REST surface uses
    the store and that ConfirmStore.complete_session is the single-use
    gate."""

    def test_rest_dangerous_op_creates_confirm_store_session(self, client):
        # Build a tiny ad-hoc dangerous operation by injecting a YAML
        # would be complex; instead we just verify the REST flow uses
        # the store by issuing a token via the store directly and then
        # consuming it via the REST /api/catalog/confirm endpoint.
        from admz.api.confirm_store import confirm_store
        # Create a fake device and seed the store with a session that
        # references an operation that doesn't exist — we just want to
        # prove the token is recognized and the *store* is the source
        # of truth.
        session = confirm_store.create_session(
            device_id="nonexistent",
            operation_id="not_a_real_op",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="llm_confirm",
        )
        # Consume via REST — even though the underlying op won't be
        # found, the token must be recognized (not 'invalid/expired'),
        # i.e. status should be 404 (op not in catalog) or 500, never
        # 400 (token lookup failure).
        r = client.post(
            "/api/catalog/confirm",
            json={"confirm_token": session.token},
        )
        assert r.status_code != 400, (
            "Token should have been recognized via the shared store"
        )

    def test_invalid_token_returns_400(self, client):
        r = client.post(
            "/api/catalog/confirm",
            json={"confirm_token": "not-a-real-token"},
        )
        assert r.status_code == 400
        assert "Invalid" in r.json()["detail"]

    def test_token_is_single_use(self, client):
        from admz.api.confirm_store import confirm_store
        session = confirm_store.create_session(
            device_id="nonexistent",
            operation_id="not_a_real_op",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="llm_confirm",
        )
        # First consumption marks completed (404 because op doesn't exist,
        # but the token was successfully consumed)
        r1 = client.post(
            "/api/catalog/confirm",
            json={"confirm_token": session.token},
        )
        # Second consumption finds the session COMPLETED, not PENDING
        r2 = client.post(
            "/api/catalog/confirm",
            json={"confirm_token": session.token},
        )
        assert r2.status_code == 400
        assert "Invalid" in r2.json()["detail"]


class TestRestExecuteGate:
    """The REST /catalog/execute now routes through the shared gated core, so
    it honors the per-risk confirmation policy exactly like MCP (was: a
    hardcoded dangerous-only check that ran service-affecting ops inline)."""

    def test_service_affecting_blocks_via_rest(self, client, monkeypatch):
        from admz import operations
        monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "llm_confirm")
        r = client.post(
            "/api/catalog/execute",
            json={"device_id": "dev", "operation_id": "restart.cgi:restart", "params": {}},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["blocked"] is True
        assert body["confirmation_level"] == "llm_confirm"
        assert body["confirm_url"].startswith("/confirm/")
        # Old REST-only field is gone; the unified shape is used.
        assert "confirm_endpoint" not in body

    def test_dangerous_returns_url_and_password(self, client, monkeypatch):
        from admz import operations
        monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "url_and_password")
        r = client.post(
            "/api/catalog/execute",
            json={"device_id": "dev", "operation_id": "factorydefault.cgi:reset", "params": {}},
        )
        body = r.json()
        assert body["blocked"] is True
        assert body["confirmation_level"] == "url_and_password"
        assert "/confirm/" in body["confirm_url"]

    def test_none_level_reaches_execution(self, client, monkeypatch):
        from admz import operations
        monkeypatch.setattr(operations, "resolve_confirmation", lambda r: "none")
        # A none-level op falls through to the execution tail; an unknown
        # device/op surfaces as 404 (proving it was NOT blocked).
        r = client.post(
            "/api/catalog/execute",
            json={"device_id": "ghost", "operation_id": "param.cgi:list", "params": {}},
        )
        assert r.status_code == 404
