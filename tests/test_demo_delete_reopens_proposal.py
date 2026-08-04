"""Deleting a demo re-opens the proposal it was confirmed from (#201).

`demo_proposals.demo_id` is the only persisted back-reference to a demo, and
nothing reconciled it. The row stayed `confirmed`, so `decided_content_keys` —
the memory that stops a re-run re-asking what a human already answered — kept
skipping that member set forever. `content_key` is `sha1(sorted member ids)`, so
a stable fleet re-derives the same key on every run and the cluster is never
proposed again. Both exits were shut too: confirm 409s ("already confirmed") and
dismiss 409s with *"delete the demo instead"* — advice the operator had already
taken.

**Vacuity note.** "the proposal is not confirmed any more" is trivially green
against a row that was never confirmed, and "the cluster is proposed again" is
trivially green against a run that proposes everything. So every test here pins
the *before* state positively first —
`TestTheLockoutIsRealBeforeTheFix::test_confirming_locks_the_member_set` is that
guard, and `test_a_dismissed_proposal_is_not_disturbed` is the negative: a row
that must NOT move proves the status filter is doing work rather than the update
sweeping the table.

Re-open rather than delete: the evidence, score and rules survive, so the
operator gets *both* exits back — re-confirm with a corrected device list, or
dismiss — which is what the issue's "two demos, not one" scenario actually
needs. `ProposalStore.delete` stays uncalled and is deliberately not wired up.
"""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, __import__("os").path.dirname(__file__))

from test_demo_proposals import (  # noqa: E402
    _Ctx, _add_device, _proposal, _seed, _seed_fleet, client, ctx,  # noqa: F401
    isolate_admz_dirs,  # noqa: F401
)

STATUS_PROPOSED = "proposed"
STATUS_CONFIRMED = "confirmed"
STATUS_DISMISSED = "dismissed"


@pytest.fixture(autouse=True)
def _no_audit_noise(monkeypatch):
    """Only the audit-content test cares about the row; the rest must not
    depend on a writable audit DB."""
    yield


def _confirm_then_delete(c):
    """Confirm `p1` into a demo, then delete that demo. Returns the demo id."""
    from admz.demos.actions import delete_demo_core
    from admz.demos.inference.confirm import confirm_proposal_core

    confirm_proposal_core(c, c.proposal_store.upsert(_proposal()), "alice")
    demo = c.demo_store.list()[0]
    delete_demo_core(c, demo, "alice")
    return demo.id


# ── the anti-vacuity guard: the lockout has to exist to be released ──────────
class TestTheLockoutIsRealBeforeTheFix:
    def test_confirming_locks_the_member_set(self, tmp_path):
        """FIRST. If confirm did not put `ck1` into the decided memory, every
        "it is gone afterwards" assertion below would pass for free."""
        from admz.demos.inference.confirm import confirm_proposal_core

        c = _Ctx(tmp_path)
        confirm_proposal_core(c, c.proposal_store.upsert(_proposal()), "alice")
        row = c.proposal_store.get("p1")
        assert row.status == STATUS_CONFIRMED
        assert row.demo_id == c.demo_store.list()[0].id
        assert "ck1" in c.proposal_store.decided_content_keys(), (
            "the lockout this issue is about does not exist; the rest of this "
            "file is measuring nothing")


