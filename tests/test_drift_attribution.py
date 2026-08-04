"""#230 — drift attribution + per-rule grouping.

The load-bearing test in this file is ``TestAnnotateNeverSuppresses``. Everything
else is behaviour; that one is the correctness boundary, and it is written so it
FAILS if attribution ever starts removing rows or touching drift state.
"""

import json
import sqlite3
import time

import pytest

from admz.audit import AuditLog
from admz.snapshot.attribution import (
    APPROVE_WINDOW_S,
    _rule_id_of,
    annotate_attribution,
    live_rule_names,
)
from admz.snapshot.models import DriftField, DriftReport

DEVICE = "E827250959C6"
TEMPLATE = "admz/api/templates/index.html"


@pytest.fixture()
def audit(tmp_path):
    """Isolated audit DB. NEVER the operator's real one (CLAUDE.md)."""
    return AuditLog(db_path=str(tmp_path / "admz.db"))


def _insert(audit, *, action, resource="", details=None, ts=None, success=True):
    """Insert a row with a CONTROLLED timestamp (record() always stamps now)."""
    with sqlite3.connect(audit._db_path) as conn:
        conn.execute(
            "INSERT INTO audit_log (timestamp, requester, auth_source, action, "
            "resource, details_json, success, error_message) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                ts if ts is not None else time.time(),
                "DNLT\\dnich",
                "windows",
                action,
                resource,
                json.dumps(details or {}),
                1 if success else 0,
                "",
            ),
        )
        conn.commit()


def _create_rule_row(audit, *, rule_name, ts=None, rule_id=None):
    """The shape ADMZ actually writes: an INTENT row, success=0, args only."""
    details = {"args": {"device_id": DEVICE, "rule_name": rule_name}}
    if rule_id is not None:
        details["rule_id"] = rule_id  # what #230 PR 2 will add
    _insert(
        audit,
        action="mcp.create_action_rule",
        resource=f"mcp:create_action_rule/device:{DEVICE}",
        details=details,
        ts=ts,
        success=False,
    )


def _rule_rows(rid, name=None, *, added=True):
    """The ~11 flat rows one added rule produces, trimmed to the shape that
    matters: several params plus (optionally) a `name` row."""
    paths = ["actionConfig.actionParameters", "actionConfig.recipientId", "enabled", "id"]
    if name is not None:
        paths.append("name")
    out = []
    for p in paths:
        value = name if p == "name" else "x"
        out.append({
            "facet": "action_rules",
            "path": f"{rid}.{p}",
            "expected": "<missing>" if added else "old",
            "actual": value,
            "canonical_key": f"action_rules:{rid}.{p}",
            "bucket": "unclaimed",
            "owner": None,
            "owner_name": None,
            "candidates": [],
            "base_value": None,
        })
    return out


def _summary(fields, has_drift=True):
    return {
        "device_id": DEVICE,
        "has_drift": has_drift,
        "no_baseline": False,
        "unreadable": False,
        "facets_checked": 5,
        "facets_drifted": 1,
        "drifted_fields": list(fields),
    }


