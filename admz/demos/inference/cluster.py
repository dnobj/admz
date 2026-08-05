"""Clustering + scoring the evidence graph into demo **proposals** (#124, slice 3).

*Pure*, deterministic, no I/O — the same testability contract as
``modules/acs_pro/correlate.py``, ``demos/readiness.py`` and
:mod:`admz.demos.inference.graph`. Every input is handed in; nothing here reads
a device, a DB, git or ACS. :mod:`admz.demos.inference.collect` does the
gathering, :mod:`admz.demos.inference.proposals` does the storing.

The pipeline
------------
1. **Seed** — connected components over the graph's kept edges.
2. **Split** — a component larger than :data:`MAX_CLUSTER_DEVICES` or thinner
   than its density floor (:data:`DENSITY_MIN`, or the stricter
   :data:`DENSITY_MIN_CORROBORATING` when nothing relational holds it together)
   is cut, weakest link first, until every part satisfies both. Every cut is
   recorded as ``split`` evidence.
3. **Keep overlaps** — a device that bridged two parts is put back in **both**.
   ADR-0046 demos on the same device coexist by design (``0046-demos.md:59-61``);
   the only real exclusivity (same-key fragment overlap between *active* demos)
   is already enforced at adopt time with a 409. So an ambiguous hub is reported
   twice, never silently assigned to one side.
4. **Score** — the published formula below, with every term auditable.
5. **Name** — deterministically, so the whole feature works with no LLM at all.

The score (published, every term returned in ``score_breakdown``)
-----------------------------------------------------------------
::

    score = 0.40 · topology_cohesion   # min(1, topo_pairs / max(1, n-1))
          + 0.25 · rule_density        # min(1, named_rules / max(1, n))
          + 0.10 · name_cohesion       # members sharing the top token
          + 0.10 · tag_cohesion        # members sharing the most common tag
          + 0.15 · firing_recency      # 1.0 <7d, 0.5 <30d, 0 otherwise

``confidence = high (≥0.70) | medium (≥0.45) | low (<0.45)``, then capped:
a cluster with **no topology edge** is capped at ``low`` and flagged
``no_topology``; a run with **no ACS** carries ``acs_absent`` and an explicit
evidence line, and caps a topology-less cluster at ``medium`` (the ``low`` cap
above is stricter and wins — the line exists so the operator knows *why* the
evidence is thin rather than concluding the site has no demos).

Why ``include_weak`` defaults to **True**
-----------------------------------------
The plan assumed topology (an ACS rule triggering on A and acting on B) would be
the dominant signal and that name/tag-only clusters would be a rare, noisy tail
worth hiding by default. **The live fleet disproved that** (#124, slice 2): on
the reference site *every* ACS rule triggers and acts on the same device, so
there are **zero** topology edges and clustering runs entirely on corroborating
evidence (shared ACAP, name token, tag). Defaulting ``include_weak`` to False
there returns an empty list — the flagship "ADMZ already knows your demos"
moment would show nothing at all.

So the default is **surface, flag and cap**, not hide: weak clusters are
returned, flagged (``no_topology`` / ``name_only`` / ``acap_only`` /
``tag_only``), capped at ``low``, ordered below anything topology-backed, and
every one shows the exact evidence that produced it. ``include_weak=False``
remains available for a caller that only wants topology-backed proposals.

Firing recency is **best-effort**
---------------------------------
``firings`` maps a rule key to the epoch seconds it was last seen firing. It is
optional by design: the historical read behind it (ACS recording/alarm history,
the ADMZ event log) may be unavailable, disabled or empty, and a scoring term
that *fails* the run when its data source is missing would make the whole
feature depend on the most fragile input it has. Missing data degrades the term
to 0 and raises the ``firing_unknown`` flag, so a reader can tell "not seen"
from "not looked".

``acap_inventory_partial`` does **not** mean a read failed (#189)
-------------------------------------------------------------------
Any proposal whose evidence includes an E6 (shared-ACAP) edge is flagged
``acap_inventory_partial`` whenever the graph's known-app-inventory population
(``graph.known_app_total``) is smaller than the full device count — computed
fresh here from ``graph["nodes"]``, unconditionally, every run where that is
true.

It is tempting to read that flag as "something broke." **It does not mean
that.** ``graph.py``'s E6 distinctiveness test divides by the size of the
*known* population, and any device outside it — for ANY reason — shifts that
ratio for every other app. Two of the possible reasons are ordinary and
expected: a device that has never been snapshotted, or one that snapshotted
fine and genuinely has no installed ACAPs. A third reason, a failed facet
read, looks IDENTICAL to the second at every layer ADMZ has today (see
``capabilities.device_applications_detail``'s docstring). There is no
reliable way to tell a facet that failed to read apart from one that read
successfully and found nothing — inventing one would trade a false "unknown"
claim for a false "failed" or false "empty" one, so this flag does not try.
It reports only the one fact that is actually knowable: the population this
run's ACAP evidence was measured against was not the whole fleet, so an E6
edge here can look different on a re-run even if nothing about these specific
devices changed.
"""

from __future__ import annotations

import hashlib
import re
from typing import (AbstractSet, Any, Dict, Iterable, List, Optional, Sequence,
                    Set, Tuple)

from admz.demos.inference.graph import TOPOLOGY_EDGES, known_app_total, name_tokens

