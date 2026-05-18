"""Tests for the bind-safety check and the ``admz api-key`` CLI."""

import pytest


# ---------------------------------------------------------------------------
# Bind-safety check
# ---------------------------------------------------------------------------


def _check_with_env(monkeypatch, host, **env):
    """Invoke _check_bind_safety with controlled env. Returns the
    function or raises SystemExit (which we catch in tests)."""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # Make sure unset values *are* unset
    if "ADMZ_AUTH_BACKEND" not in env:
        monkeypatch.delenv("ADMZ_AUTH_BACKEND", raising=False)
    if "ADMZ_AUTH_INSECURE_BIND_OK" not in env:
        monkeypatch.delenv("ADMZ_AUTH_INSECURE_BIND_OK", raising=False)

    from admz.__main__ import _check_bind_safety
    _check_bind_safety(host)


class TestBindSafety:
    def test_noauth_with_any_host_is_fine(self, monkeypatch):
        # NoAuth doesn't trust forwarded headers — bind wherever you want
        _check_with_env(monkeypatch, "0.0.0.0", ADMZ_AUTH_BACKEND="none")

    def test_apikey_backend_with_any_host_is_fine(self, monkeypatch):
        # API-key doesn't trust forwarded headers either
        _check_with_env(monkeypatch, "0.0.0.0", ADMZ_AUTH_BACKEND="api-key")

    def test_windows_backend_with_localhost_is_fine(self, monkeypatch):
        for host in ("127.0.0.1", "::1", "localhost"):
            _check_with_env(monkeypatch, host, ADMZ_AUTH_BACKEND="windows")

    def test_composite_backend_with_localhost_is_fine(self, monkeypatch):
        _check_with_env(monkeypatch, "127.0.0.1", ADMZ_AUTH_BACKEND="composite")

    def test_windows_with_wildcard_bind_refuses_to_start(self, monkeypatch, capsys):
        with pytest.raises(SystemExit) as exc:
            _check_with_env(
                monkeypatch, "0.0.0.0", ADMZ_AUTH_BACKEND="windows"
            )
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert "Refusing to start" in captured.err
        assert "header" in captured.err.lower()

    def test_composite_with_external_bind_refuses_to_start(self, monkeypatch):
        with pytest.raises(SystemExit):
            _check_with_env(
                monkeypatch, "10.0.0.5", ADMZ_AUTH_BACKEND="composite"
            )

    def test_override_env_var_allows_unsafe_bind(self, monkeypatch, capsys):
        # Operator with an unusual setup can explicitly opt in
        _check_with_env(
            monkeypatch,
            "10.0.0.5",
            ADMZ_AUTH_BACKEND="windows",
            ADMZ_AUTH_INSECURE_BIND_OK="true",
        )
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "ADMZ_AUTH_INSECURE_BIND_OK" in captured.err


# ---------------------------------------------------------------------------
# api-key CLI
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    """Point ADMZ at tmp_path so the CLI doesn't touch real ~/.admz/."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


class _ArgsObj:
    """Minimal duck-typed argparse Namespace for run_api_key()."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestApiKeyCli:
    def test_create_prints_plaintext_once(self, cli_env, capsys):
        from admz.__main__ import run_api_key

        args = _ArgsObj(
            apikey_command="create",
            name="nightly-bot",
            created_by="alice:cli",
            expires_in_days=None,
        )
        run_api_key(args)
        captured = capsys.readouterr()
        # Plaintext should be visible in the output
        assert "admz_" in captured.out
        assert "nightly-bot" in captured.out
        # And the "show once" warning
        assert "ONLY time" in captured.out

    def test_list_shows_created_key(self, cli_env, capsys):
        from admz.__main__ import run_api_key

        run_api_key(_ArgsObj(
            apikey_command="create", name="bot-a", created_by="alice:cli",
            expires_in_days=None,
        ))
        capsys.readouterr()  # drain
        run_api_key(_ArgsObj(
            apikey_command="list", include_revoked=False, json=False,
        ))
        out = capsys.readouterr().out
        assert "bot-a" in out
        assert "active" in out

    def test_list_json_format(self, cli_env, capsys):
        from admz.__main__ import run_api_key
        import json as json_mod

        run_api_key(_ArgsObj(
            apikey_command="create", name="bot-json", created_by="alice:cli",
            expires_in_days=None,
        ))
        capsys.readouterr()
        run_api_key(_ArgsObj(
            apikey_command="list", include_revoked=False, json=True,
        ))
        out = capsys.readouterr().out
        data = json_mod.loads(out)
        assert isinstance(data, list)
        assert any(k["display_name"] == "bot-json" for k in data)
        # No plaintext leaks into list output
        assert all("plaintext" not in k for k in data)

    def test_revoke_works(self, cli_env, capsys):
        from admz.__main__ import run_api_key

        run_api_key(_ArgsObj(
            apikey_command="create", name="doomed", created_by="alice:cli",
            expires_in_days=None,
        ))
        # Look up the id from the JSON list
        capsys.readouterr()
        run_api_key(_ArgsObj(
            apikey_command="list", include_revoked=False, json=True,
        ))
        import json as json_mod
        keys = json_mod.loads(capsys.readouterr().out)
        new_id = keys[0]["id"]

        run_api_key(_ArgsObj(apikey_command="revoke", id=new_id))
        out = capsys.readouterr().out
        assert "Revoked" in out

        # Active list no longer includes it
        run_api_key(_ArgsObj(
            apikey_command="list", include_revoked=False, json=True,
        ))
        active = json_mod.loads(capsys.readouterr().out)
        assert all(k["id"] != new_id for k in active)

    def test_revoke_nonexistent_exits_nonzero(self, cli_env, capsys):
        from admz.__main__ import run_api_key

        with pytest.raises(SystemExit) as exc:
            run_api_key(_ArgsObj(apikey_command="revoke", id=99999))
        assert exc.value.code != 0

    def test_create_with_empty_name_exits(self, cli_env, capsys):
        from admz.__main__ import run_api_key

        with pytest.raises(SystemExit):
            run_api_key(_ArgsObj(
                apikey_command="create", name="   ", created_by="x",
                expires_in_days=None,
            ))
