"""Shared pytest fixtures / test-isolation guards.

Several suites exercise the *global, in-memory* rate limiter
(`admz.rate_limit.rate_limiter`) and the per-token confirm-password lockout
dict (`admz.api.routes.confirm._PW_ATTEMPTS`). Both are process-wide singletons,
so a test that drains the ``confirm`` token bucket (or leaves a token locked
out) can make a *later* confirm test fail with an unexpected 429 — purely as a
function of test order. This was latent for a long time and surfaced when new
test files shifted the collection order.

The autouse fixture below resets that shared state before every test, making
the confirm/rate-limit tests order-independent. Tests that configure their own
bucket policy still work — they configure after this reset.
"""

import importlib.util
import os
import shutil

import pytest

# Loaded by explicit file path, not `import _admz_isolation`. pytest does not
# put tests/ on sys.path until it imports the first *test module*, which is
# after this conftest — so a plain import raises ModuleNotFoundError here.
# (Test modules can import it normally; by then the path insertion has
# happened.) Loading by path also keeps tests/ off sys.path entirely.
_ISOLATION_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "_admz_isolation.py")
_spec = importlib.util.spec_from_file_location("_admz_isolation", _ISOLATION_PY)
_admz_isolation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_admz_isolation)

assert_isolated = _admz_isolation.assert_isolated
redirect_to_throwaway = _admz_isolation.redirect_to_throwaway

# ---------------------------------------------------------------------------
# ADMZ_HOME isolation (#257) — MUST be the first thing this module does.
#
# This is module-level rather than a fixture on purpose, and the reason is not
# style. Several ADMZ stores build a module-level singleton at *import* and
# bind their DB path in ``__init__`` (#254). Any fixture — even session-scoped
# autouse — runs after test modules are imported, by which point those
# singletons already exist and are already pointed wherever ``ADMZ_HOME`` said.
# There is nothing later that can undo that, so the redirect has to happen
# here, before pytest collects anything.
#
# On the reference box ``ADMZ_HOME`` is a *Machine*-scoped variable set to
# ``C:\ProgramData\admz`` — the live production data directory — so every
# pytest process inherited it. See tests/_admz_isolation.py for the full
# reasoning, including why HOME/USERPROFILE are deliberately left alone.
# ---------------------------------------------------------------------------
TEST_ADMZ_HOME, _PREVIOUS_ADMZ_HOME, _CLEARED_OVERRIDES = redirect_to_throwaway()

# Fail closed immediately: prove the redirect actually took effect before a
# single admz module is imported. A specific override that survived, or an
# environment we did not anticipate, stops the session here.
assert_isolated(
    TEST_ADMZ_HOME,
    previous=_PREVIOUS_ADMZ_HOME,
    cleared=_CLEARED_OVERRIDES,
)


def pytest_report_header(config):
    """Make the redirect visible in every run's header.

    The next person to add a test file will not read #257, but they will see
    this line, and it is what tells them the suite is not using their real
    ADMZ_HOME.
    """
    lines = [f"admz: ADMZ_HOME redirected to {TEST_ADMZ_HOME}"]
    if _PREVIOUS_ADMZ_HOME:
        lines.append(f"admz: inherited ADMZ_HOME was {_PREVIOUS_ADMZ_HOME} (not used)")
    for name, value in sorted(_CLEARED_OVERRIDES.items()):
        lines.append(f"admz: cleared {name}={value} (not used)")
    return lines


def pytest_configure(config):
    """Re-check after every conftest/plugin has loaded, before collection.

    The module-level check above proves the redirect worked. This one catches
    anything that re-pointed ADMZ_HOME between then and collection.
    """
    try:
        assert_isolated(
            TEST_ADMZ_HOME,
            previous=_PREVIOUS_ADMZ_HOME,
            cleared=_CLEARED_OVERRIDES,
        )
    except RuntimeError as exc:
        raise pytest.UsageError(str(exc)) from exc


def pytest_sessionfinish(session, exitstatus):
    """Remove the throwaway directory. Best-effort: on Windows a still-open
    SQLite handle can hold a file, and failing to tidy a temp dir must never
    fail a run."""
    shutil.rmtree(TEST_ADMZ_HOME, ignore_errors=True)


