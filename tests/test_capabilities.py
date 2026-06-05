"""Tests for the device API capabilities registry: models, loader, resolver."""

import os
import shutil
import tempfile

import pytest
import yaml

from axis_api_atlas.capabilities.models import (
    FirmwareSnapshot,
    ModelCapabilities,
    CapabilityLookupResult,
)
from axis_api_atlas.capabilities.loader import CapabilitiesLoader
from axis_api_atlas.capabilities.resolver import CapabilitiesResolver


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def tmp_catalog(tmp_path):
    """Create a temporary catalog directory with capability files."""
    cap_dir = tmp_path / "capabilities"
    cap_dir.mkdir()
    models_dir = cap_dir / "models"
    models_dir.mkdir()

    # Write a test model file
    model_data = {
        "model": "Q3538-SLVE",
        "series": "q35",
        "snapshots": [
            {
                "firmware": "12.8.54",
                "discovered": "2026-02-19",
                "device_id": "B8A44F661A2F",
                "api_count": 3,
                "apis": {
                    "api-discovery": "1.1",
                    "basic-device-info": "1.3",
                    "fwmgr": "1.8",
                },
            },
            {
                "firmware": "11.10.72",
                "discovered": "2026-01-15",
                "device_id": "B8A44F661A2F",
                "api_count": 2,
                "apis": {
                    "api-discovery": "1.0",
                    "basic-device-info": "1.2",
                },
            },
        ],
    }
    with open(models_dir / "q3538-slve.yaml", "w") as f:
        yaml.dump(model_data, f, default_flow_style=False)

    # Write API ID map
    api_map = {
        "firmware-manager": "fwmgr",
    }
    with open(cap_dir / "_api_id_map.yaml", "w") as f:
        yaml.dump(api_map, f, default_flow_style=False)

    return str(tmp_path)


@pytest.fixture
def loader(tmp_catalog):
    return CapabilitiesLoader(tmp_catalog)


@pytest.fixture
def resolver(loader):
    return CapabilitiesResolver(loader)


# ------------------------------------------------------------------
# FirmwareSnapshot tests
# ------------------------------------------------------------------


class TestFirmwareSnapshot:

    def test_basic_creation(self):
        snap = FirmwareSnapshot(
            firmware="12.8.54",
            discovered="2026-02-19",
            device_id="ABC123",
            api_count=5,
            apis={"api-discovery": "1.1", "ntp": "1.5"},
        )
        assert snap.firmware == "12.8.54"
        assert snap.api_count == 5
        assert snap.apis["ntp"] == "1.5"

    def test_defaults(self):
        snap = FirmwareSnapshot(firmware="1.0", discovered="2026-01-01")
        assert snap.device_id == ""
        assert snap.api_count == 0
        assert snap.apis == {}


# ------------------------------------------------------------------
# ModelCapabilities tests
# ------------------------------------------------------------------


class TestModelCapabilities:

    def test_get_snapshot_exact(self):
        mc = ModelCapabilities(
            model="TEST",
            snapshots=[
                FirmwareSnapshot(firmware="1.0", discovered="2026-01-01"),
                FirmwareSnapshot(firmware="2.0", discovered="2026-02-01"),
            ],
        )
        snap = mc.get_snapshot("2.0")
        assert snap is not None
        assert snap.firmware == "2.0"

    def test_get_snapshot_missing(self):
        mc = ModelCapabilities(
            model="TEST",
            snapshots=[
                FirmwareSnapshot(firmware="1.0", discovered="2026-01-01"),
            ],
        )
        assert mc.get_snapshot("9.9") is None

    def test_get_latest_snapshot(self):
        mc = ModelCapabilities(
            model="TEST",
            snapshots=[
                FirmwareSnapshot(firmware="1.0", discovered="2026-01-01"),
                FirmwareSnapshot(firmware="2.0", discovered="2026-02-15"),
                FirmwareSnapshot(firmware="1.5", discovered="2026-02-01"),
            ],
        )
        latest = mc.get_latest_snapshot()
        assert latest.firmware == "2.0"

    def test_get_latest_snapshot_empty(self):
        mc = ModelCapabilities(model="TEST")
        assert mc.get_latest_snapshot() is None

    def test_supports_api_found(self):
        mc = ModelCapabilities(
            model="TEST",
            snapshots=[
                FirmwareSnapshot(
                    firmware="1.0",
                    discovered="2026-01-01",
                    apis={"ntp": "1.5", "api-discovery": "1.1"},
                ),
            ],
        )
        assert mc.supports_api("ntp", "1.0") == "1.5"

    def test_supports_api_not_found(self):
        mc = ModelCapabilities(
            model="TEST",
            snapshots=[
                FirmwareSnapshot(
                    firmware="1.0",
                    discovered="2026-01-01",
                    apis={"ntp": "1.5"},
                ),
            ],
        )
        assert mc.supports_api("mqtt-client", "1.0") is None

    def test_supports_api_no_firmware_uses_latest(self):
        mc = ModelCapabilities(
            model="TEST",
            snapshots=[
                FirmwareSnapshot(
                    firmware="1.0",
                    discovered="2026-01-01",
                    apis={"ntp": "1.5"},
                ),
                FirmwareSnapshot(
                    firmware="2.0",
                    discovered="2026-02-01",
                    apis={"ntp": "2.0", "mqtt-client": "1.0"},
                ),
            ],
        )
        # No firmware specified -> uses latest (2.0)
        assert mc.supports_api("mqtt-client") == "1.0"


