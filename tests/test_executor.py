"""Tests for VapixExecutor — template resolution, type coercion, response parsing."""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from xml.etree import ElementTree

import httpx
import pytest

from admz.executor.vapix import VapixExecutor, _BearerAuth


@pytest.fixture
def executor():
    return VapixExecutor()


# ------------------------------------------------------------------
# _coerce_value
# ------------------------------------------------------------------


class TestCoerceValue:
    def test_int(self):
        assert VapixExecutor._coerce_value("42", "int") == 42

    def test_int_negative(self):
        assert VapixExecutor._coerce_value("-5", "int") == -5

    def test_int_invalid(self):
        with pytest.raises(ValueError):
            VapixExecutor._coerce_value("abc", "int")

    def test_float(self):
        assert VapixExecutor._coerce_value("3.14", "float") == 3.14

    def test_bool_true_variants(self):
        assert VapixExecutor._coerce_value("true", "bool") is True
        assert VapixExecutor._coerce_value("True", "bool") is True
        assert VapixExecutor._coerce_value("1", "bool") is True
        assert VapixExecutor._coerce_value("yes", "bool") is True

    def test_bool_false_variants(self):
        assert VapixExecutor._coerce_value("false", "bool") is False
        assert VapixExecutor._coerce_value("0", "bool") is False
        assert VapixExecutor._coerce_value("no", "bool") is False

    def test_array(self):
        result = VapixExecutor._coerce_value('["a", "b"]', "array")
        assert result == ["a", "b"]

    def test_array_of_ints(self):
        result = VapixExecutor._coerce_value("[1, 2, 3]", "array")
        assert result == [1, 2, 3]

    def test_object(self):
        result = VapixExecutor._coerce_value('{"key": "val"}', "object")
        assert result == {"key": "val"}

    def test_str_default(self):
        assert VapixExecutor._coerce_value("hello", "str") == "hello"

    def test_unknown_type_returns_str(self):
        assert VapixExecutor._coerce_value("hello", "unknown") == "hello"


# ------------------------------------------------------------------
# _resolve_template
# ------------------------------------------------------------------


class TestResolveTemplate:
    def setup_method(self):
        self.executor = VapixExecutor()

    def test_whole_value_str(self):
        result = self.executor._resolve_template("{host}", {"host": "10.0.0.1"})
        assert result == "10.0.0.1"

    def test_whole_value_int(self):
        result = self.executor._resolve_template("{port:int}", {"port": "8883"})
        assert result == 8883

    def test_whole_value_bool(self):
        result = self.executor._resolve_template("{enabled:bool}", {"enabled": "true"})
        assert result is True

    def test_whole_value_array(self):
        result = self.executor._resolve_template(
            "{servers:array}", {"servers": '["ntp1.example.com"]'}
        )
        assert result == ["ntp1.example.com"]

    def test_whole_value_missing_returns_none(self):
        result = self.executor._resolve_template("{missing}", {})
        assert result is None

    def test_embedded_placeholders(self):
        result = self.executor._resolve_template(
            "{panSpeed},{tiltSpeed}", {"panSpeed": "50", "tiltSpeed": "-30"}
        )
        assert result == "50,-30"

    def test_embedded_partial_missing(self):
        """If one placeholder is missing, it stays as-is."""
        result = self.executor._resolve_template(
            "{panSpeed},{tiltSpeed}", {"panSpeed": "50"}
        )
        assert result == "50,{tiltSpeed}"

    def test_literal_string(self):
        result = self.executor._resolve_template("update", {"x": "1"})
        assert result == "update"

    def test_nested_dict(self):
        template = {
            "server": {
                "protocol": "{protocol}",
                "host": "{host}",
                "port": "{port:int}",
            },
            "clientId": "{clientId}",
        }
        params = {"protocol": "tcp", "host": "broker.local", "port": "1883", "clientId": "cam1"}
        result = self.executor._resolve_template(template, params)
        assert result == {
            "server": {"protocol": "tcp", "host": "broker.local", "port": 1883},
            "clientId": "cam1",
        }

    def test_nested_dict_omits_missing(self):
        template = {
            "required": "{a}",
            "optional": "{b}",
        }
        result = self.executor._resolve_template(template, {"a": "yes"})
        assert result == {"required": "yes"}
        assert "optional" not in result

    def test_nested_dict_all_missing_returns_none(self):
        template = {"x": "{missing}"}
        result = self.executor._resolve_template(template, {})
        assert result is None

    def test_list(self):
        template = ["{a}", "{b}"]
        result = self.executor._resolve_template(template, {"a": "1", "b": "2"})
        assert result == ["1", "2"]

    def test_passthrough_numbers(self):
        result = self.executor._resolve_template(42, {})
        assert result == 42

    def test_passthrough_bool(self):
        result = self.executor._resolve_template(True, {})
        assert result is True

    def test_full_json_rpc_body(self):
        """Simulate a real JSON-RPC body template with typed placeholders."""
        template = {
            "apiVersion": "1.0",
            "method": "setNTPClientConfiguration",
            "params": {
                "enabled": "{enabled:bool}",
                "serversSource": "{serversSource}",
                "staticServers": "{staticServers:array}",
            },
        }
        params = {
            "enabled": "true",
            "serversSource": "static",
            "staticServers": '["ntp1.example.com", "ntp2.example.com"]',
        }
        result = self.executor._resolve_template(template, params)
        assert result["apiVersion"] == "1.0"
        assert result["method"] == "setNTPClientConfiguration"
        assert result["params"]["enabled"] is True
        assert result["params"]["serversSource"] == "static"
        assert result["params"]["staticServers"] == ["ntp1.example.com", "ntp2.example.com"]


