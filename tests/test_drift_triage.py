"""ADR-0070 §1 and §7 — drift triage, and the FirmwareManagement seed rule.

The load-bearing tests are the ANNOTATE-NEVER-SUPPRESS ones: triage adds keys
and never changes what counts as drift. The classification tests pin the table
and, more importantly, its ORDER, which is where the judgement lives.
"""

from __future__ import annotations

import copy
import subprocess

import pytest
import yaml

from admz.snapshot import triage
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.triage import (
    TriageContext,
    annotate_triage,
    classify_field,
    highest_importance,
    report_context,
    summarize_by_class,
)

DEVICE = "B8A44F9C0A11"
MISSING = "<missing>"


def _field(key, expected, actual, *, facet=None, path=None, bucket="unclaimed",
           revertable=None):
    """A drifted-field dict as ``to_summary`` + ``annotate_revertable`` make it.

    Param facets: the canonical key is the full ``root.*`` key. Other facets:
    ``<facet>:<path>``.
    """
    if facet is None:
        facet = "other"
    if path is None:
        path = key.split(":", 1)[1] if ":" in key else key
    fld = {
        "facet": facet, "path": path, "expected": expected, "actual": actual,
        "canonical_key": key, "bucket": bucket, "owner": None,
        "owner_name": None, "candidates": [], "base_value": None,
    }
    if revertable is not None:
        fld["revertable"] = revertable
    return fld


def _summary(fields, has_drift=True):
    return {
        "device_id": DEVICE, "has_drift": has_drift, "baseline_sha": "b" * 40,
        "observed_sha": "o" * 40, "drifted_fields": fields,
    }


def _cls(fld, ctx=None):
    return classify_field(fld, ctx)["class"]


FIRMWARE_UP = TriageContext(baseline_firmware="12.9.57", live_firmware="12.11.77",
                            firmware_changed=True)

# The operator's screenshot, AXIS C8110 on 12.11.77.
SCREENSHOT = [
    _field("event_mqtt_bridge:publication.topicPrefix", "default", "DEFAULT",
           facet="event_mqtt_bridge", revertable=True),
    _field("root.Properties.FirmwareManagement.Version", "1.8", "1.10",
           revertable=False),
    _field("root.ImageSource.I0.Sensor.HDRMode", MISSING, "auto",
           revertable=False),
    _field("root.Output.O0.PulseMode", MISSING, "no", revertable=False),
]


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #
class TestTheScreenshotIsAllNoise:
    def test_the_four_rows(self):
        assert [_cls(f) for f in SCREENSHOT] == [
            "cosmetic", "firmware_managed", "added_key", "added_key"]

    def test_highest_importance_is_low(self):
        summary = annotate_triage(_summary(copy.deepcopy(SCREENSHOT)))
        assert summary["highest_importance"] == "low"
        assert {f["triage"]["recommendation"] for f in summary["drifted_fields"]} == {
            "accept"}

    def test_the_case_only_row_says_why(self):
        label = classify_field(SCREENSHOT[0])
        assert label["rule"] == "cosmetic.case_or_number"
        assert "case" in label["why"]


