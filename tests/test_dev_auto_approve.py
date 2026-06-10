"""Tests for the dev-only confirmation auto-approver (tools/dev_auto_approve.py).

These pin the SAFETY behaviour: the guard env var, the lab/test tag scope
(including plans with mixed tags), and that an out-of-scope session is never
driven to the approval endpoint.
"""

import importlib.util
from pathlib import Path

import pytest

# Load the standalone tools/ script as a module (it's not a package).
_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "dev_auto_approve.py"
_spec = importlib.util.spec_from_file_location("dev_auto_approve", _TOOL_PATH)
daa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(daa)


# --- fakes -----------------------------------------------------------------


class _Session:
    def __init__(self, *, device_id="dev1", operation_id="systemready.cgi:restart",
                 confirmation_level="url_only", is_plan=False, plan_id="",
                 plan_steps_json=""):
        self.device_id = device_id
        self.operation_id = operation_id
        self.confirmation_level = confirmation_level
        self.is_plan = is_plan
        self.plan_id = plan_id
        self.plan_steps_json = plan_steps_json


class _Registry:
    def __init__(self, tags_by_device):
        self._tags = tags_by_device

    def device_exists(self, device_id):
        return device_id in self._tags

    def get_device_info(self, device_id):
        return {"tags": self._tags.get(device_id, [])}


class _Store:
    def __init__(self, session):
        self._session = session

    def get_session(self, token):
        return self._session


class _Resp:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class _Poster:
    def __init__(self, resp):
        self.resp = resp
        self.calls = []

    def __call__(self, url, data):
        self.calls.append((url, data))
        return self.resp


@pytest.fixture(autouse=True)
def _no_real_audit(monkeypatch):
    """Don't hit the real audit DB from unit tests."""
    monkeypatch.setattr(daa, "_audit_dev_approval", lambda *a, **k: None)


# --- guard -----------------------------------------------------------------


@pytest.mark.parametrize("val,expected", [
    ("1", True), ("true", True), ("YES", True), ("on", True),
    ("0", False), ("", False), ("false", False),
])
def test_guard_enabled(val, expected):
    assert daa.guard_enabled({daa.GUARD_ENV: val}) is expected


def test_guard_absent_is_false():
    assert daa.guard_enabled({}) is False


def test_main_refuses_without_guard(monkeypatch):
    monkeypatch.delenv(daa.GUARD_ENV, raising=False)
    assert daa.main([]) == 2


def test_main_all_requires_acknowledgement(monkeypatch):
    monkeypatch.setenv(daa.GUARD_ENV, "1")
    # --all without the acknowledgement flag must refuse.
    assert daa.main(["--all"]) == 2


# --- scope -----------------------------------------------------------------


def test_load_allow_tags_default():
    assert daa.load_allow_tags(None) == {"lab", "test"}
    assert daa.load_allow_tags("staging, qa ") == {"staging", "qa"}


def test_device_ids_single_op():
    s = _Session(device_id="cam1")
    assert daa.device_ids_for_session(s) == ["cam1"]


def test_device_ids_plan_uses_steps():
    s = _Session(device_id="multiple", is_plan=True, plan_id="p1",
                 plan_steps_json='[{"device_id":"a"},{"device_id":"b"},{"device_id":"a"}]')
    assert daa.device_ids_for_session(s) == ["a", "b"]


def test_in_scope_lab_tagged():
    reg = _Registry({"cam1": ["indoor", "lab"]})
    assert daa.session_in_scope(reg, _Session(device_id="cam1"), {"lab", "test"}) is True


def test_out_of_scope_untagged():
    reg = _Registry({"cam1": ["indoor"]})
    assert daa.session_in_scope(reg, _Session(device_id="cam1"), {"lab", "test"}) is False


def test_out_of_scope_unknown_device():
    reg = _Registry({})
    assert daa.session_in_scope(reg, _Session(device_id="ghost"), {"lab"}) is False


def test_plan_in_scope_requires_all_devices_tagged():
    reg = _Registry({"a": ["lab"], "b": ["lab"]})
    s = _Session(device_id="multiple", is_plan=True,
                 plan_steps_json='[{"device_id":"a"},{"device_id":"b"}]')
    assert daa.session_in_scope(reg, s, {"lab"}) is True


def test_plan_out_of_scope_if_any_device_untagged():
    reg = _Registry({"a": ["lab"], "b": ["prod"]})
    s = _Session(device_id="multiple", is_plan=True,
                 plan_steps_json='[{"device_id":"a"},{"device_id":"b"}]')
    assert daa.session_in_scope(reg, s, {"lab"}) is False


# --- approve_token ---------------------------------------------------------


def test_out_of_scope_never_posts():
    reg = _Registry({"cam1": ["prod"]})
    store = _Store(_Session(device_id="cam1"))
    poster = _Poster(_Resp(200, {"status": "completed"}))
    result = daa.approve_token(
        "tok", base_url="http://x", password=None, registry=reg,
        allow_tags={"lab"}, scope_all=False, store=store, http_post=poster,
    )
    assert result == "out-of-scope"
    assert poster.calls == []  # the gate was never driven


def test_in_scope_approves_and_posts():
    reg = _Registry({"cam1": ["lab"]})
    store = _Store(_Session(device_id="cam1"))
    poster = _Poster(_Resp(200, {"status": "completed", "outcome": {"success": True}}))
    result = daa.approve_token(
        "tok123", base_url="http://localhost:4242", password=None, registry=reg,
        allow_tags={"lab"}, scope_all=False, store=store, http_post=poster,
    )
    assert result == "approved"
    assert len(poster.calls) == 1
    url, data = poster.calls[0]
    assert url == "http://localhost:4242/api/chat/confirm/tok123"
    assert data == {}  # no password configured


def test_password_passed_through():
    reg = _Registry({"cam1": ["lab"]})
    store = _Store(_Session(device_id="cam1", confirmation_level="url_and_password"))
    poster = _Poster(_Resp(200, {"status": "completed", "outcome": {"success": True}}))
    daa.approve_token(
        "tok", base_url="http://x", password="hunter2", registry=reg,
        allow_tags={"lab"}, scope_all=False, store=store, http_post=poster,
    )
    assert poster.calls[0][1] == {"confirm_password": "hunter2"}


def test_scope_all_bypasses_tag_check():
    reg = _Registry({"cam1": ["prod"]})  # not lab — but scope_all overrides
    store = _Store(_Session(device_id="cam1"))
    poster = _Poster(_Resp(200, {"status": "completed", "outcome": {"success": True}}))
    result = daa.approve_token(
        "tok", base_url="http://x", password=None, registry=reg,
        allow_tags={"lab"}, scope_all=True, store=store, http_post=poster,
    )
    assert result == "approved"
    assert len(poster.calls) == 1


def test_expired_session_returns_expired():
    poster = _Poster(_Resp(200, {}))
    result = daa.approve_token(
        "gone", base_url="http://x", password=None, registry=_Registry({}),
        allow_tags={"lab"}, scope_all=False, store=_Store(None), http_post=poster,
    )
    assert result == "expired"
    assert poster.calls == []


def test_wrong_password_reported_as_error():
    reg = _Registry({"cam1": ["lab"]})
    store = _Store(_Session(device_id="cam1", confirmation_level="url_and_password"))
    poster = _Poster(_Resp(403, {"status": "wrong_password", "error": "Incorrect confirmation password."}))
    result = daa.approve_token(
        "tok", base_url="http://x", password="bad", registry=reg,
        allow_tags={"lab"}, scope_all=False, store=store, http_post=poster,
    )
    assert result.startswith("error")