# ------------------------------------------------------------------
# _build_json_rpc integration
# ------------------------------------------------------------------


class TestBuildJsonRpc:
    def setup_method(self):
        self.executor = VapixExecutor()

    def test_typed_placeholders(self):
        """Typed placeholders are coerced in the JSON body."""
        operation = {
            "request": {
                "content_type": "application/json",
                "body": {
                    "apiVersion": "1.0",
                    "method": "find",
                    "params": {
                        "duration": "{duration:int}",
                    },
                },
            },
        }
        request = self.executor._build_json_rpc(operation, "/axis-cgi/findmydevice.cgi", {"duration": "30"})
        assert request.json_body["params"]["duration"] == 30

    def test_nested_object_preserved(self):
        """Nested objects in body template are resolved recursively."""
        operation = {
            "request": {
                "content_type": "application/json",
                "body": {
                    "apiVersion": "1.0",
                    "method": "configureClient",
                    "params": {
                        "server": {
                            "protocol": "{protocol}",
                            "host": "{host}",
                            "port": "{port:int}",
                        },
                        "cleanSession": "{cleanSession:bool}",
                    },
                },
            },
        }
        params = {"protocol": "tcp", "host": "broker", "port": "1883", "cleanSession": "true"}
        request = self.executor._build_json_rpc(operation, "/axis-cgi/mqtt/client.cgi", params)
        body = request.json_body
        assert body["params"]["server"]["port"] == 1883
        assert body["params"]["cleanSession"] is True
        assert body["params"]["server"]["protocol"] == "tcp"

    def test_backward_compat_no_template(self):
        """Operations without typed placeholders fall back to putting params under 'params'."""
        operation = {
            "request": {
                "content_type": "application/json",
                "body": {
                    "apiVersion": "1.0",
                    "method": "getAllProperties",
                },
            },
        }
        # No placeholders in template — params go under "params" key
        request = self.executor._build_json_rpc(operation, "/axis-cgi/basicdeviceinfo.cgi", {})
        # No params provided and no placeholders → body should just have the template
        assert request.json_body["apiVersion"] == "1.0"
        assert request.json_body["method"] == "getAllProperties"

    def test_timeout_from_request_spec(self):
        operation = {
            "request": {
                "content_type": "application/json",
                "timeout": 120,
                "body": {
                    "apiVersion": "1.0",
                    "method": "test",
                },
            },
        }
        request = self.executor._build_json_rpc(operation, "/test", {})
        assert request.timeout_override == 120.0

    def test_array_param(self):
        """Array params are correctly coerced from JSON string."""
        operation = {
            "request": {
                "content_type": "application/json",
                "body": {
                    "apiVersion": "1.0",
                    "method": "setPorts",
                    "params": {
                        "ports": "{ports:array}",
                    },
                },
            },
        }
        params = {"ports": '[{"port": "1", "normalState": "open"}]'}
        request = self.executor._build_json_rpc(operation, "/test", params)
        assert request.json_body["params"]["ports"] == [{"port": "1", "normalState": "open"}]