# ------------------------------------------------------------------
# CapabilitiesLoader tests
# ------------------------------------------------------------------


class TestCapabilitiesLoader:

    def test_load_model(self, loader):
        mc = loader.load_model("Q3538-SLVE")
        assert mc is not None
        assert mc.model == "Q3538-SLVE"
        assert mc.series == "q35"
        assert len(mc.snapshots) == 2

    def test_load_model_normalizes(self, loader):
        mc = loader.load_model("AXIS Q3538-SLVE")
        assert mc is not None
        assert mc.model == "Q3538-SLVE"

    def test_load_model_missing(self, loader):
        mc = loader.load_model("NONEXISTENT-999")
        assert mc is None

    def test_load_model_caching(self, loader):
        mc1 = loader.load_model("Q3538-SLVE")
        mc2 = loader.load_model("Q3538-SLVE")
        assert mc1 is mc2

    def test_load_model_snapshot_data(self, loader):
        mc = loader.load_model("Q3538-SLVE")
        snap = mc.get_snapshot("12.8.54")
        assert snap is not None
        assert snap.device_id == "B8A44F661A2F"
        assert snap.api_count == 3
        assert snap.apis["fwmgr"] == "1.8"

    def test_list_models(self, loader):
        models = loader.list_models()
        assert "q3538-slve" in models

    def test_get_api_id_map(self, loader):
        mapping = loader.get_api_id_map()
        assert mapping["firmware-manager"] == "fwmgr"

    def test_catalog_api_id_to_device_id_mapped(self, loader):
        assert loader.catalog_api_id_to_device_id("firmware-manager") == "fwmgr"

    def test_catalog_api_id_to_device_id_passthrough(self, loader):
        assert loader.catalog_api_id_to_device_id("ntp") == "ntp"

    def test_device_id_to_catalog_api_id_mapped(self, loader):
        assert loader.device_id_to_catalog_api_id("fwmgr") == "firmware-manager"

    def test_device_id_to_catalog_api_id_passthrough(self, loader):
        assert loader.device_id_to_catalog_api_id("ntp") == "ntp"

    def test_clear_cache(self, loader):
        loader.load_model("Q3538-SLVE")
        loader.get_api_id_map()
        assert len(loader._model_cache) > 0
        assert loader._api_id_map is not None
        loader.clear_cache()
        assert len(loader._model_cache) == 0
        assert loader._api_id_map is None
        assert loader._reverse_map is None

    def test_load_model_no_capabilities_dir(self, tmp_path):
        """Loader works gracefully when capabilities dir doesn't exist."""
        loader = CapabilitiesLoader(str(tmp_path))
        assert loader.load_model("anything") is None
        assert loader.list_models() == []
        assert loader.get_api_id_map() == {}


# ------------------------------------------------------------------
# CapabilitiesResolver tests
# ------------------------------------------------------------------


