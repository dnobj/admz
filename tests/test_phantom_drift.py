"""Phantom drift — #215 (the device wall clock) and #228 (reordered
action-rule condition clauses).

Both issues are the same user-visible defect: ADMZ reports a change that is not
a change, and the only offered action (*accept baseline*) cannot settle it
because the next read re-drifts.

Every "stop reporting X" assertion here is PAIRED with a negative that proves
the suppression is narrow — a genuine clock *config* change still drifts, and a
genuinely different condition still drifts. A false negative here hides real
change, which is far worse than the noise being removed.
"""

import subprocess

import pytest

from admz.snapshot.drift import DriftDetector
from admz.snapshot.facets.action_rules import (
    ActionRulesFacet,
    normalize_condition_expression,
)
from admz.snapshot.git_repo import GitRepo
from tests.test_drift import FakeRegistry, FakeSnapshotEngine


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_repo(tmp_path):
    repo_path = str(tmp_path / "config-repo")
    repo = GitRepo(repo_path)
    for key, val in [
        ("user.email", "test@test.com"),
        ("user.name", "Test"),
        ("commit.gpgsign", "false"),
    ]:
        subprocess.run(["git", "config", key, val], cwd=repo_path, check=True)
    return repo


@pytest.fixture
def ignore_store(monkeypatch):
    """In-memory fleet_settings so ignore rules never touch a real DB."""
    store = {}

    class _FS:
        def get(self, key):
            return store.get(key)

        def set(self, key, value):
            store[key] = value

    import admz.fleet_settings as fs
    monkeypatch.setattr(fs, "fleet_settings", _FS(), raising=False)
    return store


# The two clauses observed on the C1110-E (B8A44FB0BDA1), verbatim. Note each
# carries a literal " and " INSIDE its predicate — a naive split shreds them.
A = 'boolean(//SimpleItem[@Name="CallState" and @Value="Ringing"])'
B = 'boolean(//SimpleItem[@Name="Source" and @Value="NetworkSpeaker"])'

# Sorted order is (A, B) — so a baseline stored as "B and A" is NOT already in
# normal form. That orientation is deliberate: it is what makes
# ``test_old_baseline_...`` fail if normalisation lives only in serialize().
assert sorted([A, B]) == [A, B]


def rule(msg, *, rid="1", enabled=True, name="Loud ringer"):
    """One action rule in the exact shape captured live (verified against
    C:\\ProgramData\\admz-staging\\config-repo\\fleet\\B8A44FB0BDA1)."""
    return {
        "id": rid,
        "name": name,
        "enabled": enabled,
        "activationConfig": {
            "condition": [
                {"messageContent": msg, "topicExpression": "tnsaxis:Call/State"}
            ],
            "startEvent": None,
            "timeout": None,
        },
        "actionConfig": {
            "template": "com.axis.action.unlimited.play.audioclip",
            "recipientId": None,
            "recipientParameters": [],
            "actionParameters": [
                {"name": "location", "value": "%2Fetc%2Faudioclips%2Falarm.mp3"}
            ],
        },
    }


class RuleEngine(FakeSnapshotEngine):
    """FakeSnapshotEngine that also serves the action_rules extra read op."""

    def __init__(self, registry, rules_payload, **kw):
        super().__init__(registry, **kw)
        self.rules_payload = rules_payload

    async def _read_extra_ops(self, device_id, device_info, facets, family):
        return {"action_rules": self.rules_payload}


def _registry():
    return FakeRegistry({
        "cam-01": {
            "host": "1.2.3.4", "api_family": "vapix",
            "firmware_version": "12.1.65", "baseline_sha": "HEAD",
        }
    })


async def _drift(tmp_repo, baseline_doc, live_rules):
    tmp_repo.write_facet("cam-01", "action_rules", baseline_doc)
    tmp_repo.commit_snapshot("cam-01")
    engine = RuleEngine(_registry(), live_rules)
    return await DriftDetector(engine, tmp_repo).check_drift("cam-01")


