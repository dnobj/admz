"""Snapshot path — the most-complex tool path with both happy
states ("committed something") and the formerly-confusing one
("nothing to commit because config is unchanged").

These tests were the original reason this suite exists. Pre-fix,
the LLM was saying "I couldn't get the SHA" when the snapshot
succeeded as a no-op — fix #24 added an explicit `committed: bool`
field to the snapshot tool's response so the LLM has unambiguous
semantics.
"""

from __future__ import annotations

import re
import os
import pathlib
import time

import pytest


HOMELAB_REPO = pathlib.Path(os.path.expanduser("~/.admz/config-repo"))
P3748_DEVICE_ID = "B8A44FD0257C"  # canonical "device that exists in homelab"


@pytest.fixture
def force_diff():
    """Yields a function that creates a marker file in the homelab
    config-repo so the next snapshot has something real to commit.
    Cleans up afterwards.
    """
    created: list = []

    def _force(name: str = ".e2e-marker"):
        path = HOMELAB_REPO / f"{name}-{int(time.time())}"
        path.write_text(f"e2e marker {time.time()}\n")
        created.append(path)
        return path

    yield _force

    # Cleanup: delete + commit the deletions so we leave the tree clean.
    if not created:
        return
    import subprocess
    for p in created:
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
    # Commit the cleanup so subsequent runs don't see a dirty tree.
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=HOMELAB_REPO, capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m", "e2e: cleanup test markers"],
            cwd=HOMELAB_REPO, capture_output=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def test_snapshot_committed_path(chat, cost_recorder, force_diff):
    """Force a real diff in the working tree (via a marker file the
    snapshot won't overwrite) and verify the LLM reports the SHA.

    Catches: any regression that swallows the SHA, returns null on
    a real commit, or fails to communicate success to the user.
    """
    force_diff()  # creates an untracked file → has_changes() = True

    result = chat(
        f"Snapshot device {P3748_DEVICE_ID}. After the tool returns, "
        "tell me in one sentence: was a new commit made, and what is "
        "the SHA prefix (first 7 chars)?"
    )
    cost_recorder(result)
    assert result.success
    # Should mention the commit + a SHA-shaped substring.
    # Snapshot SHAs are 40-char hex; first-7 is at least 7 hex chars.
    has_sha = bool(re.search(r"\b[a-f0-9]{7,40}\b", result.lower))
    assert has_sha, (
        f"expected a SHA-shaped token in the response, got: {result!r}"
    )
    # Should NOT report failure.
    assert not result.contains_any(
        "could not", "couldn't", "unable", "failed", "no commit",
    ), f"response sounds like failure despite snapshot succeeding: {result!r}"


def test_snapshot_no_changes_path(chat, cost_recorder):
    """Run a second snapshot back-to-back without forcing a diff.
    Since the first one committed everything to the working tree
    + got auto-pushed, the second one should find nothing to commit
    and report it CLEARLY as 'no changes' (NOT as failure).

    Pre-fix #24, this was the bug that broke chat: the LLM saw
    git_sha:null and reported 'I was not able to retrieve the
    commit SHA' — sounding like failure.
    """
    # First snapshot consolidates any pending changes so the second
    # one has the no-changes baseline we want to test.
    chat(f"Snapshot device {P3748_DEVICE_ID}.")

    result = chat(
        f"Snapshot device {P3748_DEVICE_ID} again, right now. "
        "Tell me in one sentence whether anything was committed "
        "or whether the config was unchanged."
    )
    cost_recorder(result)
    assert result.success
    # The response should signal "no changes" clearly.
    assert result.contains_any(
        "unchanged", "no change", "nothing committed", "no commit",
        "nothing was committed", "no new commit", "already",
        "no diff", "no differences", "identical",
    ), (
        f"expected clear 'no changes' phrasing, got: {result!r}"
    )
    # Critically: this is NOT a failure. The response must not
    # frame it as one.
    assert not result.contains_any(
        "could not retrieve", "couldn't retrieve", "failed to retrieve",
        "was unable to", "snapshot failed",
    ), (
        f"response framed the no-op as failure (regression of fix #24): "
        f"{result!r}"
    )
