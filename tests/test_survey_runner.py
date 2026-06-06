"""Tests for the survey run orchestration + scheduler handler registration."""

import os
from pathlib import Path

import pytest

from admz.survey.collector import SurveyCollector
from admz.survey.diff import AtlasIndex
from admz.survey.runner import SurveyRunReport, run_survey


class _FakeRegistry:
    def get_credentials(self, device_id, requester=None):
        return {"host": "10.0.0.9", "username": "root", "password": "pw"}

    def get_device_info(self, device_id):
        return {"model": "Z9999-XX"}

    def list_devices(self):
        return [{"device_id": "d1"}]


def _snapshot(host, user, password, verify=True, auth="auto"):
    return {
        "model": "Z9999-XX", "firmware": "1.0", "discovered": "2026-06-05",
        "device_id": "B8A44F000000", "api_count": 1,
        "apis": {"demo-rest": "1.0"},
        "apis_detail": {"demo-rest": {"dca": {
            "openapi": "/config/discover/apis/demo-rest/v1/openapi.json",
            "rest_api": "/config/rest/demo-rest/v1beta",
            "major": "v1beta", "state": "beta"}}},
    }


def _spec(host, user, password, verify, path):
    return {"openapi": "3.0.0", "paths": {"/demo-rest/v1beta": {"get": {}}}}


def _collector(tmp_path):
    idx = AtlasIndex(data_path=str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir(exist_ok=True)
    return SurveyCollector(_FakeRegistry(), index=idx,
                           snapshot_fn=_snapshot, spec_fetcher=_spec,
                           profile="hash-serial")


def test_run_offline_when_no_pat(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_SURVEY_WORK", str(tmp_path / "work"))
    monkeypatch.setenv("ADMZ_SURVEY_OUT", str(tmp_path / "out"))
    # ensure no PAT path is taken regardless of host state
    monkeypatch.setattr("admz.survey.runner.secrets.has_pat", lambda: False)
    monkeypatch.setattr("admz.survey.runner.secrets.get_contributor", lambda: "ec-test")

    report = run_survey(submit=False, respect_enabled=False,
                        collector=_collector(tmp_path))
    assert isinstance(report, SurveyRunReport)
    assert report.status == "offline"
    assert report.models == ["Z9999-XX"]
    assert Path(report.offline_path).exists()


def test_run_disabled_is_noop(monkeypatch):
    monkeypatch.setattr("admz.survey.runner.secrets.is_enabled", lambda: False)
    report = run_survey(submit=True, respect_enabled=True)
    assert report.status == "disabled"


def test_run_submits_when_pat_present(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_SURVEY_WORK", str(tmp_path / "work"))
    monkeypatch.setattr("admz.survey.runner.secrets.has_pat", lambda: True)
    monkeypatch.setattr("admz.survey.runner.secrets.get_contributor", lambda: "ec")

    class _FakeSubmitter:
        def submit(self, root, *, branch, title, body, **kw):
            from admz.survey.github import SubmitResult
            assert Path(root).is_dir()
            return SubmitResult(pr_url="https://github.com/up/pr/7",
                                branch=branch, created=True, message="ok")

    report = run_survey(submit=True, respect_enabled=False,
                        collector=_collector(tmp_path),
                        submitter=_FakeSubmitter())
    assert report.status == "submitted"
    assert report.pr_url.endswith("/7")


def test_scheduler_registers_survey_handler():
    from admz.snapshot.scheduler import get_job_handler, list_job_types
    assert "survey" in list_job_types()
    assert get_job_handler("survey") is not None


def test_app_includes_survey_routes():
    from admz.api.main import app
    paths = {r.path for r in app.routes}
    assert "/settings/survey" in paths
