"""Unit tests for the GitHub App backup subsystem (ADR-0045):
JWT signing, installation-token minting + cache, manifest exchange, repo list,
and the encrypted secret store.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from admz.github_app import client as gh_client
from admz.github_app import secrets as gh_secrets


@pytest.fixture(scope="module")
def rsa_pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return pem, key.public_key()


@pytest.fixture(autouse=True)
def _clear_token_cache():
    gh_client.clear_token_cache()
    yield
    gh_client.clear_token_cache()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class _Resp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")
        self.content = self.text.encode()

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, handler):
        self._handler = handler
        self.calls = []
        self.closed = False

    def request(self, method, url, headers=None, json=None):
        self.calls.append((method, url, headers, json))
        return self._handler(method, url, headers, json)

    def close(self):
        self.closed = True


# ---------------------------------------------------------------------------
# App JWT
# ---------------------------------------------------------------------------


class TestAppJwt:
    def test_signs_verifiable_rs256(self, rsa_pem):
        pem, pub = rsa_pem
        tok = gh_client.app_jwt(1234, pem, now=1_000_000)
        header_b64, payload_b64, sig_b64 = tok.split(".")
        # The signature must verify over "header.payload" with the public key.
        pub.verify(
            _unb64(sig_b64),
            f"{header_b64}.{payload_b64}".encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )  # raises InvalidSignature if wrong
        header = json.loads(_unb64(header_b64))
        payload = json.loads(_unb64(payload_b64))
        assert header == {"alg": "RS256", "typ": "JWT"}
        assert payload["iss"] == "1234"
        assert payload["iat"] == 1_000_000 - 60
        assert payload["exp"] == 1_000_000 + 540
        assert payload["exp"] - payload["iat"] <= 600  # GitHub's 10-min cap


# ---------------------------------------------------------------------------
# Installation token
# ---------------------------------------------------------------------------


class TestInstallationToken:
    def test_mint_then_cache(self, rsa_pem):
        pem, _ = rsa_pem

        def handler(method, url, headers, body):
            assert method == "POST" and "access_tokens" in url
            assert headers["Authorization"].startswith("Bearer ")
            return _Resp(201, {"token": "ghs_abc",
                               "expires_at": "2999-01-01T00:00:00Z"})

        sess = _FakeSession(handler)
        t1 = gh_client.get_installation_token(1, pem, 99, session=sess, now=1000)
        t2 = gh_client.get_installation_token(1, pem, 99, session=sess, now=1001)
        assert t1 == t2 == "ghs_abc"
        assert len(sess.calls) == 1  # second call served from cache

    def test_expired_token_reminted(self, rsa_pem):
        pem, _ = rsa_pem
        seq = iter(["tok1", "tok2"])

        def handler(m, u, h, b):
            return _Resp(201, {"token": next(seq),
                              "expires_at": "1970-01-01T00:00:10Z"})

        sess = _FakeSession(handler)
        a = gh_client.get_installation_token(1, pem, 5, session=sess, now=0)
        b = gh_client.get_installation_token(1, pem, 5, session=sess, now=10_000)
        assert a == "tok1" and b == "tok2"
        assert len(sess.calls) == 2

    def test_non_2xx_raises(self, rsa_pem):
        pem, _ = rsa_pem
        sess = _FakeSession(lambda m, u, h, b: _Resp(404, None, text="nope"))
        with pytest.raises(gh_client.GitHubAppError):
            gh_client.get_installation_token(1, pem, 7, session=sess)


# ---------------------------------------------------------------------------
# Manifest exchange + repo list
# ---------------------------------------------------------------------------


class TestManifestExchange:
    def test_exchange_returns_creds(self):
        payload = {"id": 42, "slug": "admz-x", "pem": "PEMDATA",
                   "client_secret": "cs"}
        sess = _FakeSession(lambda m, u, h, b: _Resp(201, payload))
        out = gh_client.exchange_manifest_code("thecode", session=sess)
        assert out["id"] == 42 and out["pem"] == "PEMDATA"
        assert "app-manifests/thecode/conversions" in sess.calls[0][1]

    def test_missing_creds_raises(self):
        sess = _FakeSession(lambda m, u, h, b: _Resp(200, {"id": 1}))  # no pem
        with pytest.raises(gh_client.GitHubAppError):
            gh_client.exchange_manifest_code("c", session=sess)


class TestListRepos:
    def test_parse(self):
        payload = {"repositories": [
            {"full_name": "o/r", "name": "r", "owner": {"login": "o"}},
        ]}
        sess = _FakeSession(lambda m, u, h, b: _Resp(200, payload))
        repos = gh_client.list_installation_repositories("tok", session=sess)
        assert repos == [{"full_name": "o/r", "owner": "o", "name": "r"}]


class TestListInstallations:
    def test_list_app_installations(self, rsa_pem):
        pem, _ = rsa_pem
        payload = [{"id": 145, "account": {"login": "pettheory"}}]
        sess = _FakeSession(lambda m, u, h, b: _Resp(200, payload))
        out = gh_client.list_app_installations(1, pem, session=sess)
        assert out == [{"id": 145, "account": "pettheory"}]
        assert "/app/installations" in sess.calls[0][1]
        # authenticated with the App JWT (Bearer), not an installation token
        assert sess.calls[0][2]["Authorization"].startswith("Bearer ")


# ---------------------------------------------------------------------------
# Secret store
# ---------------------------------------------------------------------------


@pytest.fixture
def gh_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    from admz.fleet_settings import FleetSettings
    fs = FleetSettings(str(tmp_path / "admz.db"))
    monkeypatch.setattr(gh_secrets, "fleet_settings", fs)
    return fs


class TestSecrets:
    PEM = "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"

    def test_save_roundtrip_and_encrypted(self, gh_settings):
        gh_secrets.save_app(42, "admz-cfg", self.PEM)
        assert gh_secrets.get_app_id() == "42"
        assert gh_secrets.get_slug() == "admz-cfg"
        assert gh_secrets.get_private_key() == self.PEM
        # ciphertext, not plaintext, is what lands in the settings table
        stored = gh_settings.get("github_app_private_key") or ""
        assert "BEGIN PRIVATE KEY" not in stored
        assert not gh_secrets.is_connected()  # no installation yet

        gh_secrets.set_installation_id(777)
        gh_secrets.set_config_repo("pettheory/admz-config-homelab")
        assert gh_secrets.is_connected()

        st = gh_secrets.status()
        assert st["connected"] and st["slug"] == "admz-cfg"
        assert st["config_repo"].endswith("homelab")
        # status must never leak the key material
        assert "BEGIN" not in json.dumps(st)

    def test_clear_forgets_everything(self, gh_settings):
        gh_secrets.save_app(1, "s", self.PEM)
        gh_secrets.set_installation_id(2)
        gh_secrets.clear()
        assert gh_secrets.get_app_id() is None
        assert gh_secrets.get_private_key() is None
        assert gh_secrets.get_installation_id() is None
        assert not gh_secrets.is_connected()

    def test_signing_key_stable_and_derived(self, gh_settings):
        gh_secrets.encrypt("x")  # forces the key file to exist
        k1 = gh_secrets.signing_key()
        k2 = gh_secrets.signing_key()
        assert k1 == k2 and len(k1) == 32  # sha256 HMAC digest
        # domain-separated — not the raw key-file bytes
        raw = Path(gh_settings._db_path).with_name("admz.key").read_bytes()
        assert k1 != raw


class TestPushBridgeIsolation:
    """``installation_token_for_push`` is the one place the git layer reaches
    into the App's stored connection — and the connection is machine-level, so a
    developer's real credentials must not leak into a unit-test push."""

    def test_disable_flag_short_circuits_before_the_store(self, monkeypatch):
        from admz.github_app import push as gh_push

        # Would raise if the guard didn't return first.
        def _boom():
            raise AssertionError("secret store must not be touched")

        monkeypatch.setattr(gh_secrets, "is_connected", _boom)
        monkeypatch.setenv("ADMZ_DISABLE_GITHUB_APP_PUSH", "1")
        assert gh_push.installation_token_for_push() is None

    def test_without_the_flag_an_unconnected_app_is_none(self, monkeypatch):
        from admz.github_app import push as gh_push

        monkeypatch.delenv("ADMZ_DISABLE_GITHUB_APP_PUSH", raising=False)
        monkeypatch.setattr(gh_secrets, "is_connected", lambda: False)
        assert gh_push.installation_token_for_push() is None


