"""Input validators for identifiers that flow into filesystem paths.

CR-5: ``device_id`` (and friends) reach :func:`admz.snapshot.git_repo.device_path`
unvalidated; a malicious value like ``"../../../tmp/pwned"`` escapes the
config-repo root and lets a writer create files outside the intended tree.
SQL is safe (parameterized everywhere), but filesystem and git-command
inputs need a strict allow-list at entry points.

This module exposes two predicates:

  * :func:`validate_identifier` — for ``device_id``, ``account_id``,
    ``facet_name``. Allow-list: alphanumeric (must start with one),
    ``.``, ``_``, ``-``. Max 128 chars. Explicit reject for ``..``.

  * :func:`validate_git_ref` — for git refs (commit SHAs, tag names,
    branch names). Wider allow-list including ``/`` because git refs
    are slash-separated, but still rejects ``..``.

Both raise :class:`ValueError` on invalid input. Pydantic ``field_validator``
hooks and FastAPI ``Path(regex=)`` enforce them at the REST boundary;
the MCP ``call_tool`` dispatcher applies them at the LLM boundary; and
:func:`admz.snapshot.git_repo.GitRepo.device_path` applies them as
defense-in-depth so a missed entry point can't slip through.
"""

from __future__ import annotations

import re


# Identifiers — used in filesystem path components.
# - Must start with alphanumeric (rules out leading "." and "-" which
#   are both legitimate problems: "." traversal, "-" looks like a flag
#   to subprocess callers)
# - Subsequent chars: alphanumeric + . _ -
# - 1–128 chars total
# The pattern alone rules out path separators ("/" "\\"), spaces,
# control chars, and ".." (no two adjacent dots? actually two adjacent
# dots are matched by the pattern — see explicit check below).
_IDENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# Git refs — wider charset for slash-separated names (refs/heads/main,
# tags/v1.0, etc.). Still rejects path separators that aren't "/", spaces,
# and ".." per the explicit check.
_GIT_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")


def validate_identifier(value: object, kind: str = "identifier") -> str:
    """Return ``value`` if it's a valid identifier; otherwise raise.

    ``kind`` is just a label for the error message (e.g. ``"device_id"``).
    """
    if not isinstance(value, str):
        raise ValueError(
            f"{kind} must be a string (got {type(value).__name__})"
        )
    if not _IDENT_RE.match(value):
        raise ValueError(
            f"{kind} must match {_IDENT_RE.pattern} "
            f"(alphanumeric start, then alphanumeric + . _ -; "
            f"max 128 chars). Got: {value!r}"
        )
    # Belt-and-braces: the regex already excludes ".." because "."
    # isn't allowed as the first char, but ":foo..bar" passes the
    # general pattern — kill it explicitly so the rule is obvious.
    if ".." in value:
        raise ValueError(f"{kind} cannot contain '..': {value!r}")
    return value


def validate_git_ref(value: object) -> str:
    """Return ``value`` if it's a valid git ref; otherwise raise.

    Accepts the shape used by ``git show``, ``git diff``, ``git log``
    (commit SHAs, branch names, tag names, ``HEAD~N``, ``refs/heads/x``).
    Rejects shell metacharacters and ``..`` (which would
    expand a ref's reachable history in ways the caller probably
    doesn't want).
    """
    if not isinstance(value, str):
        raise ValueError(
            f"git ref must be a string (got {type(value).__name__})"
        )
    if not _GIT_REF_RE.match(value):
        raise ValueError(
            f"git ref must match {_GIT_REF_RE.pattern}. Got: {value!r}"
        )
    if ".." in value:
        # The "X..Y" syntax denotes a range, which is generally not what
        # a config-restore caller wants. Reject explicitly.
        raise ValueError(f"git ref cannot contain '..': {value!r}")
    return value


# ── Scan scope ──────────────────────────────────────────────────────────────

#: Smallest prefix an ARP sweep may be asked for. /16 is 65,534 hosts — already
#: generous for any site LAN — and it rejects the case that motivated this:
#: a ``/8`` is 16,777,214 ARP packets, which is a network flood, not a scan.
#: Deliberately a REJECT and not a clamp: silently scanning something narrower
#: than asked would report "no devices found" for addresses never probed, which
#: is indistinguishable from a clean result.
MIN_SCAN_PREFIXLEN = 16


def validate_scan_subnet(value):
    """Validate a subnet destined for an ARP sweep. Returns the canonical form.

    ``None`` passes through — it means "auto-detect the local /24", which is
    the documented default and involves no caller-supplied string.

    This exists because the subnet is **model-supplied free text** that reaches
    ``scapy``'s ``ARP(pdst=...)`` untouched (#199). The confirmation gate added
    in #299 makes the scan *deliberate*; it does nothing about what is in the
    string. ``ipaddress.ip_network`` was already imported one function away in
    ``arp_scanner._parse_arp_table`` — but only to filter results, and it
    swallows ``ValueError``, so it never validated anything.

    Enforced in :func:`admz.discovery.orchestrator.discover_devices`, the one
    function all five callers funnel through (REST scan, the demo-inference
    survey, two MCP tools, and the CLI) — rather than at those five call sites.
    Validating per-entry-point is how you miss the sixth.
    """
    import ipaddress

    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(
            f"subnet must be a string in CIDR form (got {type(value).__name__})"
        )
    text = value.strip()
    if not text:
        raise ValueError("subnet must not be empty — omit it to auto-detect")
    try:
        # strict=False so "192.168.1.42/24" is accepted and normalised to
        # "192.168.1.0/24"; an operator naming a host on the target network is
        # being helpful, not wrong.
        network = ipaddress.ip_network(text, strict=False)
    except ValueError as exc:
        raise ValueError(
            f"subnet {text!r} is not valid CIDR ({exc}). Expected e.g. "
            f"'192.168.1.0/24'."
        ) from exc

    if network.version != 4:
        raise ValueError(
            f"subnet {text!r} is IPv6. An ARP sweep is IPv4-only — ARP has no "
            f"IPv6 equivalent (neighbour discovery is a different protocol "
            f"ADMZ does not implement)."
        )
    if network.prefixlen < MIN_SCAN_PREFIXLEN:
        raise ValueError(
            f"subnet {str(network)!r} is {network.num_addresses - 2:,} hosts. "
            f"The limit is /{MIN_SCAN_PREFIXLEN} "
            f"({2 ** (32 - MIN_SCAN_PREFIXLEN) - 2:,} hosts) — an ARP sweep "
            f"sends one packet per host, so a wider range floods the network "
            f"rather than scanning it. Name the subnet you actually mean."
        )
    return str(network)


__all__ = [
    "validate_identifier",
    "validate_git_ref",
    "validate_scan_subnet",
    "MIN_SCAN_PREFIXLEN",
]
