"""Rule ↔ demo correlation (ADR-0048 Phase B).

The demo store's rule-membership column and the attach/detach bookkeeping that
records a created rule on a demo + auto-attaches its condition topic as a demo
signal (deduped), with implicit device binding, and reverses it on delete.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from admz.demos.store import Demo, DemoStore


@pytest.fixture(autouse=True)
def _no_audit(monkeypatch):
    import admz.audit
    monkeypatch.setattr(admz.audit, "record_event", lambda *a, **k: None)


@pytest.fixture
def store(tmp_path):
    return DemoStore(str(tmp_path / "demos.db"))


def _ctx(store):
    return SimpleNamespace(demo_store=store)


def _rule(rule_id="7", topic="tns1:Device/tnsaxis:IO/Port", device="cam-a", name="PIR play"):
    return {"device_id": device, "rule_id": rule_id, "rule_name": name,
            "condition_id": "c1", "condition_topic": topic}


class TestStoreRules:
    def test_rules_roundtrip(self, store):
        d = store.create(Demo(id="", name="Lobby"))
        assert store.get(d.id).rules == []
        d.rules = [{"device_id": "cam-a", "rule_id": "7"}]
        store.update(d)
        assert store.get(d.id).rules == [{"device_id": "cam-a", "rule_id": "7"}]

    def test_to_dict_includes_rules(self, store):
        d = store.create(Demo(id="", name="X", rules=[{"rule_id": "1"}]))
        assert store.get(d.id).to_dict()["rules"] == [{"rule_id": "1"}]


class TestAttach:
    def test_records_membership_signal_and_binds_device(self, store):
        import admz.demos.actions as da
        demo = store.create(Demo(id="", name="Lobby"))
        da.attach_rule_to_demo(_ctx(store), demo, _rule())
        got = store.get(demo.id)
        assert len(got.rules) == 1 and got.rules[0]["rule_id"] == "7"
        assert got.signals == [{"label": "PIR play",
                                "topic": "tns1:Device/tnsaxis:IO/Port", "device_id": "cam-a"}]
        assert got.device_ids == ["cam-a"]  # implicit bind (device-scoped demo)

    def test_dedupes_on_device_and_rule(self, store):
        import admz.demos.actions as da
        demo = store.create(Demo(id="", name="Lobby"))
        da.attach_rule_to_demo(_ctx(store), demo, _rule(name="v1"))
        da.attach_rule_to_demo(_ctx(store), store.get(demo.id), _rule(name="v2"))
        got = store.get(demo.id)
        assert len(got.rules) == 1 and got.rules[0]["rule_name"] == "v2"  # replaced, not doubled
        assert len(got.signals) == 1

    def test_signal_deduped_across_rules_same_topic(self, store):
        import admz.demos.actions as da
        demo = store.create(Demo(id="", name="Lobby"))
        da.attach_rule_to_demo(_ctx(store), demo, _rule(rule_id="7"))
        da.attach_rule_to_demo(_ctx(store), store.get(demo.id), _rule(rule_id="8"))
        got = store.get(demo.id)
        assert len(got.rules) == 2 and len(got.signals) == 1  # two rules, one topic → one signal

    def test_tag_scoped_demo_not_bound(self, store):
        import admz.demos.actions as da
        demo = store.create(Demo(id="", name="Lobby", tag="lobby"))
        da.attach_rule_to_demo(_ctx(store), demo, _rule())
        assert store.get(demo.id).device_ids == []  # tag-scoped → no explicit bind

    def test_no_topic_no_signal(self, store):
        import admz.demos.actions as da
        demo = store.create(Demo(id="", name="Lobby"))
        da.attach_rule_to_demo(_ctx(store), demo, _rule(topic=None))
        got = store.get(demo.id)
        assert len(got.rules) == 1 and got.signals == []


class TestDetach:
    def test_removes_membership_and_signal(self, store):
        import admz.demos.actions as da
        demo = store.create(Demo(id="", name="Lobby"))
        da.attach_rule_to_demo(_ctx(store), demo, _rule())
        da.detach_rule_from_demo(_ctx(store), "7", "cam-a")
        got = store.get(demo.id)
        assert got.rules == [] and got.signals == []

    def test_keeps_signal_when_another_rule_shares_topic(self, store):
        import admz.demos.actions as da
        demo = store.create(Demo(id="", name="Lobby"))
        da.attach_rule_to_demo(_ctx(store), demo, _rule(rule_id="7"))
        da.attach_rule_to_demo(_ctx(store), store.get(demo.id), _rule(rule_id="8"))
        da.detach_rule_from_demo(_ctx(store), "7", "cam-a")
        got = store.get(demo.id)
        assert [r["rule_id"] for r in got.rules] == ["8"]
        assert len(got.signals) == 1  # 8 still uses the topic

    def test_unknown_rule_is_noop(self, store):
        import admz.demos.actions as da
        demo = store.create(Demo(id="", name="Lobby", rules=[{"device_id": "x", "rule_id": "1"}]))
        da.detach_rule_from_demo(_ctx(store), "999", "cam-a")
        assert len(store.get(demo.id).rules) == 1
