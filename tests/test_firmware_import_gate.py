"""GH #188: importing into the firmware cache is a write into a trusted directory.

`executor/vapix.py::_upload_path_allowed` (the H-3 guard) answers "is this path
inside the firmware cache?" — containment, not authentication. It is therefore
only as strong as the doors into that directory, and `import_firmware` was an
ungated, LLM-reachable one whose `directory` argument was unconstrained and
defaulted to `~/Downloads`.

**The attack this file is really about is not firmware.** Rename `admz.key` —
the Fernet key protecting every stored device credential — to `X.bin`, import
it, then ask the executor to upload "firmware" to a device you control. The file
is inside the cache, so the guard says yes, and the host secret H-3 exists to
protect leaves the machine through the guard built to prevent exactly that.
`test_a_renamed_non_firmware_file_is_not_imported_ungated` is that case.

**What this does NOT close, so no one reads it as more:** it gates the *door*,
not the *artifact*. Nothing here verifies that a `.bin` is genuine firmware —
that is #188's second half (pin at entry, verify at the read), and even that
detects substitution rather than authenticating. What stops a genuinely
malicious firmware image flashing is the device's own mandatory signature check
(VAPIX `422`), which belongs to the device, not to ADMZ.

**The vacuity shape.** "the import is blocked" is trivially green if the tool
errors for an unrelated reason — no Downloads directory, an unknown device,
a missing catalog all return `success: False`. So every blocked assertion
checks for the *blocked envelope* specifically and asserts **nothing was
copied**, and `test_a_none_level_still_imports` pins that importing still works.

No test downloads real firmware or touches a real cache: `ADMZ_HOME` is
redirected and every file is bytes written into `tmp_path`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from admz import operations
from admz.operations import FIRMWARE_IMPORT_STAGES_FOR


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Mandatory: no test may reach a real firmware cache or database."""
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "home" / "admz.db"))
    yield tmp_path


@pytest.fixture
def staging(tmp_path):
    """A directory of plausible-looking artifacts, written not downloaded."""
    d = tmp_path / "Downloads"
    d.mkdir()
    (d / "P3245-V_11_11_181.bin").write_bytes(b"\x00fimage-ish bytes" * 64)
    return d


def _server(risk="dangerous"):
    from admz.mcp.server import ADMZMCPServer

    srv = object.__new__(ADMZMCPServer)
    srv.catalog = MagicMock()
    srv.catalog.get_risk_level.return_value = risk
    srv.registry = MagicMock()
    srv.registry.device_exists.return_value = True
    srv.registry.get_device_info.return_value = {"model": "P3245-V"}
    return srv


def _call(srv, **kw):
    args = {"directory": kw.pop("directory", None), **kw}
    return asyncio.run(srv._import_firmware(args))


def _cache_files():
    from admz.paths import firmware_dir

    root = Path(firmware_dir())
    return sorted(p.name for p in root.glob("*")) if root.exists() else []


# --- the gate --------------------------------------------------------------


def test_an_import_is_blocked_and_copies_nothing(staging):
    """THE #188 defect. This was an ungated write into the trusted directory."""
    srv = _server()

    out = _call(srv, directory=str(staging))

    assert out.get("blocked") is True, f"not blocked: {out}"
    assert out.get("success") is False
    assert out.get("confirm_token"), "a blocked envelope must carry a token"
    assert _cache_files() == [], "files were copied into the cache anyway"


def test_a_renamed_non_firmware_file_is_not_imported_ungated(tmp_path):
    """**The actual attack.** A host secret renamed to `.bin`.

    `scan_directory` globs `*.bin`, so the rename is all it takes to make the
    importer treat the Fernet key as firmware. Once inside the cache,
    `_upload_path_allowed` vouches for it and the executor will upload it to
    whichever device the caller names.
    """
    d = tmp_path / "Downloads"
    d.mkdir()
    # Shaped like the real thing: a Fernet key is 44 url-safe base64 bytes.
    (d / "P3245-V_11_11_181.bin").write_bytes(
        b"7SkV9mYQ2xJ4nR8pL1wC6tB0aZ3fH5eD7gN9iU2oK4M=")

    srv = _server()
    out = _call(srv, directory=str(d))

    assert out.get("blocked") is True
    assert _cache_files() == [], (
        "a renamed host secret reached the directory the upload guard trusts")


