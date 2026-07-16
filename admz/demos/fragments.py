"""Demo-owned config fragments (ADR-0047).

A *fragment* is the sparse set of config keys a demo owns, per role, stored in
the config-repo at ``demos/<demo_id>/roles/<role>.yaml``:

.. code-block:: yaml

    demo_name: Loitering detection      # human breadcrumb; the id is the key
    facets:
      other:
        set:                            # pushed + owned when the demo is active
          Motion.M0.Enabled: "yes"
        require:                        # asserted at readiness, never pushed
          Audio.A0.Enabled: "yes"

Values are the **flattened strings** drift compares (``snapshot/flatten.py``)
— captured from a live drift diff, never authored by hand, so they round-trip
exactly. v1 constraints (ADR-0047):

* ``set`` only for param-writable keys (``facet.revert_param``) that already
  exist in the device's baseline — ``param.cgi`` cannot create or delete keys.
* Keys under an ignore rule can't be assigned (drift filters them before
  compare, so an ignored fragment key would never be verified).
* Values containing the device's own IP/hostname/MAC/serial are flagged as
  device-local (a warning, not a rejection) — they're unsafe to carry to a
  swapped-in device.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

MISSING = "<missing>"

MODE_SET = "set"
MODE_REQUIRE = "require"
MODES = (MODE_SET, MODE_REQUIRE)


def fragment_rel_path(demo_id: str, role: str) -> str:
    from admz.validators import validate_identifier

    validate_identifier(demo_id, "demo_id")
    validate_identifier(role, "role")
    return f"demos/{demo_id}/roles/{role}.yaml"


def normalize_role(role: Optional[str]) -> str:
    """Fold a free-text role into a path-safe slug (``Front Door`` → ``front-door``)."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", (role or "").strip()).strip("-").lower()
    return slug or "default"


def load_fragment(git, demo_id: str, role: str, ref: str = "HEAD") -> Dict[str, Any]:
    """The ``facets`` map of one role's fragment (``{}`` when none exists).

    Reads the working tree first so just-written entries are visible before the
    commit lands; falls back to the ref for callers pinning history.
    """
    rel = fragment_rel_path(demo_id, role)
    try:
        path = git._safe_rel_path(rel)
        if path.exists():
            with open(path) as f:
                doc = yaml.safe_load(f) or {}
            return doc.get("facets") or {}
    except Exception:  # noqa: BLE001 — fall through to git
        pass
    content = git.get_file(rel, ref)
    if content is None:
        return {}
    try:
        doc = yaml.safe_load(content) or {}
    except Exception:  # noqa: BLE001 — malformed fragment reads as empty
        logger.warning("malformed fragment %s — treating as empty", rel)
        return {}
    return doc.get("facets") or {}


def list_roles(git, demo_id: str) -> List[str]:
    """Roles that have a fragment on disk for this demo."""
    from admz.validators import validate_identifier

    validate_identifier(demo_id, "demo_id")
    try:
        roles_dir = git._safe_rel_path(f"demos/{demo_id}/roles")
        if not roles_dir.is_dir():
            return []
        return sorted(p.stem for p in roles_dir.glob("*.yaml"))
    except Exception:  # noqa: BLE001
        return []


def load_all_fragments(git, demo_id: str) -> Dict[str, Dict[str, Any]]:
    """``{role: facets-map}`` for every role fragment the demo owns."""
    return {r: load_fragment(git, demo_id, r) for r in list_roles(git, demo_id)}


def fragment_entry_count(facets: Dict[str, Any]) -> Dict[str, int]:
    counts = {MODE_SET: 0, MODE_REQUIRE: 0}
    for f in (facets or {}).values():
        for mode in MODES:
            counts[mode] += len(f.get(mode) or {})
    return counts


# ── Validation (capture-time gate) ──────────────────────────────────────────


def device_local_hits(value: str, device_info: Dict[str, Any]) -> List[str]:
    """Which of the device's own identity facts appear inside ``value``.

    A fragment value embedding the device's IP/hostname/MAC/serial is unsafe to
    carry to a swapped-in device — flag it so the operator reviews on rebind.
    """
    hits: List[str] = []
    facts = {
        "ip": device_info.get("ip_address") or "",
        "host": device_info.get("host") or "",
        "mac": device_info.get("mac_address") or "",
        "serial": device_info.get("serial_number") or "",
    }
    low = (value or "").lower()
    for label, fact in facts.items():
        fact = str(fact).strip()
        if len(fact) >= 4 and fact.lower() in low:
            hits.append(label)
    # MACs often appear without separators (e.g. in default hostnames).
    mac_bare = re.sub(r"[^0-9A-Fa-f]", "", str(facts["mac"]))
    if "mac" not in hits and len(mac_bare) == 12 and mac_bare.lower() in re.sub(
        r"[^0-9a-f]", "", low
    ):
        hits.append("mac")
    return hits


