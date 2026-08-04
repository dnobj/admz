"""#258 — stores must resolve their DB path at call time, and do no I/O to exist.

This is the harness the staged conversion is measured against. It lands in
stage 1 with one store converted and grows as stores move.

## What the conversion is actually for

Not "laziness". Measured before the plan was written: the four stores that were
already converted to a lazy ``get_x()`` singleton bind their path at *first
use* and never rebind — behaviourally identical to the eager ones. It is the
**cache in ``__init__``**, not the timing, that freezes the path. So the
property under test is *call-time resolution*, and the two things that follow
from it:

1. constructing a store performs **no I/O**, so a module-level singleton costs
   nothing at import; and
2. a store **honours a changed** ``ADMZ_DB_PATH`` / ``ADMZ_HOME``, for the life
   of the instance.

(2) is the one nothing in the suite asserted before this file, which is why a
regression to caching in ``__init__`` would have gone unnoticed.

## The vacuity trap in this specific shape

*"No store connected"* is trivially true if nothing imported a store. A
subprocess that imports nothing and asserts no database appeared would pass
forever and read as coverage — the same failure mode as #207's skipped ACL test
and #250's "no broad principal can read it", which is satisfied by a file
nobody can read.

Two latches against it:

* every subprocess test asserts the target directory is **absent first**, and
  then asserts a positive — that first *use* does create it and the value round
  trips. A test that proved only absence would pass if the store were broken.
* :func:`test_inventory_is_complete` rediscovers the store modules from source
  and fails if the union of CONVERTED and PENDING does not cover them. Store #18
  cannot appear without being listed, even mid-conversion.

## Why these are subprocess tests

The subject is construction- and import-time behaviour. By the time pytest has
collected anything, every singleton in this interpreter already exists and the
directory exists with it. ``tests/test_api_import_isolation.py`` and
``tests/test_fresh_install.py`` use the same shape for the same reason.

This does **not** replace ``tests/conftest.py``'s ADMZ_HOME redirect (#257/#260).
That guard makes the default safe; this makes it honourable. Both are permanent,
and #260's guard must keep passing at every stage of this conversion.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class StoreSpec:
    """How to construct a store and make it actually touch its database."""

    cls: str
    exercise: str


# --------------------------------------------------------------------------
# The inventory. CONVERTED grows and PENDING shrinks with each stage; the
# final stage deletes PENDING entirely. test_inventory_is_complete asserts
# the two together always cover every store module in the tree.
# --------------------------------------------------------------------------

CONVERTED: dict[str, StoreSpec] = {
    # Stage 1 (#258). Chosen as the proving ground because it is
    # self-contained, has no cross-store callers, and its failure mode is a
    # chat token counter rather than the fleet.
    "admz.chatbot.usage": StoreSpec(
        cls="TokenUsageStore",
        exercise=(
            "s.record_turn(principal='p', model='m', "
            "input_tokens=1, output_tokens=2)"
        ),
    ),
}

PENDING: set[str] = {
    # Stage 2
    "admz.fleet_settings",
    # Stage 3 — the remaining eager stores
    "admz.api.capture",
    "admz.api.confirm_store",
    "admz.api_keys",
    "admz.audit",
    "admz.chatbot.sessions",
    "admz.events.detections",
    "admz.events.store",
    "admz.events.watched",
    "admz.fleet.health",
    "admz.snapshot.drift_alerts",
    "admz.tasks.store",
    # Stage 4 — the lazy stores, plus retiring demos/store's __new__ hack
    "admz.demos.store",
    "admz.demos.inference.proposals",
    "admz.demos.inference.runs",
    "admz.session_store",
}


def _discover_store_modules() -> set[str]:
    """Every module defining a SQLite store keyed off the shared ADMZ db.

    Textual rather than AST: the shape is uniform across all seventeen
    (``_default_db_path()`` plus ``def __init__(self, db_path``), and a
    heuristic that is easy to read is worth more here than one that is hard to
    get wrong. If a future store deviates, this test fails loudly and someone
    updates the heuristic — which is the outcome we want either way.
    """
    found = set()
    for path in sorted((REPO_ROOT / "admz").rglob("*.py")):
        src = path.read_text(encoding="utf-8", errors="replace")
        if "_default_db_path" in src and re.search(
            r"def __init__\(self, db_path", src
        ):
            rel = path.relative_to(REPO_ROOT).with_suffix("")
            found.add(".".join(rel.parts))
    return found


def _run(statement: str, home: Path, extra_env: dict | None = None):
    env = dict(os.environ)
    env["ADMZ_HOME"] = str(home)
    # Pinned: paths.admz_home() falls back to Path.home()/".admz", which is a
    # real directory on a developer box and would mask the whole test.
    env["HOME"] = str(home.parent)
    env["USERPROFILE"] = str(home.parent)
    env["PYTHONPATH"] = str(REPO_ROOT)
    for name in ("ADMZ_DB_PATH", "ADMZ_KEY_PATH", "ADMZ_CONFIG_REPO_PATH",
                 "ADMZ_REPO_PATH_ROOT", "ADMZ_SURVEY_OUT", "ADMZ_SURVEY_WORK"):
        env.pop(name, None)
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True, text=True, env=env, timeout=300,
    )


class TestInventory:
    def test_inventory_is_complete(self):
        """Store #18 cannot escape, at any stage of the conversion."""
        discovered = _discover_store_modules()
        listed = set(CONVERTED) | PENDING
        assert discovered == listed, (
            f"store inventory drifted.\n"
            f"  in tree but unlisted: {sorted(discovered - listed)}\n"
            f"  listed but not found: {sorted(listed - discovered)}"
        )

    def test_converted_and_pending_are_disjoint(self):
        assert not (set(CONVERTED) & PENDING)

    def test_something_is_actually_converted(self):
        """Anti-vacuity: every parametrised test below draws from CONVERTED,
        so an empty CONVERTED would silently skip the whole file."""
        assert CONVERTED


@pytest.mark.parametrize("module", sorted(CONVERTED))
class TestConvertedStores:
    def test_construction_does_no_io(self, module, tmp_path):
        """A store must cost nothing to exist — that is what makes a
        module-level singleton safe at import."""
        spec = CONVERTED[module]
        home = tmp_path / "never-created"
        assert not home.exists(), "the fixture must start with NO ADMZ_HOME"

        result = _run(
            f"import os\n"
            f"from pathlib import Path\n"
            f"from {module} import {spec.cls}\n"
            f"h = Path(os.environ['ADMZ_HOME'])\n"
            f"import shutil; shutil.rmtree(h, ignore_errors=True)\n"
            f"print('BEFORE', h.exists())\n"
            f"s = {spec.cls}()\n"
            f"print('AFTER_CTOR', h.exists())\n"
            f"{spec.exercise}\n"
            f"print('AFTER_USE', h.exists())\n",
            home,
        )
        assert result.returncode == 0, result.stderr
        assert "BEFORE False" in result.stdout
        assert "AFTER_CTOR False" in result.stdout, (
            "constructing the store performed I/O — it must not"
        )
        # The positive half. Without it, a store that simply never worked
        # would pass the assertion above.
        assert "AFTER_USE True" in result.stdout, (
            "first use did not create the data directory"
        )

    def test_store_honours_a_rebind(self, module, tmp_path):
        """The property laziness cannot give, and that nothing else asserts.

        Same instance, used before and after the environment changes. If the
        path were cached in __init__ (or at first use, as the 'lazy' stores
        do), B would never be created.
        """
        spec = CONVERTED[module]
        home = tmp_path / "home"
        a = tmp_path / "a" / "admz.db"
        b = tmp_path / "b" / "admz.db"

        result = _run(
            f"import os\n"
            f"from pathlib import Path\n"
            f"from {module} import {spec.cls}\n"
            f"s = {spec.cls}()\n"
            f"os.environ['ADMZ_DB_PATH'] = os.environ['PROBE_A']\n"
            f"{spec.exercise}\n"
            f"os.environ['ADMZ_DB_PATH'] = os.environ['PROBE_B']\n"
            f"{spec.exercise}\n"
            f"print('A', Path(os.environ['PROBE_A']).exists())\n"
            f"print('B', Path(os.environ['PROBE_B']).exists())\n",
            home,
            extra_env={"PROBE_A": str(a), "PROBE_B": str(b)},
        )
        assert result.returncode == 0, result.stderr
        assert "A True" in result.stdout
        assert "B True" in result.stdout, (
            "the store ignored a changed ADMZ_DB_PATH — its path is cached"
        )


class TestStagingTripwire:
    """Characterisation of what is NOT yet true, so the sequence enforces itself.

    ``admz.chatbot.usage`` imports ``admz.fleet_settings`` at module level, and
    fleet_settings is stage 2. So *importing* the stage-1 module still creates
    ADMZ_HOME even though constructing its store does not.

    That is the honest state, and it is asserted rather than glossed: module
    import-purity is only reachable once a module's whole transitive store
    graph is converted. This test **must be inverted in stage 2** — when
    fleet_settings lands, importing this module will stop creating anything and
    this test will fail, which is exactly the reminder the next author needs.
    """

    def test_importing_the_stage1_module_still_creates_admz_home(self, tmp_path):
        home = tmp_path / "never-created"
        assert not home.exists()
        result = _run(
            "import os\n"
            "from pathlib import Path\n"
            "import admz.chatbot.usage\n"
            "print('EXISTS', Path(os.environ['ADMZ_HOME']).exists())\n",
            home,
        )
        assert result.returncode == 0, result.stderr
        assert "EXISTS True" in result.stdout, (
            "importing admz.chatbot.usage no longer creates ADMZ_HOME — "
            "if admz.fleet_settings has been converted (stage 2), delete this "
            "tripwire and add a real module-import-purity assertion instead"
        )

    def test_the_transitive_dependency_is_named_in_pending(self):
        """Pins the reason above to the inventory, so the tripwire cannot be
        deleted without fleet_settings actually having moved."""
        assert "admz.fleet_settings" in PENDING