# ------------------------------------------------------------------
# _build_legacy_cgi integration
# ------------------------------------------------------------------


class TestBuildLegacyCgi:
    def setup_method(self):
        self.executor = VapixExecutor()

    def test_compound_placeholder(self):
        """Compound placeholders like {panSpeed},{tiltSpeed} are resolved."""
        operation = {
            "method": "GET",
            "request": {
                "query": {
                    "continuouspantiltmove": "{panSpeed},{tiltSpeed}",
                    "camera": "{camera}",
                },
            },
        }
        params = {"panSpeed": "50", "tiltSpeed": "-30", "camera": "1"}
        request = self.executor._build_legacy_cgi(operation, "/axis-cgi/com/ptz.cgi", params)
        assert request.query_params["continuouspantiltmove"] == "50,-30"
        assert request.query_params["camera"] == "1"

    def test_literal_values_preserved(self):
        """Non-placeholder values in query template are kept as-is."""
        operation = {
            "method": "GET",
            "request": {
                "query": {
                    "action": "update",
                    "user": "{username}",
                },
            },
        }
        params = {"username": "admin"}
        request = self.executor._build_legacy_cgi(operation, "/axis-cgi/pwdgrp.cgi", params)
        assert request.query_params["action"] == "update"
        assert request.query_params["user"] == "admin"

    def test_user_params_added(self):
        """User params not in template are added to query."""
        operation = {
            "method": "GET",
            "request": {
                "query": {
                    "action": "update",
                },
            },
        }
        params = {"root.Image.I0.Resolution": "1920x1080"}
        request = self.executor._build_legacy_cgi(operation, "/axis-cgi/param.cgi", params)
        assert request.query_params["action"] == "update"
        assert request.query_params["root.Image.I0.Resolution"] == "1920x1080"

    def test_timeout_from_request_spec(self):
        operation = {
            "method": "GET",
            "request": {
                "query": {},
                "timeout": 120,
            },
        }
        request = self.executor._build_legacy_cgi(operation, "/test", {})
        assert request.timeout_override == 120.0

    def test_missing_placeholder_omitted(self):
        """Whole-value placeholders that aren't filled are omitted."""
        operation = {
            "method": "GET",
            "request": {
                "query": {
                    "action": "list",
                    "group": "{group}",
                },
            },
        }
        request = self.executor._build_legacy_cgi(operation, "/axis-cgi/param.cgi", {})
        assert request.query_params["action"] == "list"
        assert "group" not in request.query_params


# ------------------------------------------------------------------
# _build_config_rest integration
# ------------------------------------------------------------------


class TestBuildConfigRest:
    def setup_method(self):
        self.executor = VapixExecutor()

    def test_timeout_from_request_spec(self):
        operation = {
            "method": "GET",
            "base_path": "/config/rest",
            "path": "/test",
            "request": {"timeout": 30},
        }
        request = self.executor._build_config_rest(operation, {})
        assert request.timeout_override == 30.0


# ------------------------------------------------------------------
# Binary response parsing
# ------------------------------------------------------------------


class TestBinaryResponse:
    def setup_method(self):
        self.executor = VapixExecutor()

    def test_content_type_extension(self):
        assert VapixExecutor._content_type_extension("application/x-tar") == ".tar"
        assert VapixExecutor._content_type_extension("application/octet-stream") == ".bin"
        assert VapixExecutor._content_type_extension("image/jpeg") == ".jpg"
        assert VapixExecutor._content_type_extension("unknown/type") == ".bin"


