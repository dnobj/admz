"""The ``demo_proposals`` store, confirm/dismiss, and their REST + MCP surface
(#124, slice 3).

Store tests take an explicit ``db_path`` (singletons bind their path at import,
so a test relying on the default would pollute the real DB). Route tests use the
real app on an isolated ``ADMZ_HOME``, the same harness as
``tests/test_demo_inference_runs.py``.

The load-bearing assertion in here is ``fragments_written == 0``: confirming a
proposal creates a demo that owns **nothing**, which is what keeps it out of
drift attribution and what makes confirm safe to leave ungated.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from admz.demos.inference.proposals import (STATUS_CONFIRMED, STATUS_DISMISSED,
                                            STATUS_PROPOSED, STATUS_SUPERSEDED,
                                            DemoProposal, ProposalStore)


# ═══════════════════════════════════════════════════════════════════════════
# Store
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def store(tmp_path):
    return ProposalStore(db_path=str(tmp_path / "admz.db"))


def _proposal(pid="p1", name="Lobby demo", devices=("cam", "spk"),
              content_key="ck1", score=0.8, **kw):
    return DemoProposal(
        id=pid, run_id=kw.pop("run_id", "run1"), content_key=content_key,
        name=name, device_ids=list(devices),
        roles={d: "detector" for d in devices},
        rules=[{"source": "acs", "device_id": devices[0], "rule_id": "7",
                "rule_name": "Announce", "condition_topic": "tns1:X"}],
        evidence=[{"kind": "edge:E1", "weight": 1.0, "detail": "why",
                   "source": "acs:7"}],
        suggested_owned_keys=[{"device_id": devices[0], "facet": "applications",
                               "path": "aoa", "reason": "r",
                               "not_capturable": True}],
        score=score, confidence="high", flags=[], overlaps=[], **kw)


class TestProposalStore:
    def test_roundtrip_keeps_every_evidence_field(self, store):
        store.upsert(_proposal())
        got = store.get("p1")
        assert got.name == "Lobby demo" and got.device_ids == ["cam", "spk"]
        assert got.rules[0]["source"] == "acs"
        assert got.evidence[0]["kind"] == "edge:E1"
        assert got.suggested_owned_keys[0]["not_capturable"] is True
        assert got.status == STATUS_PROPOSED and got.created_at > 0

    def test_list_defaults_to_open_proposals_strongest_first(self, store):
        store.upsert(_proposal("a", "Alpha", score=0.4, content_key="ka"))
        store.upsert(_proposal("b", "Bravo", score=0.9, content_key="kb"))
        store.upsert(_proposal("c", "Charlie", score=0.6, content_key="kc"))
        store.decide("c", STATUS_DISMISSED, decided_by="alice")
        assert [p.id for p in store.list()] == ["b", "a"]
        assert [p.id for p in store.list(status=None)] == ["b", "c", "a"]

    def test_proposed_name_is_backfilled_from_the_name_at_creation(self, store):
        store.upsert(_proposal(name="Activation demo"))
        got = store.get("p1")
        assert got.proposed_name == "Activation demo"
        assert got.to_dict()["renamed"] is False

    def test_decide_never_touches_proposed_name(self, store):
        """ADMZ's own guess is the only way to answer "was the deterministic
        namer any good?" after the fact — a rename must not destroy it."""
        store.upsert(_proposal(name="Activation demo"))
        store.decide("p1", STATUS_CONFIRMED, decided_by="alice",
                     name="Speaker announcement demo")
        got = store.get("p1")
        assert got.name == "Speaker announcement demo"
        assert got.proposed_name == "Activation demo"
        assert got.summary()["renamed"] is True

    def test_the_proposed_name_column_migrates_idempotently(self, tmp_path):
        """House try-ALTER pattern: a DB created by an older build gains the
        column, and re-opening it repeatedly is a no-op that keeps the data."""
        import sqlite3

        db = str(tmp_path / "admz.db")
        first = ProposalStore(db_path=db)
        first.upsert(_proposal(name="Activation demo"))

        # Simulate the pre-column build: drop it and re-open twice.
        conn = sqlite3.connect(db)
        try:
            conn.execute("ALTER TABLE demo_proposals DROP COLUMN proposed_name")
            conn.commit()
        finally:
            conn.close()
        assert ProposalStore(db_path=db).get("p1").proposed_name == ""
        again = ProposalStore(db_path=db)
        assert again.get("p1").proposed_name == ""   # legacy row stays honest
        assert again.get("p1").name == "Activation demo"
        assert again.get("p1").to_dict()["renamed"] is False

    def test_decide_records_who_and_when(self, store):
        store.upsert(_proposal())
        got = store.decide("p1", STATUS_CONFIRMED, decided_by="alice",
                           demo_id="d9", name="Renamed")
        assert got.status == STATUS_CONFIRMED and got.demo_id == "d9"
        assert got.decided_by == "alice" and got.decided_at > 0
        assert got.name == "Renamed"

    def test_supersede_only_moves_still_open_rows(self, store):
        store.upsert(_proposal("old", content_key="same"))
        store.upsert(_proposal("decided", content_key="same"))
        store.decide("decided", STATUS_DISMISSED, decided_by="alice")
        store.upsert(_proposal("new", content_key="same"))
        moved = store.supersede_open("same", except_id="new")
        assert moved == 1
        assert store.get("old").status == STATUS_SUPERSEDED
        assert store.get("decided").status == STATUS_DISMISSED   # untouched
        assert store.get("new").status == STATUS_PROPOSED

    def test_decided_content_keys_is_the_dismissal_memory(self, store):
        store.upsert(_proposal("a", content_key="ka"))
        store.upsert(_proposal("b", content_key="kb"))
        store.decide("a", STATUS_DISMISSED, decided_by="alice")
        decided = store.decided_content_keys()
        assert set(decided) == {"ka"} and decided["ka"].status == STATUS_DISMISSED

    def test_corrupt_stored_json_degrades_that_field_only(self, store):
        import sqlite3
        store.upsert(_proposal())
        conn = sqlite3.connect(store._db_path)
        conn.execute("UPDATE demo_proposals SET evidence_json = '{oops' "
                     "WHERE id = 'p1'")
        conn.commit()
        conn.close()
        got = store.get("p1")
        assert got.evidence == [] and got.name == "Lobby demo"

    def test_the_demos_table_is_untouched(self, store, tmp_path):
        """A proposal must never be enumerated by list_demos or walked by
        drift attribution — separate table, no exceptions."""
        from admz.demos.store import DemoStore
        store.upsert(_proposal())
        assert DemoStore(str(tmp_path / "admz.db")).list() == []


