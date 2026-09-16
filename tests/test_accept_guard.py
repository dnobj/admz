"""ADR-0070 §4 — the ADR-0047 accept guard runs on every path.

Before this, only the two REST accept routes ran it: an accept driven from the
chat (the MCP handler, then the approved-action executor) could bake an active
demo's config into the baseline. The REST behaviour is pinned, unchanged, in
tests/test_demos_routes.py and is the control for the chat cases here.
"""

from __future__ import annotations

import sqlite3
import subprocess
from types import SimpleNamespace

import pytest

import admz.demos.fragments as fragments_mod
from admz.snapshot.accept_guard import (
    ACTIVE_DEMO,
    GUARD_UNAVAILABLE,
    AcceptRefused,
    check_accept_allowed,
)
from tests import mcp_harness

DEVICE = "cam-guard"


class _DemoStore:
    def __init__(self, demos=()):
        self.demos = list(demos)

    def list(self):
        return list(self.demos)


def _owned_by(monkeypatch, *owners):
    """An active demo owning keys on the device, as ``owning_demos`` reports."""
    monkeypatch.setattr(
        fragments_mod, "owning_demos",
        lambda git, demos, device_id, device_info: [
            (SimpleNamespace(name=name), n) for name, n in owners],
    )


def _locked(monkeypatch):
    def boom(*a, **kw):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(fragments_mod, "owning_demos", boom)


# --------------------------------------------------------------------------- #
# The guard
# --------------------------------------------------------------------------- #
class TestCheckAcceptAllowed:
    def _check(self):
        check_accept_allowed(git_repo=None, demo_store=_DemoStore(),
                             device_id=DEVICE, device_info={})

    def test_no_demo_no_refusal(self):
        self._check()

    def test_an_active_demo_is_a_409_naming_it(self, monkeypatch):
        _owned_by(monkeypatch, ("Lobby promo", 3), ("Night", 1))
        with pytest.raises(AcceptRefused) as caught:
            self._check()
        assert caught.value.status == ACTIVE_DEMO
        assert caught.value.reason == "active_demo"
        assert "'Lobby promo' (3 keys)" in caught.value.detail
        assert "'Night' (1 key)" in caught.value.detail

    @pytest.mark.parametrize("exc", [
        sqlite3.OperationalError("database is locked"),
        subprocess.TimeoutExpired(cmd=["git", "show"], timeout=30),
        OSError("git not found"),
    ])
    def test_an_unevaluable_guard_is_a_503(self, monkeypatch, exc):
        def boom(*a, **kw):
            raise exc
        monkeypatch.setattr(fragments_mod, "owning_demos", boom)
        with pytest.raises(AcceptRefused) as caught:
            self._check()
        assert caught.value.status == GUARD_UNAVAILABLE
        assert caught.value.reason == "guard_unavailable"
        assert "retry" in caught.value.detail.lower()
        assert caught.value.__cause__ is exc

    def test_a_bug_is_not_dressed_as_unavailable(self, monkeypatch):
        def bug(*a, **kw):
            raise KeyError("a genuine bug")
        monkeypatch.setattr(fragments_mod, "owning_demos", bug)
        with pytest.raises(KeyError):
            self._check()


# --------------------------------------------------------------------------- #
# The two chat paths
# --------------------------------------------------------------------------- #
@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "HOMELAB\\alice")
    monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "windows-local")
    import admz.api.confirm_store as cs_module
    monkeypatch.setattr(cs_module, "confirm_store",
                        cs_module.ConfirmStore(db_path=str(tmp_path / "admz.db")))
    from admz.mcp.server import ADMZMCPServer
    srv = ADMZMCPServer()
    repo = str(tmp_path / "config-repo")
    for k, v in [("user.email", "t@t.com"), ("user.name", "T"),
                 ("commit.gpgsign", "false")]:
        subprocess.run(["git", "config", k, v], cwd=repo, check=True)
    srv.registry.add_device(DEVICE, {"host": "192.0.2.20"})
    srv.git_repo.write_facet(DEVICE, "image", {"I0.Resolution": "1920x1080"})
    sha = srv.git_repo.commit_snapshot(DEVICE, message="Audit", auto_push=False)
    srv.registry.set_config_pointers(DEVICE, latest_observed_sha=sha)
    srv.observed_sha = sha
    srv.db_path = tmp_path / "admz.db"
    return srv


def _sessions(server):
    import contextlib

    import admz.api.confirm_store as cs_module
    cs_module.confirm_store.get_session("schema-ensure")
    with contextlib.closing(sqlite3.connect(str(server.db_path))) as conn:
        return conn.execute("SELECT COUNT(*) FROM confirm_sessions").fetchone()[0]


async def _accept(server, **args):
    return await mcp_harness.call_tool(
        server, "accept_baseline", {"device_id": DEVICE, **args})


async def _approve(server, token):
    from admz import operations
    import admz.api.confirm_store as cs_module
    store = cs_module.confirm_store
    session = store.get_session(token)
    store.complete_session(token, confirmed_by="test-approver")
    return await operations.execute_approved_session(
        session, catalog=None, registry=server.registry, executors={},
        git_repo=server.git_repo,
    )


class TestTheHandlerRefusesBeforeMinting:
    @pytest.mark.asyncio
    async def test_an_active_demo_means_no_card(self, server, monkeypatch):
        _owned_by(monkeypatch, ("Lobby promo", 2))
        before = _sessions(server)
        result = await _accept(server, note="keep it")
        assert result["success"] is False
        assert result.get("blocked") is not True
        assert result["refused"] == "active_demo"
        assert "Lobby promo" in result["error"]
        assert _sessions(server) == before

    @pytest.mark.asyncio
    async def test_an_unavailable_guard_means_no_card(self, server, monkeypatch):
        _locked(monkeypatch)
        before = _sessions(server)
        result = await _accept(server)
        assert result["refused"] == "guard_unavailable"
        assert result.get("blocked") is not True
        assert _sessions(server) == before


class TestTheExecutorRefusesAtExecution:
    @pytest.mark.asyncio
    async def test_a_demo_activated_after_minting_is_not_baked_in(
            self, server, monkeypatch):
        minted = await _accept(server)
        assert minted["blocked"] is True
        # The operator activates a demo, then approves the old card.
        _owned_by(monkeypatch, ("Lobby promo", 2))
        outcome = await _approve(server, minted["confirm_token"])
        assert outcome["success"] is False
        assert outcome["refused"] == "active_demo"
        assert server.registry.get_device_info(DEVICE).get("baseline_sha") is None

    @pytest.mark.asyncio
    async def test_an_unavailable_guard_at_execution_moves_nothing(
            self, server, monkeypatch):
        minted = await _accept(server, ignore_keys=["root.Noise.*"])
        _locked(monkeypatch)
        outcome = await _approve(server, minted["confirm_token"])
        assert outcome["success"] is False
        assert outcome["refused"] == "guard_unavailable"
        assert server.registry.get_device_info(DEVICE).get("baseline_sha") is None
        # Nothing on the card happened — the exclusion is not written either.
        from admz.snapshot import ignore
        assert not ignore.is_ignored("root.Noise.X", DEVICE, [])

    @pytest.mark.asyncio
    async def test_with_no_demo_the_approval_goes_through(self, server):
        minted = await _accept(server)
        outcome = await _approve(server, minted["confirm_token"])
        assert outcome["success"] is True
        assert server.registry.get_device_info(DEVICE)["baseline_sha"] == (
            server.observed_sha)
