"""SipFacet — SIP config via the Call service API (shapes captured live on a
C1710, API v2.2). Accounts carry plaintext passwords → censored in serialize."""

import json

from admz.snapshot.facets.sip import SipFacet

LIVE_CONFIG = {"SIPConfiguration": {
    "SIPEnabled": False, "SIPPort": 5060, "SIPTLSPort": 5061,
    "RTPStartPort": 4000, "STUNEnabled": False, "STUNServers": [],
    "TURNEnabled": False, "TURNServers": [], "ICEEnabled": False,
    "AllowIncomingCalls": False, "ApplyUserAuthentication": False,
    "AllowedUsers": [], "ApplyAllowedURIs": False, "AllowedURIs": [],
    "CallingTimeout": 60, "AnsweringTimeout": 60, "Attribute": [],
}}

LIVE_ACCOUNTS = {"SIPAccount": [{
    "Id": "sip_account_0", "Enabled": True, "Name": "peer-to-peer",
    "CallerId": "peer-to-peer", "UserId": "peer-to-peer",
    "Password": "hunter2", "Registrar": None, "PublicDomain": None,
    "SIPProxies": [], "SecondarySIPProxies": [], "IsDefault": True,
    "AutoAnswerEnabled": True, "Transport": "udp", "StreamParameters": "",
    "DTMFConfigurationId": "dtmf_config_default", "MediaEncryption": "None",
    "Attribute": [],
}]}


class TestSerialize:
    def test_config_and_accounts_captured(self):
        doc = SipFacet().serialize(
            {"sip_config": LIVE_CONFIG, "sip_accounts": LIVE_ACCOUNTS})
        assert doc["config"]["SIPEnabled"] is False
        assert doc["config"]["SIPPort"] == 5060
        assert doc["config"]["STUNServers"] == "[]"       # list → stable JSON
        assert "sip_account_0" in doc["accounts"]
        assert doc["accounts"]["sip_account_0"]["Transport"] == "udp"

    def test_account_password_censored(self):
        doc = SipFacet().serialize(
            {"sip_config": LIVE_CONFIG, "sip_accounts": LIVE_ACCOUNTS})
        blob = json.dumps(doc)
        assert "hunter2" not in blob and '"Password"' not in blob

    def test_non_sip_device_serializes_empty(self):
        assert SipFacet().serialize({}) == {}


class TestRevert:
    def test_config_paths_op_revertable_accounts_not(self):
        f = SipFacet()
        assert f.op_revertable("config.CallingTimeout")
        assert not f.op_revertable("accounts.sip_account_0.Transport")

    def test_revert_writes_baseline_config_with_decoded_lists(self):
        f = SipFacet()
        baseline = f.serialize(
            {"sip_config": LIVE_CONFIG, "sip_accounts": LIVE_ACCOUNTS})
        steps = f.build_revert_ops(
            [("config.CallingTimeout", 60, 61)], baseline)
        assert len(steps) == 1
        s = steps[0]
        assert s["operation_id"] == "sip:setSIPConfiguration"
        conf = s["params"]["SIPConfiguration"]
        assert conf["CallingTimeout"] == 60
        assert conf["STUNServers"] == []                  # decoded back to list
        # censored account data never rides in the config write
        assert "hunter2" not in json.dumps(s)

    def test_empty_baseline_returns_none(self):
        assert SipFacet().build_revert_ops([("config.SIPPort", 5060, 5070)], {}) is None
