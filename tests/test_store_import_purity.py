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
  and fails unless CONVERTED covers them exactly. Store #18 cannot appear
  without being listed. Through stages 1-3b this was ``CONVERTED | PENDING`` so
  the same held mid-conversion; PENDING is gone now that all 17 are converted.
* :func:`test_importing_the_module_creates_nothing` asserts the import really
  happened -- the module is in ``sys.modules`` -- before believing the absence,
  so it cannot pass by importing nothing.

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
# The inventory. All 17 stores, converted across five stages.
# test_inventory_is_complete asserts it covers every store module in the tree,
# in both directions -- an unlisted store and a dropped entry both fail.
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
    # Stage 2 (#258). Highest blast radius — imported at module scope by ~15
    # modules in admz/ and reached from ~120 sites — so it moves early, to keep
    # the window where it uses the old idiom and others use the new one short.
    "admz.fleet_settings": StoreSpec(
        cls="FleetSettings",
        exercise="s.set('probe_key', 'probe_value')",
    ),
    # Stage 3a (#258). The six stores whose _ensure_table only creates schema
    # -- no column migration -- and which have no open issue needing reviewer
    # context. Stage 3b takes the five where moving _ensure_table also moves a
    # migration (api.confirm_store, chatbot.sessions, fleet.health,
    # snapshot.drift_alerts) or where an open issue does (audit #270,
    # confirm_store #266).
    "admz.api.capture": StoreSpec(
        cls="CaptureStore", exercise="s.get_session('no-such-token')"),
    "admz.api_keys": StoreSpec(cls="ApiKeyStore", exercise="s.list()"),
    "admz.events.detections": StoreSpec(cls="DetectionStore", exercise="s.list()"),
    "admz.events.store": StoreSpec(cls="EventStore", exercise="s.count()"),
    "admz.events.watched": StoreSpec(cls="WatchedEventStore", exercise="s.list()"),
    "admz.tasks.store": StoreSpec(cls="TaskStore", exercise="s.list()"),
    # Stage 3b (#258). The five whose _ensure_table carries a schema COLUMN
    # MIGRATION -- so moving it into _connect() moves when an ALTER TABLE runs,
    # not just a CREATE TABLE IF NOT EXISTS -- or which had an issue in flight
    # when 3a landed. audit is the latter: it has no migration at all, and was
    # held back only because #270/#276 was open against it.
    "admz.api.confirm_store": StoreSpec(
        cls="ConfirmStore", exercise="s.get_session('no-such-token')"),
    "admz.audit": StoreSpec(cls="AuditLog", exercise="s.list_recent(limit=1)"),
    "admz.chatbot.sessions": StoreSpec(
        cls="ChatSessionStore", exercise="s.list_conversations('probe')"),
    "admz.fleet.health": StoreSpec(cls="DeviceHealthStore", exercise="s.list_all()"),
    "admz.snapshot.drift_alerts": StoreSpec(
        cls="DriftAlertStore", exercise="s.list_alerts()"),
    # Stage 4 (#258) — the last four. These were ALREADY "lazy" before #258,
    # and that is the point: measured at plan time, a lazy singleton binds its
    # path at FIRST USE and never rebinds, which is behaviourally identical to
    # an eager one. Laziness moved when the freeze happened; it did not thaw it.
    "admz.demos.store": StoreSpec(cls="DemoStore", exercise="s.list()"),
    "admz.demos.inference.proposals": StoreSpec(
        cls="ProposalStore", exercise="s.list()"),
    "admz.demos.inference.runs": StoreSpec(
        cls="InferenceRunStore", exercise="s.list()"),
    "admz.session_store": StoreSpec(
        cls="SessionStore", exercise="s.purge_expired()"),
    # Store #18, added by #314 rather than converted by #258 — and the reason
    # this inventory exists. It was an in-memory dict; making it persistent
    # created a new store, and the latch caught it on the first run before any
    # human looked. Built to the call-time contract from the start.
    "admz.mcp.temp_credentials": StoreSpec(
        cls="TempCredentialManager",
        exercise="s.count_active_for_device('probe-device')"),
    # Store #19, added by #188 part 2. The firmware artifact digests live in
    # the database rather than in a sidecar beside the artifact, because a
    # sidecar would sit in the very directory the threat model says an attacker
    # can write — a trust anchor must not live inside the zone it vouches for.
    "admz.firmware.pinning": StoreSpec(
        cls="ArtifactStore",
        exercise="s.get('probe-artifact.bin')"),
}

#: Modules whose *import* provably creates nothing.
#:
#: As of stage 3b this is EVERY converted module: measured, importing any of
#: them against a non-existent ADMZ_HOME creates nothing. It stayed a separate
#: set from CONVERTED through stages 1-3a because import purity needs a
#: module's whole TRANSITIVE store graph converted, and until sessions moved
#: it was not true for chatbot.usage. Kept as a separate name rather than
#: inlined, so a future module that reintroduces import-time I/O has somewhere
#: to be excluded from without silently dropping out of CONVERTED.
IMPORT_PURE: set[str] = set(CONVERTED)

