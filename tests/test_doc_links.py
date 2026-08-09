"""Relative links in Markdown docs must resolve to real files (GH #173).

While restructuring `DEPLOYMENT_WINDOWS.md` I hand-wrote four new ADR links and
**got all four filenames wrong** — plausible-looking slugs for real decisions.
Nothing in review caught them, and nothing would have. That is what this guards:
a link that reads correctly and 404s for the reader.

It runs in CI. `.github/workflows/ci.yml` executes the full suite on pull
requests; on pushes to `master` only `preflight` + `quick` run, so a broken link
merged without a PR is caught at collection time but not asserted on.

Deliberately narrow, and the exclusions are the interesting part:

* external `http(s)://` and `mailto:` links — checking them needs the network;
* pure `#anchor` links — a heading checker is a different tool with different
  false positives;
* code spans and fenced blocks — `[foo](bar)` in a shell example is not a link;
* ``docs/vapix-docs/`` — a vendored mirror of Axis's own documentation whose
  cross-references point into Axis's site structure. That is 163 of the 306
  Markdown files under `docs/`, leaving 143 checked. Not ours to fix, and an
  ignore list that size would swamp the signal.

**Known limits**, so nobody mistakes a pass for proof (found by review):

* inline links split across two lines are not seen — the scan is line-based;
* the fence tracker treats any ``` or ~~~ as a toggle, so a ~~~ line will close
  a ``` fence and fence-like text inside a fence flips state;
* four-space indented code blocks are not stripped, so a link-shaped string
  inside one is checked as if it were a link;
* destinations containing balanced parentheses, or labels containing nested
  brackets, are not parsed.

The dangerous direction is the first three — a checker that silently sees
nothing passes everything — which is why `test_the_checker_sees_the_deployment_guide_links`
pins that the file this guard was written for is actually being read.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOC_DIRS = ("docs",)

#: Vendored third-party documentation — see the module docstring.
EXCLUDE = ("docs/vapix-docs/",)

#: Escape hatch for a broken link that genuinely cannot be fixed yet, as
#: ``(doc, target)``. **Empty, and that is the point** — it held 32 entries when
#: the checker landed, and GH #376 burned all of them down: 49 repo-root-relative
#: paths in plan files (`admz/events/store.py` from `docs/specification/plans/`,
#: which needed `../../../`), plus four that had moved or never existed.
#:
#: Adding an entry is not how you fix a broken link. It is for a target that is
#: legitimately absent right now — a file a merged-but-unshipped plan will add.
#:
#: **Using it takes two deliberate edits**, by design: add the entry here, and
#: add the same pair to ``ALLOWED_WHILE_EMPTY`` below with a one-line reason.
#: ``test_the_baseline_only_shrinks`` then fails the moment the target starts
#: resolving, so an entry cannot outlive its reason.
KNOWN_BROKEN: set = set()

#: The one place an entry above is justified, with why. Two lists rather than
#: one so that adding an exemption cannot be a one-line edit lost in a diff.
ALLOWED_WHILE_EMPTY: dict = {}

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


#: ``[label]: target`` on its own line — the definition half of a
#: reference-style link. Without this the checker sees no links at all in a doc
#: written that way, and passes it (review finding on #378).
_REFDEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^>\s]+)>?")


def _links_in(path: Path):
    """Yield ``(lineno, target)`` for links outside fenced blocks and code spans."""
    in_fence = False
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if _FENCE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        refdef = _REFDEF.match(raw)
        if refdef:
            yield lineno, refdef.group(1)
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
          "KNOWN_BROKEN unless the target genuinely cannot exist yet -- and "
          "then justify it in ALLOWED_WHILE_EMPTY."
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


class TestTheCheckerItself:
    """The scanner needs its own tests: every weakness here makes docs pass
    silently, which is indistinguishable from having no guard."""

    def _scan(self, tmp_path, text):
        f = tmp_path / "d.md"
        f.write_text(text, encoding="utf-8")
        return [t for _, t in _links_in(f)]

    def test_inline_links_are_found(self, tmp_path):
        assert self._scan(tmp_path, "see [x](a/b.md) here") == ["a/b.md"]

    def test_reference_definitions_are_found(self, tmp_path):
        """Added after review: a doc written entirely in reference style used to
        yield zero links and therefore pass with every target broken."""
        assert self._scan(tmp_path, "see [x][k]\n\n[k]: a/b.md") == ["a/b.md"]

    def test_fenced_blocks_are_skipped(self, tmp_path):
        assert self._scan(tmp_path, "```\n[x](nope.md)\n```\n[y](yes.md)") == ["yes.md"]

    def test_code_spans_are_skipped(self, tmp_path):
        assert self._scan(tmp_path, "`[x](nope.md)` and [y](yes.md)") == ["yes.md"]

    def test_external_and_anchor_targets_are_not_checkable(self):
        for t in ("https://example.com", "http://x", "mailto:a@b", "#heading"):
            assert _is_checkable(t) is False
        assert _is_checkable("a/b.md") is True


def test_every_exemption_is_justified():
    """GH #376 emptied `KNOWN_BROKEN`. It stays usable — but an entry must also
    be justified in `ALLOWED_WHILE_EMPTY`, so an exemption cannot be a one-line
    edit that reads like a fix."""
    unjustified = sorted(set(KNOWN_BROKEN) - set(ALLOWED_WHILE_EMPTY))
    assert not unjustified, (
        "KNOWN_BROKEN is for a target that legitimately does not exist yet, not "
        "a place to put a link you could fix. Add a reason to "
        "ALLOWED_WHILE_EMPTY, or fix the link:\n  "
        + "\n  ".join(f"{d} -> {t}" for d, t in unjustified))
