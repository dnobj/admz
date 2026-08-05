"""GH #213: documented inventories of code-derived facts must match the code.

Seven documents publish hand-copied enumerations of something whose real source
is the repo. Measured on this branch before writing anything, 48 PRs after the
issue was filed:

    ADRs:        58 on disk, 41 linked from a file whose first line says
                 "Complete table of contents"  -> 17 unreachable
    Plans:       11 on disk, 6 linked                    -> 5 unreachable
    MCP tools:   TOOL_HANDLERS = 75; 21 doc claims disagreed
    README:      "~1,600 tests" against ~3,150 static test functions
    ARCHITECTURE storage table: 7 of 31 tables named

A hand-copied inventory is not merely stale, it is *confidently* stale, and a
reader cannot tell.

WHAT IS GUARDED HERE, AND WHAT DELIBERATELY IS NOT
--------------------------------------------------
A guard on everything gets disabled, so only inventories where being wrong
*misleads someone into acting* are enforced:

  * **Every ADR is reachable from INDEX.** CLAUDE.md requires reading the
    relevant ADR before changing a subsystem. 17 unreachable ADRs included
    ADR-0034 (the confirmation gate) and ADR-0039 (module footprint) — two of
    the load-bearing invariants CLAUDE.md itself names. Highest value here.
  * **Every plan is reachable from INDEX.** The orchestration playbook's
    "check for an existing plan" step silently fails otherwise, and the cost
    is duplicated design work.
  * **FR-SEC-012's allow-set matches `LLM_WRITABLE_SETTING_KEYS`.** A security
    boundary, two items, almost never changes. If a third key is ever added,
    the requirement must not keep claiming there are two.
  * **`MCP_TOOLS_REFERENCE.md` names exactly the registered tools.** It is the
    document people actually use, and it was the *only* one already correct.

NOT guarded, on purpose:

  * **The test count.** It changes with almost every PR; a guard would fail
    constantly and be deleted. Fixed by hand to stop asserting a number.
  * **The ARCHITECTURE storage table.** Churns with every new store, and being
    incomplete misleads nobody into a wrong action.
  * **Tool counts in `decisions/`, `plans/`, `review-*`, `MIGRATION.md` and
    the `*_DESIGN`/`*_RESEARCH` documents.** These are *point-in-time records*.
    ADR-0025 saying "44 tools" is CORRECT as history — forcing it to 75 would
    falsify the record. This is the distinction the issue misses, and it is why
    the sweep left those numbers alone.

THE TRAP
--------
An inventory test that asserts "the doc mentions each item" passes when the doc
says the *opposite* about that item, and passes when the doc lists items that no
longer exist. Every assertion below is a **set equality, checked in both
directions**, or a resolvable-link check — never a substring "is it mentioned".
"""

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
SPEC = REPO / "docs" / "specification"
INDEX = SPEC / "INDEX.md"


def _index_text() -> str:
    return INDEX.read_text(encoding="utf-8")


# --- ADRs ------------------------------------------------------------------


def test_every_adr_is_linked_from_the_index():
    """INDEX.md line 1 says "Complete table of contents". Make that true."""
    on_disk = {p.name for p in (SPEC / "decisions").glob("[0-9][0-9][0-9][0-9]-*.md")}
    linked = set(re.findall(r"decisions/([0-9]{4}-[a-z0-9-]+\.md)", _index_text()))

    assert on_disk, "found no ADRs at all — the glob is wrong, not the docs"
    missing = on_disk - linked
    assert not missing, (
        f"{len(missing)} ADR(s) exist but are unreachable from INDEX.md: "
        f"{sorted(missing)}. CLAUDE.md requires reading the relevant ADR before "
        "changing a subsystem; an unlinked ADR will not be found.")


