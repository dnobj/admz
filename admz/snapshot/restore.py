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

    def build_targeted_revert_plan(
        self,
        device_id: str,
        drifted_fields: List[Any],
        family: str = "vapix",
    ) -> Dict[str, Any]:
        """Revert ONLY the drifted fields to their baseline values.

        A full ``build_restore_plan`` re-pushes the entire baseline (every
        restorable param across every facet — hundreds of params, many chunked
        steps) even when a handful of fields drifted. This builds the minimal
        diff-scoped plan instead: each ``DriftField`` carries ``expected`` (the
        baseline value) + ``facet`` + ``path``; map (facet, path) back to its
        param.cgi key via the facet's ``revert_param``. Fields a facet can't
        write back (read-only/uncategorized/masked) or that *appeared* (not in
        the baseline) are skipped with a warning, not blindly forced.
        """
        from admz.snapshot.facets import get_facets_for_device

        device_info = self.registry.get_device_info(device_id)
        device_info["device_id"] = device_id
        facets_by_name = {
            f.name: f for f in get_facets_for_device(device_info)
        }
        baseline_sha = device_info.get("baseline_sha")

        params: Dict[str, str] = {}
        op_fields: Dict[str, List[Any]] = {}   # facet name -> its op-revertable fields
        not_revertable: List[str] = []
        for field in drifted_fields:
            label = f"{field.facet}.{field.path}"
            facet = facets_by_name.get(field.facet)
            # API-backed facets revert whole-object via their own setter op —
            # this also covers fields that APPEARED live (writing the baseline
            # object removes additions), which param.cgi never could.
            if facet is not None and facet.op_revertable(field.path):
                op_fields.setdefault(field.facet, []).append(field)
                continue
            # A field present live but NOT in the baseline ("appeared") can't
            # be reverted by writing a value — there's nothing to restore to.
            if str(field.expected) == "<missing>":
                not_revertable.append(f"{label} (added, not in baseline)")
                continue
            if facet is None:
                not_revertable.append(label)
                continue
            rv = facet.revert_param(field.path, field.expected)
            if rv is None:
                not_revertable.append(label)
                continue
            full_key, value = rv
            params[full_key] = value

        warnings: List[str] = []

        # Op-level reverts: one whole-object write-back per facet, built from
        # the facet's baseline doc (the desired state), not from field deltas.
        op_steps: List[Dict[str, Any]] = []
        op_field_count = 0
        for facet_name, fields in sorted(op_fields.items()):
            facet = facets_by_name[facet_name]
            labels = ", ".join(sorted(f"{facet_name}.{f.path}" for f in fields))
            baseline_doc = (
                self.git.read_facet(device_id, facet_name, baseline_sha)
                if baseline_sha else None
            )
            if not baseline_doc:
                warnings.append(
                    f"No baseline doc for facet '{facet_name}' — cannot "
                    f"op-revert: {labels}"
                )
                continue
            try:
                steps_for_facet = facet.build_revert_ops(
                    [(f.path, f.expected) for f in fields], baseline_doc
                )
            except Exception:  # noqa: BLE001 — one bad facet must not kill the plan
                logger.warning(
                    "build_revert_ops failed for facet %s on %s",
                    facet_name, device_id, exc_info=True,
                )
                steps_for_facet = None
            if not steps_for_facet:
                warnings.append(f"Facet '{facet_name}' produced no revert op for: {labels}")
                continue
            for s in steps_for_facet:
                op_steps.append({
                    **s,
                    "device_id": device_id,
                    # ADR-0034: writing live config — must gate at the widget.
                    "risk_level": "service-affecting",
                })
            op_field_count += len(fields)

        if not_revertable:
            warnings.append(
                "Not auto-revertable (read-only / uncategorized / masked / "
                "added), skipping: " + ", ".join(sorted(not_revertable))
            )

        steps = []
        if params:
            param_sets = _chunk_params(params)
            total = len(param_sets)
            for idx, chunk in enumerate(param_sets, 1):
                description = (
                    f"Revert {len(chunk)} drifted setting"
                    + ("s" if len(chunk) != 1 else "")
                    + f" on {device_id}"
                )
                if total > 1:
                    description += f" ({idx}/{total})"
                steps.append({
                    # ADR-0034: writing live config — must gate at the widget.
                    "operation_id": "param.cgi:update",
                    "device_id": device_id,
                    "params": chunk,
                    "description": description,
                    "risk_level": "service-affecting",
                })

        steps.extend(op_steps)

        n = len(params) + op_field_count
        return {
            "description": (
                f"Revert {n} drifted setting" + ("s" if n != 1 else "")
                + f" on {device_id} to baseline"
            ),
            "steps": steps,
            "on_failure": "stop",
            "warnings": warnings,
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
