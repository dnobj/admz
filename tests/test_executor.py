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
# Issue #10 — config-rest path parameter injection guard
# ------------------------------------------------------------------


class TestSanitizePathParamRejects:
    """config-rest is the only generation that puts caller params in the URL
    *path*, and those params arrive from untrusted surfaces (MCP tool call,
    chat turn, REST body). httpx cooperates with the attacker here: it
    resolves "."/".." client-side and honours "?"/"#", so a raw substitution
    lets a caller retarget an authenticated request to any endpoint on the
    device."""

    @pytest.mark.parametrize(
        "value,reason",
        [
            ("..", "parent-segment"),
            ("../..", "repeated-parent"),
            (".", "bare-dot-segment"),
            ("a/b", "embedded-separator"),
            ("x/../../y", "middle-segment-traversal"),
            ("x?y=1", "query-injection"),
            ("x#f", "fragment-truncation"),
            ("a\\b", "backslash-separator"),
            ("%2e", "pre-encoded-dot"),
            ("%2e%2e", "pre-encoded-parent"),
            ("%2F", "pre-encoded-separator-upper"),
            ("%2f", "pre-encoded-separator-lower"),
            ("..%2f..", "mixed-encoding-traversal"),
            ("%252e", "double-encoded-dot"),
            ("%252f", "double-encoded-separator"),
            ("a%5Cb", "pre-encoded-backslash"),
            ("", "empty-collapses-segment"),
            ("a\nb", "control-character"),
        ],
    )
    def test_rejects_shape_changing(self, value, reason):
        from admz.executor.vapix import PathParamRejected, _sanitize_path_param

        with pytest.raises(PathParamRejected):
            _sanitize_path_param("id1", value)

    def test_rejection_names_the_parameter(self):
        """The caller must learn which param was refused and why — a silent
        strip would just produce a confusing 404 from the device."""
        from admz.executor.vapix import PathParamRejected, _sanitize_path_param

        with pytest.raises(PathParamRejected) as exc:
            _sanitize_path_param("alias", "../../axis-cgi/admin/pwdgrp.cgi")
        assert "alias" in str(exc.value)
        assert ".." in str(exc.value)


class TestSanitizePathParamAccepts:
    """Paired accept table — the guard must not be satisfied by rejecting
    everything. These are real catalogued id shapes."""

    @pytest.mark.parametrize(
        "value,expected,reason",
        [
            # event-schedules ids are dotted (facets/event_schedules.py)
            ("com.axis.schedules.weekends", "com.axis.schedules.weekends", "dotted-id"),
            # siren-and-light {id1} is a profile NAME, not an opaque id
            ("SIP", "SIP", "profile-name"),
            # cert {alias} is an operator-chosen label; spaces are legitimate
            ("My Cert 2024", "My%20Cert%202024", "alias-with-space"),
            # event-mqtt-bridge eventFilter/subscription ids are ordinals
            ("0", "0", "ordinal"),
            (
                "550e8400-e29b-41d4-a716-446655440000",
                "550e8400-e29b-41d4-a716-446655440000",
                "uuid",
            ),
            ("root.Network.eth0", "root.Network.eth0", "dotted-param-path"),
            ("profile-1_x", "profile-1_x", "hyphen-underscore"),
            ("Kamera-\xd6", "Kamera-%C3%96", "non-ascii-utf8"),
        ],
    )
    def test_accepts_legitimate_values(self, value, expected, reason):
        from admz.executor.vapix import _sanitize_path_param

        assert _sanitize_path_param("id1", value) == expected

    def test_unreserved_values_pass_through_byte_identical(self):
        """Encoding must not change values that already work in production."""
        from admz.executor.vapix import _sanitize_path_param

        for value in (
            "com.axis.schedules.office_hours",
            "com.axis.action.fixed.play.audioclip",
            "Camera1Profile1",
        ):
            assert _sanitize_path_param("id1", value) == value