class TestClassification:
    @pytest.mark.parametrize("fld, expected", [
        # identity
        (_field("users:admin_access.AdminAccess", MISSING, "admin", facet="users",
                revertable=False), "security_sensitive"),
        (_field("root.Properties.API.HTTP.AdminAccess", "yes", "no",
                facet="users", revertable=False), "security_sensitive"),
        (_field("applications:objectanalytics.status", MISSING, "Running",
                facet="applications", revertable=False), "security_sensitive"),
        (_field("applications:objectanalytics.status", "Running", MISSING,
                facet="applications", revertable=False), "security_sensitive"),
        # cosmetic
        (_field("root.Image.I0.Appearance.Mode", "  day   NIGHT ", "Day Night",
                revertable=True), "cosmetic"),
        (_field("root.Image.I0.Appearance.Brightness", "50.0", "50",
                revertable=True), "cosmetic"),
        # firmware-managed keys
        (_field("root.Properties.Firmware.BuildDate", "a", "b"), "firmware_managed"),
        (_field("root.Brand.ProdNbr", "C8110", "C8110-X"), "firmware_managed"),
        (_field("root.Audio.DSP.Build", "7", "9", revertable=True),
         "firmware_managed"),
        # runtime state beats network configuration
        (_field("root.Network.eth0.IPAddress", "10.0.0.5", "10.0.0.9",
                facet="network", revertable=False), "runtime_state"),
        (_field("root.Network.Resolver.NameServer1", "10.0.0.1", "10.0.0.2",
                facet="network", revertable=False), "runtime_state"),
        (_field("root.Network.Interface.I0.dot1x.Status", "Stopped", "Unauthorized",
                facet="network", revertable=False), "runtime_state"),
        (_field("root.Time.NTP.VolatileServer", "a", "b", facet="time",
                revertable=False), "runtime_state"),
        (_field("root.Time.ServerTime", "10:00:00", "10:00:01", facet="time",
                revertable=False), "runtime_state"),
        # security configuration
        (_field("root.Network.IPv4.DefaultRouter", "10.0.0.1", "10.0.0.254",
                facet="network", revertable=True), "security_sensitive"),
        (_field("root.HTTPS.Port", "443", "8443", revertable=True),
         "security_sensitive"),
        (_field("root.RemoteService.Enabled", "no", "yes", revertable=False),
         "security_sensitive"),
        (_field("root.SNMP.Enabled", "no", "yes", revertable=True),
         "security_sensitive"),
        (_field("root.System.BoaGroupPolicy.AccessAdmin", "a", "b",
                revertable=True), "security_sensitive"),
        # service configuration
        (_field("root.Image.I0.Appearance.Brightness", "50", "60",
                facet="image", revertable=True), "service_config"),
        (_field("ntp:servers.0.address", "a.pool", "b.pool", facet="ntp",
                revertable=True), "service_config"),
        (_field("action_rules:3.enabled", "true", "false", facet="action_rules",
                revertable=False), "service_config"),
        (_field("applications:objectanalytics.status", "Running", "Stopped",
                facet="applications", revertable=False), "service_config"),
        # read-only
        (_field("root.Image.I0.MaxResolution", "1920x1080", "3840x2160",
                facet="image", revertable=False), "read_only"),
        (_field("applications:objectanalytics.version", "1.2", "1.3",
                facet="applications", revertable=False), "read_only"),
        # the rest
        (_field("root.MyAcap.Threshold", "10", "20", revertable=True),
         "uncategorized"),
    ])
    def test_class(self, fld, expected):
        assert _cls(fld) == expected

    def test_demo_buckets_pass_through(self):
        base = _field("root.Image.I0.Appearance.Brightness", "50", "60",
                      facet="image", revertable=True)
        got = {}
        for bucket in ("demo_set", "demo_broken", "candidate"):
            got[bucket] = classify_field(dict(base, bucket=bucket))
        assert (got["demo_set"]["class"], got["demo_set"]["importance"]) == (
            "demo_set", "none")
        assert (got["demo_broken"]["class"], got["demo_broken"]["importance"],
                got["demo_broken"]["recommendation"]) == (
            "demo_broken", "high", "repair")
        assert (got["candidate"]["class"], got["candidate"]["importance"]) == (
            "demo_candidate", "medium")

    def test_every_label_has_every_key(self):
        label = classify_field(SCREENSHOT[1])
        assert set(label) == {"class", "importance", "recommendation", "why", "rule"}
        assert label["importance"] in triage.IMPORTANCE_ORDER


class TestTheOrderCarriesTheJudgement:
    """Swap two rows of the table and one of these fails."""

    def test_a_new_admin_account_is_high_although_it_appeared(self):
        label = classify_field(_field(
            "users:admin_access.AdminAccess", MISSING, "admin", facet="users",
            revertable=False))
        assert (label["class"], label["importance"]) == ("security_sensitive", "high")
        assert label["rule"] == "identity.account"

    def test_a_dhcp_re_lease_is_not_a_security_alarm(self):
        label = classify_field(_field(
            "root.Network.eth0.IPAddress", "10.0.0.5", "10.0.0.9",
            facet="network", revertable=False))
        assert (label["class"], label["importance"]) == ("runtime_state", "low")

    def test_a_security_change_admz_cannot_write_back_stays_high(self):
        label = classify_field(_field(
            "root.HTTPS.Port", "443", "8443", revertable=False))
        assert (label["class"], label["importance"]) == ("security_sensitive", "high")

    def test_a_new_admin_account_stays_high_after_a_firmware_upgrade(self):
        label = classify_field(_field(
            "users:admin_access.AdminAccess", MISSING, "admin", facet="users",
            revertable=False), FIRMWARE_UP)
        assert label["importance"] == "high"

    def test_the_rule_ids_are_in_the_documented_order(self):
        ids = [r.id for r in triage.RULES]
        assert ids.index("identity.account") < ids.index("added.key")
        assert ids.index("runtime.state") < ids.index("security.config")
        assert ids.index("security.config") < ids.index("read_only.not_revertable")
        # the refinement: read-only-by-design facets stay reachable
        assert ids.index("service.action_rule") < ids.index("read_only.not_revertable")
        assert ids.index("service.app_run_state") < ids.index("read_only.not_revertable")
        assert ids[-1] == "uncategorized"


