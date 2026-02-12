"""Tests for the operations catalog: loader, resolver, and plan engine."""

import os
import pytest

from admz.catalog.loader import CatalogLoader
from admz.catalog.resolver import CatalogResolver
from admz.catalog.models import Operation, ParameterGroup

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "catalog")


@pytest.fixture
def loader():
    return CatalogLoader(CATALOG_PATH)


@pytest.fixture
def resolver(loader):
    return CatalogResolver(loader)


# ------------------------------------------------------------------
# CatalogLoader tests
# ------------------------------------------------------------------


class TestCatalogLoader:

    def test_load_cgi_metadata(self, loader):
        meta = loader.get_cgi_metadata("vapix", "param.cgi")
        assert meta is not None
        assert meta.endpoint == "/axis-cgi/param.cgi"
        assert meta.generation == "legacy-cgi"
        assert meta.auth == "digest"

    def test_load_cgi_metadata_json_rpc(self, loader):
        meta = loader.get_cgi_metadata("vapix", "basicdeviceinfo.cgi")
        assert meta is not None
        assert meta.generation == "json-rpc"
        assert meta.min_firmware == "6.50"
        assert meta.api_id == "basic-device-info"

    def test_load_cgi_metadata_missing(self, loader):
        meta = loader.get_cgi_metadata("vapix", "nonexistent.cgi")
        assert meta is None

    def test_load_operation_param_update(self, loader):
        op = loader.get_operation("vapix", "param.cgi:update")
        assert op is not None
        assert isinstance(op, Operation)
        assert op.id == "param.cgi:update"
        assert op.method == "GET"
        assert op.risk_level == "normal"
        assert op.endpoint == "/axis-cgi/param.cgi"
        assert op.generation == "legacy-cgi"
        assert op.rollback is not None
        assert op.rollback.strategy == "revert-params"

    def test_load_operation_param_list(self, loader):
        op = loader.get_operation("vapix", "param.cgi:list")
        assert op is not None
        assert op.risk_level == "read-only"

    def test_load_operation_json_rpc(self, loader):
        op = loader.get_operation("vapix", "basicdeviceinfo.cgi:getAllProperties")
        assert op is not None
        assert op.method == "POST"
        assert op.risk_level == "read-only"
        assert op.generation == "json-rpc"

    def test_load_operation_dangerous(self, loader):
        op = loader.get_operation("vapix", "factorydefault.cgi:factory-reset")
        assert op is not None
        assert op.risk_level == "dangerous"
        assert op.danger_description is not None
        assert "ERASES" in op.danger_description

    def test_load_operation_missing(self, loader):
        op = loader.get_operation("vapix", "nonexistent.cgi:nope")
        assert op is None

    def test_load_parameter_group(self, loader):
        pg = loader.get_parameter_group("vapix", "root.Image")
        assert pg is not None
        assert isinstance(pg, ParameterGroup)
        assert pg.group == "root.Image"
        assert pg.channel_indexed is True
        assert pg.channel_key == "I"
        assert "Resolution" in pg.parameters
        assert pg.parameters["Resolution"].type == "enum"

    def test_load_parameter_group_network(self, loader):
        pg = loader.get_parameter_group("vapix", "root.Network")
        assert pg is not None
        assert pg.channel_indexed is False
        assert "HostName" in pg.parameters

    def test_load_parameter_group_missing(self, loader):
        pg = loader.get_parameter_group("vapix", "root.DoesNotExist")
        assert pg is None

    def test_load_task_index(self, loader):
        index = loader.load_index("vapix", "by-task")
        assert len(index) > 0
        assert "change-resolution" in index
        assert "factory-reset" in index
        paths = index["change-resolution"]
        assert any("root.Image" in p for p in paths)

    def test_load_risk_index(self, loader):
        index = loader.load_index("vapix", "by-risk")
        assert "read-only" in index
        assert "dangerous" in index
        assert any("factorydefault" in p for p in index["dangerous"])

    def test_get_risk_level(self, loader):
        assert loader.get_risk_level("vapix", "param.cgi:list") == "read-only"
        assert loader.get_risk_level("vapix", "param.cgi:update") == "normal"
        assert loader.get_risk_level(
            "vapix", "factorydefault.cgi:factory-reset"
        ) == "dangerous"

    def test_cache_works(self, loader):
        # Load twice — second should come from cache
        op1 = loader.get_operation("vapix", "param.cgi:update")
        op2 = loader.get_operation("vapix", "param.cgi:update")
        assert op1 is op2  # same object from cache

    def test_clear_cache(self, loader):
        loader.get_operation("vapix", "param.cgi:update")
        assert len(loader._operation_cache) > 0
        loader.clear_cache()
        assert len(loader._operation_cache) == 0


