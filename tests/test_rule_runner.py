"""Unit tests for admz/rules/runner.py — the SOAP rule-execution consumer.

Drives the runner with a fake catalog + fake executor so the two-call create
choreography, orphan cleanup, delete-with-config-removal, response parsing, and
secret redaction are all covered without touching a device.
"""

import pytest

from admz.rules import runner
from admz.rules.runner import RuleRunnerError


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------

class FakeResult:
    def __init__(self, success=True, response_body="", status_code=200, error=None):
        self.success = success
        self.response_body = response_body
        self.status_code = status_code
        self.error = error


class FakeOp:
    def __init__(self, op_id, body_xml=""):
        self.op_id = op_id
        self._body_xml = body_xml

    def to_executor_dict(self):
        return {
            "id": self.op_id,
            "_generation": "soap",
            "request": {"content_type": "application/xml", "body_xml": self._body_xml},
        }


class FakeCatalog:
    """Returns a FakeOp for known action-service ids; None for anything else."""

    def __init__(self, known=None):
        # template body_xml the runner would override (create) or fill (delete)
        self._templates = known if known is not None else {
            "action-service:AddActionConfiguration": "<config-template/>",
            "action-service:AddActionRule": "<rule-template/>",
            "action-service:GetActionRules": "<get-rules/>",
            "action-service:RemoveActionRule": "<Remove><RuleID>{rule_id}</RuleID></Remove>",
            "action-service:RemoveActionConfiguration":
                "<Remove><ConfigurationID>{configuration_id}</ConfigurationID></Remove>",
        }

    def get_operation(self, family, op_id):
        if op_id not in self._templates:
            return None
        return FakeOp(op_id, self._templates[op_id])


class FakeExecutor:
    """Routes on op_dict['id'] to a canned FakeResult, recording every call."""

    def __init__(self, responses):
        self.responses = responses          # op_id -> FakeResult | list[FakeResult]
        self.calls = []                     # (op_id, body_xml, params)

    async def execute(self, op_dict, device, creds, params):
        op_id = op_dict["id"]
        body = (op_dict.get("request") or {}).get("body_xml")
        self.calls.append((op_id, body, dict(params or {})))
        resp = self.responses[op_id]
        if isinstance(resp, list):
            return resp.pop(0)
        return resp

    def body_for(self, op_id):
        for oid, body, _ in self.calls:
            if oid == op_id:
                return body
        return None

    def params_for(self, op_id):
        for oid, _, params in self.calls:
            if oid == op_id:
                return params
        return None


DEVICE = {"host": "10.0.0.5", "device_id": "cam1", "auth": {"scheme": "http"}}
CREDS = {"username": "root", "password": "x"}


def _run(catalog, executor, coro_factory):
    return coro_factory(catalog, executor)


# --------------------------------------------------------------------------
# create_rule
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_rule_happy_path_fills_placeholder():
    catalog = FakeCatalog()
    executor = FakeExecutor({
        "action-service:AddActionConfiguration":
            FakeResult(response_body="<r><ConfigurationID>42</ConfigurationID></r>"),
        "action-service:AddActionRule":
            FakeResult(response_body="<r><RuleID>7</RuleID></r>"),
    })
    out = await runner.create_rule(
        catalog=catalog, executor=executor, device=DEVICE, creds=CREDS,
        config_body="<aa:AddActionConfiguration>ding</aa:AddActionConfiguration>",
        rule_body="<PrimaryAction>{action_configuration_id}</PrimaryAction>",
    )
    assert out["config_id"] == "42"
    assert out["rule_id"] == "7"
    # the config body was sent verbatim (override), params skipped
    assert executor.body_for("action-service:AddActionConfiguration") == \
        "<aa:AddActionConfiguration>ding</aa:AddActionConfiguration>"
    assert executor.params_for("action-service:AddActionConfiguration") == {}
    # the rule body had the returned ConfigurationID substituted in
    assert executor.body_for("action-service:AddActionRule") == \
        "<PrimaryAction>42</PrimaryAction>"
    assert [s["op"] for s in out["steps"]] == ["AddActionConfiguration", "AddActionRule"]


