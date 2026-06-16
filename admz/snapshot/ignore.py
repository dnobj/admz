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

# Shipped, always-on GLOBAL patterns (treated as global rules). Intentionally
# tiny — operators add the rest. New fleet-wide defaults go here over time.
_GLOBAL_IGNORE_PATTERNS: tuple = ()

#: Legacy flat list (newline/comma separated), still editable in Settings; read
#: as implicit global rules.
USER_SETTING_KEY = "config_ignore_patterns"
#: Scoped rules, JSON list of {"key","scope"}.
RULES_SETTING_KEY = "config_ignore_rules"


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
# Back-compat: a couple of callers/tests still use the flat-pattern helpers.
# --------------------------------------------------------------------------- #
def get_ignore_patterns() -> List[str]:
    """Legacy: global built-in + textarea patterns (flat strings)."""
    return _legacy_global_patterns()
