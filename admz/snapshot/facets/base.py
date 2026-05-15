from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type
import fnmatch


@dataclass
class DeviceCriteria:
    device_types: Optional[List[str]] = None
    model_patterns: Optional[List[str]] = None
    families: Optional[List[str]] = None
    min_firmware: Optional[str] = None


@dataclass
class ReadSpec:
    operation_id: str
    params: Dict[str, str] = field(default_factory=dict)
    result_key: str = ""

    def cache_key(self) -> tuple:
        return (self.operation_id, tuple(sorted(self.params.items())))


class FacetAdapter(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def applies_to(self) -> List[DeviceCriteria]:
        ...

    @property
    def param_prefixes(self) -> List[str]:
        """Parameter prefixes this facet filters from a full param.cgi dump.
        Return empty if this facet doesn't use param.cgi."""
        return []

    @property
    def extra_read_ops(self) -> List[ReadSpec]:
        """Additional operations beyond the shared param.cgi dump."""
        return []

    @property
    @abstractmethod
    def write_ops(self) -> List[str]:
        ...

    @property
    def restore_order(self) -> int:
        return 50

    def matches_device(self, device_info: Dict[str, Any]) -> bool:
        if not self.applies_to:
            return True
        return any(
            self._matches_criteria(c, device_info) for c in self.applies_to
        )

    def _matches_criteria(
        self, criteria: DeviceCriteria, device_info: Dict[str, Any]
    ) -> bool:
        model = device_info.get("model", "")
        device_type = device_info.get("device_type", "")
        family = device_info.get("api_family", "vapix")
        firmware = device_info.get("firmware", "")

        if criteria.device_types and device_type not in criteria.device_types:
            return False
        if criteria.families and family not in criteria.families:
            return False
        if criteria.model_patterns:
            if not any(fnmatch.fnmatch(model, p) for p in criteria.model_patterns):
                return False
        if criteria.min_firmware and firmware < criteria.min_firmware:
            return False
        return True

    @abstractmethod
    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw API responses into normalized YAML-ready dict.

        raw_responses keys:
          - "params": dict of all param.cgi key=value pairs (if param_prefixes)
          - any result_key from extra_read_ops
        """
        ...

    @abstractmethod
    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert YAML back into operation calls for restore.

        Returns list of {"operation_id": str, "params": dict}.
        """
        ...


class SimpleParamFacet(FacetAdapter):
    """Base class for facets that filter a single param.cgi prefix and round-trip
    cleanly via param.cgi:update. Subclasses just declare name, prefix,
    restore_order, and optionally applies_to."""

    PREFIX: str = ""
    NAME: str = ""
    RESTORE_ORDER: int = 50
    APPLIES_TO: List[DeviceCriteria] = [DeviceCriteria(families=["vapix"])]

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        return self.APPLIES_TO

    @property
    def param_prefixes(self) -> List[str]:
        return [self.PREFIX]

    @property
    def write_ops(self) -> List[str]:
        return ["param.cgi:update"]

    @property
    def restore_order(self) -> int:
        return self.RESTORE_ORDER

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        params = raw_responses.get("params", {})
        result = {}
        for key, value in sorted(params.items()):
            if key.startswith(self.PREFIX):
                short_key = key[len(self.PREFIX):]
                result[short_key] = value
        return result

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        params = {}
        for key, value in yaml_doc.items():
            params[f"{self.PREFIX}{key}"] = str(value)
        return [{"operation_id": "param.cgi:update", "params": params}]


_registry: List[Type[FacetAdapter]] = []


def register_facet(cls: Type[FacetAdapter]) -> Type[FacetAdapter]:
    _registry.append(cls)
    return cls


def get_facets_for_device(device_info: Dict[str, Any]) -> List[FacetAdapter]:
    adapters = []
    for cls in _registry:
        adapter = cls()
        if adapter.matches_device(device_info):
            adapters.append(adapter)
    return sorted(adapters, key=lambda a: a.restore_order)


def get_all_facets() -> List[Type[FacetAdapter]]:
    return list(_registry)
