"""Tests for firmware upgrade support.

Covers:
  - VapixExecutor multipart request building (content_type dispatch, JSON
    envelope serialization, timeout_override, file path resolution)
  - Firmware downloader (model normalization, version check, download,
    cache hit, 404 handling)
  - Upgrade path computation (same-major direct, cross-major intermediates,
    version parsing, format)
  - Resolver firmware synonyms
"""

import asyncio
import json
import os
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from admz.executor.vapix import VapixExecutor
from admz.executor.models import ExecutionRequest
from admz.firmware.downloader import (
    normalize_model_for_ftp,
    FirmwareNotAvailableError,
    _ftp_bases_for_model,
    _FTP_MPQT,
    _FTP_PACS,
    _FIMAGE_MAGIC,
    extract_firmware_version,
    scan_firmware_files,
    import_firmware_files,
    default_download_dirs,
    ScannedFirmware,
    ImportResult,
    _RE_VERSIONED,
    _RE_PLAIN,
)
from admz.firmware.upgrade_path import (
    parse_version,
    compute_upgrade_path,
    format_upgrade_path,
    LTS_MILESTONES,
)
from admz.catalog.resolver import _INTENT_SYNONYMS


def _run(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.run(coro)


# ------------------------------------------------------------------
# Multipart executor tests
# ------------------------------------------------------------------


class TestExecutorMultipart:
    """Test VapixExecutor multipart request building."""

    def _make_executor(self):
        return VapixExecutor()

    def test_content_type_dispatch_overrides_generation(self):
        """content_type=multipart/form-data should route to _build_multipart
        even if generation is legacy-cgi."""
        executor = self._make_executor()
        op = {
            "id": "test:upload",
            "method": "POST",
            "generation": "legacy-cgi",
            "request": {
                "content_type": "multipart/form-data",
                "body": {
                    "json": {"apiVersion": "1.0", "method": "upgrade"},
                    "file": "{firmware_file}",
                },
            },
        }
        params = {"firmware_file": "/tmp/test.bin"}
        req = executor.build_request(op, params)
        assert req.content_type == "multipart/form-data"
        assert req.file_path == "/tmp/test.bin"

    def test_json_envelope_serialized(self):
        """The JSON dict in the body template should be serialized as a string."""
        executor = self._make_executor()
        op = {
            "id": "firmwaremanagement.cgi:upgrade",
            "method": "POST",
            "request": {
                "content_type": "multipart/form-data",
                "body": {
                    "json": {"apiVersion": "1.0", "method": "upgrade"},
                    "file": "{firmware_file}",
                },
            },
        }
        params = {"firmware_file": "/tmp/fw.bin"}
        req = executor.build_request(op, params)
        assert "json" in req.form_data
        parsed = json.loads(req.form_data["json"])
        assert parsed["apiVersion"] == "1.0"
        assert parsed["method"] == "upgrade"

    def test_extra_params_merged_into_json_envelope(self):
        """Extra user params (like factoryDefaultMode) get merged into
        the JSON envelope's 'params' key."""
        executor = self._make_executor()
        op = {
            "id": "firmwaremanagement.cgi:upgrade",
            "method": "POST",
            "request": {
                "content_type": "multipart/form-data",
                "body": {
                    "json": {"apiVersion": "1.0", "method": "upgrade"},
                    "file": "{firmware_file}",
                },
            },
        }
        params = {
            "firmware_file": "/tmp/fw.bin",
            "factoryDefaultMode": "soft",
        }
        req = executor.build_request(op, params)
        parsed = json.loads(req.form_data["json"])
        assert parsed["params"]["factoryDefaultMode"] == "soft"

    def test_timeout_override_from_spec(self):
        """timeout from request spec should set timeout_override."""
        executor = self._make_executor()
        op = {
            "id": "firmwaremanagement.cgi:upgrade",
            "method": "POST",
            "request": {
                "content_type": "multipart/form-data",
                "timeout": 600,
                "body": {
                    "json": {"apiVersion": "1.0", "method": "upgrade"},
                    "file": "{firmware_file}",
                },
            },
        }
        params = {"firmware_file": "/tmp/fw.bin"}
        req = executor.build_request(op, params)
        assert req.timeout_override == 600.0

    def test_no_timeout_override_when_absent(self):
        """When no timeout in spec, timeout_override should be None."""
        executor = self._make_executor()
        op = {
            "id": "test:upload",
            "method": "POST",
            "request": {
                "content_type": "multipart/form-data",
                "body": {
                    "json": {"apiVersion": "1.0", "method": "test"},
                    "file": "{firmware_file}",
                },
            },
        }
        params = {"firmware_file": "/tmp/fw.bin"}
        req = executor.build_request(op, params)
        assert req.timeout_override is None

    def test_file_path_resolved_from_params(self):
        """File path placeholder should be resolved from params dict."""
        executor = self._make_executor()
        op = {
            "id": "test:upload",
            "method": "POST",
            "request": {
                "content_type": "multipart/form-data",
                "body": {
                    "file": "{firmware_file}",
                },
            },
        }
        params = {"firmware_file": "/home/user/firmware.bin"}
        req = executor.build_request(op, params)
        assert req.file_path == "/home/user/firmware.bin"

    def test_method_is_post(self):
        """Multipart requests should always use POST."""
        executor = self._make_executor()
        op = {
            "id": "test:upload",
            "method": "POST",
            "request": {
                "content_type": "multipart/form-data",
                "body": {"file": "{firmware_file}"},
            },
        }
        params = {"firmware_file": "/tmp/fw.bin"}
        req = executor.build_request(op, params)
        assert req.method == "POST"


# ------------------------------------------------------------------
# Firmware downloader tests
# ------------------------------------------------------------------


class TestNormalizeModel:
    """Test normalize_model_for_ftp."""

    def test_uppercase(self):
        assert normalize_model_for_ftp("p3245-v") == "P3245-V"

    def test_strip_axis_prefix(self):
        assert normalize_model_for_ftp("AXIS C1710") == "C1710"

    def test_axis_prefix_lowercase(self):
        assert normalize_model_for_ftp("axis c1710") == "C1710"

    def test_already_normalized(self):
        assert normalize_model_for_ftp("C1710") == "C1710"

    def test_whitespace(self):
        assert normalize_model_for_ftp("  P8815-2  ") == "P8815-2"


class TestFtpBasesForModel:
    """Test FTP base URL routing for MPQT vs PACS."""

    def test_camera_tries_mpqt_first(self):
        bases = _ftp_bases_for_model("P3245-V")
        assert bases[0] == _FTP_MPQT

    def test_intercom_tries_pacs_first(self):
        bases = _ftp_bases_for_model("I8016-LVE")
        assert bases[0] == _FTP_PACS

    def test_door_controller_tries_pacs_first(self):
        bases = _ftp_bases_for_model("A1610")
        assert bases[0] == _FTP_PACS

    def test_speaker_c1710_tries_pacs_first(self):
        """C1xxx models are PACS (speakers/intercoms)."""
        bases = _ftp_bases_for_model("C1710")
        assert bases[0] == _FTP_PACS

    def test_switch_tries_pacs_first(self):
        bases = _ftp_bases_for_model("S2208")
        assert bases[0] == _FTP_PACS

    def test_always_includes_both(self):
        """Both bases should always be included as fallback."""
        bases = _ftp_bases_for_model("P3245-V")
        assert len(bases) == 2
        assert _FTP_MPQT in bases
        assert _FTP_PACS in bases


class TestGetLatestVersion:
    """Test get_latest_version with mocked HTTP responses."""

    def test_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "12.8.54\n"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from admz.firmware.downloader import get_latest_version

            result = _run(get_latest_version("C1710"))
            assert result == "12.8.54"

    def test_not_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = ""

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from admz.firmware.downloader import get_latest_version

            result = _run(get_latest_version("NONEXISTENT"))
            assert result is None


class TestDownloadFirmware:
    """Test download_firmware with mocked responses."""

    def test_cache_hit(self, tmp_path):
        """When firmware file exists, should return cached info."""
        model = "C1710"
        version = "12.8.54"
        cached_file = tmp_path / "C1710_12_8_54.bin"
        cached_file.write_bytes(b"fake firmware content")

        # Mock get_latest_version (shouldn't be called for explicit version)
        from admz.firmware.downloader import download_firmware

        result = _run(
            download_firmware(
                model=model,
                version=version,
                firmware_dir=str(tmp_path),
            )
        )
        assert result.already_cached is True
        assert result.file_size > 0
        assert result.model == "C1710"

    def test_404_raises_not_available(self, tmp_path):
        """When FTP returns 404, should raise FirmwareNotAvailableError."""
        # Mock the stream response
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        # Also mock get for get_latest_version
        mock_ver_response = MagicMock()
        mock_ver_response.status_code = 404
        mock_client.get = AsyncMock(return_value=mock_ver_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from admz.firmware.downloader import download_firmware

            with pytest.raises(FirmwareNotAvailableError):
                _run(
                    download_firmware(
                        model="NONEXISTENT",
                        version="1.0",
                        firmware_dir=str(tmp_path),
                    )
                )


# ------------------------------------------------------------------
# Upgrade path tests
# ------------------------------------------------------------------


class TestParseVersion:
    """Test version string parsing."""

    def test_three_part(self):
        assert parse_version("12.6.51") == (12, 6, 51)

    def test_two_part(self):
        assert parse_version("9.80") == (9, 80, 0)

    def test_whitespace(self):
        assert parse_version("  10.12.3  ") == (10, 12, 3)

    def test_invalid(self):
        assert parse_version("not-a-version") is None

    def test_empty(self):
        assert parse_version("") is None


class TestComputeUpgradePath:
    """Test upgrade path computation through LTS milestones."""

    def test_same_major_direct(self):
        """Same major version → direct upgrade, no intermediates."""
        result = compute_upgrade_path("12.6.51", "12.8.54")
        assert result == []

    def test_cross_major_intermediates(self):
        """Crossing major versions → intermediate LTS milestones."""
        result = compute_upgrade_path("9.20.1", "12.8.54")
        assert result == ["9.80", "10.12", "11.11"]

    def test_from_old_version(self):
        """Starting from version 7.x → all LTS milestones."""
        result = compute_upgrade_path("7.40.1", "12.8.54")
        assert "8.40" in result
        assert "9.80" in result
        assert "10.12" in result
        assert "11.11" in result

    def test_single_major_step(self):
        """One major version jump → single intermediate."""
        result = compute_upgrade_path("10.5.0", "11.11.0")
        assert result == ["10.12"]

    def test_already_at_target(self):
        """Same version → empty path."""
        result = compute_upgrade_path("12.6.51", "12.6.51")
        assert result == []

    def test_downgrade_returns_empty(self):
        """Downgrade → empty path (user must handle manually)."""
        result = compute_upgrade_path("12.6.51", "11.11.0")
        assert result == []

    def test_invalid_version_returns_empty(self):
        """Invalid version strings → empty path."""
        result = compute_upgrade_path("invalid", "12.6.51")
        assert result == []

    def test_past_lts_in_same_major(self):
        """When current is past the LTS for that major, skip it."""
        # 9.81 is past the 9.80 LTS
        result = compute_upgrade_path("9.81.0", "12.8.54")
        assert "9.80" not in result
        assert "10.12" in result
        assert "11.11" in result


class TestFormatUpgradePath:
    """Test human-readable upgrade path formatting."""

    def test_direct_upgrade(self):
        result = format_upgrade_path("12.6.51", "12.8.54")
        assert "direct" in result.lower()
        assert "12.6.51" in result
        assert "12.8.54" in result

    def test_with_intermediates(self):
        result = format_upgrade_path("9.20.1", "12.8.54")
        assert "9.20.1" in result
        assert "9.80 (LTS)" in result
        assert "10.12 (LTS)" in result
        assert "11.11 (LTS)" in result
        assert "12.8.54" in result

    def test_explicit_intermediates(self):
        """Can pass intermediates explicitly."""
        result = format_upgrade_path(
            "9.20.1", "12.8.54", ["9.80", "10.12"]
        )
        assert "9.80 (LTS)" in result
        assert "10.12 (LTS)" in result


# ------------------------------------------------------------------
# Resolver synonym tests
# ------------------------------------------------------------------


class TestResolverFirmwareSynonyms:
    """Test that firmware-related intents are mapped correctly."""

    def test_upgrade_firmware(self):
        assert "upgrade firmware" in _INTENT_SYNONYMS
        assert "upgrade-firmware" in _INTENT_SYNONYMS["upgrade firmware"]

    def test_firmware_upgrade(self):
        assert "firmware upgrade" in _INTENT_SYNONYMS
        assert "upgrade-firmware" in _INTENT_SYNONYMS["firmware upgrade"]

    def test_update_firmware(self):
        assert "update firmware" in _INTENT_SYNONYMS
        assert "upgrade-firmware" in _INTENT_SYNONYMS["update firmware"]

    def test_flash_firmware(self):
        assert "flash firmware" in _INTENT_SYNONYMS
        assert "upgrade-firmware" in _INTENT_SYNONYMS["flash firmware"]

    def test_rollback_firmware(self):
        assert "rollback firmware" in _INTENT_SYNONYMS
        assert "rollback-firmware" in _INTENT_SYNONYMS["rollback firmware"]

    def test_firmware_status(self):
        assert "firmware status" in _INTENT_SYNONYMS
        assert "check-firmware" in _INTENT_SYNONYMS["firmware status"]

    def test_reboot(self):
        assert "reboot" in _INTENT_SYNONYMS
        assert "reboot-device" in _INTENT_SYNONYMS["reboot"]

    def test_restart(self):
        assert "restart" in _INTENT_SYNONYMS
        assert "reboot-device" in _INTENT_SYNONYMS["restart"]


# ------------------------------------------------------------------
# Firmware file detection regex tests
# ------------------------------------------------------------------


class TestFirmwareRegex:
    """Test regex patterns for firmware file detection."""

    def test_versioned_pattern_standard(self):
        m = _RE_VERSIONED.match("P3245-V_11_11_181.bin")
        assert m
        assert m.group(1) == "P3245-V"
        assert m.group(2) == "11_11_181"

    def test_versioned_pattern_four_segments(self):
        m = _RE_VERSIONED.match("A1610_12_8_55_1.bin")
        assert m
        assert m.group(1) == "A1610"
        assert m.group(2) == "12_8_55_1"

    def test_versioned_pattern_intercom(self):
        m = _RE_VERSIONED.match("I8016-LVE_12_7_53.bin")
        assert m
        assert m.group(1) == "I8016-LVE"
        assert m.group(2) == "12_7_53"

    def test_plain_pattern_standard(self):
        m = _RE_PLAIN.match("P3245-V.bin")
        assert m
        assert m.group(1) == "P3245-V"

    def test_plain_pattern_companion(self):
        m = _RE_PLAIN.match("Companion_Dome_V.bin")
        assert m
        assert m.group(1) == "Companion_Dome_V"

    def test_plain_pattern_excam(self):
        m = _RE_PLAIN.match("ExCam_XF_P3807.bin")
        assert m
        assert m.group(1) == "ExCam_XF_P3807"

    def test_rejects_generic_names(self):
        """Generic bin filenames should not match."""
        assert _RE_PLAIN.match("update.bin") is None
        assert _RE_PLAIN.match("firmware.bin") is None
        assert _RE_PLAIN.match("bootloader.bin") is None

    def test_rejects_lowercase_start(self):
        """Filenames starting with lowercase should not match plain pattern."""
        assert _RE_PLAIN.match("myfile.bin") is None


# ------------------------------------------------------------------
# Firmware version extraction tests
# ------------------------------------------------------------------


def _build_fimage_v4(version: str) -> bytes:
    """Build a minimal fimage header (version 4) with a version string."""
    # Pad to 0x200 (boot header area) then fimage header
    boot = b"\x00" * 0x200
    magic = _FIMAGE_MAGIC
    hdr_version = struct.pack("<I", 4)
    # Pad from +0x08 to +0x140 (0x138 bytes of placeholder)
    padding = b"\x00" * 0x138
    # Version string at +0x140, null-terminated in 64-byte field
    ver_bytes = version.encode("ascii") + b"\x00" * (64 - len(version))
    return boot + magic + hdr_version + padding + ver_bytes


def _build_fimage_v1(version: str) -> bytes:
    """Build a minimal fimage header (version 1) with a version string."""
    boot = b"\x00" * 0x200
    magic = _FIMAGE_MAGIC
    hdr_version = struct.pack("<I", 1)
    # Pad from +0x08 to +0x4C (0x44 bytes)
    padding = b"\x00" * 0x44
    ver_bytes = version.encode("ascii") + b"\x00" * (32 - len(version))
    return boot + magic + hdr_version + padding + ver_bytes


class TestExtractFirmwareVersion:
    """Test extract_firmware_version binary header parsing."""

    def test_fimage_v4_raw(self, tmp_path):
        """New-format fimage header (version 4), raw binary."""
        fw = tmp_path / "test.bin"
        fw.write_bytes(_build_fimage_v4("12.8.54"))
        assert extract_firmware_version(str(fw)) == "12.8.54"

    def test_fimage_v1_raw(self, tmp_path):
        """Old-format fimage header (version 1), raw binary."""
        fw = tmp_path / "test.bin"
        fw.write_bytes(_build_fimage_v1("9.80.78"))
        assert extract_firmware_version(str(fw)) == "9.80.78"

    def test_fimage_v4_gzip(self, tmp_path):
        """Gzip-wrapped fimage header."""
        import gzip as gz
        fw = tmp_path / "test.bin"
        raw = _build_fimage_v4("11.11.181")
        fw.write_bytes(gz.compress(raw))
        assert extract_firmware_version(str(fw)) == "11.11.181"

    def test_jffsid(self, tmp_path):
        """JFFSID format (network switches)."""
        fw = tmp_path / "test.bin"
        data = b'\x9b\x22\x77\x00AXIS:JFFSID="id-1234-6.54.3925"\x00'
        fw.write_bytes(data + b"\x00" * 256)
        assert extract_firmware_version(str(fw)) == "6.54.3925"

    def test_returns_none_for_garbage(self, tmp_path):
        """Random data should return None, not crash."""
        fw = tmp_path / "test.bin"
        fw.write_bytes(b"this is not firmware" * 100)
        assert extract_firmware_version(str(fw)) is None

    def test_returns_none_for_empty(self, tmp_path):
        """Empty file should return None."""
        fw = tmp_path / "test.bin"
        fw.write_bytes(b"")
        assert extract_firmware_version(str(fw)) is None

    def test_returns_none_for_missing_file(self, tmp_path):
        """Non-existent file should return None."""
        assert extract_firmware_version(str(tmp_path / "nope.bin")) is None

    def test_four_part_version(self, tmp_path):
        """Versions like 12.8.55.1 (PACS firmware)."""
        fw = tmp_path / "test.bin"
        fw.write_bytes(_build_fimage_v4("12.8.55.1"))
        assert extract_firmware_version(str(fw)) == "12.8.55.1"

    def test_scan_uses_binary_extraction(self, tmp_path):
        """scan_firmware_files should populate version from binary header."""
        import gzip as gz
        fw = tmp_path / "C1710.bin"
        fw.write_bytes(gz.compress(_build_fimage_v4("12.8.54")))
        results = scan_firmware_files(str(tmp_path), firmware_dir=str(tmp_path / "cache"))
        assert len(results) == 1
        assert results[0].model == "C1710"
        assert results[0].version == "12.8.54"


# ------------------------------------------------------------------
# Scan firmware files tests
# ------------------------------------------------------------------


class TestScanFirmwareFiles:
    """Test scan_firmware_files with real temp directories."""

    def test_detects_versioned_file(self, tmp_path):
        (tmp_path / "P3245-V_11_11_181.bin").write_bytes(b"x" * 1000)
        results = scan_firmware_files(str(tmp_path), firmware_dir=str(tmp_path / "cache"))
        assert len(results) == 1
        assert results[0].model == "P3245-V"
        assert results[0].version == "11.11.181"

    def test_detects_plain_file(self, tmp_path):
        (tmp_path / "C1710.bin").write_bytes(b"x" * 1000)
        results = scan_firmware_files(str(tmp_path), firmware_dir=str(tmp_path / "cache"))
        assert len(results) == 1
        assert results[0].model == "C1710"
        assert results[0].version is None

    def test_ignores_non_firmware_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hi")
        (tmp_path / "update.bin").write_bytes(b"x" * 1000)
        (tmp_path / "data.zip").write_bytes(b"x" * 1000)
        results = scan_firmware_files(str(tmp_path), firmware_dir=str(tmp_path / "cache"))
        assert len(results) == 0

    def test_ignores_unknown_model(self, tmp_path):
        """Without manifest, unknown series prefix should be rejected."""
        (tmp_path / "ZZZFOO.bin").write_bytes(b"x" * 1000)
        results = scan_firmware_files(str(tmp_path), firmware_dir=str(tmp_path / "cache"))
        assert len(results) == 0

    def test_detects_already_cached(self, tmp_path):
        # Create a cached file
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "P3245-V_11_11_181.bin").write_bytes(b"firmware")

        # Create matching source file
        (tmp_path / "P3245-V_11_11_181.bin").write_bytes(b"firmware")
        results = scan_firmware_files(str(tmp_path), firmware_dir=str(cache_dir))
        assert len(results) == 1
        assert results[0].already_cached is True

    def test_not_cached_when_different_version(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "P3245-V_11_11_180.bin").write_bytes(b"old")

        (tmp_path / "P3245-V_11_11_181.bin").write_bytes(b"new")
        results = scan_firmware_files(str(tmp_path), firmware_dir=str(cache_dir))
        assert len(results) == 1
        assert results[0].already_cached is False

    def test_manifest_validation(self, tmp_path):
        """When manifest exists, only listed models should be accepted."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Create manifest with just one model
        manifest = {"models": {"C1710": {"version": "12.8.54"}}}
        (cache_dir / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        # C1710 should be accepted, P3245-V should not
        (tmp_path / "C1710.bin").write_bytes(b"x" * 1000)
        (tmp_path / "P3245-V.bin").write_bytes(b"x" * 1000)

        results = scan_firmware_files(str(tmp_path), firmware_dir=str(cache_dir))
        assert len(results) == 1
        assert results[0].model == "C1710"

    def test_multiple_files(self, tmp_path):
        (tmp_path / "P3245-V_11_11_181.bin").write_bytes(b"x" * 1000)
        (tmp_path / "C1710.bin").write_bytes(b"x" * 1000)
        (tmp_path / "I8016-LVE_12_7_53.bin").write_bytes(b"x" * 1000)
        results = scan_firmware_files(str(tmp_path), firmware_dir=str(tmp_path / "cache"))
        assert len(results) == 3

    def test_nonexistent_directory(self):
        results = scan_firmware_files("/nonexistent/path")
        assert results == []


# ------------------------------------------------------------------
# Import firmware files tests
# ------------------------------------------------------------------


class TestImportFirmwareFiles:
    """Test import_firmware_files with mocked version lookups."""

    def test_import_versioned_file(self, tmp_path):
        """Versioned files should be copied directly."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        (tmp_path / "P3245-V_11_11_181.bin").write_bytes(b"firmware data")

        result = _run(import_firmware_files(str(tmp_path), str(cache_dir)))
        assert len(result.imported) == 1
        assert result.imported[0][0] == "P3245-V_11_11_181.bin"
        # Verify file actually copied
        assert (cache_dir / "P3245-V_11_11_181.bin").exists()

    def test_import_plain_file_with_version_lookup(self, tmp_path):
        """Plain MODEL.bin files need version lookup."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        (tmp_path / "C1710.bin").write_bytes(b"firmware data")

        with patch("admz.firmware.downloader.get_latest_version",
                    new_callable=AsyncMock, return_value="12.8.54"):
            result = _run(import_firmware_files(str(tmp_path), str(cache_dir)))

        assert len(result.imported) == 1
        assert (cache_dir / "C1710_12_8_54.bin").exists()

    def test_plain_file_no_version_available(self, tmp_path):
        """If version can't be determined, skip (not an error)."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        (tmp_path / "C1710.bin").write_bytes(b"firmware data")

        with patch("admz.firmware.downloader.get_latest_version",
                    new_callable=AsyncMock, return_value=None):
            result = _run(import_firmware_files(str(tmp_path), str(cache_dir)))

        assert len(result.skipped) == 1
        assert "version unknown" in result.skipped[0][1]
        assert len(result.errors) == 0

    def test_skip_already_cached(self, tmp_path):
        """Files already in cache should be skipped."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "P3245-V_11_11_181.bin").write_bytes(b"existing")

        (tmp_path / "P3245-V_11_11_181.bin").write_bytes(b"duplicate")
        result = _run(import_firmware_files(str(tmp_path), str(cache_dir)))
        assert len(result.skipped) == 1
        assert len(result.imported) == 0

    def test_mixed_results(self, tmp_path):
        """Mix of importable, skipped, and error files."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Will be imported (versioned)
        (tmp_path / "I8016-LVE_12_7_53.bin").write_bytes(b"new firmware")

        # Will be skipped (already cached)
        (cache_dir / "P3245-V_11_11_181.bin").write_bytes(b"existing")
        (tmp_path / "P3245-V_11_11_181.bin").write_bytes(b"dup")

        result = _run(import_firmware_files(str(tmp_path), str(cache_dir)))
        assert len(result.imported) == 1
        assert len(result.skipped) == 1


# ------------------------------------------------------------------
# Default download directories tests
# ------------------------------------------------------------------


class TestDefaultDownloadDirs:
    """Test default_download_dirs discovery."""

    def test_returns_list(self):
        result = default_download_dirs()
        assert isinstance(result, list)

    def test_all_dirs_exist(self):
        """All returned directories should actually exist."""
        for d in default_download_dirs():
            assert os.path.isdir(d)
