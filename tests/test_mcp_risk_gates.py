"""Per-risk confirmation gate in MCP _execute_operation.

Bug found in live testing: user said "lets reboot the D4200",
chatbot called execute_operation, and the device rebooted with no
confirmation. The reboot op is risk_level=service-affecting, which
the spec (ADR-0006) says must be gated — but the implementation only
blocked 'dangerous' ops.

These tests verify the gate now reads the *configured*
confirmation level for the op's risk class and blocks accordingly.
Covers:

  - read-only / normal pass through (default 'none')
  - service-affecting blocks (default 'url_only' — deterministic widget)
  - dangerous blocks (default 'url_and_password')
  - operator overrides via fleet settings change the gate
  - confirm_dangerous_operation refuses URL-flow tokens
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def isolate_db(tmp_path, monkeypatch):
    """Each test gets fresh ADMZ DB + fleet_settings + confirm_store."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from admz import fleet_settings as fs_module
    from admz.api import confirm_store as cs_module

    db_path = str(tmp_path / "admz.db")
    orig_fs = fs_module.fleet_settings
    orig_cs = cs_module.confirm_store

    fs_module.fleet_settings = fs_module.FleetSettings(db_path)
    cs_module.confirm_store = cs_module.ConfirmStore(db_path)

    try:
        yield
    finally:
        fs_module.fleet_settings = orig_fs
        cs_module.confirm_store = orig_cs


def _make_server(catalog_risk: str = "service-affecting"):
    """Build a minimal MCP server with the catalog mocked to return
    a specific risk_level for any operation.

    Most fields are mocks — the only thing we actually exercise is
    _execute_operation's gating logic and _confirm_dangerous's
    rejection of URL-flow tokens.
    """
    from admz.mcp.server import ADMZMCPServer

    server = ADMZMCPServer.__new__(ADMZMCPServer)
    server.catalog = MagicMock()
    server.catalog.get_risk_level.return_value = catalog_risk

    op = MagicMock()
    op.danger_description = ""
    op.service_impact = ""
    op.to_executor_dict.return_value = {"id": "test:op"}
    server.catalog.get_operation.return_value = op

    server.registry = MagicMock()
    server.registry.device_exists.return_value = True
    server.registry.get_device_info.return_value = {"host": "192.0.2.1"}
    server.registry.get_credentials.return_value = {
        "username": "root", "password": "secret"
    }

    executor = MagicMock()
    fake_result = MagicMock()
    fake_result.success = True
    fake_result.operation_id = "test:op"
    fake_result.device_id = "test-dev"
    fake_result.status_code = 200
    fake_result.duration_ms = 5.0
    fake_result.parsed_data = {"ok": True}
    fake_result.warnings = []
    fake_result.error = None
    executor.execute = AsyncMock(return_value=fake_result)
    server.executors = {"vapix": executor}

    return server, executor


# ---------------------------------------------------------------------------
# Pass-through risk levels (none configured)
# ---------------------------------------------------------------------------


class TestReadOnlyPassesThrough:
    @pytest.mark.asyncio
    async def test_read_only_runs_inline(self, isolate_db):
        server, executor = _make_server(catalog_risk="read-only")
        result = await server._execute_operation(
            device_id="test-dev",
            operation_id="test:op",
            params={},
            family="vapix",
        )
        assert result["success"] is True
        assert "blocked" not in result
        executor.execute.assert_awaited_once()


class TestNormalPassesThrough:
    @pytest.mark.asyncio
    async def test_normal_runs_inline(self, isolate_db):
        server, executor = _make_server(catalog_risk="normal")
        result = await server._execute_operation(
            device_id="test-dev",
            operation_id="test:op",
            params={},
            family="vapix",
        )
        assert result["success"] is True
        assert "blocked" not in result
        executor.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# Service-affecting blocks (the bug case)
# ---------------------------------------------------------------------------


