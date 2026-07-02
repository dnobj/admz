"""EventSchedulesFacet / MqttBridgeFacet / TimeApiFacet — the API-backed
facets built on the op-level revert seam (PR-C; sample shapes captured live
on a Q3538, AXIS OS 12)."""

import json

from admz.snapshot.facets.event_mqtt_bridge import MqttBridgeFacet
from admz.snapshot.facets.event_schedules import EventSchedulesFacet
from admz.snapshot.facets.time_api import TimeApiFacet

LIVE_SCHEDULES = [
    {"id": "com.axis.schedules.weekends", "name": "Weekends",
     "schedule": "DTSTART:19700103T000000\nDTEND:19700105T000000\nRRULE:FREQ=WEEKLY",
     "scheduleType": "INTERVAL"},
    {"id": "com.axis.schedules.office_hours", "name": "Office Hours",
     "schedule": "DTSTART:19700101T080000\nDTEND:19700101T180000\nRRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
     "scheduleType": "INTERVAL"},
]

LIVE_MQTT = {
    "deviceTopicPrefix": "axis/B8A44F661A2F",
    "publication": {
        "appendEventTopic": True,
        "customTopicPrefix": "",
        "eventFilter": [],
        "includeSerialNumberInPayload": False,
        "includeTopicNamespaces": True,
        "topicPrefix": "default",
    },
    "subscription": [],
}

LIVE_TIMEZONE = {
    "activeTimeZone": "America/Chicago",
    "dhcp": {"enabled": False, "timeZone": None},
    "iana": {"posixTimeZone": "CST6CDT,M3.2.0,M11.1.0",
             "timeZone": "America/Chicago"},
    "posix": {"dstEnabled": True, "timeZone": None},
}


class TestEventSchedules:
    def test_serialize_keys_by_stable_id(self):
        doc = EventSchedulesFacet().serialize({"event_schedules": LIVE_SCHEDULES})
        assert set(doc) == {"com.axis.schedules.weekends",
                            "com.axis.schedules.office_hours"}
        assert doc["com.axis.schedules.weekends"]["name"] == "Weekends"
        assert doc["com.axis.schedules.weekends"]["scheduleType"] == "INTERVAL"

    def test_serialize_missing_is_empty(self):
        assert EventSchedulesFacet().serialize({}) == {}

    def test_revert_update_changed_schedule(self):
        f = EventSchedulesFacet()
        baseline = f.serialize({"event_schedules": LIVE_SCHEDULES})
        steps = f.build_revert_ops(
            [("com.axis.schedules.weekends.name", "Weekends", "Hacked")],
            baseline)
        assert len(steps) == 1
        assert steps[0]["operation_id"] == "event-schedules:updateSchedule"
        assert steps[0]["params"]["id1"] == "com.axis.schedules.weekends"
        assert steps[0]["params"]["data"]["name"] == "Weekends"
        assert steps[0]["params"]["data"]["id"] == "com.axis.schedules.weekends"

    def test_revert_deletes_live_added_schedule(self):
        f = EventSchedulesFacet()
        baseline = f.serialize({"event_schedules": LIVE_SCHEDULES})
        steps = f.build_revert_ops(
            [("rogue-id.name", "<missing>", "Sneaky"),
             ("rogue-id.schedule", "<missing>", "DTSTART:...")],
            baseline)
        assert len(steps) == 1
        assert steps[0]["operation_id"] == "event-schedules:deleteSchedule"
        assert steps[0]["params"] == {"id1": "rogue-id"}
        assert "live-added" in steps[0]["description"]

    def test_revert_recreates_deleted_schedule(self):
        f = EventSchedulesFacet()
        baseline = f.serialize({"event_schedules": LIVE_SCHEDULES})
        steps = f.build_revert_ops(
            [("com.axis.schedules.weekends.name", "Weekends", "<missing>"),
             ("com.axis.schedules.weekends.schedule",
              LIVE_SCHEDULES[0]["schedule"], "<missing>")],
            baseline)
        assert len(steps) == 1
        assert steps[0]["operation_id"] == "event-schedules:createSchedule"
        assert steps[0]["params"]["data"]["id"] == "com.axis.schedules.weekends"

    def test_op_revertable_all_paths(self):
        assert EventSchedulesFacet().op_revertable("anything.name")

    def test_deserialize_updates_every_baseline_schedule(self):
        f = EventSchedulesFacet()
        baseline = f.serialize({"event_schedules": LIVE_SCHEDULES})
        calls = f.deserialize(baseline)
        assert len(calls) == 2
        assert all(c["operation_id"] == "event-schedules:updateSchedule"
                   for c in calls)


