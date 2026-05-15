"""Tests for VapixExecutor.execute and _parse_response using an httpx mock transport."""

import httpx
import pytest

from admz.executor.vapix import VapixExecutor


# Capture the real AsyncClient once so we can wrap it later without recursing.
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def patch_httpx(monkeypatch, handler):
    """Patch httpx.AsyncClient inside admz.executor.vapix to use a MockTransport."""
    transport = httpx.MockTransport(handler)

    def factory(*args, **kwargs):
        # Drop kwargs the MockTransport doesn't understand
        kwargs.pop("verify", None)
        kwargs["transport"] = transport
        return _REAL_ASYNC_CLIENT(*args, **kwargs)

    monkeypatch.setattr("admz.executor.vapix.httpx.AsyncClient", factory)


@pytest.fixture
def device():
    return {
        "device_id": "cam-01",
        "host": "192.168.1.100",
        "port": 443,
        "https": True,
    }


@pytest.fixture
def credentials():
    return {"username": "admin", "password": "secret"}


@pytest.fixture
def legacy_op():
    return {
        "id": "param.cgi:list",
        "_generation": "legacy-cgi",
        "_endpoint": "/axis-cgi/param.cgi",
        "method": "GET",
        "request": {"query": {"action": "list"}},
        "response": {"format": "text"},
    }


@pytest.fixture
def json_op():
    return {
        "id": "basicdeviceinfo.cgi:getAllProperties",
        "_generation": "json-rpc",
        "_endpoint": "/axis-cgi/basicdeviceinfo.cgi",
        "method": "POST",
        "request": {
            "body": {"apiVersion": "1.0", "method": "getAllProperties"}
        },
        "response": {"format": "json", "data_path": "data.propertyList"},
    }


class TestExecute:

    @pytest.mark.asyncio
    async def test_legacy_cgi_success(
        self, device, credentials, legacy_op, monkeypatch
    ):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["method"] = request.method
            return httpx.Response(
                200,
                text="root.Image.I0.Resolution=1920x1080\nroot.Image.I0.Compression=30",
            )

        patch_httpx(monkeypatch, handler)
        executor = VapixExecutor(timeout=2.0)
        result = await executor.execute(legacy_op, device, credentials, {"group": "root.Image"})

        assert result.success is True
        assert result.status_code == 200
        assert "1920x1080" in result.parsed_data
        assert captured["method"] == "GET"
        assert "192.168.1.100" in captured["url"]

    @pytest.mark.asyncio
    async def test_json_rpc_success(
        self, device, credentials, json_op, monkeypatch
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "apiVersion": "1.0",
                    "data": {
                        "propertyList": {
                            "ProdNbr": "P3245-V",
                            "Version": "11.8.60",
                        }
                    },
                },
            )

        patch_httpx(monkeypatch, handler)
        executor = VapixExecutor(timeout=2.0)
        result = await executor.execute(json_op, device, credentials, {})

        assert result.success is True
        assert result.parsed_data["ProdNbr"] == "P3245-V"

    @pytest.mark.asyncio
    async def test_returns_401_as_failure(
        self, device, credentials, legacy_op, monkeypatch
    ):
        def handler(request):
            return httpx.Response(401, text="Unauthorized")

        patch_httpx(monkeypatch, handler)
        executor = VapixExecutor(timeout=2.0)
        result = await executor.execute(legacy_op, device, credentials, {})

        assert result.success is False
        assert result.status_code == 401
        assert "Authentication failed" in result.error

    @pytest.mark.asyncio
    async def test_returns_500_as_failure(
        self, device, credentials, legacy_op, monkeypatch
    ):
        def handler(request):
            return httpx.Response(500, text="Internal Server Error")

        patch_httpx(monkeypatch, handler)
        executor = VapixExecutor(timeout=2.0)
        result = await executor.execute(legacy_op, device, credentials, {})

        assert result.success is False
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_no_host_returns_error(self, credentials, legacy_op):
        executor = VapixExecutor(timeout=2.0)
        result = await executor.execute(
            legacy_op, {"device_id": "x", "host": ""}, credentials, {}
        )
        assert result.success is False
        assert "No host" in result.error

    @pytest.mark.asyncio
    async def test_json_rpc_error_in_body(
        self, device, credentials, json_op, monkeypatch
    ):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "apiVersion": "1.0",
                    "error": {"code": -1, "message": "Bad parameter"},
                },
            )

        patch_httpx(monkeypatch, handler)
        executor = VapixExecutor(timeout=2.0)
        result = await executor.execute(json_op, device, credentials, {})

        assert result.success is False
        assert "Bad parameter" in result.error

    @pytest.mark.asyncio
    async def test_text_error_prefix(self, device, credentials, monkeypatch):
        op = {
            "id": "param.cgi:update",
            "_generation": "legacy-cgi",
            "_endpoint": "/axis-cgi/param.cgi",
            "method": "GET",
            "request": {"query": {"action": "update"}},
            "response": {"format": "text", "error_prefix": "# Error"},
        }

        def handler(request):
            return httpx.Response(200, text="# Error: parameter not found")

        patch_httpx(monkeypatch, handler)
        executor = VapixExecutor(timeout=2.0)
        result = await executor.execute(op, device, credentials, {})

        assert result.success is False
        assert "Error" in result.error

    @pytest.mark.asyncio
    async def test_service_impact_added_as_warning(
        self, device, credentials, monkeypatch
    ):
        op = {
            "id": "param.cgi:update",
            "_generation": "legacy-cgi",
            "_endpoint": "/axis-cgi/param.cgi",
            "method": "GET",
            "request": {"query": {"action": "update"}},
            "response": {"format": "text"},
            "service_impact": "Video stream briefly disrupted",
        }

        def handler(request):
            return httpx.Response(200, text="OK")

        patch_httpx(monkeypatch, handler)
        executor = VapixExecutor(timeout=2.0)
        result = await executor.execute(op, device, credentials, {})

        assert result.success is True
        assert "Video stream briefly disrupted" in result.warnings

    @pytest.mark.asyncio
    async def test_duration_is_recorded(
        self, device, credentials, legacy_op, monkeypatch
    ):
        def handler(request):
            return httpx.Response(200, text="OK")

        patch_httpx(monkeypatch, handler)
        executor = VapixExecutor(timeout=2.0)
        result = await executor.execute(legacy_op, device, credentials, {})

        assert result.duration_ms is not None
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_https_false_uses_http_scheme(
        self, credentials, legacy_op, monkeypatch
    ):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            return httpx.Response(200, text="OK")

        patch_httpx(monkeypatch, handler)
        executor = VapixExecutor(timeout=2.0)
        device = {
            "device_id": "cam-01",
            "host": "10.0.0.5",
            "https": False,
            "port": 80,
        }
        await executor.execute(legacy_op, device, credentials, {})
        assert captured["url"].startswith("http://10.0.0.5")

    @pytest.mark.asyncio
    async def test_user_params_added_to_query_string(
        self, device, credentials, legacy_op, monkeypatch
    ):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            return httpx.Response(200, text="OK")

        patch_httpx(monkeypatch, handler)
        executor = VapixExecutor(timeout=2.0)
        await executor.execute(
            legacy_op,
            device,
            credentials,
            {"root.Image.I0.Resolution": "1920x1080"},
        )
        assert "root.Image.I0.Resolution" in captured["url"]
        assert "1920x1080" in captured["url"]
