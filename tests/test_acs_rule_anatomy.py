"""ACS rule anatomy reader + firing-observability classifier (#124, slice 1).

``firebird.rule_anatomy`` answers *what does this rule listen to, on which
device, and what does it do, to which device* — the join the demo-inference
evidence graph needs. ``demos.inference.observability.classify_rule`` is the
pure verdict over one of its rows.

Everything here drives the injected ``Reader`` seam (``tests/test_acs_firebird.py``'s
pattern) or a stubbed ``_connect_copy``, so the suite runs on any host with or
without ACS/Firebird installed. The specimen fixture below is the **real**
12-rule inventory read live from ACS Pro 6.16.19560 on 2026-07-27, encoded as a
regression fixture: an SFH alert on a P3288-LVE, the I8016-LVE door-station
cluster, three I/O "Open Door" rules and an HTTPS-triggered example.
"""

from __future__ import annotations

import asyncio
import json

import pytest


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _isolate_admz_home(tmp_path, monkeypatch):
    """House convention: never let a test read or write the real ADMZ_HOME DB.

    Nothing in this file should reach a store at all (every seam is injected),
    so this is a guard rather than a dependency.
    """
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path / "admz_home"))


# ═══════════════════════════════════════════════════════════════════════════
# The live specimen, as read from ACS Pro 6.16.19560 (2026-07-27)
# ═══════════════════════════════════════════════════════════════════════════
SPECIMEN = {
    "rules": [
        {"id": 13874, "name": "Alert on SFH", "is_enabled": True,
         "require_all_triggers": False, "schedule_id": 79},
        {"id": 14358, "name": "DoorStationRuleDevice#14070", "is_enabled": True,
         "require_all_triggers": False, "schedule_id": 79},
        {"id": 18086, "name": "External Trigger Example", "is_enabled": True,
         "require_all_triggers": False, "schedule_id": 95},
        {"id": 14389, "name": "Open Door Rule - B8A44F0C5B32", "is_enabled": True,
         "require_all_triggers": False, "schedule_id": 79},
        {"id": 14384, "name": "Record ongoing call - B8A44F0C5B32", "is_enabled": False,
         "require_all_triggers": True, "schedule_id": 79},
        # auto-generated per-camera rule — must never reach the caller
        {"id": 13833, "name": "PredefinedContinuousRecording13825", "is_enabled": True,
         "require_all_triggers": False, "schedule_id": 79},
    ],
    "triggers": [
        {"id": 13872, "rule_id": 13874, "discriminator": "DeviceEventTriggerEntity",
         "trigger_type": 9, "camera_id": None, "device_id": 13758, "port_id": None,
         "topic_filter": "tnsaxis:CameraApplicationPlatform/sfh_detector/SfHCandidate",
         "subscription_filter": "axis:CameraApplicationPlatform/sfh_detector/SfHCandidate",
         "nice_name": "Signal for Help Candidate", "trigger_name": None,
         "trigger_state": None, "is_stateful": True, "button_configuration_id": None},
        {"id": 14353, "rule_id": 14358, "discriminator": "DeviceEventTriggerEntity",
         "trigger_type": 9, "camera_id": None, "device_id": 14070, "port_id": None,
         "topic_filter": "tnsaxis:Call/StateChange", "subscription_filter": None,
         "nice_name": "StateChange", "trigger_name": None, "trigger_state": None,
         "is_stateful": None, "button_configuration_id": None},
        {"id": 18085, "rule_id": 18086, "discriminator": "HttpsTriggerEntity",
         "trigger_type": 12, "camera_id": None, "device_id": None, "port_id": None,
         "topic_filter": None, "subscription_filter": None, "nice_name": None,
         "trigger_name": "test", "trigger_state": None, "is_stateful": None,
         "button_configuration_id": None},
        {"id": 14388, "rule_id": 14389, "discriminator": "ManualTriggerEntity",
         "trigger_type": 10, "camera_id": None, "device_id": None, "port_id": None,
         "topic_filter": None, "subscription_filter": None, "nice_name": None,
         "trigger_name": None, "trigger_state": None, "is_stateful": None,
         "button_configuration_id": 14385},
        {"id": 14381, "rule_id": 14384, "discriminator": "DeviceEventTriggerEntity",
         "trigger_type": 9, "camera_id": None, "device_id": 14070, "port_id": None,
         "topic_filter": "tnsaxis:Call/State", "subscription_filter": None,
         "nice_name": "State", "trigger_name": None, "trigger_state": None,
         "is_stateful": None, "button_configuration_id": None},
        # trigger belonging to the hidden Predefined rule
        {"id": 13834, "rule_id": 13833, "discriminator": "AlwaysActiveTriggerEntity",
         "trigger_type": 1, "camera_id": None, "device_id": None, "port_id": None,
         "topic_filter": None, "subscription_filter": None, "nice_name": None,
         "trigger_name": None, "trigger_state": None, "is_stateful": None,
         "button_configuration_id": None},
    ],
    "content_filters": [
        {"id": 13873, "device_event_trigger_id": 13872, "name": "state",
         "value": "1", "is_state": True, "value_type": 2},
        {"id": 14354, "device_event_trigger_id": 14353, "name": "Source",
         "value": "DoorStation", "is_state": False, "value_type": 1},
        {"id": 14355, "device_event_trigger_id": 14353, "name": "Reason",
         "value": "Initiated", "is_state": False, "value_type": 1},
        {"id": 14382, "device_event_trigger_id": 14381, "name": "CallState",
         "value": "Active", "is_state": True, "value_type": 1},
    ],
    "actions": [
        {"id": 13869, "rule_id": 13874, "discriminator": "RecordActionEntity",
         "action_type": 3, "streaming_profile_id": 13826, "pre_buffer": 100000000,
         "post_buffer": 100000000},
        {"id": 13870, "rule_id": 13874, "discriminator": "AlarmActionEntity",
         "action_type": 1, "title": "Signal For Help"},
        {"id": 13871, "rule_id": 13874,
         "discriminator": "MobileAppNotificationActionEntity", "action_type": 9,
         "mobile_app_notification_message": "Signal For Help",
         "associated_camera": 13825},
        {"id": 14352, "rule_id": 14358, "discriminator": "DoorStationActionEntity",
         "action_type": 8, "device_id": 14070, "door_station_call_state_change": 1,
         "event_recipients": 3},
        {"id": 30061, "rule_id": 18086, "discriminator": "LiveViewActionEntity",
         "action_type": 5, "camera_id": 14717},
        {"id": 14386, "rule_id": 14389, "discriminator": "IOActionEntity",
         "action_type": 4, "port_id": 14141, "new_state": 1, "is_pulse": True,
         "pulse_length": 7},
        {"id": 14380, "rule_id": 14384, "discriminator": "RecordActionEntity",
         "action_type": 3, "streaming_profile_id": 14145, "pre_buffer": 0,
         "post_buffer": 50000000},
        {"id": 13835, "rule_id": 13833, "discriminator": "RecordActionEntity",
         "action_type": 3, "streaming_profile_id": 13826},
    ],
    "devices": [
        {"id": 13758, "mac_address": "E827251FFB8D", "model": "AXIS P3288-LVE",
         "manufacturer": "Axis", "ip_address": "192.168.1.105", "hostname": "",
         "product_type": "Dome Camera"},
        {"id": 14070, "mac_address": "B8A44F0C5B32", "model": "AXIS I8016-LVE",
         "manufacturer": "Axis", "ip_address": "192.168.1.208", "hostname": "",
         "product_type": "Network Video Intercom"},
        {"id": 14486, "mac_address": "B8A44F28230F", "model": "AXIS M4308-PLE",
         "manufacturer": "Axis", "ip_address": "192.168.1.114", "hostname": "",
         "product_type": "Panoramic Camera"},
    ],
    "cameras": [
        {"id": 13825, "name": "AXIS P3288-LVE", "device_id": 13758, "is_enabled": True},
        {"id": 14142, "name": "AXIS I8016-LVE", "device_id": 14070, "is_enabled": True},
        {"id": 14717, "name": "AXIS M4308-PLE - View Area 4", "device_id": 14486,
         "is_enabled": True},
    ],
    "io_ports": [
        {"id": 14141, "device_id": 14070, "name": "Door I/O Port", "port_type": 2,
         "port_identifier": "4", "is_enabled": True},
    ],
    "profiles": [
        {"id": 13826, "camera_id": 13825},
        {"id": 14145, "camera_id": 14142},
    ],
    "schedules": [
        {"id": 79, "name": "Always schedule", "discriminator": "AlwaysScheduleEntity"},
        {"id": 95, "name": "Office Hours", "discriminator": "MainScheduleEntity"},
    ],
}

