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


__all__ = [
    "validate_identifier",
    "validate_git_ref",
]