# ------------------------------------------------------------------
# _xml_to_dict
# ------------------------------------------------------------------


class TestXmlToDict:
    def test_simple_element(self):
        xml = "<root>hello</root>"
        root = ElementTree.fromstring(xml)
        result = VapixExecutor._xml_to_dict(root)
        assert result == {"root": "hello"}

    def test_attributes(self):
        xml = '<disk diskid="SD_DISK" totalsize="7500"/>'
        root = ElementTree.fromstring(xml)
        result = VapixExecutor._xml_to_dict(root)
        assert result == {
            "disk": {"@diskid": "SD_DISK", "@totalsize": "7500"}
        }

    def test_nested_children(self):
        xml = "<root><child1>val1</child1><child2>val2</child2></root>"
        root = ElementTree.fromstring(xml)
        result = VapixExecutor._xml_to_dict(root)
        assert result == {"root": {"child1": "val1", "child2": "val2"}}

    def test_repeated_children(self):
        xml = "<root><item>a</item><item>b</item><item>c</item></root>"
        root = ElementTree.fromstring(xml)
        result = VapixExecutor._xml_to_dict(root)
        assert result == {"root": {"item": ["a", "b", "c"]}}

    def test_namespace_stripping(self):
        xml = '<ns:root xmlns:ns="http://example.com"><ns:child>val</ns:child></ns:root>'
        root = ElementTree.fromstring(xml)
        result = VapixExecutor._xml_to_dict(root)
        assert result == {"root": {"child": "val"}}

    def test_empty_element(self):
        xml = "<root><empty/></root>"
        root = ElementTree.fromstring(xml)
        result = VapixExecutor._xml_to_dict(root)
        assert result == {"root": {"empty": None}}

    def test_mixed_attrs_and_text(self):
        xml = '<item id="42">hello</item>'
        root = ElementTree.fromstring(xml)
        result = VapixExecutor._xml_to_dict(root)
        assert result == {"item": {"@id": "42", "#text": "hello"}}

    def test_vapix_disk_response(self):
        """Realistic VAPIX disk list XML."""
        xml = """<?xml version="1.0"?>
        <root>
            <disks>
                <disk diskid="SD_DISK" totalsize="7500" freesize="6200"
                      cleanuplevel="90" mounted="yes"/>
            </disks>
        </root>"""
        root = ElementTree.fromstring(xml)
        result = VapixExecutor._xml_to_dict(root)
        inner = result["root"]
        disk = inner["disks"]["disk"]
        assert disk["@diskid"] == "SD_DISK"
        assert disk["@totalsize"] == "7500"
        assert disk["@mounted"] == "yes"


# ------------------------------------------------------------------
# XML response parsing integration
# ------------------------------------------------------------------


class TestXmlResponseParsing:
    def setup_method(self):
        self.executor = VapixExecutor()

    def test_xml_format_parsed(self):
        """XML format responses are parsed to dict."""
        operation = {
            "response": {"format": "xml"},
        }
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.text = "<root><status>OK</status></root>"

        result = self.executor._parse_response(
            operation, response, "test:op", "dev1", 10.0
        )
        assert result.success is True
        assert result.parsed_data == {"status": "OK"}

    def test_xml_parse_failure_fallback(self):
        """Invalid XML falls back to raw text."""
        operation = {
            "response": {"format": "xml"},
        }
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.text = "not valid xml <<<"

        result = self.executor._parse_response(
            operation, response, "test:op", "dev1", 10.0
        )
        assert result.success is True
        assert result.parsed_data == "not valid xml <<<"
        assert any("XML parse failed" in w for w in result.warnings)


# ------------------------------------------------------------------
# Expected timeout
# ------------------------------------------------------------------