@pytest.mark.asyncio
async def test_create_rule_config_step_fails():
    catalog = FakeCatalog()
    executor = FakeExecutor({
        "action-service:AddActionConfiguration":
            FakeResult(success=False, error="400 bad template", status_code=400),
    })
    with pytest.raises(RuleRunnerError) as ei:
        await runner.create_rule(
            catalog=catalog, executor=executor, device=DEVICE, creds=CREDS,
            config_body="<x/>", rule_body="<PrimaryAction>{action_configuration_id}</PrimaryAction>",
        )
    assert "action configuration failed" in str(ei.value)
    # AddActionRule must NOT have been attempted
    assert executor.body_for("action-service:AddActionRule") is None


@pytest.mark.asyncio
async def test_create_rule_missing_configuration_id():
    catalog = FakeCatalog()
    executor = FakeExecutor({
        "action-service:AddActionConfiguration":
            FakeResult(response_body="<r>ok, but no id</r>"),
    })
    with pytest.raises(RuleRunnerError) as ei:
        await runner.create_rule(
            catalog=catalog, executor=executor, device=DEVICE, creds=CREDS,
            config_body="<x/>", rule_body="<PrimaryAction>{action_configuration_id}</PrimaryAction>",
        )
    assert "no ConfigurationID" in str(ei.value)


@pytest.mark.asyncio
async def test_create_rule_rule_step_fails_cleans_up_orphan_config():
    catalog = FakeCatalog()
    executor = FakeExecutor({
        "action-service:AddActionConfiguration":
            FakeResult(response_body="<r><ConfigurationID>99</ConfigurationID></r>"),
        "action-service:AddActionRule":
            FakeResult(success=False, error="requires at least one condition"),
        "action-service:RemoveActionConfiguration":
            FakeResult(response_body="<ok/>"),
    })
    with pytest.raises(RuleRunnerError) as ei:
        await runner.create_rule(
            catalog=catalog, executor=executor, device=DEVICE, creds=CREDS,
            config_body="<x/>", rule_body="<PrimaryAction>{action_configuration_id}</PrimaryAction>",
        )
    assert "orphaned configuration was cleaned up" in str(ei.value)
    # the just-created config (99) was removed
    assert executor.params_for("action-service:RemoveActionConfiguration") == \
        {"configuration_id": "99"}
    assert ei.value.steps[-1]["op"].startswith("RemoveActionConfiguration")


# --------------------------------------------------------------------------
# delete_rule / list_rules / parse_rules
# --------------------------------------------------------------------------

_GET_RULES_XML = """<?xml version="1.0"?>
<GetActionRulesResponse xmlns="http://www.axis.com/vapix/ws/action1">
 <ActionRules>
  <ActionRule><RuleID>7</RuleID><Name>ding-dong</Name><Enabled>true</Enabled>
   <PrimaryAction>42</PrimaryAction></ActionRule>
  <ActionRule><RuleID>8</RuleID><Name>led</Name><Enabled>false</Enabled>
   <PrimaryAction>43</PrimaryAction></ActionRule>
 </ActionRules>
</GetActionRulesResponse>"""


def test_parse_rules_two_rules():
    rules = runner.parse_rules(_GET_RULES_XML)
    assert len(rules) == 2
    assert rules[0] == {
        "rule_id": "7", "name": "ding-dong", "enabled": True, "primary_action": "42",
    }
    assert rules[1]["enabled"] is False
    assert rules[1]["primary_action"] == "43"


def test_parse_rules_namespace_prefixed():
    xml = ("<aa:GetActionRulesResponse xmlns:aa='http://x'>"
           "<aa:ActionRule><aa:RuleID>3</aa:RuleID><aa:Name>n</aa:Name>"
           "<aa:PrimaryAction>5</aa:PrimaryAction></aa:ActionRule>"
           "</aa:GetActionRulesResponse>")
    rules = runner.parse_rules(xml)
    assert rules == [{"rule_id": "3", "name": "n", "enabled": None, "primary_action": "5"}]


