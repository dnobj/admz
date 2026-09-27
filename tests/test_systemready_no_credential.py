"""#479 — a ``systemready`` read carries no credential, from any caller.

``systemready.cgi`` is auth-free by design, and each caller asks it right after
the device refused, or may have refused, the stored pair: the health sweep's
credential-less tier, drift's readability probe, and onboarding's
factory-default check. Onboarding and drift used to hand ``read_systemready``
the stored pair with the device's auth profile, so the pair ADMZ had just
watched fail went to the device once more. The reader now takes no credential
and switches auth off itself.

The wire tests run the REAL ``VapixExecutor`` against the REAL catalog op,
through httpx's ``MockTransport``, because the hazard lives in the executor:
with auth switched off it still answers a 401 challenge by retrying with
whatever pair it was handed. So switching auth off is not enough on its own,
and only a test that watches the ``Authorization`` headers can show it.
"""

import ast
import asyncio
import base64
import inspect
from pathlib import Path
from unittest.mock import AsyncMock

import axis_api_atlas
import httpx
import pytest
from axis_api_atlas.catalog.loader import CatalogLoader

import admz
from admz.executor.vapix import VapixExecutor
from admz.fleet.systemready import read_systemready, unauthenticated
from admz.onboarding import APPROVAL_REQUIRED

STORED_USER = "stored-user-479"
STORED_PASS = "Stored-Pass-479"
STORED = {"username": STORED_USER, "password": STORED_PASS}

SYSTEMREADY_PATH = "/axis-cgi/systemready.cgi"
NEEDS_SETUP = {"apiVersion": "1.0", "data": {
    "systemready": "yes", "needsetup": "yes", "uptime": "5", "bootid": "b1"}}

DIGEST_PROFILE = {"scheme": "http", "http": "digest", "https": "digest"}
BASIC_HTTPS_PROFILE = {"scheme": "https", "http": "digest", "https": "basic"}


@pytest.fixture(scope="module")
def catalog():
    return CatalogLoader(axis_api_atlas.default_data_path())


def _leaks_stored_pair(header: str) -> bool:
    """Whether one Authorization header carries the stored pair. Digest puts
    the username on the wire in clear; Basic puts both, base64-encoded."""
    if STORED_USER in header:
        return True
    if header.startswith("Basic "):
        decoded = base64.b64decode(header[len("Basic "):]).decode("utf-8", "replace")
        return STORED_USER in decoded or STORED_PASS in decoded
    return False


