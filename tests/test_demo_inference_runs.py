"""The ``demo_inference_runs`` store and its REST/MCP surface (#124, slice 2).

Store tests take an explicit ``db_path`` (singletons bind their path at import,
so a test relying on the default would pollute the real DB). Route tests use the
real app on an isolated ``ADMZ_HOME``, the same harness as
``tests/test_demos_routes.py``.

Nothing here starts a real deep survey: the one test that exercises the
background-job path replaces ``collect.run_survey`` with a stub, because the
real one discovers on whatever network the test box sits on.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from admz.demos.inference.runs import (MODE_FAST, MODE_SURVEY, STATUS_COMPLETE,
                                       STATUS_FAILED, STATUS_RUNNING,
                                       InferenceRunStore)


# ═══════════════════════════════════════════════════════════════════════════
# Store
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def store(tmp_path):
    return InferenceRunStore(db_path=str(tmp_path / "admz.db"))


def _graph(devices=2, rules=3, edges=1, acs_available=True, reason="ok"):
    return {
        "acs": {"available": acs_available, "reason": reason},
        "params": {"weights": {"E1": 1.0}},
        "nodes": [], "rules": [], "edges": [],
        "summary": {"device_count": devices, "rule_count": rules,
                    "edge_count": edges,
                    "acs": {"available": acs_available, "reason": reason}},
    }


class TestRunStore:
    def test_start_records_a_running_row(self, store):
        run = store.start(mode=MODE_FAST, created_by="alice")
        assert run.status == STATUS_RUNNING and run.mode == MODE_FAST
        assert store.get(run.id).created_by == "alice"
        assert store.running() and store.running()[0].id == run.id

    def test_finish_stores_the_graph_and_its_provenance(self, store):
        run = store.start(mode=MODE_FAST)
        done = store.finish(run.id, _graph(devices=7, rules=12, edges=4),
                            message="7 device(s)")
        assert done.status == STATUS_COMPLETE
        assert (done.device_count, done.rule_count, done.edge_count) == (7, 12, 4)
        assert done.acs_available is True and done.acs_reason == "ok"
        assert done.finished_at > 0 and done.message == "7 device(s)"
        # The graph IS the audit trail — it round-trips intact.
        assert done.graph["summary"]["device_count"] == 7
        assert done.params == {"weights": {"E1": 1.0}}

    def test_degradation_reason_is_persisted(self, store):
        run = store.start(mode=MODE_FAST)
        done = store.finish(run.id, _graph(acs_available=False,
                                           reason="Firebird reader disabled"))
        assert done.acs_available is False
        assert done.acs_reason == "Firebird reader disabled"
        assert done.header()["acs"] == {"available": False,
                                        "reason": "Firebird reader disabled"}

    def test_fail_is_terminal_and_carries_the_error(self, store):
        run = store.start(mode=MODE_SURVEY)
        store.fail(run.id, "discovery exploded")
        got = store.get(run.id)
        assert got.status == STATUS_FAILED and got.error == "discovery exploded"
        assert store.running() == []

    def test_progress_advances_phase_and_counter(self, store):
        run = store.start(mode=MODE_SURVEY)
        store.progress(run.id, phase="snapshot", step=2, total=4,
                       message="Snapshotting…")
        got = store.get(run.id)
        assert (got.phase, got.progress, got.message) == ("snapshot", "2/4",
                                                          "Snapshotting…")
        assert got.status == STATUS_RUNNING

    def test_list_is_newest_first_and_header_omits_the_graph(self, store):
        first = store.start(mode=MODE_FAST)
        store.finish(first.id, _graph())
        second = store.start(mode=MODE_FAST)
        ids = [r.id for r in store.list()]
        assert ids[0] == second.id and first.id in ids
        assert "graph" not in store.get(first.id).header()

    def test_running_filters_by_mode(self, store):
        fast = store.start(mode=MODE_FAST)
        survey = store.start(mode=MODE_SURVEY)
        assert [r.id for r in store.running(mode=MODE_SURVEY)] == [survey.id]
        assert {r.id for r in store.running()} == {fast.id, survey.id}

    def test_running_can_ignore_a_row_abandoned_by_a_dead_process(self, store):
        """A crash mid-survey must not wedge the feature forever."""
        import sqlite3
        import time

        run = store.start(mode=MODE_SURVEY)
        conn = sqlite3.connect(store._db_path)
        conn.execute("UPDATE demo_inference_runs SET started_at = ? WHERE id = ?",
                     (time.time() - 7200, run.id))
        conn.commit()
        conn.close()
        assert store.running(mode=MODE_SURVEY) != []          # still 'running'
        assert store.running(mode=MODE_SURVEY, max_age=3600) == []

    def test_ensure_table_is_idempotent_and_upgrades_the_plan_schema(self, tmp_path):
        """The house try-ALTER pattern: a DB created from the plan's exact
        schema gains the job columns in place, with no backfill."""
        import sqlite3

        db = str(tmp_path / "admz.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE demo_inference_runs (id TEXT PRIMARY KEY, "
            "started_at REAL, finished_at REAL, created_by TEXT, "
            "acs_available INTEGER, acs_reason TEXT, device_count INTEGER, "
            "rule_count INTEGER, graph_json TEXT, params_json TEXT)")
        conn.execute("INSERT INTO demo_inference_runs (id) VALUES ('legacy')")
        conn.commit()
        conn.close()

        s = InferenceRunStore(db_path=db)
        InferenceRunStore(db_path=db)          # second call must be a no-op
        legacy = s.get("legacy")
        assert legacy is not None and legacy.mode == MODE_FAST
        assert s.start(mode=MODE_FAST).id != "legacy"

    def test_corrupt_stored_json_is_surfaced_not_read_as_an_empty_graph(self,
                                                                        store):
        """The graph IS the audit trail. A row whose ``graph_json`` will not
        parse has lost it — reading back a tidy ``complete`` run with no graph
        would hide the damage instead of reporting it."""
        import sqlite3

        run = store.start(mode=MODE_FAST)
        store.finish(run.id, _graph(), message="7 device(s)")
        conn = sqlite3.connect(store._db_path)
        conn.execute("UPDATE demo_inference_runs SET graph_json = ? WHERE id = ?",
                     ('{"summary": {"device_c', run.id))
        conn.commit()
        conn.close()

        got = store.get(run.id)
        assert got.graph == {}
        assert got.status == STATUS_FAILED          # not a successful run
        assert "corrupt" in got.error and "graph" in got.error
        assert "corrupt" in got.header()["error"]

    def test_corrupt_params_are_reported_without_condemning_the_run(self, store):
        import sqlite3

        run = store.start(mode=MODE_FAST)
        store.finish(run.id, _graph())
        conn = sqlite3.connect(store._db_path)
        conn.execute("UPDATE demo_inference_runs SET params_json = ? WHERE id = ?",
                     ("{not json", run.id))
        conn.commit()
        conn.close()

        got = store.get(run.id)
        assert got.status == STATUS_COMPLETE        # the graph survived
        assert "params" in got.error and "corrupt" in got.error

    def test_a_migration_failure_that_is_not_a_duplicate_column_is_raised(
            self, tmp_path, monkeypatch):
        """Suppressing every ``OperationalError`` here would let a locked or
        read-only DB leave the job columns absent — failing much later, and
        somewhere that gives no hint why. Only "already there" is expected.

        (The duplicate-column half stays covered by
        ``test_ensure_table_is_idempotent_and_upgrades_the_plan_schema``.)"""
        import sqlite3

        real_connect = sqlite3.connect

        class _AlterFails:
            """A connection whose ALTERs fail the way a locked DB's would."""

            def __init__(self, conn):
                self._conn = conn

            def execute(self, sql, *args):
                if sql.lstrip().upper().startswith("ALTER TABLE"):
                    raise sqlite3.OperationalError("database is locked")
                return self._conn.execute(sql, *args)

            def __getattr__(self, name):
                return getattr(self._conn, name)

        monkeypatch.setattr(sqlite3, "connect",
                            lambda *a, **k: _AlterFails(real_connect(*a, **k)))
        # #258: constructing a store no longer runs the migration -- that
        # moved into _connect(). The PROPERTY under test is unchanged (a
        # non-"duplicate column" OperationalError is re-raised, never
        # swallowed); only the moment it surfaces moved from construction to
        # first use. So exercise the store rather than just build it.
        store = InferenceRunStore(db_path=str(tmp_path / "admz.db"))
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            store.list()

    def test_the_demos_table_is_untouched(self, tmp_path):
        """A run is evidence, never a demo — it must not appear in list_demos."""
        from admz.demos.store import DemoStore

        db = str(tmp_path / "admz.db")
        runs = InferenceRunStore(db_path=db)
        runs.finish(runs.start(mode=MODE_FAST).id, _graph())
        assert DemoStore(db_path=db).list() == []


