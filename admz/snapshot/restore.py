import logging
from typing import Any, Dict, List, Optional

import yaml

from axis_api_atlas.catalog.loader import CatalogLoader
from admz.device_registry import DeviceRegistry
from admz.snapshot.facets import get_facets_for_device
from admz.snapshot.facets.base import FacetAdapter
from admz.snapshot.git_repo import GitRepo

logger = logging.getLogger(__name__)

# param.cgi:update goes out as a GET query string (legacy-cgi executor);
# a whole-facet restore (image: ~340 params) overflows the device's URI
# limit — observed live as HTTP 414 on a P3288. Chunk big updates into
# multiple plan steps: ~1500 bytes of raw key=value per call keeps the
# encoded URI comfortably under the ~8k device default. (A general fix —
# POSTing long param.cgi updates — belongs in the executor; this keeps
# restore working without touching the shared execution path.)
_PARAM_UPDATE_BUDGET = 1500


def _chunk_params(
    params: Dict[str, str], budget: int = _PARAM_UPDATE_BUDGET
) -> List[Dict[str, str]]:
    chunks: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    size = 0
    for key, value in params.items():
        item = len(key) + len(str(value)) + 2  # '=' + '&'
        if current and size + item > budget:
            chunks.append(current)
            current, size = {}, 0
        current[key] = value
        size += item
    if current:
        chunks.append(current)
    return chunks


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
        ref: Optional[str] = None,
        facet_names: Optional[List[str]] = None,
        family: str = "vapix",
    ) -> Dict[str, Any]:
        device_info = self.registry.get_device_info(device_id)
        device_info["device_id"] = device_id

        # Restore targets the device's blessed baseline by default (ADR-0031),
        # NOT git HEAD — audits now advance HEAD to the latest observation, so
        # "restore" to HEAD could replay a drifted state. An explicit ref
        # overrides; if no baseline is set yet, fall back to HEAD.
        if ref is None:
            ref = device_info.get("baseline_sha") or "HEAD"

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

                skipped = call.get("skipped")
                if skipped:
                    warnings.append(
                        f"{facet.name}: not restorable (read-only/runtime/"
                        f"secret-masked), skipping: {', '.join(skipped)}"
                    )

                risk = self.catalog.get_risk_level(family, operation_id)
                if risk == "dangerous":
                    warnings.append(
                        f"Step {step_number} ({facet.name}): operation "
                        f"{operation_id} is dangerous — will require confirmation"
                    )

                if operation_id == "param.cgi:update":
                    param_sets = _chunk_params(call["params"])
                else:
                    param_sets = [call["params"]]

                total = len(param_sets)
                for idx, chunk in enumerate(param_sets, 1):
                    description = f"Restore {facet.name} from {ref}"
                    if total > 1:
                        description += f" ({idx}/{total})"
                    steps.append(
                        {
                            "operation_id": operation_id,
                            "device_id": device_id,
                            "params": chunk,
                            "description": description,
                            # ADR-0034: a restore overwrites device config
                            # wholesale — it must always stop at the approval
                            # widget like a reboot, even though
                            # param.cgi:update alone is catalog-risk
                            # "normal". The engine treats this as a floor
                            # (it can raise catalog risk, never lower it).
                            "risk_level": "service-affecting",
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
                skipped = call.get("skipped")
                if skipped:
                    warnings.append(
                        f"{facet.name}: not restorable (read-only/runtime/"
                        f"secret-masked), skipping: {', '.join(skipped)}"
                    )

                if call["operation_id"] == "param.cgi:update":
                    param_sets = _chunk_params(call["params"])
                else:
                    param_sets = [call["params"]]

                total = len(param_sets)
                for idx, chunk in enumerate(param_sets, 1):
                    description = f"Apply profile {profile_name}/{facet.name}"
                    if total > 1:
                        description += f" ({idx}/{total})"
                    steps.append(
                        {
                            "operation_id": call["operation_id"],
                            "device_id": device_id,
                            "params": chunk,
                            "description": description,
                            # ADR-0034: bulk config overwrite — same widget
                            # gate as a restore.
                            "risk_level": "service-affecting",
                        }
                    )
                    step_number += 1

        return {
            "description": f"Apply profile '{profile_name}' to {device_id}",
            "steps": steps,
            "on_failure": "stop",
            "warnings": warnings,
        }