# PENDING is GONE, and its absence is the deliverable.
#
# Through stages 1-3b it held the not-yet-converted stores, and
# test_inventory_is_complete asserted `discovered == CONVERTED | PENDING` so a
# store could never be missing from BOTH lists mid-conversion. With every store
# converted the assertion becomes `discovered == CONVERTED`, which is strictly
# stronger, not weaker: set equality still fails in both directions -- an
# unlisted store #18 makes `discovered` the larger side, and a store dropped
# from CONVERTED makes it the smaller one. Both were re-verified by mutation on
# this final shape rather than argued.
#
# So an empty PENDING would be dead weight, and keeping one "just in case"
# would invite someone to park a new store there instead of converting it.


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
        listed = set(CONVERTED)
        assert discovered == listed, (
            f"store inventory drifted.\n"
            f"  in tree but unlisted: {sorted(discovered - listed)}\n"
            f"  listed but not found: {sorted(listed - discovered)}"
        )

    def test_something_is_actually_converted(self):
        """Anti-vacuity: every parametrised test below draws from CONVERTED,
        so an empty CONVERTED would silently skip the whole file."""
        assert CONVERTED

    def test_every_store_in_the_tree_is_converted(self):
        """The claim #258 was filed to make true, stated as an assertion.

        Not "we converted some stores" — every SQLite store discovered in
        ``admz/`` is in CONVERTED, and every entry in CONVERTED is exercised by
        the parametrised tests below for both properties. When this passes,
        "every store resolves its DB path at call time" is a checked fact.
        """
        discovered = _discover_store_modules()
        assert discovered == set(CONVERTED)
        # 17 at the end of #258; 18 since #314 made temp credentials
        # persistent. Updated deliberately, which is what this assertion is
        # for — it fired on the new store before any human looked at the diff.
        assert len(discovered) == 19, (
            f"expected 19 stores, found {len(discovered)} — if a store was "
            "added or removed, update this number deliberately"
        )

    def test_import_pure_is_a_subset_of_converted(self):
        """A module cannot be import-pure while its own store still does I/O.
        Stops someone promoting a module into IMPORT_PURE ahead of its store."""
        assert IMPORT_PURE <= set(CONVERTED)

    def test_import_pure_is_not_empty(self):
        """Anti-vacuity for the import-purity parametrisation, which would
        collect nothing — and so assert nothing — if IMPORT_PURE emptied."""
        assert IMPORT_PURE

    @pytest.mark.parametrize("module", sorted(CONVERTED))
    def test_no_duplicate_method_definitions(self, module):
        r"""A converted store must define each method exactly once.

        Earned the hard way in stage 3a. The mechanical edit that converts a
        store replaced ``__init__`` but, in two files where an ``@property``
        sits between ``__init__`` and ``_connect``, stopped short — leaving the
        ORIGINAL ``_connect`` and ``_ensure_table`` further down the class.
        Python takes the last definition, so the old ones silently won and the
        schema was never created: ``DetectionStore.list()`` raised
        ``no such table: event_detections`` while every other check passed.

        The rebind/no-IO tests do catch it once a store is in CONVERTED, but
        only then; this catches it structurally and points straight at the
        cause rather than at a missing table.

        The regex ends in ``\(`` deliberately. An earlier version used a
        ``\b`` word boundary that got written through a shell heredoc as a
        literal backspace byte, so it matched nothing and this guard passed
        vacuously — caught only by mutation-checking it.
        """
        path = REPO_ROOT / Path(*module.split(".")).with_suffix(".py")
        src = path.read_text(encoding="utf-8")
        for name in ("_connect", "_ensure_table", "_create_schema", "_db_path"):
            n = len(re.findall(rf"^    def {name}\(", src, re.M))
            assert n <= 1, f"{module}: {name} defined {n} times"


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


@pytest.mark.parametrize("module", sorted(IMPORT_PURE))
def test_importing_the_module_creates_nothing(module, tmp_path):
    """The structural guarantee, for modules that have earned it.

    Not merely "the store does no I/O" — *importing the module*, with every
    transitive import it drags in, must leave the filesystem untouched.
    """
    home = tmp_path / "never-created"
    assert not home.exists(), "the fixture must start with NO ADMZ_HOME"
    result = _run(
        f"import os\n"
        f"from pathlib import Path\n"
        f"import {module}\n"
        f"import sys\n"
        f"loaded = len([m for m in sys.modules if m.startswith('admz')])\n"
        f"print('SELF', {module!r} in sys.modules)\n"
        f"print('LOADED', loaded)\n"
        f"print('EXISTS', Path(os.environ['ADMZ_HOME']).exists())\n",
        home,
    )
    assert result.returncode == 0, result.stderr
    # Anti-vacuity: "nothing was created" is trivially true if nothing was
    # imported. Prove the import really happened before believing the absence.
    #
    # Asserting the module itself is in sys.modules, rather than a magic count:
    # the count varies with how leaf-like a module is (api_keys and audit pull
    # in 5, chatbot.usage 11), so a threshold tuned to one silently fails the
    # others. That is exactly what happened in stage 3b when this read `> 5`.
    assert "SELF True" in result.stdout, f"{module} did not actually import"
    loaded = int(result.stdout.split("LOADED")[1].split()[0])
    assert loaded >= 3, f"import surface was only {loaded} admz modules"
    assert "EXISTS False" in result.stdout
    assert not home.exists()


# The stage-2 tripwire is gone, and its removal is the point.
#
# It asserted that importing admz.chatbot.usage STILL created ADMZ_HOME, named
# admz.chatbot.sessions as the remaining cause, and said to invert it when that
# store converted. Stage 3b converted it, both tripwire tests went red on the
# first run, and IMPORT_PURE grew to cover every converted module instead.
#
# Recorded rather than silently deleted: a characterisation test that fires on
# schedule is the mechanism working, not a test that broke.
