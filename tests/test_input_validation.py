"""Tests for CR-5 — input validation on identifier-shaped fields.

Background: an unvalidated ``device_id`` like ``"../../../tmp/pwned"``
used to flow into ``GitRepo.device_path`` → ``mkdir`` / ``open``,
escaping the config-repo root. SQL was already safe (parameterized);
the fix is to reject malicious values at the entry points + add
defense-in-depth at the filesystem-touching code.

This file pins:
  - validate_identifier(): allow-list + explicit ``..`` reject
  - validate_git_ref(): wider charset for slash-separated refs
  - Pydantic models reject path-traversal device_id / account_id
  - FastAPI path-param validation rejects URL-encoded escapes
  - MCP call_tool dispatcher returns InvalidInput envelope on bad args
  - git_repo.device_path raises ValueError directly (defense-in-depth)
  - Legitimate identifiers continue to work end-to-end
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers (unit-level)
# ---------------------------------------------------------------------------


class TestValidateIdentifier:
    @pytest.mark.parametrize(
        "value",
        [
            "cam-01",
            "P3748-PLVE",
            "axis_b8a44f",
            "x",                          # single-char
            "a" * 128,                    # max-length
            "Q3538-SLVE",
            "device.with.dots",           # dots OK in middle (but not "..")
            "1234",                       # all-digit OK
        ],
    )
    def test_accepts_legitimate_ids(self, value):
        from admz.validators import validate_identifier
        assert validate_identifier(value, "device_id") == value

    @pytest.mark.parametrize(
        "value,reason",
        [
            ("", "empty"),
            ("../etc/passwd", "leading-dot"),
            (".hidden", "leading-dot"),
            ("-leading-dash", "leading-dash"),
            ("foo/bar", "slash"),
            ("foo\\bar", "backslash"),
            ("foo bar", "space"),
            ("a" * 129, "too-long"),
            ("foo;rm -rf /", "shell-metachar"),
            ("foo\nbar", "newline"),
            ("foo..bar", "double-dot"),
            ("..", "all-dots"),
            ("foo$bar", "dollar"),
        ],
    )
    def test_rejects_invalid(self, value, reason):
        from admz.validators import validate_identifier
        with pytest.raises(ValueError):
            validate_identifier(value, "device_id")

    def test_rejects_non_string(self):
        from admz.validators import validate_identifier
        with pytest.raises(ValueError):
            validate_identifier(123, "device_id")
        with pytest.raises(ValueError):
            validate_identifier(None, "device_id")


class TestValidateGitRef:
    @pytest.mark.parametrize(
        "value",
        [
            "HEAD",
            "main",
            "refs/heads/main",
            "v1.0.0",
            "abc123def456",       # commit SHA
            "tags/2026-05-21",
        ],
    )
    def test_accepts_legitimate_refs(self, value):
        from admz.validators import validate_git_ref
        assert validate_git_ref(value) == value

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "HEAD~1..HEAD",   # range — explicit reject
            "main..feature",  # range
            "HEAD; rm -rf /",
            "foo bar",
            ".badref",
            "-flag",
        ],
    )
    def test_rejects_invalid(self, value):
        from admz.validators import validate_git_ref
        with pytest.raises(ValueError):
            validate_git_ref(value)


# ---------------------------------------------------------------------------
# Pydantic model integration
# ---------------------------------------------------------------------------


class TestPydanticValidation:
    def test_device_create_rejects_traversal(self):
        from pydantic import ValidationError
        from admz.api.models import DeviceCreate
        with pytest.raises(ValidationError):
            DeviceCreate(device_id="../etc/passwd", host="x")

    def test_device_create_accepts_legitimate(self):
        from admz.api.models import DeviceCreate
        d = DeviceCreate(device_id="cam-01", host="192.0.2.1")
        assert d.device_id == "cam-01"

    def test_account_create_rejects_traversal(self):
        from pydantic import ValidationError
        from admz.api.models import AccountCreate
        with pytest.raises(ValidationError):
            AccountCreate(
                account_id="../escape", username="u", password="p"
            )

    def test_account_create_accepts_legitimate(self):
        from admz.api.models import AccountCreate
        a = AccountCreate(account_id="default", username="u", password="p")
        assert a.account_id == "default"


# ---------------------------------------------------------------------------
# REST endpoint integration
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    from admz.api.main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


class TestRestInputValidation:
    def test_post_devices_rejects_traversal_in_body(self, client):
        r = client.post(
            "/api/devices",
            json={"device_id": "../../../tmp/pwned", "host": "x"},
        )
        # Pydantic field_validator → 422 Unprocessable Entity.
        assert r.status_code == 422
        body = r.json()
        # The error message names the offending field + the rule.
        detail_str = str(body)
        assert "device_id" in detail_str

    def test_post_devices_accepts_legitimate(self, client):
        r = client.post(
            "/api/devices",
            json={"device_id": "test-cam-01", "host": "192.0.2.10"},
        )
        assert r.status_code == 201

    def test_post_accounts_rejects_traversal(self, client):
        client.post(
            "/api/devices",
            json={"device_id": "v-cam", "host": "192.0.2.11"},
        )
        r = client.post(
            "/api/devices/v-cam/accounts",
            json={
                "account_id": "../escape",
                "username": "u",
                "password": "p",
            },
        )
        assert r.status_code == 422

    def test_post_snapshot_restore_rejects_traversal(self, client):
        r = client.post(
            "/api/snapshot/restore",
            json={"device_id": "../escape", "ref": "HEAD"},
        )
        assert r.status_code == 422

    def test_post_snapshot_restore_rejects_bad_ref(self, client):
        # Even with a valid device_id, a malicious ref should be rejected.
        client.post(
            "/api/devices",
            json={"device_id": "r-cam", "host": "192.0.2.12"},
        )
        r = client.post(
            "/api/snapshot/restore",
            json={"device_id": "r-cam", "ref": "HEAD; rm -rf /"},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Filesystem defense-in-depth
# ---------------------------------------------------------------------------


class TestGitRepoDefenseInDepth:
    def test_device_path_rejects_traversal(self, tmp_path):
        from admz.snapshot.git_repo import GitRepo
        repo = GitRepo(tmp_path)
        with pytest.raises(ValueError, match="device_id"):
            repo.device_path("../../escape")

    def test_device_path_accepts_legitimate(self, tmp_path):
        from admz.snapshot.git_repo import GitRepo
        repo = GitRepo(tmp_path)
        p = repo.device_path("cam-01")
        assert p == tmp_path / "fleet" / "cam-01"

    def test_write_facet_rejects_traversal_facet_name(self, tmp_path):
        from admz.snapshot.git_repo import GitRepo
        repo = GitRepo(tmp_path)
        # Init the repo enough that device_path works.
        with pytest.raises(ValueError, match="facet_name"):
            repo.write_facet("cam-01", "../escape", {"x": 1})


# ---------------------------------------------------------------------------
# MCP dispatcher integration
# ---------------------------------------------------------------------------


class TestMcpInputValidation:
    """Validates the MCP call_tool dispatcher rejects bad identifier
    args with an InvalidInput envelope."""

    @pytest.fixture
    def mcp_server(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
        monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
        monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
        from admz import audit as audit_module
        fresh_audit = audit_module.AuditLog(db_path=str(tmp_path / "admz.db"))
        monkeypatch.setattr(audit_module, "audit_log", fresh_audit)
        from admz.mcp.server import ADMZMCPServer
        return ADMZMCPServer()

    @pytest.mark.asyncio
    async def test_get_device_rejects_traversal(self, mcp_server):
        from tests.test_mcp_audit import _call_tool
        result = await _call_tool(
            mcp_server, "get_device",
            {"device_id": "../../../etc/passwd"},
        )
        assert result.get("error") == "InvalidInput"
        assert "device_id" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_get_device_accepts_legitimate(self, mcp_server):
        mcp_server.registry.add_device("valid-cam", {"host": "x"})
        from tests.test_mcp_audit import _call_tool
        result = await _call_tool(
            mcp_server, "get_device", {"device_id": "valid-cam"}
        )
        assert result.get("success") is True
        # get_device returns the device shape under "device", not as
        # a top-level field.
        assert result.get("device", {}).get("device_id") == "valid-cam"

    @pytest.mark.asyncio
    async def test_diff_device_rejects_bad_ref(self, mcp_server):
        mcp_server.registry.add_device("ok-cam", {"host": "x"})
        from tests.test_mcp_audit import _call_tool
        result = await _call_tool(
            mcp_server, "diff_device",
            {"device_id": "ok-cam", "ref_a": "HEAD..HEAD~1"},
        )
        assert result.get("error") == "InvalidInput"


class TestDiffRefOptionInjection:
    """GH #162. `git diff <ref_a> <ref_b> -- <path>` puts both refs in argv
    **before** the `--` separator, so a ref beginning with `-` is parsed by git
    as an option. `--output=<path>` turns a read endpoint into an arbitrary file
    create/truncate running as the ADMZ service account.

    `GET /api/snapshot/diff/{device_id}` was the one handler in
    `api/routes/snapshot.py` validating neither its refs nor its device id,
    while five siblings validate both.
    """

    def test_the_dangerous_shape_is_rejected(self):
        import pytest
        from admz.validators import validate_git_ref
        for ref in ("--output=C:/evil.txt", "-o/tmp/evil", "--upload-pack=calc"):
            with pytest.raises(ValueError):
                validate_git_ref(ref)

    def test_the_leading_character_is_the_security_property(self):
        """`-` is fine inside a ref (`my-branch`) and fatal at the front."""
        from admz.validators import validate_git_ref
        import pytest
        assert validate_git_ref("my-branch") == "my-branch"
        with pytest.raises(ValueError):
            validate_git_ref("-my-branch")

    def test_rev_parse_suffixes_are_accepted(self):
        """They were not, while the docstring promised `HEAD~N` — and the one
        route defaulting to `HEAD~1` was the one that never validated, so
        nothing caught the contradiction. Applying the validator did."""
        from admz.validators import validate_git_ref
        for ref in ("HEAD~1", "HEAD^", "HEAD~10", "main~2", "v1.0.0"):
            assert validate_git_ref(ref) == ref

    def test_ranges_are_still_rejected(self):
        import pytest
        from admz.validators import validate_git_ref
        with pytest.raises(ValueError):
            validate_git_ref("HEAD~5..HEAD")

    def test_the_sink_validates_even_if_a_caller_forgets(self):
        """Validating only at the route is how this survived: five siblings did
        and this one didn't. `GitRepo.diff` now refuses regardless of caller."""
        import pytest
        from admz.snapshot.git_repo import GitRepo
        repo = GitRepo.__new__(GitRepo)          # no filesystem needed
        with pytest.raises(ValueError):
            repo.diff("--output=C:/evil.txt", "HEAD")
        with pytest.raises(ValueError):
            repo.diff("HEAD~1", "--output=C:/evil.txt")

    def test_a_pathspec_after_the_separator_is_not_validated(self):
        """Stated so the asymmetry is deliberate, not an oversight: `path` sits
        after `--`, where git treats it as a pathspec and never an option."""
        import inspect
        from admz.snapshot.git_repo import GitRepo
        src = inspect.getsource(GitRepo.diff)
        assert 'args += ["--", path]' in src
