"""HTTP-level tests for #340: rehydrating pinned confirm/capture widgets
after a page reload.

Root cause (from the issue): approval/capture widgets are built ONLY from
a live turn's structured tool_result (chat.js's own deliberate rule, so the
model can't fabricate one by typing a URL). restoreActiveConversation()
rebuilds the transcript on load but no widgets, and returning from
/capture/{token} or /confirm/{token} is a full-page navigation — so a
reload, a second tab, or returning from either page silently drops every
pinned action, including ones the operator never got to. GET
/api/chat/pending-actions is the new rehydration source chat.js calls on
load.

That endpoint is also a token-disclosure surface — a confirm/capture token
IS the authorization to act (ADR-0009 / ADR-0034) — so these tests pin the
SECURITY shape as hard as the rehydration behavior itself:
  - anonymous/unauthenticated callers get nothing (403), even under the
    ADMZ_AUTH_BACKEND=none default where every caller shares one synthetic
    "anonymous" identity
  - scoped to the calling principal via chat_action_links — a DIFFERENT
    principal's pending session must never appear
  - a pending session rehydrates; a completed or expired one must not
    (both directions, per the brief)
"""

from __future__ import annotations

import subprocess
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolate_admz_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_TRUSTED_PROXIES", "testclient,127.0.0.1,::1")


def _make_client(monkeypatch, tmp_path, backend="none"):
    """Build a TestClient under the requested auth backend, mirroring
    test_auth_integration.py's helper — module-level auth state must be
    reset so the new backend env is actually honored."""
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", backend)
    import admz.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_ACTIVE_BACKEND", None)

    from admz.api.main import app
    client = TestClient(app)
    client.__enter__()
    repo = str(tmp_path / "config-repo")
    for k, v in [("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")]:
        subprocess.run(["git", "config", k, v], cwd=repo, check=True)
    return client


def _mint_key(tmp_path, display_name="alice-bot"):
    from admz.api_keys import ApiKeyStore
    store = ApiKeyStore(db_path=str(tmp_path / "admz.db"))
    return store.create(display_name=display_name, created_by="setup")


def _principal_name(display_name):
    """admz.auth.ApiKeyAuth resolves Principal.name to ``api-key:<display_name>``,
    not the bare display name (confirmed by reading ApiKeyAuth.authenticate) —
    chat_action_links must be linked under that exact string, since that's
    what get_current_principal hands the endpoint."""
    return f"api-key:{display_name}"


def _auth_headers(created):
    return {"Authorization": "Bearer " + created.plaintext}


def _link(principal, kind, token, conv="conv-1"):
    from admz.chatbot.sessions import chat_sessions
    chat_sessions.link_action(token, principal, conv, kind, label="test")


def _seed_confirm(level="url_only"):
    from admz.api.confirm_store import confirm_store
    return confirm_store.create_session(
        device_id="dev", operation_id="test:op", family="vapix",
        params={}, risk_level="dangerous", confirmation_level=level,
    )


def _seed_capture(ttl=600.0):
    from admz.api.capture import capture_store
    return capture_store.create_session(device_id="dev", ttl=ttl)


class TestAnonymousBlocked:
    def test_anonymous_gets_403(self, monkeypatch, tmp_path):
        """The ADMZ_AUTH_BACKEND=none default — every caller shares the
        SAME synthetic 'anonymous' principal, so this must be a hard
        refusal, not an empty list that happens to look safe today."""
        client = _make_client(monkeypatch, tmp_path, "none")
        r = client.get("/api/chat/pending-actions")
        assert r.status_code == 403

    def test_anonymous_gets_nothing_even_with_a_linked_session(self, monkeypatch, tmp_path):
        """Positive control for the refusal above: even when a session IS
        linked to the literal 'anonymous' principal (i.e. it was created by
        some OTHER anonymous caller under the shared no-auth identity), a
        request under that same backend must still be refused outright —
        never handed that other caller's token."""
        session = _seed_confirm()
        _link("anonymous", "confirm", session.token)
        client = _make_client(monkeypatch, tmp_path, "none")
        r = client.get("/api/chat/pending-actions")
        assert r.status_code == 403


class TestPendingSessionsRehydrate:
    def test_pending_confirm_session_rehydrates(self, monkeypatch, tmp_path):
        session = _seed_confirm()
        _link(_principal_name("alice-bot"), "confirm", session.token)
        created = _mint_key(tmp_path, "alice-bot")
        client = _make_client(monkeypatch, tmp_path, "api-key")

        r = client.get("/api/chat/pending-actions", headers=_auth_headers(created))
        assert r.status_code == 200
        assert r.json()["pending"] == [{"kind": "confirm", "token": session.token}]

    def test_pending_capture_session_rehydrates(self, monkeypatch, tmp_path):
        session = _seed_capture()
        _link(_principal_name("alice-bot"), "capture", session.token)
        created = _mint_key(tmp_path, "alice-bot")
        client = _make_client(monkeypatch, tmp_path, "api-key")

        r = client.get("/api/chat/pending-actions", headers=_auth_headers(created))
        assert r.status_code == 200
        assert r.json()["pending"] == [{"kind": "capture", "token": session.token}]

    def test_multiple_pending_sessions_all_rehydrate(self, monkeypatch, tmp_path):
        """The operator's actual report: THREE capture cards in one turn."""
        s1, s2, s3 = _seed_capture(), _seed_capture(), _seed_capture()
        for s in (s1, s2, s3):
            _link(_principal_name("alice-bot"), "capture", s.token)
        created = _mint_key(tmp_path, "alice-bot")
        client = _make_client(monkeypatch, tmp_path, "api-key")

        r = client.get("/api/chat/pending-actions", headers=_auth_headers(created))
        tokens = {item["token"] for item in r.json()["pending"]}
        assert tokens == {s1.token, s2.token, s3.token}


