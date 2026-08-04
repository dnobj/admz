"""`record_event` refuses to misattribute silently (#285).

It reads `.name`/`.source` with `getattr` defaults, so before this a wrong
argument wrote a **plausible** row — `requester="unknown"`, indistinguishable
from a legitimately unattended event — instead of failing. That is how a
`Request` survived at a call site (#205/#283), and why finding it needed an AST
walk over 164 call sites rather than a review.

Vacuity note: "the guard exists" is worth nothing. The load-bearing test here is
`TestLegitimateCallersAreUntouched` — the FALSE-POSITIVE case. A guard that
warns on correct code gets disabled within a week, so `None` producing
`unknown`/`none` **silently** matters more than the wrong object warning.
"""

from __future__ import annotations

import ast
import logging
import pathlib
from types import SimpleNamespace as NS

import pytest

AUDIT_LOGGER = "admz.audit"


@pytest.fixture(autouse=True)
def _reset_guard_latch():
    """The warn-once latch is module state; keep tests order-independent.

    Tolerant of the attribute being absent on purpose. If this fixture required
    the new symbol, reverting the change would make EVERY test in this file
    error inside the fixture — masking the one assertion that can fail
    behaviourally behind twelve structural ones.
    """
    from admz import audit
    latch = getattr(audit, "_GUARD_WARNED", None)
    if latch is not None:
        latch.clear()
    yield
    if latch is not None:
        latch.clear()


def _fields(principal, action="some.action"):
    from admz.audit import _principal_fields
    return _principal_fields(principal, action)


# ── the false-positive case: what keeps the guard alive ──────────────────────
class TestLegitimateCallersAreUntouched:
    def test_a_real_principal_is_unaffected_and_silent(self, caplog):
        from admz.auth import Principal
        p = Principal(name="AXIS\\dnich", display_name="dnich", source="windows-local")
        with caplog.at_level(logging.WARNING, logger=AUDIT_LOGGER):
            assert _fields(p) == ("AXIS\\dnich", "windows-local")
        assert caplog.records == []

    def test_none_still_yields_unknown_none_WITHOUT_warning(self, caplog):
        """THE assertion that matters. `principal=None` is deliberate for
        unattended and system events; a truthiness-keyed guard would warn on
        every one of them and be switched off."""
        with caplog.at_level(logging.WARNING, logger=AUDIT_LOGGER):
            assert _fields(None) == ("unknown", "none")
        assert caplog.records == [], "the guard fired on a legitimate None"

    @pytest.mark.parametrize("synthetic", [
        NS(name="demo:Speaker", source="rule-attach"),
        NS(name="demo:Speaker", source="rule-detach"),
        NS(name="demo:Speaker", source="plan-complete"),
        NS(name="acs-webhook", source="acs-webhook"),
    ])
    def test_the_four_synthetic_principals_are_accepted(self, synthetic, caplog):
        """The shapes at demos/actions.py:342,:373, demos/activation.py:251 and
        modules/acs_pro/routes.py:297 — events with no human actor. They carry
        exactly the two attributes read, and must not trip the guard."""
        with caplog.at_level(logging.WARNING, logger=AUDIT_LOGGER):
            assert _fields(synthetic) == (synthetic.name, synthetic.source)
        assert caplog.records == []

    def test_an_empty_name_is_not_treated_as_a_wrong_object(self, caplog):
        """Present-but-empty is a value problem, not a type problem; `record`
        already normalises it. The guard must not conflate the two."""
        with caplog.at_level(logging.WARNING, logger=AUDIT_LOGGER):
            assert _fields(NS(name="", source="")) == ("", "")
        assert caplog.records == []