# ═══════════════════════════════════════════════════════════════════════════
# REST
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
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
    # ACS off: the routes must degrade with a reason, never error.
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


class TestInferenceRoutes:
    def test_fast_run_returns_the_graph_inline(self, client, ctx):
        _add_device(ctx, "AABBCCDDEE01", tags=["entrance"])
        _add_device(ctx, "AABBCCDDEE02", tags=["entrance"])
        _add_device(ctx, "AABBCCDDEE03")
        _add_device(ctx, "AABBCCDDEE04")
        res = client.post("/api/demos/inference/runs", json={"mode": "fast"})
        assert res.status_code == 200
        run = res.json()["run"]
        assert run["status"] == "complete" and run["mode"] == "fast"
        assert run["device_count"] == 4
        assert run["graph"]["summary"]["device_count"] == 4
        # E4 links the two tagged devices even with no ACS and no snapshots.
        assert [e["id"] for e in run["graph"]["edges"]] == ["E4"]

    def test_no_acs_degrades_with_a_reason_rather_than_erroring(self, client, ctx):
        _add_device(ctx, "AABBCCDDEE01")
        run = client.post("/api/demos/inference/runs",
                          json={"mode": "fast"}).json()["run"]
        assert run["acs"]["available"] is False and run["acs"]["reason"]
        assert run["status"] == "complete"

    def test_run_with_an_empty_registry_still_succeeds(self, client):
        run = client.post("/api/demos/inference/runs",
                          json={"mode": "fast"}).json()["run"]
        assert run["status"] == "complete" and run["device_count"] == 0
        assert run["graph"]["edges"] == []

    def test_bad_mode_is_rejected(self, client):
        res = client.post("/api/demos/inference/runs", json={"mode": "wild"})
        assert res.status_code == 400

    def test_list_and_fetch_a_run(self, client, ctx):
        _add_device(ctx, "AABBCCDDEE01")
        created = client.post("/api/demos/inference/runs",
                              json={"mode": "fast"}).json()["run"]
        listed = client.get("/api/demos/inference/runs").json()
        assert listed["count"] == 1
        assert listed["runs"][0]["id"] == created["id"]
        assert "graph" not in listed["runs"][0]        # headers only

        one = client.get(f"/api/demos/inference/runs/{created['id']}").json()["run"]
        assert one["graph"]["params"]["weights"]["E1"] == 1.0

    def test_unknown_run_is_404(self, client):
        assert client.get("/api/demos/inference/runs/nope").status_code == 404

    def test_a_run_never_creates_a_demo(self, client, ctx):
        _add_device(ctx, "AABBCCDDEE01")
        client.post("/api/demos/inference/runs", json={"mode": "fast"})
        assert client.get("/api/demos").json()["demos"] == []

    def test_survey_starts_in_the_background_and_is_polled(self, client, monkeypatch):
        from admz.demos.inference import collect

        started = {}

        async def _fake_survey(ctx, store, run_id, **kwargs):
            started["run_id"] = run_id
            started["kwargs"] = kwargs
            store.progress(run_id, phase="snapshot", step=2, total=4)
            store.finish(run_id, _graph(devices=0, rules=0, edges=0),
                         message="survey done")

        monkeypatch.setattr(collect, "run_survey", _fake_survey)
        res = client.post("/api/demos/inference/runs",
                          json={"mode": "survey", "register_new": False})
        assert res.status_code == 200
        body = res.json()
        assert body["started"] is True
        run_id = body["run"]["id"]
        # The response returns immediately; the row starts out running.
        assert body["run"]["status"] == "running"
        assert body["run"]["progress"] == "0/4"

        for _ in range(50):
            run = client.get(f"/api/demos/inference/runs/{run_id}").json()["run"]
            if run["status"] != "running":
                break
        assert started["run_id"] == run_id
        assert started["kwargs"]["register_new"] is False
        assert run["status"] == "complete" and run["message"] == "survey done"

    def test_only_one_survey_at_a_time(self, client, ctx):
        ctx.inference_run_store.start(mode=MODE_SURVEY)
        res = client.post("/api/demos/inference/runs", json={"mode": "survey"})
        assert res.status_code == 409
        assert "already running" in res.json()["detail"]

    def test_the_demos_page_offers_the_button(self, client):
        html = client.get("/demos").text
        assert 'id="infer-fast"' in html and "Infer demos" in html
        assert 'id="infer-survey"' in html and "Deep survey" in html
        assert "let ADMZ look around" in html