#: ``DeviceListFacade:GetDeviceList`` rows for the same fleet — the composite
#: ``"<DEVICE.ID>_<server-guid>"`` spelling of the identical devices.
API_DEVICES = [
    {"DeviceId": {"Id": "13758_77952d52-68c9-4862-a17f-3fdcbdfeb013"},
     "MacAddress": "E827251FFB8D", "Model": "AXIS P3288-LVE"},
    {"DeviceId": {"Id": "14070_77952d52-68c9-4862-a17f-3fdcbdfeb013"},
     "MacAddress": "B8A44F0C5B32", "Model": "AXIS I8016-LVE"},
    {"DeviceId": {"Id": "14486_77952d52-68c9-4862-a17f-3fdcbdfeb013"},
     "MacAddress": "B8A44F28230F", "Model": "AXIS M4308-PLE"},
]


def _reader(specimen=None, *, seen=None):
    """A ``Reader`` over the specimen that evaluates the SQL the way Firebird
    would — so the ``Predefined*`` exclusion is genuinely exercised rather than
    assumed, and a query naming an unknown table fails loudly."""
    data = specimen if specimen is not None else SPECIMEN

    def reader(db_name, sql, params=None):
        from admz.modules.acs_pro.firebird import CONFIG_DB
        assert db_name == CONFIG_DB
        if seen is not None:
            seen.append(sql)
        if "FROM RULE" in sql:
            rows = data["rules"]
            if "NOT STARTING WITH 'Predefined'" in sql:
                rows = [r for r in rows if not str(r["name"]).startswith("Predefined")]
            return list(rows)
        if 'FROM "TRIGGER"' in sql:
            return list(data["triggers"])
        if "FROM CONTENT_FILTER" in sql:
            return list(data["content_filters"])
        if "FROM ACTION" in sql:
            return list(data["actions"])
        if "FROM DEVICE" in sql:
            return list(data["devices"])
        if "FROM CAMERA" in sql:
            return list(data["cameras"])
        if "FROM IO_PORT" in sql:
            return list(data["io_ports"])
        if "FROM STREAMING_PROFILE" in sql:
            return list(data["profiles"])
        if "FROM SCHEDULE" in sql:
            return list(data["schedules"])
        raise AssertionError("unexpected sql: " + sql)

    return reader


