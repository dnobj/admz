"""Lock down resolver intent synonyms against the catalog task index.

Bug found in live testing: chat user asked "lets reboot the D4200"
and the LLM said it couldn't find a reboot/restart operation. The
underlying cause was a key mismatch — resolver._INTENT_SYNONYMS
mapped "reboot"/"restart" to ``reboot-device``, but the catalog
``by-task.yaml`` index uses ``restart-device``. The resolver
lookup quietly returned empty, the LLM concluded the operation
didn't exist, and confidently told the user.

These tests parse the synonyms table and the index, and assert
that every synonym target resolves to a real index key. Catches
this class of typo at CI time.
"""

import re
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESOLVER_PATH = PROJECT_ROOT / "admz" / "catalog" / "resolver.py"
BY_TASK_INDEX = (
    PROJECT_ROOT / "catalog" / "vapix" / "index" / "by-task.yaml"
)


def _extract_synonym_targets() -> set[str]:
    """Parse resolver.py and return every task key referenced in
    _INTENT_SYNONYMS values.

    We use a regex parse rather than importing the module because
    we want to fail loudly if the synonyms drift away from the
    index regardless of whether the module imports cleanly.
    """
    src = RESOLVER_PATH.read_text(encoding="utf-8")
    # Find the _INTENT_SYNONYMS dict literal.
    start_idx = src.find("_INTENT_SYNONYMS")
    if start_idx < 0:
        raise AssertionError("Couldn't find _INTENT_SYNONYMS in resolver.py")
    # Walk to the closing brace at the same depth.
    open_brace = src.find("{", start_idx)
    if open_brace < 0:
        raise AssertionError("Couldn't find opening brace of _INTENT_SYNONYMS")
    depth = 0
    close_brace = -1
    for i in range(open_brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                close_brace = i
                break
    if close_brace < 0:
        raise AssertionError("Couldn't find closing brace of _INTENT_SYNONYMS")
    body = src[open_brace + 1 : close_brace]
    targets: set[str] = set()
    # Inner lists look like:  ["change-resolution"]  or  ["a", "b"]
    for list_match in re.finditer(r"\[([^\[\]]+)\]", body):
        for value in re.findall(
            r"""['"]([^'"]+)['"]""",
            list_match.group(1),
        ):
            targets.add(value)
    return targets


def _load_index_keys() -> set[str]:
    """Load the by-task.yaml index and return the set of task keys."""
    with open(BY_TASK_INDEX) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise AssertionError("by-task.yaml didn't parse as a dict")
    return set(data.keys())


class TestSynonymTargetsResolveToIndexKeys:
    """Every value in resolver._INTENT_SYNONYMS must reference a
    real key in catalog/vapix/index/by-task.yaml. If not, the
    resolver returns empty for that intent and the chatbot
    silently misleads the user."""

    def test_all_synonym_targets_exist_in_index(self):
        targets = _extract_synonym_targets()
        index_keys = _load_index_keys()
        dead = targets - index_keys
        assert not dead, (
            f"Resolver synonyms point at non-existent task keys: "
            f"{sorted(dead)}. Either add the keys to "
            f"catalog/vapix/index/by-task.yaml or fix the synonym "
            f"to point at an existing key."
        )

    def test_reboot_and_restart_resolve_to_restart_device(self):
        """Regression — this is the specific bug found in live testing."""
        # Re-import resolver lazily so the test sees the live module
        # (handy when running this file standalone in dev).
        from admz.catalog.resolver import _INTENT_SYNONYMS
        assert "restart-device" in _INTENT_SYNONYMS["reboot"]
        assert "restart-device" in _INTENT_SYNONYMS["restart"]


class TestParseHelpers:
    def test_extract_synonym_targets_finds_known_entries(self):
        targets = _extract_synonym_targets()
        # Sanity: we should see at least these (stable for years).
        assert "change-resolution" in targets
        assert "restart-device" in targets
        assert "factory-reset" in targets

    def test_load_index_keys_finds_known_keys(self):
        keys = _load_index_keys()
        assert "restart-device" in keys
        assert "factory-reset" in keys
        assert "upgrade-firmware" in keys
