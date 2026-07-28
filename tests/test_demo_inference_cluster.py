"""Clustering the evidence graph into proposals (#124, slice 3) — pure functions.

Everything here is table-driven over hand-built graphs: no ACS, no device, no
network, no DB. That is the point of :mod:`admz.demos.inference.cluster` —
scoring and membership are the parts a human has to be able to argue with, so
they must be inspectable without a fleet.
"""

from __future__ import annotations

import pytest

from admz.demos.inference import cluster as cl


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures — the smallest graphs that make each behaviour visible
# ═══════════════════════════════════════════════════════════════════════════

def node(device_id, name=None, model="P1234", tags=(), mac=None):
    return {"device_id": device_id, "name": name or device_id, "model": model,
            "tags": list(tags), "mac": mac or device_id.upper(),
            "host": "", "acaps_known": True, "acaps": []}


def edge(edge_id, a, b, weight=None, detail="because", source="src"):
    weights = {"E1": 1.0, "E2": 0.9, "E3": 0.8, "E4": 0.5, "E6": 0.45, "E5": 0.4}
    lo, hi = sorted((a, b))
    return {"id": edge_id, "a": lo, "b": hi,
            "weight": weights[edge_id] if weight is None else weight,
            "class": {"E1": "topology", "E2": "topology", "E3": "topology",
                      "E4": "grouping", "E5": "naming", "E6": "capability"}[edge_id],
            "corroborating": edge_id not in ("E1", "E2", "E3"),
            "evidence": [{"detail": detail, "source": source}]}


def acs_rule(rule_id, name, triggers=(), actions=(), topics=(), kinds=(),
             enabled=True, observability=None):
    return {"source": "acs", "rule_key": f"acs:{rule_id}", "rule_id": str(rule_id),
            "name": name, "enabled": enabled, "owner_device_id": None,
            "trigger_device_ids": list(triggers), "action_device_ids": list(actions),
            "device_ids": sorted(set(triggers) | set(actions)),
            "topics": list(topics), "action_kinds": list(kinds),
            "names_only": False, "observability": observability,
            "app_grounding": [], "join_methods": {}}


def device_rule(device_id, rule_id, name, topics=(), kinds=(), names_only=False,
                enabled=True):
    return {"source": "device", "rule_key": f"device:{device_id}:{rule_id}",
            "rule_id": str(rule_id), "name": name, "enabled": enabled,
            "owner_device_id": device_id, "trigger_device_ids": [device_id],
            "action_device_ids": [], "device_ids": [device_id],
            "topics": list(topics), "action_kinds": list(kinds),
            "names_only": names_only, "observability": None,
            "app_grounding": [], "join_methods": {}}


def graph(nodes, edges=(), rules=(), acs_available=True, acs_reason="ok"):
    return {"generated_at": None, "params": {},
            "acs": {"available": acs_available, "reason": acs_reason},
            "nodes": list(nodes), "edges": list(edges), "rules": list(rules),
            "unresolved": [], "unattached_rules": [],
            "devices_without_rule_facet": [], "summary": {}}


# ═══════════════════════════════════════════════════════════════════════════
# Seeding + the split guard
# ═══════════════════════════════════════════════════════════════════════════

