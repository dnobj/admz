"""A declared capability's setting key is written only by `set_enabled` (#164).

`POST /api/capabilities/{cap_id}` enforces four things before flipping a
capability — reveal-group membership, toggleability, a typed confirmation id, a
mandatory reason — and writes an audit row. But `fleet_settings.set()` is
public, and four other routes wrote the **same four keys** directly:
`events.py` (three keys, with no principal resolved at all), `detections.py`
(as a side effect of creating a rule) and `survey.py`. The registry's
guarantees applied to one caller out of five.

`fleet_settings.set()` now refuses a declared capability `setting_key` unless
the write arrived through `capabilities.set_enabled`.

**Scope is the point.** The guard's vocabulary is exactly the four declared
`setting_key`s from the ADR-0052 registry — not "settings". There are ~41
`fleet_settings.set()` call sites in the tree and ~35 of them write unrelated
keys; `TestTheUntouchedWritersStillWork` pins that they are unaffected, because
"capability writes are guarded" is trivially green for a `set()` that refuses
everything. Both directions or neither.

**What this does NOT add.** The three converted routes gain *registry
integrity* — attributed, reasoned, audited, toggleability enforced. They do
**not** gain the four-part reveal ceremony. Whether they should is an open
product decision (#164): a typed capability id to toggle live event ingest from
the events page is heavy, and heavy enough friction pushes operators to the API,
which is worse. Do not read "capability writes go through the gate" as meaning
all four parts.
"""

from __future__ import annotations

import inspect

import pytest

from admz import capabilities
from admz.capabilities import CapabilityWriteBypass
from admz.fleet_settings import fleet_settings

#: The four declared capability keys and the capability that owns each.
CAP_KEYS = {
    "event_ingest_enabled": "events.device_ingest",
    "acs_event_ingest_enabled": "events.acs_poll",
    "acs_firebird_enabled": "acs.firebird_read",
    "survey_mode_enabled": "survey.contributor",
}


# ── the anti-vacuity guard: what must STILL be writable ──────────────────────
class TestTheUntouchedWritersStillWork:
    """FIRST. A guard that refused every key would satisfy every refusal test
    below while breaking ~35 unrelated writers — the chatbot's API key, the
    confirm password hash, the ignore rules, the GitHub App config. "Capability
    writes are guarded" must not be able to pass by locking the store."""

    @pytest.mark.parametrize("key,value", [
        ("gemini_api_key", "sk-test"),
        ("confirm_password_hash", "pbkdf2$x"),
        ("health_monitor_enabled", "true"),
        ("default_username", "admin"),
        ("chat_daily_token_budget", "1000"),
        ("some_key_invented_tomorrow", "x"),
    ])
    def test_a_non_capability_key_is_written_normally(self, key, value):
        fleet_settings.set(key, value)
        assert fleet_settings.get(key) is not None

    def test_the_guard_vocabulary_is_exactly_the_declared_registry(self):
        """Not a hand-maintained list. If a capability is added tomorrow with a
        `setting_key`, it is protected without anyone remembering — and if the
        registry loses one, the guard narrows with it rather than lying."""
        assert capabilities.capability_setting_keys() == frozenset(CAP_KEYS)
        declared = {c.setting_key for c in capabilities.all_capabilities()
                    if c.setting_key}
        assert capabilities.capability_setting_keys() == declared

    def test_the_guard_is_not_a_lock_on_settings(self):
        """Stated as a count so a future widening is visible: four protected
        keys, not the whole store."""
        assert len(capabilities.capability_setting_keys()) == 4


# ── the defect ───────────────────────────────────────────────────────────────
class TestADirectWriteIsRefused:
    @pytest.mark.parametrize("key", sorted(CAP_KEYS))
    def test_every_declared_capability_key_refuses_a_direct_write(self, key):
        """THE defect, one case per key — all four had a bypassing writer."""
        with pytest.raises(CapabilityWriteBypass) as exc:
            fleet_settings.set(key, "true")
        assert key in str(exc.value)
        assert "set_enabled" in str(exc.value), (
            "the error must name the sanctioned path, or the next author "
            "widens the guard instead of using it")

    def test_the_refusal_happens_before_the_store_is_touched(self):
        """Fail closed *and* early: the value must not land and then be
        complained about."""
        before = fleet_settings.get("acs_firebird_enabled")
        with pytest.raises(CapabilityWriteBypass):
            fleet_settings.set("acs_firebird_enabled", "true")
        assert fleet_settings.get("acs_firebird_enabled") == before

    def test_the_flag_does_not_leak_after_a_sanctioned_write(self):
        """The `try/finally` is load-bearing — a leaked flag would silently
        disable the guard for everything later on this thread."""
        capabilities.set_enabled("events.device_ingest", True, None,
                                 reason="test")
        assert capabilities.is_sanctioned_capability_write() is False
        with pytest.raises(CapabilityWriteBypass):
            fleet_settings.set("event_ingest_enabled", "false")

    def test_the_flag_does_not_leak_when_the_write_raises(self, monkeypatch):
        """Same, on the exception path."""
        def _boom(self, key, value):
            raise RuntimeError("disk full")
        monkeypatch.setattr(type(fleet_settings), "_raw_set", _boom)
        with pytest.raises(RuntimeError):
            capabilities.set_enabled("events.device_ingest", True, None,
                                     reason="test")
        assert capabilities.is_sanctioned_capability_write() is False


