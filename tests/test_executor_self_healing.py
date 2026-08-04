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


# --- GH #171: refuse to LEARN Basic over a plaintext channel ---------------
#
# The property under test is "no `Authorization: Basic` crossed the wire", so
# every assertion below is made against the requests the transport actually
# SAW, not against the return value. Asserting on the return value alone would
# pass just as happily if the executor had never sent anything at all.
#
# Each refusal case is therefore paired with a positive assertion that the
# Digest attempt DID happen. That pairing is the anti-vacuity control: without
# it, "no Basic on the wire" is trivially true for a test that makes no
# request, and the rule could be deleted entirely without the test noticing.


def _recording_handler(*, accept_basic: bool = True, challenge: str = 'Basic realm="x"'):
    """A device that 401s with `challenge` until Basic arrives.

    Returns (handler, seen) where `seen` accumulates the Authorization header
    of every request the transport received, in order — `None` for none.
    """
    seen: list = []

    def handler(request):
        seen.append(request.headers.get("authorization"))
        if accept_basic and (request.headers.get("authorization") or "").startswith("Basic "):
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(401, headers={"WWW-Authenticate": challenge})

    return handler, seen


def _basic_creds_on_wire(seen) -> list:
    return [a for a in seen if a and a.startswith("Basic ")]


@pytest.mark.asyncio
async def test_basic_challenge_over_plain_http_sends_no_credential():
    """The #171 harm itself: a Basic challenge on http must not spend the password."""
    handler, seen = _recording_handler()
    device = {"auth": {"http": "digest", "scheme": "http"}, "device_id": "DEV"}

    resp, learned = await _heal(_exe(handler), device, scheme="http", port=80)

    # The harm is blocked...
    assert _basic_creds_on_wire(seen) == [], (
        "a Basic credential reached the wire over plaintext http")
    assert learned is None, "a plaintext Basic downgrade was persisted"
    assert resp.status_code == 401, "the caller must still see the 401"

    # ...and NOT because nothing happened. Exactly one attempt was made, and it
    # was the Digest one. If this assertion is ever relaxed, the two above stop
    # proving anything.
    assert len(seen) == 1, f"expected exactly the digest attempt, saw {seen!r}"


@pytest.mark.asyncio
async def test_basic_challenge_over_https_still_relearns():
    """The rule must not over-fire: the same challenge on TLS is permitted."""
    handler, seen = _recording_handler()
    device = {"auth": {"https": "digest", "scheme": "https"}, "device_id": "DEV"}

    resp, learned = await _heal(_exe(handler), device, scheme="https", port=443)

    assert resp.status_code == 200
    assert learned == {"scheme": "https", "https": "basic"}
    # The mirror image of the test above, on the same fixture: here the Basic
    # credential SHOULD have been sent. This is what makes the pair meaningful.
    assert len(_basic_creds_on_wire(seen)) == 1
    assert len(seen) == 2, f"expected digest then basic, saw {seen!r}"


@pytest.mark.asyncio
async def test_digest_challenge_over_plain_http_still_relearns():
    """Only Basic is refused. Relearning Digest over http is untouched.

    Starts from ``none`` so nothing is sent preemptively and the first request
    is genuinely unauthenticated — the point is that a plaintext channel does
    not by itself block a relearn, only a relearn *to Basic* does.
    """
    seen: list = []

    def handler(request):
        auth = request.headers.get("authorization")
        seen.append(auth)
        if auth and auth.startswith("Digest "):
            return httpx.Response(200, json={"ok": True})
        # httpx.DigestAuth sends nothing until challenged; this 401 is what
        # triggers its second, authenticated request.
        return httpx.Response(
            401, headers={"WWW-Authenticate": 'Digest realm="x", nonce="n"'})

    device = {"auth": {"http": "none", "scheme": "http"}, "device_id": "DEV"}
    resp, learned = await _heal(_exe(handler), device, scheme="http", port=80)

    assert resp.status_code == 200
    assert learned == {"scheme": "http", "http": "digest"}
    assert _basic_creds_on_wire(seen) == [], "no Basic should appear on this path"


@pytest.mark.asyncio
async def test_explicitly_configured_basic_over_http_still_works():
    """The escape hatch, and the limit of the rule.

    The rule refuses to *learn* Basic over plaintext; it does not refuse to
    *use* it. A device an operator has deliberately configured as
    ``{"http": "basic"}`` authenticates on the first attempt, so the relearn
    branch is never reached. This is what an operator does today when a device
    genuinely requires Basic over HTTP, and it is why D1 can ship before D2's
    pin exists.
    """
    handler, seen = _recording_handler()
    device = {"auth": {"http": "basic", "scheme": "http"}, "device_id": "DEV"}

    resp, learned = await _heal(_exe(handler), device, scheme="http", port=80)

    assert resp.status_code == 200
    assert learned is None, "nothing was learned; the profile was already right"
    assert len(_basic_creds_on_wire(seen)) == 1, (
        "an explicitly configured Basic-over-http device must still authenticate")


@pytest.mark.asyncio
async def test_refusal_survives_a_scheme_flip_to_http():
    """The refusal keys off the channel actually in use, not the starting one.

    https is refused at the TCP level, so the executor flips to http and *then*
    meets the Basic challenge. `scheme` has been reassigned by that point, and
    the rule must see the post-flip value. Reading the parameter the function
    was called with instead would leak the credential on exactly the path #171
    describes.
    """
    handler_inner, seen = _recording_handler()

    def handler(request):
        if request.url.scheme == "https":
            raise httpx.ConnectError("refused", request=request)
        return handler_inner(request)

    device = {"auth": {"http": "digest", "https": "digest", "scheme": "https"},
              "device_id": "DEV"}
    resp, learned = await _heal(_exe(handler), device, scheme="https", port=443)

    assert _basic_creds_on_wire(seen) == []
    assert resp.status_code == 401
    # The scheme correction is still learned — only the Basic method is refused.
    assert learned == {"scheme": "http", "http": "digest"}


@pytest.mark.asyncio
async def test_refusal_logs_a_warning_without_the_credential():
    """The refusal must be loud, and must not itself leak.

    The warning names the device and what was refused; it must never carry the
    password, and it must not echo the attacker-controlled challenge verbatim.
    """
    handler, _ = _recording_handler()
    device = {"auth": {"http": "digest", "scheme": "http"}, "device_id": "DEV"}

    import logging
    records: list = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    log = logging.getLogger("admz.executor.vapix")
    cap = _Capture()
    log.addHandler(cap)
    try:
        await _heal(_exe(handler), device, scheme="http", port=80)
    finally:
        log.removeHandler(cap)

    warns = [m for m in records if "Refusing to relearn Basic" in m]
    assert len(warns) == 1, f"expected exactly one refusal warning, got {records!r}"
    assert "DEV" in warns[0] and "#171" in warns[0]
    assert "pw" not in warns[0], "the warning leaked the password"
    assert "realm" not in warns[0], "the warning echoed the raw challenge header"


@pytest.mark.parametrize("scheme,plaintext", [
    ("http", True),
    ("https", False),
    ("HTTPS", False),   # case-folded before comparing
    (" https ", False),
    ("HTTP", True),
    ("", True),         # fail closed: unknown scheme is treated as plaintext
    (None, True),
    ("ftp", True),
])
def test_is_plaintext_channel(scheme, plaintext):
    from admz.executor.vapix import _is_plaintext_channel
    assert _is_plaintext_channel(scheme) is plaintext


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