class TestClientSecretIsNotStored:
    """GH #172. GitHub's manifest conversion returns a client secret; ADMZ used
    to encrypt and keep it, and nothing ever read it back.

    ADMZ authenticates as the App with the *private key* (JWT → installation
    token). A client secret is only for OAuth **user**-to-server flows, which
    ADMZ does not perform — so it was a real credential held at rest forever to
    no purpose. A stored secret with no reader cannot be protected by anything
    except not having it.
    """

    PEM = "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"

    def test_save_app_takes_no_client_secret(self):
        """The parameter is gone, so a caller cannot reintroduce the store by
        passing one."""
        import inspect
        assert "client_secret" not in inspect.signature(
            gh_secrets.save_app).parameters

    def test_nothing_is_written_under_the_key(self, gh_settings):
        gh_secrets.save_app(42, "admz-cfg", self.PEM)
        assert gh_settings.get(gh_secrets.KEY_CLIENT_SECRET) in (None, "")

    def test_a_legacy_value_is_cleared_on_re_setup(self, gh_settings):
        """An install that already holds one is cleaned when it next
        establishes App credentials — no separate migration needed."""
        gh_settings.set(gh_secrets.KEY_CLIENT_SECRET, "legacy-ciphertext")
        gh_secrets.save_app(42, "admz-cfg", self.PEM)
        assert gh_settings.get(gh_secrets.KEY_CLIENT_SECRET) in (None, "")

    def test_the_key_stays_protected_and_encrypted(self):
        """Still declared, on purpose: until every install has started once,
        some of them hold the old value, and it must stay masked and
        un-writable by the LLM for as long as one can exist. Dropping it from
        `KNOWN_SETTING_KEYS` would turn a live credential into an unknown key.

        Membership is asserted directly as well as through the predicates —
        removing it from `MODULE_ENCRYPTED_SETTING_KEYS` alone would leave the
        predicate assertions green.
        """
        from admz.fleet_settings import is_protected_setting, is_sensitive_setting_key
        from admz.setting_policy import (
            KNOWN_SETTING_KEYS, LLM_WRITABLE_SETTING_KEYS,
            MODULE_ENCRYPTED_SETTING_KEYS,
        )
        assert is_protected_setting(gh_secrets.KEY_CLIENT_SECRET) is True
        assert is_sensitive_setting_key(gh_secrets.KEY_CLIENT_SECRET) is True
        assert gh_secrets.KEY_CLIENT_SECRET in KNOWN_SETTING_KEYS
        assert gh_secrets.KEY_CLIENT_SECRET not in LLM_WRITABLE_SETTING_KEYS
        assert gh_secrets.KEY_CLIENT_SECRET in MODULE_ENCRYPTED_SETTING_KEYS

    def test_disconnect_still_removes_it(self, gh_settings):
        """`clear()` iterates SETTING_KEYS, which still names it — so Disconnect
        cleans a legacy value even without a re-setup."""
        gh_settings.set(gh_secrets.KEY_CLIENT_SECRET, "legacy-ciphertext")
        gh_secrets.clear()
        assert gh_settings.get(gh_secrets.KEY_CLIENT_SECRET) in (None, "")