# ── split guard ─────────────────────────────────────────────────────────────
#: More members than this and the component is a hub blob, not a demo.
MAX_CLUSTER_DEVICES = 8
#: Pair density ``2·pairs / (n·(n−1))`` below this is a chain through a hub
#: rather than a group that genuinely belongs together.
DENSITY_MIN = 0.30
#: …and a stricter bar for a component held together by **corroborating
#: evidence only** (no topology pair anywhere inside it).
#:
#: Topology is relational — "this rule triggers on A and acts on B" is a fact
#: *about the pair*, so it chains meaningfully: A→B→C really is one mechanism.
#: Corroboration is not. "A and B both run objectanalytics" and "B and C both
#: run AudioManagerPro" say nothing whatsoever about A and C, yet connected
#: components will happily chain them into one "demo". Observed live on the
#: reference fleet (#124): six of eleven devices merged into a single blob
#: through exactly that accident, swallowing the one grouping a human would
#: actually name. So a group with no relational evidence has to be a group
#: *pairwise*, not a chain.
DENSITY_MIN_CORROBORATING = 0.60
#: How many links a cut device needs *into* a part before it rejoins it as a
#: shared member. One link is the coincidence the split just rejected; two or
#: more mean it is genuinely embedded in both groups.
OVERLAP_MIN_LINKS = 2

# ── score ───────────────────────────────────────────────────────────────────
W_TOPOLOGY = 0.40
W_RULE_DENSITY = 0.25
W_NAME = 0.10
W_TAG = 0.10
W_FIRING = 0.15

CONFIDENCE_HIGH = 0.70
CONFIDENCE_MEDIUM = 0.45

HIGH, MEDIUM, LOW = "high", "medium", "low"
_CONFIDENCE_RANK = {LOW: 0, MEDIUM: 1, HIGH: 2}

#: Firing-recency bands, in seconds.
FIRING_RECENT_SECONDS = 7 * 86400.0
FIRING_STALE_SECONDS = 30 * 86400.0

# ── flags ───────────────────────────────────────────────────────────────────
FLAG_NO_TOPOLOGY = "no_topology"
FLAG_ACS_ABSENT = "acs_absent"
FLAG_NAME_ONLY = "name_only"
FLAG_ACAP_ONLY = "acap_only"
FLAG_TAG_ONLY = "tag_only"
FLAG_SINGLE_DEVICE = "single_device"
FLAG_SPLIT = "split_from_larger_component"
FLAG_OVERLAP = "overlaps_another_proposal"
FLAG_FIRING_UNKNOWN = "firing_unknown"
FLAG_NAMES_ONLY_RULES = "names_only_rules"
FLAG_BLIND_RULES = "blind_rules"
FLAG_ACAP_INVENTORY_PARTIAL = "acap_inventory_partial"

#: Corroborating-edge id → the flag a cluster built from *only* that id earns.
_ONLY_FLAG = {"E5": FLAG_NAME_ONLY, "E6": FLAG_ACAP_ONLY, "E4": FLAG_TAG_ONLY}

# ── roles (free-form by design — ``store.py:54-55``) ────────────────────────
ROLE_DETECTOR = "detector"
ROLE_RECORDER = "recorder"
ROLE_RESPONDER = "responder"
ROLE_MEMBER = "member"

# ── deterministic naming ────────────────────────────────────────────────────
#: Trigger-topic substring → what the demo is *about*. Checked first, because a
#: topic says what is being detected; an action only says what happens next.
_TOPIC_HINTS = (
    ("loitering", "loitering detection"),
    ("fenceguard", "fence detection"),
    ("motionguard", "motion detection"),
    ("objectanalytics", "object detection"),
    ("object_analytics", "object detection"),
    ("vmd", "motion detection"),
    ("motionalarm", "motion detection"),
    ("motion", "motion detection"),
    ("detector", "detection"),
    ("audio", "audio"),
    ("virtualinput", "trigger"),
)
#: ACS/device action kind → what the demo *does*.
_ACTION_HINTS = (
    ("Record", "recording"),
    ("Alarm", "alert"),
    ("IO", "door control"),
    ("DoorStation", "door station"),
    ("HttpNotification", "notification"),
    ("MobileAppNotification", "notification"),
    ("Ptz", "PTZ"),
    ("PTZ", "PTZ"),
    ("LiveView", "live view"),
)
_DEFAULT_HINT = "demo"

# ── suggested owned keys (read-only evidence — resolved DECISION b) ─────────
#: Facets ``fragments.validate_assignment`` would refuse a ``set`` key on,
#: because they are not param-writable (``FacetAdapter.revert_param`` returns
#: None — ``snapshot/facets/base.py:108-120`` names these explicitly). Listed
#: anyway, flagged ``not_capturable``, so the report stays honest.
READ_ONLY_FACETS = frozenset({"action_rules", "applications", "users"})

#: Where an I/O port's configuration lives in the param tree.
_IO_PORT_PREFIX = "root.IOPort"

#: Analytics app (as named by ``capabilities._TOPIC_APP_HINTS``) → the param
#: root its scenario/profile configuration lives under. Only apps whose config
#: really is param-backed appear here; anything else is reported through the
#: read-only ``applications`` facet instead of inventing a key.
_ANALYTICS_PARAM_ROOT = {
    "vmd": "root.VMD",
    "objectanalytics": "root.ObjectAnalytics",
    "fenceguard": "root.FenceGuard",
    "loiteringguard": "root.LoiteringGuard",
    "motionguard": "root.MotionGuard",
}

_ACAP_TOPIC_RE = re.compile(r"CameraApplicationPlatform/([A-Za-z0-9_]+)")