# --------------------------------------------------------------------------- #
# THE CORRECTNESS BOUNDARY
# --------------------------------------------------------------------------- #
class TestAnnotateNeverSuppresses:
    """A matched row is STILL DRIFT. An ADMZ-originated write and a later
    on-device edit can touch the same rule; auto-accepting on a matched audit
    row would hide the second, and nothing downstream could recover it."""

    def test_matched_row_is_still_counted_as_drift(self, audit):
        _create_rule_row(audit, rule_name="AOA Demo - Flash LED Red on Motion")
        fields = _rule_rows("175", "AOA Demo - Flash LED Red on Motion")
        summary = _summary(fields)

        before_paths = [f["path"] for f in summary["drifted_fields"]]
        before_buckets = [f["bucket"] for f in summary["drifted_fields"]]

        annotate_attribution(summary, device_id=DEVICE, audit=audit)

        # The match must have happened — otherwise this test proves nothing.
        assert any(f.get("attribution") for f in summary["drifted_fields"])

        # ...and NOTHING about drift state may have moved.
        assert summary["has_drift"] is True
        assert [f["path"] for f in summary["drifted_fields"]] == before_paths
        assert [f["bucket"] for f in summary["drifted_fields"]] == before_buckets
        assert summary["facets_drifted"] == 1

    def test_bucket_is_never_used_to_express_attribution(self, audit):
        """`demo_set` already suppresses via `bucket` (excluded from
        real_fields). Expressing attribution through `bucket` would silently
        change drift state — so it must stay `unclaimed`."""
        _create_rule_row(audit, rule_name="R")
        summary = _summary(_rule_rows("175", "R"))
        annotate_attribution(summary, device_id=DEVICE, audit=audit)
        for fld in summary["drifted_fields"]:
            assert fld["bucket"] == "unclaimed"
            assert fld.get("attribution") is not None

    def test_real_fields_and_has_drift_survive_a_full_report_round_trip(self, audit):
        _create_rule_row(audit, rule_name="R")
        report = DriftReport(
            device_id=DEVICE,
            has_drift=True,
            fields=[
                DriftField(
                    facet="action_rules",
                    path="175.enabled",
                    expected="<missing>",
                    actual="true",
                    canonical_key="action_rules:175.enabled",
                ),
                DriftField(
                    facet="action_rules",
                    path="175.name",
                    expected="<missing>",
                    actual="R",
                    canonical_key="action_rules:175.name",
                ),
            ],
        )
        assert len(report.real_fields) == 2

        summary = annotate_attribution(
            report.to_summary(), device_id=DEVICE, audit=audit
        )

        assert summary["has_drift"] is True
        assert len(summary["drifted_fields"]) == 2
        assert all(f.get("attribution") for f in summary["drifted_fields"])
        # The dataclass side is untouched — annotation works on the dict only.
        assert len(report.real_fields) == 2
        assert all(f.bucket == "unclaimed" for f in report.fields)

    def test_a_suppressing_implementation_would_fail_this_file(self, audit):
        """Guard the guard: if annotate_attribution ever filtered matched rows
        out, the row count would drop and this asserts it cannot."""
        _create_rule_row(audit, rule_name="R")
        fields = _rule_rows("175", "R") + _rule_rows("194", "S")
        summary = _summary(fields)
        n = len(summary["drifted_fields"])
        annotate_attribution(summary, device_id=DEVICE, audit=audit)
        assert len(summary["drifted_fields"]) == n


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
class TestMatching:
    def test_unmatched_row_renders_normally(self, audit):
        """No audit rows at all → not one key added, anywhere."""
        summary = _summary(_rule_rows("175", "Nobody wrote me"))
        annotate_attribution(summary, device_id=DEVICE, audit=audit)
        assert all("attribution" not in f for f in summary["drifted_fields"])

    def test_other_device_does_not_attribute(self, audit):
        _create_rule_row(audit, rule_name="R")
        summary = _summary(_rule_rows("175", "R"))
        annotate_attribution(summary, device_id="B8A44F0C5B32", audit=audit)
        assert all("attribution" not in f for f in summary["drifted_fields"])

    def test_name_match_is_labelled_a_correlation(self, audit):
        _create_rule_row(audit, rule_name="Welcome to AEC")
        summary = _summary(_rule_rows("194", "Welcome to AEC"))
        annotate_attribution(summary, device_id=DEVICE, audit=audit)
        attr = summary["drifted_fields"][0]["attribution"]
        assert attr["match"] == "rule_name"
        assert attr["confidence"] == "correlated"
        # The hedge must be in the operator-facing text, not just the docstring.
        assert "not by rule id" in attr["note"]
        assert "not unique" in attr["note"]
        assert "NOT proof" in attr["note"]
        # The success=0 intent-row caveat is stated, not hidden.
        assert "success=0" in attr["note"]

    def test_rule_id_match_is_exact_and_wins_over_name(self, audit):
        """Forward-compatible with #230 PR 2: once confirm.py records the id,
        this path lights up with no change to attribution.py."""
        _create_rule_row(audit, rule_name="Some other name", rule_id="175")
        summary = _summary(_rule_rows("175", "Live name differs"))
        annotate_attribution(summary, device_id=DEVICE, audit=audit)
        attr = summary["drifted_fields"][0]["attribution"]
        assert attr["match"] == "rule_id"
        assert attr["confidence"] == "exact"

    def test_device_level_fallback_when_no_rule_matches(self, audit):
        """The weakest tier, and still most of the value: 'ADMZ changed rules on
        this device on <date>' beats 'unexplained'."""
        _insert(
            audit,
            action="snapshot.scenario_activate",
            resource="scenario:demo-verify",
            details={"name": "demo-verify", "applied": [DEVICE]},
        )
        summary = _summary(_rule_rows("175", "Never created via chat"))
        annotate_attribution(summary, device_id=DEVICE, audit=audit)
        attr = summary["drifted_fields"][0]["attribution"]
        assert attr["match"] == "device"
        assert attr["confidence"] == "correlated"
        assert "NOT matched to this specific rule" in attr["note"]

    def test_scenario_save_does_not_attribute(self, audit):
        """scenario_save records a snapshot; it pushes nothing to a device."""
        _insert(
            audit,
            action="snapshot.scenario_save",
            resource="scenario:x",
            details={"name": "x", "saved": [DEVICE]},
        )
        summary = _summary(_rule_rows("175", "R"))
        annotate_attribution(summary, device_id=DEVICE, audit=audit)
        assert all("attribution" not in f for f in summary["drifted_fields"])

    def test_non_action_rules_rows_are_never_touched(self, audit):
        _create_rule_row(audit, rule_name="R")
        other = {
            "facet": "params", "path": "root.Image.I0.Enabled",
            "expected": "yes", "actual": "no",
            "canonical_key": "root.Image.I0.Enabled", "bucket": "unclaimed",
        }
        summary = _summary(_rule_rows("175", "R") + [other])
        annotate_attribution(summary, device_id=DEVICE, audit=audit)
        assert "attribution" not in summary["drifted_fields"][-1]

    def test_no_rule_rows_means_no_audit_query(self, audit):
        """Cheap path: a report with no action_rules rows must not query at all."""
        class Exploding:
            def search(self, **kw):
                raise AssertionError("should not have been queried")

        summary = _summary([{
            "facet": "params", "path": "root.X", "expected": "a",
            "actual": "b", "bucket": "unclaimed",
        }])
        annotate_attribution(summary, device_id=DEVICE, audit=Exploding())