def _anatomy(**kw):
    from admz.modules.acs_pro.firebird import rule_anatomy
    kw.setdefault("reader", _reader())
    return rule_anatomy(**kw)


def _by_name(rules, name):
    return next(r for r in rules if r["name"] == name)


# ═══════════════════════════════════════════════════════════════════════════
# _read_many — one copy, N cursors
# ═══════════════════════════════════════════════════════════════════════════
class _FakeCursor:
    def __init__(self, log):
        self._log = log
        self.description = None
        self._rows = []

    def execute(self, sql, params):
        self._log.append((sql, params))
        self.description = [("ID",), ("NAME",)]
        self._rows = [(len(self._log), sql)]

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, log):
        self._log = log
        self.closed = False

    def cursor(self):
        return _FakeCursor(self._log)

    def close(self):
        self.closed = True


@pytest.fixture
def fake_db(monkeypatch, tmp_path):
    """Stub ``_connect_copy`` and count how many DB copies a read costs."""
    import admz.modules.acs_pro.firebird as fb
    state = {"copies": 0, "queries": [], "conns": [], "tmps": []}

    def connect_copy(db_name):
        state["copies"] += 1
        tmp = tmp_path / f"copy{state['copies']}.fdb"
        tmp.write_bytes(b"not a real fdb")
        con = _FakeConn(state["queries"])
        state["conns"].append(con)
        state["tmps"].append(tmp)
        return con, str(tmp)

    monkeypatch.setattr(fb, "_connect_copy", connect_copy)
    return state


def test_read_many_copies_the_db_once_for_n_queries(fake_db):
    """The whole point: ``_read`` copies the 22 MB .FDB per SELECT, so a naive
    four-query anatomy would copy it four times."""
    from admz.modules.acs_pro.firebird import CONFIG_DB, _read_many

    out = _read_many(CONFIG_DB, [
        "SELECT ID, NAME FROM RULE",
        ("SELECT ID FROM ACTION WHERE RULE_ID = ?", [7]),
        'SELECT ID FROM "TRIGGER"',
        "SELECT ID FROM DEVICE",
    ])
    assert fake_db["copies"] == 1                      # ← one copy, four cursors
    assert len(out) == 4
    assert len(fake_db["queries"]) == 4
    assert fake_db["queries"][1] == ("SELECT ID FROM ACTION WHERE RULE_ID = ?", [7])
    assert out[0] == [{"id": 1, "name": "SELECT ID, NAME FROM RULE"}]


def test_read_many_closes_the_connection_and_removes_the_copy(fake_db):
    from admz.modules.acs_pro.firebird import CONFIG_DB, _read_many
    _read_many(CONFIG_DB, ["SELECT 1 FROM RDB$DATABASE"])
    assert fake_db["conns"][0].closed is True
    assert not fake_db["tmps"][0].exists()             # the copy never lingers


def test_read_many_cleans_up_when_a_query_raises(fake_db, monkeypatch):
    import admz.modules.acs_pro.firebird as fb

    def boom(self, sql, params):
        raise RuntimeError("bad sql")

    monkeypatch.setattr(_FakeCursor, "execute", boom)
    with pytest.raises(RuntimeError):
        fb._read_many(fb.CONFIG_DB, ["SELECT 1 FROM RDB$DATABASE"])
    assert fake_db["conns"][0].closed is True
    assert not fake_db["tmps"][0].exists()