def test_the_index_has_no_dead_adr_links():
    """The other direction: a link to an ADR that no longer exists.

    Without this, the test above would pass for an INDEX that linked every real
    ADR *and* a dozen imaginary ones.
    """
    on_disk = {p.name for p in (SPEC / "decisions").glob("*.md")}
    linked = set(re.findall(r"decisions/([0-9]{4}-[a-z0-9-]+\.md)", _index_text()))
    dead = linked - on_disk
    assert not dead, f"INDEX.md links ADRs that do not exist: {sorted(dead)}"


# --- plans -----------------------------------------------------------------


def test_every_plan_is_linked_from_the_index():
    on_disk = {p.name for p in REPO.glob("docs/**/plans/*.md")}
    linked = {m.split("/")[-1]
              for m in re.findall(r"\]\(([^)]*plans/[a-z0-9-]+\.md)\)", _index_text())}

    assert on_disk, "found no plans at all — the glob is wrong"
    missing = on_disk - linked
    assert not missing, (
        f"{len(missing)} plan(s) exist but are unreachable from INDEX.md: "
        f"{sorted(missing)}. The orchestration playbook's 'check for an existing "
        "plan' step reads INDEX; an unlinked plan gets re-designed from scratch.")


def test_the_index_has_no_dead_plan_links():
    on_disk = {p.name for p in REPO.glob("docs/**/plans/*.md")}
    linked = {m.split("/")[-1]
              for m in re.findall(r"\]\(([^)]*plans/[a-z0-9-]+\.md)\)", _index_text())}
    dead = linked - on_disk
    assert not dead, f"INDEX.md links plans that do not exist: {sorted(dead)}"


# --- the dangerous one: a documented security boundary ---------------------


def test_fr_sec_012_lists_exactly_the_llm_writable_keys():
    """The requirement enumerates the allow-set. Assert the FACT, both ways.

    This is the inventory where being wrong is dangerous rather than untidy: a
    contributor reads FR-SEC-012 to decide whether a new setting needs a guard,
    which is how #212's protected-key gaps kept being introduced.

    Both directions matter. "Every code key appears in the doc" passes for a doc
    that also lists five keys the code refuses; "every doc key is in the code"
    passes for a doc that lists one of three.
    """
    from admz.setting_policy import LLM_WRITABLE_SETTING_KEYS

    text = (SPEC / "requirements" / "security.md").read_text(encoding="utf-8")
    start = text.index("### FR-SEC-012")
    body = text[start:text.index("\n### ", start + 1)]

    # The enumerated bullet list under "The allow-set is ...".
    listed = set(re.findall(r"^\s*-\s+`([a-z_]+)`", body, re.M))

    assert listed == set(LLM_WRITABLE_SETTING_KEYS), (
        "FR-SEC-012's enumerated allow-set disagrees with the code.\n"
        f"  documented: {sorted(listed)}\n"
        f"  code:       {sorted(LLM_WRITABLE_SETTING_KEYS)}\n"
        "This is a security boundary; update the requirement in the same PR as "
        "the code, or stop enumerating and point at the symbol.")


# --- the MCP tool surface --------------------------------------------------


TOOLS_REFERENCE = REPO / "docs" / "MCP_TOOLS_REFERENCE.md"


def _documented_tool_names() -> set:
    text = TOOLS_REFERENCE.read_text(encoding="utf-8")
    return set(re.findall(r"`([a-z][a-z0-9_]{3,})`", text)) | set(
        re.findall(r"^#+\s*`?([a-z][a-z0-9_]{3,})`?", text, re.M))


def test_the_tools_reference_documents_every_registered_tool():
    from admz.mcp.dispatch import TOOL_HANDLERS

    missing = set(TOOL_HANDLERS) - _documented_tool_names()
    assert not missing, (
        f"{len(missing)} MCP tool(s) are registered but absent from "
        f"MCP_TOOLS_REFERENCE.md: {sorted(missing)}")