# ═══════════════════════════════════════════════════════════════════════════
# Confirm / dismiss cores
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _no_audit(monkeypatch):
    import admz.audit
    monkeypatch.setattr(admz.audit, "record_event", lambda *a, **k: None)


class _Registry:
    def __init__(self, ids):
        self._ids = set(ids)

    def device_exists(self, did):
        return did in self._ids

    def list_devices(self):
        return [{"device_id": d, "nickname": d, "tags": []} for d in sorted(self._ids)]

    def get_device_info(self, did):
        return {"device_id": did, "nickname": did, "tags": []}


class _Ctx:
    def __init__(self, tmp_path, device_ids=("cam", "spk")):
        from admz.demos.store import DemoStore
        self.demo_store = DemoStore(str(tmp_path / "admz.db"))
        self.proposal_store = ProposalStore(db_path=str(tmp_path / "admz.db"))
        self.registry = _Registry(device_ids)
        self.event_store = None
        self.git_repo = None


class TestConfirm:
    def test_creates_a_real_demo_with_rules_signals_and_roles(self, tmp_path):
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path)
        proposal = ctx.proposal_store.upsert(_proposal())
        out = confirm_proposal_core(ctx, proposal, "alice")

        assert out["success"] is True and out["rules_attached"] == 1
        demo = ctx.demo_store.list()[0]
        assert demo.name == "Lobby demo"
        assert sorted(demo.device_ids) == ["cam", "spk"]
        assert demo.roles == {"cam": "detector", "spk": "detector"}
        # attach_rule_to_demo derived the signal from the condition topic.
        assert demo.signals == [{"label": "Announce", "topic": "tns1:X",
                                 "device_id": "cam"}]
        assert demo.rules[0]["source"] == "acs"
        assert demo.active is False       # never adopted by inference
        assert ctx.proposal_store.get("p1").status == STATUS_CONFIRMED
        assert ctx.proposal_store.get("p1").demo_id == demo.id

    def test_confirm_writes_zero_fragments(self, tmp_path, monkeypatch):
        """Resolved DECISION b, and the reason confirm stays ungated: the demo
        owns nothing, so it changes no drift verdict."""
        from admz.demos import fragments as fr
        from admz.demos.inference.confirm import confirm_proposal_core

        def _boom(*a, **k):
            raise AssertionError("confirm must never write a fragment")

        monkeypatch.setattr(fr, "add_entries", _boom)
        ctx = _Ctx(tmp_path)
        out = confirm_proposal_core(ctx, ctx.proposal_store.upsert(_proposal()),
                                    "alice")
        assert out["fragments_written"] == 0
        assert out["suggested_owned_keys"][0]["not_capturable"] is True

    def test_name_purpose_devices_and_roles_are_overridable(self, tmp_path):
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path)
        out = confirm_proposal_core(
            ctx, ctx.proposal_store.upsert(_proposal()), "alice",
            name="Reception greeting", purpose="What we say",
            device_ids=["cam"], roles={"cam": "greeter"})
        demo = ctx.demo_store.get(out["demo"]["id"])
        assert demo.name == "Reception greeting" and demo.narrative == "What we say"
        assert demo.device_ids == ["cam"] and demo.roles == {"cam": "greeter"}

    # ── rename-on-confirm (ADR-0051 — the agent narration surface) ──────────
    #
    # The deterministic name is a serviceable PLACEHOLDER, not a good name (the
    # reference fleet's two-speaker demo comes back "Activation demo"). Slice 4
    # lets the agent hand a better name + a purpose narrative at confirm time —
    # and the fallback has to keep working with no LLM in the loop at all.

    def test_the_deterministic_name_survives_when_nothing_is_supplied(self,
                                                                      tmp_path):
        """No LLM, no override: the stored name and empty purpose are used
        verbatim, on both the demo and the proposal row."""
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path)
        proposal = ctx.proposal_store.upsert(_proposal(name="Activation demo"))
        out = confirm_proposal_core(ctx, proposal, "alice")

        demo = ctx.demo_store.get(out["demo"]["id"])
        assert demo.name == "Activation demo" and demo.narrative == ""
        row = ctx.proposal_store.get("p1")
        assert row.name == "Activation demo" and row.purpose == ""
        assert row.proposed_name == "Activation demo"
        assert out["proposal"]["renamed"] is False

    def test_a_better_name_and_purpose_are_recorded_on_both_sides(self, tmp_path):
        """The renamed proposal must not read back as the placeholder — the
        audit trail is "ADMZ guessed X, the operator confirmed Y"."""
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path)
        proposal = ctx.proposal_store.upsert(_proposal(name="Activation demo"))
        out = confirm_proposal_core(
            ctx, proposal, "alice", name="Speaker announcement demo",
            purpose="The C1110-E detects and the C1710 announces.")

        demo = ctx.demo_store.get(out["demo"]["id"])
        assert demo.name == "Speaker announcement demo"
        assert demo.narrative == "The C1110-E detects and the C1710 announces."
        row = ctx.proposal_store.get("p1")
        assert row.name == "Speaker announcement demo"
        assert row.purpose == "The C1110-E detects and the C1710 announces."
        assert out["proposal"]["name"] == "Speaker announcement demo"
        # …and ADMZ's own guess survives the rename, with both names on the view.
        assert row.proposed_name == "Activation demo"
        assert out["proposal"]["proposed_name"] == "Activation demo"
        assert out["proposal"]["renamed"] is True

    def test_confirming_records_both_names_in_the_audit_event(self, tmp_path,
                                                              monkeypatch):
        """The record itself has to tell the story — what ADMZ guessed and what
        the human accepted — or the naming layer can't be evaluated later."""
        from admz.demos.inference import confirm as confirm_mod

        import admz.audit as audit

        events = []
        monkeypatch.setattr(audit, "record_event",
                            lambda *a, **k: events.append((a, k)))
        ctx = _Ctx(tmp_path)
        confirm_mod.confirm_proposal_core(
            ctx, ctx.proposal_store.upsert(_proposal(name="Activation demo")),
            "alice", name="Speaker announcement demo")

        details = next(k["details"] for a, k in events
                       if a[1] == "demo.proposal_confirm")
        assert details["proposed_name"] == "Activation demo"
        assert details["name"] == "Speaker announcement demo"
        assert details["renamed"] is True

    def test_a_purpose_alone_keeps_the_deterministic_name(self, tmp_path):
        """Narration is per-field: writing only the narrative must not blank or
        rewrite the fallback name."""
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path)
        proposal = ctx.proposal_store.upsert(_proposal(name="Activation demo"))
        out = confirm_proposal_core(ctx, proposal, "alice",
                                    purpose="What the presenter says.")
        demo = ctx.demo_store.get(out["demo"]["id"])
        assert demo.name == "Activation demo"
        assert demo.narrative == "What the presenter says."

    def test_a_pre_written_purpose_on_the_proposal_carries_into_the_demo(self,
                                                                        tmp_path):
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path)
        proposal = ctx.proposal_store.upsert(
            _proposal(purpose="Narrated earlier in the review."))
        out = confirm_proposal_core(ctx, proposal, "alice")
        assert ctx.demo_store.get(out["demo"]["id"]).narrative == (
            "Narrated earlier in the review.")

    def test_a_blank_name_override_is_rejected_not_silently_accepted(self,
                                                                     tmp_path):
        """An empty rename would mint an unresolvable demo (every demo tool
        addresses demos by name)."""
        from admz.demos.actions import DemoActionError
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path)
        proposal = ctx.proposal_store.upsert(_proposal())
        with pytest.raises(DemoActionError):
            confirm_proposal_core(ctx, proposal, "alice", name="   ")
        assert ctx.demo_store.list() == []
        assert ctx.proposal_store.get("p1").status == STATUS_PROPOSED

    def test_devices_deleted_since_the_run_are_skipped_and_reported(self, tmp_path):
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path, device_ids=("cam",))     # spk is gone
        out = confirm_proposal_core(ctx, ctx.proposal_store.upsert(_proposal()),
                                    "alice")
        assert out["skipped_devices"] == ["spk"]
        assert ctx.demo_store.list()[0].device_ids == ["cam"]
        assert "no longer registered" in out["message"]

    def test_confirming_when_every_device_is_gone_is_a_409(self, tmp_path):
        from admz.demos.actions import DemoActionError
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path, device_ids=())
        with pytest.raises(DemoActionError) as exc:
            confirm_proposal_core(ctx, ctx.proposal_store.upsert(_proposal()),
                                  "alice")
        assert exc.value.status == 409
        assert ctx.demo_store.list() == []

    def test_confirming_twice_is_a_409(self, tmp_path):
        from admz.demos.actions import DemoActionError
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path)
        confirm_proposal_core(ctx, ctx.proposal_store.upsert(_proposal()), "alice")
        with pytest.raises(DemoActionError) as exc:
            confirm_proposal_core(ctx, ctx.proposal_store.get("p1"), "alice")
        assert exc.value.status == 409
        assert len(ctx.demo_store.list()) == 1

    def test_a_rule_naming_an_out_of_scope_device_is_skipped_not_attached(
            self, tmp_path):
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path)
        proposal = _proposal()
        proposal.rules[0]["device_id"] = "ghost"
        out = confirm_proposal_core(ctx, ctx.proposal_store.upsert(proposal),
                                    "alice")
        assert out["rules_attached"] == 0
        assert out["skipped_rules"][0]["reason"].startswith("device ghost")

    def test_confirm_supersedes_other_open_proposals_for_the_same_devices(
            self, tmp_path):
        from admz.demos.inference.confirm import confirm_proposal_core

        ctx = _Ctx(tmp_path)
        ctx.proposal_store.upsert(_proposal("other", content_key="ck1"))
        confirm_proposal_core(ctx, ctx.proposal_store.upsert(_proposal()), "alice")
        assert ctx.proposal_store.get("other").status == STATUS_SUPERSEDED


