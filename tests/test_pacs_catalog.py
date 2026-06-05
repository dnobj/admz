"""Tests for the Physical Access Control catalog entries.

Door-control-service and schedule-service SOAP catalog files. Verifies
the loader picks them up, the risk classifications match the indexes,
and the resolver can find them for the canonical task slugs.
"""

import pytest

from axis_api_atlas.catalog.loader import CatalogLoader
from axis_api_atlas.catalog.resolver import CatalogResolver


@pytest.fixture(scope="module")
def loader():
    # Catalog data now ships with the axis-api-atlas package (ADR-0029).
    import axis_api_atlas
    return CatalogLoader(axis_api_atlas.default_data_path())


@pytest.fixture(scope="module")
def resolver(loader):
    return CatalogResolver(loader)


class TestDoorControlServiceCatalog:

    @pytest.mark.parametrize("op_id", [
        "door-control-service:GetDoorInfoList",
        "door-control-service:GetDoorState",
        "door-control-service:GetDoorConfigurationList",
        "door-control-service:AccessDoor",
        "door-control-service:LockDoor",
        "door-control-service:UnlockDoor",
        "door-control-service:BlockDoor",
        "door-control-service:ReleaseDoor",
        "door-control-service:LockDownDoor",
    ])
    def test_operation_loads(self, loader, op_id):
        op = loader.get_operation("vapix", op_id)
        assert op is not None, f"{op_id} did not load"
        assert op.id == op_id
        assert op.cgi == "door-control-service"
        assert op.method == "POST"
        assert op.generation == "soap"

    def test_soap_namespace_is_axis_door_control(self, loader):
        op = loader.get_operation("vapix", "door-control-service:GetDoorInfoList")
        assert op.soap_namespace == "http://www.axis.com/vapix/ws/door-control/"

    def test_read_ops_classified_read_only(self, loader):
        for op_id in (
            "door-control-service:GetDoorInfoList",
            "door-control-service:GetDoorState",
            "door-control-service:GetDoorConfigurationList",
        ):
            assert loader.get_risk_level("vapix", op_id) == "read-only", op_id

    def test_state_change_ops_classified_service_affecting(self, loader):
        for op_id in (
            "door-control-service:AccessDoor",
            "door-control-service:LockDoor",
            "door-control-service:UnlockDoor",
            "door-control-service:BlockDoor",
            "door-control-service:ReleaseDoor",
        ):
            assert loader.get_risk_level("vapix", op_id) == "service-affecting", op_id

    def test_lockdown_classified_dangerous(self, loader):
        """Emergency lockdown is the only door-control operation gated
        through the two-gate confirm flow."""
        assert loader.get_risk_level(
            "vapix", "door-control-service:LockDownDoor"
        ) == "dangerous"

    def test_lockdown_has_danger_description(self, loader):
        op = loader.get_operation("vapix", "door-control-service:LockDownDoor")
        assert op.danger_description, "Dangerous ops must explain themselves"
        assert "emergency" in op.danger_description.lower()


class TestScheduleServiceCatalog:

    @pytest.mark.parametrize("op_id", [
        "schedule-service:GetScheduleList",
        "schedule-service:ScheduleActive",
    ])
    def test_operation_loads(self, loader, op_id):
        op = loader.get_operation("vapix", op_id)
        assert op is not None, f"{op_id} did not load"
        assert op.cgi == "schedule-service"
        assert op.generation == "soap"

    def test_namespace_is_axis_schedule(self, loader):
        op = loader.get_operation("vapix", "schedule-service:GetScheduleList")
        assert op.soap_namespace == "http://www.axis.com/vapix/ws/schedule/"

    def test_both_ops_are_read_only(self, loader):
        for op_id in (
            "schedule-service:GetScheduleList",
            "schedule-service:ScheduleActive",
        ):
            assert loader.get_risk_level("vapix", op_id) == "read-only", op_id


class TestPacsTaskIndex:
    """The by-task index should resolve the canonical PACS task slugs
    to the right operations."""

    def test_list_doors_task(self, resolver):
        result = resolver.resolve(
            device_id="dummy", intent="list doors", family="vapix"
        )
        op_ids = {op["id"] for op in result.operations}
        assert "door-control-service:GetDoorInfoList" in op_ids

    def test_grant_door_access_task(self, resolver):
        result = resolver.resolve(
            device_id="dummy",
            intent="grant door access",
            family="vapix",
        )
        op_ids = {op["id"] for op in result.operations}
        assert "door-control-service:AccessDoor" in op_ids

    def test_emergency_lockdown_task(self, resolver):
        result = resolver.resolve(
            device_id="dummy", intent="emergency lockdown", family="vapix"
        )
        op_ids = {op["id"] for op in result.operations}
        assert "door-control-service:LockDownDoor" in op_ids
        assert "door-control-service:BlockDoor" in op_ids

    def test_list_schedules_task(self, resolver):
        result = resolver.resolve(
            device_id="dummy", intent="list schedules", family="vapix"
        )
        op_ids = {op["id"] for op in result.operations}
        assert "schedule-service:GetScheduleList" in op_ids