class TestServiceAffectingBlocks:
    @pytest.mark.asyncio
    async def test_service_affecting_returns_blocked(self, isolate_db):
        server, executor = _make_server(catalog_risk="service-affecting")
        result = await server._execute_operation(
            device_id="test-dev",
            operation_id="test:op",
            params={},
            family="vapix",
        )
        assert result["blocked"] is True
        assert result["risk_level"] == "service-affecting"
        assert result["confirmation_level"] == "url_only"  # default
        assert "confirm_token" in result
        assert result["confirm_url"] == f"/confirm/{result['confirm_token']}"
        # The executor MUST NOT have been called.
        executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_service_affecting_with_none_override_runs_inline(self, isolate_db):
        """Operator can downgrade the gate via fleet settings."""
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_level_service-affecting", "none")

        server, executor = _make_server(catalog_risk="service-affecting")
        result = await server._execute_operation(
            device_id="test-dev",
            operation_id="test:op",
            params={},
            family="vapix",
        )
        assert result["success"] is True
        assert "blocked" not in result
        executor.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# Dangerous blocks (unchanged from before)
# ---------------------------------------------------------------------------


class TestDangerousBlocks:
    @pytest.mark.asyncio
    async def test_dangerous_default_is_url_and_password(self, isolate_db):
        server, executor = _make_server(catalog_risk="dangerous")
        result = await server._execute_operation(
            device_id="test-dev",
            operation_id="test:op",
            params={},
            family="vapix",
        )
        assert result["blocked"] is True
        assert result["risk_level"] == "dangerous"
        assert result["confirmation_level"] == "url_and_password"
        # Default message should direct user to the URL flow.
        assert "web UI" in result["message"]
        executor.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Fleet-setting overrides escalate too
# ---------------------------------------------------------------------------


class TestOperatorEscalation:
    @pytest.mark.asyncio
    async def test_normal_can_be_escalated_to_llm_confirm(self, isolate_db):
        """An anxious operator can require LLM-confirmation even on
        normal-risk ops."""
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_level_normal", "llm_confirm")

        server, executor = _make_server(catalog_risk="normal")
        result = await server._execute_operation(
            device_id="test-dev",
            operation_id="test:op",
            params={},
            family="vapix",
        )
        assert result["blocked"] is True
        assert result["confirmation_level"] == "llm_confirm"
        executor.execute.assert_not_called()


# ---------------------------------------------------------------------------
# _confirm_dangerous behavior
# ---------------------------------------------------------------------------


class TestConfirmTool:
    @pytest.mark.asyncio
    async def test_llm_confirm_token_consumed_inline(self, isolate_db):
        """The MCP confirm tool happily completes llm_confirm tokens.

        service-affecting now defaults to url_only (which the confirm tool
        refuses), so opt this risk class into llm_confirm explicitly to mint a
        token the MCP confirm tool may consume.
        """
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_level_service-affecting", "llm_confirm")

        server, executor = _make_server(catalog_risk="service-affecting")
        block = await server._execute_operation(
            device_id="test-dev",
            operation_id="test:op",
            params={},
            family="vapix",
        )
        token = block["confirm_token"]

        result = await server._confirm_dangerous(token)
        assert result["success"] is True
        assert result["confirmed"] is True
        # Backward-compat field still present.
        assert result.get("confirmed_dangerous") is True
        assert result["risk_level"] == "service-affecting"
        executor.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_url_and_password_token_refused_by_mcp(self, isolate_db):
        """Tokens that require a URL flow must NOT be silently
        approved by the MCP confirm tool — MCP can't supply a
        password."""
        server, executor = _make_server(catalog_risk="dangerous")
        block = await server._execute_operation(
            device_id="test-dev",
            operation_id="test:op",
            params={},
            family="vapix",
        )
        token = block["confirm_token"]

        result = await server._confirm_dangerous(token)
        assert result["success"] is False
        assert "web UI" in result["error"]
        assert result["confirmation_level"] == "url_and_password"
        assert result["confirm_url"] == f"/confirm/{token}"
        # And — critically — the operation was NOT executed.
        executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_url_only_token_also_refused_by_mcp(self, isolate_db):
        """url_only tokens are the same story — must go through the
        web form."""
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_level_service-affecting", "url_only")

        server, executor = _make_server(catalog_risk="service-affecting")
        block = await server._execute_operation(
            device_id="test-dev",
            operation_id="test:op",
            params={},
            family="vapix",
        )
        token = block["confirm_token"]

        result = await server._confirm_dangerous(token)
        assert result["success"] is False
        assert result["confirmation_level"] == "url_only"
        executor.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Reason hints — surface the right description for each risk
# ---------------------------------------------------------------------------