class TestMqttBridge:
    def test_serialize_drops_derived_prefix_and_stabilizes_lists(self):
        doc = MqttBridgeFacet().serialize({"event_mqtt_bridge": LIVE_MQTT})
        assert "deviceTopicPrefix" not in doc          # derived (serial-bearing)
        assert doc["publication"]["topicPrefix"] == "default"
        assert doc["publication"]["eventFilter"] == "[]"   # JSON-stable string
        assert doc["subscription"] == "[]"

    def test_serialize_censors_secret_keys(self):
        raw = {
            "publication": {"topicPrefix": "x", "password": "s3cret"},
            "subscription": [{"server": "b", "username": "u", "password": "p"}],
        }
        doc = MqttBridgeFacet().serialize({"event_mqtt_bridge": raw})
        blob = json.dumps(doc)
        assert "s3cret" not in blob and '"password"' not in blob

    def test_revert_writes_baseline_publication_without_path_noise(self):
        f = MqttBridgeFacet()
        baseline = f.serialize({"event_mqtt_bridge": LIVE_MQTT})
        steps = f.build_revert_ops(
            [("publication.topicPrefix", "default", "custom")], baseline)
        assert len(steps) == 1
        s = steps[0]
        assert s["operation_id"] == "event-mqtt-bridge:updatePublication"
        assert s["params"]["data"]["topicPrefix"] == "default"
        assert s["params"]["data"]["eventFilter"] == []    # decoded back to list

    def test_subscription_not_op_revertable(self):
        f = MqttBridgeFacet()
        assert f.op_revertable("publication.topicPrefix")
        assert not f.op_revertable("subscription")


class TestTimeApi:
    def test_serialize_only_iana_and_dhcp(self):
        doc = TimeApiFacet().serialize({"timezone": LIVE_TIMEZONE})
        assert doc == {"iana_timezone": "America/Chicago", "dhcp_enabled": False}
        # posix subtree is param-tracked (root.Time.POSIXTimeZone) — not here

    def test_revert_sets_baseline_timezone(self):
        steps = TimeApiFacet().build_revert_ops(
            [("iana_timezone", "America/Chicago", "Europe/Stockholm")],
            {"iana_timezone": "America/Chicago", "dhcp_enabled": False})
        assert steps == [{
            "operation_id": "time:setTimezone",
            "params": {"data": "America/Chicago"},   # leaf setter: bare string
            "description": "Restore baseline IANA timezone 'America/Chicago'",
        }]

    def test_only_iana_is_op_revertable(self):
        f = TimeApiFacet()
        assert f.op_revertable("iana_timezone")
        assert not f.op_revertable("dhcp_enabled")

    def test_empty_baseline_returns_none(self):
        assert TimeApiFacet().build_revert_ops([("iana_timezone", "X", "Y")], {}) is None


class TestConfigRestPathParams:
    """The executor must not leak path params into config-rest JSON bodies."""

    def test_path_param_excluded_from_body(self):
        from admz.executor.vapix import VapixExecutor
        ex = VapixExecutor()
        req = ex._build_config_rest(
            {"method": "PATCH",
             "base_path": "/config/rest/event-schedules/v2beta",
             "path": "/schedules/{id1}"},
            {"id1": "com.axis.schedules.weekends", "data": {"name": "W"}},
        )
        assert req.path.endswith("/schedules/com.axis.schedules.weekends")
        assert req.json_body == {"data": {"name": "W"}}   # id1 consumed by path