class TestConfigRestPathSubstitution:
    """The guard applied at the substitution site (_build_config_rest)."""

    def setup_method(self):
        self.executor = VapixExecutor()

    def test_final_segment_substituted_and_body_stripped(self):
        req = self.executor._build_config_rest(
            {
                "method": "PATCH",
                "base_path": "/config/rest/event-schedules/v2beta",
                "path": "/schedules/{id1}",
            },
            {"id1": "com.axis.schedules.weekends", "data": {"name": "W"}},
        )
        assert req.path == (
            "/config/rest/event-schedules/v2beta/schedules/"
            "com.axis.schedules.weekends"
        )
        assert req.json_body == {"data": {"name": "W"}}

    def test_middle_segment_placeholder_is_guarded(self):
        """cert:generateCSR is /certificates/{alias}/get_csr — an unencoded
        separator here retargets the request rather than 404ing."""
        from admz.executor.vapix import PathParamRejected

        op = {
            "method": "POST",
            "base_path": "/config/rest/cert/v1",
            "path": "/certificates/{alias}/get_csr",
        }
        with pytest.raises(PathParamRejected):
            self.executor._build_config_rest(op, {"alias": "../../../param/v2beta"})

        ok = self.executor._build_config_rest(op, {"alias": "My Cert"})
        assert ok.path == "/config/rest/cert/v1/certificates/My%20Cert/get_csr"

    def test_both_placeholders_guarded_in_two_param_op(self):
        """siren-and-light:startFunctionPattern is the catalog's only
        two-placeholder path — neither may be left raw."""
        from admz.executor.vapix import PathParamRejected

        op = {
            "method": "POST",
            "base_path": "/config/rest/siren-and-light/v2beta",
            "path": "/functions/{id1}/patterns/{id2}/start",
        }
        assert self.executor._build_config_rest(
            op, {"id1": "SIP", "id2": "pattern 1"}
        ).path == (
            "/config/rest/siren-and-light/v2beta/functions/SIP"
            "/patterns/pattern%201/start"
        )
        for bad in ({"id1": "..", "id2": "p"}, {"id1": "f", "id2": "../.."}):
            with pytest.raises(PathParamRejected):
                self.executor._build_config_rest(op, bad)

    def test_literal_template_is_never_encoded(self):
        """param:exportParams is path: '/$export'. Only the *value* may be
        encoded — quoting the assembled path would break these ops."""
        req = self.executor._build_config_rest(
            {"method": "POST", "base_path": "/config/rest/param/v2beta",
             "path": "/$export"},
            {},
        )
        assert req.path == "/config/rest/param/v2beta/$export"

    def test_non_placeholder_params_are_untouched(self):
        """A param that isn't consumed by the path still rides in the body
        verbatim — the guard is scoped to path interpolation only."""
        req = self.executor._build_config_rest(
            {"method": "POST", "base_path": "/config/rest/ssh/v2",
             "path": "/users"},
            {"username": "root", "sshKey": "ssh-rsa AAAA+/=="},
        )
        assert req.path == "/config/rest/ssh/v2/users"
        assert req.json_body == {"username": "root", "sshKey": "ssh-rsa AAAA+/=="}


class TestConfigRestPathCannotEscapeEndpoint:
    """End-to-end through build_request on a REAL catalogued operation."""

    OP_ID = "event-schedules:getSchedule"

    def _op(self):
        import axis_api_atlas
        from axis_api_atlas.catalog.loader import CatalogLoader

        loader = CatalogLoader(axis_api_atlas.default_data_path())
        op = loader.get_operation("vapix", self.OP_ID)
        assert op is not None, f"{self.OP_ID} missing from catalog"
        return op.to_executor_dict()

    def test_catalogued_op_still_builds_for_a_real_id(self):
        ex = VapixExecutor.__new__(VapixExecutor)
        req = ex.build_request(self._op(), {"id1": "com.axis.schedules.weekends"})
        assert req.path.endswith("/schedules/com.axis.schedules.weekends")

    @pytest.mark.parametrize(
        "hostile",
        [
            "..",
            "../../../../axis-cgi/admin/pwdgrp.cgi",
            "x?action=add&grp=root",
            "x#truncate",
            "%2e%2e%2f%2e%2e",
        ],
    )
    def test_traversal_never_escapes_the_operations_endpoint(self, hostile):
        """The invariant: no param value may produce a URL that resolves
        outside the operation's own base_path. httpx resolves dot-segments
        itself, so the assertion is made against the normalised URL."""
        from admz.executor.vapix import PathParamRejected

        op = self._op()
        base = op["base_path"]
        ex = VapixExecutor.__new__(VapixExecutor)

        try:
            req = ex.build_request(op, {"id1": hostile})
        except PathParamRejected:
            return  # refused outright — the intended outcome

        # If it ever builds, the normalised wire path must stay under base.
        resolved = httpx.URL(f"http://device{req.path}")
        assert resolved.path.startswith(base), (
            f"{hostile!r} escaped {base} -> {resolved.path}"
        )
        assert resolved.query == b""


