#!/usr/bin/env python3
"""
Firmware cache builder — checks latest versions for all registered devices
and opens download URLs in the browser for any missing firmware.

Usage:
    python scripts/download_firmware.py                # check + open browser
    python scripts/download_firmware.py --check-only   # just show status
    python scripts/download_firmware.py --import-dir ~/Downloads  # import .bin files

The script:
  1. Reads all devices from the ADMZ registry
  2. Checks the latest firmware version on the Axis public FTP (no auth needed)
  3. Checks what's already cached in ~/.admz/firmware/
  4. Opens download URLs in your default browser for missing firmware
     (you must be logged into axis.com — downloads require an Axis account)
  5. After downloading, use --import-dir to move .bin files into the cache

Cache directory: ~/.admz/firmware/
Cache naming:    {MODEL}_{VERSION_UNDERSCORED}.bin  (e.g., I8016-LVE_12_7_53.bin)
"""

import argparse
import asyncio
import os
import re
import sys
import webbrowser
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def create_device_registry():
    """Create registry, handling missing hvac gracefully."""
    try:
        from admz import create_device_registry as _create
        return _create()
    except (ImportError, ModuleNotFoundError):
        # Import sqlite backend directly, bypassing __init__.py
        # which unconditionally imports the vault backend
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sqlite_backend",
            os.path.join(
                os.path.dirname(__file__), "..",
                "admz", "backends", "sqlite_backend.py",
            ),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.SQLiteDeviceRegistry()

from admz.firmware.downloader import (
    normalize_model_for_ftp,
    get_latest_version,
    import_firmware_files as module_import_firmware,
    _ftp_bases_for_model,
    _DEFAULT_FIRMWARE_DIR,
)


def get_devices_with_models(registry):
    """Get unique (model, device_ids) pairs from the registry."""
    models = {}  # model -> [device_ids]
    for device in registry.list_devices():
        device_id = device.get("device_id", "")
        # Try multiple fields for model name
        model = (
            device.get("model")
            or device.get("nickname", "")
        )
        if not model:
            continue

        normalized = normalize_model_for_ftp(model)
        if normalized not in models:
            models[normalized] = []
        models[normalized].append(device_id)

    return models


def get_cached_versions(firmware_dir):
    """Scan the cache directory for existing firmware files."""
    cache_dir = Path(firmware_dir)
    cached = {}  # model -> [(version, path, size)]
    if not cache_dir.exists():
        return cached

    for f in cache_dir.glob("*.bin"):
        # Parse filename: MODEL_VERSION.bin
        match = re.match(r"^(.+?)_(\d+_.+)\.bin$", f.name)
        if match:
            model = match.group(1)
            version = match.group(2).replace("_", ".")
            if model not in cached:
                cached[model] = []
            cached[model].append((version, str(f), f.stat().st_size))

    return cached


def build_download_url(model, version=None):
    """Build the FTP download URL for a model."""
    bases = _ftp_bases_for_model(model)
    base = bases[0]  # primary location
    if version:
        ver_path = version.replace(".", "_")
        return f"{base}/{model}/{ver_path}/{model}.bin"
    return f"{base}/{model}/latest/{model}.bin"


async def check_all_versions(models):
    """Check latest versions for all models in parallel."""
    tasks = {
        model: get_latest_version(model)
        for model in models
    }

    results = {}
    for model, coro in tasks.items():
        results[model] = await coro

    return results


def import_firmware_files(source_dir, firmware_dir):
    """Import .bin files from a directory into the firmware cache.

    Delegates to the module-level import function which handles
    pattern matching, version lookup, and manifest validation.
    """
    result = asyncio.run(module_import_firmware(source_dir, firmware_dir))
    # Convert ImportResult to the (imported, skipped) tuple format
    # that the CLI output code expects. Errors are reported as skipped.
    skipped = list(result.skipped) + list(result.errors)
    return list(result.imported), skipped


