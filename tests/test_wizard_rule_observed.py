"""GH #198: ADR-0050's "is the rule still on the device?" check did not check that.

``_rules_status`` computed ``observed = rid in str(doc)`` — a substring test
against the repr of the WHOLE parsed ``action_rules`` facet. ``rule_id`` is a
small AXIS integer, and the haystack contains every rule name, ONVIF topic,
profile string and codec, so ``"2"`` matches ``Camera1Profile2``. The check
could essentially never report a deleted rule: it answered ``True`` in exactly
the case it existed to catch.

**The vacuity shape this file is built around.** A test asserting "the check
passes when the rule is present" proves nothing here — the old code passed that
test too. What distinguishes the fix is a rule removed *from the facet*, so
every positive case below is paired with the same fixture minus the rule.

**What `observed` does and does not mean.** The right-hand side is the
``action_rules`` facet from the git snapshot repo at ``latest_observed_sha``,
not a live device read — this module never probes, by design. So ``observed``
means "present as of the last audit". ``test_observed_is_snapshot_not_device``
pins that so nobody later reads it as a liveness check.
"""

from types import SimpleNamespace

import pytest

from admz.demos import wizard
from admz.demos.store import Demo, DemoStore


# --- fixtures --------------------------------------------------------------


def _ctx(facet, *, sha="abc"):
    """A ctx whose snapshot repo returns ``facet`` for any device."""
    reads = []

    def _read(did, name, ref):
        reads.append((did, name, ref))
        return facet

    return SimpleNamespace(
        registry=SimpleNamespace(get_device_info=lambda d: {"latest_observed_sha": sha}),
        git_repo=SimpleNamespace(read_facet=_read),
        _reads=reads,
    )


def _demo(store, rules):
    return store.create(Demo(id="", name="Lobby demo", rules=rules))


@pytest.fixture
def store(tmp_path):
    return DemoStore(str(tmp_path / "admz.db"))


#: The scenario from #198: rule 1 survives, rule 2 was deleted from the camera.
#: Every digit-bearing string here is real facet content — the profile name is
#: what made the old substring check answer "2 is present".
FACET_AFTER_DELETION = {
    "1": {
        "id": "1",
        "name": "Front door -> recording",
        "activationConfig": {
            "condition": [{"topicExpression":
                           "tns1:RuleEngine/MotionRegionDetector/Motion"}]},
        "actionConfig": {
            "template": "com.axis.action.fixed.record",
            "parameters": [{"name": "profile", "value": "Camera1Profile2"}]},
    },
}

FACET_BEFORE_DELETION = {
    **FACET_AFTER_DELETION,
    "2": {"id": "2", "name": "Lobby motion -> strobe",
          "actionConfig": {"template": "com.axis.action.fixed.led"}},
}


def _observed(ctx, store, rule_id="2", **extra):
    demo = _demo(store, [{"device_id": "cam-01", "rule_id": rule_id,
                          "source": "device", **extra}])
    rows = {r["rule_id"]: r for r in wizard._rules_status(ctx, demo)}
    return rows[rule_id]["observed"]


# --- the defect ------------------------------------------------------------


def test_deleted_rule_reads_false(store):
    """The one test that fails against the old line. This is the whole issue."""
    assert _observed(_ctx(FACET_AFTER_DELETION), store) is False


def test_present_rule_still_reads_true(store):
    """The pair. Same fixture WITH rule 2 — proves the test above is not
    trivially green because everything now reads False."""
    assert _observed(_ctx(FACET_BEFORE_DELETION), store) is True


def test_the_old_substring_check_would_have_passed_the_positive_case(store):
    """Pins WHY the positive case alone was worthless as a regression test.

    The deleted-rule facet contains the substring "2" (in Camera1Profile2), so
    the pre-fix implementation answered True for a rule that is gone. If this
    ever stops holding, the fixture has lost the property that makes
    ``test_deleted_rule_reads_false`` meaningful and it must be rebuilt.
    """
    assert "2" in str(FACET_AFTER_DELETION), (
        "fixture no longer reproduces the substring collision it exists to model")


def test_empty_facet_means_gone_not_unknown(store):
    """A readable facet with no rules is a real answer: the device has none."""
    assert _observed(_ctx({}), store) is False


# --- the "cannot tell" cases must not become false accusations -------------


@pytest.mark.parametrize("facet", [
    ["1", "2"],            # a list, not a rule map — build_graph calls this damaged
    "not a facet",
    42,
])
def test_unparsable_facet_is_unknown_not_missing(store, facet):
    """A damaged facet must read None.

    Reporting False would render a permanent, false "your rule vanished" — the
    exact failure this module's docstring argues against for ACS rules, in the
    other direction.
    """
    assert _observed(_ctx(facet), store) is None


def test_unparsable_entry_makes_the_whole_answer_unknown(store, monkeypatch):
    """One entry we cannot parse means we cannot claim the rule is absent."""
    import admz.demos.inference.graph as graph

    def _boom(*a, **k):
        raise ValueError("malformed entry")

    monkeypatch.setattr(graph, "normalize_device_rule", _boom)
    assert _observed(_ctx(FACET_AFTER_DELETION), store) is None


