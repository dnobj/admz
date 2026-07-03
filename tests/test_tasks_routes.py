"""Tests for the unified /api/tasks REST surface (ADR-0037)."""

from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


@pytest.fixture
def client(isolate, tmp_path):
    from admz.api.main import app
    with TestClient(app) as c:
        repo = str(tmp_path / "config-repo")
        for k, v in [("user.email", "t@t.com"), ("user.name", "T"),
                     ("commit.gpgsign", "false")]:
            subprocess.run(["git", "config", k, v], cwd=repo, check=True)
        yield c


def _register_device(client, device_id="cam-01"):
    client.post("/api/devices", json={"device_id": device_id, "host": "10.0.0.9",
                                      "nickname": device_id})


@pytest.fixture
def as_console_operator(monkeypatch):
    """Task writes gate for non-interactive principals; TestTasksRest
    exercises the direct (console-operator) path. The gate itself is
    covered by TestTaskWriteGate with the real check."""
    import admz.tasks.gated as gated
    monkeypatch.setattr(gated, "is_interactive", lambda p: True)


@pytest.mark.usefixtures("as_console_operator")
class TestTasksRest:
    def test_action_types(self, client):
        r = client.get("/api/tasks/action-types")
        assert r.status_code == 200
        body = r.json()
        assert {"snapshot", "drift_audit", "reprovision"} <= set(body["action_types"])
        assert "on_needs_setup" in body["events"]

    def test_list_empty(self, client):
        r = client.get("/api/tasks")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_create_and_list_schedule(self, client):
        r = client.post("/api/tasks", json={
            "trigger_kind": "schedule", "action_type": "snapshot",
            "description": "Nightly", "interval": "1d", "tag_filter": "lab",
        })
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        assert r.json()["trigger_kind"] == "schedule"
        assert r.json()["interval_seconds"] == 86400

        lst = client.get("/api/tasks").json()
        assert lst["count"] == 1
        assert lst["tasks"][0]["id"] == tid
        assert lst["tasks"][0]["action_type"] == "snapshot"

        one = client.get(f"/api/tasks/{tid}")
        assert one.status_code == 200 and one.json()["tag_filter"] == "lab"

    def test_create_schedule_bad_action(self, client):
        r = client.post("/api/tasks", json={
            "trigger_kind": "schedule", "action_type": "nope", "interval": "1h",
        })
        assert r.status_code == 400

    def test_create_schedule_needs_interval(self, client):
        r = client.post("/api/tasks", json={
            "trigger_kind": "schedule", "action_type": "snapshot",
        })
        assert r.status_code == 400

    def test_update_and_delete_schedule(self, client):
        tid = client.post("/api/tasks", json={
            "trigger_kind": "schedule", "action_type": "snapshot",
            "interval": "1h", "task_id": "sched-1",
        }).json()["id"]
        r = client.patch(f"/api/tasks/{tid}", json={"enabled": False})
        assert r.status_code == 200 and r.json()["enabled"] is False
        d = client.delete(f"/api/tasks/{tid}")
        assert d.status_code == 200 and d.json()["success"] is True
        assert client.get(f"/api/tasks/{tid}").status_code == 404

    def test_detection_requires_auth(self, client):
        # The test app runs ADMZ_AUTH_BACKEND=none -> anonymous principal, which
        # may not arm a (destructive) detection task.
        r = client.post("/api/tasks", json={
            "trigger_kind": "detection", "action_type": "reprovision",
            "event": "on_needs_setup", "device_id": "cam-01",
        })
        assert r.status_code in (401, 403), r.text

    def test_unknown_kind(self, client):
        r = client.post("/api/tasks", json={
            "trigger_kind": "whatever", "action_type": "snapshot", "interval": "1h",
        })
        assert r.status_code == 400

    def test_filter_by_kind(self, client):
        client.post("/api/tasks", json={"trigger_kind": "schedule",
                                        "action_type": "snapshot", "interval": "1h"})
        assert client.get("/api/tasks?kind=detection").json()["count"] == 0
        assert client.get("/api/tasks?kind=schedule").json()["count"] == 1


class TestTaskWriteGate:
    """Non-interactive principals (the test app's anonymous default) don't
    write tasks directly — they get the confirmation widget, and the task
    exists only after the card is approved."""

    def test_create_blocks_then_approval_creates(self, client):
        r = client.post("/api/tasks", json={
            "trigger_kind": "schedule", "action_type": "drift_audit",
            "description": "gated", "interval": "2h", "tag_filter": "lab",
        })
        assert r.status_code == 200, r.text
        env = r.json()
        assert env["blocked"] is True
        assert env["confirm_url"].startswith("/confirm/")
        assert "RECURRING" in env["reason"]
        # nothing written yet
        assert client.get("/api/tasks").json()["count"] == 0

        # approve via the same endpoint the chat widget uses
        token = env["confirm_url"].rsplit("/", 1)[1]
        a = client.post(f"/api/chat/confirm/{token}")
        assert a.status_code == 200, a.text
        assert a.json()["status"] == "completed"
        assert a.json()["outcome"]["success"] is True, a.text

        lst = client.get("/api/tasks").json()
        assert lst["count"] == 1
        assert lst["tasks"][0]["action_type"] == "drift_audit"

    def test_update_blocks_then_approval_applies(self, client, monkeypatch):
        # seed a schedule as the console operator…
        import admz.tasks.gated as gated
        real = gated.is_interactive
        monkeypatch.setattr(gated, "is_interactive", lambda p: True)
        tid = client.post("/api/tasks", json={
            "trigger_kind": "schedule", "action_type": "snapshot",
            "interval": "1h", "task_id": "sched-g",
        }).json()["id"]
        monkeypatch.setattr(gated, "is_interactive", real)

        # …then a non-interactive update must gate
        r = client.patch(f"/api/tasks/{tid}", json={"interval": "6h"})
        env = r.json()
        assert env["blocked"] is True
        assert client.get(f"/api/tasks/{tid}").json()["interval_seconds"] == 3600

        token = env["confirm_url"].rsplit("/", 1)[1]
        a = client.post(f"/api/chat/confirm/{token}")
        assert a.json()["outcome"]["success"] is True, a.text
        assert client.get(f"/api/tasks/{tid}").json()["interval_seconds"] == 21600

    def test_denied_card_writes_nothing(self, client):
        env = client.post("/api/tasks", json={
            "trigger_kind": "schedule", "action_type": "snapshot",
            "interval": "1h",
        }).json()
        token = env["confirm_url"].rsplit("/", 1)[1]
        d = client.post(f"/api/chat/confirm/{token}/deny")
        assert d.status_code == 200
        assert client.get("/api/tasks").json()["count"] == 0

    def test_bad_spec_fails_fast_without_session(self, client):
        r = client.post("/api/tasks", json={
            "trigger_kind": "schedule", "action_type": "nope", "interval": "1h",
        })
        assert r.status_code == 400  # rejected before any card is created
