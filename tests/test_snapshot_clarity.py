"""Tests for the `_annotate_snapshot_summary` helper that disambiguates
'no changes' from 'committed' in the snapshot_device MCP tool response.

Before this fix, the tool returned ``git_sha: null`` when nothing had
changed since the previous snapshot. The LLM interpreted the null SHA
as a failure ('I was not able to retrieve the commit SHA') even
though the snapshot itself succeeded. The annotation adds an explicit
``committed: bool`` flag plus a human-readable ``message`` so the LLM
has unambiguous semantics.
"""

from __future__ import annotations

from admz.mcp.server import _annotate_snapshot_summary


class TestAnnotateSnapshotSummary:
    def test_committed_when_sha_present(self):
        summary = {
            "device_id": "cam-01",
            "status": "completed",
            "git_sha": "6bf521842fac6a11c7b83ef6cfb0b471bf1c0a0d",
            "facets_succeeded": 6,
            "facets_failed": 0,
        }
        out = _annotate_snapshot_summary(summary)
        assert out["committed"] is True
        assert "6bf521842fac" in out["message"]
        assert "committed" in out["message"].lower()
        assert "6 facet" in out["message"]
        # Original fields preserved.
        assert out["git_sha"] == summary["git_sha"]
        assert out["device_id"] == "cam-01"

    def test_no_changes_when_sha_null(self):
        summary = {
            "device_id": "cam-01",
            "status": "completed",
            "git_sha": None,
            "facets_succeeded": 6,
            "facets_failed": 0,
        }
        out = _annotate_snapshot_summary(summary)
        assert out["committed"] is False
        assert out["git_sha"] is None
        msg = out["message"].lower()
        # The message must NOT sound like failure — it's a successful
        # no-op. Specifically: don't use words like "fail", "error",
        # "couldn't" that the LLM might echo back as a failure.
        assert "fail" not in msg
        assert "error" not in msg
        assert "couldn't" not in msg
        # AND it must clearly say "no changes" / "unchanged" so the
        # LLM has the right concept to summarize for the user.
        assert "unchanged" in msg or "no change" in msg

    def test_empty_sha_treated_as_no_changes(self):
        """An empty-string SHA (rather than None) should also count
        as no-commit. Defensive — shouldn't happen in practice."""
        summary = {"git_sha": "", "facets_succeeded": 6}
        out = _annotate_snapshot_summary(summary)
        assert out["committed"] is False

    def test_preserves_failed_facets(self):
        summary = {
            "device_id": "cam-01",
            "git_sha": "abc123",
            "facets_succeeded": 4,
            "facets_failed": 2,
            "failed": [
                {"name": "events", "error": "401"},
                {"name": "users", "error": "403"},
            ],
        }
        out = _annotate_snapshot_summary(summary)
        assert out["committed"] is True
        assert out["facets_failed"] == 2
        assert out["failed"] == summary["failed"]

    def test_returns_new_dict_not_mutating(self):
        summary = {"git_sha": "abc", "facets_succeeded": 1}
        out = _annotate_snapshot_summary(summary)
        assert "committed" in out
        assert "committed" not in summary  # original untouched
