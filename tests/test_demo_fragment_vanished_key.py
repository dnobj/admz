"""ADR-0047 Guard 3's second half: a key deleted from the device is not
capturable (#208).

Guard 3's rationale is a capability claim about `param.cgi` — it "cannot create
**or delete** keys, so a fragment overrides, never invents". Both endpoints of
the diff must therefore be values the device actually had. Only the create half
was implemented: `expected == "<missing>"` was refused, `actual == "<missing>"`
was not.

The consequence is not a bad write — no device is ever sent the literal
sentinel, `restore.py:195` blocks that. It is drift blindness. Capturing a
vanished key stores `set: {key: "<missing>"}`; once the demo is adopted,
`attribution_maps` registers `want="<missing>"` and `drift.py`'s `actual ==
want` is then satisfied *precisely while the key stays deleted*, bucketing it
`demo_set` — "Deliberate: the active demo set this. NOT counted as drift."

**Vacuity note.** "capture refuses X" is trivially green against a validator
that refuses everything, so `TestThePermittedDirectionStillWorks` runs first and
pins what must still be accepted — an ordinary override, and `require` mode,
which Guard 3 deliberately does not constrain. In the drift half,
`test_the_same_deletion_is_reported_when_no_demo_claims_it` is the control: the
same vanished key on the same device with no fragment must still read as drift,
or the suppression assertion would be measuring nothing.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

sys.path.insert(0, __import__("os").path.dirname(__file__))

from admz.demos import fragments as fr  # noqa: E402
from admz.demos.store import Demo  # noqa: E402
from admz.snapshot.drift import DriftDetector  # noqa: E402
from admz.snapshot.git_repo import GitRepo  # noqa: E402
from test_demo_fragments import (  # noqa: E402
    _DEV, BASE, _FakeDemoStore, _FakeParamFacet, _FakeRegistry, _ReadOnlyFacet,
    _engine, _field,
)

LIVE_KEY = "root.Image.I0.Resolution"


@pytest.fixture
def repo(tmp_path):
    path = str(tmp_path / "config-repo")
    r = GitRepo(path)
    for key, val in [("user.email", "t@t"), ("user.name", "T"),
                     ("commit.gpgsign", "false")]:
        subprocess.run(["git", "config", key, val], cwd=path, check=True)
    return r


# ── what must STILL be accepted ──────────────────────────────────────────────
class TestThePermittedDirectionStillWorks:
    def test_an_ordinary_override_is_still_capturable(self):
        """FIRST. Every refusal below is worthless if `set` now refuses
        everything — this is the case Guard 3 exists to permit."""
        ok, reason, warns = fr.validate_assignment(
            _field(expected="1920x1080", actual="3840x2160"),
            _FakeParamFacet(), "set", _DEV)
        assert ok, f"the permitted direction broke: {reason}"
        assert not warns

    def test_a_falsy_live_value_is_not_mistaken_for_absence(self):
        """`""` and `"0"` are real values a device can hold. The guard keys on
        equality with the sentinel, never on truthiness — the #285 lesson."""
        for value in ("", "0", "no", "false"):
            ok, reason, _ = fr.validate_assignment(
                _field(expected="yes", actual=value),
                _FakeParamFacet(), "set", _DEV)
            assert ok, f"live value {value!r} was refused as {reason!r}"

    def test_require_mode_is_deliberately_unconstrained(self):
        """Guard 3 is scoped to `set` in the ADR — `require` is never pushed and
        never enters `owned` (`_set_map_for` reads MODE_SET only), so it cannot
        suppress drift. Widening the guard to `require` would be a scope change,
        not a fix."""
        ok, reason, _ = fr.validate_assignment(
            _field(actual=fr.MISSING), _ReadOnlyFacet(), "require", _DEV)
        assert ok, f"require was refused: {reason!r}"