def test_no_snapshot_sha_is_unknown(store):
    ctx = SimpleNamespace(
        registry=SimpleNamespace(get_device_info=lambda d: {}),
        git_repo=SimpleNamespace(read_facet=lambda *a, **k: FACET_AFTER_DELETION))
    assert _observed(ctx, store) is None


def test_acs_rule_is_never_looked_for_on_a_device(store):
    """Pre-existing contract (#124 slice 3) — unchanged by this fix."""
    demo = _demo(store, [{"device_id": "cam-01", "rule_id": "7", "source": "acs"}])
    ctx = _ctx(FACET_AFTER_DELETION)
    rows = {r["rule_id"]: r for r in wizard._rules_status(ctx, demo)}
    assert rows["7"]["observed"] is None
    assert ctx._reads == [], "an ACS rule must not trigger a facet read at all"


# --- identity resolution ---------------------------------------------------


def test_cross_rule_collision_no_longer_matches(store):
    """``rule_id="8"`` must not match a facet whose only rule is ``18``.

    The old check said True for this; it carried no information in either
    direction.
    """
    assert _observed(_ctx({"18": {"id": "18", "name": "Other"}}), store,
                     rule_id="8") is False


def test_id_inside_a_value_no_longer_matches(store):
    assert _observed(_ctx({"1": {"id": "1", "name": "zone 8 west"}}), store,
                     rule_id="8") is False


def test_matches_on_name_when_the_facet_has_no_id(store):
    """``serialize`` keys by ``id or name or index``, so on an entry with no id
    the rule's NAME is the only identity present. Matching ids alone would
    report a live rule as vanished on that shape."""
    facet = {"Lobby motion -> strobe": {"name": "Lobby motion -> strobe"}}
    assert _observed(_ctx(facet), store, rule_id="2",
                     rule_name="Lobby motion -> strobe") is True
    # ...and the same shape without the rule is still False.
    assert _observed(_ctx({"Front door": {"name": "Front door"}}), store,
                     rule_id="2", rule_name="Lobby motion -> strobe") is False


def test_reuses_the_graph_normalizer(store, monkeypatch):
    """Structural guard: the facet must not gain a second parser.

    ``normalize_device_rule`` owns the id-resolution chain and the AXIS OS <12
    firmware asymmetry. A private reimplementation here is the drift that
    produced #255 and #274.
    """
    import admz.demos.inference.graph as graph
    calls = []
    real = graph.normalize_device_rule

    def _spy(did, key, raw):
        calls.append(key)
        return real(did, key, raw)

    monkeypatch.setattr(graph, "normalize_device_rule", _spy)
    _observed(_ctx(FACET_BEFORE_DELETION), store)
    assert sorted(calls) == ["1", "2"], (
        "_observed_rule_keys did not delegate to the shared normalizer")


def test_observed_is_snapshot_not_device(store):
    """``observed`` is 'present as of the last audit', never a live probe.

    Pinned so nobody later reads it as liveness. The facet is read at the
    device's ``latest_observed_sha`` and no device call occurs.
    """
    ctx = _ctx(FACET_BEFORE_DELETION, sha="deadbeef")
    _observed(ctx, store)
    assert ctx._reads == [("cam-01", "action_rules", "deadbeef")]


# --- the consequence path: next_actions --------------------------------------


def _status(ctx, store, rules):
    demo = _demo(store, rules)
    return wizard.setup_status(_full_ctx(ctx), demo)


def _full_ctx(ctx):
    """setup_status needs a little more of the context surface than
    _rules_status does; everything else degrades to empty."""
    ctx.event_store = None
    ctx.registry.get_devices = lambda *a, **k: []
    return ctx


def test_vanished_rule_reaches_next_actions(store):
    """Fixing the check alone was not enough.

    ``next_actions`` keys off ``rules`` being EMPTY, and never read ``observed``
    at all — so before this branch a demo whose rule had vanished still fell
    through to "Demo looks set up", while the rules table said otherwise.
    """
    st = _status(_ctx(FACET_AFTER_DELETION), store,
                 [{"device_id": "cam-01", "rule_id": "2", "source": "device",
                   "rule_name": "Lobby motion -> strobe"}])

    joined = " ".join(st["next_actions"])
    assert "Re-create" in joined, f"no vanished-rule action: {st['next_actions']}"
    assert "Lobby motion -> strobe" in joined
    assert "Demo looks set up" not in joined, (
        "the summary still claims the demo is fine")


def test_present_rule_produces_no_recreate_action(store):
    """The pair — otherwise the assertion above passes for any demo at all."""
    st = _status(_ctx(FACET_BEFORE_DELETION), store,
                 [{"device_id": "cam-01", "rule_id": "2", "source": "device",
                   "rule_name": "Lobby motion -> strobe"}])
    assert "Re-create" not in " ".join(st["next_actions"])


def test_unknown_observed_is_not_reported_as_missing(store):
    """``None`` means "cannot tell" and must not be rendered as a missing rule —
    the branch tests ``is False``, not falsiness."""
    st = _status(_ctx("damaged"), store,
                 [{"device_id": "cam-01", "rule_id": "2", "source": "device"}])
    assert "Re-create" not in " ".join(st["next_actions"])
