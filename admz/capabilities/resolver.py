"""
Capabilities resolver -- checks whether a device supports a given API.
"""

import logging
from typing import Any, Dict, Optional

from admz.capabilities.loader import CapabilitiesLoader
from admz.capabilities.models import CapabilityLookupResult
from admz.knowledge.loader import normalize_model

logger = logging.getLogger(__name__)


class CapabilitiesResolver:
    """
    Checks if a device supports a specific API based on its model and firmware.

    Uses the CapabilitiesLoader to look up pre-populated snapshots.
    """

    def __init__(self, loader: CapabilitiesLoader):
        self.loader = loader

    def check_api_support(
        self,
        device_id: str,
        catalog_api_id: str,
        device_info: Optional[Dict[str, Any]] = None,
    ) -> CapabilityLookupResult:
        """Check if a device supports a specific catalog API.

        Args:
            device_id: Device identifier.
            catalog_api_id: The api_id from an _api.yaml file.
            device_info: Device metadata dict (needs 'model', optionally 'firmware').

        Returns:
            CapabilityLookupResult with support status.
        """
        result = CapabilityLookupResult(device_id=device_id)
        device_info = device_info or {}

        model = device_info.get("model")
        firmware = device_info.get("firmware")
        result.model = model
        result.firmware = firmware

        if not model:
            result.notes.append("No model in device info; cannot check capabilities.")
            return result

        mc = self.loader.load_model(model)
        if not mc:
            result.notes.append(
                f"No capabilities file for model '{normalize_model(model)}'. "
                f"Run discover_device_apis to populate."
            )
            return result

        # Find the right snapshot
        snap = mc.get_snapshot(firmware) if firmware else mc.get_latest_snapshot()
        if not snap:
            result.notes.append(
                f"No snapshot for firmware '{firmware}'. "
                f"Available: {[s.firmware for s in mc.snapshots]}"
            )
            return result

        result.snapshot = snap

        # Translate catalog api_id to device-reported id
        device_api_id = self.loader.catalog_api_id_to_device_id(catalog_api_id)
        version = snap.apis.get(device_api_id)

        if version is not None:
            result.supported = True
            result.api_version = version
        else:
            result.supported = False
            result.notes.append(
                f"API '{catalog_api_id}' (device id: '{device_api_id}') "
                f"not found in {snap.api_count} APIs for "
                f"{mc.model} firmware {snap.firmware}."
            )

        return result

    def get_all_apis(
        self,
        device_id: str,
        device_info: Optional[Dict[str, Any]] = None,
    ) -> CapabilityLookupResult:
        """Get the full API snapshot for a device.

        Returns:
            CapabilityLookupResult with the snapshot populated (no specific API check).
        """
        result = CapabilityLookupResult(device_id=device_id)
        device_info = device_info or {}

        model = device_info.get("model")
        firmware = device_info.get("firmware")
        result.model = model
        result.firmware = firmware

        if not model:
            result.notes.append("No model in device info; cannot look up capabilities.")
            return result

        mc = self.loader.load_model(model)
        if not mc:
            result.notes.append(
                f"No capabilities file for model '{normalize_model(model)}'."
            )
            return result

        snap = mc.get_snapshot(firmware) if firmware else mc.get_latest_snapshot()
        if not snap:
            result.notes.append(
                f"No snapshot for firmware '{firmware}'."
            )
            return result

        result.snapshot = snap
        result.supported = True
        return result