# ------------------------------------------------------------------
# CatalogResolver tests
# ------------------------------------------------------------------


class TestCatalogResolver:

    def test_resolve_change_resolution(self, resolver):
        result = resolver.resolve("lobby-cam", "change resolution")
        assert len(result.operations) > 0
        assert len(result.parameter_groups) > 0
        # Should include param.cgi:update
        op_ids = [op.get("id") for op in result.operations]
        assert "param.cgi:update" in op_ids
        # Should include root.Image parameter group
        groups = [pg.get("group") for pg in result.parameter_groups]
        assert "root.Image" in groups

    def test_resolve_ntp(self, resolver):
        result = resolver.resolve("cam-01", "configure NTP")
        op_ids = [op.get("id") for op in result.operations]
        assert "param.cgi:update" in op_ids
        groups = [pg.get("group") for pg in result.parameter_groups]
        assert "root.Time" in groups

    def test_resolve_device_info(self, resolver):
        result = resolver.resolve("cam-01", "get device info")
        op_ids = [op.get("id") for op in result.operations]
        assert "basicdeviceinfo.cgi:getAllProperties" in op_ids

    def test_resolve_firmware(self, resolver):
        result = resolver.resolve("cam-01", "check firmware")
        op_ids = [op.get("id") for op in result.operations]
        assert "firmwaremanagement.cgi:status" in op_ids

    def test_resolve_factory_reset_warns(self, resolver):
        result = resolver.resolve("cam-01", "factory reset")
        assert len(result.notes) > 0
        assert any("dangerous" in n.lower() or "WARNING" in n for n in result.notes)
        assert result.risk_summary.get("dangerous", 0) > 0

    def test_resolve_unknown_intent(self, resolver):
        result = resolver.resolve("cam-01", "xyzzy foobar nonsense")
        assert len(result.operations) == 0
        assert len(result.notes) > 0

    def test_resolve_enriches_cgi_metadata(self, resolver):
        result = resolver.resolve("cam-01", "change resolution")
        for op in result.operations:
            if op.get("id") == "param.cgi:update":
                assert "_cgi" in op
                assert op["_cgi"]["endpoint"] == "/axis-cgi/param.cgi"
                assert op["_cgi"]["generation"] == "legacy-cgi"

    def test_resolve_user_management(self, resolver):
        result = resolver.resolve("cam-01", "add user")
        op_ids = [op.get("id") for op in result.operations]
        assert "pwdgrp.cgi:add-user" in op_ids

    def test_resolve_network(self, resolver):
        result = resolver.resolve("cam-01", "configure network")
        op_ids = [op.get("id") for op in result.operations]
        assert "param.cgi:update" in op_ids
        groups = [pg.get("group") for pg in result.parameter_groups]
        assert "root.Network" in groups

    def test_list_available_tasks(self, resolver):
        tasks = resolver.list_available_tasks()
        assert len(tasks) > 10
        assert "change-resolution" in tasks
        assert "factory-reset" in tasks
        assert "configure-ntp" in tasks


# ------------------------------------------------------------------
# Executor build_request tests
# ------------------------------------------------------------------