# ── the defect case ──────────────────────────────────────────────────────────
class TestAWrongObjectIsLoud:
    def test_a_request_like_object_warns_and_names_the_action(self, caplog):
        """Deliberately through the PUBLIC `record_event`, not the private
        helper: that API exists before this change too, so this is the one
        assertion here that can fail BEHAVIOURALLY against the old code rather
        than merely ImportError-ing on a new symbol.

        The object mirrors #205's defect exactly — a Starlette Request is truthy
        and carries neither attribute, so the old code wrote a plausible row and
        said nothing.
        """
        from admz.audit import AuditLog, record_event
        request_like = NS(url="/api/github/test", method="POST", headers={})
        with caplog.at_level(logging.WARNING, logger=AUDIT_LOGGER):
            record_event(request_like, "github_app.test", log=AuditLog())
        msgs = [r.getMessage() for r in caplog.records
                if r.levelno == logging.WARNING]
        assert len(msgs) == 1, "a non-principal was accepted silently"
        assert "github_app.test" in msgs[0], "the offending call site is not findable"
        assert "not a principal" in msgs[0]

    def test_the_row_is_still_written(self, caplog):
        """Warns, never raises: AuditLog.record already swallows its own DB
        errors under 'an audit-write failure must never break the underlying
        op', and 146 of 165 call sites are bare. A raise would reverse that."""
        from admz.audit import AuditLog, record_event
        log = AuditLog()
        with caplog.at_level(logging.WARNING, logger=AUDIT_LOGGER):
            record_event(NS(url="/x"), "some.action", resource="r", log=log)
        rows = log.list_recent(action="some.action")
        assert rows and rows[0].requester == "unknown"
        assert rows[0].auth_source == "none"

    def test_it_warns_once_per_call_site_not_once_per_call(self, caplog):
        """A guard that floods gets silenced — which is the failure mode this
        change exists to prevent."""
        with caplog.at_level(logging.WARNING, logger=AUDIT_LOGGER):
            for _ in range(25):
                _fields(NS(url="/x"), "hot.path")
        assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1

    def test_a_different_action_warns_separately(self, caplog):
        """Two distinct buggy call sites must both be reported."""
        with caplog.at_level(logging.WARNING, logger=AUDIT_LOGGER):
            _fields(NS(url="/x"), "action.one")
            _fields(NS(url="/x"), "action.two")
        msgs = "\n".join(r.getMessage() for r in caplog.records)
        assert "action.one" in msgs and "action.two" in msgs


# ── the static lint: what catches it BEFORE merge ────────────────────────────
class TestEveryCallSitePassesAPrincipal:
    """The runtime guard is a backstop; this is the check that fails a PR.

    #283 found the one bad call site by walking every `record_event`/`_audit`
    call in `admz/` and enumerating the distinct first-argument expressions —
    159x `principal`, 1x `request`, 4x `SimpleNamespace(name=, source=)`. That
    sweep was manual and therefore one-off. This makes it permanent.

    Deliberately a heuristic SUPERSET: it accepts a small allow-list of shapes
    and flags anything else, so a new shape fails loudly and gets reviewed
    rather than slipping through. It is not a second implementation of the
    runtime predicate — it cannot be, one is static and one is dynamic — so it
    is scoped as a lint over call-site *expressions*, not over principal values.
    """

    ACCEPTED_NAMES = {"principal", "who", "actor"}

    def _first_args(self):
        out = []
        for p in sorted(pathlib.Path("admz").rglob("*.py")):
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:  # pragma: no cover
                continue
            for n in ast.walk(tree):
                if not isinstance(n, ast.Call):
                    continue
                fn = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
                if fn in ("record_event", "_audit") and n.args:
                    out.append((p, n.lineno, n.args[0]))
        return out

    def _is_accepted(self, node):
        if isinstance(node, ast.Name) and node.id in self.ACCEPTED_NAMES:
            return True
        if isinstance(node, ast.Constant) and node.value is None:
            return True                       # explicit "no human actor"
        # SimpleNamespace(name=..., source=...) — the synthetic-principal shape.
        if isinstance(node, ast.Call):
            fname = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if fname in ("SimpleNamespace", "Principal", "system_principal"):
                kw = {k.arg for k in node.keywords}
                return {"name", "source"} <= kw or fname != "SimpleNamespace"
        return False

    def test_the_sweep_finds_the_call_sites_at_all(self):
        """Anti-vacuity: an empty sweep would make the next test pass for free."""
        found = self._first_args()
        assert len(found) > 100, f"expected the full corpus, walked {len(found)}"

    def test_no_call_site_passes_a_non_principal(self):
        bad = [f"{p}:{ln} -> {ast.unparse(node)}"
               for p, ln, node in self._first_args() if not self._is_accepted(node)]
        assert not bad, (
            "record_event/_audit called with something that is not a principal:\n  "
            + "\n  ".join(bad)
            + "\n\nPass the principal, or None for an event with no human actor. "
              "If this is a new legitimate shape, add it to ACCEPTED_NAMES / "
              "_is_accepted deliberately rather than widening it by reflex.")