class TestDismiss:
    def test_dismiss_is_remembered(self, tmp_path):
        from admz.demos.inference.confirm import dismiss_proposal_core

        ctx = _Ctx(tmp_path)
        out = dismiss_proposal_core(ctx, ctx.proposal_store.upsert(_proposal()),
                                    "alice", reason="that's just the lab")
        assert out["success"] is True
        assert ctx.proposal_store.get("p1").status == STATUS_DISMISSED
        assert "ck1" in ctx.proposal_store.decided_content_keys()
        assert ctx.demo_store.list() == []

    def test_dismissing_a_confirmed_proposal_is_a_409(self, tmp_path):
        from admz.demos.actions import DemoActionError
        from admz.demos.inference.confirm import (confirm_proposal_core,
                                                  dismiss_proposal_core)

        ctx = _Ctx(tmp_path)
        confirm_proposal_core(ctx, ctx.proposal_store.upsert(_proposal()), "alice")
        with pytest.raises(DemoActionError) as exc:
            dismiss_proposal_core(ctx, ctx.proposal_store.get("p1"), "alice")
        assert exc.value.status == 409


class TestResolve:
    def test_by_id_then_by_unique_name(self, tmp_path):
        from admz.demos.actions import DemoActionError
        from admz.demos.inference.confirm import resolve_proposal

        ctx = _Ctx(tmp_path)
        ctx.proposal_store.upsert(_proposal())
        assert resolve_proposal(ctx.proposal_store, "p1").id == "p1"
        assert resolve_proposal(ctx.proposal_store, "lobby DEMO").id == "p1"
        with pytest.raises(DemoActionError) as exc:
            resolve_proposal(ctx.proposal_store, "nope")
        assert exc.value.status == 404

    def test_an_ambiguous_name_lists_the_candidates(self, tmp_path):
        from admz.demos.actions import DemoActionError
        from admz.demos.inference.confirm import resolve_proposal

        ctx = _Ctx(tmp_path)
        ctx.proposal_store.upsert(_proposal("a", content_key="ka"))
        ctx.proposal_store.upsert(_proposal("b", content_key="kb"))
        with pytest.raises(DemoActionError) as exc:
            resolve_proposal(ctx.proposal_store, "Lobby demo")
        assert "ambiguous" in str(exc.value)