class TestSeedAndSplit:
    def test_every_node_lands_in_exactly_one_component(self):
        nodes = [node("a"), node("b"), node("c")]
        comps = cl.seed_clusters(nodes, [edge("E1", "a", "b")])
        assert comps == [["c"], ["a", "b"]]

    @pytest.mark.parametrize("members,pairs,expected", [
        (["a"], {}, 1.0),                                     # nothing to connect
        (["a", "b"], {("a", "b"): 1.0}, 1.0),
        (["a", "b", "c"], {("a", "b"): 1.0}, pytest.approx(1 / 3)),
        (["a", "b", "c"], {("a", "b"): 1.0, ("a", "c"): 1.0,
                           ("b", "c"): 1.0}, 1.0),
    ])
    def test_density_counts_pairs_not_edge_rows(self, members, pairs, expected):
        assert cl.density(members, pairs) == expected

    def test_a_healthy_component_is_never_cut(self):
        pairs = {("a", "b"): 1.0, ("a", "c"): 1.0, ("b", "c"): 1.0}
        parts, cuts = cl.split_component(["a", "b", "c"], pairs)
        assert parts == [["a", "b", "c"]] and cuts == []

    def test_hub_blob_is_split_into_parts_within_the_size_guard(self):
        """One camera wired into 40 rules must not become one 'demo'."""
        hub = "hub"
        pairs = {}
        for i in range(20):
            pairs[tuple(sorted((hub, f"d{i:02d}")))] = 0.45
        members = [hub] + [f"d{i:02d}" for i in range(20)]
        parts, cuts = cl.split_component(members, pairs)
        assert cuts, "a 21-device star must be cut"
        assert all(len(p) <= cl.MAX_CLUSTER_DEVICES for p in parts)
        assert sorted(d for p in parts for d in p) == sorted(set(members))

    def test_split_is_deterministic(self):
        pairs = {("a", "b"): 0.9, ("b", "c"): 0.4, ("c", "d"): 0.9,
                 ("a", "c"): 0.5, ("b", "d"): 0.5}
        first = cl.split_component(["a", "b", "c", "d", "e"],
                                   {**pairs, ("d", "e"): 0.4})
        second = cl.split_component(["a", "b", "c", "d", "e"],
                                    {**pairs, ("d", "e"): 0.4})
        assert first == second

    def test_the_weakest_link_is_cut_first(self):
        # A long thin chain (7 devices, 6 links → density 0.29) forces a cut,
        # and it must fall on the 0.40 link rather than anywhere convenient.
        pairs = {("a", "b"): 0.9, ("b", "c"): 0.4, ("c", "d"): 0.9,
                 ("d", "e"): 0.9, ("e", "f"): 0.9, ("f", "g"): 0.9}
        _, cuts = cl.split_component(list("abcdefg"), pairs)
        assert cuts and cuts[0]["weight"] == 0.4
        assert (cuts[0]["a"], cuts[0]["b"]) == ("b", "c")

    def test_a_corroborating_only_group_must_clear_the_stricter_floor(self):
        """Shared-attribute evidence does not chain: "A and B both run X" and
        "B and C both run Y" says nothing about A and C. Live on the reference
        fleet that accident merged 6 of 11 devices into one 'demo'."""
        # 4 devices, 3 links → density 0.50: fine with topology, not without.
        pairs = {("a", "b"): 0.45, ("b", "c"): 0.45, ("c", "d"): 0.45}
        assert cl.density(list("abcd"), pairs) == 0.5
        assert cl.density_floor(list("abcd"), frozenset()) == (
            cl.DENSITY_MIN_CORROBORATING)
        kept, no_cuts = cl.split_component(list("abcd"), pairs,
                                           frozenset({("a", "b")}))
        assert kept == [["a", "b", "c", "d"]] and no_cuts == []
        parts, cuts = cl.split_component(list("abcd"), pairs, frozenset())
        assert cuts and len(parts) > 1
        assert all(cl.density(p, pairs) >= cl.DENSITY_MIN_CORROBORATING
                   for p in parts)
        assert "chain of coincidences" in cuts[0]["detail"]

    def test_a_bridge_device_rejoins_a_part_it_is_embedded_in(self):
        parts = [["a", "b"], ["c", "d"]]
        cuts = [{"a": "b", "b": "c", "weight": 0.4, "detail": "cut"}]
        # b links to BOTH c and d, so it is genuinely in the second group too.
        pairs = {("a", "b"): 0.9, ("b", "c"): 0.4, ("b", "d"): 0.4,
                 ("c", "d"): 0.9}
        grown = cl.reattach_bridges(parts, cuts, pairs)
        assert ["b", "c", "d"] in grown and ["a", "b"] in grown

    def test_a_single_weak_link_does_not_earn_a_place_in_the_other_part(self):
        """One link is exactly the coincidence the split just rejected — putting
        the device back on the strength of it would undo the split."""
        parts = [["a", "b"], ["c", "d"]]
        cuts = [{"a": "b", "b": "c", "weight": 0.4, "detail": "cut"}]
        pairs = {("a", "b"): 0.9, ("b", "c"): 0.4, ("c", "d"): 0.9}
        assert cl.reattach_bridges(parts, cuts, pairs) == [["a", "b"], ["c", "d"]]


# ═══════════════════════════════════════════════════════════════════════════
# Scoring
# ═══════════════════════════════════════════════════════════════════════════