class TestLegacyClientSecretPurge:
    """GH #172. `save_app` and `clear()` both need the operator to *do*
    something; the ordinary install — connected, working, upgraded in place —
    does neither, and would keep the credential forever. The startup purge is
    what actually retires it, so it is tested as the migration it is.
    """

    def test_purges_and_reports_it(self, gh_settings):
        gh_settings.set(gh_secrets.KEY_CLIENT_SECRET, "legacy-ciphertext")
        assert gh_secrets.purge_legacy_client_secret() is True
        assert gh_settings.get(gh_secrets.KEY_CLIENT_SECRET) in (None, "")

    def test_is_idempotent_and_quiet_when_there_is_nothing_to_do(self, gh_settings):
        """Every start after the first. Must not report a purge it didn't do —
        the return value is what gets logged."""
        assert gh_secrets.purge_legacy_client_secret() is False
        assert gh_secrets.purge_legacy_client_secret() is False

    def test_never_raises_when_the_store_fails(self, gh_settings, monkeypatch):
        """It runs in the API lifespan. A cleanup that can stop the process
        coming up is worse than the value it removes."""
        from admz.fleet_settings import fleet_settings
        monkeypatch.setattr(
            fleet_settings, "delete",
            lambda k: (_ for _ in ()).throw(RuntimeError("database is locked")))
        assert gh_secrets.purge_legacy_client_secret() is False

    def test_leaves_the_other_app_settings_alone(self, gh_settings):
        """It targets one key. A purge that also cleared the private key would
        silently disconnect a working install."""
        gh_secrets.save_app(42, "admz-cfg", "PEM")
        gh_settings.set(gh_secrets.KEY_CLIENT_SECRET, "legacy-ciphertext")
        gh_secrets.purge_legacy_client_secret()
        assert gh_secrets.get_app_id() == "42"
        assert gh_secrets.get_private_key() == "PEM"
        assert gh_secrets.get_slug() == "admz-cfg"
