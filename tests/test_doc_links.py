"""Relative links in Markdown docs must resolve to real files (GH #173).

There is no CI and no link checker, and `DEPLOYMENT_WINDOWS.md` accumulated a
`## See also` list that pointed only at the ADRs its own body had superseded.
While fixing that I hand-wrote four new ADR links and **got all four filenames
wrong** — plausible-looking slugs for real decisions. That is the failure this
guards: a link that reads correctly in review and 404s for the reader.

Deliberately narrow. It checks only *relative* links to paths inside the repo:

* external `http(s)://` and `mailto:` links — not our business, and checking
  them would need the network;
* pure `#anchor` links — a heading checker is a different tool with different
  false positives;
* code spans and fenced blocks — `[foo](bar)` inside a shell example is not a
  link, and a doc showing Markdown syntax should not fail for it;
* ``docs/vapix-docs/`` — a vendored mirror of Axis's own documentation, whose
  cross-references point into Axis's site structure. 169 of those files fail
  this check and none of it is ours to fix; policing it would mean either
  rewriting a third party's text or carrying a permanent ignore list.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOC_DIRS = ("docs",)

#: Vendored third-party documentation — see the module docstring.
EXCLUDE = ("docs/vapix-docs/",)

#: Pre-existing broken links, as ``(doc, target)``. **A baseline, not an
#: exemption.** Two classes, both real 404s on GitHub, and both needing
#: judgement that this guard's own PR should not be making: plan files writing
#: repo-root-relative paths (``admz/events/store.py`` from
#: ``docs/specification/plans/``), and links to things that moved or were never
#: written (the catalog now lives in the ``axis-api-atlas`` repo; ``hierarchy.md``
#: and ``plans/dev-prod-split.md`` exist nowhere).
#:
#: ``test_the_baseline_only_shrinks`` fails once an entry starts resolving, so
#: the set cannot outlive the debt. Burn-down: GH #376.
KNOWN_BROKEN = {
    ("docs/specification/INDEX.md", "plans/dev-prod-split.md"),
    ("docs/specification/decisions/0001-organize-catalog-by-cgi.md", "../../../catalog/vapix/index/by-risk.yaml"),
    ("docs/specification/decisions/0001-organize-catalog-by-cgi.md", "../../../catalog/vapix/index/by-task.yaml"),
    ("docs/specification/decisions/0027-pluggable-control-families-and-config-collectors.md", "hierarchy.md"),
    ("docs/specification/plans/acs-poller-watermark.md", "admz/api/routes/events.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "admz/events/acs_firebird_ingest.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "admz/events/acs_ingest.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "admz/events/config.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "admz/events/evaluator.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "admz/events/ingest.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "admz/events/store.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "admz/modules/acs_pro/events.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "admz/modules/acs_pro/routes.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "admz/modules/acs_pro/tools.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "admz/snapshot/ignore.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "tests/test_acs_detections.py"),
    ("docs/specification/plans/acs-poller-watermark.md", "tests/test_acs_event_ingest.py"),
    ("docs/specification/plans/acs-refire-on-callback-failure.md", "admz/events/acs_firebird_ingest.py"),
    ("docs/specification/plans/acs-refire-on-callback-failure.md", "admz/events/acs_ingest.py"),
    ("docs/specification/plans/acs-refire-on-callback-failure.md", "admz/events/detections.py"),
    ("docs/specification/plans/acs-refire-on-callback-failure.md", "admz/events/evaluator.py"),
    ("docs/specification/plans/acs-refire-on-callback-failure.md", "admz/events/subscriptions.py"),
    ("docs/specification/plans/acs-refire-on-callback-failure.md", "admz/events/wsstream.py"),
    ("docs/specification/plans/acs-refire-on-callback-failure.md", "admz/modules/acs_pro/routes.py"),
    ("docs/specification/plans/acs-refire-on-callback-failure.md", "tests/test_event_detections.py"),
    ("docs/specification/plans/acs-refire-on-callback-failure.md", "tests/test_events_watched_scoping.py"),
    ("docs/specification/plans/demo-setup-wizard.md", "admz/demos/fragments.py"),
    ("docs/specification/plans/demo-setup-wizard.md", "admz/operations.py"),
    ("docs/specification/plans/demo-setup-wizard.md", "admz/snapshot/drift.py"),
    ("docs/specification/plans/demo-setup-wizard.md", "admz/snapshot/restore.py"),
    ("docs/specification/requirements/plans.md", "../../tests/test_fleet_concurrency.py"),
    ("docs/specification/requirements/snapshot-restore.md", "../../tests/test_fleet_concurrency.py"),
}

#: ``[text](target)`` — target captured up to the first space (Markdown allows
#: a trailing "title") or the closing paren.
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_FENCE = re.compile(r"^\s*(```|~~~)")


def _markdown_files():
    for d in DOC_DIRS:
        for path in sorted((REPO / d).rglob("*.md")):
            rel = str(path.relative_to(REPO)).replace("\\", "/")
            if any(rel.startswith(x) for x in EXCLUDE):
                continue
            yield path


def _links_in(path: Path):
    """Yield ``(lineno, target)`` for links outside fenced blocks and code spans."""
    in_fence = False
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if _FENCE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = re.sub(r"`[^`]*`", "", raw)      # drop inline code spans
        for m in _LINK.finditer(line):
            yield lineno, m.group(1)


def _is_checkable(target: str) -> bool:
    if target.startswith(("http://", "https://", "mailto:", "#", "<")):
        return False
    return True


@pytest.mark.parametrize("doc", list(_markdown_files()),
                         ids=lambda p: str(p.relative_to(REPO)).replace("\\", "/"))
def test_relative_links_resolve(doc):
    broken = []
    for lineno, target in _links_in(doc):
        if not _is_checkable(target):
            continue
        path_part = target.split("#", 1)[0]
        if not path_part:                        # pure anchor after stripping
            continue
        rel = str(doc.relative_to(REPO)).replace("\\", "/")
        if (rel, target) in KNOWN_BROKEN:
            continue
        if not (doc.parent / path_part).resolve().exists():
            broken.append(f"{rel}:{lineno} -> {target}")
    assert not broken, (
        "broken relative links:\n  " + "\n  ".join(broken)
        + "\n\nIf the target moved, fix the link. Do NOT add it to "
          "KNOWN_BROKEN -- that set is a frozen record of debt predating this "
          "guard, not somewhere to put new breakage."
    )


def test_the_checker_sees_the_deployment_guide_links():
    """Guard the guard: if the link regex or the fence skipping breaks, every
    doc trivially "passes" with zero links examined. This pins that the file
    the guard was written for is actually being read."""
    doc = REPO / "docs" / "DEPLOYMENT_WINDOWS.md"
    targets = [t for _, t in _links_in(doc) if _is_checkable(t)]
    assert len([t for t in targets if "decisions/" in t]) >= 7


def test_the_baseline_only_shrinks():
    """A fixed link must leave ``KNOWN_BROKEN``, or the set rots into a
    permanent exemption that hides the next real break in the same file."""
    fixed = []
    for rel, target in sorted(KNOWN_BROKEN):
        path_part = target.split("#", 1)[0]
        if ((REPO / rel).parent / path_part).resolve().exists():
            fixed.append(f"{rel} -> {target}")
    assert not fixed, (
        "these resolve now; remove them from KNOWN_BROKEN:\n  "
        + "\n  ".join(fixed))
