"""Config-tracking ignore list — config items the operator excludes from
snapshots and drift.

An excluded item is dropped at snapshot CAPTURE (so it never enters a baseline,
drift report, or the git config repo) AND filtered out of drift comparison (so
it vanishes from drift immediately, even against an older baseline). Use it for
noisy keys, or config an app stores badly — e.g. a custom ACAP that writes a
plaintext credential into param.cgi.

Rules are SCOPED and FACET-AWARE:
  * a rule is ``{"key": <canonical-key glob>, "scope": ...}``,
  * ``scope`` is ``global`` | ``tag:<tag>`` | ``device:<device_id>``,
  * the ``key`` is a *canonical key* (see facets' ``canonical_key``): a full
    ``root.*`` param key for param-backed facets, or ``<facet>:<path>`` for
    non-param facets (applications, action_rules, …) — so the same rule model
    addresses any config item.

Rules are additive (union) — an item is ignored if ANY applicable rule matches;
there are no negative/un-ignore rules. The legacy flat ``config_ignore_patterns``
setting (the Settings textarea) is read as implicit ``global`` rules for
back-compat.

Pattern syntax — case-insensitive against the canonical key:
  * contains ``*`` / ``?``  → glob (``fnmatch``), where ``*`` crosses dots,
  * otherwise               → exact key, OR a parent group (dotted prefix).
"""

