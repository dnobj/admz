"""Tests for VapixExecutor connectivity self-healing (scheme + auth relearn).

Reproduces the real P3288 case: a device whose stored profile says http but
which is HTTPS-only and wants Basic auth. The executor should fall back to
https, relearn the auth method from the 401 challenge, and report the
corrected profile via StepResult.learned_auth — which run_execution_tail
persists.
"""

import httpx
import pytest

from admz.executor.vapix import VapixExecutor, _auth_method_from_challenge
from admz.executor.models import ExecutionRequest, StepResult


def _req():
    return ExecutionRequest(
        method="POST", path="/axis-cgi/systemready.cgi",
        json_body={"apiVersion": "1.0", "method": "systemReady"},
    )


def _exe(handler):
    return VapixExecutor(timeout=2.0, retries=0, transport=httpx.MockTransport(handler))


async def _heal(exe, device, scheme="http", port=80):
    return await exe._send_self_healing(
        request=_req(), host="192.0.2.1", device=device,
        credentials={"username": "root", "password": "pw"},
        scheme=scheme, port=port, timeout=2.0,
    )


# --- challenge parser ------------------------------------------------------


@pytest.mark.parametrize("header,expected", [
    ('Basic realm="AXIS_x"', "basic"),
    ('Digest realm="x", nonce="y", qop="auth"', "digest"),
    ('Digest realm="x", Basic realm="x"', "digest"),  # prefer digest
    ("", None),
    (None, None),
    ("Bearer", None),
])
def test_auth_method_from_challenge(header, expected):
    assert _auth_method_from_challenge(header) == expected


# --- scheme fallback -------------------------------------------------------


@pytest.mark.asyncio
async def test_scheme_fallback_http_refused_https_ok():
    def handler(request):
        if request.url.scheme == "http":
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"systemready": "yes"})

    resp, learned = await _heal(_exe(handler), {"auth": None})
    assert resp.status_code == 200
    # scheme corrected to https; method stays the (default) digest
    assert learned == {"scheme": "https", "https": "digest"}


@pytest.mark.asyncio
async def test_p3288_full_heal_scheme_and_method():
    """HTTPS-only device that wants Basic — the exact P3288 failure."""
    def handler(request):
        if request.url.scheme == "http":
            raise httpx.ConnectError("refused", request=request)
        if request.headers.get("authorization", "").startswith("Basic "):
            return httpx.Response(200, json={"data": {"systemready": "yes"}})
        return httpx.Response(401, headers={"WWW-Authenticate": 'Basic realm="AXIS"'})

    resp, learned = await _heal(_exe(handler), {"auth": None})
    assert resp.status_code == 200
    assert learned == {"scheme": "https", "https": "basic"}


@pytest.mark.asyncio
async def test_both_schemes_refused_raises_connecterror():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(httpx.ConnectError):
        await _heal(_exe(handler), {"auth": None})


# --- method relearn only (scheme already correct) --------------------------


@pytest.mark.asyncio
async def test_method_relearn_digest_to_basic():
    def handler(request):
        if request.headers.get("authorization", "").startswith("Basic "):
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(401, headers={"WWW-Authenticate": 'Basic realm="x"'})

    device = {"auth": {"http": "digest", "https": "digest", "scheme": "https"}}
    resp, learned = await _heal(_exe(handler), device, scheme="https", port=443)
    assert resp.status_code == 200
    assert learned == {"scheme": "https", "https": "basic"}


@pytest.mark.asyncio
async def test_no_healing_when_first_attempt_works():
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    device = {"auth": {"http": "digest", "scheme": "http"}}
    resp, learned = await _heal(_exe(handler), device)
    assert resp.status_code == 200
    assert learned is None


@pytest.mark.asyncio
async def test_wrong_password_not_persisted():
    """A 401 that stays 401 even after a method retry must not 'learn'
    anything — the password is wrong, not the method."""
    def handler(request):
        # offers Basic but rejects everything (bad password)
        return httpx.Response(401, headers={"WWW-Authenticate": 'Basic realm="x"'})

    device = {"auth": {"https": "digest", "scheme": "https"}}
    resp, learned = await _heal(_exe(handler), device, scheme="https", port=443)
    assert resp.status_code == 401
    assert learned is None


# --- persistence via run_execution_tail ------------------------------------


class _Op:
    def to_executor_dict(self):
        return {"id": "systemready.cgi:systemReady"}


class _Catalog:
    def get_operation(self, family, op_id):
        return _Op()


class _Registry:
    def __init__(self, auth):
        self.auth = auth
        self.updates = []

    def device_exists(self, did):
        return True

    def get_device_info(self, did):
        return {"host": "192.0.2.1", "auth": self.auth}

    def get_credentials(self, did):
        return {"username": "root", "password": "pw"}

    def update_device_info(self, did, updates):
        self.updates.append((did, updates))


class _HealingExecutor:
    """Fake executor that reports a learned_auth correction."""
    def __init__(self, learned):
        self.learned = learned

    async def execute(self, op, device, creds, params):
        return StepResult(operation_id="systemready.cgi:systemReady",
                          device_id=device["device_id"], success=True,
                          status_code=200, parsed_data={"ok": True},
                          learned_auth=self.learned)


@pytest.mark.asyncio
async def test_run_execution_tail_persists_learned_auth():
    from admz import operations
    reg = _Registry(auth=None)
    execs = {"vapix": _HealingExecutor({"scheme": "https", "https": "basic"})}
    await operations.run_execution_tail(
        device_id="DEV", operation_id="systemready.cgi:systemReady", family="vapix",
        params={}, catalog=_Catalog(), registry=reg, executors=execs,
    )
    assert reg.updates == [("DEV", {"auth": {"scheme": "https", "https": "basic"}})]


@pytest.mark.asyncio
async def test_run_execution_tail_merges_into_existing_auth():
    from admz import operations
    reg = _Registry(auth={"http": "digest", "https": "digest", "scheme": "http"})
    execs = {"vapix": _HealingExecutor({"scheme": "https", "https": "basic"})}
    await operations.run_execution_tail(
        device_id="DEV", operation_id="systemready.cgi:systemReady", family="vapix",
        params={}, catalog=_Catalog(), registry=reg, executors=execs,
    )
    # merged: http preserved, https + scheme corrected
    assert reg.updates == [("DEV", {"auth": {
        "http": "digest", "https": "basic", "scheme": "https"}})]


@pytest.mark.asyncio
async def test_run_execution_tail_no_update_when_nothing_learned():
    from admz import operations
    reg = _Registry(auth={"scheme": "http"})
    execs = {"vapix": _HealingExecutor(None)}
    await operations.run_execution_tail(
        device_id="DEV", operation_id="systemready.cgi:systemReady", family="vapix",
        params={}, catalog=_Catalog(), registry=reg, executors=execs,
    )
    assert reg.updates == []
