"""Tests for admz.snapshot.drift_alerts."""

import pytest

from admz.snapshot.drift_alerts import (
    DriftAlert,
    DriftAlertStore,
    _signature_for,
)
from admz.snapshot.models import DriftField, DriftReport


@pytest.fixture
def store(tmp_path):
    return DriftAlertStore(str(tmp_path / "admz.db"))


def _report(device_id, *fields):
    """Build a DriftReport from (facet, path, expected, actual) tuples."""
    r = DriftReport(device_id=device_id, has_drift=bool(fields))
    for facet, path, expected, actual in fields:
        r.fields.append(
            DriftField(facet=facet, path=path, expected=expected, actual=actual)
        )
    return r


# ---------------------------------------------------------------------------
# Signature hashing
# ---------------------------------------------------------------------------


class TestSignature:
    def test_empty_report_has_stable_signature(self):
        s1 = _signature_for(_report("cam-01"))
        s2 = _signature_for(_report("cam-01"))
        assert s1 == s2

    def test_field_order_does_not_affect_signature(self):
        r1 = _report(
            "cam-01",
            ("network", "host", "a", "b"),
            ("image", "fps", "30", "60"),
        )
        r2 = _report(
            "cam-01",
            ("image", "fps", "30", "60"),
            ("network", "host", "a", "b"),
        )
        assert _signature_for(r1) == _signature_for(r2)

    def test_value_change_changes_signature(self):
        r1 = _report("cam-01", ("network", "host", "a", "b"))
        r2 = _report("cam-01", ("network", "host", "a", "different"))
        assert _signature_for(r1) != _signature_for(r2)

    def test_path_change_changes_signature(self):
        r1 = _report("cam-01", ("network", "host", "a", "b"))
        r2 = _report("cam-01", ("network", "other", "a", "b"))
        assert _signature_for(r1) != _signature_for(r2)


# ---------------------------------------------------------------------------
# process_report transitions
# ---------------------------------------------------------------------------


class TestProcessReportTransitions:
    def test_first_report_sets_baseline_no_alert(self, store):
        result = store.process_report(_report("cam-01"))
        assert result is None
        baseline = store.get_last_signature("cam-01")
        assert baseline is not None
        assert baseline["field_count"] == 0

    def test_same_report_twice_no_alert(self, store):
        r = _report("cam-01", ("network", "host", "a", "b"))
        # First call sets baseline.
        assert store.process_report(r) is None
        # Same drift → no transition.
        assert store.process_report(r) is None

    def test_sync_to_drifted_emits_appeared(self, store):
        store.process_report(_report("cam-01"))  # baseline: in sync
        alert = store.process_report(
            _report("cam-01", ("network", "host", "a", "b"))
        )
        assert alert is not None
        assert alert.transition == "appeared"
        assert alert.previous_count == 0
        assert alert.current_count == 1
        assert "1 field" in alert.summary

    def test_drifted_to_sync_emits_cleared(self, store):
        # Establish drifted baseline.
        store.process_report(_report("cam-01", ("network", "host", "a", "b")))
        alert = store.process_report(_report("cam-01"))
        assert alert is not None
        assert alert.transition == "cleared"
        assert alert.previous_count == 1
        assert alert.current_count == 0

    def test_drift_field_change_emits_changed(self, store):
        store.process_report(
            _report("cam-01", ("network", "host", "a", "b"))
        )
        alert = store.process_report(
            _report(
                "cam-01",
                ("network", "host", "a", "b"),
                ("image", "fps", "30", "60"),
            )
        )
        assert alert is not None
        assert alert.transition == "changed"
        assert alert.previous_count == 1
        assert alert.current_count == 2

    def test_field_value_change_emits_changed(self, store):
        """Same field set, different actual value → still 'changed'."""
        store.process_report(
            _report("cam-01", ("network", "host", "a", "b"))
        )
        alert = store.process_report(
            _report("cam-01", ("network", "host", "a", "different"))
        )
        assert alert is not None
        assert alert.transition == "changed"


# ---------------------------------------------------------------------------
# list_alerts queries
# ---------------------------------------------------------------------------


