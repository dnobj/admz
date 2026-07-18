"""Fragment demo activation (ADR-0047 slice 3 / ADR-0050 Phase A).

Covers push-field synthesis (values + op-revertable/non-param prefilter) and the
completion handlers that flip demo.active — the core guarantee being that the
flip happens ONLY on a COMPLETED plan (a partial/failed push leaves the demo
inactive with a note), and that a fresh overlap conflict at completion blocks it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from admz.plans.models import PlanStatus


# ---------------------------------------------------------------------------
# synthesize_push_fields — value + prefilter
# ---------------------------------------------------------------------------


class _Facet:
    def __init__(self, op_revertable=False, revert=("k", "v")):
        self._op = op_revertable
        self._rv = revert

    def op_revertable(self, path):
        return self._op

    def revert_param(self, path, value):
        return self._rv

    def canonical_key(self, path):
        return "root." + path


class TestSynthesize:
    def test_only_param_writable_pushed_others_warned(self, monkeypatch):
        from admz.demos import activation as act
        from admz.demos import fragments as fr

        monkeypatch.setattr(fr, "_set_map_for", lambda git, demo, did: {
            ("ntp", "root.NTP.Server"): "1.1.1.1",   # param-writable → push
            ("img", "root.Image.X"): "hi",            # op-revertable  → skip+warn
            ("ro", "root.RO.Y"): "z",                 # not param-writable → skip+warn
        })
        facets = {
            "ntp": _Facet(op_revertable=False, revert=("root.NTP.Server", "1.1.1.1")),
            "img": _Facet(op_revertable=True),
            "ro": _Facet(op_revertable=False, revert=None),
        }
        demo = SimpleNamespace(id="d1", roles={"dev": "r"})
        fields, warns = act.synthesize_push_fields(None, demo, "dev", facets)
        assert [(f.facet, f.expected, f.actual) for f in fields] == [("ntp", "1.1.1.1", "")]
        assert len(warns) == 2  # img + ro
        assert any("API-backed" in w for w in warns)
        assert any("not param-writable" in w for w in warns)

    def test_missing_facet_is_skipped(self, monkeypatch):
        from admz.demos import activation as act
        from admz.demos import fragments as fr
        monkeypatch.setattr(fr, "_set_map_for", lambda git, demo, did: {("x", "root.X.Y"): "v"})
        fields, warns = act.synthesize_push_fields(None, SimpleNamespace(id="d", roles={}), "dev", {})
        assert fields == [] and len(warns) == 1


# ---------------------------------------------------------------------------
# Completion handlers — flip only on COMPLETED
# ---------------------------------------------------------------------------


class _Demo:
    def __init__(self, active=False):
        self.id = "d1"
        self.name = "Lobby"
        self.active = active


class _Store:
    def __init__(self, demo):
        self._d = demo
        self.updates = []

    def get(self, i):
        return self._d if i == self._d.id else None

    def list(self):
        return [self._d]

    def update(self, d):
        self.updates.append(d.active)


class _Ctx:
    def __init__(self, demo):
        self.demo_store = _Store(demo)
        self.git_repo = object()
        self.registry = object()


def _plan(status):
    return SimpleNamespace(status=status, plan_id="p1", completion_note="")


@pytest.fixture
def wired(monkeypatch):
    """Stub get_context, overlap_conflicts, and record_event for handler tests."""
    import admz.api.context as apictx
    import admz.audit as audit
    import admz.demos.fragments as fr

    demo = _Demo()
    ctx = _Ctx(demo)
    monkeypatch.setattr(apictx, "get_context", lambda: ctx)
    monkeypatch.setattr(audit, "record_event", lambda *a, **k: None)
    monkeypatch.setattr(fr, "overlap_conflicts", lambda *a, **k: [])
    return SimpleNamespace(demo=demo, ctx=ctx, fr=fr, monkeypatch=monkeypatch)


class TestActivationHandler:
    def test_flips_active_on_completed(self, wired):
        from admz.demos import activation as act
        p = _plan(PlanStatus.COMPLETED)
        act.on_activation_complete(p, {"demo_id": "d1", "demo_name": "Lobby"})
        assert wired.demo.active is True
        assert wired.ctx.demo_store.updates == [True]
        assert "active" in p.completion_note.lower()

    def test_stays_inactive_on_failed(self, wired):
        from admz.demos import activation as act
        p = _plan(PlanStatus.FAILED)
        act.on_activation_complete(p, {"demo_id": "d1", "demo_name": "Lobby"})
        assert wired.demo.active is False
        assert wired.ctx.demo_store.updates == []  # never flipped
        assert "inactive" in p.completion_note.lower()

    def test_overlap_at_completion_blocks_activation(self, wired):
        from admz.demos import activation as act
        wired.monkeypatch.setattr(
            wired.fr, "overlap_conflicts",
            lambda *a, **k: [{"facet": "ntp", "path": "root.NTP.Server",
                              "device_id": "dev", "other_demo": "Other"}])
        p = _plan(PlanStatus.COMPLETED)
        act.on_activation_complete(p, {"demo_id": "d1", "demo_name": "Lobby"})
        assert wired.demo.active is False
        assert "claims the same" in p.completion_note

    def test_unknown_demo_noted(self, wired):
        from admz.demos import activation as act
        p = _plan(PlanStatus.COMPLETED)
        act.on_activation_complete(p, {"demo_id": "ghost"})
        assert wired.demo.active is False and "not found" in p.completion_note


class TestDeactivationHandler:
    def test_flips_inactive_on_completed(self, wired):
        from admz.demos import activation as act
        wired.demo.active = True
        p = _plan(PlanStatus.COMPLETED)
        act.on_deactivation_complete(p, {"demo_id": "d1", "demo_name": "Lobby"})
        assert wired.demo.active is False
        assert wired.ctx.demo_store.updates == [False]

    def test_stays_active_on_failed(self, wired):
        from admz.demos import activation as act
        wired.demo.active = True
        p = _plan(PlanStatus.FAILED)
        act.on_deactivation_complete(p, {"demo_id": "d1", "demo_name": "Lobby"})
        assert wired.demo.active is True
        assert wired.ctx.demo_store.updates == []
        assert "demo_broken" in p.completion_note