class TestApprover:
    def test_approver_correlated_within_window(self, audit):
        now = time.time()
        _create_rule_row(audit, rule_name="R", ts=now)
        _insert(
            audit,
            action="confirm.approve",
            resource=f"device:{DEVICE}/op:create-action-rule",
            details={"confirmed_by": "DNLT\\dnich", "risk_level": "high"},
            ts=now + 30,
        )
        summary = _summary(_rule_rows("175", "R"))
        annotate_attribution(summary, device_id=DEVICE, audit=audit)
        attr = summary["drifted_fields"][0]["attribution"]
        assert attr["approved_by"] == "DNLT\\dnich"
        assert attr["approved_by_correlated"] is True
        assert "correlated by device and time" in attr["note"]

    def test_approver_outside_window_is_not_claimed(self, audit):
        now = time.time()
        _create_rule_row(audit, rule_name="R", ts=now)
        _insert(
            audit,
            action="confirm.approve",
            resource=f"device:{DEVICE}/op:something-else",
            details={},
            ts=now + APPROVE_WINDOW_S + 60,
        )
        summary = _summary(_rule_rows("175", "R"))
        annotate_attribution(summary, device_id=DEVICE, audit=audit)
        attr = summary["drifted_fields"][0]["attribution"]
        assert attr["approved_by"] is None
        assert attr["approved_by_correlated"] is False


# --------------------------------------------------------------------------- #
# Read-time, not capture-time
# --------------------------------------------------------------------------- #
class TestReadTime:
    def test_report_cached_before_its_audit_row_is_attributed_on_next_read(
        self, audit, tmp_path
    ):
        """The exact ordering the operator hits: drift is computed and cached,
        THEN the audit row is queried. Attribution must not be baked in."""
        cached = _summary(_rule_rows("175", "AOA Demo"))
        assert all("attribution" not in f for f in cached["drifted_fields"])

        # ...audit row exists by the time someone opens the report.
        _create_rule_row(audit, rule_name="AOA Demo")

        annotate_attribution(cached, device_id=DEVICE, audit=audit)
        assert all(f.get("attribution") for f in cached["drifted_fields"])

    def test_to_summary_itself_carries_no_attribution(self):
        """What gets written into the drift cache must stay attribution-free,
        or a stale cache would pin a stale attribution forever."""
        report = DriftReport(
            device_id=DEVICE,
            has_drift=True,
            fields=[DriftField(facet="action_rules", path="175.enabled",
                               expected="<missing>", actual="true")],
        )
        for fld in report.to_summary()["drifted_fields"]:
            assert "attribution" not in fld

    def test_audit_failure_leaves_the_report_untouched(self):
        """Attribution is a nicety; drift is not. A raising audit store must not
        break the report for the device."""
        class Broken:
            def search(self, **kw):
                raise sqlite3.OperationalError("database is locked")

        summary = _summary(_rule_rows("175", "R"))
        n = len(summary["drifted_fields"])
        annotate_attribution(summary, device_id=DEVICE, audit=Broken())
        assert summary["has_drift"] is True
        assert len(summary["drifted_fields"]) == n
        assert all("attribution" not in f for f in summary["drifted_fields"])


