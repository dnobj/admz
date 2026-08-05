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
        mac=None, has_snapshot_ref=None):
    """``has_snapshot_ref`` defaults to True when ``acaps`` is given (a device
    with a known inventory obviously has a snapshot) and False otherwise (the
    ordinary "never snapshotted" case) — pass it explicitly to build the third
    state: a device WITH a snapshot ref whose inventory reads empty (#189)."""
    if has_snapshot_ref is None:
        has_snapshot_ref = bool(acaps)
    return {"device_id": device_id, "nickname": name or device_id, "model": model,
            "tags": list(tags), "host": host, "mac_address": mac or device_id,
            "acaps": dict(acaps or {}), "has_snapshot_ref": has_snapshot_ref}


def acs_rule(rid, name, *, triggers=(), actions=(), enabled=True):
    return {"id": rid, "name": name, "enabled": enabled,
            "require_all_triggers": False, "schedule": None,
            "triggers": list(triggers), "actions": list(actions), "unresolved": []}


def trig(tid, mac, *, kind="DeviceEvent", topic="tns1:Device/tnsaxis:IO/Port",
         unresolved=False, join="api_device_id", ref=None):
    """``ref`` overrides the device reference outright — how a test expresses a
    reference that *exists but is incomplete* (the resolver's
    ``acs_device_id_only`` path yields a device dict whose ``mac`` is None)."""
    return {"id": tid, "kind": kind, "topic": topic, "filters": [],
            "device_ref_unresolved": unresolved,
            "device": (ref if ref is not None else
                       (None if (unresolved or mac is None)
                        else {"mac": mac, "join_method": join, "acs_device_id": 1})),
            "join_method": join}


def act(aid, mac, *, kind="Record", params=None, unresolved=False,
        join="api_device_id", ref=None):
    return {"id": aid, "kind": kind, "params": dict(params or {}),
            "device_ref_unresolved": unresolved,
            "target_device": (ref if ref is not None else
                              (None if (unresolved or mac is None)
                               else {"mac": mac, "join_method": join})),
            "join_method": join}