# ═══════════════════════════════════════════════════════════════════════════
# Survey orchestration (fakes for every phase — no network, no device)
# ═══════════════════════════════════════════════════════════════════════════

class TestSurveyOrchestration:
    def test_every_phase_reports_and_a_failing_phase_never_aborts_the_run(
            self, tmp_path, monkeypatch):
        from admz.demos.inference import collect

        store = InferenceRunStore(db_path=str(tmp_path / "admz.db"))
        run = store.start(mode=MODE_SURVEY)

        async def _boom_discover(**_kw):
            raise RuntimeError("no network here")

        monkeypatch.setattr("admz.discovery.discover_devices", _boom_discover)

        class _Ctx:
            registry = type("R", (), {"list_devices": staticmethod(lambda: []),
                                      "get_device_info": staticmethod(lambda d: {})})()
            git_repo = type("G", (), {
                "read_facet": staticmethod(lambda *a, **k: None)})()
            catalog, executors = object(), {}

        monkeypatch.setattr("admz.modules.acs_pro.config.acs_enabled", lambda: False)
        asyncio.run(
            collect.run_survey(_Ctx(), store, run.id, register_new=False))

        done = store.get(run.id)
        assert done.status == STATUS_COMPLETE          # degraded, not failed
        assert done.graph["survey"]["discovered"] == 0
        assert "onboarding skipped by request" in done.graph["survey"]["notes"]

    def test_an_unexpected_error_marks_the_run_failed(self, tmp_path, monkeypatch):
        from admz.demos.inference import collect

        store = InferenceRunStore(db_path=str(tmp_path / "admz.db"))
        run = store.start(mode=MODE_SURVEY)

        def _explode(*_a, **_k):
            raise RuntimeError("store gone")

        monkeypatch.setattr(store, "progress", _explode)
        asyncio.run(
            collect.run_survey(object(), store, run.id))
        assert store.get(run.id).status == STATUS_FAILED
        assert "store gone" in store.get(run.id).error


