"""The deploy log: what this host was asked to run, and how each attempt ended.

ADR-0054 decision 7 asked for it in August. It was never built, so every deploy
of the lab instance was recorded only in issue comments and session notes, and
the host itself could not say what it was running or since when (FR-DEP-006).

One JSON object per line, appended to ``deployed.log`` in the instance's data
folder. It lives with the data and not with the code, because the code is what
an upgrade replaces.

Every attempt gets a line, including one that was refused before anything
changed and one that was rolled back. "Nothing happened, and here is why" is
part of the history of a host.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

LOG_NAME = "deployed.log"

#: How an attempt ended. ``refused`` changed nothing. ``rolled-back`` switched
#: and returned to where it started. ``rollback-failed`` is the one that needs a
#: person: the instance is in a state this command could not repair.
OUTCOMES = ("ok", "refused", "rolled-back", "rollback-failed")


def _operator() -> str:
    try:
        return getpass.getuser()
    except Exception:                    # no usable account name, e.g. a bare service context
        return "unknown"


def append(home: Path, *, action: str, outcome: str, source: Optional[str],
           target: Optional[str], detail: str = "", now: Optional[datetime] = None,
           **extra) -> dict:
    """Append one line and return the record that was written.

    ``home`` must already exist. A mistyped data folder must fail here, not be
    created and then quietly hold a log nobody will read.
    """
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}; expected one of {OUTCOMES}")
    home = Path(home)
    if not home.is_dir():
        raise FileNotFoundError(f"{home} is not a folder; the deploy log is kept in the "
                                f"instance's data folder and does not create one")
    record = {
        "at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action": action,
        "outcome": outcome,
        "from": source,
        "to": target,
        "operator": _operator(),
        "host": platform.node(),
        "detail": detail,
    }
    record.update(extra)
    line = json.dumps(record, sort_keys=True, ensure_ascii=False)
    with open(home / LOG_NAME, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return record


def read(home: Path) -> List[dict]:
    """Every record, oldest first.

    A line that is not a JSON object comes back as ``{"unreadable": <the line>}``.
    Dropping it would shorten the history without saying so.
    """
    path = Path(home) / LOG_NAME
    if not path.exists():
        return []
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except ValueError:
            record = None
        out.append(record if isinstance(record, dict) else {"unreadable": raw})
    return out


def last_success(home: Path) -> Optional[dict]:
    """The newest record that left the instance on a new build, or ``None``."""
    for record in reversed(read(home)):
        if record.get("outcome") == "ok":
            return record
    return None