def test_read_still_works_for_existing_callers(fake_db):
    """``_read`` is the seam ``list_rules`` / the firing poller use — unchanged
    signature, unchanged return, still exactly one copy."""
    from admz.modules.acs_pro.firebird import CONFIG_DB, _read
    rows = _read(CONFIG_DB, "SELECT ID, NAME FROM RULE WHERE ID > ?", [5])
    assert fake_db["copies"] == 1
    assert fake_db["queries"] == [("SELECT ID, NAME FROM RULE WHERE ID > ?", [5])]
    assert rows == [{"id": 1, "name": "SELECT ID, NAME FROM RULE WHERE ID > ?"}]


def test_rule_anatomy_default_reader_costs_one_copy(fake_db):
    """Nine queries against one copy — the production path."""
    from admz.modules.acs_pro.firebird import _ANATOMY_QUERIES, rule_anatomy
    rule_anatomy()                                     # fake cursor → empty-ish rows
    assert fake_db["copies"] == 1
    assert len(fake_db["queries"]) == len(_ANATOMY_QUERIES) == 9


# ═══════════════════════════════════════════════════════════════════════════
# SQL hygiene: reserved words quoted, credential columns never selected
# ═══════════════════════════════════════════════════════════════════════════
def test_anatomy_sql_quotes_firebird_reserved_words():
    """``TRIGGER``, ``TIMESTAMP`` and ``VALUE`` are reserved — an unquoted
    ``FROM TRIGGER`` is a parser error at runtime, invisible to a mock."""
    import admz.modules.acs_pro.firebird as fb
    assert 'FROM "TRIGGER"' in fb._Q_TRIGGERS
    assert "FROM TRIGGER " not in fb._Q_TRIGGERS
    assert '"VALUE"' in fb._Q_CONTENT_FILTERS
    for sql in fb._ANATOMY_QUERIES:
        assert " VALUE," not in sql and " TRIGGER " not in sql


def test_anatomy_sql_never_selects_credential_columns():
    """``DEVICE`` carries device admin creds and ``ACTION`` carries HTTP-notify
    creds. Redaction is by construction: the columns are never in the SELECT."""
    import admz.modules.acs_pro.firebird as fb
    for sql in fb._ANATOMY_QUERIES:
        upper = sql.upper()
        assert "USERNAME" not in upper, sql
        assert "PASSWORD" not in upper, sql
        assert "SELECT *" not in upper, sql            # explicit columns only


@pytest.mark.parametrize("raw,expected", [
    ("https://user:s3cret@admz.local/api/acs/rule-fired",
     "https://***@admz.local/api/acs/rule-fired"),
    ("https://admz.local/api/acs/rule-fired?token=abc123",
     "https://admz.local/api/acs/rule-fired?token=%2A%2A%2A"),
    ("https://admz.local/hook?rule=Front+Door&apikey=xyz",
     "https://admz.local/hook?rule=Front+Door&apikey=%2A%2A%2A"),
    ("https://plain.example/hook", "https://plain.example/hook"),
    (None, None),
])
def test_redact_url_masks_userinfo_and_secret_query_params(raw, expected):
    from admz.modules.acs_pro.firebird import redact_url
    assert redact_url(raw) == expected


def test_anatomy_output_carries_no_credentials():
    rules = _anatomy(acs_api_devices=API_DEVICES)
    blob = json.dumps(rules, default=str).lower()
    for word in ("password", "passwd", "username", "masterkey"):
        assert word not in blob


# ═══════════════════════════════════════════════════════════════════════════
# rule_anatomy — shaping
# ═══════════════════════════════════════════════════════════════════════════
def test_rule_anatomy_hides_predefined_rules():
    rules = _anatomy()
    assert len(rules) == 5
    assert not any(r["name"].startswith("Predefined") for r in rules)


def test_list_rules_is_unchanged_by_the_anatomy_work():
    """Existing callers (the /acs page) must see exactly the old shape."""
    from admz.modules.acs_pro.firebird import list_rules
    rules = list_rules(reader=_reader())
    assert {r["name"] for r in rules} == {
        "Alert on SFH", "DoorStationRuleDevice#14070", "External Trigger Example",
        "Open Door Rule - B8A44F0C5B32", "Record ongoing call - B8A44F0C5B32"}
    sfh = _by_name(rules, "Alert on SFH")
    assert set(sfh.keys()) == {"id", "name", "enabled", "actions"}
    assert sfh["actions"] == ["Alarm", "MobileAppNotification", "Record"]