# ═══════════════════════════════════════════════════════════════════════════
# MCP
# ═══════════════════════════════════════════════════════════════════════════

class TestMcpTool:
    @pytest.fixture
    def server(self, isolate_admz_dirs, monkeypatch):
        monkeypatch.setattr("admz.modules.acs_pro.config.acs_enabled", lambda: False)
        from admz.mcp.server import ADMZMCPServer
        return ADMZMCPServer()

    def test_survey_demo_evidence_returns_the_digest(self, server):
        server.registry.add_device("AABBCCDDEE01",
                                   {"host": "192.0.2.1", "nickname": "Gate",
                                    "model": "AXIS TEST", "tags": []})
        res = asyncio.run(
            server._survey_demo_evidence())
        assert res["success"] is True and res["status"] == "complete"
        assert res["summary"]["device_count"] == 1
        assert res["acs"]["available"] is False
        assert res["devices"][0]["name"] == "Gate"
        assert res["rules"] == [] and res["edges"] == []

    def test_a_stored_run_can_be_replayed_by_id(self, server):
        first = asyncio.run(
            server._survey_demo_evidence())
        again = asyncio.run(
            server._survey_demo_evidence(first["run_id"]))
        assert again["run_id"] == first["run_id"]
        assert again["summary"] == first["summary"]

    def test_unknown_run_id_is_an_error_not_a_crash(self, server):
        res = asyncio.run(
            server._survey_demo_evidence("nope"))
        assert res["success"] is False and "nope" in res["error"]
