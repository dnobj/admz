"""ACS Pro module (#2) — enablement gating, executor, correlation (ADR-0040).

The live Negotiate handshake + a real ACS server are out of scope here (need an
on-prem Windows/ACS box); these cover everything around that seam with mocks.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from tests import mcp_harness


class _FakeSettings:
    """In-memory stand-in for the fleet_settings key/value store."""

    def __init__(self):
        self._d = {}

    def get(self, k):
        return self._d.get(k)

    def set(self, k, v):
        self._d[k] = v


@pytest.fixture
def fake_settings(monkeypatch):
    fs = _FakeSettings()
    import admz.modules.acs_pro.config as cfg
    monkeypatch.setattr(cfg, "_settings", lambda: fs)
    return fs


# --------------------------------------------------------------------------
# Config + enablement gating
# --------------------------------------------------------------------------
class TestConfigGating:
    def test_default_disabled(self, fake_settings):
        from admz.modules.acs_pro.config import acs_config, acs_enabled

        assert acs_enabled() is False
        assert acs_config()["port"] == 29204

    def test_enabled_requires_server_url(self, fake_settings):
        from admz.modules.acs_pro.config import acs_enabled, save_acs_config

        save_acs_config(enabled=True, server_url="")  # no host → still off
        assert acs_enabled() is False
        save_acs_config(enabled=True, server_url="acs.example.com")
        assert acs_enabled() is True

    def test_base_url_builds_https_with_port(self, fake_settings):
        from admz.modules.acs_pro.config import base_url, save_acs_config

        save_acs_config(enabled=True, server_url="acs.example.com", port=29204)
        assert base_url() == "https://acs.example.com:29204"

    def test_base_url_accepts_full_url(self, fake_settings):
        from admz.modules.acs_pro.config import base_url, save_acs_config

        save_acs_config(enabled=True, server_url="https://acs:443/", port=29204)
        assert base_url() == "https://acs:443"


# --------------------------------------------------------------------------
# Module factories self-gate (zero footprint until enabled)
# --------------------------------------------------------------------------
class TestModuleGating:
    def test_no_footprint_when_disabled(self, fake_settings):
        from admz.modules import acs_pro

        m = acs_pro.get_module()
        assert m.mcp_tools() == []
        assert m.nav_section() is None
        assert m.build_prompt_section() == ""
        assert m.self_heals() is False
        # The executor is always registered (cheap), so the family resolves.
        assert "acs-pro" in m.executors()

    def test_full_surface_when_enabled(self, fake_settings):
        from admz.modules import acs_pro
        from admz.modules.acs_pro.config import save_acs_config

        save_acs_config(enabled=True, server_url="acs.example.com")
        m = acs_pro.get_module()
        names = [s.tool.name for s in m.mcp_tools()]
        assert "acs_find_camera_for_device" in names
        assert m.nav_section() is not None
        assert "Axis Camera Station Pro" in m.build_prompt_section()


# --------------------------------------------------------------------------
# Correlation (pure)
# --------------------------------------------------------------------------
class TestCorrelation:
    def _acs(self):
        devices = [
            {"DeviceId": {"Id": "dev-1"}, "Name": "Lobby", "MacAddress": "B8:A4:4F:D0:25:7C", "Model": "P3748"},
            {"DeviceId": {"Id": "dev-2"}, "Name": "Dock", "MacAddress": "AA:BB:CC:DD:EE:FF"},
        ]
        cameras = [
            {"CameraId": {"Id": "cam-1"}, "DeviceId": {"Id": "dev-1"}, "Name": "Lobby Cam", "Model": "P3748"},
            {"CameraId": {"Id": "cam-9"}, "DeviceId": {"Id": "dev-2"}, "Name": "Other"},
        ]
        return devices, cameras

    def test_match_by_mac(self):
        from admz.modules.acs_pro.correlate import correlate_device_to_cameras

        devices, cameras = self._acs()
        out = correlate_device_to_cameras(
            {"device_id": "B8A44FD0257C", "mac_address": "B8:A4:4F:D0:25:7C"}, devices, cameras
        )
        assert out["matched"] is True
        assert out["match_key"] == "mac"
        assert [c["camera_id"] for c in out["cameras"]] == ["cam-1"]

    def test_no_match(self):
        from admz.modules.acs_pro.correlate import correlate_device_to_cameras

        devices, cameras = self._acs()
        out = correlate_device_to_cameras({"device_id": "001122334455"}, devices, cameras)
        assert out["matched"] is False
        assert out["cameras"] == []

    def test_serial_fallback(self):
        from admz.modules.acs_pro.correlate import correlate_device_to_cameras

        devices = [{"DeviceId": {"Id": "d"}, "SerialNumber": "ACCC123", "MacAddress": ""}]
        cameras = [{"CameraId": {"Id": "c"}, "DeviceId": {"Id": "d"}}]
        out = correlate_device_to_cameras(
            {"device_id": "x", "serial_number": "accc123"}, devices, cameras
        )
        assert out["matched"] is True and out["match_key"] == "serial"


# --------------------------------------------------------------------------
# Executor (mocked transport + Negotiate)
# --------------------------------------------------------------------------
def _run(coro):
    return asyncio.run(coro)


class TestExecutor:
    def _patch_negotiate(self, monkeypatch):
        import admz.modules.acs_pro.negotiate as neg

        class _FakeNeg:
            def step(self, blob):
                return True, b"tok"

            def close(self):
                pass

        monkeypatch.setattr(
            neg, "initial_header", lambda host: ("Negotiate AAAA", _FakeNeg())
        )

    def _patch_httpclient(self, monkeypatch, captured):
        """Mock httpx.AsyncClient so no socket is touched + we capture verify."""
        import httpx

        class _FakeClient:
            def __init__(self, verify=True, timeout=None):
                captured["verify"] = verify

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    def test_builds_url_and_posts_json(self, monkeypatch):
        self._patch_negotiate(monkeypatch)
        import admz.modules.acs_pro.executor as ex

        captured = {}
        self._patch_httpclient(monkeypatch, captured)

        async def fake_send(client, method, url, headers, json_body):
            captured.update(method=method, url=url, headers=headers, body=json_body)
            return 200, '{"Cameras": []}', {}, "OK"

        monkeypatch.setattr(ex, "_send", fake_send)
        executor = ex.AcsProExecutor()
        op = {"id": "CameraListFacade:GetCameraList", "path": "/Acs/Api/CameraListFacade/GetCameraList", "method": "POST"}
        server = {"device_id": "acs-server", "host": "https://acs:29204", "verify_tls": False}
        result = _run(executor.execute(op, server, {}, {"range": {"StartIndex": 0}}))
        assert result.success is True
        assert captured["url"] == "https://acs:29204/Acs/Api/CameraListFacade/GetCameraList"
        assert captured["method"] == "POST"
        assert captured["verify"] is False  # self-signed tolerated, scoped to call
        assert captured["body"] == {"range": {"StartIndex": 0}}
        assert "Negotiate" in captured["headers"]["Authorization"]
        assert result.parsed_data == {"Cameras": []}

    def test_ntlm_challenge_leg(self, monkeypatch):
        """A 401 + Negotiate challenge triggers a second leg on the SAME client."""
        self._patch_negotiate(monkeypatch)
        import admz.modules.acs_pro.executor as ex

        captured = {}
        self._patch_httpclient(monkeypatch, captured)
        calls = []

        async def fake_send(client, method, url, headers, json_body):
            calls.append(headers["Authorization"])
            if len(calls) == 1:
                return 401, "", {"www-authenticate": "Negotiate oYGc, Basic realm=\"\""}, "Unauthorized"
            return 200, '{"Major": 2}', {}, "OK"

        monkeypatch.setattr(ex, "_send", fake_send)
        op = {"id": "VersionFacade:GetApiVersion", "path": "/Acs/Api/VersionFacade/GetApiVersion", "method": "POST"}
        result = _run(ex.AcsProExecutor().execute(op, {"host": "https://acs:29204"}, {}, {}))
        assert result.success is True and result.parsed_data == {"Major": 2}
        assert len(calls) == 2  # initial + continued token

    def test_http_error_uses_reason_phrase(self, monkeypatch):
        self._patch_negotiate(monkeypatch)
        import admz.modules.acs_pro.executor as ex

        captured = {}
        self._patch_httpclient(monkeypatch, captured)

        async def fake_send(*a, **k):
            return 400, "", {}, "ApiException"

        monkeypatch.setattr(ex, "_send", fake_send)
        op = {"id": "X:Y", "path": "/Acs/Api/X/Y", "method": "POST"}
        result = _run(ex.AcsProExecutor().execute(op, {"host": "https://acs:29204"}, {}, {}))
        assert result.success is False
        assert "400" in result.error and "ApiException" in result.error

    def test_negotiate_challenge_parser(self):
        from admz.modules.acs_pro.executor import _negotiate_challenge

        assert _negotiate_challenge("Negotiate oYGc, Basic realm=\"\"") == "oYGc"
        assert _negotiate_challenge("Negotiate, Basic realm=\"\"") is None
        assert _negotiate_challenge("") is None

    def test_no_host_fails_cleanly(self, monkeypatch):
        import admz.modules.acs_pro.executor as ex

        executor = ex.AcsProExecutor()
        result = _run(executor.execute({"id": "X:Y"}, {"host": ""}, {}, {}))
        assert result.success is False
        assert "not configured" in result.error

    def test_self_heals_false(self):
        from admz.modules.acs_pro.executor import AcsProExecutor

        assert AcsProExecutor().self_heals() is False
        assert AcsProExecutor().family == "acs-pro"


# --------------------------------------------------------------------------
# MCP surface grows only when enabled (the frozen 52 device tools are unchanged)
# --------------------------------------------------------------------------
class TestMcpSurface:
    def test_acs_tools_appended_when_enabled(self, monkeypatch):
        import admz.modules.acs_pro.config as cfg

        monkeypatch.setattr(cfg, "acs_enabled", lambda: True)

        from mcp.types import ListToolsRequest

        from admz.mcp.server import ADMZMCPServer
        from tests.test_mcp_tool_order import EXPECTED_TOOL_ORDER

        srv = ADMZMCPServer()
        names = _run(mcp_harness.tool_names(srv))

        from admz.modules.acs_pro.tools import tool_specs as acs_tool_specs

        # The frozen device tools come first, unchanged; the ACS tools append
        # after (count derived from the module so adding an ACS tool is fine).
        assert names[: len(EXPECTED_TOOL_ORDER)] == EXPECTED_TOOL_ORDER
        appended = names[len(EXPECTED_TOOL_ORDER):]
        assert "acs_find_camera_for_device" in appended
        assert "acs_search_events" in appended
        assert len(names) == len(EXPECTED_TOOL_ORDER) + len(acs_tool_specs())
        # The server resolves ACS handlers via the module registry (not the
        # static device TOOL_HANDLERS).
        assert any(
            s.tool.name == "acs_get_api_version"
            for s in srv.module_registry.tool_specs_all()
        )


class TestNoNegotiateToUnconfirmedHost:
    """GH #160 — outbound credential relay, not a reachability oracle.

    `negotiate.spn_for` derives the SPN from the host being probed, so
    `POST /api/acs/test` against an attacker-supplied address made ADMZ mint a
    Windows token for the attacker's service principal and send it to them.
    Kerberos fails for an unregistered SPN, SSPI falls back to NTLM, and the
    401 challenge leg returned a NetNTLMv2 response for the ADMZ service
    account — the account with rights against the live ACS install.

    #355 added authentication and an audit row to this route but left the
    target unvalidated, and its docstring called the residual risk a
    reachability oracle. It is worse than that, which is what these pin.
    """

    def test_the_spn_really_is_derived_from_the_probed_host(self):
        """The premise. If this stops being true the rest is moot."""
        from admz.modules.acs_pro.negotiate import spn_for
        assert spn_for("http://attacker.example:8080") == "HTTP/attacker.example"

    def test_executor_sends_no_authorization_when_forbidden(self):
        """`no_negotiate` must suppress the header entirely — not send an empty
        one, and not fall back to some other scheme."""
        import inspect
        from admz.modules.acs_pro import executor as ex
        src = inspect.getsource(ex.AcsProExecutor.execute)
        assert 'no_auth = bool(device.get("no_negotiate"))' in src
        assert "if not no_auth:" in src
        assert 'if auth_header is not None:' in src

    def test_the_401_challenge_leg_is_skipped_without_a_client(self):
        """The Type-3 message is where the NetNTLMv2 response actually leaves.
        Suppressing only the first header would still leak on the retry."""
        import inspect
        from admz.modules.acs_pro import executor as ex
        src = inspect.getsource(ex.AcsProExecutor.execute)
        assert "if status == 401 and neg_client is not None:" in src

    def test_probing_an_unconfigured_host_forbids_negotiate(self, monkeypatch):
        captured = {}

        from admz.modules.acs_pro import routes

        async def fake_run(catalog, executors, op, params, server):
            captured.update(server)
            class _R:
                success, error, parsed_data = True, None, {}
            return _R()

        monkeypatch.setattr(routes, "run_acs_op_direct", fake_run, raising=False)
        monkeypatch.setattr("admz.modules.acs_pro.config.base_url",
                            lambda: "https://real-acs.example:55756")
        self._post(routes, {"server_url": "http://attacker.example:8080"})
        assert captured.get("no_negotiate") is True

    def test_probing_the_configured_host_still_authenticates(self, monkeypatch):
        """The legitimate case must not regress: once the operator has saved a
        server, testing it is a full authenticated check."""
        captured = {}

        from admz.modules.acs_pro import routes

        async def fake_run(catalog, executors, op, params, server):
            captured.update(server)
            class _R:
                success, error, parsed_data = True, None, {}
            return _R()

        monkeypatch.setattr(routes, "run_acs_op_direct", fake_run, raising=False)
        monkeypatch.setattr("admz.modules.acs_pro.config.base_url",
                            lambda: "https://real-acs.example:55756")
        self._post(routes, {"server_url": "https://real-acs.example:55756"})
        assert captured.get("no_negotiate") is False

    @staticmethod
    def _post(routes, body):
        """Drive `acs_test` directly — the route is the unit under test, and a
        full TestClient would pull in the whole lifespan for one branch."""
        import asyncio

        class _Req:
            async def json(self):
                return body
            headers = {}
            client = None
            scope = {"type": "http", "headers": []}

        async def _go():
            import admz.api.context as ctxmod
            import admz.audit as audit
            import admz.auth as auth
            import admz.authz as authz

            async def _principal(_req):
                class _P:
                    name, is_anonymous, groups = "test\agent", False, []
                return _P()

            class _Ctx:
                catalog = None
                executors = {}

            saved = (auth.get_current_principal,
                     authz.require_authenticated_principal,
                     ctxmod.get_context, audit.record_event)
            auth.get_current_principal = _principal
            authz.require_authenticated_principal = lambda p: None
            ctxmod.get_context = lambda: _Ctx()
            audit.record_event = lambda *a, **k: None      # no real audit row
            try:
                return await routes.acs_test(_Req())
            finally:
                (auth.get_current_principal,
                 authz.require_authenticated_principal,
                 ctxmod.get_context, audit.record_event) = saved

        return asyncio.run(_go())


class TestExecutorHonoursNoNegotiate:
    """Behavioural, not source-string (review finding on #160).

    The first pass asserted on `inspect.getsource` phrasing, which pins wording
    and permits an equivalent leak written differently. These drive the real
    executor and assert on what left the process.
    """

    def _op(self):
        return {"id": "VersionFacade:GetApiVersion", "path": "/Acs/Api/v", "method": "GET"}

    def _run(self, monkeypatch, *, no_negotiate, status=401):
        """Execute one operation, capturing every request the executor makes."""
        import asyncio

        from admz.modules.acs_pro import executor as ex
        from admz.modules.acs_pro import negotiate

        sent, minted, continued = [], [], []

        # Recorded, not raised. The executor wraps `initial_header` in
        # `except Exception`, so an AssertionError thrown here is swallowed and
        # turns into a clean error result — which would let the leak tests pass
        # for the wrong reason. (Found writing these: the first version raised.)
        class _Client:
            def close(self):
                pass

        def _record(host):
            minted.append(host)
            return "Negotiate AAAA", _Client()

        monkeypatch.setattr(negotiate, "initial_header", _record)

        def _cont(_client, _token):
            continued.append(_token)
            return "Negotiate BBBB"

        monkeypatch.setattr(negotiate, "continued_header", _cont)

        async def _fake_send(http, method, url, headers, body):
            sent.append({"url": url, "headers": dict(headers)})
            # NTLM over HTTP: the 401 carries the Type-2 challenge token, and
            # that token is what a leaky client answers with a Type-3. A bare
            # `Negotiate` with no token cannot be continued at all, so using one
            # would make the leak tests pass without proving anything.
            return status, "", {"www-authenticate": "Negotiate T2TOKEN"}, "Unauthorized"

        monkeypatch.setattr(ex, "_send", _fake_send)

        server = {"device_id": "acs-server", "host": "https://attacker.example",
                  "verify_tls": False, "no_negotiate": no_negotiate}
        res = asyncio.run(
            ex.AcsProExecutor().execute(self._op(), server, {}, {}))
        return res, sent, minted, continued

    def test_no_token_is_minted_and_no_authorization_is_sent(self, monkeypatch):
        res, sent, minted, _ = self._run(monkeypatch, no_negotiate=True)
        assert minted == [], "a token was minted for a host nobody confirmed"
        assert len(sent) == 1, "the 401 challenge leg must not re-send"
        assert not any(k.lower() == "authorization" for k in sent[0]["headers"]), \
            f"Authorization leaked: {sent[0]['headers']}"
        assert res.status_code == 401          # reported, not retried

    def test_the_401_leg_does_not_run(self, monkeypatch):
        """The Type-3 message is where the NetNTLMv2 response actually leaves,
        so suppressing only the first header would still leak on the retry.
        `continued_header` raises if reached."""
        _res, sent, _minted, continued = self._run(monkeypatch, no_negotiate=True)
        assert continued == [], "the Type-3 leg ran — that is where the response leaves"
        assert len(sent) == 1

    def test_without_the_flag_it_still_authenticates(self, monkeypatch):
        """Guard the guard: if the executor never negotiated at all, the tests
        above would pass for the wrong reason."""
        _res, sent, minted, continued = self._run(monkeypatch, no_negotiate=False)
        assert minted == ["https://attacker.example"]      # it did negotiate
        assert continued == ["T2TOKEN"]                    # and ran the 401 leg
        assert len(sent) == 2
        assert any(k.lower() == "authorization" for k in sent[0]["headers"])


async def _async(v):
    return v


class _MemSettings:
    def __init__(self):
        self._d = {}

    def set(self, k, v):
        self._d[k] = v

    def get(self, k, d=None):
        return self._d.get(k, d)


class TestConfigWriteIsPrivileged:
    """GH #160, the review's critical finding: the first fix was bypassable one
    request earlier.

    `no_negotiate` keys off "is this the saved host?", and saving needed only a
    non-anonymous identity. So an ordinary authenticated user saved
    `https://attacker`, and from then on it *was* the configured host — Test
    authenticated against it, and the pollers did too, on their own schedule.

    Escalated to the reveal gate, matching this file's precedent for
    `webhook-token/regenerate`: both hand over a live credential. Testing is
    deliberately not escalated, so an ordinary operator can still check
    reachability while setting the module up.
    """

    @staticmethod
    def _call(routes, fn, body, *, groups):
        """Drive a route with a principal holding `groups`, through the REAL
        authz helpers. Asserting on `inspect.getsource` was the first attempt
        and it did not work: dropping the *call* while leaving the import left
        the phrase in the source, so a positive control that removed the gate
        still passed."""
        import asyncio

        from admz.api import context as ctxmod
        from admz import audit, auth

        class _P:
            name, is_anonymous = "test\agent", False

            def __init__(self, g):
                self.groups = g

        class _Req:
            async def json(self):
                return body

        class _Ctx:
            catalog = None
            executors = {}

        async def _go():
            saved = (auth.get_current_principal, ctxmod.get_context, audit.record_event)
            auth.get_current_principal = lambda _r: _async(_P(groups))
            ctxmod.get_context = lambda: _Ctx()
            audit.record_event = lambda *a, **k: None
            try:
                return await fn(_Req())
            finally:
                (auth.get_current_principal, ctxmod.get_context,
                 audit.record_event) = saved

        return asyncio.run(_go())

    def test_an_unprivileged_user_cannot_point_admz_at_a_host(self, monkeypatch):
        """The critical one. Behavioural, through the real reveal check."""
        from fastapi import HTTPException
        import pytest

        from admz.modules.acs_pro import config as cfgmod
        from admz.modules.acs_pro import routes

        monkeypatch.setattr(cfgmod, "_settings", lambda: _MemSettings())
        with pytest.raises(HTTPException) as exc:
            self._call(routes, routes.acs_save_config,
                       {"enabled": True, "server_url": "https://attacker.example"},
                       groups=[])
        assert exc.value.status_code == 403

    def test_testing_a_connection_stays_open_to_any_authenticated_user(self):
        """The asymmetry is the point — escalating this one would stop an
        operator setting the module up at all. An unprivileged caller must get
        past the gate (the probe itself then fails on a nonexistent host)."""
        from admz.modules.acs_pro import routes

        res = self._call(routes, routes.acs_test,
                         {"server_url": "http://127.0.0.1:9"}, groups=[])
        assert res is not None          # reached the probe, not a 403

    def test_userinfo_does_not_survive_into_the_stored_config(self, monkeypatch):
        """The test path stripped it and the save path did not, so
        `https://real@evil/` was refused unsaved and authenticated once saved."""
        from admz.modules.acs_pro import config as cfgmod
        saved = {}

        class _S:
            def set(self, k, v):
                saved[k] = v

            def get(self, k, d=None):
                return saved.get(k, d)

        monkeypatch.setattr(cfgmod, "_settings", lambda: _S())
        out = cfgmod.save_acs_config(enabled=True, server_url="https://real@evil/",
                                     port=55756, verify_tls=False,
                                     client_machine_name="")
        assert "@" not in out["server_url"], out["server_url"]


class TestCanonicalHostComparison:
    """Raw string equality dropped authentication against the real server for
    harmless spelling differences (review finding)."""

    def _c(self, u):
        from admz.modules.acs_pro.routes import _canonical
        return _canonical(u)

    def test_equivalent_spellings_fold_together(self):
        base = self._c("https://acs.example:55756")
        for other in ("https://ACS.Example:55756/",
                      "https://acs.example.:55756",
                      "https://acs.example:55756"):
            assert self._c(other) == base, other

    def test_default_ports_fold(self):
        assert self._c("https://acs.example:443") == self._c("https://acs.example")
        assert self._c("http://acs.example:80") == self._c("http://acs.example")

    def test_different_hosts_do_not_fold(self):
        assert self._c("https://acs.example") != self._c("https://evil.example")
        assert self._c("https://acs.example:55756") != self._c("https://acs.example:1234")

    def test_userinfo_cannot_smuggle_a_match(self):
        """`https://real@evil` must not canonicalise to the real host."""
        assert self._c("https://acs.example@evil.example") != self._c("https://acs.example")