def test_rule_anatomy_joins_trigger_content_filter_and_action():
    sfh = _by_name(_anatomy(acs_api_devices=API_DEVICES), "Alert on SFH")
    assert sfh["id"] == 13874 and sfh["enabled"] is True
    assert sfh["require_all_triggers"] is False
    assert sfh["schedule"] == {"id": 79, "name": "Always schedule", "kind": "Always"}

    (trig,) = sfh["triggers"]
    assert trig["kind"] == "DeviceEvent"
    assert trig["topic"] == "tnsaxis:CameraApplicationPlatform/sfh_detector/SfHCandidate"
    assert trig["nice_name"] == "Signal for Help Candidate"
    assert trig["stateful"] is True
    assert trig["filters"] == [{"name": "state", "value": "1", "is_state": True}]
    assert trig["device"]["mac"] == "E827251FFB8D"
    assert trig["device"]["model"] == "AXIS P3288-LVE"
    assert trig["device"]["ip"] == "192.168.1.105"

    kinds = [a["kind"] for a in sfh["actions"]]
    assert kinds == ["Record", "Alarm", "MobileAppNotification"]
    record = sfh["actions"][0]
    # record action → STREAMING_PROFILE → CAMERA → DEVICE
    assert record["target_device"]["mac"] == "E827251FFB8D"
    assert record["params"]["camera"] == {"id": 13825, "name": "AXIS P3288-LVE"}
    assert record["params"]["pre_buffer"] == 100000000
    # a server-side alarm names no device — that is correct, not a failed join
    assert sfh["actions"][1]["target_device"] is None
    assert sfh["unresolved"] == []


def test_rule_anatomy_resolves_io_action_through_the_port():
    rule = _by_name(_anatomy(acs_api_devices=API_DEVICES),
                    "Open Door Rule - B8A44F0C5B32")
    (trig,) = rule["triggers"]
    assert trig["kind"] == "Manual"                     # ACS-internal, no device
    assert trig["device"] is None
    assert trig["button_configuration_id"] == 14385
    (act,) = rule["actions"]
    assert act["kind"] == "IO"
    assert act["target_device"]["mac"] == "B8A44F0C5B32"     # IO_PORT → DEVICE
    assert act["params"]["port"]["name"] == "Door I/O Port"
    assert act["params"]["port"]["identifier"] == "4"
    assert act["params"]["is_pulse"] is True and act["params"]["pulse_length"] == 7
    assert rule["unresolved"] == []


def test_rule_anatomy_resolves_live_view_action_through_the_camera():
    rule = _by_name(_anatomy(acs_api_devices=API_DEVICES), "External Trigger Example")
    (trig,) = rule["triggers"]
    assert trig["kind"] == "Https" and trig["trigger_name"] == "test"
    assert trig["device"] is None
    (act,) = rule["actions"]
    assert act["kind"] == "LiveView"
    assert act["target_device"]["mac"] == "B8A44F28230F"
    assert act["params"]["camera"]["name"] == "AXIS M4308-PLE - View Area 4"


def test_rule_anatomy_carries_disabled_and_require_all_triggers():
    rule = _by_name(_anatomy(), "Record ongoing call - B8A44F0C5B32")
    assert rule["enabled"] is False
    assert rule["require_all_triggers"] is True
    assert rule["schedule"]["kind"] == "Always"


def test_rule_anatomy_reports_a_non_always_schedule():
    rule = _by_name(_anatomy(), "External Trigger Example")
    assert rule["schedule"] == {"id": 95, "name": "Office Hours", "kind": "Main"}


def test_rule_anatomy_lists_only_genuine_join_failures_as_unresolved():
    """A rule whose trigger names a device ACS no longer has is *reported*, never
    silently dropped — but a trigger that names no device at all is not a
    failure."""
    import copy
    spec = copy.deepcopy(SPECIMEN)
    spec["devices"] = [d for d in spec["devices"] if d["id"] != 13758]
    rules = _anatomy(reader=_reader(spec))
    sfh = _by_name(rules, "Alert on SFH")
    assert sfh["triggers"][0]["device"] is None
    assert sfh["triggers"][0]["device_ref_unresolved"] is True
    assert "trigger:13872" in sfh["unresolved"]
    # the alarm action still names no device — still not counted as unresolved
    assert "action:13870" not in sfh["unresolved"]
    # and the rule itself is still returned
    assert sfh["name"] == "Alert on SFH"


def test_rule_anatomy_reader_seam_runs_every_query():
    from admz.modules.acs_pro.firebird import _ANATOMY_QUERIES, rule_anatomy
    seen = []
    rule_anatomy(reader=_reader(seen=seen))
    assert seen == _ANATOMY_QUERIES