# ═══════════════════════════════════════════════════════════════════════════
# The wizard's ACS-rule fix (additive `source`, no schema migration)
# ═══════════════════════════════════════════════════════════════════════════

class TestWizardRuleSource:
    def test_an_acs_rule_reads_unknown_not_missing(self, tmp_path):
        """Without this an ACS rule would read `observed: false` forever — a
        permanent, false 'your rule vanished'."""
        from types import SimpleNamespace

        from admz.demos import wizard
        from admz.demos.store import Demo, DemoStore

        store = DemoStore(str(tmp_path / "admz.db"))
        demo = store.create(Demo(id="", name="X", rules=[
            {"device_id": "cam", "rule_id": "7", "source": "acs"},
            {"device_id": "cam", "rule_id": "8", "source": "device"},
        ]))
        ctx = SimpleNamespace(
            registry=SimpleNamespace(
                get_device_info=lambda d: {"latest_observed_sha": "abc"}),
            git_repo=SimpleNamespace(read_facet=lambda *a, **k: {"8": {}}))
        rows = {r["rule_id"]: r for r in wizard._rules_status(ctx, demo)}
        assert rows["7"]["observed"] is None and rows["7"]["source"] == "acs"
        assert rows["8"]["observed"] is True

    def test_membership_defaults_to_device_for_every_pre_existing_entry(self,
                                                                        tmp_path):
        from types import SimpleNamespace

        from admz.demos import actions as da
        from admz.demos.store import Demo, DemoStore

        store = DemoStore(str(tmp_path / "admz.db"))
        demo = store.create(Demo(id="", name="X"))
        da.attach_rule_to_demo(SimpleNamespace(demo_store=store), demo,
                               {"device_id": "cam", "rule_id": "7"})
        assert store.get(demo.id).rules[0]["source"] == "device"