# ---------------------------------------------------------------------------
# #228 — the decisive test: an OLD baseline must clear with no re-capture
# ---------------------------------------------------------------------------

class TestOldBaselineClearsWithoutRecapture:
    """The whole design argument for #228.

    Normalising inside ``serialize()`` alone would leave every baseline already
    on disk drifting until an operator re-captures it — the same silent-no-op
    shape as an ignore rule that doesn't reach. The baseline below is stored in
    the PRE-FIX form and in the NON-sorted clause order, so it only compares
    equal if normalisation is applied to the git-stored side too.
    """

    @pytest.mark.asyncio
    async def test_reordered_clauses_report_no_drift_against_old_baseline(
        self, tmp_repo
    ):
        report = await _drift(
            tmp_repo,
            {"1": rule(f"{B} and {A}")},   # stored pre-fix, un-normalised order
            [rule(f"{A} and {B}")],        # live, other order — same rule
        )
        assert report.has_drift is False, [
            (f.path, f.expected, f.actual) for f in report.fields
        ]
        assert report.fields == []

    @pytest.mark.asyncio
    async def test_facet_was_actually_compared(self, tmp_repo):
        """Guard for the test above: prove the facet is checked at all, so a
        "no drift" result can never come from the facet being skipped."""
        report = await _drift(
            tmp_repo,
            {"1": rule(f"{B} and {A}")},
            [rule(f"{A} and {B}")],
        )
        assert report.facets_checked >= 1


# ---------------------------------------------------------------------------
# #228 — negatives: everything not provably equivalent must STILL drift
# ---------------------------------------------------------------------------

class TestConditionNegativesStillDrift:

    @pytest.mark.asyncio
    async def test_different_clause_value_still_drifts(self, tmp_repo):
        """Bracket awareness: the change is INSIDE a predicate that itself
        contains " and ". A splitter that ignored bracket depth would mangle
        both sides into clause soup and could compare them equal."""
        changed = A.replace('"Ringing"', '"Idle"')
        report = await _drift(
            tmp_repo, {"1": rule(f"{A} and {B}")}, [rule(f"{changed} and {B}")]
        )
        assert report.has_drift is True

    @pytest.mark.asyncio
    async def test_values_swapped_across_clauses_still_drift(self, tmp_repo):
        """The failure a depth-aware splitter exists to prevent.

        These two rules are genuinely DIFFERENT — the values have been swapped
        between the two clauses. Split naively on " and " and both sides shatter
        into the SAME four fragments, so sorting them compares the rules equal
        and a real change disappears. Depth-aware splitting yields two whole
        clauses per side, which differ.
        """
        base = (f'boolean(//SimpleItem[@Name="CallState" and @Value="Ringing"])'
                f' and '
                f'boolean(//SimpleItem[@Name="Source" and @Value="NetworkSpeaker"])')
        live = (f'boolean(//SimpleItem[@Name="CallState" and @Value="NetworkSpeaker"])'
                f' and '
                f'boolean(//SimpleItem[@Name="Source" and @Value="Ringing"])')
        assert sorted(base.split(" and ")) == sorted(live.split(" and ")), (
            "fixture no longer exercises the naive-split collapse")
        report = await _drift(tmp_repo, {"1": rule(base)}, [rule(live)])
        assert report.has_drift is True

    @pytest.mark.asyncio
    async def test_removed_clause_still_drifts(self, tmp_repo):
        report = await _drift(tmp_repo, {"1": rule(f"{A} and {B}")}, [rule(A)])
        assert report.has_drift is True

    @pytest.mark.asyncio
    async def test_dropped_duplicate_clause_still_drifts(self, tmp_repo):
        """MULTISET, not set. Under set semantics ``A and A and B`` compares
        equal to ``A and B`` and a dropped duplicate becomes invisible — the
        false negative that #228's original "compare as sets" wording would
        have shipped."""
        report = await _drift(
            tmp_repo, {"1": rule(f"{A} and {A} and {B}")}, [rule(f"{A} and {B}")]
        )
        assert report.has_drift is True

    @pytest.mark.asyncio
    async def test_reordered_or_still_drifts(self, tmp_repo):
        """``or`` is deliberately NOT recognised. Reordering it may well be
        equivalent, but proving that needs an expression evaluator, and every
        bug in one is a false negative. Pin the boundary."""
        report = await _drift(
            tmp_repo, {"1": rule(f"{A} or {B}")}, [rule(f"{B} or {A}")]
        )
        assert report.has_drift is True

    @pytest.mark.asyncio
    async def test_reordered_condition_list_still_drifts(self, tmp_repo):
        """Scope boundary, enforced rather than merely commented: only clause
        order WITHIN one messageContent is normalised. Reordering the condition
        LIST is plausibly equivalent too, but that is a separate claim about
        the API's semantics and is not made here — so it still reports."""
        two = {
            "id": "1", "name": "r", "enabled": True,
            "activationConfig": {
                "condition": [
                    {"messageContent": A, "topicExpression": "tnsaxis:Call/State"},
                    {"messageContent": B, "topicExpression": "tnsaxis:Other"},
                ],
                "startEvent": None, "timeout": None,
            },
            "actionConfig": {"template": "t", "recipientId": None,
                             "recipientParameters": [], "actionParameters": []},
        }
        flipped = {**two, "activationConfig": {
            **two["activationConfig"],
            "condition": list(reversed(two["activationConfig"]["condition"])),
        }}
        report = await _drift(tmp_repo, {"1": two}, [flipped])
        assert report.has_drift is True

    @pytest.mark.asyncio
    async def test_non_condition_field_still_drifts_alongside_reorder(
        self, tmp_repo
    ):
        """Normalisation is scoped to the condition — it must not swallow the
        rest of the row."""
        report = await _drift(
            tmp_repo,
            {"1": rule(f"{B} and {A}", enabled=True)},
            [rule(f"{A} and {B}", enabled=False)],
        )
        assert report.has_drift is True
        paths = {f.path for f in report.fields}
        assert paths == {"1.enabled"}, paths


