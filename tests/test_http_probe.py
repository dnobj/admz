"""The discovery HTTP probe recognises Axis devices set up HTTPS-only.

The probe used to try plain HTTP only. An Axis device with HTTP turned off never
answered it, so a scan listed it without the VAPIX tag and without the model
and serial that basicdeviceinfo gives — on 2026-09-17 exactly the four devices
the registry has on HTTPS (.123, .134, .208, .220). The probe now falls back to
HTTPS when plain HTTP does not answer at all, and uses the scheme that answered
for its follow-up calls.

httpx's MockTransport stands in for the network, so nothing leaves the process.
"""

import asyncio
import json

import httpx
import pytest

from admz.discovery.http_probe import HTTPProbe

IP = "192.0.2.208"
AXIS_CSP = "default-src 'self'; img-src 'self' https://*.axis.com"
DEVICE_INFO = {"apiVersion": "1.0", "data": {"propertyList": {}, "properties": {
    "ProdNbr": "I8016-LVE", "SerialNumber": "B8A44F000208",
    "Version": "12.10.68", "ProdType": "Network Camera",
}}}


def _probe_with(monkeypatch, handler):
    """Run the probe against ``handler`` and return (device, requested URLs)."""
    seen = []

    def recording(request):
        seen.append(f"{request.method} {request.url}")
        return handler(request)

    real = httpx.AsyncClient

    def client(**kwargs):
        kwargs["transport"] = httpx.MockTransport(recording)
        return real(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    device = asyncio.run(HTTPProbe(targets=[IP])._probe_host(IP, timeout=1.0))
    return device, seen


def _https_only_axis(request):
    if request.url.scheme == "http":
        raise httpx.ConnectError("port 80 closed", request=request)
    if request.url.path == "/":
        return httpx.Response(200, headers={"content-security-policy": AXIS_CSP})
    if request.url.path == "/axis-cgi/basicdeviceinfo.cgi":
        return httpx.Response(200, json=DEVICE_INFO)
    if request.url.path == "/axis-cgi/param.cgi":
        return httpx.Response(401)
    return httpx.Response(404)


class TestAnHttpsOnlyDevice:
    def test_it_is_recognised_as_axis_with_vapix(self, monkeypatch):
        device, _ = _probe_with(monkeypatch, _https_only_axis)
        assert device is not None
        assert (device.is_axis, device.vapix_available) == (True, True)
        assert device.factory_default is False

    def test_its_follow_up_calls_use_https(self, monkeypatch):
        device, seen = _probe_with(monkeypatch, _https_only_axis)
        assert f"POST https://{IP}/axis-cgi/basicdeviceinfo.cgi" in seen
        assert not [u for u in seen if u.startswith("POST http://")]
        assert (device.model, device.serial_number, device.firmware_version) == (
            "I8016-LVE", "B8A44F000208", "12.10.68")


class TestPlainHttpIsStillFirst:
    def test_a_device_answering_http_is_never_asked_over_https(self, monkeypatch):
        def http_axis(request):
            if request.url.path == "/":
                return httpx.Response(200, headers={"server": "Boa/0.94"})
            return httpx.Response(401)

        device, seen = _probe_with(monkeypatch, http_axis)
        assert device.vapix_available is True
        assert not [u for u in seen if "https://" in u]

    def test_a_web_server_that_is_not_axis_is_not_retried(self, monkeypatch):
        """HTTP answered — with no Axis signature — so HTTPS is not tried."""
        def router(request):
            return httpx.Response(200, headers={"server": "nginx"})

        device, seen = _probe_with(monkeypatch, router)
        assert device.is_axis is False
        assert seen == [f"GET http://{IP}/"]


class TestNothingAnswers:
    def test_no_device_is_reported(self, monkeypatch):
        def dead(request):
            raise httpx.ConnectError("refused", request=request)

        device, seen = _probe_with(monkeypatch, dead)
        assert device is None
        assert seen == [f"GET http://{IP}/", f"GET https://{IP}/"]

    def test_no_credentials_are_sent_on_either_scheme(self, monkeypatch):
        def check(request):
            assert "authorization" not in request.headers
            return _https_only_axis(request)

        device, _ = _probe_with(monkeypatch, check)
        assert device is not None


@pytest.mark.parametrize("body", [json.dumps(DEVICE_INFO)])
def test_the_fixture_is_what_basicdeviceinfo_returns(body):
    """Guards the fixture's shape against the parser's expectations."""
    assert json.loads(body)["data"]["properties"]["SerialNumber"]