class TestExpectTimeout:
    def setup_method(self):
        self.executor = VapixExecutor()

    @pytest.mark.anyio
    async def test_expect_timeout_returns_success(self):
        """Operations with expect_timeout treat timeout as success."""
        operation = {
            "id": "restart.cgi:restart",
            "method": "GET",
            "request": {"query": {}},
            "response": {"format": "text", "expect_timeout": True},
            "_endpoint": "/axis-cgi/restart.cgi",
            "_generation": "legacy-cgi",
        }
        device = {"device_id": "cam1", "host": "192.168.1.100"}
        credentials = {"username": "root", "password": "pass"}

        with patch("admz.executor.vapix.httpx.AsyncHTTPTransport"), \
             patch("admz.executor.vapix.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.TimeoutException("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.executor.execute(
                operation, device, credentials, {}
            )

        assert result.success is True
        assert any("expected" in w.lower() for w in result.warnings)

    @pytest.mark.anyio
    async def test_normal_timeout_returns_error(self):
        """Operations without expect_timeout treat timeout as error."""
        operation = {
            "id": "param.cgi:list",
            "method": "GET",
            "request": {"query": {}},
            "response": {"format": "text"},
            "_endpoint": "/axis-cgi/param.cgi",
            "_generation": "legacy-cgi",
        }
        device = {"device_id": "cam1", "host": "192.168.1.100"}
        credentials = {"username": "root", "password": "pass"}

        with patch("admz.executor.vapix.httpx.AsyncHTTPTransport"), \
             patch("admz.executor.vapix.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.TimeoutException("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.executor.execute(
                operation, device, credentials, {}
            )

        assert result.success is False
        assert "timed out" in result.error


# ------------------------------------------------------------------
# Retry config
# ------------------------------------------------------------------


class TestRetryConfig:
    def test_default_retries(self):
        executor = VapixExecutor()
        assert executor._retries == 1

    def test_custom_retries(self):
        executor = VapixExecutor(retries=3)
        assert executor._retries == 3

    def test_retries_zero(self):
        executor = VapixExecutor(retries=0)
        assert executor._retries == 0


# ------------------------------------------------------------------
# Bearer auth
# ------------------------------------------------------------------


class TestBearerAuth:
    def test_bearer_auth_class(self):
        auth = _BearerAuth("my-token-123")
        request = httpx.Request("GET", "http://example.com")
        flow = auth.auth_flow(request)
        modified = next(flow)
        assert modified.headers["Authorization"] == "Bearer my-token-123"

    def test_resolve_auth_bearer(self):
        device = {"auth": {"http": "bearer"}}
        credentials = {"username": "root", "password": "", "token": "abc123"}
        auth = VapixExecutor._resolve_auth(device, credentials, "http")
        assert isinstance(auth, _BearerAuth)
        # Verify the token is set correctly
        request = httpx.Request("GET", "http://example.com")
        flow = auth.auth_flow(request)
        modified = next(flow)
        assert modified.headers["Authorization"] == "Bearer abc123"

    def test_resolve_auth_bearer_falls_back_to_password(self):
        """If no 'token' field, use password as token."""
        device = {"auth": {"http": "bearer"}}
        credentials = {"username": "root", "password": "my-password"}
        auth = VapixExecutor._resolve_auth(device, credentials, "http")
        assert isinstance(auth, _BearerAuth)
        request = httpx.Request("GET", "http://example.com")
        flow = auth.auth_flow(request)
        modified = next(flow)
        assert modified.headers["Authorization"] == "Bearer my-password"

    def test_resolve_auth_digest_unchanged(self):
        """Existing digest auth still works."""
        device = {"auth": {"http": "digest"}}
        credentials = {"username": "root", "password": "pass"}
        auth = VapixExecutor._resolve_auth(device, credentials, "http")
        assert isinstance(auth, httpx.DigestAuth)

    def test_resolve_auth_basic_unchanged(self):
        """Existing basic auth still works."""
        device = {"auth": {"https": "basic"}}
        credentials = {"username": "root", "password": "pass"}
        auth = VapixExecutor._resolve_auth(device, credentials, "https")
        assert isinstance(auth, httpx.BasicAuth)

    def test_resolve_auth_none_unchanged(self):
        """Auth method 'none' returns None."""
        device = {"auth": {"http": "none"}}
        credentials = {"username": "root", "password": "pass"}
        auth = VapixExecutor._resolve_auth(device, credentials, "http")
        assert auth is None