def params() -> Dict[str, Any]:
    """Every clustering constant in force, echoed into the run's ``params_json``.

    Pinning them per run is what keeps an old proposal explainable after the
    weights are tuned — the same audit contract ``graph.params()`` keeps.
    """
    return {
        "max_cluster_devices": MAX_CLUSTER_DEVICES,
        "density_min": DENSITY_MIN,
        "density_min_corroborating": DENSITY_MIN_CORROBORATING,
        "overlap_min_links": OVERLAP_MIN_LINKS,
        "score_weights": {
            "topology_cohesion": W_TOPOLOGY,
            "rule_density": W_RULE_DENSITY,
            "name_cohesion": W_NAME,
            "tag_cohesion": W_TAG,
            "firing_recency": W_FIRING,
        },
        "confidence_thresholds": {"high": CONFIDENCE_HIGH,
                                  "medium": CONFIDENCE_MEDIUM},
        "firing_bands_seconds": {"recent": FIRING_RECENT_SECONDS,
                                 "stale": FIRING_STALE_SECONDS},
        "include_weak_default": True,
        "read_only_facets": sorted(READ_ONLY_FACETS),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. Seed clusters — connected components
# ═══════════════════════════════════════════════════════════════════════════

def _pairs(edges: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], float]:
    """Distinct device pairs → the strongest edge weight on that pair.

    Density and the split order are measured over **pairs**, not edge rows: two
    devices linked by both a shared tag and a shared app are one connection with
    two pieces of evidence, and counting it twice would let density exceed 1.
    """
    out: Dict[Tuple[str, str], float] = {}
    for e in edges or []:
        key = (e["a"], e["b"]) if e["a"] <= e["b"] else (e["b"], e["a"])
        out[key] = max(out.get(key, 0.0), float(e.get("weight") or 0.0))
    return out


def _components(members: Iterable[str],
                pairs: Iterable[Tuple[str, str]]) -> List[List[str]]:
    """Connected components, each sorted, the list itself sorted — determinism
    is a contract here, not a nicety (proposal ids are content-derived)."""
    parent: Dict[str, str] = {m: m for m in members}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        if a not in parent or b not in parent:
            continue
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    groups: Dict[str, List[str]] = {}
    for m in parent:
        groups.setdefault(find(m), []).append(m)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: (len(g), g))


def seed_clusters(nodes: Sequence[Dict[str, Any]],
                  edges: Sequence[Dict[str, Any]]) -> List[List[str]]:
    """Connected components over the kept edges — every node appears exactly
    once, including devices with no edge at all (their own singleton)."""
    ids = [str(n["device_id"]) for n in nodes or []]
    return _components(ids, _pairs(edges).keys())


# ═══════════════════════════════════════════════════════════════════════════
# 2. Split runaway components
# ═══════════════════════════════════════════════════════════════════════════

def density(members: Sequence[str], pairs: Dict[Tuple[str, str], float]) -> float:
    """``2·pairs / (n·(n−1))`` over the pairs internal to ``members``.

    A component of one or two devices is dense by definition (there is at most
    one pair to have), so it can never be split by density.
    """
    n = len(members)
    if n < 2:
        return 1.0
    inside = set(members)
    count = sum(1 for (a, b) in pairs if a in inside and b in inside)
    return (2.0 * count) / (n * (n - 1))


def density_floor(members: Sequence[str],
                  topo_pairs: AbstractSet[Tuple[str, str]]) -> float:
    """Which density bar this group has to clear — see
    :data:`DENSITY_MIN_CORROBORATING` for why the two differ."""
    inside = set(members)
    has_topology = any(a in inside and b in inside for a, b in topo_pairs)
    return DENSITY_MIN if has_topology else DENSITY_MIN_CORROBORATING


def _healthy(members: Sequence[str], pairs: Dict[Tuple[str, str], float],
             topo_pairs: AbstractSet[Tuple[str, str]] = frozenset()) -> bool:
    return (len(members) <= MAX_CLUSTER_DEVICES
            and density(members, pairs) >= density_floor(members, topo_pairs))


def split_component(members: Sequence[str],
                    pairs: Dict[Tuple[str, str], float],
                    topo_pairs: AbstractSet[Tuple[str, str]] = frozenset(),
                    ) -> Tuple[List[List[str]], List[Dict[str, Any]]]:
    """Cut a runaway component until every part is small **and** dense enough.

    The failure mode this exists for is one hub camera wired into everything:
    connected components would merge the whole site into a single "demo". Cuts
    happen weakest-link-first (weight ascending, then the sorted device-id pair)
    so the result is reproducible, and **every cut is returned** — the operator
    sees that the component was broken up and exactly where.

    ``topo_pairs`` names the pairs joined by a real rule link, which is what
    decides whether the part is judged at :data:`DENSITY_MIN` or the stricter
    :data:`DENSITY_MIN_CORROBORATING`.

    Returns ``(parts, cuts)``; ``parts`` is ``[[members], …]`` and each cut is
    ``{"a", "b", "weight", "detail"}``.
    """
    members = sorted(set(members))
    if _healthy(members, pairs, topo_pairs):
        return [list(members)], []

    inside = set(members)
    live = {p: w for p, w in pairs.items() if p[0] in inside and p[1] in inside}
    cuts: List[Dict[str, Any]] = []

    while True:
        parts = _components(members, live.keys())
        bad = [p for p in parts if not _healthy(p, live, topo_pairs)]
        if not bad:
            return sorted(parts, key=lambda p: (-len(p), p)), cuts
        # Work on the worst offender first; ties broken by the sorted id list.
        target = sorted(bad, key=lambda p: (-len(p), p))[0]
        tset = set(target)
        candidates = sorted(
            ((w, p) for p, w in live.items() if p[0] in tset and p[1] in tset),
            key=lambda item: (item[0], item[1]),
        )
        if not candidates:
            # No edges left to cut: the part is a set of singletons already.
            return sorted(parts, key=lambda p: (-len(p), p)), cuts
        weight, pair = candidates[0]
        floor = density_floor(target, topo_pairs)
        before = density(target, live)
        del live[pair]
        cuts.append({
            "a": pair[0], "b": pair[1], "weight": weight,
            "detail": (f"cut the weakest link ({pair[0]} ↔ {pair[1]}, weight "
                       f"{weight:.2f}) — the group had {len(target)} devices at "
                       f"density {before:.2f}, past the "
                       f"{MAX_CLUSTER_DEVICES}-device / {floor:.2f}-density "
                       "guard"
                       + (", and nothing but corroborating evidence held it "
                          "together, so it was a chain of coincidences rather "
                          "than one demo" if floor == DENSITY_MIN_CORROBORATING
                          else ", so it was a hub blob rather than one demo")),
        })