class TestListAlerts:
    def test_returns_empty_when_no_alerts(self, store):
        assert store.list_alerts() == []

    def test_returns_newest_first(self, store):
        store.process_report(_report("cam-01"))
        store.process_report(
            _report("cam-01", ("network", "host", "a", "b"))
        )
        store.process_report(
            _report("cam-01", ("network", "host", "a", "c"))
        )
        alerts = store.list_alerts()
        assert len(alerts) == 2
        # Newest first
        assert alerts[0].transition == "changed"
        assert alerts[1].transition == "appeared"

    def test_filter_by_device_id(self, store):
        store.process_report(_report("cam-01"))
        store.process_report(_report("cam-01", ("a", "b", "c", "d")))
        store.process_report(_report("cam-02"))
        store.process_report(_report("cam-02", ("x", "y", "z", "w")))

        alerts = store.list_alerts(device_id="cam-01")
        assert len(alerts) == 1
        assert alerts[0].device_id == "cam-01"

    def test_filter_by_transition(self, store):
        store.process_report(_report("cam-01"))
        store.process_report(_report("cam-01", ("a", "b", "c", "d")))
        store.process_report(_report("cam-01"))

        appeared = store.list_alerts(transitions=["appeared"])
        cleared = store.list_alerts(transitions=["cleared"])
        assert len(appeared) == 1
        assert len(cleared) == 1
        assert appeared[0].transition == "appeared"
        assert cleared[0].transition == "cleared"

    def test_filter_by_since(self, store):
        import time

        store.process_report(_report("cam-01"))
        store.process_report(_report("cam-01", ("a", "b", "c", "d")))

        future = time.time() + 60
        assert store.list_alerts(since=future) == []

    def test_limit(self, store):
        store.process_report(_report("cam-01"))
        for i in range(10):
            store.process_report(
                _report("cam-01", ("k", "p", "e", f"a-{i}"))
            )
        assert len(store.list_alerts(limit=3)) == 3


# ---------------------------------------------------------------------------
# clear_baseline
# ---------------------------------------------------------------------------


class TestClearBaseline:
    def test_clear_returns_true_when_existed(self, store):
        store.process_report(_report("cam-01"))
        assert store.clear_baseline("cam-01") is True
        assert store.get_last_signature("cam-01") is None

    def test_clear_returns_false_for_unknown(self, store):
        assert store.clear_baseline("never-seen") is False

    def test_after_clear_next_report_is_baseline(self, store):
        """Clearing means the next report is treated as the baseline
        (no transition alert)."""
        store.process_report(_report("cam-01"))
        store.process_report(_report("cam-01", ("a", "b", "c", "d")))
        # Drifted baseline now stored. Clear it.
        store.clear_baseline("cam-01")
        # Next report — even if drifted — should not emit an alert.
        result = store.process_report(_report("cam-01", ("a", "b", "c", "d")))
        assert result is None


# ---------------------------------------------------------------------------
# DriftDetector integration: check_drift feeds the alert store
# ---------------------------------------------------------------------------


class TestDriftDetectorIntegration:
    @pytest.mark.asyncio
    async def test_check_drift_records_baseline_on_first_call(
        self, tmp_path, monkeypatch
    ):
        """The first check_drift() call sets the alert-store baseline
        for that device. No alert emitted (it's the baseline)."""
        from admz import snapshot as _snap_module
        from admz.snapshot import drift_alerts as _alerts_module

        store = DriftAlertStore(str(tmp_path / "admz.db"))
        monkeypatch.setattr(_alerts_module, "drift_alerts", store)

        # Drive check_drift with a stubbed detector — easier than a
        # real one. We just want to verify the alert plumbing is wired.
        from admz.snapshot.drift import DriftDetector
        from unittest.mock import AsyncMock, MagicMock

        engine = MagicMock()
        engine.registry.get_device_info.return_value = {"device_id": "cam-01"}
        engine._read_all_params = AsyncMock(return_value={})
        engine._read_extra_ops = AsyncMock(return_value={})

        git = MagicMock()
        git.read_facet.return_value = None  # no facets stored → no drift

        detector = DriftDetector(engine, git)
        report = await detector.check_drift("cam-01")
        # Empty report, but the baseline is now in place.
        baseline = store.get_last_signature("cam-01")
        assert baseline is not None
        assert baseline["field_count"] == 0
        # No alert on first observation.
        assert store.list_alerts() == []