class TestScore:
    def test_every_term_is_published_with_its_contribution(self):
        nodes = [node("cam", "Lobby loitering cam", tags=["lobby"]),
                 node("spk", "Lobby speaker", tags=["lobby"])]
        by_id = {n["device_id"]: n for n in nodes}
        rules = [acs_rule(1, "Lobby loitering announce", triggers=["cam"],
                          actions=["spk"], topics=["…/loiteringguard/Event"])]
        out = cl.score_cluster(["cam", "spk"], [edge("E1", "cam", "spk")],
                               rules, by_id)
        names = [t["name"] for t in out["terms"]]
        assert names == ["topology_cohesion", "rule_density", "name_cohesion",
                         "tag_cohesion", "firing_recency"]
        assert out["score"] == pytest.approx(sum(t["contribution"]
                                                 for t in out["terms"]))
        # 1 topology pair over 1 needed; 1 named rule over 2 devices; both share
        # 'lobby' as a token AND as a tag; no firing history.
        assert dict(zip(names, [t["value"] for t in out["terms"]])) == {
            "topology_cohesion": 1.0, "rule_density": 0.5,
            "name_cohesion": 1.0, "tag_cohesion": 1.0, "firing_recency": 0.0}

    @pytest.mark.parametrize("score,expected", [
        (0.9, "high"), (0.7, "high"), (0.69, "medium"), (0.45, "medium"),
        (0.44, "low"), (0.0, "low"),
    ])
    def test_confidence_bands(self, score, expected):
        assert cl.confidence_for(score) == expected

    @pytest.mark.parametrize("age_days,term", [(1, 1.0), (6.9, 1.0), (8, 0.5),
                                               (29, 0.5), (31, 0.0)])
    def test_firing_recency_bands(self, age_days, term):
        now = 1_000_000.0
        got, last, _ = cl.firing_recency(
            ["r"], {"r": now - age_days * 86400}, now)
        assert got == term and last is not None

    def test_firing_recency_degrades_to_zero_when_history_is_unavailable(self):
        """Best-effort by design: 'not looked' must be distinguishable from
        'not seen', and must never fail the run."""
        term, last, detail = cl.firing_recency(["r"], None, None)
        assert (term, last) == (0.0, None) and "not looked" in detail
        term, last, detail = cl.firing_recency(["r"], {"other": 1.0}, 2.0)
        assert (term, last) == (0.0, None) and "not looked" in detail


# ═══════════════════════════════════════════════════════════════════════════
# Roles + naming
# ═══════════════════════════════════════════════════════════════════════════

class TestRolesAndNaming:
    def test_trigger_side_is_the_detector_even_when_it_also_records(self):
        """The reference fleet's norm: every ACS rule triggers and acts on the
        same device. Calling that device a 'recorder' would lose the point."""
        rules = [acs_rule(1, "Alert on SFH", triggers=["cam"], actions=["cam"],
                          kinds=["Record", "Alarm"])]
        assert cl.assign_roles(["cam"], rules) == {"cam": "detector"}

    def test_record_target_is_the_recorder_responder_otherwise(self):
        rules = [acs_rule(1, "r", triggers=["cam"], actions=["nvr"],
                          kinds=["Record"]),
                 acs_rule(2, "r2", triggers=["cam"], actions=["spk"],
                          kinds=["DoorStation"])]
        assert cl.assign_roles(["cam", "nvr", "spk", "idle"], rules) == {
            "cam": "detector", "nvr": "recorder", "spk": "responder",
            "idle": "member"}

    @pytest.mark.parametrize("token,topics,kinds,expected", [
        ("loitering", ["…/loiteringguard/Event"], [], "Loitering detection"),
        ("alert", ["…/sfh_detector/SfHCandidate"], ["Record"], "Alert detection"),
        ("reception", [], ["Record"], "Reception recording"),
        ("reception", [], [], "Reception demo"),
    ])
    def test_deterministic_name_pairs_the_top_token_with_a_role_hint(
            self, token, topics, kinds, expected):
        rules = [acs_rule(1, "r", topics=topics, kinds=kinds)]
        assert cl.deterministic_name(["a"], {"a": node("a")}, rules,
                                     token, None) == expected

    def test_name_falls_back_to_the_model_when_nothing_is_shared(self):
        by_id = {"a": node("a", model="C1710"), "b": node("b", model="C1710")}
        assert cl.deterministic_name(["a", "b"], by_id, [], None, None) == (
            "C1710 demo (2 devices)")

    def test_repeat_names_are_disambiguated(self):
        assert cl.uniquify(["X", "Y", "X", "X"]) == ["X", "Y", "X (2)", "X (3)"]