def reattach_bridges(parts: List[List[str]], cuts: List[Dict[str, Any]],
                     pairs: Dict[Tuple[str, str], float]) -> List[List[str]]:
    """Put a cut device back into **every** part its evidence still reaches.

    Splitting answers "these are not one demo"; it must not also answer "and
    this camera belongs to that side, not this one". A device that bridged two
    groups is genuinely in both — ADR-0046 says overlapping demos on one device
    are normal — so each endpoint of a cut rejoins any part it is genuinely
    embedded in: :data:`OVERLAP_MIN_LINKS` original links into that part (one
    link is the coincidence the split just rejected), and subject to
    :data:`MAX_CLUSTER_DEVICES` so re-attachment cannot rebuild the blob it just
    broke. Parts wholly contained in another part are dropped (the lone hub left
    behind by its own cuts is already represented).
    """
    if not cuts:
        return parts
    bridges = sorted({c["a"] for c in cuts} | {c["b"] for c in cuts})
    grown = [sorted(p) for p in parts]
    for device in bridges:
        for i, part in enumerate(grown):
            if device in part:
                continue
            if len(part) + 1 > MAX_CLUSTER_DEVICES:
                continue
            links = sum(1 for m in part
                        if (min(device, m), max(device, m)) in pairs)
            if links >= OVERLAP_MIN_LINKS:
                grown[i] = sorted(part + [device])
    # Drop any part that is now a subset of another (the stranded hub).
    kept: List[List[str]] = []
    for part in sorted(grown, key=lambda p: (-len(p), p)):
        pset = set(part)
        if any(pset < set(other) for other in kept):
            continue
        if pset in [set(k) for k in kept]:
            continue
        kept.append(part)
    return sorted(kept, key=lambda p: (-len(p), p))


# ═══════════════════════════════════════════════════════════════════════════
# 3. Rules, roles, tokens
# ═══════════════════════════════════════════════════════════════════════════