# ---------------------------------------------------------------------------
# #228 — the normaliser's recognised / unrecognised shapes, stated directly
# ---------------------------------------------------------------------------

class TestNormaliseConditionExpression:

    def test_sorts_top_level_and_clauses(self):
        assert (normalize_condition_expression(f"{B} and {A}")
                == normalize_condition_expression(f"{A} and {B}")
                == f"{A} and {B}")

    def test_predicate_internal_and_is_not_a_split_point(self):
        """Each clause here contains a literal " and " inside [...]. Asserting
        the EXACT output matters: a naive splitter shatters the clauses, fails
        the boolean(...) guard and bails to identity — which a containment or
        count assertion would happily accept."""
        assert normalize_condition_expression(f"{B} and {A}") == f"{A} and {B}"
        out = normalize_condition_expression(f"{A} and {B}")
        assert out.count("boolean(") == 2
        assert A in out and B in out

    def test_single_clause_is_returned_unchanged(self):
        assert normalize_condition_expression(A) == A

    def test_duplicates_are_preserved(self):
        out = normalize_condition_expression(f"{B} and {A} and {A}")
        assert out.count("boolean(") == 3
        assert out != normalize_condition_expression(f"{A} and {B}")

    @pytest.mark.parametrize("expr", [
        f"{A} or {B}",                       # or
        f"{A} and {B} or {A}",               # mixed precedence
        f"{A} and not({B})",                 # not()
        f"({A} and {B}) and {A}",            # top-level grouping
        f"{A} AND {B}",                      # mixed-case keyword
        f"{A} and {B} | {A}",                # union
        f"{A} and boolean(//SimpleItem[",    # unbalanced
        'boolean(//SimpleItem[@Name="a and b) and boolean(x)',  # unbalanced quote
    ])
    def test_unrecognised_shapes_fall_through_unchanged(self, expr):
        """Anything not confidently equivalent is returned verbatim, so it is
        byte-compared and still reports as drift."""
        assert normalize_condition_expression(expr) == expr

    def test_non_string_is_passed_through(self):
        assert normalize_condition_expression(None) is None
        assert normalize_condition_expression(7) == 7

    def test_normalisation_is_idempotent(self):
        once = normalize_condition_expression(f"{B} and {A}")
        assert normalize_condition_expression(once) == once

    def test_normalize_doc_tolerates_odd_shapes(self):
        """The hook runs on whatever git holds, including hand-edited YAML."""
        facet = ActionRulesFacet()
        for doc in ({}, {"1": None}, {"1": {"activationConfig": None}},
                    {"1": {"activationConfig": {"condition": "nope"}}},
                    {"1": {"activationConfig": {"condition": [None, {}]}}}):
            assert facet.normalize_doc(doc) is not None

    def test_serialize_also_normalises(self):
        """New baselines and the git config repo go quiet too — not just the
        comparison."""
        facet = ActionRulesFacet()
        doc = facet.serialize({"action_rules": [rule(f"{B} and {A}")]})
        msg = doc["1"]["activationConfig"]["condition"][0]["messageContent"]
        assert msg == f"{A} and {B}"


