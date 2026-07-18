"""Drift-diff cache (ADR-0049): cache the full DriftReport at detection so the
diff can be inspected / accepted / reverted instantly, without re-probing the
device. A cached report may be stale (further drift can occur after it's
computed) — accepted by design and reconciled by the next audit — but it is
invalidated the moment the baseline moves.

Covers the store (store/get/clear, cache-on-every-check, baseline stamp) and the
route paths (inspect serves cache + ?refresh forces live; the baseline-match
guard; revert reads the cache instead of re-probing).
"""

from __future__ import annotations

import subprocess
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from admz.auth import AuthBackend, NoAuth, Principal, set_active_backend
from admz.snapshot.drift_alerts import DriftAlertStore
from admz.snapshot.models import DriftField, DriftReport


def _report(device_id, *, baseline="base1", observed="obs1", fields=(), has_drift=None):
    r = DriftReport(
        device_id=device_id,
        has_drift=(bool(fields) if has_drift is None else has_drift),
        baseline_sha=baseline, observed_sha=observed,
    )
    for facet, path, expected, actual in fields:
        r.fields.append(DriftField(facet=facet, path=path, expected=expected, actual=actual))
    return r


# ---------------------------------------------------------------------------
# Store-level
# ---------------------------------------------------------------------------


class TestReportCacheStore:
    @pytest.fixture
    def store(self, tmp_path):
        return DriftAlertStore(str(tmp_path / "admz.db"))

    def test_store_get_roundtrip(self, store):
        store.store_report(_report("d", fields=[("ntp", "root.NTP.Server", "a", "b")]))
        got = store.get_report("d")
        assert got is not None
        assert got["observed_sha"] == "obs1"
        assert got["report"]["baseline_sha"] == "base1"
        assert got["report"]["has_drift"] is True
        assert len(got["report"]["drifted_fields"]) == 1
        assert isinstance(got["computed_at"], (int, float))

    def test_get_missing_is_none(self, store):
        assert store.get_report("nope") is None

    def test_clear_report(self, store):
        store.store_report(_report("d"))
        assert store.clear_report("d") is True
        assert store.get_report("d") is None
        assert store.clear_report("d") is False  # already gone

    def test_process_report_caches_the_diff(self, store):
        """The core wiring: every check (process_report) warms the diff cache."""
        store.process_report(_report("d", fields=[("f", "p", "x", "y")]))
        got = store.get_report("d")
        assert got is not None and len(got["report"]["drifted_fields"]) == 1

    def test_process_report_caches_in_sync_too(self, store):
        store.process_report(_report("d", fields=[("f", "p", "x", "y")]))
        store.process_report(_report("d", fields=[], has_drift=False))  # now in sync
        got = store.get_report("d")
        assert got is not None
        assert got["report"]["has_drift"] is False
        assert got["report"]["drifted_fields"] == []

    def test_clear_baseline_clears_cached_report(self, store):
        store.process_report(_report("d", fields=[("f", "p", "x", "y")]))
        assert store.get_report("d") is not None
        store.clear_baseline("d")  # accept-of-older-commit path
        assert store.get_report("d") is None


# ---------------------------------------------------------------------------
# Route-level
# ---------------------------------------------------------------------------


class _StubBackend(AuthBackend):
    def __init__(self, p):
        self.p = p

    async def authenticate(self, request):
        return self.p


@contextmanager
def _with_admin():
    admin = Principal(name="AXIS\\admin", display_name="admin", source="windows",
                      groups=["Administrators"], is_anonymous=False)
    set_active_backend(_StubBackend(admin))
    try:
        yield admin
    finally:
        set_active_backend(NoAuth())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    monkeypatch.setenv("ADMZ_AUTO_PUSH", "false")

    from admz.snapshot import drift_alerts as da_module
    fresh_da = da_module.DriftAlertStore(str(tmp_path / "admz.db"))
    monkeypatch.setattr(da_module, "drift_alerts", fresh_da)

    from admz.api.main import app
    with TestClient(app, follow_redirects=False) as c:
        repo = str(tmp_path / "config-repo")
        for k, v in [("user.email", "t@t.com"), ("user.name", "T"),
                     ("commit.gpgsign", "false")]:
            subprocess.run(["git", "config", k, v], cwd=repo, check=True)
        c._da = fresh_da  # expose the isolated store to tests
        yield c