# ═══════════════════════════════════════════════════════════════════════════
# REST
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def isolate_admz_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    from admz import audit as audit_module
    monkeypatch.setattr(
        audit_module, "audit_log",
        audit_module.AuditLog(db_path=str(tmp_path / "admz.db")))


@pytest.fixture
def client(isolate_admz_dirs, monkeypatch):
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    monkeypatch.setattr("admz.authz.require_authenticated_principal", lambda p: None)
    monkeypatch.setattr("admz.modules.acs_pro.config.acs_enabled", lambda: False)
    from admz.api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def ctx(client):
    from admz.api.context import get_context
    return get_context()


def _add_device(ctx, device_id, **extra):
    info = {"host": "192.0.2.10", "nickname": device_id, "model": "AXIS TEST",
            "tags": []}
    info.update(extra)
    ctx.registry.add_device(device_id, info)


def _seed(ctx, **kw):
    ctx.proposal_store.upsert(_proposal(**kw))


def _seed_fleet(add, /):
    """Five devices, two of which share a tag.

    The fleet size matters: ``TAG_MAX_FRACTION`` treats a tag on 60 % or more of
    the fleet as a *fleet label*, not a demo grouping — so on a two-device
    registry a shared tag is ubiquitous and links nothing. Five devices make
    ``#lobby`` (2 of 5) distinctive, which is the whole point of the
    self-calibrating test.
    """
    add("AABBCCDDEE01", nickname="Reception cam", tags=["lobby"])
    add("AABBCCDDEE02", nickname="Reception speaker", tags=["lobby"])
    for i in range(3, 6):
        add(f"AABBCCDDEE0{i}", nickname=f"Spare {i}")


