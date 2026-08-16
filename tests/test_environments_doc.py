"""Every claim in docs/ENVIRONMENTS.md must be one the checker can verify (#398).

The page exists because environment facts kept being *asserted* when they were
*observable*, and four such assertions went silently false. A page that can
absorb a new unverifiable claim would reintroduce exactly that.

So the contract is narrow and mechanical: the declaration parses, every
environment carries the keys the checker reads, and **no environment declares a
key the checker does not know how to observe**. Free-form prose lives outside
the fenced block, where it is obviously prose.

These tests do not observe anything themselves — no ports, no subprocesses, no
network. Running the suite must not depend on the state of the machine it runs
on, which is the opposite requirement from the checker's.
"""

from __future__ import annotations

import pytest

from tools.environments import load_declaration

#: Keys the checker reads for every environment. Adding a key here without
#: teaching the checker to observe it makes test_no_unobservable_keys fail.
REQUIRED = {
    "port", "admz_home", "checkout", "venv", "expect_listening", "touch",
    # The install shape the checker must compare against, rather than asking
    # the installation itself (#424). Without it here, an environment could be
    # added with no declared atlas and would silently skip the whole check.
    "atlas",
}

#: The only values the checker knows how to act on.
ATLAS_KINDS = {"copy", "editable", "none"}

#: Keys that are allowed but optional.
OPTIONAL = {"note"}


@pytest.fixture(scope="module")
def declared():
    return load_declaration()


def test_the_declaration_parses_and_is_not_empty(declared):
    assert declared, "no environments declared — the checker would check nothing"
    # A guard against the block being emptied or renamed while the page still
    # reads as though it declares something.
    assert len(declared) >= 3, f"expected at least production/staging/dev, got {list(declared)}"


def test_the_environments_that_matter_are_declared(declared):
    for name in ("production", "staging", "dev"):
        assert name in declared, f"{name} is not declared in docs/ENVIRONMENTS.md"


@pytest.mark.parametrize("key", sorted(REQUIRED))
def test_every_environment_declares_every_required_key(declared, key):
    missing = [name for name, spec in declared.items() if key not in spec]
    assert not missing, (
        f"{missing} do not declare {key!r}. The checker reads it for every "
        f"environment, and a missing key reads as 'not applicable' rather than "
        f"'nobody filled this in'."
    )


def test_every_declared_atlas_kind_is_one_the_checker_acts_on(declared):
    """A typo here would silently disable the check for that environment.

    ``atlas_problem`` returns None for an unrecognised value, so ``coppy`` or
    ``non-editable`` would read as "nothing to check" rather than as a mistake —
    the same self-disarming shape #424 was filed about.
    """
    wrong = {
        name: spec["atlas"] for name, spec in declared.items()
        if spec.get("atlas") not in ATLAS_KINDS
    }
    assert not wrong, f"unrecognised atlas kinds: {wrong} (expected one of {sorted(ATLAS_KINDS)})"


def test_production_declares_a_non_editable_atlas(declared):
    """ADR-0054's requirement, as a claim the checker enforces.

    Production's atlas must be a copy, never editable — an editable install
    re-creates the dev/prod coupling the split removed, and until #424 nothing
    would have noticed the reinstall.
    """
    assert declared["production"]["atlas"] == "copy"


def test_no_unobservable_keys(declared):
    """A claim the checker cannot verify must not be addable silently.

    This is the test that does the real work. The page's whole argument is that
    observable facts must be observed rather than asserted; a key nobody checks
    is an assertion wearing the page's authority.
    """
    known = REQUIRED | OPTIONAL
    for name, spec in declared.items():
        extra = set(spec) - known
        assert not extra, (
            f"{name} declares {sorted(extra)}, which tools/environments.py does "
            f"not observe. Either teach the checker to observe it and add it to "
            f"REQUIRED/OPTIONAL, or put it in the prose outside the fenced block."
        )


def test_production_is_marked_untouchable(declared):
    """The one claim whose absence would be dangerous rather than merely stale."""
    touch = str(declared["production"].get("touch", "")).lower()
    assert "never" in touch, (
        f"production's 'touch' reads {touch!r}. It manages real devices; this "
        f"line is what a reader checks before running anything."
    )


def test_only_production_is_expected_to_be_listening(declared):
    """Staging and dev must not claim a listener; #399 is what that confusion costs."""
    listening = {n for n, s in declared.items() if s.get("expect_listening")}
    assert listening == {"production"}, (
        f"environments expecting a listener: {sorted(listening)}. Only production "
        f"runs as a service; a second one claiming a port is how a config ends up "
        f"on production's data (#399)."
    )
