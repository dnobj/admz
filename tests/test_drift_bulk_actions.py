"""Tests for the bulk drift actions behind the drift-review UI:

  * ``POST /api/snapshot/accept-baseline-bulk`` — bless N devices in ONE
    combined git commit (``Accept baseline: N devices — <note>``).
  * ``POST /api/snapshot/revert`` — revert one OR many devices in a single
    gated plan (the plan engine already serializes multi-device plans);
    also the unified path the per-device "Revert" button uses.

Both require an authenticated principal (CR-3 parity with accept/restore).
The revert ``note`` is an audit annotation only (revert makes no git change).
"""

from __future__ import annotations

import subprocess
from contextlib import contextmanager

import pytest
import yaml
from fastapi.testclient import TestClient

from admz.auth import AuthBackend, NoAuth, Principal, set_active_backend


class _StubBackend(AuthBackend):
    def __init__(self, p):
        self.p = p

    async def authenticate(self, request):
        return self.p


@contextmanager
def _with_admin():
    admin = Principal(
        name="AXIS\\admin", display_name="admin", source="windows",
        groups=["Administrators"], is_anonymous=False,
    )
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

    # Isolate the drift-signature cache on the temp DB so accept can write
    # in-sync signatures the test can read back (the endpoints resolve the
    # singleton at call time, so a monkeypatch is seen).
    from admz.snapshot import drift_alerts as da_module
    fresh_da = da_module.DriftAlertStore(str(tmp_path / "admz.db"))
    monkeypatch.setattr(da_module, "drift_alerts", fresh_da)

    from admz.api.main import app
    with TestClient(app, follow_redirects=False) as c:
        repo = str(tmp_path / "config-repo")
        for k, v in [("user.email", "t@t.com"),
                     ("user.name", "T"), ("commit.gpgsign", "false")]:
            subprocess.run(["git", "config", k, v], cwd=repo, check=True)
        yield c


def _ctx():
    from admz.api.context import get_context
    return get_context()


# ---------------------------------------------------------------------------
# Request-model validation
# ---------------------------------------------------------------------------

def test_refresh_drift_after_accept_branches(tmp_path, monkeypatch):
    """Accepting the latest observation marks in-sync; accepting an older
    commit drops the signature (forces the next check to recompute)."""
    from admz.snapshot import drift_alerts as da_module
    from admz.snapshot.models import DriftField, DriftReport
    from admz import operations

    store = da_module.DriftAlertStore(str(tmp_path / "drift.db"))
    monkeypatch.setattr(da_module, "drift_alerts", store)

    def _seed_drift(did):
        store.process_report(DriftReport(
            device_id=did, has_drift=True,
            fields=[DriftField(facet="f", path="p", expected="a", actual="b")],
        ))

    # Accept the latest observation → in-sync (field_count 0).
    _seed_drift("dev-latest")
    assert store.get_last_signature("dev-latest")["field_count"] == 1
    operations.refresh_drift_after_accept("dev-latest", "sha1", "sha1")
    assert store.get_last_signature("dev-latest")["field_count"] == 0

    # Accept an older/specific commit (target != latest) → cache cleared.
    _seed_drift("dev-old")
    operations.refresh_drift_after_accept("dev-old", "older-sha", "latest-sha")
    assert store.get_last_signature("dev-old") is None


class TestRequestModels:
    def test_revert_rejects_empty_device_ids(self):
        from pydantic import ValidationError
        from admz.api.routes.snapshot import RevertRequest
        with pytest.raises(ValidationError):
            RevertRequest(device_ids=[])

    def test_revert_accepts_ids_and_note(self):
        from admz.api.routes.snapshot import RevertRequest
        req = RevertRequest(device_ids=["a", "b"], note="rollback")
        assert req.device_ids == ["a", "b"]
        assert req.note == "rollback"

    def test_bulk_accept_rejects_empty_device_ids(self):
        from pydantic import ValidationError
        from admz.api.routes.snapshot import AcceptBaselineBulkRequest
        with pytest.raises(ValidationError):
            AcceptBaselineBulkRequest(device_ids=[])

    def test_bulk_accept_accepts_ids_and_note(self):
        from admz.api.routes.snapshot import AcceptBaselineBulkRequest
        req = AcceptBaselineBulkRequest(device_ids=["a"], note="fw")
        assert req.device_ids == ["a"]
        assert req.note == "fw"


