"""The demo-inference evidence graph (#124, slice 2).

``admz/demos/inference/graph.py`` is pure — every input is passed in — so this
suite is table-driven and needs no ACS, no device, no network and no DB. The
collection layer (``collect.py``) is exercised through tiny fakes for the three
seams it reads: the registry, the git repo and ACS.

The failure cases the plan names are all here: no ACS (degrade with a reason),
a SOAP-only device (names-only rules), an unresolvable MAC (lands in
``unresolved[]`` while the run still succeeds), no snapshot yet in fast mode,
and a device with no rules producing no edges.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from admz.demos.inference import graph as G


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _isolate_admz_home(tmp_path, monkeypatch):
    """House convention: never let a test read or write the real ADMZ_HOME DB.

    Nothing here should reach a store at all (every seam is injected), so this
    is a guard rather than a dependency.
    """
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path / "admz_home"))


# ═══════════════════════════════════════════════════════════════════════════
# Fixture builders
# ═══════════════════════════════════════════════════════════════════════════

def dev(device_id, *, name=None, model="AXIS TEST", tags=(), host="", acaps=None,
        mac=None):
    return {"device_id": device_id, "nickname": name or device_id, "model": model,
            "tags": list(tags), "host": host, "mac_address": mac or device_id,
            "acaps": dict(acaps or {})}


def acs_rule(rid, name, *, triggers=(), actions=(), enabled=True):
    return {"id": rid, "name": name, "enabled": enabled,
            "require_all_triggers": False, "schedule": None,
            "triggers": list(triggers), "actions": list(actions), "unresolved": []}


def trig(tid, mac, *, kind="DeviceEvent", topic="tns1:Device/tnsaxis:IO/Port",
         unresolved=False, join="api_device_id"):
    return {"id": tid, "kind": kind, "topic": topic, "filters": [],
            "device_ref_unresolved": unresolved,
            "device": (None if (unresolved or mac is None)
                       else {"mac": mac, "join_method": join, "acs_device_id": 1}),
            "join_method": join}


def act(aid, mac, *, kind="Record", params=None, unresolved=False,
        join="api_device_id"):
    return {"id": aid, "kind": kind, "params": dict(params or {}),
            "device_ref_unresolved": unresolved,
            "target_device": (None if (unresolved or mac is None)
                              else {"mac": mac, "join_method": join}),
            "join_method": join}


def device_rule(name, *, topic="tns1:Device/tnsaxis:IO/Port", template="com.axis.x",
                params=()):
    return {"id": "1", "name": name, "enabled": True,
            "activationConfig": {"condition": [{"topicExpression": topic,
                                                "messageContent": "boolean(1)"}],
                                 "startEvent": None, "timeout": None},
            "actionConfig": {"template": template, "recipientId": None,
                             "recipientParameters": [],
                             "actionParameters": [{"name": n, "value": v}
                                                  for n, v in params]}}


def edges_of(graph, edge_id):
    return [e for e in graph["edges"] if e["id"] == edge_id]


def pair(edge):
    return (edge["a"], edge["b"])


# ═══════════════════════════════════════════════════════════════════════════
# Nodes + params
# ═══════════════════════════════════════════════════════════════════════════

class TestNodesAndParams:
    def test_node_carries_mac_tags_and_apps(self):
        nodes = G.build_nodes([dev("AABBCCDDEEFF", name="Front door",
                                   tags=["lab"], acaps={"vmd": "Running"})])
        assert nodes[0]["device_id"] == "AABBCCDDEEFF"
        assert nodes[0]["mac"] == "AABBCCDDEEFF"
        assert nodes[0]["tags"] == ["lab"]
        assert nodes[0]["acaps_known"] is True
        assert nodes[0]["acaps"][0]["name"] == "vmd"

    def test_separator_forms_of_the_same_mac_are_one_key(self):
        """``canonical_mac`` is the only join — never a raw string compare."""
        nodes = G.build_nodes([dev("slot-1", mac="AC:CC:8E:E6:E7:EE")])
        assert nodes[0]["mac"] == "ACCC8EE6E7EE"
        assert G._index_by_mac(nodes)["ACCC8EE6E7EE"] == "slot-1"

    def test_empty_applications_facet_is_unknown_not_no_apps(self):
        nodes = G.build_nodes([dev("A"), dev("B", acaps={"vmd": "Running"})])
        assert nodes[0]["acaps_known"] is False and nodes[0]["acaps"] == []
        assert nodes[1]["acaps_known"] is True

    def test_params_are_echoed_into_the_graph(self):
        g = G.build_graph([dev("A")])
        assert g["params"] == G.params()
        assert g["params"]["weights"]["E1"] == G.E1_WEIGHT
        assert g["params"]["acap"]["max_fraction"] == G.ACAP_MAX_FRACTION


# ═══════════════════════════════════════════════════════════════════════════
# Edges — one class per test, table-driven where it earns it
# ═══════════════════════════════════════════════════════════════════════════

class TestTopologyEdges:
    def test_e1_trigger_on_one_device_action_on_another(self):
        g = G.build_graph(
            [dev("CAM1", name="Lobby cam"), dev("SPK1", name="Lobby speaker")],
            acs_rules=[acs_rule(1, "Greeting on motion",
                                triggers=[trig(10, "CAM1")],
                                actions=[act(20, "SPK1", kind="IO")])],
            acs={"available": True, "reason": "ok"})
        e1 = edges_of(g, "E1")
        assert len(e1) == 1
        assert pair(e1[0]) == ("CAM1", "SPK1")
        assert e1[0]["weight"] == G.E1_WEIGHT
        assert e1[0]["corroborating"] is False
        assert "Greeting on motion" in e1[0]["evidence"][0]["detail"]

    def test_e2_co_membership_only_where_e1_does_not_already_say_it(self):
        """Two triggers, one action: the trigger pair is E2, each trigger→action
        pair is E1 — the same pair never gets both from the same rule."""
        g = G.build_graph(
            [dev("CAM1"), dev("CAM2"), dev("SPK1")],
            acs_rules=[acs_rule(1, "Two cams one speaker",
                                triggers=[trig(10, "CAM1"), trig(11, "CAM2")],
                                actions=[act(20, "SPK1", kind="IO")])],
            acs={"available": True, "reason": "ok"})
        assert {pair(e) for e in edges_of(g, "E1")} == {("CAM1", "SPK1"),
                                                       ("CAM2", "SPK1")}
        assert {pair(e) for e in edges_of(g, "E2")} == {("CAM1", "CAM2")}

    def test_e1_is_not_emitted_when_a_rule_acts_on_its_own_trigger_device(self):
        g = G.build_graph(
            [dev("CAM1"), dev("CAM2")],
            acs_rules=[acs_rule(1, "Record self", triggers=[trig(10, "CAM1")],
                                actions=[act(20, "CAM1")])],
            acs={"available": True, "reason": "ok"})
        assert g["edges"] == []
        assert g["summary"]["topology_edge_count"] == 0

    def test_e3_device_rule_action_naming_another_device(self):
        g = G.build_graph(
            [dev("CAM1", name="Gate cam", host="192.0.2.10"),
             dev("SPK1", name="Gate speaker", host="192.0.2.55")],
            device_rule_facets={
                "CAM1": {"1": device_rule("Announce at the gate",
                                          params=[("url", "http://192.0.2.55/axis-cgi/x")])},
                "SPK1": {},
            })
        e3 = edges_of(g, "E3")
        assert len(e3) == 1 and pair(e3[0]) == ("CAM1", "SPK1")
        assert e3[0]["weight"] == G.E3_WEIGHT
        assert "by host (192.0.2.55)" in e3[0]["evidence"][0]["detail"]

    def test_e3_matches_a_mac_written_with_separators(self):
        g = G.build_graph(
            [dev("AABBCCDDEE01"), dev("AABBCCDDEE02")],
            device_rule_facets={
                "AABBCCDDEE01": {"1": device_rule(
                    "Talk to the other one",
                    params=[("target", "AA:BB:CC:DD:EE:02")])},
                "AABBCCDDEE02": {},
            })
        assert len(edges_of(g, "E3")) == 1

    def test_e3_ip_match_requires_boundaries(self):
        """``10.0.0.5`` must not match inside ``10.0.0.50``."""
        g = G.build_graph(
            [dev("A", host="10.0.0.5"), dev("B", host="10.0.0.50")],
            device_rule_facets={
                "B": {"1": device_rule("Self reference",
                                       params=[("url", "http://10.0.0.50/x")])},
                "A": {},
            })
        assert edges_of(g, "E3") == []


class TestCorroboratingEdges:
    def test_e4_shared_tag(self):
        g = G.build_graph([dev("A", tags=["entrance"]), dev("B", tags=["entrance"]),
                           dev("C"), dev("D")])
        e4 = edges_of(g, "E4")
        assert len(e4) == 1 and pair(e4[0]) == ("A", "B")
        assert e4[0]["weight"] == G.E4_WEIGHT and e4[0]["corroborating"] is True

    def test_e4_ignores_a_tag_every_device_carries(self):
        g = G.build_graph([dev("A", tags=["lab"]), dev("B", tags=["lab"])])
        assert edges_of(g, "E4") == []

    def test_e4_ignores_a_fleet_label_most_devices_carry(self):
        """``#lab`` on 3 of 5 (60 %) is a site label, not a demo grouping —
        the same inverse-frequency test ACAPs get, no hardcoded tag list."""
        g = G.build_graph([dev("A", tags=["lab", "entrance"]),
                           dev("B", tags=["lab", "entrance"]),
                           dev("C", tags=["lab"]), dev("D"), dev("E")])
        e4 = edges_of(g, "E4")
        assert len(e4) == 1 and pair(e4[0]) == ("A", "B")
        assert "entrance" in e4[0]["evidence"][0]["detail"]

    def test_e4_ignores_stopword_tags(self):
        g = G.build_graph([dev("A", tags=["prod"]), dev("B", tags=["prod"]),
                           dev("C"), dev("D")])
        assert edges_of(g, "E4") == []

    def test_e5_distinctive_name_token(self):
        # 5 devices → the 0.40 cap allows a token on 2 of them.
        g = G.build_graph([dev("A", name="Loitering north"),
                           dev("B", name="Loitering south"),
                           dev("C", name="Reception"), dev("D", name="Store room"),
                           dev("E", name="Yard")])
        e5 = edges_of(g, "E5")
        assert len(e5) == 1 and pair(e5[0]) == ("A", "B")
        assert e5[0]["weight"] == G.E5_WEIGHT
        assert "'loitering'" in e5[0]["evidence"][0]["detail"]

    def test_e5_ignores_house_style_and_model_numbers(self):
        g = G.build_graph([dev("A", name="AXIS P3288-LVE camera"),
                           dev("B", name="AXIS P3288-LVE camera"),
                           dev("C", name="Yard"), dev("D", name="Gate"),
                           dev("E", name="Store")])
        assert edges_of(g, "E5") == []


# ═══════════════════════════════════════════════════════════════════════════
# E6 — shared distinctive ACAP (self-calibrating, never a hardcoded list)
# ═══════════════════════════════════════════════════════════════════════════

class TestAcapEdges:
    def _fleet(self, extra_app_on_all=True):
        """Six devices with an app inventory; ``vmd`` is on five of them."""
        common = {"vmd": "Running"} if extra_app_on_all else {}
        return [
            dev("A", acaps={**common, "sfh_detector": "Running"}),
            dev("B", acaps={**common, "sfh_detector": "Running"}),
            dev("C", acaps=dict(common)),
            dev("D", acaps=dict(common)),
            dev("E", acaps=dict(common)),
            dev("F", acaps={"other": "Running"}),
        ]

    def test_distinctive_app_on_two_devices_makes_an_edge_naming_its_rarity(self):
        g = G.build_graph(self._fleet())
        e6 = edges_of(g, "E6")
        assert len(e6) == 1 and pair(e6[0]) == ("A", "B")
        detail = e6[0]["evidence"][0]["detail"]
        assert detail == "both run sfh_detector (2 of 6 devices with an app inventory)"
        assert e6[0]["evidence"][0]["device_count"] == 2
        assert e6[0]["evidence"][0]["inventory_size"] == 6

    def test_ubiquitous_app_produces_no_edge(self):
        """``vmd`` sits on 5 of 6 (83 % ≥ 60 %) — bundled, so it links nothing."""
        g = G.build_graph(self._fleet())
        assert all(e["evidence"][0].get("app") != "vmd" for e in edges_of(g, "E6"))
        apps = {a["name"]: a["distinctive"]
                for a in g["summary"]["acaps"]["apps"]}
        assert apps["vmd"] is False and apps["sfh_detector"] is True

    def test_weight_sits_in_the_rarity_band_and_never_below_edge_min(self):
        g = G.build_graph(self._fleet())
        w = edges_of(g, "E6")[0]["weight"]
        assert G.EDGE_MIN <= w <= G.E6_WEIGHT
        # rarer than the threshold → strictly above the floor
        assert w > G.E6_WEIGHT_FLOOR

    def test_unknown_application_facets_neither_create_nor_suppress_an_edge(self):
        """Devices with no ``applications`` snapshot are out of the denominator,
        so a bundled app can't be mistaken for a rare one (and no edge is made
        for the unknown devices themselves)."""
        with_apps = [dev(x, acaps={"vmd": "Running"}) for x in "ABCD"]
        unknown = [dev(x) for x in "EFGHIJKLMN"]      # 10 devices, facet missing
        g = G.build_graph(with_apps + unknown)
        assert edges_of(g, "E6") == []                 # vmd = 4/4 known → ubiquitous
        assert g["summary"]["acaps"]["devices_with_app_inventory"] == 4

    def test_acap_only_pair_is_labelled_so_slice_3_can_cap_it(self):
        g = G.build_graph(self._fleet())
        e6 = edges_of(g, "E6")[0]
        assert e6["corroborating"] is True and e6["class"] == "capability"
        assert g["summary"]["topology_edge_count"] == 0
        assert "E6" not in G.TOPOLOGY_EDGES

    def test_app_on_a_single_device_links_nothing(self):
        g = G.build_graph([dev("A", acaps={"rare": "Running"}),
                           dev("B", acaps={"other": "Running"})])
        assert edges_of(g, "E6") == []


# ═══════════════════════════════════════════════════════════════════════════
# Rules — normalization, resolution, grounding
# ═══════════════════════════════════════════════════════════════════════════

class TestRules:
    def test_device_rule_normalizes_to_the_shared_shape(self):
        g = G.build_graph(
            [dev("A")],
            device_rule_facets={"A": {"7": device_rule("Casing open",
                                                       topic="tns1:Device/Casing")}})
        r = g["rules"][0]
        assert r["source"] == "device" and r["rule_key"] == "device:A:7"
        assert r["device_ids"] == ["A"] and r["topics"] == ["tns1:Device/Casing"]
        assert r["names_only"] is False
        assert r["join_methods"]["A"] == "registry_device"

    def test_soap_fallback_rule_is_names_only(self):
        """Older firmware yields ``{rule_id, name, enabled, primary_action}`` —
        no condition, no action params. It must be weaker BY CONSTRUCTION: it
        can never produce an E3 edge."""
        g = G.build_graph(
            [dev("A", host="10.1.1.1"), dev("B", host="10.1.1.2")],
            device_rule_facets={
                "A": {"3": {"rule_id": "3", "name": "Legacy 10.1.1.2 notify",
                            "enabled": True, "primary_action": "com.axis.legacy"}},
                "B": {},
            })
        r = g["rules"][0]
        assert r["names_only"] is True and r["topics"] == []
        assert edges_of(g, "E3") == []
        assert g["summary"]["names_only_rules"] == 1

    def test_acs_rule_records_its_join_method(self):
        g = G.build_graph(
            [dev("slot-1", mac="AC:CC:8E:E6:E7:EE")],
            acs_rules=[acs_rule(1, "R", triggers=[trig(10, "ACCC8EE6E7EE")],
                                actions=[])],
            acs={"available": True, "reason": "ok"})
        assert g["rules"][0]["join_methods"] == {"slot-1": "api_device_id"}

    def test_unregistered_mac_lands_in_unresolved_and_the_run_still_succeeds(self):
        g = G.build_graph(
            [dev("KNOWN")],
            acs_rules=[acs_rule(9, "Ghost rule",
                                triggers=[trig(10, "FFFFFFFFFFFF")], actions=[])],
            acs={"available": True, "reason": "ok"})
        assert len(g["unresolved"]) == 1
        u = g["unresolved"][0]
        assert u["kind"] == "unregistered_device" and u["mac"] == "FFFFFFFFFFFF"
        assert "not in the ADMZ registry" in u["reason"]
        assert [r["name"] for r in g["unattached_rules"]] == ["Ghost rule"]
        assert g["summary"]["rule_count"] == 1      # reported, never dropped

    def test_acs_reference_the_anatomy_could_not_resolve_is_reported(self):
        g = G.build_graph(
            [dev("KNOWN")],
            acs_rules=[acs_rule(9, "Broken ref",
                                triggers=[trig(10, None, unresolved=True)],
                                actions=[])],
            acs={"available": True, "reason": "ok"})
        assert g["unresolved"][0]["kind"] == "acs_reference"

    def test_a_rule_naming_no_device_at_all_is_not_an_error(self):
        """An ACS server-side action / HTTPS trigger legitimately names nobody."""
        g = G.build_graph(
            [dev("A")],
            acs_rules=[acs_rule(1, "Server side", triggers=[trig(10, None)],
                                actions=[act(20, None, kind="Alarm")])],
            acs={"available": True, "reason": "ok"})
        assert g["unresolved"] == []
        assert len(g["unattached_rules"]) == 1

    def test_observability_verdict_is_attached_to_acs_rules(self):
        g = G.build_graph(
            [dev("A")],
            acs_rules=[acs_rule(1, "Alarm rule", triggers=[trig(10, None,
                                                                kind="Manual")],
                                actions=[act(20, None, kind="Alarm")])],
            acs={"available": True, "reason": "ok"})
        assert g["rules"][0]["observability"]["verdict"] == "acs_log_alarm"
        assert g["summary"]["observability"] == {"acs_log_alarm": 1}

    def test_malformed_facet_entry_is_skipped_and_the_run_completes(self):
        g = G.build_graph([dev("A")], device_rule_facets={"A": "not-a-dict"})
        assert g["rules"] == [] and g["summary"]["rule_count"] == 0


class TestAppGrounding:
    def test_installed_publisher_app_corroborates_the_rule(self):
        g = G.build_graph(
            [dev("A", acaps={"vmd": "Running"})],
            device_rule_facets={"A": {"1": device_rule(
                "Motion", topic="tnsaxis:CameraApplicationPlatform/VMD/Camera1ProfileANY")}})
        grounding = g["rules"][0]["app_grounding"]
        assert grounding[0]["verdict"] == "corroborated" and grounding[0]["app"] == "vmd"
        assert g["summary"]["rule_app_grounding"]["corroborated"] == 1

    def test_missing_publisher_app_is_the_known_dead_rule_class(self):
        g = G.build_graph(
            [dev("A", acaps={"objectanalytics": "Running"})],
            device_rule_facets={"A": {"1": device_rule(
                "Loitering", topic="tnsaxis:CameraApplicationPlatform/loiteringguard/x")}})
        grounding = g["rules"][0]["app_grounding"]
        assert grounding[0]["verdict"] == "missing_app"
        assert "cannot fire" in grounding[0]["detail"]

    def test_no_application_snapshot_says_unknown_rather_than_guessing(self):
        g = G.build_graph(
            [dev("A")],
            device_rule_facets={"A": {"1": device_rule(
                "Motion", topic="tnsaxis:CameraApplicationPlatform/VMD/x")}})
        assert g["rules"][0]["app_grounding"][0]["verdict"] == "unknown"

    def test_shadowed_motionalarm_carries_the_111_caution(self):
        g = G.build_graph(
            [dev("A", acaps={"vmd": "Running"})],
            device_rule_facets={"A": {"1": device_rule(
                "Motion", topic="tns1:VideoSource/MotionAlarm")}})
        verdicts = [x["verdict"] for x in g["rules"][0]["app_grounding"]]
        assert "shadowed" in verdicts


# ═══════════════════════════════════════════════════════════════════════════
# Degradation + determinism
# ═══════════════════════════════════════════════════════════════════════════

class TestDegradationAndDeterminism:
    def test_no_acs_degrades_with_a_reason_and_still_builds_the_graph(self):
        g = G.build_graph(
            [dev("A", tags=["entrance"]), dev("B", tags=["entrance"]), dev("C"),
             dev("D")],
            device_rule_facets={"A": {"1": device_rule("Local rule")}, "B": {},
                                "C": {}, "D": {}},
            acs={"available": False, "reason": "Firebird reader disabled"})
        assert g["acs"] == {"available": False, "reason": "Firebird reader disabled"}
        assert g["summary"]["acs"]["reason"] == "Firebird reader disabled"
        assert g["summary"]["rules_by_source"] == {"acs": 0, "device": 1}
        assert len(edges_of(g, "E4")) == 1          # device evidence still lands
        assert g["summary"]["topology_edge_count"] == 0

    def test_no_snapshot_yet_is_reported_not_hidden(self):
        g = G.build_graph([dev("A"), dev("B")],
                          device_rule_facets={"A": None, "B": None})
        assert g["devices_without_rule_facet"] == ["A", "B"]
        assert g["summary"]["devices_without_rule_facet"] == 2
        assert g["rules"] == []

    def test_devices_with_no_rules_tags_apps_or_names_produce_no_edges(self):
        g = G.build_graph([dev("A", name="Alpha"), dev("B", name="Bravo"),
                           dev("C", name="Charlie")])
        assert g["edges"] == []
        assert g["summary"]["linked_device_count"] == 0
        assert g["summary"]["edge_count"] == 0

    def test_the_same_inputs_build_an_identical_graph(self):
        devices = [dev("A", tags=["x"], acaps={"rare": "Running"}),
                   dev("B", tags=["x"], acaps={"rare": "Running"}),
                   dev("C", tags=["y"])]
        rules = [acs_rule(1, "R", triggers=[trig(10, "A")],
                          actions=[act(20, "C", kind="IO")])]
        kw = dict(acs_rules=rules, acs={"available": True, "reason": "ok"},
                  generated_at=1.0)
        first = json.dumps(G.build_graph(devices, **kw), sort_keys=True, default=str)
        second = json.dumps(G.build_graph(devices, **kw), sort_keys=True, default=str)
        assert first == second

    def test_edges_are_ordered_strongest_first(self):
        g = G.build_graph(
            [dev("A", tags=["t"], acaps={"rare": "Running"}),
             dev("B", tags=["t"], acaps={"rare": "Running"}),
             dev("C")],
            acs_rules=[acs_rule(1, "R", triggers=[trig(10, "A")],
                                actions=[act(20, "C", kind="IO")])],
            acs={"available": True, "reason": "ok"})
        weights = [e["weight"] for e in g["edges"]]
        assert weights == sorted(weights, reverse=True)
        assert g["edges"][0]["id"] == "E1"


# ═══════════════════════════════════════════════════════════════════════════
# Collection (the I/O layer), driven through fakes
# ═══════════════════════════════════════════════════════════════════════════

class FakeRegistry:
    def __init__(self, devices, info=None):
        self._devices = devices
        self._info = info or {}

    def list_devices(self):
        return list(self._devices)

    def get_device_info(self, device_id):
        return self._info.get(device_id, {})


class FakeGitRepo:
    def __init__(self, facets=None):
        self._facets = facets or {}

    def read_facet(self, device_id, facet, ref=None):
        return self._facets.get((device_id, facet))


class FakeCtx:
    def __init__(self, registry, git_repo):
        self.registry, self.git_repo = registry, git_repo
        self.catalog, self.executors = object(), {}


class TestCollect:
    def test_fast_path_reads_registry_facets_and_degrades_without_acs(self, monkeypatch):
        from admz.demos.inference import collect

        registry = FakeRegistry(
            [{"device_id": "A", "nickname": "Gate", "tags": ["entrance"]},
             {"device_id": "B", "nickname": "Lobby", "tags": ["entrance"]},
             {"device_id": "C", "nickname": "Yard", "tags": []},
             {"device_id": "D", "nickname": "Store", "tags": []}],
            info={"A": {"latest_observed_sha": "sha1"},
                  "B": {"baseline_sha": "sha2"}, "C": {}, "D": {}})
        git = FakeGitRepo({
            ("A", "action_rules"): {"1": device_rule("Gate rule")},
            ("A", "applications"): {"rare": {"status": "Running"}},
            ("B", "applications"): {"rare": {"status": "Running"}},
        })
        monkeypatch.setattr("admz.modules.acs_pro.config.acs_enabled", lambda: False)

        g = _run(collect.collect_graph(FakeCtx(registry, git)))
        assert g["acs"]["available"] is False
        assert collect.ACS_DISABLED_REASON in g["acs"]["reason"]
        assert g["summary"]["device_count"] == 4
        assert g["summary"]["rules_by_source"] == {"acs": 0, "device": 1}
        # B has a snapshot but no action_rules facet; C/D have no snapshot at all.
        assert g["summary"]["devices_without_rule_facet"] == 3
        assert [e["id"] for e in g["edges"]] == ["E4"]             # tag only

    def test_firebird_failure_degrades_with_a_reason_never_raises(self, monkeypatch):
        from admz.demos.inference import collect

        monkeypatch.setattr("admz.modules.acs_pro.config.acs_enabled", lambda: True)
        monkeypatch.setattr("admz.modules.acs_pro.firebird.firebird_enabled",
                            lambda: True)
        monkeypatch.setattr("admz.modules.acs_pro.firebird.firebird_available",
                            lambda: (True, "ok"))

        def _boom(*_a, **_k):
            raise RuntimeError("database is locked")

        monkeypatch.setattr("admz.modules.acs_pro.firebird.rule_anatomy", _boom)
        monkeypatch.setattr("admz.modules.acs_pro.client.run_acs_op",
                            _fake_op({"success": False, "message": "offline"}))

        res = _run(collect.read_acs_rules(FakeCtx(FakeRegistry([]), FakeGitRepo())))
        assert res["available"] is False and "database is locked" in res["reason"]
        assert res["rules"] == []

    def test_live_device_list_feeds_the_supported_join_path(self, monkeypatch):
        from admz.demos.inference import collect

        seen = {}

        def _anatomy(reader=None, acs_api_devices=None):
            seen["api"] = acs_api_devices
            return []

        monkeypatch.setattr("admz.modules.acs_pro.config.acs_enabled", lambda: True)
        monkeypatch.setattr("admz.modules.acs_pro.firebird.firebird_enabled",
                            lambda: True)
        monkeypatch.setattr("admz.modules.acs_pro.firebird.firebird_available",
                            lambda: (True, "ok"))
        monkeypatch.setattr("admz.modules.acs_pro.firebird.rule_anatomy", _anatomy)
        monkeypatch.setattr("admz.modules.acs_pro.client.run_acs_op", _fake_op(
            {"success": True,
             "data": {"Devices": [{"DeviceId": "14070_guid",
                                   "MacAddress": "B8A44F0C5B32"}]}}))

        res = _run(collect.read_acs_rules(FakeCtx(FakeRegistry([]), FakeGitRepo())))
        assert res["available"] is True and res["api_device_count"] == 1
        assert seen["api"][0]["MacAddress"] == "B8A44F0C5B32"

    def test_describe_headlines_the_run(self):
        from admz.demos.inference import collect

        g = G.build_graph([dev("A"), dev("B")],
                          acs={"available": False, "reason": "no acs"})
        line = collect.describe(g)
        assert "2 device(s)" in line and "ACS unavailable" in line

    def test_summary_only_is_the_agent_digest(self):
        from admz.demos.inference import collect

        g = G.build_graph([dev("A", acaps={"rare": "Running"}),
                           dev("B", acaps={"rare": "Running"}),
                           dev("C", acaps={"common": "Running"}),
                           dev("D", acaps={"common": "Running"})])
        digest = collect.summary_only(g)
        assert digest["devices"][0]["distinctive_apps"] == ["rare"]
        assert digest["edges"][0]["id"] == "E6"
        assert digest["edges"][0]["why"]


def _fake_op(result):
    async def _op(*_args, **_kwargs):
        return result
    return _op
