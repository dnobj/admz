"""
Firmware downloader — fetches firmware .bin files from Axis public FTP.

Axis hosts firmware in two locations:
  - MPQT: cameras, encoders, radar, speakers (most models)
  - PACS: intercoms, door controllers, I/O relays, network switches

Both use the same directory layout:
  {BASE}/{MODEL}/latest/{MODEL}.bin   (latest version)
  {BASE}/{MODEL}/{VER}/{MODEL}.bin    (specific version)
  {BASE}/{MODEL}/latest/ver.txt       (version string)

Not all models are available on the public FTP.  When a model is
missing, returns a clear error suggesting manual download from
axis.com/support/device-software.
"""

import gzip
import json
import logging
import os
import platform
import re
import shutil
import struct
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_FIRMWARE_DIR = os.path.join(str(Path.home()), ".admz", "firmware")

# FTP base URLs — tried in order per model
_FTP_MPQT = "https://www.axis.com/ftp/pub_soft/MPQT"
_FTP_PACS = "https://www.axis.com/ftp/pub_soft/PACS"

# Model prefixes that live under PACS (intercoms, door controllers, etc.)
_PACS_PREFIXES = ("A", "I", "C1", "S2", "TA", "XC")

# Legacy alias for external consumers
_FTP_BASE = _FTP_MPQT


class FirmwareNotAvailableError(Exception):
    """Raised when firmware is not available on the public FTP for a model."""


class FirmwareDownloadError(Exception):
    """Raised when firmware download fails due to network/IO error."""


class FirmwareLoginRequiredError(FirmwareDownloadError):
    """Raised when the FTP server redirects to a login page."""


@dataclass
class FirmwareInfo:
    """Metadata about a downloaded or available firmware file."""

    model: str
    version: Optional[str]
    file_path: Optional[str]
    file_size: Optional[int]
    url: str
    already_cached: bool = False


def normalize_model_for_ftp(model: str) -> str:
    """Normalize model name for FTP path lookup.

    Axis FTP uses uppercase model names.
    Examples: "AXIS C1710" -> "C1710", "p3245-v" -> "P3245-V"
    """
    name = model.upper().strip()
    if name.startswith("AXIS "):
        name = name[5:]
    return name


def _ftp_bases_for_model(normalized: str) -> List[str]:
    """Return FTP base URLs to try for a model, ordered by likelihood.

    PACS models (intercoms, door controllers, I/O relays, switches)
    are tried on PACS first, then MPQT.  All others try MPQT first.
    """
    if any(normalized.startswith(p) for p in _PACS_PREFIXES):
        return [_FTP_PACS, _FTP_MPQT]
    return [_FTP_MPQT, _FTP_PACS]


async def get_latest_version(
    model: str, timeout: float = 30.0
) -> Optional[str]:
    """Check the latest available firmware version on the public FTP.

    Reads ver.txt from the model's latest/ directory.
    Tries both MPQT and PACS locations.
    Returns the version string, or None if model not found.
    """
    normalized = normalize_model_for_ftp(model)
    bases = _ftp_bases_for_model(normalized)

    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True
    ) as client:
        for base in bases:
            url = f"{base}/{normalized}/latest/ver.txt"
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.text.strip()
            except httpx.HTTPError:
                continue
        return None