# ── the fix, at the core ─────────────────────────────────────────────────────
class TestDeletingTheDemoReopensItsProposal:
    def test_the_row_goes_back_to_proposed_with_the_link_cleared(self, tmp_path):
        c = _Ctx(tmp_path)
        _confirm_then_delete(c)
        row = c.proposal_store.get("p1")
        assert row.status == STATUS_PROPOSED
        assert row.demo_id == "", "the row still points at a demo that is gone"
        assert row.decided_by == "" and row.decided_at == 0, (
            "a re-opened row claims a decision it no longer has")

    def test_the_member_set_leaves_the_decided_memory(self, tmp_path):
        """THE defect, at its narrowest: this dict is what `persist_proposals`
        consults to skip a cluster."""
        c = _Ctx(tmp_path)
        _confirm_then_delete(c)
        assert c.proposal_store.decided_content_keys() == {}

    def test_the_evidence_survives(self, tmp_path):
        """Why re-open beats delete: the operator's proposal comes back intact,
        so confirming it again with corrected devices is one call, not a re-run
        of inference."""
        c = _Ctx(tmp_path)
        _confirm_then_delete(c)
        row = c.proposal_store.get("p1")
        # Ordered first deliberately: every assertion below is true of a row
        # that never re-opened at all, so without this the test is vacuous.
        assert row.status == STATUS_PROPOSED
        assert row.device_ids == ["cam", "spk"]
        assert len(row.evidence) == 1 and row.score == 0.8
        assert row.rules and row.rules[0]["rule_name"] == "Announce"
        assert row.content_key == "ck1"

    def test_dismiss_now_works_the_way_the_409_promised(self, tmp_path):
        """The message said "delete the demo instead". It now delivers."""
        from admz.demos.inference.confirm import dismiss_proposal_core

        c = _Ctx(tmp_path)
        _confirm_then_delete(c)
        out = dismiss_proposal_core(c, c.proposal_store.get("p1"), "alice",
                                    reason="that was two demos, not one")
        assert out["success"] is True
        assert c.proposal_store.get("p1").status == STATUS_DISMISSED

    def test_re_confirming_with_a_corrected_device_list_works(self, tmp_path):
        """The issue's actual scenario: three devices were really two demos.
        The operator deletes and re-confirms a narrower set."""
        from admz.demos.inference.confirm import confirm_proposal_core

        c = _Ctx(tmp_path)
        _confirm_then_delete(c)
        out = confirm_proposal_core(c, c.proposal_store.get("p1"), "alice",
                                    name="Lobby camera only",
                                    device_ids=["cam"])
        assert out["success"] is True
        demo = c.demo_store.list()[0]
        assert demo.name == "Lobby camera only" and demo.device_ids == ["cam"]

    def test_the_audit_row_names_what_was_reopened(self, tmp_path, monkeypatch):
        """A silent state change on someone else's table is how #201 stayed
        invisible; the delete event says so."""
        import admz.audit as audit_mod
        seen = {}
        monkeypatch.setattr(
            audit_mod, "record_event",
            lambda *a, **k: seen.update(action=a[1], details=k.get("details")))
        c = _Ctx(tmp_path)
        _confirm_then_delete(c)
        assert seen["action"] == "demo.delete"
        assert seen["details"]["proposals_reopened"] == ["p1"]


# ── the negatives: the update must not sweep ─────────────────────────────────
class TestItTouchesNothingElse:
    def test_a_dismissed_proposal_is_not_disturbed(self, tmp_path):
        """Load-bearing. `reopen_for_demo` filters on status AND demo_id; a
        dismissal is an operator decision that no demo delete may undo. Without
        the status filter this row would come back as `proposed`."""
        from admz.demos.actions import create_demo_core, delete_demo_core
        from admz.demos.inference.confirm import dismiss_proposal_core

        c = _Ctx(tmp_path)
        dismiss_proposal_core(c, c.proposal_store.upsert(_proposal()), "alice")
        demo = create_demo_core(c, {"name": "Unrelated", "device_ids": ["cam"]},
                                "alice")
        delete_demo_core(c, demo, "alice")
        assert c.proposal_store.get("p1").status == STATUS_DISMISSED

    def test_another_demos_proposal_is_not_disturbed(self, tmp_path):
        """Two confirmed proposals, one demo deleted: only its own row moves."""
        from admz.demos.actions import delete_demo_core
        from admz.demos.inference.confirm import confirm_proposal_core

        c = _Ctx(tmp_path, device_ids=("cam", "spk"))
        confirm_proposal_core(c, c.proposal_store.upsert(_proposal()), "alice")
        confirm_proposal_core(
            c, c.proposal_store.upsert(
                _proposal("p2", name="Other", content_key="ck2")), "alice")
        keep = [d for d in c.demo_store.list() if d.name == "Other"][0]
        drop = [d for d in c.demo_store.list() if d.name == "Lobby demo"][0]
        delete_demo_core(c, drop, "alice")
        assert c.proposal_store.get("p1").status == STATUS_PROPOSED
        assert c.proposal_store.get("p2").status == STATUS_CONFIRMED
        assert c.proposal_store.get("p2").demo_id == keep.id

    def test_a_demo_with_no_proposal_deletes_cleanly(self, tmp_path):
        """Most demos are created by hand and have no proposal at all."""
        from admz.demos.actions import create_demo_core, delete_demo_core

        c = _Ctx(tmp_path)
        demo = create_demo_core(c, {"name": "Hand made",
                                    "device_ids": ["cam"]}, "alice")
        delete_demo_core(c, demo, "alice")
        assert c.demo_store.list() == []

    def test_a_broken_proposal_store_does_not_fail_the_delete(self, tmp_path,
                                                              caplog):
        """The demo row is already gone by then. Failing to tidy the proposal
        must not turn a completed delete into a 500 — same policy as the
        fragment cleanup three lines below it."""
        from types import SimpleNamespace as NS

        from admz.demos.actions import create_demo_core, delete_demo_core

        c = _Ctx(tmp_path)
        demo = create_demo_core(c, {"name": "X", "device_ids": ["cam"]}, "alice")

        def _boom(_demo_id):
            raise RuntimeError("database is locked")
        c.proposal_store = NS(reopen_for_demo=_boom)
        delete_demo_core(c, demo, "alice")           # must not raise
        assert c.demo_store.list() == []
        assert any("proposal re-open failed" in r.getMessage()
                   for r in caplog.records)