class TestUnknownOperationGuidesToCatalog:
    """When execute_operation is called with a non-existent operation_id,
    the error response must actively guide the LLM to query_catalog
    rather than just saying 'not found'."""

    @pytest.mark.asyncio
    async def test_unknown_op_response_mentions_query_catalog(self, isolate_db):
        from admz.mcp.server import ADMZMCPServer

        server = ADMZMCPServer.__new__(ADMZMCPServer)
        server.catalog = MagicMock()
        server.catalog.get_risk_level.return_value = "normal"
        # Return None — pretend the operation doesn't exist in catalog
        server.catalog.get_operation.return_value = None

        server.registry = MagicMock()
        server.registry.device_exists.return_value = True
        server.executors = {"vapix": MagicMock()}

        result = await server._execute_operation(
            device_id="cam-01",
            operation_id="system.cgi:restart",  # fake op
            params={},
            family="vapix",
        )
        assert result["success"] is False
        assert "query_catalog" in result["error"]
        assert "do not guess" in result["error"].lower()
        assert result["next_step"] == "query_catalog"
        assert result["operation_id_attempted"] == "system.cgi:restart"

    @pytest.mark.asyncio
    async def test_unknown_op_passes_device_id_for_lookup(self, isolate_db):
        from admz.mcp.server import ADMZMCPServer

        server = ADMZMCPServer.__new__(ADMZMCPServer)
        server.catalog = MagicMock()
        server.catalog.get_risk_level.return_value = "normal"
        server.catalog.get_operation.return_value = None
        server.registry = MagicMock()
        server.registry.device_exists.return_value = True
        server.executors = {"vapix": MagicMock()}

        result = await server._execute_operation(
            device_id="cam-99",
            operation_id="fake.cgi:nope",
            params={},
            family="vapix",
        )
        # The helpful error should include the device_id so the LLM
        # can plug it straight into query_catalog.
        assert "cam-99" in result["error"]


class TestExecuteOperationSchema:
    """Regression: 'params' must NOT be marked required.

    Found in live testing: LLM tried restart.cgi:restart (which
    takes no params), the SDK rejected the call with "the 'params'
    property is required" before our code even ran, and the LLM
    then guessed a non-existent operation id. The schema lists
    params with a default of {} so the LLM can omit it.
    """

    @pytest.mark.asyncio
    async def test_params_not_required(self, tmp_path, monkeypatch):
        # Inspect the REAL emitted tool schema. (A prior version scanned a
        # fixed-width window of the source and broke when the params schema
        # grew — inspect the actual inputSchema instead.)
        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
        monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
        monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")

        from admz.mcp.server import ADMZMCPServer
        from mcp.types import ListToolsRequest

        server = ADMZMCPServer()
        handler = server.server.request_handlers.get(ListToolsRequest)
        result = await handler(ListToolsRequest(method="tools/list"))
        tool = next(t for t in result.root.tools if t.name == "execute_operation")

        required = tool.inputSchema.get("required", [])
        assert "params" not in required, (
            "execute_operation should not require 'params' — many ops take "
            f"no params. required={required}"
        )
        assert "device_id" in required
        assert "operation_id" in required


class TestReasonText:
    @pytest.mark.asyncio
    async def test_dangerous_uses_danger_description(self, isolate_db):
        from admz.mcp.server import ADMZMCPServer

        server = ADMZMCPServer.__new__(ADMZMCPServer)
        server.catalog = MagicMock()
        server.catalog.get_risk_level.return_value = "dangerous"
        op = MagicMock()
        op.danger_description = "This will wipe all settings."
        op.service_impact = "should be ignored"
        server.catalog.get_operation.return_value = op

        result = await server._execute_operation(
            device_id="d",
            operation_id="o",
            params={},
            family="vapix",
        )
        assert "wipe all settings" in result["reason"]

    @pytest.mark.asyncio
    async def test_service_affecting_uses_service_impact(self, isolate_db):
        from admz.mcp.server import ADMZMCPServer

        server = ADMZMCPServer.__new__(ADMZMCPServer)
        server.catalog = MagicMock()
        server.catalog.get_risk_level.return_value = "service-affecting"
        op = MagicMock()
        op.danger_description = None  # No danger_description on service-affecting ops
        op.service_impact = "Streams restart briefly."
        server.catalog.get_operation.return_value = op

        result = await server._execute_operation(
            device_id="d",
            operation_id="o",
            params={},
            family="vapix",
        )
        assert "Streams restart" in result["reason"]