def test_rule_anatomy_is_deterministic():
    a = _anatomy(acs_api_devices=API_DEVICES)
    b = _anatomy(acs_api_devices=API_DEVICES)
    assert json.dumps(a, default=str) == json.dumps(b, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# The device join — the one assumption the whole ACS link rests on
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("value,expected", [
    (14070, 14070),
    ("14070", 14070),
    ("14070_77952d52-68c9-4862-a17f-3fdcbdfeb013", 14070),
    ({"Id": "14070_77952d52-68c9-4862-a17f-3fdcbdfeb013"}, 14070),
    ({"id": "14070"}, 14070),
    (None, None), ("", None), ("not-an-id", None), (True, None),
])
def test_acs_id_int_accepts_every_spelling_of_the_same_id(value, expected):
    """Verified live on ACS 6.16.19560: the integer prefix of the API
    ``DeviceId`` is the Firebird ``DEVICE.ID``."""
    from admz.modules.acs_pro.firebird import acs_id_int
    assert acs_id_int(value) == expected


def test_resolver_path1_prefers_the_live_api_mac_address():
    from admz.modules.acs_pro.firebird import build_device_resolver
    resolve = build_device_resolver(SPECIMEN["devices"], API_DEVICES)
    ref = resolve(14070)
    assert ref["mac"] == "B8A44F0C5B32"
    assert ref["join_method"] == "api_device_id"
    assert ref["acs_device_id"] == 14070


def test_resolver_path2_falls_back_to_the_firebird_device_mac():
    from admz.modules.acs_pro.firebird import build_device_resolver
    resolve = build_device_resolver(SPECIMEN["devices"], None)   # no ACS API
    ref = resolve("14070_77952d52-68c9-4862-a17f-3fdcbdfeb013")
    assert ref["mac"] == "B8A44F0C5B32"
    assert ref["join_method"] == "firebird_device_mac"


def test_resolver_path3_falls_back_to_device_serial_number():
    """``CameraListFacade`` rows carry ``DeviceSerialNumber`` and no
    ``MacAddress`` — and on Axis devices the serial *is* the MAC."""
    from admz.modules.acs_pro.firebird import build_device_resolver
    fb_devices = [dict(d, mac_address=None) for d in SPECIMEN["devices"]]
    api = [{"DeviceId": {"Id": "14070_guid"}, "DeviceSerialNumber": "B8A44F0C5B32"}]
    ref = build_device_resolver(fb_devices, api)(14070)
    assert ref["mac"] == "B8A44F0C5B32"
    assert ref["join_method"] == "device_serial_number"


def test_resolver_normalizes_separated_macs_through_canonical_mac():
    """MAC-join regression: the ACS spelling and the ADMZ device_id spelling of
    the same unit must compare equal (``device_registry.canonical_mac``)."""
    from admz.device_registry import canonical_mac
    from admz.modules.acs_pro.firebird import build_device_resolver
    api = [{"DeviceId": 14070, "MacAddress": "AC:CC:8E:E6:E7:EE"}]
    ref = build_device_resolver([{"id": 14070}], api)(14070)
    assert ref["mac"] == "ACCC8EE6E7EE" == canonical_mac("ACCC8EE6E7EE")
    assert ref["join_method"] == "api_device_id"


def test_resolver_reports_a_macless_device_rather_than_dropping_it():
    from admz.modules.acs_pro.firebird import build_device_resolver
    ref = build_device_resolver([{"id": 14070, "model": "AXIS I8016-LVE"}], None)(14070)
    assert ref["mac"] is None and ref["join_method"] == "acs_device_id_only"


def test_resolver_returns_none_for_an_unknown_id():
    from admz.modules.acs_pro.firebird import build_device_resolver
    resolve = build_device_resolver(SPECIMEN["devices"], API_DEVICES)
    assert resolve(999999) is None
    assert resolve(None) is None


def test_every_join_path_resolves_the_specimen_to_the_same_macs():
    """The live proof, as a regression: API-MAC, Firebird-MAC and serial paths
    must agree, or the whole ACS↔ADMZ join is unsound."""
    serial_only = [{"DeviceId": d["DeviceId"], "DeviceSerialNumber": d["MacAddress"]}
                   for d in API_DEVICES]
    macless = _reader({**SPECIMEN,
                       "devices": [dict(d, mac_address=None) for d in SPECIMEN["devices"]]})

    def macs_and_methods(**kw):
        out = {}
        methods = set()
        for rule in _anatomy(**kw):
            for ref in ([t["device"] for t in rule["triggers"]]
                        + [a["target_device"] for a in rule["actions"]]):
                if ref:
                    out[ref["acs_device_id"]] = ref["mac"]
                    methods.add(ref["join_method"])
        return out, methods

    by_api, m1 = macs_and_methods(acs_api_devices=API_DEVICES)
    by_fb, m2 = macs_and_methods(acs_api_devices=None)
    by_serial, m3 = macs_and_methods(reader=macless, acs_api_devices=serial_only)

    expected = {13758: "E827251FFB8D", 14070: "B8A44F0C5B32", 14486: "B8A44F28230F"}
    assert by_api == by_fb == by_serial == expected
    assert m1 == {"api_device_id"}
    assert m2 == {"firebird_device_mac"}
    assert m3 == {"device_serial_number"}


# ═══════════════════════════════════════════════════════════════════════════
# classify_rule — the six verdicts
# ═══════════════════════════════════════════════════════════════════════════
def _rule(triggers=(), actions=()):
    return {"id": 1, "name": "r", "triggers": list(triggers), "actions": list(actions)}


def _trigger(kind, mac="B8A44F0C5B32", topic="tnsaxis:Call/State"):
    return {"id": 10, "kind": kind, "topic": topic,
            "device": ({"mac": mac} if mac else None)}


def _action(kind, mac="B8A44F0C5B32", params=None):
    return {"id": 20, "kind": kind, "params": params or {},
            "target_device": ({"mac": mac} if mac else None)}


@pytest.mark.parametrize("verdict,rule", [
    # a device-originated trigger → subscribe to the same event directly
    ("device_event_direct", _rule(triggers=[_trigger("DeviceEvent")],
                                  actions=[_action("DoorStation")])),
    ("device_event_direct", _rule(triggers=[_trigger("MotionDetection")])),
    ("device_event_direct", _rule(triggers=[_trigger("ObjectDetection")])),
    # a record action is rule-attributed in ACS_RECORDINGS.RECORDING_SEQUENCE
    ("recording_sequence", _rule(triggers=[_trigger("Manual", mac=None)],
                                 actions=[_action("Record")])),
    # an alarm action lands in ACS_LOGS.LOG as a named firing
    ("acs_log_alarm", _rule(triggers=[_trigger("Https", mac=None)],
                            actions=[_action("Alarm", mac=None)])),
    # an I/O output is observable as the target device's own output event
    ("device_event", _rule(triggers=[_trigger("Manual", mac=None)],
                           actions=[_action("IO", params={"port": {"identifier": "4"}})])),
    # an HTTP notify already aimed at ADMZ is real-time and rule-named
    ("webhook", _rule(triggers=[_trigger("Https", mac=None)],
                      actions=[_action("HttpNotification", mac=None, params={
                          "url": "https://admz.local/api/acs/rule-fired?token=***"})])),
    # nothing observes a mobile-notify-only rule on an ACS-internal trigger
    ("blind", _rule(triggers=[_trigger("Https", mac=None)],
                    actions=[_action("MobileAppNotification")])),
    ("blind", _rule(triggers=[_trigger("Manual", mac=None)],
                    actions=[_action("Ptz", mac=None)])),
    ("blind", _rule()),
])
def test_classify_rule_verdicts(verdict, rule):
    from admz.demos.inference.observability import classify_rule
    result = classify_rule(rule)
    assert result["verdict"] == verdict
    assert result["blind"] is (verdict == "blind")


def test_classify_rule_reports_every_applicable_channel():
    """"Alert on SFH" is the multi-channel case: alarm + record + a device-
    originated trigger. The verdict is the most trustworthy of the three."""
    from admz.demos.inference.observability import classify_rule
    sfh = _by_name(_anatomy(acs_api_devices=API_DEVICES), "Alert on SFH")
    result = classify_rule(sfh)
    assert [c["channel"] for c in result["channels"]] == [
        "acs_log_alarm", "recording_sequence", "device_event_direct"]
    assert result["verdict"] == "acs_log_alarm"
    assert result["blind"] is False
    direct = result["channels"][-1]
    assert direct["device_mac"] == "E827251FFB8D"
    assert direct["topic"].endswith("sfh_detector/SfHCandidate")
    assert direct["fidelity"] == "trigger"
    assert result["channels"][0]["fidelity"] == "rule"


def test_classify_rule_carries_the_fidelity_caveat():
    from admz.demos.inference.observability import FIDELITY_CAVEAT, classify_rule
    result = classify_rule(_rule(triggers=[_trigger("DeviceEvent")]))
    assert result["fidelity_caveat"] == FIDELITY_CAVEAT
    assert "require_all_triggers" in FIDELITY_CAVEAT


def test_classify_rule_notes_a_device_trigger_that_did_not_resolve():
    from admz.demos.inference.observability import classify_rule
    result = classify_rule(_rule(triggers=[_trigger("DeviceEvent", mac=None)]))
    assert result["blind"] is True
    assert any("did not resolve" in n for n in result["notes"])


def test_classify_rule_does_not_claim_a_foreign_http_notify():
    from admz.demos.inference.observability import classify_rule
    result = classify_rule(_rule(actions=[_action("HttpNotification", mac=None, params={
        "url": "https://someone-else.example/hook"})]))
    assert result["blind"] is True
    assert any("aimed elsewhere" in n for n in result["notes"])


def test_classify_rule_notes_that_a_blind_rule_needs_instrumenting():
    from admz.demos.inference.observability import classify_rule
    result = classify_rule(_rule(actions=[_action("MobileAppNotification")]))
    assert any("#127" in n for n in result["notes"])


def test_classify_rule_tolerates_a_junk_row():
    from admz.demos.inference.observability import classify_rule
    for junk in ({}, None, {"triggers": None, "actions": None}, {"actions": [{}]}):
        assert classify_rule(junk)["verdict"] == "blind"


def test_summarize_counts_channels_over_the_specimen():
    from admz.demos.inference.observability import summarize
    counts = summarize(_anatomy(acs_api_devices=API_DEVICES))
    assert counts["total"] == 5
    assert counts["acs_log_alarm"] == 1          # Alert on SFH
    assert counts["recording_sequence"] == 2     # Alert on SFH + Record ongoing call
    assert counts["device_event"] == 1           # Open Door Rule (I/O)
    assert counts["device_event_direct"] == 3    # the three DeviceEvent triggers
    assert counts["webhook"] == 0
    assert counts["blind"] == 1                  # External Trigger Example


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/acs/rules?anatomy=1 — identical envelope, identical degradation
# ═══════════════════════════════════════════════════════════════════════════
class _Req:
    def __init__(self, query=None):
        self.query_params = query or {}


def _patch_route(monkeypatch, *, enabled=True, available=True, boom=False):
    import admz.modules.acs_pro.firebird as fb
    # Bind the real reader first: the stub below replaces the module attribute
    # that ``_anatomy`` itself imports, so calling through it would recurse.
    real_anatomy = fb.rule_anatomy
    monkeypatch.setattr(fb, "firebird_enabled", lambda: enabled)
    monkeypatch.setattr(fb, "firebird_available",
                        lambda: (available, "ok" if available else
                                 "ACS.FDB not found in C:\\nope"))

    def _anatomy_stub(*a, **k):
        if boom:
            raise RuntimeError("copy locked")
        return real_anatomy(reader=_reader(), acs_api_devices=API_DEVICES)

    def _list_stub(*a, **k):
        if boom:
            raise RuntimeError("copy locked")
        return [{"id": 1, "name": "x", "enabled": True, "actions": []}]

    monkeypatch.setattr(fb, "rule_anatomy", _anatomy_stub)
    monkeypatch.setattr(fb, "list_rules", _list_stub)


def _call(query=None):
    from admz.modules.acs_pro.routes import acs_rules
    return _run(acs_rules(_Req(query)))


def test_rules_route_without_the_flag_returns_the_old_inventory(monkeypatch):
    _patch_route(monkeypatch)
    res = _call()
    assert res == {"success": True, "available": True, "reason": "ok",
                   "rules": [{"id": 1, "name": "x", "enabled": True, "actions": []}]}


@pytest.mark.parametrize("flag", ["1", "true", "yes", "on"])
def test_rules_route_anatomy_flag_returns_the_anatomy(monkeypatch, flag):
    _patch_route(monkeypatch)
    res = _call({"anatomy": flag})
    assert res["success"] is True and res["available"] is True and res["reason"] == "ok"
    sfh = _by_name(res["rules"], "Alert on SFH")
    assert sfh["triggers"][0]["device"]["mac"] == "E827251FFB8D"
    assert sfh["actions"][0]["kind"] == "Record"
    assert sfh["observability"]["verdict"] == "acs_log_alarm"


def test_rules_route_anatomy_flag_off_by_default(monkeypatch):
    _patch_route(monkeypatch)
    assert _call({"anatomy": "0"})["rules"][0]["actions"] == []


def test_rules_route_degrades_when_firebird_is_disabled(monkeypatch):
    _patch_route(monkeypatch, enabled=False)
    for query in (None, {"anatomy": "1"}):
        res = _call(query)
        assert res == {"success": True, "available": False,
                       "reason": "Firebird reader disabled", "rules": []}


def test_rules_route_degrades_when_firebird_is_unavailable(monkeypatch):
    """Non-ACS host: available False with a reason, never an error."""
    _patch_route(monkeypatch, available=False)
    for query in (None, {"anatomy": "1"}):
        res = _call(query)
        assert res["success"] is True and res["available"] is False
        assert "not found" in res["reason"] and res["rules"] == []


def test_rules_route_reports_a_read_failure_without_raising(monkeypatch):
    _patch_route(monkeypatch, boom=True)
    for query in (None, {"anatomy": "1"}):
        res = _call(query)
        assert res["success"] is False and res["available"] is True
        assert "copy locked" in res["reason"] and res["rules"] == []