class TestProposalRoutes:
    def test_a_fast_run_returns_proposals_beside_the_graph(self, client, ctx):
        _seed_fleet(lambda did, **kw: _add_device(ctx, did, **kw))
        body = client.post("/api/demos/inference/runs",
                           json={"mode": "fast"}).json()
        assert body["run"]["status"] == "complete"
        assert body["report"]["include_weak"] is True
        names = [p["name"] for p in body["proposals"]]
        assert names, body["report"]
        # No ACS, no rules, only a shared tag: honest about what that means.
        assert body["proposals"][0]["confidence"] == "low"
        assert "no_topology" in body["proposals"][0]["flags"]
        assert "acs_absent" in body["proposals"][0]["flags"]

    def test_include_weak_false_returns_nothing_and_says_why(self, client, ctx):
        _seed_fleet(lambda did, **kw: _add_device(ctx, did, **kw))
        body = client.post("/api/demos/inference/runs",
                           json={"mode": "fast", "include_weak": False}).json()
        assert body["proposals"] == []
        assert body["report"]["weak_hidden"] >= 1
        assert "include_weak" in body["report"]["note"]

    def test_a_run_still_creates_no_demo(self, client, ctx):
        _seed_fleet(lambda did, **kw: _add_device(ctx, did, **kw))
        client.post("/api/demos/inference/runs", json={"mode": "fast"})
        assert client.get("/api/demos").json()["demos"] == []
        assert client.get("/api/demos/proposals").json()["count"] >= 1

    def test_proposals_route_is_not_shadowed_by_the_demo_id_route(self, client):
        res = client.get("/api/demos/proposals")
        assert res.status_code == 200 and res.json()["success"] is True

    def test_list_filter_and_detail(self, client, ctx):
        _seed(ctx)
        assert client.get("/api/demos/proposals").json()["count"] == 1
        assert client.get("/api/demos/proposals?status=confirmed").json()["count"] == 0
        one = client.get("/api/demos/proposals/p1").json()["proposal"]
        assert one["evidence"][0]["detail"] == "why"
        assert one["suggested_owned_keys"][0]["facet"] == "applications"
        assert client.get("/api/demos/proposals/ghost").status_code == 404

    def test_confirm_creates_the_demo_and_flips_the_status(self, client, ctx):
        _add_device(ctx, "cam")
        _add_device(ctx, "spk")
        _seed(ctx)
        res = client.post("/api/demos/proposals/p1/confirm", json={})
        assert res.status_code == 200
        body = res.json()
        assert body["fragments_written"] == 0
        demos = client.get("/api/demos").json()["demos"]
        assert len(demos) == 1 and demos[0]["name"] == "Lobby demo"
        assert client.get("/api/demos/proposals/p1").json()[
            "proposal"]["status"] == "confirmed"

    def test_confirm_body_carries_the_narrated_name_and_purpose(self, client, ctx):
        """The REST twin of the chat rename path (ADR-0051) — same core, so the
        console and the agent cannot diverge."""
        _add_device(ctx, "cam")
        _add_device(ctx, "spk")
        _seed(ctx)
        res = client.post("/api/demos/proposals/p1/confirm",
                          json={"name": "Speaker announcement demo",
                                "purpose": "Camera detects, speaker announces."})
        assert res.status_code == 200
        demo = client.get("/api/demos").json()["demos"][0]
        assert demo["name"] == "Speaker announcement demo"
        assert client.get("/api/demos/proposals/p1").json()["proposal"][
            "purpose"] == "Camera detects, speaker announces."

    def test_confirm_is_ungated_no_approval_envelope(self, client, ctx):
        """Inert by the ADR-0046 bar: metadata only, `active` stays False, no
        fragment is written — so it must NOT return a blocked envelope."""
        _add_device(ctx, "cam")
        _add_device(ctx, "spk")
        _seed(ctx)
        body = client.post("/api/demos/proposals/p1/confirm", json={}).json()
        assert body["success"] is True and "confirmation" not in body
        assert body["demo"]["active"] is False

    def test_confirming_twice_is_409(self, client, ctx):
        _add_device(ctx, "cam")
        _add_device(ctx, "spk")
        _seed(ctx)
        client.post("/api/demos/proposals/p1/confirm", json={})
        assert client.post("/api/demos/proposals/p1/confirm",
                           json={}).status_code == 409

    def test_dismiss_is_remembered_across_a_re_run(self, client, ctx):
        _seed_fleet(lambda did, **kw: _add_device(ctx, did, **kw))
        first = client.post("/api/demos/inference/runs",
                            json={"mode": "fast"}).json()
        pid = first["proposals"][0]["id"]
        assert client.post(f"/api/demos/proposals/{pid}/dismiss",
                           json={"reason": "just the lab"}).status_code == 200

        second = client.post("/api/demos/inference/runs",
                             json={"mode": "fast"}).json()
        assert second["proposals"] == []
        assert second["report"]["already_decided"][0]["status"] == "dismissed"

    def test_a_re_run_supersedes_the_previous_open_proposal(self, client, ctx):
        _seed_fleet(lambda did, **kw: _add_device(ctx, did, **kw))
        first = client.post("/api/demos/inference/runs",
                            json={"mode": "fast"}).json()["proposals"][0]
        second = client.post("/api/demos/inference/runs",
                             json={"mode": "fast"}).json()["proposals"][0]
        assert first["content_key"] == second["content_key"]
        assert first["id"] != second["id"]
        assert client.get(f"/api/demos/proposals/{first['id']}").json()[
            "proposal"]["status"] == "superseded"
        assert client.get("/api/demos/proposals").json()["count"] == 1

    def test_a_run_carries_its_proposals(self, client, ctx):
        _seed_fleet(lambda did, **kw: _add_device(ctx, did, **kw))
        run_id = client.post("/api/demos/inference/runs",
                             json={"mode": "fast"}).json()["run"]["id"]
        body = client.get(f"/api/demos/inference/runs/{run_id}").json()
        assert len(body["proposals"]) == 1

    def test_the_demos_page_renders_proposal_cards(self, client):
        html = client.get("/demos").text
        assert "renderRun" in html and "proposal" in html.lower()
        assert "confirm" in html.lower() and "dismiss" in html.lower()