class TestCapabilitiesResolver:

    def test_check_api_support_found(self, resolver):
        result = resolver.check_api_support(
            "test-device",
            "basic-device-info",
            {"model": "Q3538-SLVE", "firmware": "12.8.54"},
        )
        assert result.supported is True
        assert result.api_version == "1.3"
        assert result.model == "Q3538-SLVE"

    def test_check_api_support_via_mapping(self, resolver):
        """firmware-manager maps to fwmgr on the device."""
        result = resolver.check_api_support(
            "test-device",
            "firmware-manager",
            {"model": "Q3538-SLVE", "firmware": "12.8.54"},
        )
        assert result.supported is True
        assert result.api_version == "1.8"

    def test_check_api_support_not_found(self, resolver):
        result = resolver.check_api_support(
            "test-device",
            "mqtt-client",
            {"model": "Q3538-SLVE", "firmware": "12.8.54"},
        )
        assert result.supported is False
        assert len(result.notes) > 0

    def test_check_api_support_no_model(self, resolver):
        result = resolver.check_api_support("test-device", "ntp", {})
        assert result.supported is None
        assert "No model" in result.notes[0]

    def test_check_api_support_unknown_model(self, resolver):
        result = resolver.check_api_support(
            "test-device",
            "ntp",
            {"model": "NONEXISTENT-999"},
        )
        assert result.supported is None
        assert "No capabilities file" in result.notes[0]

    def test_check_api_support_unknown_firmware(self, resolver):
        result = resolver.check_api_support(
            "test-device",
            "ntp",
            {"model": "Q3538-SLVE", "firmware": "99.99.99"},
        )
        assert result.supported is None
        assert "No snapshot" in result.notes[0]

    def test_check_api_support_no_firmware_uses_latest(self, resolver):
        """When no firmware is specified, uses the latest snapshot."""
        result = resolver.check_api_support(
            "test-device",
            "basic-device-info",
            {"model": "Q3538-SLVE"},
        )
        # Latest snapshot is 12.8.54 (discovered 2026-02-19)
        assert result.supported is True
        assert result.api_version == "1.3"

    def test_get_all_apis(self, resolver):
        result = resolver.get_all_apis(
            "test-device",
            {"model": "Q3538-SLVE", "firmware": "12.8.54"},
        )
        assert result.supported is True
        assert result.snapshot is not None
        assert result.snapshot.api_count == 3

    def test_get_all_apis_no_model(self, resolver):
        result = resolver.get_all_apis("test-device", {})
        assert result.supported is None
        assert "No model" in result.notes[0]


# ------------------------------------------------------------------
# CapabilityLookupResult tests
# ------------------------------------------------------------------


class TestCapabilityLookupResult:

    def test_defaults(self):
        result = CapabilityLookupResult(device_id="test")
        assert result.device_id == "test"
        assert result.model is None
        assert result.firmware is None
        assert result.snapshot is None
        assert result.supported is None
        assert result.api_version is None
        assert result.notes == []


# ------------------------------------------------------------------
# MCP integration: _check_api_support handler
# ------------------------------------------------------------------


class TestMCPCheckApiSupport:
    """Integration test for the check_api_support MCP tool handler."""

    @pytest.fixture
    def mcp_server(self, tmp_catalog, tmp_path, monkeypatch):
        # Isolate ADMZ state to tmp_path
        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
        monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
        monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
        monkeypatch.setenv("ADMZ_CATALOG_PATH", str(tmp_catalog))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        from admz.mcp.server import ADMZMCPServer
        server = ADMZMCPServer()
        # Register a device that maps to the fixture's Q3538-SLVE model
        server.registry.add_device(
            "test-cam",
            {"host": "10.0.0.1", "model": "Q3538-SLVE", "firmware": "12.8.54"},
        )
        return server

    @pytest.mark.asyncio
    async def test_check_known_api_returns_supported(self, mcp_server):
        result = await mcp_server._check_api_support("test-cam", "api-discovery")
        assert result["success"] is True
        assert result["supported"] is True
        assert result["api_version"] == "1.1"
        assert result["model"] == "Q3538-SLVE"
        assert result["firmware"] == "12.8.54"
        assert result["snapshot"]["api_count"] == 3

    @pytest.mark.asyncio
    async def test_check_unknown_api_returns_unsupported(self, mcp_server):
        result = await mcp_server._check_api_support("test-cam", "nonexistent-api")
        assert result["success"] is True
        assert result["supported"] is False
        assert result["api_version"] is None
        assert any("not found" in n for n in result["notes"])

    @pytest.mark.asyncio
    async def test_no_api_id_returns_full_snapshot(self, mcp_server):
        result = await mcp_server._check_api_support("test-cam", None)
        assert result["success"] is True
        assert result["supported"] is True
        assert "apis" in result["snapshot"]
        assert result["snapshot"]["apis"]["api-discovery"] == "1.1"

    @pytest.mark.asyncio
    async def test_unknown_device_returns_error(self, mcp_server):
        result = await mcp_server._check_api_support("ghost-device", "api-discovery")
        assert result["success"] is False
        assert "not found" in result["error"].lower()