class _Device:
    """A factory-defaulted Axis unit at the end of a MockTransport.

    ``challenge`` is what it answers an unauthenticated request with: ``None``
    answers it (as a factory-defaulted unit does), ``"digest"`` or ``"basic"``
    sends a 401 naming that scheme, which is what makes the executor retry.
    ``refuse_params`` makes every param.cgi read a 401, as for a device whose
    stored password no longer works. ``http_refused`` closes port 80.
    """

    def __init__(self, challenge=None, refuse_params=False, http_refused=False):
        self.challenge = challenge
        self.refuse_params = refuse_params
        self.http_refused = http_refused
        self.seen = []  # (scheme, path, Authorization header or "")

    def __call__(self, request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("authorization", "")
        self.seen.append((request.url.scheme, request.url.path, auth))
        if self.http_refused and request.url.scheme == "http":
            raise httpx.ConnectError("port 80 closed", request=request)
        if request.url.path == "/axis-cgi/param.cgi" and self.refuse_params:
            return httpx.Response(
                401, headers={"WWW-Authenticate": 'Digest realm="axis", nonce="n1"'})
        if request.url.path == SYSTEMREADY_PATH:
            if not auth and self.challenge == "digest":
                return httpx.Response(
                    401, headers={"WWW-Authenticate": 'Digest realm="axis", nonce="n2"'})
            if not auth and self.challenge == "basic":
                return httpx.Response(
                    401, headers={"WWW-Authenticate": 'Basic realm="axis"'})
            return httpx.Response(200, json=NEEDS_SETUP)
        return httpx.Response(404)

    def headers_to(self, path):
        return [auth for _scheme, p, auth in self.seen if p == path and auth]

    def requests_to(self, path):
        return [(scheme, auth) for scheme, p, auth in self.seen if p == path]


def _executor(device):
    return VapixExecutor(timeout=2.0, retries=0, transport=httpx.MockTransport(device))


class _Registry:
    """What onboarding and the drift engine read: one device, one stored pair."""

    def __init__(self, profile):
        self.profile = profile

    def get_device_info(self, device_id):
        return {"host": "192.0.2.79", "model": "", "auth": dict(self.profile)}

    def get_credentials(self, device_id, *a, **k):
        return dict(STORED)


# --- the reader --------------------------------------------------------------

class TestTheReader:
    def test_it_takes_no_credential(self):
        params = inspect.signature(read_systemready).parameters
        assert list(params) == ["catalog", "executor", "device_info", "family"]
        assert params["family"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_a_stray_positional_credential_fails_loudly(self, catalog):
        """Not silently taken for a family name, which the reader's own
        ``except`` would turn into a quiet ``None`` — needs_setup detection
        switched off with no error anywhere."""
        with pytest.raises(TypeError):
            read_systemready(catalog, object(), {"host": "192.0.2.79"}, dict(STORED))

    def test_it_switches_auth_off_and_sends_an_empty_pair(self):
        sent = []

        class _Executor:
            async def execute(self, op, device, creds, params):
                sent.append((device, creds))
                return type("R", (), {"success": True, "parsed_data": NEEDS_SETUP})()

        class _Catalog:
            def get_operation(self, family, op_id):
                return type("Op", (), {"to_executor_dict": lambda s: {"id": op_id}})()

        info = {"host": "192.0.2.79", "auth_method": "basic", "auth": dict(BASIC_HTTPS_PROFILE)}
        out = asyncio.run(read_systemready(_Catalog(), _Executor(), info))

        assert out["needsetup"] is True
        (device, creds), = sent
        assert creds == {"username": "", "password": ""}
        assert device["auth"] == {"scheme": "https", "http": "none", "https": "none"}
        assert device["auth_method"] == "none"
        assert info["auth"] == BASIC_HTTPS_PROFILE, "the caller's profile is not mutated"

    def test_unauthenticated_keeps_the_rest_of_the_profile(self):
        info = {"host": "h", "port": 8443, "auth": {"scheme": "https", "https": "basic"}}
        assert unauthenticated(info) == {
            "host": "h", "port": 8443, "auth_method": "none",
            "auth": {"scheme": "https", "http": "none", "https": "none"},
        }
        assert unauthenticated({"host": "h"})["auth"] == {"http": "none", "https": "none"}


# --- onboarding's factory-default check, on the wire -----------------------

def _onboard(monkeypatch, catalog, device, profile):
    """Run onboarding to its step 2 with the stored pair just refused.

    Step 1 is stubbed to "refused" so the only traffic is step 2's; the device
    answers ``needsetup=yes``, so onboarding stops at the provisioning gate."""
    from admz.onboarding import onboard_device_credentials

    monkeypatch.delenv("ADMZ_DISABLE_ONBOARDING_PROBES", raising=False)
    monkeypatch.setattr("admz.fleet.health._tcp_probe", AsyncMock(return_value=3))
    monkeypatch.setattr("admz.fleet.health._confirm_credentials",
                        AsyncMock(return_value=(False, {}, None)))
    return asyncio.run(onboard_device_credentials(
        device_id="dev-479", registry=_Registry(profile), catalog=catalog,
        executors={"vapix": _executor(device)},
    ))


class TestOnboardingOnTheWire:
    @pytest.mark.parametrize("profile,challenge", [
        (DIGEST_PROFILE, "digest"),
        (BASIC_HTTPS_PROFILE, "basic"),
        (BASIC_HTTPS_PROFILE, "digest"),
    ], ids=["digest", "basic-over-https", "basic-profile-digest-challenge"])
    def test_the_refused_pair_is_not_sent_to_systemready(
            self, monkeypatch, catalog, profile, challenge):
        device = _Device(challenge=challenge)
        out = _onboard(monkeypatch, catalog, device, profile)

        assert out["status"] == APPROVAL_REQUIRED, (
            "step 2 must have read needsetup=yes through the real executor", out)
        headers = device.headers_to(SYSTEMREADY_PATH)
        assert headers, "the challenge was answered, so a retry went out"
        assert not [h for h in headers if _leaks_stored_pair(h)], headers

    @pytest.mark.parametrize("profile", [DIGEST_PROFILE, BASIC_HTTPS_PROFILE],
                             ids=["digest", "basic-over-https"])
    def test_a_device_that_does_not_challenge_sees_no_authorization_at_all(
            self, monkeypatch, catalog, profile):
        """A factory-defaulted unit answers systemready unauthenticated, so the
        read never needs a header. A `basic` profile used to send one on the
        first request, before the device had asked for anything."""
        device = _Device(challenge=None)
        out = _onboard(monkeypatch, catalog, device, profile)

        assert out["status"] == APPROVAL_REQUIRED, out
        assert device.requests_to(SYSTEMREADY_PATH) == [(profile["scheme"], "")]

    def test_the_fallback_scheme_is_asked_without_auth_too(self, monkeypatch, catalog):
        """Port 80 refused, so the executor falls back to HTTPS and takes that
        scheme's method from the profile — which says `basic`. Auth must be off
        on both schemes, or the fallback sends a Basic header."""
        profile = {"scheme": "http", "http": "digest", "https": "basic"}
        device = _Device(challenge=None, http_refused=True)
        out = _onboard(monkeypatch, catalog, device, profile)

        assert out["status"] == APPROVAL_REQUIRED, out
        assert device.requests_to(SYSTEMREADY_PATH) == [("http", ""), ("https", "")]


# --- drift's readability probe, on the wire --------------------------------

class TestDriftProbeOnTheWire:
    @pytest.mark.parametrize("profile,challenge", [
        (DIGEST_PROFILE, "digest"),
        (BASIC_HTTPS_PROFILE, None),
        (DIGEST_PROFILE, None),
    ], ids=["digest", "basic-over-https", "digest-unchallenged"])
    def test_the_pair_param_cgi_refused_is_not_sent_to_systemready(
            self, catalog, profile, challenge):
        from admz.snapshot.engine import SnapshotEngine

        device = _Device(challenge=challenge, refuse_params=True)
        registry = _Registry(profile)
        engine = SnapshotEngine(
            catalog=catalog, registry=registry,
            executors={"vapix": _executor(device)}, git_repo=None,
        )
        ok, reason = asyncio.run(engine.probe_readable(
            "dev-479", registry.get_device_info("dev-479"), "vapix"))

        assert (ok, reason) == (False, "needs_setup")
        # The authenticated read is the probe's job, and it did carry the pair;
        # the control that shows this device was offered it at all.
        assert [h for h in device.headers_to("/axis-cgi/param.cgi")
                if _leaks_stored_pair(h)], device.seen
        assert not [h for h in device.headers_to(SYSTEMREADY_PATH)
                    if _leaks_stored_pair(h)], device.seen


# --- no caller can pass one --------------------------------------------------

def test_no_call_site_passes_read_systemready_a_credential():
    """Every call in admz/ passes at most (catalog, executor, device_info)
    positionally and no keyword but ``family``. Non-vacuous: the three known
    callers must be found."""
    root = Path(admz.__file__).parent
    found, bad = set(), []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name != "read_systemready":
                continue
            rel = path.relative_to(root.parent).as_posix()
            found.add(rel)
            extra = [k.arg for k in node.keywords if k.arg != "family"]
            if len(node.args) > 3 or extra:
                bad.append(f"{rel}:{node.lineno}")
    assert {"admz/fleet/health.py", "admz/onboarding.py",
            "admz/snapshot/engine.py"} <= found, found
    assert bad == []