class TestFirmwareContext:
    def test_an_app_that_moved_with_the_firmware_is_firmware_managed(self):
        fld = _field("applications:objectanalytics.version", "1.2", "1.3",
                     facet="applications", revertable=False)
        label = classify_field(fld, FIRMWARE_UP)
        assert label["class"] == "firmware_managed"
        assert "12.9.57 → 12.11.77" in label["why"]

    def test_a_key_that_appeared_with_the_firmware_is_firmware_managed(self):
        label = classify_field(SCREENSHOT[2], FIRMWARE_UP)
        assert (label["class"], label["rule"]) == (
            "firmware_managed", "firmware.appeared_with_upgrade")
        assert "12.11.77" in label["why"]

    def test_without_a_firmware_change_it_is_just_an_added_key(self):
        same = TriageContext(baseline_firmware="12.11.77", live_firmware="12.11.77")
        assert _cls(SCREENSHOT[2], same) == "added_key"

    def test_the_context_rides_on_the_report(self):
        summary = annotate_triage(_summary(copy.deepcopy(SCREENSHOT)),
                                  context=FIRMWARE_UP)
        assert summary["triage_context"] == {
            "baseline_firmware": "12.9.57", "live_firmware": "12.11.77",
            "firmware_changed": True, "last_accept": None}


# --------------------------------------------------------------------------- #
# Annotate, never suppress
# --------------------------------------------------------------------------- #
def _strip_triage(summary):
    out = copy.deepcopy(summary)
    for key in ("triage_context", "summary_by_class", "highest_importance"):
        out.pop(key, None)
    for fld in out["drifted_fields"]:
        fld.pop("triage", None)
    return out


class TestAnnotateNeverSuppresses:
    def _mixed(self):
        return _summary([
            _field("root.Image.I0.Appearance.Brightness", "50", "40",
                   facet="image", bucket="demo_set", revertable=False),
            *copy.deepcopy(SCREENSHOT),
            _field("root.HTTPS.Port", "443", "8443", revertable=True),
        ])

    def test_nothing_but_triage_keys_change(self):
        before = self._mixed()
        after = annotate_triage(copy.deepcopy(before), context=FIRMWARE_UP)
        assert _strip_triage(after) == before

    def test_every_row_survives_including_demo_set(self):
        after = annotate_triage(self._mixed())
        assert len(after["drifted_fields"]) == 6
        assert after["drifted_fields"][0]["bucket"] == "demo_set"
        assert after["drifted_fields"][0]["triage"]["class"] == "demo_set"
        assert after["has_drift"] is True
        assert [f["revertable"] for f in after["drifted_fields"]] == [
            False, True, False, False, False, True]

    def test_a_raising_rule_leaves_the_report_untouched(self, monkeypatch):
        def boom(r, ctx):
            raise RuntimeError("a rule with a bug")
        broken = triage.Rule("broken", "x", "low", "accept", boom,
                             lambda r, ctx: "")
        # Last-but-one, so only the final row — which no other rule claims —
        # reaches it: five labels are computed before the failure, and none
        # of them may land.
        monkeypatch.setattr(triage, "RULES", triage.RULES[:-1] + (broken,)
                            + triage.RULES[-1:])
        before = self._mixed()
        before["drifted_fields"].append(
            _field("root.MyAcap.Threshold", "10", "20", revertable=True))
        after = annotate_triage(copy.deepcopy(before))
        assert after == before

    def test_an_empty_report(self):
        summary = annotate_triage(_summary([], has_drift=False))
        assert summary["highest_importance"] == "none"
        assert summary["summary_by_class"] == {}
        assert summary["drifted_fields"] == []


class TestSummaries:
    def test_by_class_is_most_important_first_then_most_common(self):
        labels = [classify_field(f) for f in SCREENSHOT] + [
            classify_field(_field("root.HTTPS.Port", "443", "8443", revertable=True)),
        ]
        by_class = summarize_by_class(labels)
        assert list(by_class) == [
            "security_sensitive", "added_key", "cosmetic", "firmware_managed"]
        assert by_class["added_key"] == {
            "count": 2, "importance": "low", "recommendation": "accept"}

    def test_highest_importance(self):
        assert highest_importance([]) == "none"
        assert highest_importance([{"importance": "low"},
                                   {"importance": "medium"},
                                   {"importance": "none"}]) == "medium"


# --------------------------------------------------------------------------- #
# The context is read from git
# --------------------------------------------------------------------------- #
@pytest.fixture
def repo(tmp_path):
    path = str(tmp_path / "config-repo")
    r = GitRepo(path)
    for key, val in [("user.email", "t@t.com"), ("user.name", "T"),
                     ("commit.gpgsign", "false")]:
        subprocess.run(["git", "config", key, val], cwd=path, check=True)
    return r