def validate_assignment(
    field,
    facet,
    mode: str,
    device_info: Dict[str, Any],
) -> Tuple[bool, str, List[str]]:
    """Can this drift row be assigned to a demo fragment?

    Args:
        field: a DriftField (or duck-typed row with facet/path/expected/actual/
            canonical_key).
        facet: the FacetAdapter for ``field.facet`` (None if unknown).
        mode: ``set`` or ``require``.
        device_info: registry info for the device (identity facts).

    Returns ``(ok, reason, warnings)`` — reason set only when not ok.
    """
    from admz.snapshot.ignore import applicable_rules, is_ignored

    warnings: List[str] = []
    if mode not in MODES:
        return False, f"unknown mode {mode!r}", warnings

    canonical = getattr(field, "canonical_key", None) or (
        facet.canonical_key(field.path) if facet else field.path
    )
    try:
        rules = applicable_rules(device_info.get("device_id") or "",
                                 device_info.get("tags"))
        if is_ignored(canonical, rules=rules):
            return False, "ignored", warnings
    except Exception:  # noqa: BLE001 — ignore-store failure shouldn't block capture
        pass

    if mode == MODE_SET:
        # param.cgi can't create keys — the demo must override, not invent (H2).
        if field.expected == MISSING:
            return False, "not-in-baseline", warnings
        if facet is None or facet.revert_param(field.path, field.actual) is None:
            return False, "read-only", warnings

    hits = device_local_hits(field.actual, device_info)
    if hits:
        warnings.append(
            f"{canonical}: value embeds this device's {'/'.join(hits)} — "
            "review before fulfilling the role with a different device")
    return True, "", warnings


# ── Mutation ─────────────────────────────────────────────────────────────────


def add_entries(
    git,
    demo,
    role: str,
    entries: List[Dict[str, str]],
    mode: str = MODE_SET,
) -> Optional[str]:
    """Merge ``[{facet, path, value}]`` into the role's fragment and commit.

    Returns the commit sha (None when nothing changed — same values already
    present).
    """
    role = normalize_role(role)
    rel = fragment_rel_path(demo.id, role)
    path = git._safe_rel_path(rel)
    doc: Dict[str, Any] = {}
    if path.exists():
        with open(path) as f:
            doc = yaml.safe_load(f) or {}
    doc["demo_name"] = demo.name
    facets = doc.setdefault("facets", {})

    changed = False
    for e in entries:
        bucket = facets.setdefault(e["facet"], {}).setdefault(mode, {})
        value = str(e["value"])
        if bucket.get(e["path"]) != value:
            bucket[e["path"]] = value
            changed = True
    if not changed:
        return None

    git.write_yaml(rel, doc)
    n = len(entries)
    return git.commit_snapshot(
        demo.id,
        message=(f"Demo '{demo.name}': assign {n} key{'s' if n != 1 else ''} "
                 f"to role '{role}'"),
    )


def remove_entries(
    git,
    demo,
    role: str,
    entries: List[Dict[str, str]],
) -> Optional[str]:
    """Drop ``[{facet, path}]`` from the role's fragment (both modes) and commit.

    Removes the file when it empties out; returns the commit sha or None."""
    role = normalize_role(role)
    rel = fragment_rel_path(demo.id, role)
    path = git._safe_rel_path(rel)
    if not path.exists():
        return None
    with open(path) as f:
        doc = yaml.safe_load(f) or {}
    facets = doc.get("facets") or {}

    changed = False
    for e in entries:
        fac = facets.get(e["facet"]) or {}
        for mode in MODES:
            if e["path"] in (fac.get(mode) or {}):
                del fac[mode][e["path"]]
                changed = True
        for mode in MODES:
            if mode in fac and not fac[mode]:
                del fac[mode]
        if e["facet"] in facets and not facets[e["facet"]]:
            del facets[e["facet"]]
    if not changed:
        return None

    if not facets:
        git.remove_path(rel)
    else:
        doc["facets"] = facets
        git.write_yaml(rel, doc)
    n = len(entries)
    return git.commit_snapshot(
        demo.id,
        message=(f"Demo '{demo.name}': remove {n} key{'s' if n != 1 else ''} "
                 f"from role '{role}'"),
    )


def delete_demo_fragments(git, demo_id: str, demo_name: str = "") -> Optional[str]:
    """Remove every fragment a demo owns (on demo delete). History survives."""
    from admz.validators import validate_identifier

    validate_identifier(demo_id, "demo_id")
    if git.remove_path(f"demos/{demo_id}"):
        return git.commit_snapshot(
            demo_id, message=f"Demo '{demo_name or demo_id}': deleted — remove fragments")
    return None