# ═══════════════════════════════════════════════════════════════════════════
# MCP
# ═══════════════════════════════════════════════════════════════════════════

class TestMcpTools:
    @pytest.fixture
    def server(self, isolate_admz_dirs, monkeypatch):
        monkeypatch.setattr("admz.modules.acs_pro.config.acs_enabled", lambda: False)
        from admz.mcp.server import ADMZMCPServer
        return ADMZMCPServer()

    def _run(self, coro):
        return asyncio.new_event_loop().run_until_complete(coro)

    def test_infer_demos_proposes_and_creates_nothing(self, server):
        _seed_fleet(lambda did, **kw: server.registry.add_device(
            did, {"host": "192.0.2.1", "model": "AXIS TEST",
                  "nickname": kw.get("nickname", did),
                  "tags": kw.get("tags", [])}))
        res = self._run(server._infer_demos())
        assert res["success"] is True and res["proposals"]
        p = res["proposals"][0]
        assert p["confidence"] == "low" and "no_topology" in p["flags"]
        assert p["evidence"] and p["device_names"]
        assert server.components.demo_store.list() == []

    def test_list_and_detail(self, server):
        server.components.proposal_store.upsert(_proposal())
        listed = server._list_demo_proposals()
        assert listed["count"] == 1
        detail = server._list_demo_proposals("Lobby demo")
        assert detail["proposal"]["score_breakdown"] == {}
        assert detail["proposal"]["suggested_owned_keys"]

    def test_the_agent_view_carries_both_names(self, server):
        """So the model can contrast its suggestion with ADMZ's guess without
        having to remember what the guess was."""
        server.components.proposal_store.upsert(_proposal(name="Activation demo"))
        server.components.proposal_store.decide(
            "p1", "proposed", decided_by="", name="Speaker announcement demo")
        view = server._list_demo_proposals()["proposals"][0]
        assert view["name"] == "Speaker announcement demo"
        assert view["proposed_name"] == "Activation demo"
        assert view["renamed"] is True

    def test_confirm_and_dismiss_through_mcp(self, server):
        for did in ("cam", "spk"):
            server.registry.add_device(did, {"host": "192.0.2.1", "nickname": did,
                                             "model": "AXIS TEST", "tags": []})
        server.components.proposal_store.upsert(_proposal())
        out = server._confirm_demo_proposal({"proposal": "p1",
                                             "name": "Reception greeting"})
        assert out["success"] is True and out["fragments_written"] == 0
        assert server.components.demo_store.list()[0].name == "Reception greeting"

        server.components.proposal_store.upsert(_proposal("p2", "Other",
                                                          content_key="ck2"))
        assert server._dismiss_demo_proposal("p2", "no")["success"] is True
        assert server.components.proposal_store.get("p2").status == "dismissed"

    def test_unknown_proposal_is_an_error_not_a_crash(self, server):
        assert server._list_demo_proposals("ghost")["success"] is False
        assert server._dismiss_demo_proposal("ghost")["success"] is False

    def test_the_tools_are_dispatchable(self):
        from admz.mcp.dispatch import TOOL_HANDLERS
        for name in ("infer_demos", "list_demo_proposals",
                     "confirm_demo_proposal", "dismiss_demo_proposal"):
            assert name in TOOL_HANDLERS

    # ── rename-on-confirm reaches the tool surface (ADR-0051) ───────────────

    def test_confirm_schema_takes_an_optional_name_and_purpose(self):
        """No schema change was needed for slice 4 — but the narration flow
        depends on both staying optional (the deterministic name is the
        no-LLM fallback), so pin it."""
        from admz.mcp.tools.demos import TOOLS

        tool = next(t for t in TOOLS if t.name == "confirm_demo_proposal")
        props = tool.inputSchema["properties"]
        assert props["name"]["type"] == "string"
        assert props["purpose"]["type"] == "string"
        assert tool.inputSchema["required"] == ["proposal"]
        # The description has to say the stored name is a placeholder, or the
        # model happily confirms "Activation demo" forever.
        assert "PLACEHOLDER" in tool.description

    def test_confirm_through_mcp_carries_the_narrated_name_and_purpose(self,
                                                                       server):
        for did in ("cam", "spk"):
            server.registry.add_device(did, {"host": "192.0.2.1", "nickname": did,
                                             "model": "AXIS TEST", "tags": []})
        server.components.proposal_store.upsert(_proposal(name="Activation demo"))
        out = server._confirm_demo_proposal({
            "proposal": "Activation demo", "name": "Speaker announcement demo",
            "purpose": "The camera detects; the speaker announces."})
        assert out["success"] is True
        demo = server.components.demo_store.list()[0]
        assert demo.name == "Speaker announcement demo"
        assert demo.narrative == "The camera detects; the speaker announces."

    def test_confirm_through_mcp_without_a_name_keeps_the_placeholder(self,
                                                                      server):
        for did in ("cam", "spk"):
            server.registry.add_device(did, {"host": "192.0.2.1", "nickname": did,
                                             "model": "AXIS TEST", "tags": []})
        server.components.proposal_store.upsert(_proposal(name="Activation demo"))
        out = server._confirm_demo_proposal({"proposal": "p1"})
        assert out["success"] is True
        assert server.components.demo_store.list()[0].name == "Activation demo"
