#!/usr/bin/env python3
"""Fail if ``axis-api-atlas`` did not come from its private git repo.

This is the mechanical guard for issue #179 (dependency confusion).

``axis-api-atlas`` is private (``mrdnlabs/axis-api-atlas``) and its name is
UNREGISTERED on PyPI. If the reference ever regresses to a bare
``axis-api-atlas>=0.1.0``, pip resolves it against PyPI — where anyone may
claim the name — and executes that stranger's code inside the venv that the
``admz`` Windows service later runs as LocalSystem.

pip records where every distribution actually came from in PEP 610
``direct_url.json``:

* installed from a VCS URL  -> ``direct_url.json`` with a ``vcs_info`` block
* installed from a local dir -> ``direct_url.json`` with a ``dir_info`` block
* **installed from an index (PyPI) -> no ``direct_url.json`` at all**

So "the file is missing" is precisely the failure we must never ship. Checking
the requirements *text* would not catch a stale wheel, a cached artifact, or a
`pip install --upgrade` that quietly re-resolved the name; checking the
installed metadata catches all of them.

THIS SCRIPT IS NOW THE ONLY MECHANICAL GUARD.
------------------------------------------------------------------------------
#235 moved the atlas requirement out of ``requirements.txt`` and into the
``atlas`` extra in ``setup.py``, because the ``git+ssh://`` reference demanded a
deploy key that only CI has and broke every off-CI install. That was the right
fix, but it means there is no longer a direct reference sitting in the file most
people read. Nothing except this script now stands between a developer typing
``pip install axis-api-atlas`` and an index install. Its CI run must not become
skippable.

TWO SEPARATE CHECKS, WITH DIFFERENT JOBS
------------------------------------------------------------------------------
1. PROVENANCE (security, #179): did this come from git or a local dir, rather
   than an index? Fails closed. This is the one that matters.

2. REVISION (cache integrity / reproducibility, #232): is the installed commit
   the one ``setup.py:ATLAS_SHA`` asked for? This is NOT a security control —
   it cannot catch anything the direct reference does not already catch, since
   a mismatch would mean pip installed a commit it was not asked for. What it
   does catch is real and non-hypothetical: ``.github/actions/setup-admz`` runs
   ``actions/setup-python`` with ``cache: pip`` keyed on ``requirements.txt``,
   and atlas is no longer IN ``requirements.txt`` — so the cache key no longer
   changes when the pin changes. A restored cache serving a previously-built
   atlas wheel from a different commit is exactly the failure this catches, and
   nothing else in the pipeline would notice.

   The revision check only applies to the ``vcs_info`` branch. A local/editable
   install has no commit to assert, and demanding one would break every
   developer laptop on day one.

The commit is PRINTED on every run regardless of whether the assertion applies.
That printing is arguably worth more than the assertion: it is what lets
``git bisect`` tell an ADMZ regression from an atlas one, which was #232's
actual goal.

Exit 0 = provenance proven. Exit 1 = refuse to continue.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DIST = "axis-api-atlas"
EXPECTED_REPO = "mrdnlabs/axis-api-atlas"

# setup.py is the single source of truth for the pin. Parsing it here rather
# than hard-coding the SHA is the whole point: two copies of a SHA is two places
# to bump, and they drift silently in the stale direction — the exact failure
# shape #232 objects to.
SETUP_PY = Path(__file__).resolve().parents[2] / "setup.py"


def _fail(title: str, *lines: str) -> None:
    # GitHub Actions renders ::error as an annotation on the job.
    print(f"::error title={title}::{lines[0] if lines else title}")
    print()
    print(f"!! {title}")
    for line in lines:
        print(f"   {line}")
    sys.exit(1)


def _expected_sha() -> str | None:
    """Read ATLAS_SHA out of setup.py without importing it.

    Returns None if setup.py or the constant cannot be found — the revision
    check is then skipped with a warning rather than failing the job. A missing
    pin is a reason to look, not a reason to block the suite; the provenance
    check above is the one that fails closed.
    """
    try:
        src = SETUP_PY.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^ATLAS_SHA\s*=\s*"([0-9a-fA-F]{40})"', src, re.MULTILINE)
    return match.group(1).lower() if match else None


def main() -> None:
    try:
        from importlib.metadata import PackageNotFoundError, distribution
    except ImportError:  # pragma: no cover - Python < 3.8 is unsupported
        _fail("Python too old", "importlib.metadata is required.")

    try:
        dist = distribution(DIST)
    except PackageNotFoundError:
        _fail(
            f"{DIST} is not installed",
            "The dependency install step did not produce this package.",
            "Check the 'Install dependencies' step above for the real error.",
            "",
            "Note: since #235 the atlas requirement lives in the 'atlas' extra,",
            "not in requirements.txt. Installing requirements.txt alone will NOT",
            "bring it in. CI must run `pip install -e \".[atlas]\"`; developers",
            "run `pip install -e ../axis-api-atlas`.",
        )
        return

    raw = dist.read_text("direct_url.json")

    if not raw:
        _fail(
            f"{DIST} was installed from a package index",
            f"{DIST} has no PEP 610 direct_url.json, which means pip resolved",
            "it from an index (PyPI) rather than from its private git repo.",
            "",
            "This is exactly the dependency-confusion hazard of issue #179:",
            "the name is unregistered on PyPI, so an index install is either a",
            "typo-squatted package or an attacker's.",
            "",
            "Fix: the 'atlas' extra in setup.py must keep the PEP 508 direct",
            "reference, built from ATLAS_SHA:",
            f"    {DIST} @ git+ssh://git@github.com/{EXPECTED_REPO}.git@<ATLAS_SHA>",
            "and must NOT be reduced to a bare 'axis-api-atlas>=0.1.0'.",
            "Do not 'fix' a failing install by relaxing it to a bare name.",
        )

    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail(f"{DIST} direct_url.json is unreadable", str(exc))
        return

    url = str(info.get("url", ""))

    if "vcs_info" in info:
        vcs = info["vcs_info"]
        if EXPECTED_REPO not in url:
            _fail(
                f"{DIST} came from an unexpected repository",
                f"expected a URL containing '{EXPECTED_REPO}'",
                f"actual url: {url}",
                "Refusing to continue: a redirected or mistyped source is",
                "indistinguishable from a hostile one.",
            )
        commit = str(vcs.get("commit_id", "") or "unknown")
        requested = vcs.get("requested_revision", "(default branch)")
        print(f"OK  {DIST} installed from git")
        print(f"    url       : {url}")
        print(f"    revision  : {requested}")
        print(f"    commit    : {commit}")

        # --- revision check (cache integrity, not security) ------------------
        expected = _expected_sha()
        if expected is None:
            print(
                "    !! could not read ATLAS_SHA from setup.py — revision check "
                "SKIPPED"
            )
            print(f"       (looked in {SETUP_PY})")
            return

        # Assert on commit_id, not requested_revision. commit_id is what pip
        # actually resolved and checked out; requested_revision is what it was
        # asked for, which is the thing we are trying to verify against.
        if commit.lower() != expected:
            _fail(
                f"{DIST} is at the wrong commit",
                f"setup.py:ATLAS_SHA pins {expected}",
                f"but the installed distribution is at {commit}",
                "",
                "This is a reproducibility/cache failure, not a security one —",
                "pip installed a commit other than the one it was asked for.",
                "The likely cause is a restored pip cache serving a wheel built",
                "from an earlier atlas commit: setup-admz keys `cache: pip` on",
                "requirements.txt, and atlas is not in that file, so the",
                "cache key does not change when the pin does.",
                "",
                "Fix: re-run with the pip cache cleared. If it persists the pin",
                "and the lockstep between setup.py and the install step have",
                "diverged — check that CI installs the 'atlas' extra.",
            )
        print(f"    pin       : matches setup.py:ATLAS_SHA ({expected})")
        return

    if "dir_info" in info:
        # A local/editable install — how developers work (README
        # "Installation") and, since #235, the primary path not the fallback.
        #
        # Not an index install, so it is not the #179 hazard, and the revision
        # check does not apply: there is no commit to assert against.
        #
        # Worth saying plainly rather than leaving implicit: this branch
        # accepts ANY local directory. It does not verify the directory actually is
        # atlas, or that it came from mrdnlabs. That is a deliberate, accepted
        # hole — a developer pointing pip at a local path they control is not
        # the dependency-confusion threat #179 is about, and checking it would
        # mean second-guessing the developer's own checkout. But #235 promoted
        # local installs from "how some people work" to "the documented
        # default", so the hole is load-bearing in a way it was not before.
        editable = bool(info["dir_info"].get("editable"))
        kind = "editable" if editable else "local directory"
        print(f"OK  {DIST} installed from a {kind}: {url}")
        print("    (local install — not an index; #179 hazard does not apply)")
        print("    revision check SKIPPED: local dir has no commit to assert")
        return

    _fail(
        f"{DIST} provenance is unrecognised",
        f"direct_url.json contained neither vcs_info nor dir_info: {raw}",
    )


if __name__ == "__main__":
    main()