class TestVapixExecutorBuildRequest:

    def test_build_legacy_cgi_request(self):
        from admz.executor.vapix import VAPXExecutor

        executor = VAPXExecutor()
        operation = {
            "id": "param.cgi:update",
            "method": "GET",
            "_generation": "legacy-cgi",
            "_endpoint": "/axis-cgi/param.cgi",
            "request": {
                "query": {"action": "update"},
            },
        }
        params = {"root.Image.I0.Resolution": "1920x1080"}

        req = executor.build_request(operation, params)
        assert req.method == "GET"
        assert req.path == "/axis-cgi/param.cgi"
        assert req.query_params["action"] == "update"
        assert req.query_params["root.Image.I0.Resolution"] == "1920x1080"
        assert req.json_body is None

    def test_build_json_rpc_request(self):
        from admz.executor.vapix import VAPXExecutor

        executor = VAPXExecutor()
        operation = {
            "id": "basicdeviceinfo.cgi:getAllProperties",
            "method": "POST",
            "_generation": "json-rpc",
            "_endpoint": "/axis-cgi/basicdeviceinfo.cgi",
            "request": {
                "body": {
                    "apiVersion": "1.0",
                    "method": "getAllProperties",
                },
            },
        }

        req = executor.build_request(operation, {})
        assert req.method == "POST"
        assert req.path == "/axis-cgi/basicdeviceinfo.cgi"
        assert req.json_body["apiVersion"] == "1.0"
        assert req.json_body["method"] == "getAllProperties"
        assert req.content_type == "application/json"

    def test_build_json_rpc_with_params(self):
        from admz.executor.vapix import VAPXExecutor

        executor = VAPXExecutor()
        operation = {
            "id": "some.cgi:doThing",
            "method": "POST",
            "_generation": "json-rpc",
            "_endpoint": "/axis-cgi/some.cgi",
            "request": {
                "body": {
                    "apiVersion": "1.0",
                    "method": "doThing",
                },
            },
        }

        req = executor.build_request(operation, {"key": "value"})
        assert req.json_body["params"] == {"key": "value"}

    def test_build_config_rest_request(self):
        from admz.executor.vapix import VAPXExecutor

        executor = VAPXExecutor()
        operation = {
            "id": "config-rest:ssh:v2:create-user",
            "method": "POST",
            "_generation": "config-rest",
            "base_path": "/config/rest/ssh/v2",
            "path": "/users",
        }

        req = executor.build_request(
            operation, {"username": "test", "sshKey": "ssh-rsa AAAA..."}
        )
        assert req.method == "POST"
        assert req.path == "/config/rest/ssh/v2/users"
        assert req.json_body["username"] == "test"

    def test_build_legacy_cgi_list(self):
        from admz.executor.vapix import VAPXExecutor

        executor = VAPXExecutor()
        operation = {
            "id": "param.cgi:list",
            "method": "GET",
            "_generation": "legacy-cgi",
            "_endpoint": "/axis-cgi/param.cgi",
            "request": {
                "query": {"action": "list", "group": "{group}"},
            },
        }
        params = {"group": "Image"}

        req = executor.build_request(operation, params)
        assert req.query_params["action"] == "list"
        assert req.query_params["group"] == "Image"


# ------------------------------------------------------------------
# Plan engine tests (in-memory, no real HTTP)
# ------------------------------------------------------------------