async def download_firmware(
    model: str,
    version: Optional[str] = None,
    firmware_dir: Optional[str] = None,
    timeout: float = 600.0,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> FirmwareInfo:
    """Download firmware .bin file from the Axis public FTP.

    Args:
        model: Device model name (e.g., "P3245-V", "AXIS C1710").
        version: Specific version to download. If None, downloads latest.
        firmware_dir: Local directory for storing firmware.
        timeout: Download timeout in seconds (default 10 min).
        progress_callback: Optional callable(bytes_downloaded, total_bytes).

    Returns:
        FirmwareInfo with local file path and metadata.

    Raises:
        FirmwareNotAvailableError: Model not found on public FTP.
        FirmwareDownloadError: Network or I/O error during download.
    """
    normalized = normalize_model_for_ftp(model)
    target_dir = Path(firmware_dir or _DEFAULT_FIRMWARE_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine local filename (include version for caching)
    actual_version = version
    if not actual_version:
        actual_version = await get_latest_version(model) or "latest"

    local_filename = f"{normalized}_{actual_version.replace('.', '_')}.bin"
    local_path = target_dir / local_filename

    # Build candidate URLs (try multiple FTP locations)
    bases = _ftp_bases_for_model(normalized)
    if version:
        ver_path = version.replace(".", "_")
        candidate_urls = [
            f"{base}/{normalized}/{ver_path}/{normalized}.bin"
            for base in bases
        ]
    else:
        candidate_urls = [
            f"{base}/{normalized}/latest/{normalized}.bin"
            for base in bases
        ]

    # Check cache (URL-independent — same file regardless of source)
    if local_path.exists():
        file_size = local_path.stat().st_size
        if file_size > 0:
            logger.info(
                "Firmware already cached: %s (%d bytes)", local_path, file_size
            )
            return FirmwareInfo(
                model=normalized,
                version=actual_version,
                file_path=str(local_path),
                file_size=file_size,
                url=candidate_urls[0],
                already_cached=True,
            )

    # Download with streaming — try each candidate URL.
    # Don't follow redirects: Axis redirects .bin downloads to a login
    # page when authentication is required.  We detect the 302 and
    # report a clear error instead of saving the HTML login page.
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False
    ) as client:
        last_error = None
        login_redirect_url = None
        for bin_url in candidate_urls:
            try:
                async with client.stream("GET", bin_url) as response:
                    if response.status_code == 404:
                        logger.debug("Not found at %s, trying next", bin_url)
                        continue

                    # Detect login redirect (302 to /my-axis/login)
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location", "")
                        if "login" in location or "license" in location:
                            logger.info(
                                "Login required for %s (redirect to %s)",
                                bin_url, location,
                            )
                            login_redirect_url = bin_url
                            continue
                        # Non-login redirect — follow it manually
                        # (shouldn't happen for firmware, but just in case)
                        logger.debug("Redirect to %s, skipping", location)
                        continue

                    response.raise_for_status()

                    total = int(response.headers.get("content-length", 0))
                    downloaded = 0

                    temp_path = local_path.with_suffix(".tmp")
                    with open(temp_path, "wb") as f:
                        async for chunk in response.aiter_bytes(
                            chunk_size=65536
                        ):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total:
                                progress_callback(downloaded, total)

                    temp_path.rename(local_path)

                    file_size = local_path.stat().st_size
                    logger.info(
                        "Downloaded firmware: %s (%d bytes)", local_path, file_size
                    )
                    return FirmwareInfo(
                        model=normalized,
                        version=actual_version,
                        file_path=str(local_path),
                        file_size=file_size,
                        url=bin_url,
                        already_cached=False,
                    )

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.debug("Not found at %s, trying next", bin_url)
                    continue
                last_error = e
            except httpx.HTTPError as e:
                last_error = e

        # All URLs failed — determine best error
        if login_redirect_url:
            raise FirmwareLoginRequiredError(
                f"Firmware download for '{normalized}' requires an Axis "
                f"account (login redirect detected). Download manually "
                f"from https://www.axis.com/support/device-software and "
                f"provide the local file path to execute_operation."
            )
        if last_error and not isinstance(last_error, httpx.HTTPStatusError):
            raise FirmwareDownloadError(
                f"Network error downloading firmware: {last_error}"
            )
        raise FirmwareNotAvailableError(
            f"Firmware not found on public FTP for model '{normalized}'. "
            f"Tried: {', '.join(candidate_urls)}. "
            f"Try downloading manually from "
            f"https://www.axis.com/support/device-software"
        )


def list_cached_firmware(
    firmware_dir: Optional[str] = None,
) -> list:
    """List firmware files in the local cache directory."""
    target_dir = Path(firmware_dir or _DEFAULT_FIRMWARE_DIR)
    if not target_dir.exists():
        return []

    results = []
    for f in sorted(target_dir.glob("*.bin")):
        results.append(
            {
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "size_mb": round(f.stat().st_size / (1024 * 1024), 1),
                "path": str(f),
            }
        )
    return results


# ------------------------------------------------------------------
# Firmware version extraction from binary headers
# ------------------------------------------------------------------

# fimage header magic bytes (little-endian 0xa930ebf3)
_FIMAGE_MAGIC = b"\xf3\xeb\x30\xa9"


def extract_firmware_version(filepath: str) -> Optional[str]:
    """Extract firmware version directly from an Axis .bin file header.

    Supports five outer formats:
      1. Gzip-wrapped (most modern firmware) — decompress, find fimage header
      2. Raw binary with boot header (older firmware) — fimage at offset 0x200
      3. JFFSID (network switches like T85xx) — version in ASCII header
      4. ZIP bundle (body worn system) — version in entry filenames
      5. Encrypted/opaque MCU blobs — returns None (version not extractable)

    The fimage header (magic f3 eb 30 a9) contains the version string at a
    known offset that depends on the header version field:
      - Header version 1-3 (old): version at magic+0x4C, 32 bytes
      - Header version 4+  (new): version at magic+0x140, 64 bytes

    Only reads the first ~1KB of (decompressed) data, so this is fast even
    for multi-hundred-megabyte firmware files.
    """
    try:
        with open(filepath, "rb") as f:
            magic = f.read(4)

        if not magic or len(magic) < 4:
            return None

        # JFFSID format (network switches): magic 9b 22 77 00
        if magic == b"\x9b\x22\x77\x00":
            return _extract_jffsid_version(filepath)

        # ZIP bundle (body worn system): magic PK\x03\x04
        if magic == b"PK\x03\x04":
            return _extract_zip_version(filepath)

        # Gzip-wrapped or raw binary -> find fimage header
        if magic[:2] == b"\x1f\x8b":
            data = _read_gzip_head(filepath, 0x400)
        else:
            with open(filepath, "rb") as f:
                data = f.read(0x400)

        if not data:
            return None

        return _extract_fimage_version(data)

    except (OSError, gzip.BadGzipFile, struct.error):
        return None


def _read_gzip_head(filepath: str, nbytes: int) -> bytes:
    """Read the first nbytes of a gzip-compressed file."""
    with gzip.open(filepath, "rb") as gz:
        return gz.read(nbytes)


def _extract_fimage_version(data: bytes) -> Optional[str]:
    """Extract version from fimage header in raw/decompressed data."""
    idx = data.find(_FIMAGE_MAGIC)
    if idx < 0:
        return None

    hdr = data[idx:]
    if len(hdr) < 8:
        return None

    hdr_version = struct.unpack_from("<I", hdr, 4)[0]

    if hdr_version >= 4:
        # New format: version at +0x140, 64 bytes
        offset, length = 0x140, 64
    else:
        # Old format: version at +0x4C, 32 bytes
        offset, length = 0x4C, 32

    if len(hdr) < offset + length:
        return None

    raw = hdr[offset : offset + length]
    version = raw.split(b"\x00")[0].decode("ascii", errors="replace").strip()
    return version if version else None


def _extract_jffsid_version(filepath: str) -> Optional[str]:
    """Extract version from JFFSID header (network switches)."""
    with open(filepath, "rb") as f:
        data = f.read(256)
    m = re.search(rb'AXIS:JFFSID="id-\d+-([^"]+)"', data)
    return m.group(1).decode("ascii") if m else None


def _extract_zip_version(filepath: str) -> Optional[str]:
    """Extract version from ZIP bundle entry filenames (body worn system)."""
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            for name in z.namelist():
                m = re.search(r"(\d+\.\d+\.\d+)", name)
                if m:
                    return m.group(1)
    except zipfile.BadZipFile:
        pass
    return None


# ------------------------------------------------------------------
# Firmware file detection and import
# ------------------------------------------------------------------

# Known Axis model series prefixes (used when no manifest is available)
_KNOWN_SERIES_PREFIXES = (
    "A", "C", "D", "F", "I", "M", "P", "Q", "S", "T", "V", "W",
    "XC", "XF", "XP", "FA", "SR",
    "Companion", "ExCam",
)

# Versioned firmware: MODEL_DIGITS_DIGITS_DIGITS.bin
_RE_VERSIONED = re.compile(
    r"^([A-Za-z][A-Za-z0-9_-]+?)_(\d+(?:_\d+)+)\.bin$"
)

# Plain firmware: MODEL.bin (from latest/ download)
_RE_PLAIN = re.compile(
    r"^([A-Z][A-Za-z0-9-]+(?:_[A-Za-z][A-Za-z0-9-]*)*)\.bin$"
)


@dataclass
class ScannedFirmware:
    """A firmware file detected in a directory."""

    filename: str
    file_path: str
    file_size: int
    model: Optional[str]
    version: Optional[str]
    already_cached: bool = False


@dataclass
class ImportResult:
    """Result of importing firmware files into the cache."""

    imported: List[Tuple[str, str]] = field(default_factory=list)
    skipped: List[Tuple[str, str]] = field(default_factory=list)
    errors: List[Tuple[str, str]] = field(default_factory=list)


def _load_manifest_models(firmware_dir: str) -> Optional[Set[str]]:
    """Load known model names from manifest.json if it exists."""
    manifest_path = Path(firmware_dir) / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return set(data.get("models", {}).keys())
    except (json.JSONDecodeError, OSError):
        return None


def _is_known_series(model: str) -> bool:
    """Check if a model name starts with a known Axis series prefix."""
    upper = model.upper()
    return any(upper.startswith(p.upper()) for p in _KNOWN_SERIES_PREFIXES)


def _get_cached_versions(firmware_dir: str) -> Dict[str, List[str]]:
    """Get cached versions by model from the firmware directory."""
    cache_dir = Path(firmware_dir)
    cached: Dict[str, List[str]] = {}
    if not cache_dir.exists():
        return cached
    for f in cache_dir.glob("*.bin"):
        match = _RE_VERSIONED.match(f.name)
        if match:
            model = match.group(1)
            version = match.group(2).replace("_", ".")
            cached.setdefault(model, []).append(version)
    return cached


def scan_firmware_files(
    directory: str,
    firmware_dir: Optional[str] = None,
) -> List[ScannedFirmware]:
    """Scan a directory for files matching Axis firmware naming patterns.

    Uses layered detection to avoid false positives:
      1. Filename must match Axis firmware naming convention
      2. If manifest.json exists, model must be a known Axis model
      3. Without manifest, model must start with a known series prefix

    Returns list of detected firmware files with metadata.
    Does not copy or modify any files.
    """
    src_dir = Path(directory)
    if not src_dir.is_dir():
        return []

    fw_dir = firmware_dir or _DEFAULT_FIRMWARE_DIR
    manifest_models = _load_manifest_models(fw_dir)
    cached = _get_cached_versions(fw_dir)
    results: List[ScannedFirmware] = []

    for f in sorted(src_dir.glob("*.bin")):
        if not f.is_file():
            continue

        model = None
        version = None

        # Try versioned pattern first: MODEL_1_2_3.bin
        m = _RE_VERSIONED.match(f.name)
        if m:
            model = m.group(1)
            version = m.group(2).replace("_", ".")
        else:
            # Try plain pattern: MODEL.bin
            m = _RE_PLAIN.match(f.name)
            if m:
                model = m.group(1)

        if not model:
            continue

        # Validate model against manifest or known prefixes
        if manifest_models is not None:
            if model not in manifest_models:
                continue
        else:
            if not _is_known_series(model):
                continue

        # For plain MODEL.bin files, try to extract version from binary
        if not version:
            version = extract_firmware_version(str(f))

        # Check if already cached
        already_cached = False
        if version and model in cached:
            already_cached = version in cached[model]

        results.append(ScannedFirmware(
            filename=f.name,
            file_path=str(f),
            file_size=f.stat().st_size,
            model=model,
            version=version,
            already_cached=already_cached,
        ))

    return results


async def import_firmware_files(
    directory: str,
    firmware_dir: Optional[str] = None,
) -> ImportResult:
    """Scan a directory for firmware files and import them into the cache.

    Version detection priority:
      1. Filename (MODEL_VER.bin) — version embedded in name
      2. Binary header — parsed from fimage/JFFSID/ZIP header
      3. FTP ver.txt fallback — only if binary extraction fails

    Skips files already in cache.
    """
    fw_dir = firmware_dir or _DEFAULT_FIRMWARE_DIR
    target = Path(fw_dir)
    target.mkdir(parents=True, exist_ok=True)

    scanned = scan_firmware_files(directory, fw_dir)
    result = ImportResult()

    for item in scanned:
        if item.already_cached:
            result.skipped.append((item.filename, "already cached"))
            continue

        try:
            version = item.version
            if not version:
                # Fallback to FTP ver.txt (binary extraction already
                # ran in scan_firmware_files, so this only fires for
                # encrypted/opaque blobs that couldn't be parsed)
                version = await get_latest_version(item.model)
            if not version:
                result.skipped.append(
                    (item.filename, "version unknown (not in header or FTP)")
                )
                continue

            ver_underscored = version.replace(".", "_")
            dest_name = f"{item.model}_{ver_underscored}.bin"
            dest = target / dest_name
            if dest.exists():
                result.skipped.append(
                    (item.filename, f"already cached as {dest_name}")
                )
                continue
            shutil.copy2(item.file_path, dest)
            result.imported.append((item.filename, str(dest)))
        except OSError as e:
            result.errors.append((item.filename, str(e)))

    return result


def default_download_dirs() -> List[str]:
    """Return common download directories that exist on this system."""
    candidates = []
    home = Path.home()

    if platform.system() == "Windows":
        # Windows: check USERPROFILE\Downloads
        candidates.append(home / "Downloads")
        candidates.append(home / "Download")
    else:
        # macOS / Linux
        candidates.append(home / "Downloads")
        candidates.append(home / "Download")

    return [str(p) for p in candidates if p.is_dir()]