# ── the sanctioned path still works ──────────────────────────────────────────
class TestSetEnabledIsUnobstructed:
    @pytest.mark.parametrize("key,cap_id", sorted(CAP_KEYS.items()))
    def test_each_capability_can_still_be_toggled(self, key, cap_id):
        capabilities.set_enabled(cap_id, True, None, reason="test")
        assert fleet_settings.get(key) == "true"
        capabilities.set_enabled(cap_id, False, None, reason="test")
        assert fleet_settings.get(key) == "false"

    def test_it_still_writes_an_audit_row(self, monkeypatch):
        seen: list = []
        import admz.audit as A
        monkeypatch.setattr(A, "record_event", lambda *a, **k: seen.append((a, k)))
        capabilities.set_enabled("acs.firebird_read", True, None,
                                 reason="because the operator said so")
        assert seen, "the sanctioned write stopped auditing"
        assert seen[0][0][1] == "capability.enable"
        assert seen[0][1]["details"]["reason"] == "because the operator said so"


# ── no writer bypasses it any more ───────────────────────────────────────────
class TestNoRouteWritesACapabilityKeyDirectly:
    def test_a_static_sweep_finds_no_direct_writer(self):
        """The check that would have caught this at review. Walks every
        `fleet_settings.set(<literal>)` in `admz/` and fails on a declared
        capability key — so a *new* route reintroducing the bypass is caught
        without anyone remembering this issue existed.

        Literal-only on purpose: it cannot see a computed key, which is why the
        runtime guard above is the real defence and this is the early warning.
        """
        import ast
        import pathlib

        keys = capabilities.capability_setting_keys()
        offenders = []
        for path in sorted(pathlib.Path("admz").rglob("*.py")):
            if path.name in ("capabilities.py", "fleet_settings.py"):
                continue     # the sanctioned writer, and the store's own internals
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                # `_raw_set` too: it is the private door the *tests* use to
                # arrange legacy on-disk spellings that `set_enabled` cannot
                # produce. Legitimate there, a bypass here — so production is
                # swept for both.
                if getattr(node.func, "attr", None) not in ("set", "_raw_set")                         or not node.args:
                    continue
                a0 = node.args[0]
                if isinstance(a0, ast.Constant) and a0.value in keys:
                    offenders.append(f"{path}:{node.lineno} -> set({a0.value!r})")
        assert not offenders, (
            "these write a declared capability setting key directly instead of "
            "calling capabilities.set_enabled (#164):\n  " + "\n  ".join(offenders))

    @pytest.mark.parametrize("module,fn", [
        ("admz.api.routes.events", "events_control"),
        ("admz.api.routes.detections", "_ensure_ingest"),
    ])
    def test_the_converted_routes_call_set_enabled(self, module, fn):
        import importlib
        src = inspect.getsource(getattr(importlib.import_module(module), fn))
        assert "set_enabled" in src

    def test_the_events_route_now_resolves_a_principal(self):
        """It resolved none at all — so nothing could be attributed even if it
        had audited."""
        from admz.api.routes.events import events_control
        src = inspect.getsource(events_control)
        assert "get_current_principal" in src
        assert "require_authenticated_principal" in src

    def test_the_approval_executor_uses_the_sanctioned_writer(self):
        """`_action_set_event_ingest` runs AFTER an operator approved. It needs
        no bypass token, because `set_enabled` sits below the approval boundary
        — the ADR-0059 contrast."""
        from admz.operations import _action_set_event_ingest
        src = inspect.getsource(_action_set_event_ingest)
        assert "capabilities.set_enabled" in src
        assert "fleet_settings.set(" not in src


def test_the_reveal_ceremony_is_deliberately_not_added():
    """Pins the scope decision so nobody later reads the issue title as meaning
    all four parts shipped. `_apply_toggle` keeps the reveal-group check and the
    typed confirmation id; the three converted routes deliberately do not."""
    from admz.api.routes.capabilities import _apply_toggle
    src = inspect.getsource(_apply_toggle)
    assert "_reveal_decision" in src, "the /settings/advanced ceremony vanished"

    from admz.api.routes.events import events_control
    assert "_reveal_decision" not in inspect.getsource(events_control), (
        "the reveal gate was added to the events route — that is an open "
        "operator decision (#164), not this change's to take")