# Credential onboarding runs network probes after a device add (TCP
# preflight + systemready + basicdeviceinfo). Unit tests register devices
# with fabricated LAN addresses — without this guard every create would
# probe whatever network the test box sits on. test_onboarding.py deletes
# the var and mocks the probes to exercise the flow itself.
os.environ.setdefault("ADMZ_DISABLE_ONBOARDING_PROBES", "1")

# Same class of leak on the push path: the GitHub App connection lives in the
# machine's secret store (ADR-0045), so on a developer's *connected* box the
# git-push tests would mint a real installation token over the network and push
# with auth args a clean box never sees. Pin them to the unauthenticated path.
# tests/test_github_app*.py exercise the token machinery directly instead.
os.environ.setdefault("ADMZ_DISABLE_GITHUB_APP_PUSH", "1")


#: Modules that bind the fleet-settings singleton with
#: ``from admz.fleet_settings import fleet_settings`` — that is, at IMPORT. A
#: test that repoints the module attribute and *then* imports the app for the
#: first time leaves every one of these holding ITS temporary store, for the
#: rest of the session. Modules that import it inside a function rebind on every
#: call and cannot leak, so they are deliberately not listed.
_FLEET_SETTINGS_HOLDERS = (
    "admz.api.routes.capture",
    "admz.api.routes.confirm",
    "admz.api.routes.devices",
    "admz.api.routes.survey",
    "admz.api.routes.web",
    "admz.entry_credentials",
    "admz.github_app.secrets",
    "admz.mcp.server",
    "admz.onboarding",
    "admz.provisioning",
    "admz.survey.secrets",
)


@pytest.fixture
def repoint_fleet_settings(monkeypatch):
    """Point every module-level fleet-settings reference at one store.

    Returns a callable so a fixture can write
    ``fresh = repoint_fleet_settings(FleetSettings(path))``.

    It **imports the holders first**, which is the whole point: a module
    imported for the first time *under* the patch binds the temporary store
    permanently, and monkeypatch cannot undo that — it only restores attributes
    it set. `admz.provisioning` is imported lazily while `/settings` renders,
    which is exactly how the leak reappeared after the obvious one was fixed.
    """
    import importlib

    def _repoint(store):
        import admz.fleet_settings as fs_module

        for name in _FLEET_SETTINGS_HOLDERS:
            monkeypatch.setattr(
                importlib.import_module(name), "fleet_settings", store)
        monkeypatch.setattr(fs_module, "fleet_settings", store)
        return store

    return _repoint


@pytest.fixture(autouse=True)
def _fleet_settings_references_restored():
    """Fail the test that leaves a fleet-settings reference repointed.

    Without this the *innocent* test fails instead, one file later and with
    nothing to point at: a suite that patched the store and then imported the
    app first left ``api/routes/devices.py`` reading a deleted temp database, so
    ``tests/test_api_routes.py::TestFleetSettingsMasking`` got a 404 for a key it
    had just written — but only when the two files shared a session, which is
    why it never failed alone or in CI's full-suite order.

    Repoint every module-level reference together and restore them all; the
    ``client`` fixture in tests/test_settings_write_authz.py is the pattern.
    """
    yield
    import sys

    import admz.fleet_settings as fs_module

    current = fs_module.fleet_settings
    leaked = [
        name for name in _FLEET_SETTINGS_HOLDERS
        if (module := sys.modules.get(name)) is not None
        and getattr(module, "fleet_settings", current) is not current
    ]
    assert not leaked, (
        "these modules still point at a different fleet-settings store than "
        f"admz.fleet_settings.fleet_settings: {leaked}. Repoint every "
        "module-level reference together and restore them all in the fixture's "
        "teardown, or a later test reads a store this one never wrote to."
    )


@pytest.fixture(autouse=True)
def _reset_shared_inmemory_state():
    """Reset process-wide rate-limit + lockout state before each test."""
    try:
        from admz.rate_limit import rate_limiter
        rate_limiter.reset()  # clears token buckets; keeps configured policy
    except Exception:
        pass
    try:
        from admz.api.routes.confirm import _PW_ATTEMPTS, _PW_ATTEMPTS_LOCK
        with _PW_ATTEMPTS_LOCK:
            _PW_ATTEMPTS.clear()
    except Exception:
        pass
    yield