# ── the store method on its own ──────────────────────────────────────────────
class TestReopenForDemo:
    def test_an_empty_or_unknown_demo_id_is_a_no_op(self, tmp_path):
        from admz.demos.inference.proposals import ProposalStore

        store = ProposalStore(db_path=str(tmp_path / "admz.db"))
        store.upsert(_proposal())
        assert store.reopen_for_demo("") == []
        assert store.reopen_for_demo("nosuchdemo") == []
        assert store.get("p1").status == STATUS_PROPOSED

    def test_it_returns_the_ids_it_moved(self, tmp_path):
        from admz.demos.inference.proposals import ProposalStore

        store = ProposalStore(db_path=str(tmp_path / "admz.db"))
        store.upsert(_proposal())
        store.decide("p1", STATUS_CONFIRMED, decided_by="alice", demo_id="d7")
        assert store.reopen_for_demo("d7") == ["p1"]
        assert store.reopen_for_demo("d7") == [], "a second call must be inert"


# ── end to end, through the surfaces an operator actually uses ───────────────
class TestThroughTheRealSurfaces:
    def test_rest_delete_lets_re_inference_propose_the_cluster_again(
            self, client, ctx):
        """THE failure scenario from the issue, start to finish, over HTTP and
        through the real clustering — no store stubs.

        Run inference, confirm, delete the demo via `DELETE /api/demos/{id}`,
        re-run inference. Before the fix the second run returned zero proposals
        and an `already_decided` entry naming a demo that no longer existed.
        """
        _seed_fleet(lambda did, **kw: _add_device(ctx, did, **kw))
        first = client.post("/api/demos/inference/runs",
                            json={"mode": "fast"}).json()
        pid = first["proposals"][0]["id"]
        key = first["proposals"][0]["content_key"]

        confirmed = client.post(f"/api/demos/proposals/{pid}/confirm", json={})
        assert confirmed.status_code == 200
        demo_id = confirmed.json()["demo"]["id"]

        # Anti-vacuity: prove the lockout is armed before removing it.
        locked = client.post("/api/demos/inference/runs",
                             json={"mode": "fast"}).json()
        assert locked["proposals"] == []
        assert locked["report"]["already_decided"][0]["demo_id"] == demo_id

        assert client.delete(f"/api/demos/{demo_id}").status_code == 200

        again = client.post("/api/demos/inference/runs",
                            json={"mode": "fast"}).json()
        assert again["report"]["already_decided"] == [], (
            "the cluster is still locked out by a demo that no longer exists")
        assert [p["content_key"] for p in again["proposals"]] == [key]

    def test_the_reopened_proposal_is_listed_and_dismissible_over_rest(
            self, client, ctx):
        """It comes back on the default `status=proposed` listing — the
        operator can see it, not just re-derive it."""
        _add_device(ctx, "cam")
        _add_device(ctx, "spk")
        _seed(ctx)
        demo_id = client.post("/api/demos/proposals/p1/confirm",
                              json={}).json()["demo"]["id"]
        assert client.get("/api/demos/proposals").json()["count"] == 0
        client.delete(f"/api/demos/{demo_id}")

        listed = client.get("/api/demos/proposals").json()
        assert [p["id"] for p in listed["proposals"]] == ["p1"]
        assert listed["proposals"][0]["demo_id"] == ""
        assert client.post("/api/demos/proposals/p1/dismiss",
                           json={"reason": "two demos"}).status_code == 200

    def test_the_mcp_delete_path_reopens_too(self, tmp_path):
        """`delete_demo` is an MCP tool as well as a REST route, and both call
        `delete_demo_core` — so the fix belongs there and not in the route."""
        from admz.demos.actions import delete_demo_core
        from admz.demos.inference.confirm import confirm_proposal_core

        c = _Ctx(tmp_path)
        confirm_proposal_core(c, c.proposal_store.upsert(_proposal()), "alice")
        # Exactly what MCPServer._delete_demo does: resolve, then call the core
        # with `self.components` — the same object shape AppContext delegates to.
        from admz.demos.actions import resolve_demo
        demo = resolve_demo(c.demo_store, "Lobby demo")
        delete_demo_core(c, demo, "mcp-agent")
        assert c.proposal_store.get("p1").status == STATUS_PROPOSED
