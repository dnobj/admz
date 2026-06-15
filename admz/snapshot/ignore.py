"""Config-tracking ignore list — params the operator never wants snapshotted.

A param matching any ignore pattern is dropped at CAPTURE time (in the engine),
so it never enters a snapshot, baseline, drift report, or the git config repo.
This is the right tool for config that is noisy, or that an app stores badly —
e.g. a custom ACAP that writes a plaintext credential into ``param.cgi`` under a
non-standard key the secret filter can't recognize. ADMZ shouldn't track,
diff, or commit those.

Two layers (the union is applied):
  * GLOBAL built-in patterns — shipped defaults in this module. Kept small and
    generic; this is where fleet-wide "never useful" keys go over time.
  * USER patterns — a fleet setting (``config_ignore_patterns``), one pattern
    per line, editable in Settings. Per-deployment additions (the operator's
    own apps / noisy keys).

Pattern syntax — matched case-insensitively against the full ``root.*`` key:
  * contains ``*`` / ``?``  → glob (``fnmatch``), where ``*`` DOES cross dots:
        ``*AlarmActionPass`` , ``root.Antitailgate.*`` , ``root.*.Pwd``
  * otherwise               → exact key, OR a parent group (dotted prefix):
        ``root.Antitailgate.AlarmActionPass``  (exact one key)
        ``root.Antitailgate``                  (the whole group, any key under it)
"""

import fnmatch
from typing import List, Optional

# Shipped, always-on ignores. Intentionally tiny — operators add the rest via
# the user list. New fleet-wide defaults go here as we find genuinely-useless
# or universally-noisy keys.
_GLOBAL_IGNORE_PATTERNS: tuple = ()

#: Fleet-settings key holding the user list (newline- or comma-separated).
USER_SETTING_KEY = "config_ignore_patterns"


def _user_patterns() -> List[str]:
    """The operator-editable patterns from fleet settings. Best-effort: any
    store/parse error yields an empty list (ignore is additive — failing open
    here just means 'track everything', never a crash mid-snapshot)."""
    try:
        import admz.fleet_settings as _fs
        raw = _fs.fleet_settings.get(USER_SETTING_KEY)
    except Exception:
        return []
    if not raw:
        return []
    parts = raw.replace(",", "\n").splitlines()
    return [p.strip() for p in parts if p.strip()]


def get_ignore_patterns() -> List[str]:
    """Global defaults + the user list. Read once per snapshot and reused for
    every key (it hits the settings DB once)."""
    return list(_GLOBAL_IGNORE_PATTERNS) + _user_patterns()


def _matches(key: str, pattern: str) -> bool:
    k = key.lower()
    p = pattern.lower()
    if "*" in p or "?" in p:
        return fnmatch.fnmatch(k, p)
    # Plain pattern: exact key, or a parent group (so 'root.App' ignores
    # 'root.App.Anything' but NOT 'root.AppExtra').
    return k == p or k.startswith(p + ".")


def is_ignored(key: str, patterns: Optional[List[str]] = None) -> bool:
    """Whether ``key`` is on the ignore list. Pass a precomputed ``patterns``
    list (from :func:`get_ignore_patterns`) to avoid re-reading the DB per key
    during a full param dump."""
    pats = patterns if patterns is not None else get_ignore_patterns()
    return any(_matches(key, p) for p in pats)
