"""
Firmware upgrade path computation for Axis devices.

Axis OS enforces upgrade paths: when crossing major versions, each
intermediate LTS milestone must be installed.  Skipping LTS versions
can corrupt device configuration, and the device itself may reject
the upgrade (auto-rollback).

LTS milestones are created every two years.  This module maintains
the known milestone table and computes the required upgrade sequence.
"""

import re
from typing import List, Optional, Tuple

# Known AXIS OS LTS milestone versions (major, minor).
# Each entry represents the final LTS release for that major version.
LTS_MILESTONES: List[Tuple[int, int]] = [
    (8, 40),    # LTS 2018
    (9, 80),    # LTS 2020
    (10, 12),   # LTS 2022
    (11, 11),   # LTS 2024
]


def parse_version(version_str: str) -> Optional[Tuple[int, int, int]]:
    """Parse a version string like '12.6.51' into (major, minor, patch).

    Returns None if the string cannot be parsed.
    """
    m = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", version_str.strip())
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3)) if m.group(3) else 0
    return (major, minor, patch)


def compute_upgrade_path(
    current: str,
    target: str,
) -> List[str]:
    """Compute the required intermediate LTS versions between current and target.

    Returns a list of version strings that must be installed (in order)
    between the current and target versions.  Does NOT include the
    current version or the target version in the returned list.

    If the upgrade is within the same major version, returns an empty
    list (direct upgrade is safe).

    Examples:
        compute_upgrade_path("12.6.51", "12.8.54") -> []
        compute_upgrade_path("9.20.1", "12.8.54") -> ["9.80", "10.12", "11.11"]
        compute_upgrade_path("7.40.1", "11.11.0") -> ["8.40", "9.80", "10.12"]
    """
    cur = parse_version(current)
    tgt = parse_version(target)
    if cur is None or tgt is None:
        return []

    cur_major = cur[0]
    tgt_major = tgt[0]

    # Same major version — direct upgrade
    if cur_major == tgt_major:
        return []

    # Downgrade — no path computation (user must handle manually)
    if tgt_major < cur_major:
        return []

    intermediates: List[str] = []
    for lts_major, lts_minor in LTS_MILESTONES:
        # Include LTS milestones that are:
        # - At or above the current major version
        # - Below the target major version
        if lts_major >= cur_major and lts_major < tgt_major:
            # Skip if current version is already past this LTS
            if lts_major == cur_major and (cur[1] > lts_minor or (cur[1] == lts_minor and cur[2] > 0)):
                # Already past this LTS within the same major
                # But we still need to go through it if we're at the same LTS version
                # Actually, if cur is 9.80.x, we've already installed 9.80 LTS
                continue
            intermediates.append(f"{lts_major}.{lts_minor}")

    return intermediates


def format_upgrade_path(
    current: str,
    target: str,
    intermediates: Optional[List[str]] = None,
) -> str:
    """Format the upgrade path as a human-readable string.

    Examples:
        "12.6.51 → 12.8.54 (direct)"
        "9.20.1 → 9.80 (LTS) → 10.12 (LTS) → 11.11 (LTS) → 12.8.54"
    """
    if intermediates is None:
        intermediates = compute_upgrade_path(current, target)

    if not intermediates:
        return f"{current} → {target} (direct)"

    parts = [current]
    for v in intermediates:
        parts.append(f"{v} (LTS)")
    parts.append(target)
    return " → ".join(parts)
