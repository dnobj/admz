"""ADR-0072 §2-3 — the discovery widget's routes.

``GET /api/discovery/scans/{id}`` shows a scan to the principal who ran it,
with live registration state and what an add will take. ``POST …/add`` opens
ONE approval for the selected devices — same-origin only, all-or-nothing,
built from the scan row — and never approves; the widget sends the token to
the existing ``POST /api/chat/confirm/{token}``.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from admz.discovery import candidates
from admz.discovery.models import DiscoveredDevice
from admz.rate_limit import rate_limiter as global_limiter

A = "E82725315CDF"
B = "E827250904B4"
C = "B8A44FB892AE"
SAME_ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    global_limiter.reset()
    global_limiter.configure("confirm", capacity=100, refill_per_s=100)

    import admz.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_ACTIVE_BACKEND", None)

    from admz.api.main import app

    try:
        with TestClient(app) as c:
            yield c
    finally:
        global_limiter.configure("confirm", capacity=10, refill_per_s=1.0 / 6.0)
        global_limiter.reset()
        from admz.api.routes.confirm import _PW_ATTEMPTS
        _PW_ATTEMPTS.clear()


def _record(mac, ip, *, axis=True, factory_default=False):
    return candidates.scan_record(DiscoveredDevice(
        ip_address=ip, mac_address=mac, model="AXIS P3408-VE", is_axis=axis,
        factory_default=factory_default))


def _scan(principal="anonymous", *, age=0.0, devices=None):
    from admz.discovery.scan_store import discovery_scans

    devices = devices if devices is not None else [
        _record("E8:27:25:31:5C:DF", "192.0.2.41"),
        _record("E8:27:25:09:04:B4", "192.0.2.60", factory_default=True),
        _record("B8:A4:4F:B8:92:AE", "192.0.2.5"),
        _record("5C:35:FC:51:EA:C0", "192.0.2.1", axis=False),
    ]
    return discovery_scans.save_scan(
        principal=principal, devices=devices, subnet="192.0.2.0/24",
        now=time.time() - age)


def _registry():
    from admz.api.context import get_context
    return get_context().registry


def _session_count():
    from admz.api.confirm_store import confirm_store
    conn = confirm_store._connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM confirm_sessions").fetchone()[0]
    finally:
        conn.close()


def _add(client, scan_id, ids, headers=SAME_ORIGIN, **extra):
    return client.post(f"/api/discovery/scans/{scan_id}/add",
                       json={"device_ids": ids, **extra}, headers=headers)


class TestRead:
    def test_the_scan_comes_back_with_live_registration(self, client):
        scan = _scan()
        _registry().add_device(C, {"host": "192.0.2.5", "mac_address": C})

        body = client.get(f"/api/discovery/scans/{scan.scan_id}").json()
        by_id = {d["device_id"] or d["ip_address"]: d for d in body["devices"]}
        assert body["count"] == 4
        assert (body["axis_count"], body["new_axis_count"]) == (3, 2)
        assert by_id[C]["registered_device_id"] == C
        assert by_id[C]["add_blocker"] == candidates.BLOCK_REGISTERED
        assert by_id[A]["registered_device_id"] is None
        assert by_id[A]["add_blocker"] == ""
        assert by_id["5C35FC51EAC0"]["add_blocker"] == candidates.BLOCK_NOT_AXIS
        assert "registry_info" not in by_id[A]

    def test_another_principals_scan_is_not_found(self, client):
        scan = _scan(principal="bob")
        assert client.get(f"/api/discovery/scans/{scan.scan_id}").status_code == 404
        assert client.get("/api/discovery/scans/does-not-exist").status_code == 404

    def test_the_add_policy_by_default(self, client):
        scan = _scan()
        policy = client.get(f"/api/discovery/scans/{scan.scan_id}").json()["add_policy"]
        assert policy["confirmation_level"] == "url_only"
        assert policy["needs_password"] is False
        assert policy["may_approve"] is True
        assert policy["stale"] is False
        assert policy["max_batch"] == candidates.MAX_ADD_BATCH
        assert "fleet root password" in policy["consequence"]

    def test_a_raised_level_asks_for_the_password(self, client):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs

        fs.set("confirm_level_service-affecting", "url_and_password")
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))
        try:
            scan = _scan()
            policy = client.get(f"/api/discovery/scans/{scan.scan_id}").json()["add_policy"]
            assert policy["confirmation_level"] == "url_and_password"
            assert policy["needs_password"] is True
        finally:
            fs.delete("confirm_level_service-affecting")
            fs.delete("confirm_password_hash")

    def test_may_approve_is_the_gates_own_decision(self, client, monkeypatch):
        monkeypatch.setattr("admz.authz.principal_can_approve",
                            lambda p, **kw: (False, "not in Administrators"))
        scan = _scan()
        policy = client.get(f"/api/discovery/scans/{scan.scan_id}").json()["add_policy"]
        assert policy["may_approve"] is False
        assert policy["not_approver_reason"] == "not in Administrators"

    def test_an_old_scan_reads_as_stale(self, client):
        scan = _scan(age=candidates.MAX_SCAN_AGE_SECONDS + 60)
        policy = client.get(f"/api/discovery/scans/{scan.scan_id}").json()["add_policy"]
        assert policy["stale"] is True


class TestAddIsRefusedBeforeAnythingIsCreated:
    def test_no_origin_is_refused(self, client):
        scan = _scan()
        before = _session_count()
        assert _add(client, scan.scan_id, [A], headers={}).status_code == 403
        assert _session_count() == before

    def test_a_foreign_origin_is_refused(self, client):
        scan = _scan()
        before = _session_count()
        r = _add(client, scan.scan_id, [A], headers={"Origin": "http://evil.example"})
        assert r.status_code == 403
        assert _session_count() == before

    def test_another_principals_scan(self, client):
        scan = _scan(principal="bob")
        assert _add(client, scan.scan_id, [A]).status_code == 404

    def test_a_stale_scan(self, client):
        scan = _scan(age=candidates.MAX_SCAN_AGE_SECONDS + 60)
        before = _session_count()
        r = _add(client, scan.scan_id, [A])
        assert r.status_code == 409
        assert "new scan" in r.json()["detail"]
        assert _session_count() == before

    def test_one_unaddable_device_rejects_the_batch(self, client):
        scan = _scan()
        _registry().add_device(C, {"host": "192.0.2.5", "mac_address": C})
        before = _session_count()
        r = _add(client, scan.scan_id, [A, B, C])
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert detail["rejected"] == [
            {"device_id": C, "reason": candidates.BLOCK_REGISTERED}]
        assert _session_count() == before

    def test_an_id_not_in_the_scan(self, client):
        scan = _scan()
        r = _add(client, scan.scan_id, [A, "ACCC8EE6E7EE"])
        assert r.status_code == 400
        assert r.json()["detail"]["rejected"][0]["reason"] == "not in this scan"

    def test_a_non_device_id(self, client):
        scan = _scan()
        assert _add(client, scan.scan_id, ["<script>"]).status_code == 400
        assert _add(client, scan.scan_id, []).status_code == 400

    def test_more_than_the_batch_cap(self, client):
        many = [_record(f"00:40:8C:00:00:{i:02X}", f"192.0.2.{100 + i}")
                for i in range(candidates.MAX_ADD_BATCH + 1)]
        scan = _scan(devices=many)
        ids = [r["device_id"] for r in many]
        r = _add(client, scan.scan_id, ids)
        assert r.status_code == 400
        assert str(candidates.MAX_ADD_BATCH) in r.json()["detail"]


class TestAddOpensOneSession:
    def _session(self, token):
        from admz.api.confirm_store import confirm_store
        return confirm_store.get_session(token)

    def test_the_session_is_built_from_the_scan_not_the_body(self, client):
        scan = _scan()
        r = _add(client, scan.scan_id, [A, B],
                 devices=[{"device_id": A, "host": "198.51.100.66"}])
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "pending"
        assert body["confirm_url"] == f"/confirm/{body['token']}"

        session = self._session(body["token"])
        action = session.action
        assert action["action"] == "add_discovered_devices"
        assert action["device_ids"] == [A, B]
        assert [d["host"] for d in action["devices"]] == ["192.0.2.41", "192.0.2.60"]
        assert "198.51.100.66" not in json.dumps(action)
        assert session.device_id == "multiple"
        assert session.risk_level == "service-affecting"
        assert session.confirmation_level == "url_only"
        assert A in session.danger_description and B in session.danger_description
        assert body["danger_description"] == session.danger_description

    def test_one_device_names_itself(self, client):
        scan = _scan()
        body = _add(client, scan.scan_id, [A.lower()]).json()
        assert self._session(body["token"]).device_id == A

    def test_duplicates_collapse(self, client):
        scan = _scan()
        body = _add(client, scan.scan_id, [A, "e8:27:25:31:5c:df"]).json()
        assert self._session(body["token"]).action["device_ids"] == [A]

    def test_the_token_is_linked_to_the_scans_conversation(self, client):
        from admz.chatbot.sessions import chat_sessions
        from admz.discovery.scan_store import discovery_scans

        chat_sessions.append_turn("anonymous", "find my cameras", "Found 4.")
        conv = chat_sessions.get_active_conversation("anonymous")
        scan = _scan()
        assert discovery_scans.bind_conversation(scan.scan_id, "anonymous", conv)

        token = _add(client, scan.scan_id, [A]).json()["token"]
        link = chat_sessions.pop_action_link(token)
        assert link["conversation_id"] == conv
        assert link["kind"] == "confirm"

    def test_the_request_is_audited(self, client):
        from admz.audit import audit_log

        scan = _scan()
        _add(client, scan.scan_id, [A, B])
        rows = audit_log.search(action="discovery.add_requested", limit=5)
        assert rows and rows[0].details["device_ids"] == f"{A},{B}"
        assert rows[0].details["count"] == 2


class TestTheWholeClick:
    """Create, then approve through the existing chat confirm route — the two
    requests the widget sends for one click."""

    @pytest.fixture
    def devices_answer(self, monkeypatch):
        serials = {"192.0.2.41": A, "192.0.2.60": B}

        async def _read(catalog, executor, host, **_kw):
            return serials.get(host)

        async def _onboard(**kw):
            return {"status": "provisioned", "device_id": kw["device_id"]}

        monkeypatch.setattr("admz.discovery.identity.read_unrestricted_serial", _read)
        monkeypatch.setattr("admz.onboarding.onboard_device_credentials", _onboard)
        return serials

    def test_one_click_adds_both_and_leaves_a_trail(self, client, devices_answer):
        from admz.audit import audit_log
        from admz.chatbot.sessions import chat_sessions
        from admz.discovery.scan_store import discovery_scans

        chat_sessions.append_turn("anonymous", "find my cameras", "Found 4.")
        conv = chat_sessions.get_active_conversation("anonymous")
        scan = _scan()
        discovery_scans.bind_conversation(scan.scan_id, "anonymous", conv)

        token = _add(client, scan.scan_id, [A, B]).json()["token"]
        r = client.post(f"/api/chat/confirm/{token}", data={})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "completed"
        outcome = body["outcome"]
        assert outcome["success"] is True
        assert outcome["added"] == [A, B]

        registry = _registry()
        assert registry.device_exists(A) and registry.device_exists(B)
        assert registry.get_device_info(A)["host"] == "192.0.2.41"

        row = audit_log.search(action="confirm.approve", limit=1)[0]
        assert row.details["added_devices"] == f"{A},{B}"
        assert row.details["provisioned_devices"] == f"{A},{B}"

        note = chat_sessions.get_messages("anonymous", conv)[-1]
        assert note["role"] == "event"
        assert "on 2 devices" in note["text"]
        assert "add_discovered_devices" in note["text"]

        # A second click on the same token finds nothing to approve.
        again = client.post(f"/api/chat/confirm/{token}", data={})
        assert again.status_code == 410

    def test_a_wrong_password_leaves_the_same_token_retryable(
        self, client, devices_answer
    ):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs

        fs.set("confirm_level_service-affecting", "url_and_password")
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))
        try:
            scan = _scan()
            token = _add(client, scan.scan_id, [A]).json()["token"]
            wrong = client.post(f"/api/chat/confirm/{token}",
                                data={"confirm_password": "nope"})
            assert wrong.status_code == 403
            right = client.post(f"/api/chat/confirm/{token}",
                                data={"confirm_password": "hunter2"})
            assert right.json()["status"] == "completed"
        finally:
            fs.delete("confirm_level_service-affecting")
            fs.delete("confirm_password_hash")
