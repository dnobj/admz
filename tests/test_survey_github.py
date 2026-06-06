"""Tests for survey submission: offline writer + stubbed GitHub PR flow."""

import json
import zipfile
from pathlib import Path

import pytest

from admz.survey.github import GitHubSubmitter, SubmitResult, write_offline


def _make_bundle(tmp: Path) -> Path:
    root = tmp / "b-1"
    (root / "capabilities").mkdir(parents=True)
    (root / "capabilities" / "x.yaml").write_text("model: X\n", encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({"bundle_id": "b-1"}), encoding="utf-8")
    return root


def test_write_offline_copies_and_zips(tmp_path):
    bundle = _make_bundle(tmp_path)
    out = tmp_path / "out"
    zip_path = write_offline(bundle, out_dir=out)
    assert zip_path.exists() and zip_path.suffix == ".zip"
    assert (out / "b-1" / "manifest.json").is_file()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert any(n.endswith("manifest.json") for n in names)


# --- stubbed GitHub session -------------------------------------------------


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FakeGitHub:
    """Records requests and returns canned responses for the fork-and-PR flow."""

    def __init__(self, *, existing_fork=True, existing_pr=False):
        self.calls = []
        self.existing_fork = existing_fork
        self.existing_pr = existing_pr
        self.put_paths = []

    def request(self, method, url, headers=None, json=None):
        self.calls.append((method, url, json))
        if url.endswith("/user"):
            return _Resp(200, {"login": "ec-user"})
        if "/forks" in url and method == "POST":
            return _Resp(202, {})
        if url.endswith("/repos/ec-user/axis-api-atlas"):
            return _Resp(200 if self.existing_fork else 404,
                         {} if self.existing_fork else None,
                         text="not found")
        if "/git/ref/heads/main" in url:
            return _Resp(200, {"object": {"sha": "deadbeef"}})
        if "/pulls?" in url and method == "GET":
            return _Resp(200, [{"html_url": "https://github.com/up/pr/9"}] if self.existing_pr else [])
        if url.endswith("/git/refs") and method == "POST":
            return _Resp(201, {})
        if "/contents/" in url and method == "PUT":
            self.put_paths.append(url)
            return _Resp(201, {})
        if url.endswith("/pulls") and method == "POST":
            return _Resp(201, {"html_url": "https://github.com/up/pr/42"})
        return _Resp(500, None, text="unexpected")


def test_submit_opens_pr(tmp_path):
    bundle = _make_bundle(tmp_path)
    fake = _FakeGitHub()
    sub = GitHubSubmitter("tok", "mrdnlabs/axis-api-atlas", session=fake)
    res = sub.submit(bundle, branch="contrib/ec/x-1", title="t", body="b")
    assert isinstance(res, SubmitResult)
    assert res.created and res.pr_url.endswith("/42")
    # one PUT per file in the bundle (manifest + capabilities/x.yaml)
    assert len(fake.put_paths) == 2
    assert all("contrib/incoming/b-1/" in u for u in fake.put_paths)


def test_submit_is_idempotent_when_pr_exists(tmp_path):
    bundle = _make_bundle(tmp_path)
    fake = _FakeGitHub(existing_pr=True)
    sub = GitHubSubmitter("tok", "mrdnlabs/axis-api-atlas", session=fake)
    res = sub.submit(bundle, branch="contrib/ec/x-1", title="t", body="b")
    assert res.reused and not res.created
    assert res.pr_url.endswith("/9")
    assert fake.put_paths == []   # no files pushed when reusing


def test_submit_creates_fork_when_missing(tmp_path):
    bundle = _make_bundle(tmp_path)
    fake = _FakeGitHub(existing_fork=False)
    sub = GitHubSubmitter("tok", "mrdnlabs/axis-api-atlas", session=fake)
    res = sub.submit(bundle, branch="contrib/ec/x-1", title="t", body="b")
    assert res.created
    assert any("/forks" in url for (m, url, _) in fake.calls if m == "POST")
