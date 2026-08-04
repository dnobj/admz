"""A deep survey records the scope it scanned and the devices it WROTE to (#199).

`mode:"survey"` is not inert: its onboard phase reaches
`onboarding.onboard_device_credentials`, which for a factory-defaulted unit calls
`provisioning.provision_factory_default` — `pwdgrp.cgi:add-user`, `group=root`,
`auth_method="none"`. Before this there was **zero** `record_event` in
`onboarding.py`, `provisioning.py` or `collect.py`, and the run row held counts
only, so a survey that provisioned N root accounts left a single row reading
`{mode, run, register_new}`. Nothing could answer *what did that call write to*.

Vacuity note: "an audit row exists" is trivially green if the survey provisioned
nothing, and "no credential in the row" is trivially green if the row is empty.
So every test below plants a distinctive marker, and
`test_a_survey_that_provisions_nothing_says_so` pins the negative case against a
row that positively claims zero.

This records the WRITE, not the gate. Whether the write should be gated at all is
an open operator decision (#199) and is deliberately untouched here.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace as NS

import pytest

PASSWORD = "ZZ-PROVISIONED-SECRET-ZZ"
SUBNET = "10.20.0.0/24"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _principal():
    return NS(name="AXIS\\dnich", source="windows-local",
              groups=["Administrators"], is_anonymous=False)


# ── the allow-listed field builder ───────────────────────────────────────────
class TestSurveyAuditFields:
    def _fields(self, **kw):
        from admz.demos.inference.collect import _survey_audit_fields
        base = dict(run_id="r1", subnet=SUBNET, register_new=True,
                    registered=["b", "a"], provisioned=["a"])
        base.update(kw)
        return _survey_audit_fields(**base)

    def test_it_names_the_subnet_and_the_devices(self):
        """FIRST: if this is empty, every 'no credential' assertion is vacuous."""
        f = self._fields()
        assert f["subnet"] == SUBNET
        assert f["registered"] == ["a", "b"]        # sorted, deterministic
        assert f["provisioned"] == ["a"]
        assert f["registered_count"] == 2 and f["provisioned_count"] == 1
        assert f["run"] == "r1"

    def test_an_unnamed_subnet_is_recorded_honestly(self):
        """`None` means the ARP scanner auto-detects the local /24. Say that,
        rather than inventing a CIDR that was resolved several layers down."""
        f = self._fields(subnet=None)
        assert "auto-detected" in f["subnet"]

    def test_the_allow_list_is_load_bearing(self):
        """Every key the builder emits must be declared. A key added to the dict
        without being added to _SURVEY_AUDIT_KEYS is DROPPED, not leaked — that
        is what makes the list a boundary rather than documentation."""
        from admz.demos.inference.collect import _SURVEY_AUDIT_KEYS
        assert set(self._fields()) <= set(_SURVEY_AUDIT_KEYS)
        # And the list stays minimal + identifier-only.
        assert set(_SURVEY_AUDIT_KEYS) == {
            "run", "subnet", "register_new",
            "registered_count", "provisioned_count",
            "registered", "provisioned"}

    def test_it_records_no_device_detail_beyond_identifiers(self):
        """Discovered devices carry host/mac/model/firmware; none of it belongs
        in a log that is never pruned."""
        f = self._fields()
        blob = json.dumps(f)
        for leaked in ("host", "mac_address", "firmware", "password"):
            assert leaked not in blob


# ── the real run_survey path ─────────────────────────────────────────────────
@pytest.fixture
def survey(monkeypatch):
    """Drive the REAL `run_survey`, stubbing only the network and the device."""
    from admz.demos.inference import collect as C

    state = {"provision": [], "discovered": []}

    async def _discover(*, timeout, subnet):
        state["subnet_seen"] = subnet
        return list(state["discovered"])
    monkeypatch.setattr(C, "_discover", _discover)

    async def _snapshot(ctx, ids):
        return len(ids), 0
    monkeypatch.setattr(C, "_snapshot", _snapshot)

    async def _graph(ctx):
        return {"devices": [], "rules": [], "edges": []}
    monkeypatch.setattr(C, "collect_graph", _graph)
    monkeypatch.setattr(C, "describe", lambda g: "graph")

    async def _onboard_creds(*, device_id, registry, catalog, executors):
        from admz.onboarding import CREDENTIALS_NEEDED, PROVISIONED
        if device_id in state["provision"]:
            # The real call writes an admin account and returns this shape —
            # note the password is NOT in it, and must not appear anywhere.
            return {"status": PROVISIONED, "device_id": device_id,
                    "username": "root", "password_source": "fleet_default"}
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id}
    monkeypatch.setattr("admz.onboarding.onboard_device_credentials", _onboard_creds)

    registered = {}
    ctx = NS(
        registry=NS(list_devices=lambda: [],
                    add_device=lambda did, info: registered.__setitem__(did, info)),
        catalog=None, executors={}, snapshot_engine=None)

    store = NS(progress=lambda *a, **k: None,
               finish=lambda rid, graph, message="": NS(id=rid, status="complete"),
               fail=lambda rid, msg: None)

    def go(*, devices, provision, subnet=SUBNET, register_new=True):
        state["discovered"] = [
            NS(to_registry_dict=lambda d=d: dict(d)) for d in devices]
        state["provision"] = list(provision)
        _run(C.run_survey(ctx, store, "run-1", register_new=register_new,
                          subnet=subnet, principal=_principal()))
        from admz.audit import AuditLog
        rows = AuditLog().list_recent(action="demo.survey_devices")
        return rows[0] if rows else None
    return go


def _dev(mac, **kw):
    d = {"mac_address": mac, "device_id": mac, "host": "10.20.0.9",
         "model": "P3265", "password": PASSWORD}
    d.update(kw)
    return d


class TestTheSurveyRecordsWhatItWrote:
    def test_the_row_names_the_subnet_and_the_provisioned_devices(self, survey):
        """THE defect: before this, nothing recorded either."""
        row = survey(devices=[_dev("AA:BB:CC:00:00:01"), _dev("AA:BB:CC:00:00:02")],
                     provision=["AA:BB:CC:00:00:01"])
        assert row is not None, "the survey wrote no audit row at all"
        assert row.details["subnet"] == SUBNET
        assert row.details["provisioned"] == ["AA:BB:CC:00:00:01"]
        assert row.details["registered_count"] == 2
        assert row.details["provisioned_count"] == 1

    def test_it_is_attributed_to_the_operator(self, survey):
        """A background task still has to name who asked for it (#205)."""
        row = survey(devices=[_dev("AA:BB:CC:00:00:01")],
                     provision=["AA:BB:CC:00:00:01"])
        assert row.requester == "AXIS\\dnich"
        assert row.auth_source == "windows-local"

    def test_no_credential_reaches_the_row(self, survey):
        """The discovered device dict carries a password field; the audit log is
        never pruned, so nothing from it may land there."""
        row = survey(devices=[_dev("AA:BB:CC:00:00:01")],
                     provision=["AA:BB:CC:00:00:01"])
        blob = json.dumps({"d": row.details, "r": row.resource,
                           "e": row.error_message})
        assert PASSWORD not in blob
        assert "fleet_default" not in blob      # password_source is not recorded

    def test_a_survey_that_provisions_nothing_says_so(self, survey):
        """The anti-vacuity guard: a row that positively claims zero, rather
        than an absent row that could mean anything."""
        row = survey(devices=[_dev("AA:BB:CC:00:00:03")], provision=[])
        assert row is not None
        assert row.details["provisioned"] == []
        assert row.details["provisioned_count"] == 0
        assert row.details["registered_count"] == 1     # it DID still register

    def test_a_read_only_sweep_records_that_it_wrote_nothing(self, survey):
        """`register_new=False` is the documented opt-out — it must be visible
        in the record, not merely absent from it."""
        row = survey(devices=[_dev("AA:BB:CC:00:00:04")], provision=[],
                     register_new=False)
        assert row.details["register_new"] is False
        assert row.details["registered"] == [] and row.details["provisioned"] == []


def test_a_survey_that_provisions_records_something_at_all(monkeypatch):
    """The BEHAVIOURAL mutation target.

    Every other test here references a symbol this change introduces, so against
    the old code they can only fail structurally (ImportError / TypeError), which
    proves nothing about behaviour. This one deliberately calls `run_survey`
    using ONLY parameters that already existed, so it runs on both codebases —
    and asserts the thing that was actually missing: a survey that writes an
    admin account to a device must leave a record naming the scope and the
    device. Before this change there is no such row at all.
    """
    from admz.demos.inference import collect as C

    async def _discover(*, timeout, subnet):
        return [NS(to_registry_dict=lambda: _dev("AA:BB:CC:00:00:07"))]
    monkeypatch.setattr(C, "_discover", _discover)

    async def _snapshot(ctx, ids):
        return 1, 0
    monkeypatch.setattr(C, "_snapshot", _snapshot)

    async def _graph(ctx):
        return {}
    monkeypatch.setattr(C, "collect_graph", _graph)
    monkeypatch.setattr(C, "describe", lambda g: "graph")

    async def _creds(*, device_id, registry, catalog, executors):
        from admz.onboarding import PROVISIONED
        return {"status": PROVISIONED, "device_id": device_id}
    monkeypatch.setattr("admz.onboarding.onboard_device_credentials", _creds)

    ctx = NS(registry=NS(list_devices=lambda: [], add_device=lambda d, i: None),
             catalog=None, executors={}, snapshot_engine=None)
    store = NS(progress=lambda *a, **k: None, fail=lambda *a, **k: None,
               finish=lambda rid, graph, message="": NS(id=rid, status="ok"))

    # No `principal=` — that kwarg is part of this change.
    _run(C.run_survey(ctx, store, "run-3", subnet=SUBNET))

    from admz.audit import AuditLog
    rows = AuditLog().list_recent(action="demo.survey_devices")
    assert rows, ("a survey provisioned a device and recorded nothing about "
                  "the subnet it scanned or the device it wrote to")
    blob = json.dumps(rows[0].details)
    assert SUBNET in blob and "AA:BB:CC:00:00:07" in blob


def test_run_row_scope(monkeypatch):
    """`graph["survey"]` gains the subnet and the device lists (#199)."""
    from admz.demos.inference import collect as C

    async def _discover(*, timeout, subnet):
        return [NS(to_registry_dict=lambda: _dev("AA:BB:CC:00:00:09"))]
    monkeypatch.setattr(C, "_discover", _discover)

    async def _snapshot(ctx, ids):
        return 1, 0
    monkeypatch.setattr(C, "_snapshot", _snapshot)

    async def _graph(ctx):
        return {}
    monkeypatch.setattr(C, "collect_graph", _graph)
    monkeypatch.setattr(C, "describe", lambda g: "graph")
    monkeypatch.setattr(C, "_record_survey_writes", lambda *a, **k: None)

    async def _creds(*, device_id, registry, catalog, executors):
        from admz.onboarding import PROVISIONED
        return {"status": PROVISIONED, "device_id": device_id}
    monkeypatch.setattr("admz.onboarding.onboard_device_credentials", _creds)

    captured = {}
    ctx = NS(registry=NS(list_devices=lambda: [], add_device=lambda d, i: None),
             catalog=None, executors={}, snapshot_engine=None)
    store = NS(progress=lambda *a, **k: None, fail=lambda *a, **k: None,
               finish=lambda rid, graph, message="": (
                   captured.__setitem__("g", graph) or NS(id=rid, status="ok")))

    _run(C.run_survey(ctx, store, "run-2", subnet=SUBNET, principal=None))
    s = captured["g"]["survey"]
    assert s["subnet"] == SUBNET
    assert s["provisioned"] == ["AA:BB:CC:00:00:09"]
    assert s["registered"] == ["AA:BB:CC:00:00:09"]