# ── the missing half ─────────────────────────────────────────────────────────
class TestAVanishedKeyIsNotCapturable:
    def test_actual_missing_is_refused(self):
        """THE defect. Baseline has the key, the device no longer does."""
        ok, reason, _ = fr.validate_assignment(
            _field(expected="1920x1080", actual=fr.MISSING),
            _FakeParamFacet(), "set", _DEV)
        assert not ok, "a key deleted from the device was captured as config"
        assert reason == "vanished-from-device"

    def test_the_reason_is_distinct_from_the_create_half(self):
        """The two halves fail for opposite reasons and the operator's remedy
        differs — revert it, versus it was never yours to set. One shared code
        would hide that."""
        _, create_half, _ = fr.validate_assignment(
            _field(expected=fr.MISSING), _FakeParamFacet(), "set", _DEV)
        _, delete_half, _ = fr.validate_assignment(
            _field(actual=fr.MISSING), _FakeParamFacet(), "set", _DEV)
        assert create_half == "not-in-baseline"
        assert delete_half == "vanished-from-device"
        assert create_half != delete_half

    def test_both_missing_is_still_refused(self):
        """Belt and braces: an ignore rule or a facet quirk can strip both
        sides. Either half alone is enough to refuse."""
        ok, reason, _ = fr.validate_assignment(
            _field(expected=fr.MISSING, actual=fr.MISSING),
            _FakeParamFacet(), "set", _DEV)
        assert not ok and reason in ("not-in-baseline", "vanished-from-device")

    def test_the_read_only_gate_cannot_substitute_for_this_check(self):
        """Why a dedicated check is needed rather than leaning on the existing
        one. `is_restorable` screens only MASKED_SECRET, Volatile* and per-facet
        excludes, so for an ordinary writable key `revert_param(path,
        "<missing>")` returns a perfectly normal write tuple and the sentinel
        sails through. Both halves executed, not assumed."""
        from admz.snapshot.facets.base import is_restorable
        assert is_restorable("Motion.M0.Enabled", fr.MISSING) is True
        assert _FakeParamFacet().revert_param(
            "Motion.M0.Enabled", fr.MISSING) is not None

    def test_read_only_wins_over_vanished_when_a_key_is_both(self):
        """Pins the check ORDER, which is a real decision and was arbitrary
        until measured: a key that is both unwritable and deleted is refused on
        the more fundamental ground. "vanished-from-device" reads as "revert
        it", and a Volatile*/excluded key cannot receive a revert either — so
        that reason would be actively misleading here."""
        ok, reason, _ = fr.validate_assignment(
            _field(expected="1920x1080", actual=fr.MISSING),
            _ReadOnlyFacet(), "set", _DEV)
        assert not ok
        assert reason == "read-only", (
            "a key that was never writable is being reported as vanished, "
            "advising a revert that cannot work")


# ── the harm it prevents, through the real detector ──────────────────────────
def _detector(repo, demos, live):
    reg = _FakeRegistry({"cam-01": {"host": "192.0.2.9", "api_family": "vapix",
                                    "baseline_sha": "HEAD"}})
    return DriftDetector(_engine(reg, live), repo,
                         demo_store=_FakeDemoStore(demos))


def _baseline(repo):
    repo.write_facet("cam-01", "image", dict(BASE))
    repo.commit_snapshot("cam-01")


#: The device no longer reports I0.Resolution at all — the key was deleted.
LIVE_WITHOUT_THE_KEY = {"root.Image.I0.Compression": "30"}


class TestWhatThePoisonedFragmentWouldHaveDone:
    """Executed against a fragment written directly into the repo, bypassing
    capture. This is the state the guard now makes unreachable through the
    product — recorded so the cost of regressing the guard is explicit, and so
    an operator who already has such a fragment can be recognised."""

    @pytest.mark.asyncio
    async def test_a_missing_valued_fragment_suppresses_the_deletion(self, repo):
        _baseline(repo)
        demo = Demo(id="dpoison", name="Loitering", device_ids=["cam-01"],
                    active=True)
        fr.add_entries(repo, demo, "default",
                       [{"facet": "image", "path": "I0.Resolution",
                         "value": fr.MISSING}])
        report = await _detector(repo, [demo], LIVE_WITHOUT_THE_KEY).check_drift(
            "cam-01")
        buckets = {f.path: f.bucket for f in report.fields}
        assert buckets["I0.Resolution"] == "demo_set"
        assert report.real_fields == []
        assert report.has_drift is False

    @pytest.mark.asyncio
    async def test_the_same_deletion_is_reported_when_no_demo_claims_it(
            self, repo):
        """THE control. Without it the assertion above proves nothing — the key
        might simply never have been drift. It is: same device, same deletion,
        no fragment, and it reads as real unclaimed drift."""
        _baseline(repo)
        report = await _detector(repo, [], LIVE_WITHOUT_THE_KEY).check_drift(
            "cam-01")
        assert [(f.path, f.bucket) for f in report.real_fields] == [
            ("I0.Resolution", "unclaimed")]
        assert report.has_drift is True


# ── end to end: the capture path refuses, and refuses legibly ────────────────
class TestThroughAssignFragmentCore:
    @pytest.mark.asyncio
    async def test_the_operator_is_told_the_key_vanished(self, repo, tmp_path):
        """`assign_fragment_core` turns a refusal into a `skipped` entry, so the
        reason code is what the console and the chat both surface. Nothing is
        committed."""
        from types import SimpleNamespace as NS

        from admz.demos.actions import assign_fragment_core

        _baseline(repo)
        demo = Demo(id="dlive", name="Loitering", device_ids=["cam-01"],
                    active=False)
        detector = _detector(repo, [], LIVE_WITHOUT_THE_KEY)
        ctx = NS(registry=_FakeRegistry(
            {"cam-01": {"host": "192.0.2.9", "api_family": "vapix",
                        "baseline_sha": "HEAD", "device_id": "cam-01"}}),
            drift_detector=detector, git_repo=repo,
            demo_store=NS(update=lambda d: None))

        out = await assign_fragment_core(
            ctx, demo,
            [{"device_id": "cam-01", "facet": "image", "path": "I0.Resolution"}],
            None, "set", "alice")

        assert out["added"] == [], "the sentinel was captured into a fragment"
        assert [s["reason"] for s in out["skipped"]] == ["vanished-from-device"]
        # And nothing reached the repo.
        assert fr.load_fragment(repo, demo.id, "default") in (None, {}, {"image": {}})
