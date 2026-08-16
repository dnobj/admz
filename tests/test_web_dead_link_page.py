"""The shared dead-link page (capture_expired.html) must say what the route
that rendered it meant.

capture.py, rule_capture.py and confirm.py all render ``capture_expired.html``
for an expired / used / denied token, and every caller passes ``title`` — but
the template hard-coded its own ``<h1>Link Expired</h1>`` / ``<title>`` and a
body sentence about "this credential capture link". So a *denied
confirmation* (confirm.py passes ``title="Request Denied"``) rendered as
"Link Expired — this credential capture link has expired", which is wrong on
both counts: it was not a capture link and it did not expire.

These render through the real routes (as tests/test_return_to_chat_links.py
does), so a renamed context variable would fail them the way it would fail
in production.
"""

from __future__ import annotations

import re

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


@pytest.fixture
def client(isolate_admz_dirs, tmp_path):
    from admz.api.main import app

    with TestClient(app) as c:
        import subprocess
        repo = str(tmp_path / "config-repo")
        for k, v in [("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")]:
            subprocess.run(["git", "config", k, v], cwd=repo, check=True)

        from admz.factory import create_device_registry
        reg = create_device_registry()
        reg.add_device("dev", {"host": "192.0.2.10", "model": "M-test"})
        yield c


def _h1(html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    assert m, "no <h1> in page"
    return re.sub(r"\s+", " ", m.group(1)).strip()


def _tab_title(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    assert m, "no <title> in page"
    return re.sub(r"\s+", " ", m.group(1)).strip()


def test_denied_confirmation_says_denied_not_expired(client):
    """confirm.py passes title="Request Denied" for a declined session; the
    page must show it in the heading and the tab, and must not claim the
    link expired or that it was a credential-capture link."""
    from admz.api.confirm_store import confirm_store

    session = confirm_store.create_session(
        device_id="dev", operation_id="restart.cgi:restart", family="vapix",
        params={}, risk_level="dangerous", confirmation_level="url_only",
    )
    assert confirm_store.deny_session(session.token, denied_by="test") is True

    r = client.get(f"/confirm/{session.token}")
    assert r.status_code == 410
    assert _h1(r.text) == "Request Denied"
    assert _tab_title(r.text).startswith("Request Denied")
    assert "Link Expired" not in r.text
    assert "credential capture link" not in r.text
    assert 'href="/chat"' in r.text  # #340's way out is still there


def test_unknown_confirm_token_still_says_link_expired(client):
    r = client.get("/confirm/no-such-token-at-all")
    assert r.status_code == 410
    assert _h1(r.text) == "Link Expired"
    assert "credential capture link" not in r.text


def test_unknown_capture_token_still_says_link_expired(client):
    """The capture side keeps its wording — only the surface-specific claim
    ("credential capture link") is gone, since confirm renders this too."""
    r = client.get("/capture/no-such-token-at-all")
    assert r.status_code == 410
    assert _h1(r.text) == "Link Expired"
    assert _tab_title(r.text).startswith("Link Expired")
    assert "credential capture link" not in r.text