# ═══════════════════════════════════════════════════════════════════════════
# Suggested owned keys — READ-ONLY evidence (resolved DECISION b)
# ═══════════════════════════════════════════════════════════════════════════

class TestSuggestedOwnedKeys:
    def test_trigger_topic_names_the_publishing_app(self):
        rule = acs_rule(1, "Alert on SFH", triggers=["cam"],
                        topics=["tnsaxis:CameraApplicationPlatform/sfh_detector/X"])
        keys = cl.suggested_owned_keys(["cam"], [rule], {"cam": node("cam")})
        entry = next(k for k in keys if k["facet"] == "applications")
        assert entry["path"] == "sfh_detector"
        assert "produced by sfh_detector" in entry["reason"]

    def test_a_read_only_facet_is_listed_but_flagged_not_capturable(self):
        """Honest rather than tidy: a key capture would refuse still tells the
        operator what the demo depends on."""
        rule = device_rule("cam", "7", "PIR play")
        keys = cl.suggested_owned_keys(["cam"], [rule], {"cam": node("cam")})
        entry = next(k for k in keys if k["facet"] == "action_rules")
        assert entry["not_capturable"] is True
        assert "not param-writable" in entry["not_capturable_reason"]
        assert entry["path"] == "7"

    def test_analytics_trigger_suggests_the_detector_config(self):
        rule = acs_rule(1, "motion", triggers=["cam"],
                        topics=["tns1:RuleEngine/VMD3/vmd3_video_1"])
        rule["app_grounding"] = [{"topic": "tns1:RuleEngine/VMD3/vmd3_video_1",
                                  "app": "vmd", "device_id": "cam"}]
        keys = cl.suggested_owned_keys(["cam"], [rule], {"cam": node("cam")})
        entry = next(k for k in keys if k["path"] == "root.VMD.*")
        assert entry["facet"] == "other" and entry["not_capturable"] is False

    def test_io_action_suggests_that_ports_config_on_the_target(self):
        rule = acs_rule(1, "Open Door Rule", triggers=["i8016"],
                        actions=["i8016"], kinds=["IO"],
                        observability={"channels": [
                            {"channel": "device_event", "device_mac": "MAC1",
                             "port": "1"}]})
        keys = cl.suggested_owned_keys(
            ["i8016"], [rule], {"i8016": node("i8016", mac="MAC1")})
        entry = next(k for k in keys if k["path"].startswith("root.IOPort"))
        assert entry["path"] == "root.IOPort.I1.*"
        assert "drives output port 1" in entry["reason"]

    def test_keys_never_name_a_device_outside_the_cluster(self):
        rule = device_rule("other", "9", "x")
        assert cl.suggested_owned_keys(["cam"], [rule], {"cam": node("cam")}) == []