# ---------------------------------------------------------------------------
# #215 — the device wall clock
# ---------------------------------------------------------------------------

class TestWallClockIgnored:

    @pytest.mark.asyncio
    async def test_clock_does_not_drift_but_time_config_does(
        self, tmp_repo, ignore_store
    ):
        """One run, both halves: the wall clock is suppressed while a genuine
        timezone change on the SAME facet still reports."""
        import admz.snapshot.ignore as ig
        ig.seed_default_rules()

        tmp_repo.write_facet("cam-01", "time", {
            "ServerDate": "2011-02-12",
            "ServerTime": "12:54:06",
            "POSIXTimeZone": "<GMT+6>+6",
            "SyncSource": "NTP",
        })
        tmp_repo.commit_snapshot("cam-01")

        engine = FakeSnapshotEngine(_registry(), live_params={
            "root.Time.ServerDate": "2011-02-27",     # clock advanced
            "root.Time.ServerTime": "02:14:12",       # clock advanced
            "root.Time.POSIXTimeZone": "<GMT+0>+0",   # REAL config change
            "root.Time.SyncSource": "NTP",
        })
        report = await DriftDetector(engine, tmp_repo).check_drift("cam-01")

        paths = {f.path for f in report.fields}
        assert "ServerDate" not in paths
        assert "ServerTime" not in paths
        assert paths == {"POSIXTimeZone"}, paths
        assert report.has_drift is True

    @pytest.mark.asyncio
    async def test_sync_source_change_still_drifts(self, tmp_repo, ignore_store):
        import admz.snapshot.ignore as ig
        ig.seed_default_rules()
        tmp_repo.write_facet("cam-01", "time", {
            "ServerTime": "12:54:06", "SyncSource": "NTP",
        })
        tmp_repo.commit_snapshot("cam-01")
        engine = FakeSnapshotEngine(_registry(), live_params={
            "root.Time.ServerTime": "02:14:12",
            "root.Time.SyncSource": "Manual",
        })
        report = await DriftDetector(engine, tmp_repo).check_drift("cam-01")
        assert {f.path for f in report.fields} == {"SyncSource"}

    def test_prefix_escape_guard(self, ignore_store):
        """The rule is an exact-or-child match, never a raw startswith: a
        sibling key that merely SHARES the prefix must stay tracked."""
        import admz.snapshot.ignore as ig
        ig.seed_default_rules()
        assert ig.is_ignored("root.Time.ServerDate", "cam-01", [])
        assert ig.is_ignored("root.Time.ServerTime", "cam-01", [])
        assert not ig.is_ignored("root.Time.ServerDateFormat", "cam-01", [])
        assert not ig.is_ignored("root.Time.ServerTimeZone", "cam-01", [])
        # time CONFIG stays tracked
        assert not ig.is_ignored("root.Time.POSIXTimeZone", "cam-01", [])
        assert not ig.is_ignored("root.Time.DST.Enabled", "cam-01", [])
        assert not ig.is_ignored("root.Time.ObtainFromDHCP", "cam-01", [])
        assert not ig.is_ignored("root.Time.SyncSource", "cam-01", [])
        # the time_api facet has its own key namespace — unaffected either way
        assert not ig.is_ignored("time_api:iana_timezone", "cam-01", [])


