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

    def revert_param(
        self, path: str, baseline_value: Any
    ) -> Optional["tuple[str, str]"]:
        """For a single drifted field — its flattened ``path`` within this
        facet + its ``baseline_value`` — return ``(full_param_key, value)`` to
        write back for a TARGETED revert (only the drifted fields, not the
        whole baseline), or None if this facet can't param.cgi-revert it:
        read-only facets (other/users/action_rules) and non-restorable keys
        (masked secrets, ``Volatile*``, per-facet excludes).

        Default: not revertable. ``SimpleParamFacet`` + ``EventsFacet`` override.
        """
        return None

    def op_revertable(self, path: str) -> bool:
        """Whether a targeted revert can write this field back through the
        facet's OWN API (see build_revert_ops) rather than param.cgi. Drives
        the drift report's ``revertable`` annotation for API-backed facets.

        Note this may be True even when the field *appeared* live
        (``expected == "<missing>"``): op-level revert writes the whole
        baseline object, which removes live additions — something the
        param.cgi path can never do. Default: no op-level revert."""
        return False

    def build_revert_ops(
        self,
        drifted: "List[tuple[str, Any]]",
        baseline_doc: Dict[str, Any],
    ) -> Optional[List[Dict[str, Any]]]:
        """Facet-level targeted revert for API-backed facets (ntp, schedules,
        MQTT bridge, ...): their config is a single object behind a dedicated
        setter op, so reverting even ONE drifted field means writing the full
        baseline object back.

        ``drifted`` is this facet's drifted (path, baseline_value) pairs —
        informational, since the write is whole-object; ``baseline_doc`` is
        the facet's full YAML doc at the device's baseline commit. Return
        plan-step dicts (``{"operation_id", "params", "description"}`` —
        device_id/risk are added by the plan builder), or None when this facet
        has no op-level revert (the default; param facets use revert_param)."""
        return None

    def canonical_key(self, path: str) -> str:
        """The cross-facet identifier for a drifted/serialized field — what the
        ignore list matches against, so one rule model addresses any config
        item. Param-backed facets return the full ``root.*`` param key;
        non-param facets (applications, action_rules, users) have no param key,
        so they return ``<facet>:<path>``. Default: facet-scoped.

        Unlike ``revert_param`` this is side-effect-free and ALWAYS yields a
        key (it must address masked/Volatile/read-only fields too — those are
        exactly the noisy items an operator wants to exclude)."""
        return f"{self.name}:{path}"


# param.cgi returns this literal mask for password-class values. Restoring
# it would overwrite the device's real secret with six asterisks.
MASKED_SECRET = "******"


def _matches_exclude(key: str, pattern: str) -> bool:
    """Glob patterns ('I*.Source') match segment-wise — '*' never crosses
    a dot, and the segment counts must agree, so 'I*.Source' matches
    'I0.Source' but not 'I0.Overlay.Source'. Plain entries are prefix
    matches ('NTP.', 'eth0.')."""
    if "*" in pattern or "?" in pattern:
        kseg, pseg = key.split("."), pattern.split(".")
        return len(kseg) == len(pseg) and all(
            fnmatch.fnmatchcase(k, p) for k, p in zip(kseg, pseg)
        )
    return key.startswith(pattern)


def is_restorable(key: str, value: Any, exclude: tuple = ()) -> bool:
    """Whether a serialized param may be written back during a restore.

    Skips, in order:
      * masked secrets (see MASKED_SECRET),
      * ``Volatile*`` segments — Axis convention for runtime values the
        system manages (e.g. Time.NTP.VolatileServer,
        Network.VolatileHostName.*),
      * per-facet ``exclude`` entries (read-only mirrors, structural
        constants, live interface state, ...) — see _matches_exclude.

    Everything skipped here is still *serialized* — drift on these keys is
    real, observable change — it just can't be reverted via param.cgi.
    """
    if str(value) == MASKED_SECRET:
        return False
    if any(seg.startswith("Volatile") for seg in key.split(".")):
        return False
    return not any(_matches_exclude(key, p) for p in exclude)


class SimpleParamFacet(FacetAdapter):
    """Base class for facets that filter a single param.cgi prefix and round-trip
    cleanly via param.cgi:update. Subclasses just declare name, prefix,
    restore_order, and optionally applies_to."""

    PREFIX: str = ""
    NAME: str = ""
    RESTORE_ORDER: int = 50
    #: Short-key prefixes (sans PREFIX) that must not be written back on
    #: restore — read-only mirrors and runtime state. See is_restorable().
    RESTORE_EXCLUDE: tuple = ()
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

    def revert_param(self, path: str, baseline_value: Any):
        # path is the PREFIX-stripped key; the full param key is PREFIX + path.
        if not is_restorable(path, baseline_value, self.RESTORE_EXCLUDE):
            return None
        return (f"{self.PREFIX}{path}", str(baseline_value))

    def canonical_key(self, path: str) -> str:
        # Param-backed: the full root.* key (PREFIX re-added to the short path).
        return f"{self.PREFIX}{path}"

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        params = {}
        skipped = []
        for key, value in yaml_doc.items():
            if not is_restorable(key, value, self.RESTORE_EXCLUDE):
                skipped.append(key)
                continue
            params[f"{self.PREFIX}{key}"] = str(value)
        if not params:
            return []
        call: Dict[str, Any] = {
            "operation_id": "param.cgi:update",
            "params": params,
        }
        if skipped:
            # Surfaced as plan warnings by the restore builder.
            call["skipped"] = sorted(skipped)
        return [call]


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


def facet_param_index() -> Dict[str, List[str]]:
    """The config→facet index: facet name -> the ``param.cgi`` prefixes it
    owns. Every param under a listed prefix belongs to that facet; anything
    not under any listed prefix falls to the catch-all ``other`` facet. This
    is the single source of truth both for "which category does this config
    belong to" and for the catch-all's complement."""
    index: Dict[str, List[str]] = {}
    for cls in _registry:
        inst = cls()
        prefixes = inst.param_prefixes
        if prefixes:
            index[inst.name] = list(prefixes)
    return index


def claimed_prefixes(exclude: Optional[str] = None) -> List[str]:
    """Flat union of every facet's param prefixes — the set of params already
    owned by a named category. ``exclude`` skips one facet (the catch-all
    excludes itself so it captures only the *un*owned remainder)."""
    out: List[str] = []
    for name, prefixes in facet_param_index().items():
        if name == exclude:
            continue
        out.extend(prefixes)
    return out