def device_rule(name, *, topic="tns1:Device/tnsaxis:IO/Port", template="com.axis.x",
                params=(), enabled=True):
    return {"id": "1", "name": name, "enabled": enabled,
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

    def test_has_snapshot_ref_distinguishes_never_from_empty(self):
        """#189: a device that was never snapshotted and one that has a
        snapshot but an empty inventory both carry ``acaps_known: False`` —
        but they are not the same fleet state, and ``has_snapshot_ref`` is
        the (honest, ref-presence-only) distinction between them."""
        nodes = G.build_nodes([
            dev("never", has_snapshot_ref=False),
            dev("empty", acaps={}, has_snapshot_ref=True),
            dev("known", acaps={"vmd": "Running"}),
        ])
        by_id = {n["device_id"]: n for n in nodes}
        assert by_id["never"]["acaps_known"] is False
        assert by_id["never"]["has_snapshot_ref"] is False
        assert by_id["empty"]["acaps_known"] is False
        assert by_id["empty"]["has_snapshot_ref"] is True
        assert by_id["known"]["has_snapshot_ref"] is True

    def test_app_inventory_breakdown_splits_the_fleet_three_ways(self):
        nodes = G.build_nodes([
            dev("never1", has_snapshot_ref=False),
            dev("never2", has_snapshot_ref=False),
            dev("empty1", acaps={}, has_snapshot_ref=True),
            dev("known1", acaps={"vmd": "Running"}),
        ])
        assert G.app_inventory_breakdown(nodes) == {
            "known": 1, "never_snapshotted": 2, "empty_inventory": 1,
        }

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


class TestDisabledRules:
    """A disabled rule is *history*: it says these devices were once wired
    together, never that they work together now. It stays fully visible in
    ``rules[]`` — and contributes no edge of any class."""

    def test_a_disabled_acs_rule_makes_no_e1_edge(self):
        kw = dict(acs_rules=[acs_rule(1, "Greeting on motion",
                                      triggers=[trig(10, "CAM1")],
                                      actions=[act(20, "SPK1", kind="IO")],
                                      enabled=False)],
                  acs={"available": True, "reason": "ok"})
        devices = [dev("CAM1", name="Lobby cam"), dev("SPK1", name="Lobby speaker")]
        g = G.build_graph(devices, **kw)
        assert edges_of(g, "E1") == []
        assert g["summary"]["topology_edge_count"] == 0
        # …and the same rule enabled DOES make the edge — the flag is the only
        # difference between these two graphs.
        kw["acs_rules"][0]["enabled"] = True
        assert len(edges_of(G.build_graph(devices, **kw), "E1")) == 1

    def test_a_disabled_acs_rule_makes_no_e2_edge(self):
        g = G.build_graph(
            [dev("CAM1"), dev("CAM2")],
            acs_rules=[acs_rule(1, "Two cams", triggers=[trig(10, "CAM1"),
                                                         trig(11, "CAM2")],
                                actions=[], enabled=False)],
            acs={"available": True, "reason": "ok"})
        assert edges_of(g, "E2") == []

    def test_a_disabled_device_rule_makes_no_e3_edge(self):
        g = G.build_graph(
            [dev("CAM1", name="Gate cam", host="192.0.2.10"),
             dev("SPK1", name="Gate speaker", host="192.0.2.55")],
            device_rule_facets={
                "CAM1": {"1": device_rule(
                    "Announce at the gate", enabled=False,
                    params=[("url", "http://192.0.2.55/axis-cgi/x")])},
                "SPK1": {},
            })
        assert edges_of(g, "E3") == []

    def test_a_disabled_rule_still_records_what_it_references(self):
        """Withholding the edge must not lose the reference: the rule is kept,
        flagged disabled, with its target still resolved."""
        g = G.build_graph(
            [dev("CAM1", host="192.0.2.10"), dev("SPK1", host="192.0.2.55")],
            device_rule_facets={
                "CAM1": {"1": device_rule(
                    "Announce", enabled=False,
                    params=[("url", "http://192.0.2.55/axis-cgi/x")])},
                "SPK1": {},
            })
        r = g["rules"][0]
        assert r["enabled"] is False
        assert r["action_device_ids"] == ["SPK1"]      # reference kept on the record
        assert r["join_methods"]["SPK1"] == "action_host"
        assert g["summary"]["disabled_rules"] == 1

    def test_a_disabled_rules_name_is_not_naming_evidence_either(self):
        """E5 draws on rule names as well as device names — a disabled rule must
        not sneak its topology back in through the naming channel."""
        devices = [dev(x, name=n) for x, n in
                   [("A", "North"), ("B", "South"), ("C", "Reception"),
                    ("D", "Store room"), ("E", "Yard")]]
        rules = [acs_rule(1, "Loitering showcase",
                          triggers=[trig(10, "A")],
                          actions=[act(20, "B", kind="IO")], enabled=False)]
        g = G.build_graph(devices, acs_rules=rules,
                          acs={"available": True, "reason": "ok"})
        assert g["edges"] == []
        rules[0]["enabled"] = True
        live = G.build_graph(devices, acs_rules=rules,
                             acs={"available": True, "reason": "ok"})
        assert {e["id"] for e in live["edges"]} == {"E1", "E5"}

    def test_a_disabled_rule_is_still_reported_never_hidden(self):
        g = G.build_graph(
            [dev("CAM1"), dev("SPK1")],
            acs_rules=[acs_rule(1, "Old greeting", triggers=[trig(10, "CAM1")],
                                actions=[act(20, "SPK1", kind="IO")],
                                enabled=False)],
            acs={"available": True, "reason": "ok"})
        assert [r["name"] for r in g["rules"]] == ["Old greeting"]
        assert g["summary"]["rule_count"] == 1
        assert g["summary"]["disabled_rules"] == 1

    def test_an_anatomy_without_an_enabled_field_reads_as_enabled(self):
        """A missing field must not silently erase a rule's evidence — the same
        default a device rule gets."""
        row = acs_rule(1, "R", triggers=[trig(10, "CAM1")],
                       actions=[act(20, "SPK1", kind="IO")])
        row.pop("enabled")
        g = G.build_graph([dev("CAM1"), dev("SPK1")], acs_rules=[row],
                          acs={"available": True, "reason": "ok"})
        assert g["rules"][0]["enabled"] is True
        assert len(edges_of(g, "E1")) == 1


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

    def test_unknown_application_facets_are_excluded_from_the_known_denominator(self):
        """Devices with no ``applications`` snapshot are out of the denominator,
        so a bundled app can't be mistaken for a rare one (and no edge is made
        for the unknown devices themselves). Renamed from a name that claimed
        this exclusion "neither creates nor suppresses" an edge (#189) — that
        claim was false; see the next test."""
        with_apps = [dev(x, acaps={"vmd": "Running"}) for x in "ABCD"]
        unknown = [dev(x) for x in "EFGHIJKLMN"]      # 10 devices, facet missing
        g = G.build_graph(with_apps + unknown)
        assert edges_of(g, "E6") == []                 # vmd = 4/4 known → ubiquitous
        assert g["summary"]["acaps"]["devices_with_app_inventory"] == 4

    def test_one_unrelated_devices_missing_inventory_flips_other_devices_edges(self):
        """The actual #189 scenario: A/B/C share ``sfh_detector`` (a real,
        rare app). Six devices total, all with known inventory, gives
        3/6 = 0.50 < 0.60 — distinctive, edges exist. Take ONE more device
        (F) from "known, doesn't run it" to "unknown" and NOTHING about
        A, B or C changed — yet total drops from 6 to 5, 3/5 = 0.60 is NOT
        < 0.60, and every A-B/A-C/B-C edge disappears. This is the
        cross-contamination the corrected comments now describe honestly
        instead of denying."""
        base = [
            dev("A", acaps={"sfh_detector": "Running"}),
            dev("B", acaps={"sfh_detector": "Running"}),
            dev("C", acaps={"sfh_detector": "Running"}),
            # Each on exactly one device — below ACAP_MIN_DEVICES, so neither
            # forms its own edge; they exist only to pad the fleet to six.
            dev("D", acaps={"d_only_app": "Running"}),
            dev("E", acaps={"e_only_app": "Running"}),
        ]
        healthy = base + [dev("F", acaps={"unrelated": "Running"})]
        g_healthy = G.build_graph(healthy)
        assert g_healthy["summary"]["acaps"]["devices_with_app_inventory"] == 6
        healthy_pairs = {pair(e) for e in edges_of(g_healthy, "E6")}
        assert healthy_pairs == {("A", "B"), ("A", "C"), ("B", "C")}

        # F's read now fails/never happened — F itself is untouched otherwise.
        degraded = base + [dev("F", has_snapshot_ref=False)]
        g_degraded = G.build_graph(degraded)
        assert g_degraded["summary"]["acaps"]["devices_with_app_inventory"] == 5
        assert edges_of(g_degraded, "E6") == []   # A-B, A-C, B-C ALL vanished

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

    def test_summary_breaks_down_the_unknown_population_honestly(self):
        g = G.build_graph([
            dev("known", acaps={"vmd": "Running"}),
            dev("never", has_snapshot_ref=False),
            dev("empty", acaps={}, has_snapshot_ref=True),
        ])
        acaps = g["summary"]["acaps"]
        assert acaps["devices_with_app_inventory"] == 1
        assert acaps["devices_never_snapshotted"] == 1
        assert acaps["devices_with_empty_inventory"] == 1


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

    def test_a_device_reference_with_no_mac_is_incomplete_not_device_free(self):
        """``build_device_resolver``'s ``acs_device_id_only`` path hands back a
        device ref with ``mac: None``. That is a real device ADMZ could not
        join — never the same thing as an action that names no device."""
        g = G.build_graph(
            [dev("A")],
            acs_rules=[acs_rule(1, "Half-resolved",
                                triggers=[trig(10, None,
                                               ref={"acs_device_id": 42, "mac": None,
                                                    "name": "Cam 42", "ip": "10.0.0.9",
                                                    "join_method": "acs_device_id_only"})],
                                actions=[])],
            acs={"available": True, "reason": "ok"})
        assert [u["kind"] for u in g["unresolved"]] == ["incomplete_device_ref"]
        u = g["unresolved"][0]
        assert u["ref"] == "trigger:10" and u["rule_name"] == "Half-resolved"
        assert "Cam 42" in u["reason"] and "no MAC" in u["reason"]
        assert g["summary"]["unresolved_count"] == 1

    def test_an_action_target_with_no_mac_is_reported_too(self):
        g = G.build_graph(
            [dev("A")],
            acs_rules=[acs_rule(1, "Half-resolved action",
                                triggers=[trig(10, "A")],
                                actions=[act(20, None,
                                             ref={"acs_device_id": 7, "mac": None,
                                                  "join_method": "acs_device_id_only"})])],
            acs={"available": True, "reason": "ok"})
        assert [u["kind"] for u in g["unresolved"]] == ["incomplete_device_ref"]
        assert g["unresolved"][0]["ref"] == "action:20"

    def test_observability_verdict_is_attached_to_acs_rules(self):
        g = G.build_graph(
            [dev("A")],
            acs_rules=[acs_rule(1, "Alarm rule", triggers=[trig(10, None,
                                                                kind="Manual")],
                                actions=[act(20, None, kind="Alarm")])],
            acs={"available": True, "reason": "ok"})
        assert g["rules"][0]["observability"]["verdict"] == "acs_log_alarm"
        assert g["summary"]["observability"] == {"acs_log_alarm": 1}

    def test_a_facet_that_is_not_a_rule_map_is_reported_not_read_as_no_rules(self):
        """A damaged facet is neither "no rules" nor "no snapshot". Skipping it
        silently is the one place the no-silent-drop contract could break
        without anybody noticing, so it lands in ``unresolved``."""
        g = G.build_graph([dev("A")], device_rule_facets={"A": "not-a-dict"})
        assert g["rules"] == [] and g["summary"]["rule_count"] == 0   # run completes
        assert [u["kind"] for u in g["unresolved"]] == ["unparsable_device_rule_facet"]
        u = g["unresolved"][0]
        assert u["ref"] == "A" and "str" in u["reason"]
        assert g["summary"]["unresolved_count"] == 1
        # It HAS a facet — it must not be filed under "never snapshotted".
        assert g["devices_without_rule_facet"] == []


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

    def test_a_failed_facet_read_is_not_the_same_fact_as_no_snapshot(self):
        """"Never snapshotted" tells the operator to run a survey. A permission
        or repository failure tells them something else entirely — the two must
        not arrive as the same diagnostic."""
        g = G.build_graph(
            [dev("A"), dev("B")],
            device_rule_facets={"B": None},
            facet_read_errors={"A": "PermissionError: [Errno 13] .git/objects"})
        assert g["devices_without_rule_facet"] == ["B"]          # B only
        assert [u["kind"] for u in g["unresolved"]] == ["facet_read_error"]
        u = g["unresolved"][0]
        assert u["ref"] == "A" and "PermissionError" in u["reason"]
        assert "not a missing snapshot" in u["reason"]
        assert g["summary"]["unresolved_count"] == 1

    def test_devices_with_no_rules_tags_apps_or_names_produce_no_edges(self):
        g = G.build_graph([dev("A", name="Alpha"), dev("B", name="Bravo"),
                           dev("C", name="Charlie")])
        assert g["edges"] == []
        assert g["summary"]["linked_device_count"] == 0
        assert g["summary"]["edge_count"] == 0

    def _deterministic_inputs(self):
        devices = [dev("A", tags=["x"], acaps={"rare": "Running"}),
                   dev("B", tags=["x"], acaps={"rare": "Running"}),
                   dev("C", tags=["y"])]
        rules = [acs_rule(1, "R", triggers=[trig(10, "A")],
                          actions=[act(20, "C", kind="IO")])]
        return devices, dict(acs_rules=rules,
                             acs={"available": True, "reason": "ok"})

    def test_the_same_inputs_build_an_identical_graph(self, monkeypatch):
        """No fixed ``generated_at`` here on purpose: pinning the timestamp is
        exactly what would let a clock read hide from this test. The clock is
        made to move between the two builds, so any time-dependence in the pure
        builder fails this outright."""
        import itertools
        import time as _time

        clock = itertools.count(1_000_000.0, 1000.0)
        monkeypatch.setattr(_time, "time", lambda: next(clock))

        devices, kw = self._deterministic_inputs()
        first = json.dumps(G.build_graph(devices, **kw), sort_keys=True, default=str)
        second = json.dumps(G.build_graph(devices, **kw), sort_keys=True, default=str)
        assert first == second

    def test_the_pure_builder_reads_no_clock_and_leaves_the_stamp_to_its_caller(self):
        """``generated_at`` is provenance, and provenance is the run's job. The
        builder echoes what it is handed and invents nothing."""
        devices, kw = self._deterministic_inputs()
        assert G.build_graph(devices, **kw)["generated_at"] is None
        assert G.build_graph(devices, generated_at=1234.5, **kw)["generated_at"] == 1234.5
        assert not hasattr(G, "time")      # the module does not even import it

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

    def test_an_unreadable_registry_fails_the_run_rather_than_faking_an_empty_fleet(self):
        """The node set IS the registry. Swallowing the read turns "we could not
        look" into "there is nothing there" — a complete, clean, false run that
        no caller can tell from a genuinely empty fleet."""
        from admz.demos.inference import collect

        class Broken(FakeRegistry):
            def list_devices(self):
                raise RuntimeError("database is locked")

        with pytest.raises(collect.CollectionError) as exc:
            _run(collect.collect_graph(FakeCtx(Broken([]), FakeGitRepo())))
        assert "database is locked" in str(exc.value)
        assert "empty fleet" in str(exc.value)

    def test_that_failure_is_recorded_on_the_run_not_smoothed_over(self, tmp_path):
        from admz.demos.inference import collect
        from admz.demos.inference.runs import STATUS_FAILED, InferenceRunStore

        class Broken(FakeRegistry):
            def list_devices(self):
                raise RuntimeError("database is locked")

        store = InferenceRunStore(db_path=str(tmp_path / "admz.db"))
        run = _run(collect.run_fast(FakeCtx(Broken([]), FakeGitRepo()), store))
        assert run.status == STATUS_FAILED
        assert "database is locked" in run.error
        assert store.get(run.id).status == STATUS_FAILED

    def test_an_empty_registry_still_succeeds(self):
        """The counterpart: zero devices is a fact, and a fact still builds."""
        from admz.demos.inference import collect

        g = _run(collect.collect_graph(FakeCtx(FakeRegistry([]), FakeGitRepo()),
                                       include_acs=False))
        assert g["summary"]["device_count"] == 0 and g["nodes"] == []

    def test_a_facet_read_failure_is_not_reported_as_a_missing_snapshot(self):
        """A permission/repo/parse failure must not masquerade as "this device
        has never been snapshotted" — that sends the operator to run a survey
        that cannot fix it."""
        from admz.demos.inference import collect

        class BrokenRepo(FakeGitRepo):
            def read_facet(self, device_id, facet, ref=None):
                if device_id == "A":
                    raise PermissionError("[Errno 13] .git/objects")
                return super().read_facet(device_id, facet, ref)

        registry = FakeRegistry([{"device_id": "A"}, {"device_id": "B"}],
                                info={"A": {"latest_observed_sha": "sha1"},
                                      "B": {"latest_observed_sha": "sha2"}})
        g = _run(collect.collect_graph(FakeCtx(registry, BrokenRepo()),
                                       include_acs=False))
        assert g["devices_without_rule_facet"] == ["B"]      # B genuinely has none
        assert [u["kind"] for u in g["unresolved"]] == ["facet_read_error"]
        assert "PermissionError" in g["unresolved"][0]["reason"]
        assert g["summary"]["devices_without_rule_facet"] == 1

    def test_the_collection_layer_is_what_stamps_the_graph(self):
        """The builder is deterministic, so the wall clock enters here."""
        from admz.demos.inference import collect

        g = _run(collect.collect_graph(FakeCtx(FakeRegistry([]), FakeGitRepo()),
                                       include_acs=False))
        assert isinstance(g["generated_at"], float) and g["generated_at"] > 0

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