def _commit_device(repo, firmware):
    repo.write_device_yaml(DEVICE, {"model": "AXIS C8110",
                                    "firmware_version": firmware})
    repo.write_facet(DEVICE, "image", {"I0.Resolution": firmware})
    return repo.commit_snapshot(DEVICE, message=f"Audit: {firmware}",
                                auto_push=False)


class TestReportContext:
    def test_firmware_change_comes_from_the_two_commits(self, repo):
        baseline = _commit_device(repo, "12.9.57")
        observed = _commit_device(repo, "12.11.77")
        summary = dict(_summary([]), baseline_sha=baseline, observed_sha=observed)
        # The registry only knows the live firmware — the baseline side can
        # only have come from git.
        ctx = report_context(summary, git_repo=repo,
                             device_info={"firmware_version": "12.11.77"})
        assert (ctx.baseline_firmware, ctx.live_firmware, ctx.firmware_changed) == (
            "12.9.57", "12.11.77", True)

    def test_same_firmware_at_both_commits(self, repo):
        baseline = _commit_device(repo, "12.11.77")
        summary = dict(_summary([]), baseline_sha=baseline, observed_sha=baseline)
        ctx = report_context(summary, git_repo=repo, device_info={})
        assert ctx.firmware_changed is False

    def test_the_registry_is_only_the_live_fallback(self, repo):
        baseline = _commit_device(repo, "12.9.57")
        summary = dict(_summary([]), baseline_sha=baseline, observed_sha=None)
        ctx = report_context(summary, git_repo=repo,
                             device_info={"firmware_version": "12.11.77"})
        assert (ctx.live_firmware, ctx.firmware_changed) == ("12.11.77", True)

    def test_the_last_accept_note_when_it_describes_this_baseline(self, repo):
        baseline = _commit_device(repo, "12.9.57")
        (repo.device_path(DEVICE) / "BASELINE.yaml").write_text(yaml.safe_dump({
            "accepted_at": 1.0, "accepted_by": "HOMELAB\\alice",
            "baseline_sha": baseline, "note": "fw upgrade"}))
        repo.commit_snapshot(DEVICE, message="Accept baseline", auto_push=False)
        summary = dict(_summary([]), baseline_sha=baseline, observed_sha=baseline)
        ctx = report_context(summary, git_repo=repo, device_info={})
        assert ctx.last_accept == {"accepted_at": 1.0,
                                   "accepted_by": "HOMELAB\\alice",
                                   "note": "fw upgrade"}

        other = dict(summary, baseline_sha="c" * 40)
        assert report_context(other, git_repo=repo, device_info={}).last_accept is None

    def test_never_raises(self):
        class Broken:
            def get_file(self, path, ref):
                raise OSError("git is gone")
        ctx = report_context(_summary([]), git_repo=Broken(),
                             device_info={"firmware_version": "12.11.77"})
        assert ctx.firmware_changed is False
        assert ctx.baseline_firmware is None

    def test_a_hostile_device_id_is_not_used_as_a_path(self):
        class Recorder:
            paths = []
            def get_file(self, path, ref):
                self.paths.append(path)
                return None
        rec = Recorder()
        report_context(dict(_summary([]), device_id="../../etc"), git_repo=rec,
                       device_info={})
        assert rec.paths == []


# --------------------------------------------------------------------------- #
# ADR-0070 §7 — the seed rule
# --------------------------------------------------------------------------- #
class TestFirmwareManagementSeed:
    #: Append-only: the full list, in order. A reorder or a removal re-seeds
    #: rules operators already deleted (the list length is the high-water mark).
    SEEDS = [
        "root.Network.eth0.IPv6.IPAddresses",
        "root.Network.Routing.*",
        "root.Time.NTP.VolatileServer",
        "root.Network.DHCP.VendorClass",
        "root.Network.ZeroConf.IPAddress",
        "root.Network.ZeroConf.SubnetMask",
        "root.Network.VolatileHostName.HostName",
        "root.Network.UPnP.FriendlyName",
        "root.Time.NTP.Server",
        "root.Time.ServerDate",
        "root.Time.ServerTime",
        "root.Properties.FirmwareManagement.*",
    ]

    def test_the_seed_list_is_append_only(self):
        import admz.snapshot.ignore as ig
        assert [r["key"] for r in ig._SEED_DEFAULT_RULES] == self.SEEDS
        assert {r["scope"] for r in ig._SEED_DEFAULT_RULES} == {"global"}

    def test_it_ignores_the_screenshot_key_and_nothing_beside_it(self):
        from admz.snapshot.ignore import matches_any
        rule = [self.SEEDS[-1]]
        assert matches_any("root.Properties.FirmwareManagement.Version", rule)
        assert not matches_any("root.Properties.Firmware.Version", rule)
        assert not matches_any("root.Properties.API.HTTP.AdminAccess", rule)