def test_parse_rules_empty():
    assert runner.parse_rules("") == []
    assert runner.parse_rules(None) == []


@pytest.mark.asyncio
async def test_list_rules_reads_and_parses():
    catalog = FakeCatalog()
    executor = FakeExecutor({
        "action-service:GetActionRules": FakeResult(response_body=_GET_RULES_XML),
    })
    rules = await runner.list_rules(
        catalog=catalog, executor=executor, device=DEVICE, creds=CREDS)
    assert {r["rule_id"] for r in rules} == {"7", "8"}


@pytest.mark.asyncio
async def test_delete_rule_removes_rule_and_linked_config():
    catalog = FakeCatalog()
    executor = FakeExecutor({
        "action-service:GetActionRules": FakeResult(response_body=_GET_RULES_XML),
        "action-service:RemoveActionRule": FakeResult(response_body="<ok/>"),
        "action-service:RemoveActionConfiguration": FakeResult(response_body="<ok/>"),
    })
    out = await runner.delete_rule(
        catalog=catalog, executor=executor, device=DEVICE, creds=CREDS, rule_id="7")
    assert out["removed_rule"] == "7"
    assert out["removed_config"] == "42"
    assert executor.params_for("action-service:RemoveActionRule") == {"rule_id": "7"}
    assert executor.params_for("action-service:RemoveActionConfiguration") == \
        {"configuration_id": "42"}


@pytest.mark.asyncio
async def test_delete_rule_unknown_rule_still_removes_rule():
    catalog = FakeCatalog()
    executor = FakeExecutor({
        "action-service:GetActionRules": FakeResult(response_body=_GET_RULES_XML),
        "action-service:RemoveActionRule": FakeResult(response_body="<ok/>"),
    })
    out = await runner.delete_rule(
        catalog=catalog, executor=executor, device=DEVICE, creds=CREDS, rule_id="999")
    assert out["removed_rule"] == "999"
    assert out["removed_config"] is None


@pytest.mark.asyncio
async def test_delete_rule_removal_fails():
    catalog = FakeCatalog()
    executor = FakeExecutor({
        "action-service:GetActionRules": FakeResult(response_body=_GET_RULES_XML),
        "action-service:RemoveActionRule":
            FakeResult(success=False, error="no such rule"),
    })
    with pytest.raises(RuleRunnerError) as ei:
        await runner.delete_rule(
            catalog=catalog, executor=executor, device=DEVICE, creds=CREDS, rule_id="7")
    assert "Removing rule 7 failed" in str(ei.value)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def test_extract_namespace_tolerant():
    assert runner._extract("ConfigurationID",
                           "<aa:ConfigurationID>12</aa:ConfigurationID>") == "12"
    assert runner._extract("RuleID", "<RuleID >9</RuleID>") == "9"
    assert runner._extract("RuleID", "<other>9</other>") is None


def test_redact_soap_body_masks_secret_params_only():
    body = ('<aa:Parameter Name="upload_url" Value="http://x/y"/>'
            '<aa:Parameter Name="login" Value="operator"/>'
            '<aa:Parameter Name="password" Value="hunter2"/>')
    red = runner.redact_soap_body(body)
    assert 'Name="password" Value="***"' in red
    assert "hunter2" not in red
    assert 'Value="http://x/y"' in red          # non-secret untouched
    assert 'Value="operator"' in red            # login is a username, not masked


@pytest.mark.asyncio
async def test_missing_catalog_op_raises():
    catalog = FakeCatalog(known={})     # empty — no ops
    executor = FakeExecutor({})
    with pytest.raises(RuleRunnerError) as ei:
        await runner.list_rules(
            catalog=catalog, executor=executor, device=DEVICE, creds=CREDS)
    assert "missing SOAP op" in str(ei.value)