def _ctx():
    from admz.api.context import get_context
    return get_context()


def _seed(client, did, *, baseline="base1", observed="obs1", fields=(("ntp", "root.NTP.Server", "a", "b"),)):
    ctx = _ctx()
    ctx.registry.add_device(did, {"host": "192.0.2.9"})
    ctx.registry.set_config_pointers(did, baseline_sha=baseline)
    client._da.store_report(_report(did, baseline=baseline, observed=observed, fields=list(fields)))
    return ctx


def _count_probes(monkeypatch, ctx):
    calls = []

    async def fake_check_drift(device_id, *a, **k):
        calls.append(device_id)
        return DriftReport(device_id=device_id, has_drift=False,
                           baseline_sha="base1", observed_sha="live-obs")

    monkeypatch.setattr(ctx.drift_detector, "check_drift", fake_check_drift)
    return calls


class TestInspectServesCache:
    def test_cache_hit_no_probe(self, client, monkeypatch):
        ctx = _seed(client, "cam-x")
        calls = _count_probes(monkeypatch, ctx)
        r = client.get("/api/snapshot/drift?device_id=cam-x")
        assert r.status_code == 200
        body = r.json()
        assert body["cached"] is True
        assert body["has_drift"] is True
        assert len(body["drifted_fields"]) == 1
        assert "computed_at" in body
        assert calls == []  # served from cache — never probed the device

    def test_refresh_forces_live(self, client, monkeypatch):
        ctx = _seed(client, "cam-x")
        calls = _count_probes(monkeypatch, ctx)
        r = client.get("/api/snapshot/drift?device_id=cam-x&refresh=true")
        assert r.status_code == 200
        assert r.json()["cached"] is False
        assert calls == ["cam-x"]  # forced a live recompute

    def test_stale_baseline_cache_ignored(self, client, monkeypatch):
        # cache was computed against base1, but the device's baseline moved.
        ctx = _seed(client, "cam-x", baseline="base1")
        ctx.registry.set_config_pointers("cam-x", baseline_sha="base2")
        calls = _count_probes(monkeypatch, ctx)
        r = client.get("/api/snapshot/drift?device_id=cam-x")
        assert r.status_code == 200
        assert r.json()["cached"] is False
        assert calls == ["cam-x"]  # stale-baseline cache skipped → live check

    def test_no_cache_falls_back_to_live(self, client, monkeypatch):
        ctx = _ctx()
        ctx.registry.add_device("cam-y", {"host": "192.0.2.10"})
        ctx.registry.set_config_pointers("cam-y", baseline_sha="base1")
        calls = _count_probes(monkeypatch, ctx)
        r = client.get("/api/snapshot/drift?device_id=cam-y")
        assert r.status_code == 200
        assert r.json()["cached"] is False and calls == ["cam-y"]


class TestRevertUsesCache:
    def test_revert_reads_cache_not_probe(self, client, monkeypatch):
        ctx = _seed(client, "cam-x")
        # If revert re-probed, this would raise; it must read the cached diff.
        async def boom(device_id, *a, **k):
            raise AssertionError("revert must not re-probe when a cache exists")
        monkeypatch.setattr(ctx.drift_detector, "check_drift", boom)
        with _with_admin():
            r = client.post("/api/snapshot/revert", json={"device_ids": ["cam-x"]})
        # 200 (gated plan / nothing-to-revert) — the point is it didn't probe.
        assert r.status_code == 200