import fnmatch
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Always-on, non-removable GLOBAL patterns (treated as global rules, never shown
# in Settings). Intentionally EMPTY — shipped defaults are *seeded* as normal
# editable rules instead (see ``_SEED_DEFAULT_RULES`` / ``seed_default_rules``),
# so operators can delete or re-scope them. Reserve this only for a pattern that
# must never be turned off.
_GLOBAL_IGNORE_PATTERNS: tuple = ()

#: Legacy flat list (newline/comma separated), still editable in Settings; read
#: as implicit global rules.
USER_SETTING_KEY = "config_ignore_patterns"
#: Scoped rules, JSON list of {"key","scope"}.
RULES_SETTING_KEY = "config_ignore_rules"
#: High-water marker (int, as string) — how many of ``_SEED_DEFAULT_RULES`` have
#: been seeded into this fleet's editable store. Lets us seed each default once
#: ever, so deleting a seeded rule is permanent (it never comes back).
SEED_VERSION_KEY = "config_ignore_seed_version"

#: Shipped default ignore rules, seeded ONCE each into the operator-editable
#: scoped store on startup. All observed/runtime network+time state the *device
#: or DHCP* controls (not the operator), so it "drifts" with the environment and
#: is non-actionable. Operators can delete/edit any of these in Settings.
#:
#: APPEND-ONLY — never reorder or remove entries: ``seed_default_rules`` uses the
#: list length as a high-water mark to decide which are new, so renumbering would
#: re-seed already-deleted rules. To retire a default, leave the entry and stop
#: documenting it (or ship a follow-up that removes the rule).
_SEED_DEFAULT_RULES: tuple = (
    # Observed live IPv6 addresses — rotating SLAAC/DHCPv6/temporary globals. The
    # settable static config lives under root.Network.IPv6.* (singular) and stays
    # tracked; observed IPv4 (eth0.IPAddress) is intentionally left tracked too.
    {"key": "root.Network.eth0.IPv6.IPAddresses", "scope": "global"},
    # Learned default gateway (v4 + v6) — a route the network hands out.
    {"key": "root.Network.Routing.*", "scope": "global"},
    # DHCP/pool-provided NTP server — distinct from the configured NTP.Server,
    # which stays tracked.
    {"key": "root.Time.NTP.VolatileServer", "scope": "global"},
    # Model+firmware identity string (e.g. "AXIS,…,P3748-PLVE,12.1.65") — moves on
    # a firmware update, not an operator edit.
    {"key": "root.Network.DHCP.VendorClass", "scope": "global"},
    # Auto link-local fallback address/mask (169.254.x) — only present when DHCP
    # is unavailable.
    {"key": "root.Network.ZeroConf.IPAddress", "scope": "global"},
    {"key": "root.Network.ZeroConf.SubnetMask", "scope": "global"},
    # DHCP-assigned hostname (e.g. "axis-<mac>").
    {"key": "root.Network.VolatileHostName.HostName", "scope": "global"},
    # Derived UPnP name ("AXIS <model> - <mac>").
    {"key": "root.Network.UPnP.FriendlyName", "scope": "global"},
    # Read-only param MIRROR of the NTP client config. The ntp facet (PR #97)
    # now tracks NTP authoritatively via ntp.cgi — and is revertable — so the
    # mirror only double-reports. It also doesn't round-trip deterministically
    # (observed live: DHCP-mode mirror flips 0.0.0.0 <-> '' across config
    # writes). The DHCP-provided list (NTP.VolatileServer) is seeded above.
    {"key": "root.Time.NTP.Server", "scope": "global"},
    # The device's own WALL CLOCK — advances every second, so it drifts on
    # every computation and "accept baseline" can never settle it (#215).
    # Time *configuration* stays tracked: POSIXTimeZone, DST.*, ObtainFromDHCP
    # and SyncSource are exactly what drift detection should catch. The match
    # is exact-or-child, so a sibling like ServerDateFormat stays tracked too.
    {"key": "root.Time.ServerDate", "scope": "global"},
    {"key": "root.Time.ServerTime", "scope": "global"},
)


# --------------------------------------------------------------------------- #
# Key matching (unchanged matcher; ``:`` is an ordinary char so canonical keys
# like ``applications:objectanalytics.status`` work).
# --------------------------------------------------------------------------- #
def _matches(key: str, pattern: str) -> bool:
    k = key.lower()
    p = pattern.lower()
    if "*" in p or "?" in p:
        return fnmatch.fnmatch(k, p)
    return k == p or k.startswith(p + ".")


def matches_any(key: str, patterns: List[str]) -> bool:
    """True if ``key`` matches any of the pattern strings."""
    return any(_matches(key, p) for p in patterns)


# --------------------------------------------------------------------------- #
# Rule store
# --------------------------------------------------------------------------- #
def _fleet_get(setting_key: str) -> Optional[str]:
    try:
        import admz.fleet_settings as _fs
        return _fs.fleet_settings.get(setting_key)
    except Exception:
        return None


def _fleet_set(setting_key: str, value: str) -> None:
    import admz.fleet_settings as _fs
    _fs.fleet_settings.set(setting_key, value)


def _legacy_global_patterns() -> List[str]:
    """Built-in globals + the legacy ``config_ignore_patterns`` textarea list."""
    raw = _fleet_get(USER_SETTING_KEY)
    user: List[str] = []
    if raw:
        user = [p.strip() for p in raw.replace(",", "\n").splitlines() if p.strip()]
    return list(_GLOBAL_IGNORE_PATTERNS) + user


def _scoped_rules() -> List[Dict[str, str]]:
    """Just the JSON ``config_ignore_rules`` store (no legacy union). The
    canonical source that add/remove manage. Fails open to []."""
    raw = _fleet_get(RULES_SETTING_KEY)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        logger.warning("config_ignore_rules is not valid JSON; ignoring it")
        return []
    out: List[Dict[str, str]] = []
    if isinstance(data, list):
        for r in data:
            if isinstance(r, dict) and r.get("key"):
                out.append({
                    "key": str(r["key"]).strip(),
                    "scope": str(r.get("scope") or "global").strip() or "global",
                })
    return out


def get_rules() -> List[Dict[str, str]]:
    """All ignore rules: the scoped store + legacy flat list (as global rules),
    deduped on (key, scope). Read once per snapshot/drift and reused."""
    rules = list(_scoped_rules())
    rules.extend({"key": p, "scope": "global"} for p in _legacy_global_patterns())
    seen = set()
    out: List[Dict[str, str]] = []
    for r in rules:
        t = (r["key"], r["scope"])
        if t not in seen:
            seen.add(t)
            out.append(r)
    return out


def _scope_matches(scope: str, device_id: Optional[str], tags) -> bool:
    if scope == "global":
        return True
    if scope.startswith("device:"):
        return device_id is not None and scope[len("device:"):] == device_id
    if scope.startswith("tag:"):
        return scope[len("tag:"):] in (tags or [])
    return False  # unknown scope never matches


def applicable_rules(
    device_id: Optional[str] = None, tags=None
) -> List[Dict[str, str]]:
    """The rules whose scope covers this device. Compute once per device, then
    pass the result to :func:`is_ignored` for a cheap per-key check."""
    return [r for r in get_rules() if _scope_matches(r["scope"], device_id, tags)]


def is_ignored(
    canonical_key: str,
    device_id: Optional[str] = None,
    tags=None,
    rules: Optional[List[Dict[str, str]]] = None,
) -> bool:
    """Whether ``canonical_key`` is excluded for the given device. Pass a
    precomputed ``rules`` list (from :func:`applicable_rules`) to avoid
    re-reading/re-filtering per key."""
    rs = rules if rules is not None else applicable_rules(device_id, tags)
    return matches_any(canonical_key, [r["key"] for r in rs])


def add_rules(new_rules: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Merge ``new_rules`` ({key, scope}) into the scoped store (dedupe on
    (key, scope)). Returns the full scoped list."""
    existing = _scoped_rules()
    seen = {(r["key"], r["scope"]) for r in existing}
    for r in new_rules:
        key = str(r.get("key") or "").strip()
        scope = str(r.get("scope") or "global").strip() or "global"
        if not key or (key, scope) in seen:
            continue
        existing.append({"key": key, "scope": scope})
        seen.add((key, scope))
    _save_scoped(existing)
    return existing


def remove_rules(to_remove: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Drop matching (key, scope) tuples from the scoped store."""
    drop = {
        (str(r.get("key") or "").strip(),
         str(r.get("scope") or "global").strip() or "global")
        for r in to_remove
    }
    kept = [r for r in _scoped_rules() if (r["key"], r["scope"]) not in drop]
    _save_scoped(kept)
    return kept


def _save_scoped(rules: List[Dict[str, str]]) -> None:
    import admz.fleet_settings as _fs
    _fs.fleet_settings.set(RULES_SETTING_KEY, json.dumps(rules))


# --------------------------------------------------------------------------- #
# One-time default seeding (startup)
# --------------------------------------------------------------------------- #
def seed_default_rules() -> List[Dict[str, str]]:
    """Seed shipped default ignore rules into the operator-editable store, once
    each. Idempotent + deletion-safe via a high-water marker (``SEED_VERSION_KEY``
    = how many of ``_SEED_DEFAULT_RULES`` have ever been seeded): only entries
    beyond the marker are added, then the marker advances. So a seeded rule the
    operator later deletes never comes back, and appending a NEW default seeds
    only that one on the next startup.

    Called once at startup (see the FastAPI lifespan). Returns the rules newly
    seeded this call (empty when already up to date). Fails open — never raises,
    so a settings hiccup can't block startup."""
    try:
        try:
            applied = int(_fleet_get(SEED_VERSION_KEY) or 0)
        except (TypeError, ValueError):
            applied = 0
        target = len(_SEED_DEFAULT_RULES)
        if applied >= target:
            return []
        new = [dict(r) for r in _SEED_DEFAULT_RULES[applied:target]]
        add_rules(new)              # dedupes on (key, scope) — safe if pre-added
        _fleet_set(SEED_VERSION_KEY, str(target))
        if new:
            logger.info("Seeded %d default ignore rule(s): %s",
                        len(new), ", ".join(r["key"] for r in new))
        return new
    except Exception:  # noqa: BLE001 — seeding must never break startup
        logger.warning("default ignore-rule seeding failed", exc_info=True)
        return []


# --------------------------------------------------------------------------- #
# Back-compat: a couple of callers/tests still use the flat-pattern helpers.
# --------------------------------------------------------------------------- #
def get_ignore_patterns() -> List[str]:
    """Legacy: global built-in + textarea patterns (flat strings)."""
    return _legacy_global_patterns()
