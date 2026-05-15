import logging
from typing import Any, Dict, List, Optional

import yaml

from admz.catalog.loader import CatalogLoader
from admz.device_registry import DeviceRegistry
from admz.snapshot.facets import get_facets_for_device
from admz.snapshot.facets.base import FacetAdapter
from admz.snapshot.git_repo import GitRepo

logger = logging.getLogger(__name__)


class RestoreBuilder:
    """Reads config from git and builds an execution plan for the plan engine."""

    def __init__(
        self,
        catalog: CatalogLoader,
        registry: DeviceRegistry,
        git_repo: GitRepo,
    ):
        self.catalog = catalog
        self.registry = registry
        self.git = git_repo

    def build_restore_plan(
        self,
        device_id: str,
        ref: str = "HEAD",
        facet_names: Optional[List[str]] = None,
        family: str = "vapix",
    ) -> Dict[str, Any]:
        device_info = self.registry.get_device_info(device_id)
        device_info["device_id"] = device_id

        facets = get_facets_for_device(device_info)
        if facet_names:
            facets = [f for f in facets if f.name in facet_names]

        facets = sorted(facets, key=lambda f: f.restore_order)

        steps = []
        warnings = []
        step_number = 1

        for facet in facets:
            yaml_doc = self.git.read_facet(device_id, facet.name, ref)
            if yaml_doc is None:
                logger.info(
                    "No config for facet %s at ref %s, skipping",
                    facet.name,
                    ref,
                )
                continue

            try:
                op_calls = facet.deserialize(yaml_doc)
            except Exception as e:
                warnings.append(
                    f"Failed to deserialize facet {facet.name}: {e}"
                )
                continue

            if not op_calls:
                continue

            for call in op_calls:
                operation_id = call["operation_id"]

                risk = self.catalog.get_risk_level(family, operation_id)
                if risk == "dangerous":
                    warnings.append(
                        f"Step {step_number} ({facet.name}): operation "
                        f"{operation_id} is dangerous — will require confirmation"
                    )

                steps.append(
                    {
                        "operation_id": operation_id,
                        "device_id": device_id,
                        "params": call["params"],
                        "description": f"Restore {facet.name} from {ref}",
                    }
                )
                step_number += 1

        return {
            "description": f"Restore {device_id} to {ref}",
            "steps": steps,
            "on_failure": "stop",
            "warnings": warnings,
            "source_ref": ref,
        }

    def build_profile_plan(
        self,
        device_id: str,
        profile_name: str,
        overrides: Optional[Dict[str, str]] = None,
        family: str = "vapix",
    ) -> Dict[str, Any]:
        """Build a plan that applies a shared profile to a device."""
        device_info = self.registry.get_device_info(device_id)
        device_info["device_id"] = device_id

        facets = get_facets_for_device(device_info)
        facets = sorted(facets, key=lambda f: f.restore_order)

        steps = []
        warnings = []
        step_number = 1

        for facet in facets:
            rel_path = f"profiles/{profile_name}/config/{facet.name}.yaml"
            content = self.git.get_file(rel_path)
            if content is None:
                continue

            yaml_doc = yaml.safe_load(content)
            if not yaml_doc:
                continue

            if overrides:
                for key, value in overrides.items():
                    if key in yaml_doc:
                        yaml_doc[key] = value

            try:
                op_calls = facet.deserialize(yaml_doc)
            except Exception as e:
                warnings.append(
                    f"Failed to deserialize profile facet {facet.name}: {e}"
                )
                continue

            for call in op_calls:
                steps.append(
                    {
                        "operation_id": call["operation_id"],
                        "device_id": device_id,
                        "params": call["params"],
                        "description": (
                            f"Apply profile {profile_name}/{facet.name}"
                        ),
                    }
                )
                step_number += 1

        return {
            "description": f"Apply profile '{profile_name}' to {device_id}",
            "steps": steps,
            "on_failure": "stop",
            "warnings": warnings,
        }