def test_the_tools_reference_states_the_real_count():
    """It opens with a number. Numbers in prose are how this issue happened, so
    the one document that keeps a count has it checked."""
    from admz.mcp.dispatch import TOOL_HANDLERS

    text = TOOLS_REFERENCE.read_text(encoding="utf-8")
    claims = [int(n) for n in re.findall(r"\*\*(\d+) tools\*\*", text)]
    assert claims, "MCP_TOOLS_REFERENCE.md no longer states a tool count"
    for c in claims:
        assert c == len(TOOL_HANDLERS), (
            f"MCP_TOOLS_REFERENCE.md claims {c} tools; TOOL_HANDLERS has "
            f"{len(TOOL_HANDLERS)}")


def test_current_state_docs_do_not_publish_a_stale_tool_count():
    """No *current-state* document may hard-code a tool count.

    Deliberately a rule, not a file list: everything is checked except the
    historical patterns below, so a new current-state doc is covered the moment
    it is written. That is the failure direction ADR-0053 argued for.

    The exclusions are point-in-time records where the old number is CORRECT.
    An ADR is a historical document by definition; a review is dated; a
    migration guide describes a past state; a `*_DESIGN`/`*_RESEARCH` doc
    records a proposal. Rewriting their numbers would falsify them.
    """
    from admz.mcp.dispatch import TOOL_HANDLERS

    real = len(TOOL_HANDLERS)
    historical = re.compile(
        r"(?:^|/)(?:decisions|plans|vapix-docs)/"
        r"|(?:^|/)review[-a-z0-9]*\.md$"
        r"|(?:^|/)MIGRATION\.md$"
        r"|_(?:DESIGN|RESEARCH)\.md$")

    offenders = []
    for p in sorted(REPO.glob("docs/**/*.md")) + [REPO / "README.md"]:
        rel = p.relative_to(REPO).as_posix()
        if historical.search(rel):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace")
                                 .splitlines(), 1):
            for m in re.finditer(r"\b(\d{2,3})\s+(?:MCP\s+)?tools\b", line, re.I):
                if int(m.group(1)) != real:
                    offenders.append(f"{rel}:{i} says {m.group(1)}, real is {real}")

    assert not offenders, (
        "current-state document(s) publish a stale MCP tool count:\n  "
        + "\n  ".join(offenders)
        + "\nEither correct the number or — usually better — stop stating it and "
          "point at docs/MCP_TOOLS_REFERENCE.md.")


# --- anti-vacuity ----------------------------------------------------------
#
# Every assertion above is "the doc agrees with the code". Each is trivially
# satisfiable by an empty extraction: no ADRs found, no keys parsed, no tool
# names matched. These pin the extractors themselves, so a regex that silently
# stops matching fails here instead of turning four guards into no-ops.


def test_extractors_are_not_silently_empty():
    from admz.mcp.dispatch import TOOL_HANDLERS
    from admz.setting_policy import LLM_WRITABLE_SETTING_KEYS

    assert len(list((SPEC / "decisions").glob("[0-9][0-9][0-9][0-9]-*.md"))) > 40
    assert len(list(REPO.glob("docs/**/plans/*.md"))) > 5
    assert len(TOOL_HANDLERS) > 50
    assert len(LLM_WRITABLE_SETTING_KEYS) == 2
    assert len(_documented_tool_names()) > 50, (
        "the tools-reference extractor matched almost nothing — its guards are "
        "passing vacuously")

    text = (SPEC / "requirements" / "security.md").read_text(encoding="utf-8")
    body = text[text.index("### FR-SEC-012"):]
    assert re.findall(r"^\s*-\s+`([a-z_]+)`", body, re.M), (
        "FR-SEC-012's bullet extractor matched nothing — that guard is vacuous")


@pytest.mark.parametrize("doc", [
    "docs/specification/INDEX.md",
    "docs/MCP_TOOLS_REFERENCE.md",
    "docs/specification/requirements/security.md",
])
def test_guarded_documents_exist(doc):
    """A renamed or deleted document must fail loudly, not skip the guard."""
    assert (REPO / doc).is_file(), f"{doc} is missing; its guard is now vacuous"