class TestPlanEngine:

    @pytest.fixture
    def mock_registry(self):
        """A minimal mock registry for plan validation."""

        class MockRegistry:
            def device_exists(self, device_id):
                return device_id in ("cam-01", "cam-02", "cam-03")

            def get_device_info(self, device_id):
                return {
                    "host": f"192.168.1.{hash(device_id) % 254 + 1}",
                    "model": "P1455-LE",
                }

            def get_credentials(self, device_id, account_id="default",
                                requester=None):
                return {"username": "root", "password": "pass"}

            def list_devices(self):
                return []

            def list_accounts(self, device_id):
                return []

        return MockRegistry()

    @pytest.fixture
    def engine(self, mock_registry):
        from admz.plans.engine import PlanEngine
        from admz.executor.vapix import VAPXExecutor

        loader = CatalogLoader(CATALOG_PATH)
        executor = VAPXExecutor()
        return PlanEngine(
            catalog=loader,
            registry=mock_registry,
            executors={"vapix": executor},
        )

    def test_create_valid_plan(self, engine):
        plan = engine.create_plan(
            description="Set resolution on cam-01",
            steps=[
                {
                    "operation_id": "param.cgi:update",
                    "device_id": "cam-01",
                    "params": {"root.Image.I0.Resolution": "1920x1080"},
                    "description": "Set resolution to 1080p",
                },
            ],
        )
        assert plan.plan_id.startswith("plan-")
        assert plan.status.value == "pending_approval"
        assert len(plan.steps) == 1
        assert plan.risk_summary.get("normal", 0) == 1

    def test_create_multi_step_plan(self, engine):
        plan = engine.create_plan(
            description="Configure cam-01",
            steps=[
                {
                    "operation_id": "param.cgi:update",
                    "device_id": "cam-01",
                    "params": {"root.Image.I0.Resolution": "1920x1080"},
                    "description": "Set resolution",
                },
                {
                    "operation_id": "param.cgi:update",
                    "device_id": "cam-01",
                    "params": {"root.Time.NTPServer": "pool.ntp.org"},
                    "description": "Set NTP",
                },
                {
                    "operation_id": "param.cgi:list",
                    "device_id": "cam-01",
                    "params": {"group": "Image"},
                    "description": "Verify resolution",
                },
            ],
        )
        assert len(plan.steps) == 3
        assert plan.risk_summary["normal"] == 2
        assert plan.risk_summary["read-only"] == 1

    def test_create_plan_invalid_operation(self, engine):
        with pytest.raises(ValueError, match="not found"):
            engine.create_plan(
                description="Bad plan",
                steps=[
                    {
                        "operation_id": "nonexistent.cgi:nope",
                        "device_id": "cam-01",
                        "params": {},
                    },
                ],
            )

    def test_create_plan_invalid_device(self, engine):
        with pytest.raises(ValueError, match="not found in registry"):
            engine.create_plan(
                description="Bad plan",
                steps=[
                    {
                        "operation_id": "param.cgi:update",
                        "device_id": "nonexistent-device",
                        "params": {},
                    },
                ],
            )

    def test_create_plan_invalid_dependency(self, engine):
        with pytest.raises(ValueError, match="invalid dependency"):
            engine.create_plan(
                description="Bad deps",
                steps=[
                    {
                        "operation_id": "param.cgi:update",
                        "device_id": "cam-01",
                        "params": {},
                        "depends_on": [5],
                    },
                ],
            )

    def test_plan_summary(self, engine):
        plan = engine.create_plan(
            description="Test plan",
            steps=[
                {
                    "operation_id": "param.cgi:update",
                    "device_id": "cam-01",
                    "params": {"root.Image.I0.Resolution": "1920x1080"},
                    "description": "Set resolution",
                },
            ],
        )
        summary = plan.to_summary()
        assert summary["plan_id"] == plan.plan_id
        assert summary["step_count"] == 1
        assert summary["status"] == "pending_approval"
        assert len(summary["steps"]) == 1
        assert summary["steps"][0]["operation"] == "param.cgi:update"

    def test_plan_with_dangerous_operation(self, engine):
        plan = engine.create_plan(
            description="Reset cam-01",
            steps=[
                {
                    "operation_id": "factorydefault.cgi:factory-reset",
                    "device_id": "cam-01",
                    "params": {},
                    "description": "Factory reset",
                },
            ],
        )
        assert plan.risk_summary.get("dangerous", 0) == 1
        summary = plan.to_summary()
        assert len(summary["dangerous_steps"]) == 1

    def test_get_plan(self, engine):
        plan = engine.create_plan(
            description="Test",
            steps=[
                {
                    "operation_id": "param.cgi:list",
                    "device_id": "cam-01",
                    "params": {"group": "Image"},
                },
            ],
        )
        found = engine.get_plan(plan.plan_id)
        assert found is plan

    def test_get_plan_not_found(self, engine):
        assert engine.get_plan("nonexistent") is None

    def test_list_plans(self, engine):
        engine.create_plan(
            description="Plan 1",
            steps=[
                {
                    "operation_id": "param.cgi:list",
                    "device_id": "cam-01",
                    "params": {},
                },
            ],
        )
        engine.create_plan(
            description="Plan 2",
            steps=[
                {
                    "operation_id": "param.cgi:list",
                    "device_id": "cam-01",
                    "params": {},
                },
            ],
        )
        plans = engine.list_plans()
        assert len(plans) == 2

    def test_fleet_plan_multi_device(self, engine):
        """Create a plan with steps across multiple devices."""
        plan = engine.create_plan(
            description="Fleet NTP config",
            steps=[
                {
                    "operation_id": "param.cgi:update",
                    "device_id": "cam-01",
                    "params": {"root.Time.NTPServer": "pool.ntp.org"},
                },
                {
                    "operation_id": "param.cgi:update",
                    "device_id": "cam-02",
                    "params": {"root.Time.NTPServer": "pool.ntp.org"},
                },
                {
                    "operation_id": "param.cgi:update",
                    "device_id": "cam-03",
                    "params": {"root.Time.NTPServer": "pool.ntp.org"},
                },
            ],
            on_failure="continue",
        )
        assert len(plan.steps) == 3
        assert plan.on_failure.value == "continue"