class TestBothDirectionsPinned:
    """Pending rehydrates; completed/expired must not — pinned explicitly,
    not just implied by the pending-case tests above."""

    def test_completed_confirm_session_does_not_rehydrate(self, monkeypatch, tmp_path):
        session = _seed_confirm()
        _link(_principal_name("alice-bot"), "confirm", session.token)
        from admz.api.confirm_store import confirm_store
        assert confirm_store.complete_session(session.token) is True

        created = _mint_key(tmp_path, "alice-bot")
        client = _make_client(monkeypatch, tmp_path, "api-key")
        r = client.get("/api/chat/pending-actions", headers=_auth_headers(created))
        assert r.json()["pending"] == []

    def test_completed_capture_session_does_not_rehydrate(self, monkeypatch, tmp_path):
        session = _seed_capture()
        _link(_principal_name("alice-bot"), "capture", session.token)
        from admz.api.capture import capture_store
        assert capture_store.complete_session(session.token) is True

        created = _mint_key(tmp_path, "alice-bot")
        client = _make_client(monkeypatch, tmp_path, "api-key")
        r = client.get("/api/chat/pending-actions", headers=_auth_headers(created))
        assert r.json()["pending"] == []

    def test_expired_confirm_session_does_not_rehydrate(self, monkeypatch, tmp_path):
        """A pending row past its TTL must not come back as a live-looking
        widget — the explicit stale-vs-live requirement from the brief."""
        session = _seed_confirm()
        _link(_principal_name("alice-bot"), "confirm", session.token)
        # Age the row past its TTL directly in the DB (confirm_store has no
        # public "backdate" API, and CONFIRM_TOKEN_TTL_SECONDS is fixed at
        # create_session time) rather than sleeping for real minutes.
        import sqlite3
        from admz.api.confirm_store import confirm_store
        conn = sqlite3.connect(confirm_store._db_path)
        conn.execute("UPDATE confirm_sessions SET ttl=0.01 WHERE token=?", (session.token,))
        conn.commit()
        conn.close()
        time.sleep(0.05)

        created = _mint_key(tmp_path, "alice-bot")
        client = _make_client(monkeypatch, tmp_path, "api-key")
        r = client.get("/api/chat/pending-actions", headers=_auth_headers(created))
        assert r.json()["pending"] == []

    def test_expired_capture_session_does_not_rehydrate(self, monkeypatch, tmp_path):
        session = _seed_capture(ttl=0.01)
        _link(_principal_name("alice-bot"), "capture", session.token)
        time.sleep(0.05)

        created = _mint_key(tmp_path, "alice-bot")
        client = _make_client(monkeypatch, tmp_path, "api-key")
        r = client.get("/api/chat/pending-actions", headers=_auth_headers(created))
        assert r.json()["pending"] == []

    def test_link_to_a_session_that_was_never_created_is_dropped_not_crashed(
        self, monkeypatch, tmp_path
    ):
        """Defensive: a link row whose token has no matching session at all
        (any reason) must be silently skipped, never a 500."""
        _link(_principal_name("alice-bot"), "confirm", "totally-made-up-token")
        created = _mint_key(tmp_path, "alice-bot")
        client = _make_client(monkeypatch, tmp_path, "api-key")
        r = client.get("/api/chat/pending-actions", headers=_auth_headers(created))
        assert r.status_code == 200
        assert r.json()["pending"] == []


class TestScopedToOwningPrincipal:
    def test_a_different_principals_session_is_not_visible(self, monkeypatch, tmp_path):
        """The core ownership pin: bob's pending session must never appear
        in alice's rehydration list, even though both exist in the same
        (shared) confirm_sessions table."""
        bobs_session = _seed_confirm()
        _link(_principal_name("bob-bot"), "confirm", bobs_session.token)

        created = _mint_key(tmp_path, "alice-bot")
        client = _make_client(monkeypatch, tmp_path, "api-key")
        r = client.get("/api/chat/pending-actions", headers=_auth_headers(created))
        assert r.json()["pending"] == []

    def test_each_principal_sees_only_their_own(self, monkeypatch, tmp_path):
        alice_session = _seed_confirm()
        bob_session = _seed_confirm()
        _link(_principal_name("alice-bot"), "confirm", alice_session.token)
        _link(_principal_name("bob-bot"), "confirm", bob_session.token)

        alice_key = _mint_key(tmp_path, "alice-bot")
        client = _make_client(monkeypatch, tmp_path, "api-key")
        r = client.get("/api/chat/pending-actions", headers=_auth_headers(alice_key))
        assert r.json()["pending"] == [{"kind": "confirm", "token": alice_session.token}]