# ═══════════════════════════════════════════════════════════════════════════
# propose() — the whole pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestPropose:
    def test_two_device_topology_is_a_high_confidence_proposal(self):
        g = graph(
            [node("cam", "Lobby loitering cam", tags=["lobby"]),
             node("spk", "Lobby speaker", tags=["lobby"])],
            [edge("E1", "cam", "spk", detail="ACS rule 'Lobby announce' triggers "
                                             "on cam and acts on spk")],
            [acs_rule(1, "Lobby loitering announce", triggers=["cam"],
                      actions=["spk"], topics=["…/loiteringguard/E"],
                      kinds=["DoorStation"]),
             acs_rule(2, "Lobby record", triggers=["cam"], actions=["cam"],
                      kinds=["Record"])])
        out = cl.propose(g, run_id="run1")
        assert len(out["proposals"]) == 1
        p = out["proposals"][0]
        assert p["members"] == ["cam", "spk"]
        assert p["confidence"] == "high"
        assert cl.FLAG_NO_TOPOLOGY not in p["flags"]
        assert any("edge:E1" == e["kind"] for e in p["evidence"])
        assert p["roles"] == {"cam": "detector", "spk": "responder"}

    def test_isolated_devices_never_become_one_blob(self):
        g = graph([node("a", "Alpha"), node("b", "Bravo"), node("c", "Charlie")],
                  [], [device_rule("a", "1", "Alpha PIR"),
                       device_rule("b", "2", "Bravo PIR")])
        out = cl.propose(g, run_id="r")
        members = sorted(p["members"] for p in out["proposals"])
        # a and b each carry a named rule → their own single-device proposals.
        # c has neither a rule nor a link → not proposed, and said so.
        assert members == [["a"], ["b"]]
        assert out["report"]["skipped"][0]["device_ids"] == ["c"]
        assert all(cl.FLAG_SINGLE_DEVICE in p["flags"] for p in out["proposals"])

    def test_a_single_device_with_no_rule_is_not_proposed(self):
        g = graph([node("a", "Alpha")], [], [])
        out = cl.propose(g, run_id="r")
        assert out["proposals"] == []
        assert "no named rule" in out["report"]["skipped"][0]["reason"]
        assert out["report"]["note"]

    def test_name_only_cluster_is_surfaced_flagged_and_capped_low(self):
        """The plan assumed weak clusters would be hidden by default; the live
        fleet has NO topology at all, so hiding them shows nothing. They are
        surfaced, flagged and capped instead — and `include_weak=False` still
        hides them for a caller that wants topology only."""
        g = graph([node("a", "Reception cam", tags=["lab"]),
                   node("b", "Reception speaker", tags=["lab"])],
                  [edge("E5", "a", "b", detail="'reception' in both names")],
                  [device_rule("a", "1", "Reception greeting")])
        out = cl.propose(g, run_id="r")
        assert len(out["proposals"]) == 1
        p = out["proposals"][0]
        assert p["confidence"] == "low"
        assert cl.FLAG_NO_TOPOLOGY in p["flags"] and cl.FLAG_NAME_ONLY in p["flags"]

        hidden = cl.propose(g, run_id="r", include_weak=False)
        assert hidden["proposals"] == []
        assert hidden["report"]["weak_hidden"] == 1
        assert "include_weak" in hidden["report"]["note"]

    def test_acap_only_and_tag_only_clusters_get_their_own_flag(self):
        g = graph([node("a", "One"), node("b", "Two")],
                  [edge("E6", "a", "b", detail="both run AudioManagerPro")],
                  [device_rule("a", "1", "Play")])
        p = cl.propose(g, run_id="r")["proposals"][0]
        assert cl.FLAG_ACAP_ONLY in p["flags"]

    def test_no_acs_flags_the_degradation_and_names_the_reason(self):
        g = graph([node("a", "Alpha"), node("b", "Bravo")],
                  [edge("E4", "a", "b", detail="both tagged #speakers")],
                  [device_rule("a", "1", "Alpha play"),
                   device_rule("b", "2", "Bravo play")],
                  acs_available=False, acs_reason="ACS Pro isn't connected")
        p = cl.propose(g, run_id="r")["proposals"][0]
        assert cl.FLAG_ACS_ABSENT in p["flags"]
        assert any("ACS not connected" in e["detail"] and "ACS Pro isn't connected"
                   in e["detail"] for e in p["evidence"])
        assert p["confidence"] == "low"   # the no-topology cap is the stricter one

    def test_overlapping_hub_is_kept_in_both_proposals(self):
        """ADR-0046: demos on the same device coexist. The hub is reported
        twice, never silently assigned to one side."""
        members = ["h"] + [f"a{i}" for i in range(5)] + [f"b{i}" for i in range(5)]
        edges = []
        for i in range(5):
            edges.append(edge("E5", "h", f"a{i}", weight=0.40))
            edges.append(edge("E5", "h", f"b{i}", weight=0.40))
        for i in range(4):
            edges.append(edge("E1", f"a{i}", f"a{i+1}"))
            edges.append(edge("E1", f"b{i}", f"b{i+1}"))
        rules = [acs_rule(i, f"rule {i}", triggers=[d], actions=[d])
                 for i, d in enumerate(members)]
        out = cl.propose(graph([node(d) for d in members], edges, rules),
                         run_id="r")
        holding = [p for p in out["proposals"] if "h" in p["members"]]
        assert len(holding) >= 2, "the hub must appear in more than one proposal"
        for p in holding:
            assert cl.FLAG_OVERLAP in p["flags"]
            assert any("h" in o["device_ids"] for o in p["overlaps"])
        # And each names the other, by id.
        ids = {p["id"] for p in holding}
        for p in holding:
            assert ids & {o["proposal_id"] for o in p["overlaps"]}

    def test_same_run_over_the_same_graph_reproduces_ids_order_and_scores(self):
        g = graph([node("a", "Reception cam"), node("b", "Reception speaker"),
                   node("c", "Yard cam")],
                  [edge("E5", "a", "b"), edge("E1", "a", "c")],
                  [acs_rule(1, "Reception greet", triggers=["a"], actions=["c"]),
                   device_rule("b", "2", "Reception play")])
        first = cl.propose(g, run_id="run-x")
        second = cl.propose(g, run_id="run-x")
        assert [p["id"] for p in first["proposals"]] == [
            p["id"] for p in second["proposals"]]
        assert [p["score"] for p in first["proposals"]] == [
            p["score"] for p in second["proposals"]]
        assert first == second

    def test_content_key_is_stable_across_runs_while_the_id_is_not(self):
        """Two identifiers on purpose: the id keeps each run's row distinct, the
        content key is what supersede and the dismissal memory join on."""
        g = graph([node("a", "Reception cam"), node("b", "Reception speaker")],
                  [edge("E5", "a", "b")], [device_rule("a", "1", "Reception")])
        one = cl.propose(g, run_id="run-1")["proposals"][0]
        two = cl.propose(g, run_id="run-2")["proposals"][0]
        assert one["id"] != two["id"]
        assert one["content_key"] == two["content_key"] == cl.content_key(["a", "b"])

    def test_names_only_and_blind_rules_are_flagged(self):
        g = graph([node("a", "Alpha")], [],
                  [device_rule("a", "1", "Old rule", names_only=True),
                   acs_rule(2, "Blind", triggers=["a"],
                            observability={"blind": True, "channels": []})])
        p = cl.propose(g, run_id="r")["proposals"][0]
        assert cl.FLAG_NAMES_ONLY_RULES in p["flags"]
        assert cl.FLAG_BLIND_RULES in p["flags"]

    def test_disabled_rules_are_listed_but_never_scored(self):
        g = graph([node("a", "Alpha")], [],
                  [device_rule("a", "1", "Live one"),
                   device_rule("a", "2", "Retired", enabled=False)])
        p = cl.propose(g, run_id="r")["proposals"][0]
        assert len(p["rules"]) == 2
        assert p["score_breakdown"]["named_rule_count"] == 1

    def test_rule_entries_carry_the_additive_source_field(self):
        g = graph([node("a", "Alpha"), node("b", "Bravo")],
                  [edge("E1", "a", "b")],
                  [acs_rule(1, "ACS one", triggers=["a"], actions=["b"]),
                   device_rule("a", "2", "Device one")])
        p = cl.propose(g, run_id="r")["proposals"][0]
        assert {r["source"] for r in p["rules"]} == {"acs", "device"}
        acs_entry = next(r for r in p["rules"] if r["source"] == "acs")
        assert acs_entry["device_id"] == "a"   # the trigger side

    def test_a_rule_resolving_to_no_device_joins_no_cluster(self):
        """The graph reports it as `unattached` (slice 2); clustering must
        simply not see it — never invent a member for it."""
        g = graph([node("a", "Alpha")], [],
                  [device_rule("a", "1", "Alpha PIR"),
                   acs_rule(9, "External Trigger Example")])   # no devices at all
        p = cl.propose(g, run_id="r")["proposals"][0]
        assert p["members"] == ["a"]
        assert [r["rule_id"] for r in p["rules"]] == ["1"]

    def test_params_are_echoed_for_the_audit_trail(self):
        out = cl.propose(graph([]), run_id="r")
        assert out["params"]["max_cluster_devices"] == cl.MAX_CLUSTER_DEVICES
        assert out["params"]["score_weights"]["topology_cohesion"] == 0.40
        assert out["params"]["include_weak_default"] is True

    def test_an_empty_result_always_explains_itself(self):
        out = cl.propose(graph([]), run_id="r")
        assert out["proposals"] == [] and out["report"]["note"]