def rules_for(members: Set[str],
              rules: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every rule touching at least one member, in the graph's own order.

    Disabled rules are **included** (they are part of what this group is, and
    dropping them would hide automation the operator can see on the device) but
    they never counted toward an edge and never count toward ``rule_density``.
    """
    return [r for r in rules or [] if set(r.get("device_ids") or []) & members]


def assign_roles(members: Sequence[str],
                 rules: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    """``{device_id: role}`` from which side of a rule each device sits on.

    Precedence is most-specific-first: a device that **triggers** a rule is the
    ``detector`` even when it also records itself (the norm on the reference
    fleet — every ACS rule there triggers and acts on the same device); a device
    that is only a Record target is the ``recorder``; any other action target is
    a ``responder``. ``roles`` is free-form by design, so the operator can
    rename any of them after confirming.
    """
    triggers: Set[str] = set()
    recorders: Set[str] = set()
    responders: Set[str] = set()
    for rule in rules:
        triggers |= set(rule.get("trigger_device_ids") or [])
        targets = set(rule.get("action_device_ids") or [])
        responders |= targets
        if "Record" in (rule.get("action_kinds") or []):
            recorders |= targets
    out: Dict[str, str] = {}
    for did in sorted(members):
        if did in triggers:
            out[did] = ROLE_DETECTOR
        elif did in recorders:
            out[did] = ROLE_RECORDER
        elif did in responders:
            out[did] = ROLE_RESPONDER
        else:
            out[did] = ROLE_MEMBER
    return out


def _cluster_tokens(members: Sequence[str], by_id: Dict[str, Dict[str, Any]],
                    rules: Sequence[Dict[str, Any]]) -> Dict[str, Set[str]]:
    """``{token: {device_ids}}`` from member names **and** the names of the
    rules that touch them — the same two sources E5 draws on."""
    out: Dict[str, Set[str]] = {}
    for did in members:
        for tok in name_tokens((by_id.get(did) or {}).get("name")):
            out.setdefault(tok, set()).add(did)
    for rule in rules:
        if not rule.get("enabled"):
            continue
        for tok in name_tokens(rule.get("name")):
            for did in rule.get("device_ids") or []:
                if did in members:
                    out.setdefault(tok, set()).add(did)
    return out


def _top(counts: Dict[str, Set[str]]) -> Tuple[Optional[str], int]:
    """The most-shared key, ties broken alphabetically so it is reproducible."""
    if not counts:
        return None, 0
    key = sorted(counts, key=lambda k: (-len(counts[k]), k))[0]
    return key, len(counts[key])


# ═══════════════════════════════════════════════════════════════════════════
# 4. Score
# ═══════════════════════════════════════════════════════════════════════════

def firing_recency(rule_keys: Sequence[str], firings: Optional[Dict[str, float]],
                   now: Optional[float]) -> Tuple[float, Optional[float], str]:
    """``(term, last_seen, detail)`` — best-effort, degrades to 0.

    Returns ``last_seen=None`` when the historical read was unavailable or knew
    nothing about any of these rules; the caller raises ``firing_unknown`` so
    "we did not look" is never rendered as "it has not fired".
    """
    if not firings or now is None:
        return 0.0, None, ("no firing history available — the term scores 0 "
                           "(this is 'not looked', not 'not seen')")
    seen = [float(firings[k]) for k in rule_keys if firings.get(k)]
    if not seen:
        return 0.0, None, ("no firing history for these rules — the term scores "
                           "0 (this is 'not looked', not 'not seen')")
    last = max(seen)
    age = max(0.0, float(now) - last)
    if age < FIRING_RECENT_SECONDS:
        return 1.0, last, f"a rule fired {age / 86400.0:.1f} day(s) ago"
    if age < FIRING_STALE_SECONDS:
        return 0.5, last, f"a rule last fired {age / 86400.0:.1f} day(s) ago"
    return 0.0, last, f"nothing has fired for {age / 86400.0:.0f} day(s)"


def score_cluster(members: Sequence[str], internal_edges: Sequence[Dict[str, Any]],
                  rules: Sequence[Dict[str, Any]],
                  by_id: Dict[str, Dict[str, Any]], *,
                  firings: Optional[Dict[str, float]] = None,
                  now: Optional[float] = None) -> Dict[str, Any]:
    """The published score plus **every** term, so the number is never a claim
    the operator has to take on faith."""
    n = max(1, len(members))
    member_set = set(members)

    topo_pairs = {(e["a"], e["b"]) for e in internal_edges
                  if e["id"] in TOPOLOGY_EDGES}
    topology = min(1.0, len(topo_pairs) / max(1, n - 1))

    named = [r for r in rules if r.get("enabled") and (r.get("name") or "").strip()]
    rule_density = min(1.0, len(named) / n)

    tokens = _cluster_tokens(sorted(member_set), by_id, rules)
    top_token, token_members = _top(tokens)
    name_cohesion = token_members / n if top_token else 0.0

    tag_counts: Dict[str, Set[str]] = {}
    for did in sorted(member_set):
        for tag in (by_id.get(did) or {}).get("tags") or []:
            tag_counts.setdefault(str(tag), set()).add(did)
    top_tag, tag_members = _top(tag_counts)
    tag_cohesion = tag_members / n if top_tag else 0.0

    firing, last_seen, firing_detail = firing_recency(
        [r.get("rule_key") or "" for r in rules], firings, now)

    terms = [
        {"name": "topology_cohesion", "weight": W_TOPOLOGY, "value": round(topology, 4),
         "contribution": round(W_TOPOLOGY * topology, 4),
         "detail": (f"{len(topo_pairs)} cross-device rule link(s) over "
                    f"{max(1, n - 1)} needed to connect {n} device(s)")},
        {"name": "rule_density", "weight": W_RULE_DENSITY,
         "value": round(rule_density, 4),
         "contribution": round(W_RULE_DENSITY * rule_density, 4),
         "detail": f"{len(named)} enabled named rule(s) across {n} device(s)"},
        {"name": "name_cohesion", "weight": W_NAME, "value": round(name_cohesion, 4),
         "contribution": round(W_NAME * name_cohesion, 4),
         "detail": (f"{token_members} of {n} share the name token "
                    f"'{top_token}'" if top_token
                    else "no shared name token")},
        {"name": "tag_cohesion", "weight": W_TAG, "value": round(tag_cohesion, 4),
         "contribution": round(W_TAG * tag_cohesion, 4),
         "detail": (f"{tag_members} of {n} share the tag #{top_tag}" if top_tag
                    else "no shared tag")},
        {"name": "firing_recency", "weight": W_FIRING, "value": round(firing, 4),
         "contribution": round(W_FIRING * firing, 4), "detail": firing_detail},
    ]
    score = round(sum(t["contribution"] for t in terms), 4)
    return {
        "score": score, "terms": terms, "top_token": top_token, "top_tag": top_tag,
        "topology_pairs": len(topo_pairs), "named_rule_count": len(named),
        "firing_last_seen": last_seen, "firing_known": last_seen is not None,
    }


def confidence_for(score: float) -> str:
    if score >= CONFIDENCE_HIGH:
        return HIGH
    if score >= CONFIDENCE_MEDIUM:
        return MEDIUM
    return LOW


def _cap(current: str, ceiling: str) -> str:
    return current if _CONFIDENCE_RANK[current] <= _CONFIDENCE_RANK[ceiling] else ceiling


# ═══════════════════════════════════════════════════════════════════════════
# 5. Deterministic naming
# ═══════════════════════════════════════════════════════════════════════════

def _hint(rules: Sequence[Dict[str, Any]]) -> str:
    """What this group is *about*, from its rules' topics then their actions."""
    topics = " ".join(t for r in rules for t in (r.get("topics") or [])).lower()
    for needle, hint in _TOPIC_HINTS:
        if needle in topics:
            return hint
    kinds = {k for r in rules for k in (r.get("action_kinds") or [])}
    for needle, hint in _ACTION_HINTS:
        if needle in kinds:
            return hint
    return _DEFAULT_HINT


def deterministic_name(members: Sequence[str], by_id: Dict[str, Dict[str, Any]],
                       rules: Sequence[Dict[str, Any]],
                       top_token: Optional[str], top_tag: Optional[str]) -> str:
    """A name that needs no LLM.

    Stored **always**, so inference works with the model switched off, and shown
    beside the evidence as the *proposed* name so an agent's later rewrite is
    never mistaken for a fact.
    """
    n = len(members)
    hint = _hint(rules)
    if top_token:
        if top_token in hint:
            return hint[:1].upper() + hint[1:]
        return f"{top_token.title()} {hint}"
    if top_tag and n > 1:
        return f"#{top_tag} {hint} ({n} devices)"
    models = [str((by_id.get(d) or {}).get("model") or "").strip() for d in members]
    model = next((m for m in models if m), "")
    label = model or str((by_id.get(members[0]) or {}).get("name") or members[0])
    return f"{label} {hint}" if n == 1 else f"{label} {hint} ({n} devices)"


def uniquify(names: Sequence[str]) -> List[str]:
    """Disambiguate repeats in order — a demo name must stay resolvable, and
    ``actions.resolve_demo`` treats a duplicate name as ambiguous."""
    seen: Dict[str, int] = {}
    out: List[str] = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        out.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 6. Suggested owned keys — READ-ONLY evidence (resolved DECISION b)
# ═══════════════════════════════════════════════════════════════════════════

def _acap_from_topic(topic: str) -> Optional[str]:
    """The ACAP named directly inside a CameraApplicationPlatform topic."""
    m = _ACAP_TOPIC_RE.search(topic or "")
    return m.group(1) if m else None


def suggested_owned_keys(members: Sequence[str],
                         rules: Sequence[Dict[str, Any]],
                         by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Config the linked rules *depend on* — evidence, never a fragment write.

    Confirming a proposal creates the demo with an **empty** fragment set
    (resolved DECISION b): capture only accepts keys that are currently drifted
    (``actions.py:179`` skips ``not-drifted``; ``fragments.py:177-180`` refuses
    ``not-in-baseline``), and at first run the baseline is snapshotted *from*
    live state, so nothing is capturable yet. Listing the keys is still worth
    doing — it is how the operator sees what the demo probably owns — so each
    entry carries its ``reason`` and, when
    :func:`admz.demos.fragments.validate_assignment` would refuse it, a
    ``not_capturable`` flag with the reason it would be refused.
    """
    member_set = set(members)
    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str]] = set()

    def add(device_id: str, facet: str, path: str, reason: str) -> None:
        if device_id not in member_set:
            return
        key = (device_id, facet, path)
        if key in seen:
            return
        seen.add(key)
        entry = {"device_id": device_id, "facet": facet, "path": path,
                 "reason": reason, "not_capturable": facet in READ_ONLY_FACETS}
        if entry["not_capturable"]:
            entry["not_capturable_reason"] = (
                f"the '{facet}' facet is not param-writable, so capture would "
                "refuse it as read-only — it is listed as evidence only")
        out.append(entry)

    macs = {str((by_id.get(d) or {}).get("mac") or ""): d for d in members
            if (by_id.get(d) or {}).get("mac")}

    for rule in rules:
        rule_name = rule.get("name") or rule.get("rule_id") or "rule"
        triggers = [d for d in (rule.get("trigger_device_ids") or [])
                    if d in member_set]

        # 1 ── the trigger topic names, or needs, an application
        for topic in rule.get("topics") or []:
            app = _acap_from_topic(topic)
            publisher = next((g.get("app") for g in rule.get("app_grounding") or []
                              if g.get("topic") == topic and g.get("app")), None)
            for did in triggers:
                if app or publisher:
                    named = app or publisher
                    add(did, "applications", str(named),
                        f"trigger topic {topic} is produced by {named}")
                # 2 ── motion / object detection: the detector's own scenario
                #      and profile keys are what make the demo behave.
                root = _ANALYTICS_PARAM_ROOT.get(str(publisher or "").lower())
                if root:
                    add(did, "other", f"{root}.*",
                        f"rule triggers on {publisher} for this device — its "
                        "scenario/profile configuration is what the demo depends on")

        # 3 ── an I/O action drives an output port on the target device
        if "IO" in (rule.get("action_kinds") or []):
            ports = {ch.get("device_mac"): ch.get("port")
                     for ch in ((rule.get("observability") or {}).get("channels") or [])
                     if ch.get("channel") == "device_event"}
            for did in sorted(set(rule.get("action_device_ids") or []) & member_set):
                port = next((p for mac, p in ports.items()
                             if macs.get(str(mac or "")) == did), None)
                path = (f"{_IO_PORT_PREFIX}.I{port}.*" if port not in (None, "")
                        else f"{_IO_PORT_PREFIX}.*")
                add(did, "other", path,
                    f"rule '{rule_name}' drives output port "
                    + (str(port) if port not in (None, "") else "(port not resolved)")
                    + " on this device")

        # 4 ── a device-side rule is itself part of the chain
        if rule.get("source") == "device" and rule.get("owner_device_id"):
            add(rule["owner_device_id"], "action_rules", str(rule.get("rule_id")),
                f"demo's rule chain includes this device rule ('{rule_name}')")

    out.sort(key=lambda e: (e["device_id"], e["facet"], e["path"]))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 7. Propose
# ═══════════════════════════════════════════════════════════════════════════

def proposal_id(run_id: str, members: Sequence[str]) -> str:
    """``sha1(run_id + sorted member ids)[:12]`` — the plan's formula verbatim.

    Content-derived, so the **same** run over the same members always mints the
    same id, and two runs never collide on a primary key while both stay on the
    record. Stability *across* runs is carried by
    :func:`content_key`, which is what supersede and the dismissal memory join
    on — an id must stay unique per run for the run history to mean anything.
    """
    raw = f"{run_id}|" + ",".join(sorted(members))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def content_key(members: Sequence[str]) -> str:
    """``sha1(sorted member ids)`` — the same environment yields the same key on
    every run. Supersede and "don't re-propose what was dismissed" join on it."""
    return hashlib.sha1(",".join(sorted(members)).encode("utf-8")).hexdigest()[:16]


def _rule_entry(rule: Dict[str, Any], members: Set[str]) -> Dict[str, Any]:
    """One membership entry, in the shape ``attach_rule_to_demo`` already takes.

    ``source`` is the additive field this slice introduces (``"device"`` |
    ``"acs"``): an ACS rule has no ADMZ device rule to observe, so
    ``wizard._rules_status`` must not report it as a rule that vanished.
    """
    if rule.get("source") == "device":
        device_id = rule.get("owner_device_id") or ""
    else:
        candidates = [d for d in (rule.get("trigger_device_ids") or []) if d in members]
        if not candidates:
            candidates = [d for d in (rule.get("action_device_ids") or [])
                          if d in members]
        device_id = candidates[0] if candidates else ""
    topics = rule.get("topics") or []
    return {
        "source": rule.get("source") or "device",
        "device_id": device_id,
        "rule_id": str(rule.get("rule_id") or ""),
        "rule_name": rule.get("name") or "",
        "rule_key": rule.get("rule_key") or "",
        "condition_id": rule.get("condition_id") or "",
        "condition_topic": topics[0] if topics else "",
        "topics": topics,
        "actions": list(rule.get("action_kinds") or []),
        "enabled": bool(rule.get("enabled", True)),
        "names_only": bool(rule.get("names_only")),
        "device_ids": sorted(set(rule.get("device_ids") or []) & members),
        "observability": rule.get("observability") or None,
    }


def _evidence(kind: str, detail: str, *, weight: float = 0.0,
              source: str = "") -> Dict[str, Any]:
    return {"kind": kind, "weight": round(float(weight), 4), "detail": detail,
            "source": source}


def propose(graph: Dict[str, Any], *, run_id: str = "",
            include_weak: bool = True,
            firings: Optional[Dict[str, float]] = None,
            now: Optional[float] = None) -> Dict[str, Any]:
    """Cluster the evidence graph into scored proposals. Pure and deterministic.

    Returns ``{"proposals": [...], "params": {...}, "report": {...}}``. The
    report explains everything that did **not** become a proposal, so an empty
    or thin result is always accountable rather than mysterious.
    """
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    all_rules = list(graph.get("rules") or [])
    acs = graph.get("acs") or {}
    acs_available = bool(acs.get("available"))
    by_id = {str(n["device_id"]): n for n in nodes}
    pairs = _pairs(edges)
    # Computed once, from the graph's own nodes — not from `graph["summary"]`,
    # which a caller (or a test fixture) may not have populated. Whether this
    # is < len(nodes) is the one fact the acap_inventory_partial flag reports;
    # see the module docstring for why it is unconditional on that alone.
    acap_known_total = known_app_total(nodes)

    skipped: List[Dict[str, Any]] = []
    weak_hidden = 0

    clusters: List[Dict[str, Any]] = []
    topo_pairs = {(e["a"], e["b"]) for e in edges if e["id"] in TOPOLOGY_EDGES}
    for component in seed_clusters(nodes, edges):
        parts, cuts = split_component(component, pairs, topo_pairs)
        parts = reattach_bridges(parts, cuts, pairs)
        for part in parts:
            clusters.append({"members": part, "cuts": cuts if len(parts) > 1 else []})

    drafts: List[Dict[str, Any]] = []
    for cluster in clusters:
        members = cluster["members"]
        member_set = set(members)
        rules = rules_for(member_set, all_rules)
        named = [r for r in rules if r.get("enabled") and (r.get("name") or "").strip()]

        # A one-device demo is legitimate (a speaker announcement) — but only
        # when something actually says so. A device with no rule and no
        # distinctive link is just a device, and proposing it would turn the
        # inventory into confetti.
        if len(members) == 1 and not named:
            skipped.append({
                "device_ids": members, "reason": "single device with no named rule",
                "detail": (f"{(by_id.get(members[0]) or {}).get('name') or members[0]} "
                           "has no enabled named rule and no link to another "
                           "device — nothing here says it is part of a demo"),
            })
            continue

        internal = [e for e in edges
                    if e["a"] in member_set and e["b"] in member_set]
        breakdown = score_cluster(members, internal, rules, by_id,
                                  firings=firings, now=now)
        score = breakdown["score"]
        confidence = confidence_for(score)

        flags: List[str] = []
        evidence: List[Dict[str, Any]] = []

        for edge in internal:
            for item in edge.get("evidence") or []:
                evidence.append(_evidence(
                    f"edge:{edge['id']}", item.get("detail") or "",
                    weight=edge.get("weight") or 0.0,
                    source=item.get("source") or edge["id"]))
        for cut in cluster["cuts"]:
            evidence.append(_evidence("split", cut["detail"],
                                      weight=cut.get("weight") or 0.0,
                                      source="split-guard"))
        if cluster["cuts"]:
            flags.append(FLAG_SPLIT)

        edge_ids = {e["id"] for e in internal}
        topo = edge_ids & set(TOPOLOGY_EDGES)
        if len(members) == 1:
            flags.append(FLAG_SINGLE_DEVICE)
            evidence.append(_evidence(
                "structure",
                "one device — a single-device demo is legitimate (a speaker "
                "announcement, a camera that both detects and records), and it "
                "is proposed because it carries at least one named rule",
                source="cluster"))
        elif not topo:
            flags.append(FLAG_NO_TOPOLOGY)
            only = sorted(_ONLY_FLAG[i] for i in edge_ids if i in _ONLY_FLAG)
            if len(edge_ids) == 1 and only:
                flags.append(only[0])
            evidence.append(_evidence(
                "structure",
                "no rule links these devices to each other — they are grouped on "
                "corroborating evidence alone (shared tag, app or name), so this "
                "is a suggestion to check, not a conclusion",
                source="cluster"))
            confidence = _cap(confidence, LOW)

        if not acs_available:
            flags.append(FLAG_ACS_ABSENT)
            evidence.append(_evidence(
                "degradation",
                "ACS not connected — no cross-device rule topology available. "
                + str(acs.get("reason") or ""),
                source="acs"))
            if not topo:
                confidence = _cap(confidence, MEDIUM)

        # Unconditional on whether the known population is partial — NOT on
        # detecting why (#189; see the module docstring). Present exactly
        # when it is true, absent exactly when the fleet's app inventory is
        # complete — it does not fire just because this cluster has an E6
        # edge, and it does not fire on every cluster just because SOME
        # device's inventory is unknown elsewhere in the fleet.
        if "E6" in edge_ids and acap_known_total < len(nodes):
            flags.append(FLAG_ACAP_INVENTORY_PARTIAL)
            evidence.append(_evidence(
                "degradation",
                f"only {acap_known_total} of {len(nodes)} fleet devices have a "
                "known application inventory this run — the shared-app "
                "evidence above is measured against that population, not the "
                "whole fleet, and can look different on a re-run if it "
                "changes. This does not mean a read failed — ADMZ cannot "
                "currently tell that apart from a device that was never "
                "snapshotted or one that genuinely has no apps installed.",
                source="applications"))

        if not breakdown["firing_known"]:
            flags.append(FLAG_FIRING_UNKNOWN)
        if any(r.get("names_only") for r in rules):
            flags.append(FLAG_NAMES_ONLY_RULES)
            evidence.append(_evidence(
                "rules",
                "some rules came from the older SOAP path (AXIS OS < 12) and "
                "carry names only — no condition or action detail to reason over",
                source="firmware"))
        blind = [r for r in rules if (r.get("observability") or {}).get("blind")]
        if blind:
            flags.append(FLAG_BLIND_RULES)
            evidence.append(_evidence(
                "observability",
                f"{len(blind)} rule(s) have no observable firing channel — ADMZ "
                "cannot tell when they run (#127 remediation is out of scope here)",
                source="observability"))

        evidence.append(_evidence(
            "rules",
            f"{len(named)} enabled named rule(s) touch these devices"
            + (f", {len(rules) - len(named)} more disabled or unnamed"
               if len(rules) > len(named) else ""),
            source="rules"))

        if include_weak is False and FLAG_NO_TOPOLOGY in flags:
            weak_hidden += 1
            continue

        rule_entries = [_rule_entry(r, member_set) for r in rules]
        name = deterministic_name(members, by_id, rules,
                                  breakdown["top_token"], breakdown["top_tag"])
        drafts.append({
            "members": members, "name": name, "score": score,
            "confidence": confidence, "flags": sorted(set(flags)),
            "evidence": evidence, "rules": rule_entries,
            "roles": assign_roles(members, rules),
            "score_breakdown": breakdown,
            "suggested_owned_keys": suggested_owned_keys(members, rules, by_id),
            "devices": [{"device_id": d,
                         "name": (by_id.get(d) or {}).get("name") or d,
                         "model": (by_id.get(d) or {}).get("model") or "",
                         "tags": (by_id.get(d) or {}).get("tags") or []}
                        for d in members],
        })

    # Order: strongest first, then by name, then by members — reproducible.
    drafts.sort(key=lambda p: (-p["score"], p["name"], p["members"]))
    for draft, name in zip(drafts, uniquify([d["name"] for d in drafts])):
        draft["name"] = name
        draft["id"] = proposal_id(run_id, draft["members"])
        draft["content_key"] = content_key(draft["members"])
        draft["run_id"] = run_id

    # Overlaps are recorded on BOTH sides, never resolved to one.
    for draft in drafts:
        mine = set(draft["members"])
        overlaps = []
        for other in drafts:
            if other is draft:
                continue
            shared = sorted(mine & set(other["members"]))
            if shared:
                overlaps.append({"proposal_id": other["id"], "name": other["name"],
                                 "device_ids": shared})
        draft["overlaps"] = overlaps
        if overlaps:
            draft["flags"] = sorted(set(draft["flags"]) | {FLAG_OVERLAP})
            names = ", ".join(o["name"] for o in overlaps)
            draft["evidence"].append(_evidence(
                "overlap",
                f"shares {', '.join(o['device_ids'][0] for o in overlaps)} with "
                f"{names} — kept in both on purpose: demos on the same device "
                "coexist by design (ADR-0046), and only same-key config overlap "
                "between ACTIVE demos is exclusive",
                source="overlap"))

    return {
        "proposals": drafts,
        "params": params(),
        "report": {
            "cluster_count": len(clusters),
            "proposal_count": len(drafts),
            "skipped": skipped,
            "weak_hidden": weak_hidden,
            "include_weak": bool(include_weak),
            "acs_available": acs_available,
            "acs_reason": str(acs.get("reason") or ""),
            "firing_history": ("available" if firings else "unavailable"),
            "note": _report_note(drafts, skipped, weak_hidden, include_weak,
                                 acs_available),
        },
    }


def _report_note(drafts: List[Dict[str, Any]], skipped: List[Dict[str, Any]],
                 weak_hidden: int, include_weak: bool,
                 acs_available: bool) -> str:
    """One sentence saying why the result looks the way it does — an empty list
    must never be indistinguishable from a broken run."""
    if drafts:
        weak = sum(1 for d in drafts if FLAG_NO_TOPOLOGY in d["flags"])
        parts = [f"{len(drafts)} proposal(s)"]
        if weak:
            parts.append(f"{weak} built on corroborating evidence only (capped "
                         "at low confidence — check them, don't trust them)")
        if skipped:
            parts.append(f"{len(skipped)} device(s) left out for having no rule "
                         "and no link")
        return "; ".join(parts) + "."
    if weak_hidden:
        return (f"{weak_hidden} cluster(s) were found but every one rests on "
                "corroborating evidence alone, and include_weak was false — "
                "re-run with include_weak to see them.")
    if skipped:
        return ("No group of devices is linked by any rule, tag, app or name, "
                f"and {len(skipped)} device(s) carry no named rule either — "
                "there is nothing here that looks like a demo yet.")
    if not acs_available:
        return ("Nothing to propose: no device rules were readable and ACS is "
                "not connected, so there is no evidence to cluster.")
    return "Nothing to propose — the fleet has no rules, tags, apps or names to cluster on."


__all__ = [
    "MAX_CLUSTER_DEVICES", "DENSITY_MIN", "params", "seed_clusters", "density",
    "split_component", "reattach_bridges", "rules_for", "assign_roles",
    "DENSITY_MIN_CORROBORATING", "density_floor",
    "score_cluster", "confidence_for", "firing_recency", "deterministic_name",
    "uniquify", "suggested_owned_keys", "proposal_id", "content_key", "propose",
]
