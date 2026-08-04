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
        # ADR-0047 Guard 3, BOTH halves: param.cgi can create no key and delete
        # none, so a `set` fragment overrides an existing key — it never invents
        # one and never removes one. Both endpoints of the diff must therefore be
        # real values the device actually had.
        #
        # absent from the baseline -> the fragment would have to CREATE the key.
        if field.expected == MISSING:
            return False, "not-in-baseline", warnings
        if facet is None or facet.revert_param(field.path, field.actual) is None:
            return False, "read-only", warnings
        # absent from the device -> the fragment would have to DELETE the key,
        # and the value captured would be the sentinel itself, which is a value
        # to nothing. Once such a fragment is adopted, `attribution_maps`
        # registers want="<missing>" and drift.py's `actual == want` is then
        # satisfied precisely WHILE the key stays deleted — bucketing it
        # `demo_set` and dropping it from real_fields. A key deleted from a
        # production device would be relabelled deliberate demo config and never
        # reported as drift again (#208).
        #
        # Deliberately AFTER the read-only gate. A key that is both read-only
        # and vanished is not capturable on the more fundamental ground, and
        # "read-only" is the honest reason — "vanished-from-device" would advise
        # a revert that a Volatile*/excluded key cannot receive either. The gate
        # above cannot substitute for this one, though: `is_restorable` screens
        # only MASKED_SECRET, Volatile* and per-facet excludes, so for an
        # ordinary writable key revert_param(path, "<missing>") returns a
        # perfectly normal write tuple and the sentinel sails through.
        if field.actual == MISSING:
            return False, "vanished-from-device", warnings

    hits = device_local_hits(field.actual, device_info)
    if hits:
        warnings.append(
            f"{canonical}: value embeds this device's {'/'.join(hits)} — "
            "review before fulfilling the role with a different device")
    return True, "", warnings


# ── Attribution (drift-time overlay, ADR-0047 slice 2) ──────────────────────


def demo_covers_device(demo, device_info: Dict[str, Any]) -> bool:
    """Same scope semantics as ``service.resolve_devices``: tag wins."""
    if demo.tag:
        return demo.tag in (device_info.get("tags") or [])
    return (device_info.get("device_id") or "") in (demo.device_ids or [])


def _set_map_for(git, demo, device_id: str) -> Dict[Tuple[str, str], str]:
    """The demo's owned ``{(facet, path): value}`` for this device's role."""
    role = normalize_role((demo.roles or {}).get(device_id))
    facets = load_fragment(git, demo.id, role)
    out: Dict[Tuple[str, str], str] = {}
    for facet_name, modes in (facets or {}).items():
        for path, value in (modes.get(MODE_SET) or {}).items():
            out[(facet_name, path)] = str(value)
    return out


def attribution_maps(
    git,
    demos: List[Any],
    device_id: str,
    device_info: Dict[str, Any],
) -> Tuple[Dict[Tuple[str, str], Tuple[str, str, str]],
           Dict[Tuple[str, str], List[Dict[str, str]]]]:
    """The two lookups drift attribution needs for one device.

    Returns ``(owned, candidates)``:
      owned      — {(facet, path): (value, demo_id, demo_name)} from ACTIVE
                   demos covering this device. Two active demos claiming the
                   same key is prevented at adopt time; if it happens anyway,
                   the winner is deterministic (name order) and logged.
      candidates — {(facet, path): [{"id", "name", "value"}]} from INACTIVE
                   demos — "this change looks like demo Y".
    """
    owned: Dict[Tuple[str, str], Tuple[str, str, str]] = {}
    candidates: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    for demo in sorted(demos, key=lambda d: (d.name or "", d.id)):
        if not demo_covers_device(demo, device_info):
            continue
        try:
            set_map = _set_map_for(git, demo, device_id)
        except Exception:  # noqa: BLE001 — a bad fragment must not break drift
            logger.warning("demo %s: fragment unreadable during attribution",
                           demo.id, exc_info=True)
            continue
        for key, value in set_map.items():
            if getattr(demo, "active", False):
                if key in owned and owned[key][1] != demo.id:
                    logger.warning(
                        "demos %s and %s both claim %s on %s — keeping %s",
                        owned[key][2], demo.name, key, device_id, owned[key][2])
                    continue
                owned[key] = (value, demo.id, demo.name)
            else:
                candidates.setdefault(key, []).append(
                    {"id": demo.id, "name": demo.name, "value": value})
    return owned, candidates


def owning_demos(
    git, demos: List[Any], device_id: str, device_info: Dict[str, Any],
) -> List[Tuple[Any, int]]:
    """ACTIVE demos that own ≥1 set-key on this device — the accept-baseline
    guard (H1): blessing an observation while these are loaded would bake
    their config into base forever."""
    out = []
    for demo in demos:
        if not getattr(demo, "active", False):
            continue
        if not demo_covers_device(demo, device_info):
            continue
        n = len(_set_map_for(git, demo, device_id))
        if n:
            out.append((demo, n))
    return out


def overlap_conflicts(
    git, demo, other_active: List[Any], registry,
) -> List[Dict[str, str]]:
    """Keys where ``demo`` and another ACTIVE demo both claim the same
    (device, facet, path) — v1 forbids ALL same-key overlap, even equal
    values, so deactivation is trivially 'push base'."""
    from admz.demos.service import resolve_devices

    conflicts: List[Dict[str, str]] = []
    for d in resolve_devices(demo, registry):
        did = d.get("device_id") or ""
        mine = _set_map_for(git, demo, did)
        if not mine:
            continue
        for other in other_active:
            if other.id == demo.id or not demo_covers_device(other, d):
                continue
            theirs = _set_map_for(git, other, did)
            for key in set(mine) & set(theirs):
                conflicts.append({
                    "device_id": did, "facet": key[0], "path": key[1],
                    "other_demo": other.name,
                })
    return conflicts


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
