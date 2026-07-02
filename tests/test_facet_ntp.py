"""NtpFacet + the op-level revert seam (facet-backed API revert).

The facet tracks NTP via ntp.cgi (the param tree is a read-only mirror) and is
the first user of ``build_revert_ops``: reverting any drifted NTP field writes
the whole baseline client config back through setNTPClientConfiguration.
"""

from types import SimpleNamespace

from admz.snapshot.facets.ntp import NtpFacet

# The live getNTPInfo shape (P3748-PLVE, AXIS OS 12) — config + volatile state.
LIVE_NTP = {
    "client": {
        "enabled": True,
        "NTSEnabled": False,
        "serversSource": "static",
        "maxSupportedStaticServers": 5,
        "staticServers": ["192.168.1.195", "time.windows.com"],
        "advertisedServers": ["216.239.35.0", "216.239.35.4"],
        "staticNTSKEServers": [],
        "NTSKEServerCACerts": [],
        "synced": True,
        "timeToNextSync": 0,
        "timeOffset": -0.62378,
        "minpoll": 6,
        "maxpoll": 10,
    }
}


class TestSerialize:
    def test_config_kept_volatile_dropped(self):
        doc = NtpFacet().serialize({"ntp": LIVE_NTP})
        assert doc["enabled"] is True
        assert doc["serversSource"] == "static"
        assert doc["staticServers"] == "192.168.1.195 time.windows.com"  # joined
        assert doc["NTSEnabled"] is False
        assert doc["minpoll"] == 6 and doc["maxpoll"] == 10
        # volatile sync state + DHCP-advertised list + capability constant: gone
        for absent in ("synced", "timeOffset", "timeToNextSync",
                       "advertisedServers", "maxSupportedStaticServers",
                       "NTSKEServerCACerts"):
            assert absent not in doc

    def test_missing_or_malformed_response_serializes_empty(self):
        assert NtpFacet().serialize({}) == {}
        assert NtpFacet().serialize({"ntp": None}) == {}
        assert NtpFacet().serialize({"ntp": {"unexpected": 1}}) == {}

    def test_canonical_key_is_facet_scoped(self):
        assert NtpFacet().canonical_key("staticServers") == "ntp:staticServers"


class TestOpRevert:
    def test_op_revertable_covers_setter_fields_only(self):
        f = NtpFacet()
        assert f.op_revertable("enabled")
        assert f.op_revertable("serversSource")
        assert f.op_revertable("staticServers")
        # tracked but the catalog setter can't write these → not op-revertable
        assert not f.op_revertable("minpoll")
        assert not f.op_revertable("NTSEnabled")

    def test_build_revert_ops_writes_whole_baseline_object(self):
        baseline = {"enabled": True, "serversSource": "static",
                    "staticServers": "192.168.1.195 time.windows.com"}
        steps = NtpFacet().build_revert_ops(
            [("staticServers", "192.168.1.195 time.windows.com")], baseline
        )
        assert len(steps) == 1
        s = steps[0]
        assert s["operation_id"] == "ntp.cgi:setNTPClientConfiguration"
        assert s["params"]["enabled"] is True                    # typed bool
        assert s["params"]["serversSource"] == "static"
        assert s["params"]["staticServers"] == [
            "192.168.1.195", "time.windows.com"]                 # typed list
        assert "staticServers" in s["description"]

    def test_build_revert_ops_empty_baseline_returns_none(self):
        assert NtpFacet().build_revert_ops([("enabled", "true")], {}) is None

    def test_deserialize_builds_the_same_setter_call(self):
        calls = NtpFacet().deserialize(
            {"enabled": "true", "serversSource": "static",
             "staticServers": "a b"})
        assert calls == [{
            "operation_id": "ntp.cgi:setNTPClientConfiguration",
            "params": {"enabled": True, "serversSource": "static",
                       "staticServers": ["a", "b"]},
        }]
        assert NtpFacet().deserialize({}) == []


class TestTargetedRevertDispatch:
    """build_targeted_revert_plan mixes param.cgi chunks and op-level steps."""

    def _builder(self, baseline_docs=None, baseline_sha="abc123"):
        from admz.snapshot.restore import RestoreBuilder

        registry = SimpleNamespace(
            get_device_info=lambda did: {
                "device_id": did, "api_family": "vapix",
                "baseline_sha": baseline_sha,
            })
        git = SimpleNamespace(
            read_facet=lambda did, facet, ref: (baseline_docs or {}).get(facet))
        return RestoreBuilder(catalog=None, registry=registry, git_repo=git)

    @staticmethod
    def _field(facet, path, expected):
        return SimpleNamespace(facet=facet, path=path, expected=expected)

    def test_mixed_param_and_op_fields(self):
        builder = self._builder(baseline_docs={"ntp": {
            "enabled": True, "serversSource": "static",
            "staticServers": "192.168.1.195"}})
        plan = builder.build_targeted_revert_plan("CAM1", [
            self._field("image", "I0.Appearance.Compression", "30"),   # param path
            self._field("ntp", "staticServers", "192.168.1.195"),      # op path
        ])
        ops = [s["operation_id"] for s in plan["steps"]]
        assert "param.cgi:update" in ops
        assert "ntp.cgi:setNTPClientConfiguration" in ops
        ntp_step = next(s for s in plan["steps"]
                        if s["operation_id"] == "ntp.cgi:setNTPClientConfiguration")
        assert ntp_step["device_id"] == "CAM1"
        assert ntp_step["risk_level"] == "service-affecting"   # ADR-0034 floor
        assert "Revert 2 drifted settings" in plan["description"]

    def test_op_revert_covers_live_added_fields(self):
        # staticServers gained a server live → expected "<missing>" would be
        # unrevertable via param.cgi; the whole-object write handles it.
        builder = self._builder(baseline_docs={"ntp": {
            "enabled": True, "serversSource": "static", "staticServers": "a"}})
        plan = builder.build_targeted_revert_plan("CAM1", [
            self._field("ntp", "staticServers", "<missing>"),
        ])
        assert any(s["operation_id"] == "ntp.cgi:setNTPClientConfiguration"
                   for s in plan["steps"])
        assert not any("added, not in baseline" in w for w in plan["warnings"])

    def test_missing_baseline_doc_warns_and_skips(self):
        builder = self._builder(baseline_docs={})   # git has no ntp.yaml
        plan = builder.build_targeted_revert_plan("CAM1", [
            self._field("ntp", "enabled", "true"),
        ])
        assert plan["steps"] == []
        assert any("No baseline doc" in w for w in plan["warnings"])

    def test_no_baseline_sha_warns_and_skips(self):
        builder = self._builder(
            baseline_docs={"ntp": {"enabled": True}}, baseline_sha=None)
        plan = builder.build_targeted_revert_plan("CAM1", [
            self._field("ntp", "enabled", "true"),
        ])
        assert plan["steps"] == []
        assert any("No baseline doc" in w for w in plan["warnings"])

    def test_non_op_fields_keep_existing_behavior(self):
        builder = self._builder()
        plan = builder.build_targeted_revert_plan("CAM1", [
            self._field("ntp", "minpoll", "6"),       # tracked, NOT op-revertable
            self._field("time", "NTP.Server", "x"),   # read-only mirror
        ])
        assert plan["steps"] == []
        joined = " ".join(plan["warnings"])
        assert "ntp.minpoll" in joined and "time.NTP.Server" in joined
