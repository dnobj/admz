"""
Catalog loader — reads operation YAML files from the catalog directory.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from admz.catalog.models import (
    CgiMetadata,
    Operation,
    ParameterGroup,
    ParameterInfo,
    RollbackSpec,
)

logger = logging.getLogger(__name__)


class CatalogLoader:
    """
    Reads operation YAML files from a local catalog directory.

    The catalog_path should point to the root of the operations-catalog
    repo (or a subdirectory like catalog/ within the admz repo).
    """

    def __init__(self, catalog_path: str):
        self.catalog_path = Path(catalog_path)
        self._cgi_cache: Dict[str, CgiMetadata] = {}
        self._operation_cache: Dict[str, Operation] = {}
        self._index_cache: Dict[str, Dict[str, List[str]]] = {}

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load and parse a YAML file."""
        with open(path) as f:
            return yaml.safe_load(f) or {}

    # ------------------------------------------------------------------
    # API metadata
    # ------------------------------------------------------------------

    def get_api_metadata(self, family: str, api_name: str) -> Optional[CgiMetadata]:
        """Load _api.yaml for an API endpoint (CGI or config-rest)."""
        cache_key = f"{family}/{api_name}"
        if cache_key in self._cgi_cache:
            return self._cgi_cache[cache_key]

        # Try cgi/ first, then rest/, then ws/
        path = self.catalog_path / family / "cgi" / api_name / "_api.yaml"
        if not path.exists():
            path = self.catalog_path / family / "rest" / api_name / "_api.yaml"
        if not path.exists():
            path = self.catalog_path / family / "ws" / api_name / "_api.yaml"
        if not path.exists():
            return None

        data = self._load_yaml(path)
        meta = CgiMetadata(
            endpoint=data.get("endpoint", ""),
            generation=data["generation"],
            auth=data.get("auth"),
            min_firmware=data.get("min_firmware"),
            api_id=data.get("api_id"),
            description=data.get("description", ""),
            notes=data.get("notes"),
        )
        self._cgi_cache[cache_key] = meta
        return meta

    # Backward-compatible alias
    get_cgi_metadata = get_api_metadata

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def get_operation(self, family: str, operation_id: str) -> Optional[Operation]:
        """
        Load a single operation by ID.

        Operation IDs follow the pattern: api_name:action
        e.g., "param.cgi:update", "basicdeviceinfo.cgi:getAllProperties",
              "cert:listCertificates", "ssh:listUsers"
        """
        cache_key = f"{family}/{operation_id}"
        if cache_key in self._operation_cache:
            return self._operation_cache[cache_key]

        # Parse operation_id into api_name and action
        parts = operation_id.split(":", 1)
        if len(parts) != 2:
            return None
        api_name, action = parts

        # Find the API directory — try cgi/ first, then rest/, then ws/
        api_dir = self.catalog_path / family / "cgi" / api_name
        if not api_dir.exists():
            api_dir = self.catalog_path / family / "rest" / api_name
        if not api_dir.exists():
            api_dir = self.catalog_path / family / "ws" / api_name
        if not api_dir.exists():
            return None

        # Search for a YAML file with matching id
        for yaml_file in api_dir.glob("*.yaml"):
            if yaml_file.name == "_api.yaml":
                continue
            data = self._load_yaml(yaml_file)
            if data.get("id") == operation_id:
                op = self._parse_operation(data, family, api_name)
                self._operation_cache[cache_key] = op
                return op

        # Also search in subdirectories (e.g., groups/, version dirs)
        for yaml_file in api_dir.rglob("*.yaml"):
            if yaml_file.name == "_api.yaml":
                continue
            data = self._load_yaml(yaml_file)
            if data.get("id") == operation_id:
                op = self._parse_operation(data, family, api_name)
                self._operation_cache[cache_key] = op
                return op

        return None

    def _parse_operation(
        self, data: Dict[str, Any], family: str, api_name: str
    ) -> Operation:
        """Parse a raw YAML dict into an Operation."""
        rollback = None
        if "rollback" in data:
            rb = data["rollback"]
            rollback = RollbackSpec(
                strategy=rb.get("strategy", "none"),
                description=rb.get("description", ""),
                read_action=rb.get("read_action"),
                operation_id=rb.get("operation_id"),
                params=rb.get("params"),
            )

        op = Operation(
            id=data["id"],
            cgi=data.get("cgi", api_name),
            method=data.get("method", "GET"),
            risk_level=data.get("risk_level", "normal"),
            request=data.get("request", {}),
            response=data.get("response", {}),
            rollback=rollback,
            requires=data.get("requires", {}),
            min_api_version=data.get("min_api_version"),
            danger_description=data.get("danger_description"),
            service_impact=data.get("service_impact"),
            notes=data.get("notes"),
            param_rules=data.get("param_rules"),
            base_path=data.get("base_path"),
            path=data.get("path"),
            soap_namespace=data.get("soap_namespace"),
            soap_action=data.get("soap_action"),
        )

        # Enrich with API metadata
        api_meta = self.get_api_metadata(family, api_name)
        if api_meta:
            op.endpoint = api_meta.endpoint
            op.generation = api_meta.generation
            op.auth = api_meta.auth
            # Inherit API-level notes if operation has none
            if not op.notes and api_meta.notes:
                op.notes = api_meta.notes

        return op

    # ------------------------------------------------------------------
    # Parameter groups
    # ------------------------------------------------------------------

    def get_parameter_group(
        self, family: str, group_name: str
    ) -> Optional[ParameterGroup]:
        """
        Load a param.cgi parameter group file.

        group_name is e.g., "root.Image" — maps to
        cgi/param.cgi/<version>/groups/root.Image.yaml
        """
        param_dir = self.catalog_path / family / "cgi" / "param.cgi"
        filename = f"{group_name}.yaml"

        # Search version subfolders for groups/ directory
        path = None
        for groups_dir in param_dir.glob("*/groups"):
            candidate = groups_dir / filename
            if candidate.exists():
                path = candidate
                break

        if path is None:
            return None

        data = self._load_yaml(path)
        params = {}
        for name, pdata in data.get("parameters", {}).items():
            params[name] = ParameterInfo(
                name=name,
                type=pdata.get("type", "string"),
                description=pdata.get("description", ""),
                valid_values=pdata.get("valid_values"),
                valid_values_from=pdata.get("valid_values_from"),
                example_values=pdata.get("example_values"),
                range=pdata.get("range"),
                default=pdata.get("default"),
                auth_level=pdata.get("auth_level", "admin"),
            )

        return ParameterGroup(
            group=data["group"],
            cgi=data.get("cgi", "param.cgi"),
            read_action=data.get("read_action", "list"),
            write_action=data.get("write_action", "update"),
            description=data.get("description", ""),
            channel_indexed=data.get("channel_indexed", False),
            channel_key=data.get("channel_key"),
            parameters=params,
            service_impact=data.get("service_impact"),
        )

    # ------------------------------------------------------------------
    # Index files
    # ------------------------------------------------------------------

    def load_index(self, family: str, index_name: str) -> Dict[str, List[str]]:
        """
        Load an index file (e.g., by-task, by-risk).

        Returns a dict mapping index keys to lists of file paths.
        """
        cache_key = f"{family}/{index_name}"
        if cache_key in self._index_cache:
            return self._index_cache[cache_key]

        path = self.catalog_path / family / "index" / f"{index_name}.yaml"
        if not path.exists():
            return {}

        data = self._load_yaml(path)
        # Filter out comment-only keys
        index = {
            k: v for k, v in data.items()
            if isinstance(v, list)
        }
        self._index_cache[cache_key] = index
        return index

    # ------------------------------------------------------------------
    # Bulk loading from file paths
    # ------------------------------------------------------------------

    def load_files(
        self, family: str, file_paths: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Load multiple catalog files by path.

        Returns a dict mapping file paths to their parsed YAML content.
        Used by the resolver to load the files referenced by an index entry.
        """
        results = {}
        for fp in file_paths:
            full_path = self.catalog_path / family / fp
            if full_path.exists():
                results[fp] = self._load_yaml(full_path)
            else:
                logger.warning("Catalog file not found: %s/%s", family, fp)
        return results

    # ------------------------------------------------------------------
    # Risk lookup
    # ------------------------------------------------------------------

    def get_risk_level(self, family: str, operation_id: str) -> str:
        """
        Get the risk level for an operation.

        Checks the operation file first, then falls back to by-risk index.
        """
        op = self.get_operation(family, operation_id)
        if op:
            return op.risk_level

        # Fallback: check risk index
        risk_index = self.load_index(family, "by-risk")
        for level, paths in risk_index.items():
            for path in paths:
                # Check if any file in this risk level contains this operation
                full_path = self.catalog_path / family / path
                if full_path.exists():
                    data = self._load_yaml(full_path)
                    if data.get("id") == operation_id:
                        return level

        return "normal"  # default if not found

    def clear_cache(self):
        """Clear all caches. Useful after catalog updates."""
        self._cgi_cache.clear()
        self._operation_cache.clear()
        self._index_cache.clear()