# --------------------------------------------------------------------------- #
# Grouping — the rule id survives the flatten
# --------------------------------------------------------------------------- #
class TestGrouping:
    def test_rule_id_is_recoverable_from_every_flattened_path(self):
        """flatten() only joins segments with dots, and ActionRulesFacet keys the
        doc by rule id — so the leading segment IS the rule, always."""
        for path in ("175.actionConfig.actionParameters", "175.enabled",
                     "175.id", "175.name", "194.actionConfig.recipientId"):
            assert _rule_id_of(path) in ("175", "194")

    def test_thirty_six_rows_are_three_rules(self):
        fields = _rule_rows("175", "A") + _rule_rows("194", "B") + _rule_rows("195", "C")
        assert len({_rule_id_of(f["path"]) for f in fields}) == 3

    def test_name_recovered_for_an_added_rule(self):
        fields = _rule_rows("175", "AOA Demo - Flash LED Red on Motion")
        assert live_rule_names(fields) == {"175": "AOA Demo - Flash LED Red on Motion"}

    def test_deleted_rule_takes_its_name_from_the_baseline_side(self):
        fields = _rule_rows("175", None)
        fields.append({
            "facet": "action_rules", "path": "175.name",
            "expected": "Gone Rule", "actual": "<missing>",
            "bucket": "unclaimed",
        })
        assert live_rule_names(fields) == {"175": "Gone Rule"}

    def test_grouping_survives_a_rule_with_only_enabled_changed(self, audit):
        """No `<rid>.name` row exists, so there is no name to show. The group is
        still correct — it degrades to a bare "Rule 175", by design."""
        fields = [{
            "facet": "action_rules", "path": "175.enabled",
            "expected": "true", "actual": "false",
            "canonical_key": "action_rules:175.enabled", "bucket": "unclaimed",
        }]
        assert live_rule_names(fields) == {}       # nothing to name it with
        assert _rule_id_of(fields[0]["path"]) == "175"   # but it still groups

        # ...and it can still be attributed at the device tier.
        _insert(
            audit, action="snapshot.scenario_return",
            resource="scenario:return-to-baseline",
            details={"applied": [DEVICE]},
        )
        summary = _summary(fields)
        annotate_attribution(summary, device_id=DEVICE, audit=audit)
        assert summary["drifted_fields"][0]["attribution"]["match"] == "device"


class TestTemplateWiring:
    """The grouping itself is display-layer JS. These pin the seams so a later
    edit cannot quietly drop them; the rendering is verified on staging."""

    @pytest.fixture()
    def html(self):
        with open(TEMPLATE, encoding="utf-8") as fh:
            return fh.read()

    def test_catof_groups_action_rules_by_rule_id(self, html):
        assert "'action_rules/' + String(f.path).split('.')[0]" in html

    def test_group_label_degrades_without_a_name(self, html):
        assert "'Rule ' + rid + (ruleNames[rid] ? ' — ' + ruleNames[rid] : '')" in html

    def test_readonly_block_is_grouped_too(self, html):
        """action_rules is read-only (write_ops == []), so every rule row lands
        in the read-only block — grouping that block is the whole feature."""
        assert "ro-subgroup-head" in html
        assert "across ' + nRules + ' rule'" in html

    def test_attribution_chip_is_rendered_and_row_keeps_its_affordances(self, html):
        assert "attrChip" in html
        assert "+ demoChip + attrChip +" in html
        # A matched row must NOT lose its checkbox or its ⊘ ignore button:
        # both are built before the chip and unconditioned on attribution.
        assert "f.attribution" in html
        assert "if (f.attribution && f.attribution.label)" in html


class TestCallSites:
    """Attribution sits BELOW to_summary() so the REST route and the MCP tool
    both get it — the chat surface is where an operator most often meets a
    drift report."""

    def _src(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_rest_route_annotates(self):
        src = self._src("admz/api/routes/snapshot.py")
        assert "annotate_attribution(summary, device_id=device_id)" in src

    def test_mcp_tool_annotates(self):
        src = self._src("admz/mcp/server.py")
        assert "annotate_attribution(" in src