class TestClockSeeding:
    """Seeding asserts IDENTITY, not counts — a count assertion passes for the
    wrong rule."""

    def test_appended_defaults_seed_onto_an_existing_install(self, ignore_store):
        import admz.snapshot.ignore as ig
        # An install that already seeded everything BEFORE the clock rules.
        ignore_store[ig.SEED_VERSION_KEY] = str(len(ig._SEED_DEFAULT_RULES) - 2)
        new = ig.seed_default_rules()
        assert [r["key"] for r in new] == [
            "root.Time.ServerDate", "root.Time.ServerTime"]
        assert all(r["scope"] == "global" for r in new)

    def test_clock_rules_are_appended_last(self):
        """Append-only: ``seed_default_rules`` uses list LENGTH as a high-water
        mark, so inserting mid-list would re-seed already-deleted rules."""
        import admz.snapshot.ignore as ig
        assert [r["key"] for r in ig._SEED_DEFAULT_RULES[-2:]] == [
            "root.Time.ServerDate", "root.Time.ServerTime"]
        assert ig._SEED_DEFAULT_RULES[-3]["key"] == "root.Time.NTP.Server"

    def test_seed_is_idempotent_and_deletion_safe_for_the_clock(
        self, ignore_store
    ):
        import admz.snapshot.ignore as ig
        assert ig.seed_default_rules()
        assert ig.seed_default_rules() == []
        ig.remove_rules([{"key": "root.Time.ServerTime", "scope": "global"}])
        assert ig.seed_default_rules() == []        # no resurrection
        assert not ig.is_ignored("root.Time.ServerTime", "cam-01", [])

    def test_marker_ahead_of_the_list_is_inert(self, ignore_store):
        """A downgrade leaves the marker past the list length; it must neither
        seed nor rewind the marker."""
        import admz.snapshot.ignore as ig
        ignore_store[ig.SEED_VERSION_KEY] = str(len(ig._SEED_DEFAULT_RULES) + 5)
        assert ig.seed_default_rules() == []
        assert ignore_store[ig.SEED_VERSION_KEY] == str(
            len(ig._SEED_DEFAULT_RULES) + 5)


# ---------------------------------------------------------------------------
# Sibling exposure — REPORTED, not fixed (see the follow-up issue)
# ---------------------------------------------------------------------------

class TestSiblingListFieldsAreStillOrderSensitive:
    """``recipientParameters`` / ``actionParameters`` are list-valued and hit
    the same ``flatten()`` stringification, so they ARE structurally exposed to
    the same reorder-as-drift. They are deliberately NOT normalised here: the
    transform is different (sort a name/value bag, not split a boolean
    expression) and no reorder has been observed. This test pins current
    behaviour so the follow-up (#242) is a deliberate change, not a surprise."""

    @pytest.mark.asyncio
    async def test_reordered_action_parameters_still_drift(self, tmp_repo):
        base = rule(A)
        base["actionConfig"]["actionParameters"] = [
            {"name": "a", "value": "1"}, {"name": "b", "value": "2"}]
        live = rule(A)
        live["actionConfig"]["actionParameters"] = [
            {"name": "b", "value": "2"}, {"name": "a", "value": "1"}]
        report = await _drift(tmp_repo, {"1": base}, [live])
        assert report.has_drift is True
