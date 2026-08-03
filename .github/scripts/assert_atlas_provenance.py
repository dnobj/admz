#!/usr/bin/env python3
"""Fail if ``axis-api-atlas`` did not come from its private git repo.

This is the mechanical guard for issue #179 (dependency confusion).

``axis-api-atlas`` is private (``mrdnlabs/axis-api-atlas``) and its name is
UNREGISTERED on PyPI. If ``requirements.txt`` ever regresses to a bare
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

Exit 0 = provenance proven. Exit 1 = refuse to continue.
"""

from __future__ import annotations

import json
import sys

DIST = "axis-api-atlas"
EXPECTED_REPO = "mrdnlabs/axis-api-atlas"


def _fail(title: str, *lines: str) -> None:
    # GitHub Actions renders ::error as an annotation on the job.
    print(f"::error title={title}::{lines[0] if lines else title}")
    print()
    print(f"!! {title}")
    for line in lines:
        print(f"   {line}")
    sys.exit(1)


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
            "Fix: requirements.txt must keep the PEP 508 direct reference",
            f"    {DIST} @ git+ssh://git@github.com/{EXPECTED_REPO}.git@main",
            "and must NOT be reduced to a bare 'axis-api-atlas>=0.1.0'.",
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
        commit = vcs.get("commit_id", "unknown")
        requested = vcs.get("requested_revision", "(default branch)")
        print(f"OK  {DIST} installed from git")
        print(f"    url       : {url}")
        print(f"    revision  : {requested}")
        print(f"    commit    : {commit}")
        return

    if "dir_info" in info:
        # A local/editable install — how developers work (README "Installation").
        # Not an index install, so it is not the #179 hazard.
        editable = bool(info["dir_info"].get("editable"))
        kind = "editable" if editable else "local directory"
        print(f"OK  {DIST} installed from a {kind}: {url}")
        print("    (local install — not an index; #179 hazard does not apply)")
        return

    _fail(
        f"{DIST} provenance is unrecognised",
        f"direct_url.json contained neither vcs_info nor dir_info: {raw}",
    )


if __name__ == "__main__":
    main()