class TestExecuteRefusesRejectedPathParam:
    """Per the H-3 precedent, the refusal is asserted at the boundary too:
    execute() must return a failed StepResult naming the reason, and must
    not issue any HTTP request."""

    def test_execute_returns_failed_step_result_without_sending(self):
        import asyncio

        sent = []

        def handler(request):  # pragma: no cover - must never be reached
            sent.append(request.url)
            return httpx.Response(200, json={})

        ex = VapixExecutor(timeout=2.0, retries=0,
                           transport=httpx.MockTransport(handler))
        operation = {
            "id": "event-schedules:getSchedule",
            "method": "GET",
            "_generation": "config-rest",
            "base_path": "/config/rest/event-schedules/v2beta",
            "path": "/schedules/{id1}",
        }
        result = asyncio.run(
            ex.execute(
                operation,
                {"id": "dev1", "host": "10.0.0.5"},
                {"username": "u", "password": "p"},
                {"id1": "../../../../axis-cgi/admin/pwdgrp.cgi"},
            )
        )

        assert result.success is False
        assert "id1" in result.error
        assert sent == [], "a refused request must never reach the transport"


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


class TestSoapActionHeaderIsSent:
    """GH #245. `_build_soap` populated a `headers_extra` dict and then built
    an `ExecutionRequest` without it — and `ExecutionRequest` had no field to
    take it. `git log -S` shows one commit, the introducing one: never wired,
    not deliberately retired.

    This fixes no current failure. Nothing in the catalog sets `soap_action`,
    and all 26 live `vapix/ws/` operations work without the header. It is worth
    wiring because a catalog author adding `soap_action:` to a YAML would
    reasonably expect it to be sent, and it would silently do nothing — the
    trap is the silence, not the missing header.
    """

    def _build(self, operation):
        from admz.executor.vapix import VapixExecutor
        return VapixExecutor()._build_soap(operation, {})

    def test_the_header_reaches_the_request(self):
        req = self._build({
            "id": "action-service:GetActionRules",
            "soap_action": "http://www.axis.com/vapix/ws/action1/GetActionRules",
            "request": {"body_xml": "<x/>"},
        })
        assert req.headers_extra == {
            "SOAPAction": "http://www.axis.com/vapix/ws/action1/GetActionRules"}

    def test_no_soap_action_means_no_header(self):
        """The 26 live ops today. `None`, not an empty dict — httpx treats
        those differently enough not to want to think about it."""
        req = self._build({"id": "x", "request": {"body_xml": "<x/>"}})
        assert req.headers_extra is None

    def test_the_merge_keeps_content_type_and_adds_the_action(self):
        from admz.executor.models import ExecutionRequest
        from admz.executor.vapix import _merge_headers

        req = ExecutionRequest(method="POST", path="/vapix/services",
                               raw_body="<x/>", content_type="application/xml",
                               headers_extra={"SOAPAction": "urn:go"})
        assert _merge_headers(req, req.content_type) == {
            "Content-Type": "application/xml", "SOAPAction": "urn:go"}

    def test_an_operation_cannot_override_content_type(self):
        """The send path chooses the body encoding; an operation spec must not
        be able to contradict it from a header."""
        from admz.executor.models import ExecutionRequest
        from admz.executor.vapix import _merge_headers

        req = ExecutionRequest(method="POST", path="/p", raw_body="<x/>",
                               content_type="application/xml",
                               headers_extra={"content-type": "text/plain"})
        assert _merge_headers(req, req.content_type)["Content-Type"] == "application/xml"

    def test_nothing_to_send_is_none(self):
        from admz.executor.models import ExecutionRequest
        from admz.executor.vapix import _merge_headers

        assert _merge_headers(ExecutionRequest(method="GET", path="/p"), None) is None