def main():
    parser = argparse.ArgumentParser(
        description="Firmware cache builder for ADMZ devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Just show firmware status, don't open browser",
    )
    parser.add_argument(
        "--import-dir",
        type=str,
        help="Import .bin files from this directory into the cache",
    )
    parser.add_argument(
        "--firmware-dir",
        type=str,
        default=_DEFAULT_FIRMWARE_DIR,
        help=f"Firmware cache directory (default: {_DEFAULT_FIRMWARE_DIR})",
    )
    parser.add_argument(
        "--all-versions",
        action="store_true",
        help="Show all cached versions, not just latest",
    )
    args = parser.parse_args()

    # Handle import mode
    if args.import_dir:
        if not os.path.isdir(args.import_dir):
            print(f"Error: {args.import_dir} is not a directory")
            sys.exit(1)

        imported, skipped = import_firmware_files(
            args.import_dir, args.firmware_dir
        )

        if imported:
            print(f"\nImported {len(imported)} firmware file(s):")
            for src, dest in imported:
                print(f"  {src} -> {dest}")
        if skipped:
            print(f"\nSkipped {len(skipped)} file(s):")
            for src, reason in skipped:
                print(f"  {src}: {reason}")
        if not imported and not skipped:
            print("No .bin files found in", args.import_dir)
        return

    # Main mode: check versions and open browser
    print("Connecting to ADMZ registry...")
    registry = create_device_registry()

    print("Scanning registered devices...")
    models = get_devices_with_models(registry)

    if not models:
        print("No devices with model info found in registry.")
        sys.exit(0)

    print(f"Found {len(models)} unique model(s) across registered devices.\n")

    # Check latest versions (async)
    print("Checking latest firmware versions on Axis FTP...")
    latest_versions = asyncio.run(check_all_versions(models))

    # Check cache
    cached = get_cached_versions(args.firmware_dir)

    # Build status table
    print()
    print(f"{'Model':<20} {'Latest':<12} {'Cached':<12} {'Devices':<8} {'Status'}")
    print("-" * 75)

    needs_download = []
    for model in sorted(models.keys()):
        device_ids = models[model]
        latest = latest_versions.get(model)
        model_cached = cached.get(model, [])

        # Check if latest is cached
        if latest and model_cached:
            cached_versions = [v for v, _, _ in model_cached]
            has_latest = latest in cached_versions
        else:
            has_latest = False

        if not latest:
            status = "NOT ON FTP"
            cached_str = "-"
        elif has_latest:
            # Find the cached file size
            for v, p, s in model_cached:
                if v == latest:
                    size_mb = round(s / (1024 * 1024), 1)
                    cached_str = f"{latest} ({size_mb}MB)"
                    break
            status = "UP TO DATE"
        elif model_cached:
            cached_str = model_cached[0][0]  # show first cached version
            status = "UPDATE AVAILABLE"
            needs_download.append((model, latest))
        else:
            cached_str = "-"
            status = "NEEDS DOWNLOAD"
            needs_download.append((model, latest))

        latest_str = latest or "?"
        print(
            f"{model:<20} {latest_str:<12} {cached_str:<12} "
            f"{len(device_ids):<8} {status}"
        )

    print()

    if not needs_download:
        print("All firmware is up to date!")
        return

    print(f"{len(needs_download)} firmware file(s) need downloading.\n")

    if args.check_only:
        print("Download URLs:")
        for model, version in needs_download:
            url = build_download_url(model)
            print(f"  {model}: {url}")
        print(
            f"\nRun without --check-only to open these in your browser."
        )
        return

    # Open downloads in browser
    print("Opening download URLs in your browser...")
    print("(You must be logged into axis.com)\n")

    for model, version in needs_download:
        url = build_download_url(model)
        print(f"  Opening: {model} v{version}")
        print(f"    URL: {url}")
        webbrowser.open(url)

    print(
        f"\nAfter downloading, import the files into the cache:\n"
        f"  python scripts/download_firmware.py "
        f"--import-dir ~/Downloads\n"
    )


if __name__ == "__main__":
    main()