# ---------------------------------------------------------------------------
# Auth: anonymous is refused (valid body, so we reach the auth gate)
# ---------------------------------------------------------------------------

class TestAnonymousRefused:
    def test_anonymous_revert_403(self, client):
        r = client.post("/api/snapshot/revert", json={"device_ids": ["x"]})
        assert r.status_code == 403

    def test_anonymous_bulk_accept_403(self, client):
        r = client.post(
            "/api/snapshot/accept-baseline-bulk", json={"device_ids": ["x"]}
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Bulk accept-baseline — combined commit + per-device BASELINE.yaml
# ---------------------------------------------------------------------------

class TestBulkAccept:
    def test_accept_two_devices_one_commit(self, client):
        ctx = _ctx()
        ctx.registry.add_device("cam-a", {"host": "192.0.2.1"})
        ctx.registry.add_device("cam-b", {"host": "192.0.2.2"})
        ctx.git_repo.write_facet("cam-a", "image", {"I0.Resolution": "1920x1080"})
        sha_a = ctx.git_repo.commit_snapshot("cam-a", message="Audit: cam-a", auto_push=False)
        ctx.registry.set_config_pointers("cam-a", latest_observed_sha=sha_a)
        ctx.git_repo.write_facet("cam-b", "image", {"I0.Resolution": "1280x720"})
        sha_b = ctx.git_repo.commit_snapshot("cam-b", message="Audit: cam-b", auto_push=False)
        ctx.registry.set_config_pointers("cam-b", latest_observed_sha=sha_b)

        with _with_admin():
            r = client.post(
                "/api/snapshot/accept-baseline-bulk",
                json={"device_ids": ["cam-a", "cam-b"], "note": "firmware bump"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert {a["device_id"] for a in body["accepted"]} == {"cam-a", "cam-b"}
        assert body["commit"]  # one combined commit sha

        # Both baselines moved to their latest observation.
        assert ctx.registry.get_device_info("cam-a")["baseline_sha"] == sha_a
        assert ctx.registry.get_device_info("cam-b")["baseline_sha"] == sha_b

        # Each device got a BASELINE.yaml note; the HEAD commit covers both.
        for did, sha in [("cam-a", sha_a), ("cam-b", sha_b)]:
            p = ctx.git_repo.device_path(did) / "BASELINE.yaml"
            assert p.exists()
            data = yaml.safe_load(p.read_text())
            assert data["note"] == "firmware bump"
            assert data["baseline_sha"] == sha

        head = ctx.git_repo.log(max_count=1)[0]["message"]
        assert "Accept baseline: 2 devices" in head
        assert "firmware bump" in head

    def test_accept_skips_unknown_and_unobserved(self, client):
        ctx = _ctx()
        ctx.registry.add_device("cam-noobs", {"host": "192.0.2.3"})  # no observation
        with _with_admin():
            r = client.post(
                "/api/snapshot/accept-baseline-bulk",
                json={"device_ids": ["ghost", "cam-noobs"]},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["accepted"] == []
        reasons = {s["device_id"]: s["reason"] for s in body["skipped"]}
        assert reasons["ghost"] == "not-found"
        assert reasons["cam-noobs"] == "no-observation"
        # No note + nothing committable → no combined commit.
        assert body["commit"] is None

    def test_accept_refreshes_drift_cache_to_in_sync(self, client):
        """After bulk accept, the cached drift signature is in-sync — no
        manual Check drift needed for the UI to stop showing 'drifted'."""
        from admz.snapshot import drift_alerts as da
        from admz.snapshot.models import DriftField, DriftReport

        ctx = _ctx()
        ctx.registry.add_device("cam-d", {"host": "192.0.2.7"})
        ctx.git_repo.write_facet("cam-d", "image", {"I0.Resolution": "1920x1080"})
        sha = ctx.git_repo.commit_snapshot("cam-d", message="Audit: cam-d", auto_push=False)
        ctx.registry.set_config_pointers(
            "cam-d", baseline_sha="oldbaseline", latest_observed_sha=sha
        )
        # Seed a drifted signature, as a prior Check drift would have left.
        da.drift_alerts.process_report(DriftReport(
            device_id="cam-d", has_drift=True,
            fields=[DriftField(facet="image", path="I0.Resolution",
                               expected="640x480", actual="1920x1080")],
        ))
        assert da.drift_alerts.get_last_signature("cam-d")["field_count"] == 1

        with _with_admin():
            r = client.post(
                "/api/snapshot/accept-baseline-bulk", json={"device_ids": ["cam-d"]}
            )
        assert r.status_code == 200
        # Cache now reads in-sync, and a "cleared" transition was logged.
        assert da.drift_alerts.get_last_signature("cam-d")["field_count"] == 0
        assert da.drift_alerts.list_alerts(device_id="cam-d", transitions=["cleared"])

    def test_accept_no_note_moves_pointer_without_commit(self, client):
        ctx = _ctx()
        ctx.registry.add_device("cam-c", {"host": "192.0.2.4"})
        ctx.git_repo.write_facet("cam-c", "image", {"I0.Resolution": "800x600"})
        sha = ctx.git_repo.commit_snapshot("cam-c", message="Audit: cam-c", auto_push=False)
        ctx.registry.set_config_pointers("cam-c", latest_observed_sha=sha)
        head_before = ctx.git_repo.log(max_count=1)[0]["sha"]

        with _with_admin():
            r = client.post(
                "/api/snapshot/accept-baseline-bulk",
                json={"device_ids": ["cam-c"]},  # no note
            )
        assert r.status_code == 200
        body = r.json()
        assert body["commit"] is None  # pointer move only, no git churn
        assert ctx.registry.get_device_info("cam-c")["baseline_sha"] == sha
        # HEAD unchanged — no BASELINE.yaml commit when there's no note.
        assert ctx.git_repo.log(max_count=1)[0]["sha"] == head_before


# ---------------------------------------------------------------------------
# Bulk + single revert — one combined gated plan → confirm_url
# ---------------------------------------------------------------------------

class TestRevert:
    @staticmethod
    def _fake_drift(*facet_path_pairs):
        """An async check_drift stub returning a report with the given
        (facet, path) drifted fields (baseline 'old' -> live 'new')."""
        from admz.snapshot.models import DriftField, DriftReport

        async def _check(did, *a, **k):
            return DriftReport(
                device_id=did, has_drift=True,
                fields=[DriftField(facet=f, path=p, expected="old", actual="new")
                        for f, p in facet_path_pairs],
            )
        return _check

    def test_revert_many_builds_single_gated_plan(self, client, monkeypatch):
        ctx = _ctx()
        ctx.registry.add_device("cam-a", {"host": "192.0.2.1"})
        ctx.registry.add_device("cam-b", {"host": "192.0.2.2"})
        # Targeted revert checks drift, then writes back only the drifted
        # fields. Stub the probe; the real build_targeted_revert_plan maps the
        # image field to root.Image.I0.Resolution.
        monkeypatch.setattr(ctx.drift_detector, "check_drift",
                            self._fake_drift(("image", "I0.Resolution")))

        with _with_admin():
            r = client.post(
                "/api/snapshot/revert",
                json={"device_ids": ["cam-a", "cam-b"], "note": "rollback"},
            )
        assert r.status_code == 200
        body = r.json()
        # Service-affecting plan → deterministic widget gate (ADR-0034).
        assert body.get("blocked") is True
        assert body.get("confirm_url", "").startswith("/confirm/")

    def test_revert_no_baseline_returns_message(self, client):
        ctx = _ctx()
        ctx.registry.add_device("cam-empty", {"host": "192.0.2.9"})
        with _with_admin():
            r = client.post(
                "/api/snapshot/revert", json={"device_ids": ["cam-empty"]}
            )
        assert r.status_code == 200
        body = r.json()
        assert "message" in body
        assert body.get("confirm_url") is None

    def test_revert_skips_missing_device(self, client, monkeypatch):
        ctx = _ctx()
        ctx.registry.add_device("cam-a", {"host": "192.0.2.1"})
        monkeypatch.setattr(ctx.drift_detector, "check_drift",
                            self._fake_drift(("image", "I0.Resolution")))

        with _with_admin():
            r = client.post(
                "/api/snapshot/revert",
                json={"device_ids": ["cam-a", "ghost"]},
            )
        assert r.status_code == 200
        body = r.json()
        assert body.get("blocked") is True
        assert body.get("missing") == ["ghost"]

    def test_revert_field_selection_filters_to_chosen(self, client, monkeypatch):
        """With ``fields``, only the chosen (facet, path) pairs reach the plan
        builder — the rest of the drift is left untouched."""
        ctx = _ctx()
        ctx.registry.add_device("cam-a", {"host": "192.0.2.1"})
        # Two drifted fields; the operator picks one.
        monkeypatch.setattr(
            ctx.drift_detector, "check_drift",
            self._fake_drift(("image", "I0.Resolution"),
                             ("audio", "Source.A0.InputGain")),
        )
        captured = {}
        real_build = ctx.restore_builder.build_targeted_revert_plan

        def spy(did, fields, *a, **k):
            captured["fields"] = list(fields)
            return real_build(did, fields, *a, **k)
        monkeypatch.setattr(ctx.restore_builder,
                            "build_targeted_revert_plan", spy)

        with _with_admin():
            r = client.post("/api/snapshot/revert", json={
                "device_ids": ["cam-a"],
                "fields": [{"device_id": "cam-a", "facet": "audio",
                            "path": "Source.A0.InputGain"}],
            })
        assert r.status_code == 200
        assert r.json().get("blocked") is True
        # Only the selected field was handed to the builder.
        assert [(f.facet, f.path) for f in captured["fields"]] == \
            [("audio", "Source.A0.InputGain")]

    def test_revert_field_selection_none_chosen_is_noop(self, client, monkeypatch):
        """An empty ``fields`` list selects nothing → nothing to revert."""
        ctx = _ctx()
        ctx.registry.add_device("cam-a", {"host": "192.0.2.1"})
        monkeypatch.setattr(ctx.drift_detector, "check_drift",
                            self._fake_drift(("image", "I0.Resolution")))
        with _with_admin():
            r = client.post("/api/snapshot/revert",
                            json={"device_ids": ["cam-a"], "fields": []})
        assert r.status_code == 200
        body = r.json()
        assert body.get("confirm_url") is None
        assert "message" in body


class TestDriftRevertableAnnotation:
    """``GET /api/snapshot/drift?device_id=`` tags each drifted field with
    ``revertable`` (+ a reason) so the UI can render accurate per-row
    checkboxes — using the same facet.revert_param the plan builder uses."""

    def test_drift_marks_each_field_revertable(self, client, monkeypatch):
        ctx = _ctx()
        ctx.registry.add_device("cam-a", {"host": "192.0.2.1"})
        from admz.snapshot.models import DriftField, DriftReport

        async def _check(did, *a, **k):
            return DriftReport(device_id=did, has_drift=True, fields=[
                DriftField(facet="image", path="I0.Resolution",
                           expected="1920x1080", actual="1280x720"),
                DriftField(facet="other", path="root.Big_aoa_counter.Label",
                           expected="My count", actual="Bijan's"),
                DriftField(facet="other", path="root.SNMP.V1.WriteCommunity",
                           expected="private", actual="public"),
                DriftField(facet="audio", path="Source.A0.NewKey",
                           expected="<missing>", actual="x"),
            ])
        monkeypatch.setattr(ctx.drift_detector, "check_drift", _check)

        r = client.get("/api/snapshot/drift?device_id=cam-a")
        assert r.status_code == 200
        by_path = {f["path"]: f for f in r.json()["drifted_fields"]}
        # Named facet + catch-all both revertable.
        assert by_path["I0.Resolution"]["revertable"] is True
        assert by_path["root.Big_aoa_counter.Label"]["revertable"] is True
        # Secret catch-all key → not revertable (read-only).
        snmp = by_path["root.SNMP.V1.WriteCommunity"]
        assert snmp["revertable"] is False
        assert snmp["revert_skip_reason"] == "read-only"
        # Appeared (no baseline value) → not revertable (added).
        newk = by_path["Source.A0.NewKey"]
        assert newk["revertable"] is False
        assert newk["revert_skip_reason"] == "added"