def test_the_level_is_inherited_from_the_operation_it_stages_for():
    """Inherited, not hardcoded — and from the flash, which is what an import
    pre-authorises."""
    srv = _server()
    _call(srv, directory="/nonexistent-but-unused")

    srv.catalog.get_risk_level.assert_called_with(
        "vapix", FIRMWARE_IMPORT_STAGES_FOR)
    assert FIRMWARE_IMPORT_STAGES_FOR == "firmwaremanagement.cgi:upgrade"


def test_a_dangerous_classification_resolves_to_the_strictest_level(staging):
    srv = _server(risk="dangerous")
    out = _call(srv, directory=str(staging))

    assert out.get("risk_level") == "dangerous"
    assert out.get("confirmation_level") == "url_and_password"


def test_a_service_affecting_classification_resolves_lower(staging):
    """The pair, so the test above is not green for a gate pinned to the
    strictest level regardless of what the catalog says."""
    srv = _server(risk="service-affecting")
    out = _call(srv, directory=str(staging))

    assert out.get("risk_level") == "service-affecting"
    assert out.get("confirmation_level") == "url_only"


def test_an_unreadable_catalog_fails_closed(staging):
    """Over-refusing is recoverable; under-refusing writes into the trusted
    directory."""
    srv = _server()
    srv.catalog.get_risk_level.side_effect = RuntimeError("catalog not loaded")

    out = _call(srv, directory=str(staging))

    assert out.get("blocked") is True
    assert _cache_files() == []


def test_a_none_level_still_imports(staging):
    """Anti-vacuity, and the compatibility path.

    Without this, every 'blocked' assertion above passes for a tool that can no
    longer import anything at all.
    """
    srv = _server(risk="read-only")   # resolves to none under default policy

    out = _call(srv, directory=str(staging))

    assert out.get("blocked") is not True
    assert out.get("success") is True, f"the ungated path broke: {out}"
    assert "P3245-V_11_11_181.bin" in _cache_files(), "nothing was imported"


# --- scan_only stays ungated ----------------------------------------------


def test_scan_only_is_not_gated(staging):
    """It copies nothing, and the model must still be able to tell an operator
    what is available. Gating a read would be friction with no security gain."""
    srv = _server()

    out = _call(srv, directory=str(staging), scan_only=True)

    assert out.get("blocked") is not True
    assert out.get("success") is True
    assert out.get("scan_only") is True
    assert out.get("files_found") == 1
    assert _cache_files() == [], "scan_only copied something"


# --- the reason names what is being approved -------------------------------


def test_the_reason_says_the_contents_are_what_is_approved(staging):
    """An approval card that says only 'import files' invites a yes. The
    operator is approving the *contents* of a directory they may not have
    inspected."""
    srv = _server()
    out = _call(srv, directory=str(staging))

    reason = (out.get("danger_description") or "") + (out.get("reason") or "")
    assert str(staging) in reason
    assert "CONTENTS" in reason or "contents" in reason
    assert "does not verify" in reason


# --- the approved executor -------------------------------------------------


def test_the_action_is_registered():
    assert "import_firmware" in operations._ACTION_EXECUTORS


def test_approval_performs_the_import(staging):
    out = asyncio.run(operations._action_import_firmware(
        {"action": "import_firmware", "directory": str(staging)}, MagicMock()))

    assert out["success"] is True
    assert "P3245-V_11_11_181.bin" in _cache_files()


def test_approval_without_a_directory_imports_nothing(staging):
    out = asyncio.run(operations._action_import_firmware(
        {"action": "import_firmware"}, MagicMock()))

    assert out["success"] is False
    assert _cache_files() == []


# --- the guard's own docstring records the interaction ---------------------


def test_the_upload_guard_documents_that_it_is_not_authentication():
    """The durable record. Prose in a PR body does not survive; the next person
    to touch `_upload_path_allowed` must meet this interaction there.

    Asserted on content rather than presence — a docstring that merely
    mentioned #188 without saying what the guard does *not* cover would pass a
    substring check and teach nobody.
    """
    from admz.executor.vapix import _upload_path_allowed

    doc = (_upload_path_allowed.__doc__ or "").lower()
    assert "containment, not authentication" in doc
    assert "admz.key" in doc, "the concrete exfiltration path is not named"
    assert "#188" in doc
    assert "signature" in doc, (
        "the docstring must say what actually stops malicious firmware, or a "
        "reader will assume this guard does")
