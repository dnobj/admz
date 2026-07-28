"""The demo-inference **evidence graph** (#124, slice 2) — *pure*, no I/O.

Same testability contract as ``modules/acs_pro/correlate.py`` and
``demos/readiness.py``: every input is handed in, nothing is read from a device,
a DB, git or ACS. :mod:`admz.demos.inference.collect` does the gathering; this
module turns what it gathered into the graph.

What the graph is
-----------------
*Nodes* are ADMZ registry devices. *Rules* come from two sources — ACS action
rules (``firebird.rule_anatomy``) and device-side action rules (the
``action_rules`` snapshot facet) — normalized into **one shape** carrying
``source: "acs" | "device"``. Every device reference a rule makes is resolved to
an ADMZ ``device_id`` through :func:`admz.device_registry.canonical_mac`,
recording **how** it matched (``join_method``); a reference that fails to resolve
lands in ``unresolved[]``. Nothing is ever dropped silently.

*Edges* connect two devices, each carrying the evidence that produced it:

===== ================================================== ======== ============
id    signal                                              weight   class
===== ================================================== ======== ============
E1    ACS rule triggering on A and acting on B            1.00     topology
E2    A and B named by the same ACS rule                  0.90     topology
E3    device rule on A whose action references B          0.80     topology
E4    shared non-trivial ADMZ tag (ADR-0032)              0.50     grouping
E6    shared *distinctive* ACAP                           0.40–.45 capability
E5    distinctive shared name token                       0.40     naming
===== ================================================== ======== ============

E4/E5/E6 are **corroborating** evidence only — a cluster built from them alone
has no topology behind it, so every such edge is flagged ``corroborating: true``
and slice 3 caps those clusters (the plan's ``no_topology`` treatment).

A **disabled** rule produces no edge of any class. It is history — it says these
devices *were* wired together, never that they currently work together — so it
stays in ``rules[]`` (visible, with its device references still resolved) but
contributes nothing to the evidence. The exclusion is counted in
``summary.disabled_rules`` rather than being silent.

Distinctiveness is **self-calibrating**, never a hardcoded list: both name tokens
(E5) and ACAPs (E6) are filtered by their document frequency across *this run's*
fleet, so a bundled app or a house-style naming prefix that sits on every device
carries no signal, while an unusual one does. An empty ``applications`` facet
means **unknown**, not "no apps" (``rules/capabilities.py:150-165`` is explicit),
and unknown never creates or suppresses an edge.

Clustering, scoring and proposals are deliberately **not** here — that is slice 3.
This module outputs the graph plus per-rule detail and stops.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from admz.device_registry import canonical_mac
from admz.demos.inference.observability import classify_rule
from admz.rules.capabilities import condition_caution, publisher_app_for

# ── edge weights ────────────────────────────────────────────────────────────
E1_WEIGHT = 1.00   # ACS rule: triggers on A, acts on B — the strongest signal
E2_WEIGHT = 0.90   # ACS rule names both A and B (multi-trigger / multi-target)
E3_WEIGHT = 0.80   # device rule on A whose action references B's identity
E4_WEIGHT = 0.50   # shared non-trivial ADMZ tag
E6_WEIGHT = 0.45   # shared distinctive ACAP — the ceiling, scaled by rarity
E5_WEIGHT = 0.40   # distinctive shared name token

#: Edges strictly below this are dropped. E5 sits exactly on it by design.
EDGE_MIN = 0.40

#: Floor of the E6 rarity band. An ACAP right at the ubiquity threshold is worth
#: no more than a shared name token; a genuinely rare one earns the full 0.45.
E6_WEIGHT_FLOOR = 0.40

EDGE_CLASSES = {"E1": "topology", "E2": "topology", "E3": "topology",
                "E4": "grouping", "E5": "naming", "E6": "capability"}
EDGE_WEIGHTS = {"E1": E1_WEIGHT, "E2": E2_WEIGHT, "E3": E3_WEIGHT,
                "E4": E4_WEIGHT, "E5": E5_WEIGHT, "E6": E6_WEIGHT}
#: Edge ids that count as real topology — the rest only corroborate.
TOPOLOGY_EDGES = frozenset({"E1", "E2", "E3"})

# ── E5: distinctive name tokens ─────────────────────────────────────────────
NAME_TOKEN_MIN_LEN = 4
#: A token must name at least this many devices to be a shared signal at all…
NAME_TOKEN_MIN_DEVICES = 2
#: …and at most this fraction of the fleet, or it is house style, not a demo.
NAME_TOKEN_MAX_FRACTION = 0.40
NAME_STOPWORDS = frozenset({
    "axis", "rule", "rules", "camera", "cameras", "test", "new", "demo", "demos",
    "default", "predefined", "device", "devices", "action", "actions", "event",
    "events", "trigger", "triggers", "record", "recording", "alarm", "notify",
    "notification", "http", "https", "port", "output", "input", "door",
    "video", "audio", "speaker", "network", "system", "config", "profile",
    "continuous", "temp", "copy", "name", "none", "true", "false", "null",
})

# ── E4: tags ────────────────────────────────────────────────────────────────
TAG_STOPWORDS = frozenset({"all", "fleet", "axis", "device", "devices", "demo",
                           "test", "prod", "production"})
#: A tag on this fraction of the fleet or more is a *fleet label* (``#lab``,
#: ``#site-a``), not a demo grouping — the plan's "non-trivial tag", measured
#: the same self-calibrating way as ACAPs rather than by a hardcoded list.
TAG_MAX_FRACTION = 0.60

# ── E6: distinctive ACAPs ───────────────────────────────────────────────────
#: An app on fewer devices than this links nothing (needs a pair to be shared).
ACAP_MIN_DEVICES = 2
#: An app on this fraction of the fleet or more is bundled/default — no signal.
ACAP_MAX_FRACTION = 0.60

# ── E3: identity matching ───────────────────────────────────────────────────
#: Minimum length of an identity token, so ``"1"`` or ``"cam"`` can't match junk
#: (mirrors ``fragments.device_local_hits``' reasoning, applied in reverse).
IDENTITY_MIN_LEN = 4

_TOKEN_SPLIT = re.compile(r"[^0-9a-zA-Z]+")
_MODEL_ISH = re.compile(r"^[a-z]?\d{3,}[a-z]*$")   # p3288, i8016, m4308, 1710…
_NON_ALNUM = re.compile(r"[^0-9A-Za-z]+")


def params() -> Dict[str, Any]:
    """Every constant in force, echoed into the run's ``params_json``.

    Pinning them per run is what keeps an old graph explainable after the
    weights are tuned (the plan's audit-trail requirement).
    """
    return {
        "weights": dict(EDGE_WEIGHTS),
        "edge_classes": dict(EDGE_CLASSES),
        "edge_min": EDGE_MIN,
        "topology_edges": sorted(TOPOLOGY_EDGES),
        "name_token": {
            "min_len": NAME_TOKEN_MIN_LEN,
            "min_devices": NAME_TOKEN_MIN_DEVICES,
            "max_fraction": NAME_TOKEN_MAX_FRACTION,
            "stopwords": sorted(NAME_STOPWORDS),
        },
        "tag": {"max_fraction": TAG_MAX_FRACTION, "stopwords": sorted(TAG_STOPWORDS)},
        "acap": {"min_devices": ACAP_MIN_DEVICES, "max_fraction": ACAP_MAX_FRACTION,
                 "weight_floor": E6_WEIGHT_FLOOR},
        "identity_min_len": IDENTITY_MIN_LEN,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Nodes
# ═══════════════════════════════════════════════════════════════════════════

def _tokens(text: Any) -> Set[str]:
    """Lowercased alphanumeric tokens, minus stopwords, pure digits and model
    numbers (``P3288-LVE`` says what a device *is*, never which demo it serves)."""
    out: Set[str] = set()
    for raw in _TOKEN_SPLIT.split(str(text or "")):
        tok = raw.lower()
        if len(tok) < NAME_TOKEN_MIN_LEN or tok in NAME_STOPWORDS:
            continue
        if tok.isdigit() or _MODEL_ISH.match(tok):
            continue
        out.add(tok)
    return out


def build_nodes(devices: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One node per ADMZ registry device, with its ACAPs marked for rarity.

    ``devices`` rows are registry dicts optionally carrying ``acaps``
    (``{name: status}`` from ``capabilities.device_applications``). An **empty**
    ``acaps`` means the device has no applications snapshot — recorded as
    ``acaps_known: false`` so nothing downstream reads it as "no apps".
    """
    rows = [d for d in (devices or []) if (d or {}).get("device_id")]

    app_df: Dict[str, int] = {}
    # Ubiquity is measured against the devices whose app inventory we actually
    # KNOW. Counting unsnapshotted devices in the denominator would deflate every
    # frequency and make a bundled app (vmd on 4 of 6 known = 67%) look rare
    # (4 of 11 = 36%) — exactly the misjudgement the self-calibration exists to
    # avoid.
    total = 0
    for d in rows:
        acaps = d.get("acaps") or {}
        if not acaps:
            continue
        total += 1
        for app in acaps:
            app_df[str(app)] = app_df.get(str(app), 0) + 1

    nodes: List[Dict[str, Any]] = []
    for d in rows:
        did = str(d.get("device_id"))
        acaps = d.get("acaps") or {}
        nodes.append({
            "device_id": did,
            "mac": canonical_mac(d.get("mac_address") or did),
            "name": (d.get("nickname") or d.get("hostname") or d.get("model") or did),
            "model": d.get("model") or "",
            "tags": sorted({str(t) for t in (d.get("tags") or []) if t}),
            "host": (d.get("host") or d.get("ip_address") or "") or "",
            "acaps_known": bool(acaps),
            "acaps": [
                {"name": str(name), "status": str(status),
                 "device_count": app_df.get(str(name), 0),
                 "distinctive": _acap_distinctive(app_df.get(str(name), 0), total)}
                for name, status in sorted(acaps.items())
            ],
        })
    nodes.sort(key=lambda n: n["device_id"])
    return nodes


def known_app_total(nodes: Sequence[Dict[str, Any]]) -> int:
    """How many nodes have an applications inventory at all — the denominator
    every ACAP frequency is measured against."""
    return sum(1 for n in nodes if n.get("acaps_known"))


def _acap_distinctive(df: int, total: int) -> bool:
    """Self-calibrating: shared by at least two devices, but not by most of them.

    No hardcoded default-app list — a bundled ACAP is identified by being
    *everywhere*, which is firmware- and model-independent by construction.
    ``total`` counts only devices with a known app inventory (an empty facet is
    unknown, never "no apps"), so a missing snapshot can neither create nor
    suppress distinctiveness.
    """
    if total <= 0 or df < ACAP_MIN_DEVICES:
        return False
    return (df / total) < ACAP_MAX_FRACTION


def _acap_weight(df: int, total: int) -> float:
    """E6 weight, scaled by rarity into ``[E6_WEIGHT_FLOOR, E6_WEIGHT]``.

    Distinctiveness gates whether the edge exists at all; rarity only modulates
    within the band, so an E6 edge can never fall below :data:`EDGE_MIN`.
    """
    frac = (df / total) if total else 1.0
    rarity = max(0.0, min(1.0, 1.0 - (frac / ACAP_MAX_FRACTION)))
    return round(E6_WEIGHT_FLOOR + (E6_WEIGHT - E6_WEIGHT_FLOOR) * rarity, 4)


# ═══════════════════════════════════════════════════════════════════════════
# Rules — two sources, one shape
# ═══════════════════════════════════════════════════════════════════════════

def _index_by_mac(nodes: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    """canonical MAC → ``device_id``. Both the stored ``mac_address`` and a
    MAC-shaped ``device_id`` (ADR-0036 slot ids) index the same node."""
    idx: Dict[str, str] = {}
    for n in nodes:
        for key in (n.get("mac"), canonical_mac(n["device_id"])):
            if key:
                idx.setdefault(key, n["device_id"])
    return idx


def _strings(value: Any, out: List[str]) -> None:
    """Every string leaf under ``value`` — the haystack an E3 scan searches."""
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _strings(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _strings(v, out)
    elif value is not None and not isinstance(value, bool):
        out.append(str(value))


def _topics_of(raw: Dict[str, Any]) -> List[str]:
    """Topic expressions from an ``action_rules`` facet entry (condition list,
    ``startEvent``), tolerant of the shapes the beta API has shipped."""
    topics: List[str] = []
    act = raw.get("activationConfig") or {}
    conds = act.get("condition")
    for cond in (conds if isinstance(conds, list) else [conds] if conds else []):
        if isinstance(cond, dict) and cond.get("topicExpression"):
            topics.append(str(cond["topicExpression"]))
    start = act.get("startEvent")
    if isinstance(start, dict) and start.get("topicExpression"):
        topics.append(str(start["topicExpression"]))
    return sorted(set(topics))


def normalize_device_rule(device_id: str, key: str, raw: Any) -> Dict[str, Any]:
    """One ``action_rules`` facet entry → the shared rule shape.

    **Firmware asymmetry** (``snapshot/facets/action_rules.py:51`` vs
    ``rules/runner.py:250-263``): AXIS OS ≥ 12 gives the full rule object, so we
    get conditions and action parameters. Older firmware only ever yields the
    SOAP ``GetActionRules`` shape — ``{rule_id, name, enabled, primary_action}``,
    i.e. **names only**. Such a rule is marked ``names_only`` so downstream
    treats it as weaker evidence *by construction*, not by accident: with no
    action parameters it can never produce an E3 edge.
    """
    raw = raw if isinstance(raw, dict) else {}
    action = raw.get("actionConfig") or {}
    names_only = not action and not raw.get("activationConfig")
    values: List[str] = []
    _strings(action, values)
    enabled = raw.get("enabled")
    return {
        "source": "device",
        "rule_key": f"device:{device_id}:{key}",
        "rule_id": str(raw.get("id") or raw.get("rule_id") or key),
        "name": str(raw.get("name") or key),
        "enabled": True if enabled is None else bool(enabled),
        "owner_device_id": device_id,
        "trigger_device_ids": [device_id],
        "action_device_ids": [],
        "device_ids": [device_id],
        "topics": _topics_of(raw),
        "action_kinds": ([str(action.get("template"))] if action.get("template")
                         else ([str(raw.get("primary_action"))]
                               if raw.get("primary_action") else [])),
        "names_only": names_only,
        "action_values": values,
        "observability": None,
        "unresolved": [],
        "join_methods": {device_id: "registry_device"},
    }


def normalize_acs_rule(anatomy: Dict[str, Any], by_mac: Dict[str, str]) -> Dict[str, Any]:
    """One ``firebird.rule_anatomy`` row → the shared rule shape.

    The anatomy has already resolved each ACS device reference to a canonical
    MAC and recorded its ``join_method`` (``api_device_id`` → the supported
    ``DeviceListFacade`` route proven in slice 1, then the Firebird ``DEVICE``
    MAC, then ``DeviceSerialNumber``). Here that MAC is joined the last hop, to
    an ADMZ ``device_id``. Every hop that misses is reported: a reference the
    anatomy could not resolve at all, a reference that *did* resolve to an ACS
    device row carrying **no MAC** to join on (``build_device_resolver``'s
    ``acs_device_id_only`` path), and a MAC that resolved but names no
    registered ADMZ device (usually a camera that is in ACS but not yet
    onboarded here).

    A row with **no device reference at all** is a different thing entirely: an
    ACS server-side action or an HTTPS trigger legitimately names no device, and
    that is correct rather than unresolved. Only a reference that exists but is
    *incomplete* is reported — conflating the two is how a partially-resolved
    device silently vanishes from the graph.
    """
    unresolved: List[Dict[str, Any]] = []
    join_methods: Dict[str, str] = {}
    rule_name = str(anatomy.get("name") or "")
    rule_id = anatomy.get("id")

    def _side(rows: Iterable[Dict[str, Any]], kind: str) -> List[str]:
        found: List[str] = []
        for row in rows or []:
            row = row or {}
            ref = row.get("device") or row.get("target_device")
            ref_id = f"{kind}:{row.get('id')}"
            if row.get("device_ref_unresolved"):
                unresolved.append({
                    "kind": "acs_reference", "rule_id": rule_id, "rule_name": rule_name,
                    "ref": ref_id,
                    "reason": "ACS named a device/camera/port ADMZ could not resolve "
                              "to a MAC (not in the ACS device table).",
                })
                continue
            if not ref:
                continue          # server-side action / HTTPS trigger — names no device
            mac = ref.get("mac") if isinstance(ref, dict) else None
            if not mac:
                # The row DOES name a device — the reference is just incomplete
                # (an ACS DEVICE row with a blank MAC_ADDRESS, which the
                # resolver hands back as ``acs_device_id_only``). Dropping it
                # here would hide a real device behind "names no device".
                detail = ""
                if isinstance(ref, dict):
                    detail = str(ref.get("name") or ref.get("ip")
                                 or ref.get("acs_device_id") or "")
                unresolved.append({
                    "kind": "incomplete_device_ref", "rule_id": rule_id,
                    "rule_name": rule_name, "ref": ref_id, "mac": None,
                    "reason": (f"this {kind} names an ACS device"
                               + (f" ({detail})" if detail else "")
                               + " whose reference carries no MAC — the ACS "
                                 "device row has no MAC address, so it cannot "
                                 "be joined to the ADMZ registry."),
                })
                continue
            did = by_mac.get(canonical_mac(mac))
            if not did:
                unresolved.append({
                    "kind": "unregistered_device", "rule_id": rule_id,
                    "rule_name": rule_name, "ref": ref_id, "mac": mac,
                    "reason": f"MAC {mac} is in ACS but not in the ADMZ registry — "
                              "onboard it and re-run to link this rule.",
                })
                continue
            join_methods[did] = (ref.get("join_method")
                                 or row.get("join_method") or "unknown")
            found.append(did)
        return sorted(set(found))

    triggers = _side(anatomy.get("triggers"), "trigger")
    actions = _side(anatomy.get("actions"), "action")
    values: List[str] = []
    _strings([a.get("params") for a in anatomy.get("actions") or []], values)
    # ``rule_anatomy`` always carries ``enabled``; an anatomy that somehow omits
    # it must read as enabled, not disabled — edges now hang off this flag, and
    # a missing field silently erasing a rule's evidence is exactly the failure
    # mode this module exists to avoid. Same default as a device rule.
    acs_enabled = anatomy.get("enabled")
    return {
        "source": "acs",
        "rule_key": f"acs:{rule_id}",
        "rule_id": str(rule_id),
        "name": rule_name,
        "enabled": True if acs_enabled is None else bool(acs_enabled),
        "owner_device_id": None,
        "trigger_device_ids": triggers,
        "action_device_ids": actions,
        "device_ids": sorted(set(triggers) | set(actions)),
        "topics": sorted({str(t.get("topic")) for t in anatomy.get("triggers") or []
                          if t.get("topic")}),
        "action_kinds": sorted({str(a.get("kind")) for a in anatomy.get("actions") or []
                                if a.get("kind")}),
        "names_only": False,
        "action_values": values,
        "observability": classify_rule(anatomy),
        "unresolved": unresolved,
        "join_methods": join_methods,
        "schedule": anatomy.get("schedule"),
        "require_all_triggers": bool(anatomy.get("require_all_triggers")),
    }


def ground_rule_apps(rule: Dict[str, Any],
                     acaps_by_device: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
    """Does the rule's trigger topic depend on an ACAP, and is it installed?

    Uses the existing topic→app map (``capabilities.publisher_app_for``) rather
    than a new one. Three outcomes, all recorded as evidence, none as an edge:

    * **corroboration** — the app is installed on the trigger device, so the
      rule really is about that analytic (slice 3 turns this into a suggested
      owned key; slice 4 narrates it);
    * **dead rule** — the app is *not* installed, the known #111 failure class;
    * **unknown** — the device has no ``applications`` snapshot, so we say so.

    Also carries the shadowed-``MotionAlarm`` caution verbatim from
    ``capabilities.condition_caution``.
    """
    out: List[Dict[str, Any]] = []
    devices = rule.get("trigger_device_ids") or rule.get("device_ids") or []
    for topic in rule.get("topics") or []:
        cond = SimpleNamespace(topic=topic, label=rule.get("name") or topic,
                               id=rule.get("rule_id"))
        app = publisher_app_for(cond)
        for did in devices:
            apps = acaps_by_device.get(did)
            if app:
                if not apps:
                    out.append({"device_id": did, "topic": topic, "app": app,
                                "installed": None, "verdict": "unknown",
                                "detail": f"trigger topic needs the '{app}' application, "
                                          "but this device has no applications snapshot"})
                    continue
                status = next((s for n, s in apps.items() if n.lower() == app), None)
                if status is None:
                    out.append({"device_id": did, "topic": topic, "app": app,
                                "installed": False, "verdict": "missing_app",
                                "detail": f"trigger topic is published by '{app}', which "
                                          "is NOT installed here — this rule cannot fire "
                                          "(#111 dead-rule class)"})
                else:
                    out.append({"device_id": did, "topic": topic, "app": app,
                                "installed": True, "status": status,
                                "verdict": "corroborated" if status.lower() == "running"
                                           else "app_not_running",
                                "detail": f"trigger topic is produced by '{app}' "
                                          f"({status}) on this device"})
            caution = condition_caution(cond, apps or {})
            if caution:
                out.append({"device_id": did, "topic": topic, "app": None,
                            "installed": None, "verdict": "shadowed",
                            "detail": caution})
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Edges
# ═══════════════════════════════════════════════════════════════════════════

class _Edges:
    """Accumulator that merges repeat evidence for the same ``(id, a, b)`` pair."""

    def __init__(self) -> None:
        self._by_key: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    def add(self, edge_id: str, a: str, b: str, detail: str, *,
            weight: Optional[float] = None, source: str = "", **extra: Any) -> None:
        if not a or not b or a == b:
            return
        lo, hi = sorted((a, b))
        w = EDGE_WEIGHTS[edge_id] if weight is None else float(weight)
        if w < EDGE_MIN:
            return
        key = (edge_id, lo, hi)
        edge = self._by_key.get(key)
        if edge is None:
            edge = self._by_key[key] = {
                "id": edge_id, "a": lo, "b": hi, "weight": w,
                "class": EDGE_CLASSES[edge_id],
                "corroborating": edge_id not in TOPOLOGY_EDGES,
                "evidence": [],
            }
        edge["weight"] = max(edge["weight"], w)
        item = {"detail": detail}
        if source:
            item["source"] = source
        item.update(extra)
        if item not in edge["evidence"]:
            edge["evidence"].append(item)

    def result(self) -> List[Dict[str, Any]]:
        for edge in self._by_key.values():
            edge["evidence"].sort(key=lambda e: (e.get("source", ""), e["detail"]))
        return sorted(self._by_key.values(),
                      key=lambda e: (-e["weight"], e["id"], e["a"], e["b"]))


def _identity_hits(haystack: List[str], node: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Does any of ``haystack`` name ``node``'s MAC, IP or hostname?

    The reverse of ``fragments.device_local_hits``: instead of asking "is this
    value the device's own identity", ask "does this value name *another*
    device". MAC matching strips separators on both sides (so ``B8:A4:4F:…``
    matches ``B8A44F…``); IP matching requires digit/dot boundaries so
    ``10.0.0.5`` does not match ``10.0.0.50``. Tokens shorter than
    :data:`IDENTITY_MIN_LEN` are ignored.
    """
    joined = " ".join(haystack)
    if not joined.strip():
        return None
    mac = node.get("mac") or ""
    if len(mac) >= IDENTITY_MIN_LEN and mac in _NON_ALNUM.sub("", joined).upper():
        return {"kind": "mac", "token": mac}
    host = str(node.get("host") or "").strip()
    if len(host) >= IDENTITY_MIN_LEN:
        if re.search(r"(?<![\w.-])" + re.escape(host) + r"(?![\w.-])", joined, re.I):
            return {"kind": "host", "token": host}
    name = str(node.get("name") or "").strip()
    if len(name) >= IDENTITY_MIN_LEN and "." in name:
        if re.search(r"(?<![\w.-])" + re.escape(name) + r"(?![\w.-])", joined, re.I):
            return {"kind": "hostname", "token": name}
    return None


def build_edges(nodes: Sequence[Dict[str, Any]],
                rules: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every edge the evidence supports, each carrying why it exists.

    A **disabled** rule contributes no edge of any class: it is a record of how
    these devices were once wired, not evidence that they work together now.
    Its device references are still resolved and recorded on the rule (nothing
    is dropped) — only the edge is withheld.
    """
    edges = _Edges()
    total = len(nodes)
    by_id = {n["device_id"]: n for n in nodes}

    # ── E1 / E2: ACS rule topology ──────────────────────────────────────────
    for rule in rules:
        if rule["source"] != "acs" or not rule["enabled"]:
            continue
        label = rule["name"] or rule["rule_id"]
        direct: Set[Tuple[str, str]] = set()
        for a in rule["trigger_device_ids"]:
            for b in rule["action_device_ids"]:
                if a == b:
                    continue
                direct.add(tuple(sorted((a, b))))  # type: ignore[arg-type]
                edges.add("E1", a, b,
                          f"ACS rule '{label}' triggers on {_label(by_id, a)} and "
                          f"acts on {_label(by_id, b)}",
                          source=rule["rule_key"], rule_name=rule["name"])
        members = rule["device_ids"]
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                if tuple(sorted((a, b))) in direct:
                    continue      # already the stronger E1 for this same rule
                edges.add("E2", a, b,
                          f"ACS rule '{label}' names both {_label(by_id, a)} and "
                          f"{_label(by_id, b)}",
                          source=rule["rule_key"], rule_name=rule["name"])

    # ── E3: a device rule's action naming another device ────────────────────
    for rule in rules:
        if rule["source"] != "device" or rule["names_only"]:
            continue
        owner = rule["owner_device_id"]
        values = rule.get("action_values") or []
        for node in nodes:
            if node["device_id"] == owner:
                continue
            hit = _identity_hits(values, node)
            if not hit:
                continue
            # Resolve the reference even for a disabled rule — the rule really
            # does name this device, and that stays on the record…
            rule["action_device_ids"] = sorted(
                set(rule["action_device_ids"]) | {node["device_id"]})
            rule["device_ids"] = sorted(set(rule["device_ids"]) | {node["device_id"]})
            rule["join_methods"][node["device_id"]] = f"action_{hit['kind']}"
            if not rule["enabled"]:
                continue      # …but a disabled rule is not a working link today
            edges.add("E3", owner, node["device_id"],
                      f"device rule '{rule['name']}' on {_label(by_id, owner)} "
                      f"references {_label(by_id, node['device_id'])} by "
                      f"{hit['kind']} ({hit['token']})",
                      source=rule["rule_key"], rule_name=rule["name"])

    # ── E4: shared non-trivial tag ──────────────────────────────────────────
    tag_devices: Dict[str, List[str]] = {}
    for node in nodes:
        for tag in node["tags"]:
            if tag.lower() in TAG_STOPWORDS:
                continue
            tag_devices.setdefault(tag, []).append(node["device_id"])
    for tag, dids in sorted(tag_devices.items()):
        if len(dids) < 2 or (total and len(dids) / total >= TAG_MAX_FRACTION):
            continue
        for i, a in enumerate(dids):
            for b in dids[i + 1:]:
                edges.add("E4", a, b,
                          f"both tagged #{tag} ({len(dids)} of {total} devices)",
                          source=f"tag:{tag}", tag=tag)

    # ── E6: shared distinctive ACAP ─────────────────────────────────────────
    #     An empty facet is UNKNOWN, so such a device simply contributes no app
    #     rows here — it can neither create nor suppress an edge.
    app_total = known_app_total(nodes)
    app_devices: Dict[str, List[str]] = {}
    for node in nodes:
        for app in node["acaps"]:
            app_devices.setdefault(app["name"], []).append(node["device_id"])
    for app, dids in sorted(app_devices.items()):
        df = len(dids)
        if not _acap_distinctive(df, app_total):
            continue
        weight = _acap_weight(df, app_total)
        for i, a in enumerate(dids):
            for b in dids[i + 1:]:
                edges.add("E6", a, b,
                          f"both run {app} ({df} of {app_total} devices with an "
                          "app inventory)",
                          weight=weight, source=f"acap:{app}", app=app,
                          device_count=df, inventory_size=app_total)

    # ── E5: distinctive shared name token ───────────────────────────────────
    token_devices: Dict[str, Set[str]] = {}
    for node in nodes:
        for tok in _tokens(node["name"]):
            token_devices.setdefault(tok, set()).add(node["device_id"])
    for rule in rules:
        if not rule["enabled"]:
            continue          # history names devices too — it is still not evidence
        for tok in _tokens(rule["name"]):
            for did in rule["device_ids"]:
                token_devices.setdefault(tok, set()).add(did)
    cap = NAME_TOKEN_MAX_FRACTION * total
    for tok, members in sorted(token_devices.items()):
        dids = sorted(members)
        if len(dids) < NAME_TOKEN_MIN_DEVICES or len(dids) > cap:
            continue
        for i, a in enumerate(dids):
            for b in dids[i + 1:]:
                edges.add("E5", a, b,
                          f"'{tok}' appears in both names/rules "
                          f"({len(dids)} of {total} devices)",
                          source=f"token:{tok}", token=tok)

    return edges.result()


def _label(by_id: Dict[str, Dict[str, Any]], device_id: str) -> str:
    node = by_id.get(device_id) or {}
    return str(node.get("name") or device_id)


# ═══════════════════════════════════════════════════════════════════════════
# The graph
# ═══════════════════════════════════════════════════════════════════════════

def build_graph(
    devices: Sequence[Dict[str, Any]],
    *,
    device_rule_facets: Optional[Dict[str, Any]] = None,
    facet_read_errors: Optional[Dict[str, str]] = None,
    acs_rules: Optional[Sequence[Dict[str, Any]]] = None,
    acs: Optional[Dict[str, Any]] = None,
    generated_at: Optional[float] = None,
) -> Dict[str, Any]:
    """Assemble the whole evidence graph. Pure — every input is passed in.

    ``device_rule_facets`` maps ``device_id`` → that device's ``action_rules``
    facet document, or ``None`` when there is no snapshot to read (fast mode on
    a never-surveyed device). ``facet_read_errors`` maps ``device_id`` → why
    that facet could not be read at all; a *failed read* is deliberately not the
    same input as an *absent snapshot*, so a permission or repository error can
    never masquerade as "this device has no rules yet".

    ``acs_rules`` is ``firebird.rule_anatomy()`` output; ``acs`` is the
    degradation envelope ``{available: bool, reason: str}`` — an absent ACS
    degrades the graph, it never fails it.

    ``generated_at`` is **not** defaulted from the clock: this builder reads no
    clock at all, so the same inputs always produce the same document (the run
    row owns the wall-clock provenance, and :mod:`collect` injects it).
    """
    acs = dict(acs or {"available": False, "reason": "ACS not read"})
    nodes = build_nodes(devices)
    by_mac = _index_by_mac(nodes)
    acaps_by_device = {
        d["device_id"]: {a["name"]: a["status"] for a in d["acaps"]} for d in nodes
    }
    known_ids = {n["device_id"] for n in nodes}

    rules: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    no_rule_facet: List[str] = []

    for did in sorted(known_ids):
        err = (facet_read_errors or {}).get(did)
        if err:
            # The facet exists as far as we know — we simply could not read it.
            # Reporting this as "no snapshot" would blame the fleet for what is
            # a permission / repository / parse failure on our side.
            unresolved.append({
                "kind": "facet_read_error", "rule_id": "", "rule_name": "",
                "ref": did,
                "reason": f"the action_rules facet for {did} could not be read "
                          f"({err}) — this is a read failure, not a missing "
                          "snapshot, so this device's rules are unknown for a "
                          "reason another snapshot will not fix.",
            })
            continue
        doc = (device_rule_facets or {}).get(did)
        if doc is None:
            # No snapshot yet, or AXIS OS < 12 (the facet is firmware-gated at
            # ``snapshot/facets/action_rules.py:51``). Either way it is *unknown*,
            # not "no rules" — reported, so a thin graph is explainable.
            no_rule_facet.append(did)
            continue
        if not isinstance(doc, dict):
            # A facet that is present but not a rule map is damaged, not empty.
            # Silently treating it as "no rules" would break the no-silent-drop
            # contract in the one place nobody would think to look.
            unresolved.append({
                "kind": "unparsable_device_rule_facet", "rule_id": "",
                "rule_name": "", "ref": did,
                "reason": f"the action_rules facet for {did} is a "
                          f"{type(doc).__name__}, not a map of rules — its rules "
                          "could not be read (reported rather than counted as "
                          "'this device has no rules').",
            })
            continue
        for key in sorted(doc, key=str):
            try:
                rules.append(normalize_device_rule(did, str(key), doc[key]))
            except Exception:  # noqa: BLE001 — a malformed entry must not kill the run
                unresolved.append({
                    "kind": "unparsable_device_rule", "rule_id": str(key),
                    "rule_name": "", "ref": did,
                    "reason": "action_rules facet entry could not be parsed — skipped",
                })

    unattached: List[Dict[str, Any]] = []
    for row in acs_rules or []:
        try:
            rule = normalize_acs_rule(row, by_mac)
        except Exception:  # noqa: BLE001
            unresolved.append({
                "kind": "unparsable_acs_rule", "rule_id": str((row or {}).get("id")),
                "rule_name": str((row or {}).get("name") or ""), "ref": "",
                "reason": "ACS rule row could not be parsed — skipped",
            })
            continue
        unresolved.extend(rule.pop("unresolved"))
        if not rule["device_ids"]:
            unattached.append({"rule_key": rule["rule_key"], "rule_id": rule["rule_id"],
                               "name": rule["name"], "source": "acs",
                               "reason": "no trigger or action device resolves to an "
                                         "ADMZ device — surfaced, not dropped"})
        rules.append(rule)

    edges = build_edges(nodes, rules)   # may enrich device rules with E3 targets

    for rule in rules:
        rule["app_grounding"] = ground_rule_apps(rule, acaps_by_device)
        rule.pop("action_values", None)
    rules.sort(key=lambda r: (r["source"], r["name"].lower(), r["rule_key"]))

    return {
        # Injected, never read from the clock — see the docstring.
        "generated_at": generated_at,
        "params": params(),
        "acs": {"available": bool(acs.get("available")),
                "reason": str(acs.get("reason") or "")},
        "nodes": nodes,
        "rules": rules,
        "edges": edges,
        "unresolved": unresolved,
        "unattached_rules": unattached,
        "devices_without_rule_facet": no_rule_facet,
        "summary": summarize(nodes, rules, edges, unresolved, unattached,
                             no_rule_facet, acs),
    }


def summarize(nodes: Sequence[Dict[str, Any]], rules: Sequence[Dict[str, Any]],
              edges: Sequence[Dict[str, Any]], unresolved: Sequence[Dict[str, Any]],
              unattached: Sequence[Dict[str, Any]], no_rule_facet: Sequence[str],
              acs: Dict[str, Any]) -> Dict[str, Any]:
    """The one-glance evidence summary the ``/demos`` button renders."""
    by_source: Dict[str, int] = {"acs": 0, "device": 0}
    for r in rules:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    by_type: Dict[str, int] = {}
    for e in edges:
        by_type[e["id"]] = by_type.get(e["id"], 0) + 1

    app_rows: Dict[str, Dict[str, Any]] = {}
    for n in nodes:
        for app in n["acaps"]:
            row = app_rows.setdefault(app["name"], {"name": app["name"],
                                                    "device_count": 0,
                                                    "distinctive": app["distinctive"]})
            row["device_count"] += 1

    linked = {d for e in edges for d in (e["a"], e["b"])}
    grounding = [g for r in rules for g in (r.get("app_grounding") or [])]
    return {
        "device_count": len(nodes),
        "rule_count": len(rules),
        "rules_by_source": by_source,
        "names_only_rules": sum(1 for r in rules if r["names_only"]),
        # Kept, shown, and excluded from every edge — the exclusion is counted
        # here so a thin graph next to a lot of automation is explainable.
        "disabled_rules": sum(1 for r in rules if not r["enabled"]),
        "edge_count": len(edges),
        "edges_by_type": by_type,
        "topology_edge_count": sum(1 for e in edges if not e["corroborating"]),
        "linked_device_count": len(linked),
        "unresolved_count": len(unresolved),
        "unattached_rule_count": len(unattached),
        "devices_without_rule_facet": len(no_rule_facet),
        "acs": {"available": bool(acs.get("available")),
                "reason": str(acs.get("reason") or "")},
        "acaps": {
            "devices_with_app_inventory": known_app_total(nodes),
            "distinct_apps": len(app_rows),
            "distinctive_apps": sorted(a["name"] for a in app_rows.values()
                                       if a["distinctive"]),
            "apps": sorted(app_rows.values(), key=lambda a: (-a["device_count"],
                                                             a["name"])),
        },
        "rule_app_grounding": {
            "corroborated": sum(1 for g in grounding if g["verdict"] == "corroborated"),
            "missing_app": sum(1 for g in grounding if g["verdict"] == "missing_app"),
            "app_not_running": sum(1 for g in grounding
                                   if g["verdict"] == "app_not_running"),
            "shadowed": sum(1 for g in grounding if g["verdict"] == "shadowed"),
            "unknown": sum(1 for g in grounding if g["verdict"] == "unknown"),
        },
        "observability": _observability_counts(rules),
    }


def _observability_counts(rules: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for rule in rules:
        verdict = (rule.get("observability") or {}).get("verdict")
        if verdict:
            counts[verdict] = counts.get(verdict, 0) + 1
    return dict(sorted(counts.items()))
