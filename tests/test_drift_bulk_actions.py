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
    def test_revert_many_builds_single_gated_plan(self, client, monkeypatch):
        ctx = _ctx()
        ctx.registry.add_device("cam-a", {"host": "192.0.2.1"})
        ctx.registry.add_device("cam-b", {"host": "192.0.2.2"})

        def fake_build(did, ref=None, facet_names=None):
            return {
                "steps": [{
                    "operation_id": "param.cgi:update", "device_id": did,
                    "params": {"root.Foo": "1"}, "description": f"Restore {did}",
                    "risk_level": "service-affecting",
                }],
                "warnings": [], "description": f"Restore {did} to baseline",
                "source_ref": "baseline", "on_failure": "stop",
            }
        monkeypatch.setattr(ctx.restore_builder, "build_restore_plan", fake_build)

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

        def fake_build(did, ref=None, facet_names=None):
            return {
                "steps": [{
                    "operation_id": "param.cgi:update", "device_id": did,
                    "params": {"root.Foo": "1"}, "description": f"Restore {did}",
                    "risk_level": "service-affecting",
                }],
                "warnings": [], "description": f"Restore {did}",
                "source_ref": "baseline", "on_failure": "stop",
            }
        monkeypatch.setattr(ctx.restore_builder, "build_restore_plan", fake_build)

        with _with_admin():
            r = client.post(
                "/api/snapshot/revert",
                json={"device_ids": ["cam-a", "ghost"]},
            )
        assert r.status_code == 200
        body = r.json()
        assert body.get("blocked") is True
        assert body.get("missing") == ["ghost"]
