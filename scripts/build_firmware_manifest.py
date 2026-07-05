#!/usr/bin/env python3
"""
Build a firmware manifest and download page for all Axis models.

Scrapes the MPQT and PACS FTP directories, checks latest versions,
and generates:
  1. A JSON manifest of all models and their latest versions
  2. An HTML download page with all firmware links
  3. A URL list suitable for download managers (wget, aria2, etc.)

Usage:
    python scripts/build_firmware_manifest.py              # build manifest + HTML
    python scripts/build_firmware_manifest.py --urls-only   # just print URLs

Output files (in ~/.admz/firmware/):
    manifest.json        — model/version/URL data
    download_page.html   — open in browser, click to download
    urls.txt             — one URL per line for download managers
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from admz.firmware.downloader import (
    normalize_model_for_ftp,
    _ftp_bases_for_model,
    _FTP_MPQT,
    _FTP_PACS,
    _default_firmware_dir,
)


async def scrape_model_list(base_url: str, timeout: float = 30.0) -> List[str]:
    """Scrape model directory names from an FTP directory listing."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(base_url + "/")
        if response.status_code != 200:
            print(f"  Warning: Could not fetch {base_url} (HTTP {response.status_code})")
            return []

        # Parse Apache directory listing — look for href="NAME/"
        models = []
        for match in re.finditer(r'href="([^"]+)/"', response.text):
            name = match.group(1)
            if name in ("", "..", "/") or name.startswith("?"):
                continue
            models.append(name)

        return sorted(set(models))


async def check_version(
    client: httpx.AsyncClient,
    model: str,
    base_url: str,
) -> Optional[str]:
    """Check latest version for a model via ver.txt."""
    url = f"{base_url}/{model}/latest/ver.txt"
    try:
        response = await client.get(url)
        if response.status_code == 200:
            text = response.text.strip()
            # Sanity check — version should be short and numeric-ish
            if len(text) < 30 and re.match(r"[\d.]+", text):
                return text
        return None
    except httpx.HTTPError:
        return None


async def check_all_versions(
    models_by_base: Dict[str, List[str]],
    concurrency: int = 20,
) -> Dict[str, Tuple[str, str, str]]:
    """Check versions for all models with bounded concurrency.

    Returns dict of model -> (version, base_url, download_url).
    """
    semaphore = asyncio.Semaphore(concurrency)
    results: Dict[str, Tuple[str, str, str]] = {}

    async def check_one(client, model, base_url):
        async with semaphore:
            version = await check_version(client, model, base_url)
            if version:
                download_url = f"{base_url}/{model}/latest/{model}.bin"
                results[model] = (version, base_url, download_url)

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        tasks = []
        for base_url, models in models_by_base.items():
            for model in models:
                tasks.append(check_one(client, model, base_url))

        # Process in chunks to show progress
        total = len(tasks)
        chunk_size = 50
        for i in range(0, total, chunk_size):
            chunk = tasks[i:i + chunk_size]
            await asyncio.gather(*chunk)
            done = min(i + chunk_size, total)
            print(f"  Checked {done}/{total} models...", end="\r")

    print(f"  Checked {total}/{total} models — {len(results)} have firmware available")
    return results


def generate_html(
    models: Dict[str, Tuple[str, str, str]],
    output_path: Path,
) -> None:
    """Generate an HTML download page."""
    # Group by source
    mpqt_models = {k: v for k, v in models.items() if _FTP_MPQT in v[1]}
    pacs_models = {k: v for k, v in models.items() if _FTP_PACS in v[1]}

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ADMZ Firmware Downloads</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
  h1 {{ color: #333; }}
  h2 {{ color: #555; margin-top: 2em; }}
  .stats {{ background: #f0f0f0; padding: 15px; border-radius: 8px; margin: 15px 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background: #4a4a4a; color: white; position: sticky; top: 0; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  tr:hover {{ background: #e8e8e8; }}
  a {{ color: #0066cc; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .note {{ color: #666; font-size: 0.9em; margin: 10px 0; }}
  #filter {{ padding: 8px; width: 300px; margin: 10px 0; font-size: 14px; border: 1px solid #ccc; border-radius: 4px; }}
</style>
</head>
<body>
<h1>ADMZ Firmware Downloads</h1>
<div class="stats">
  <strong>{len(models)}</strong> models with firmware available |
  <strong>{len(mpqt_models)}</strong> cameras/encoders (MPQT) |
  <strong>{len(pacs_models)}</strong> PACS devices |
  Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
</div>
<p class="note">
  You must be logged into <a href="https://www.axis.com/my-axis/login" target="_blank">My Axis</a>
  for downloads to work. Right-click and "Save Link As" or use a download manager.
  After downloading, run: <code>python scripts/download_firmware.py --import-dir ~/Downloads</code>
</p>
<input type="text" id="filter" placeholder="Filter models..." onkeyup="filterTable()">
"""

    def table_section(title, model_dict):
        rows = ""
        for model in sorted(model_dict.keys()):
            version, base, url = model_dict[model]
            source = "PACS" if _FTP_PACS in base else "MPQT"
            rows += f'<tr><td>{model}</td><td>{version}</td><td>{source}</td><td><a href="{url}" target="_blank">Download</a></td></tr>\n'
        return f"""
<h2>{title} ({len(model_dict)} models)</h2>
<table class="firmware-table">
<thead><tr><th>Model</th><th>Latest Version</th><th>Source</th><th>Download</th></tr></thead>
<tbody>{rows}</tbody>
</table>
"""

    if pacs_models:
        html += table_section("PACS (Intercoms, Speakers, Controllers)", pacs_models)
    if mpqt_models:
        html += table_section("MPQT (Cameras, Encoders, Switches)", mpqt_models)

    html += """
<script>
function filterTable() {
  const filter = document.getElementById('filter').value.toLowerCase();
  document.querySelectorAll('.firmware-table tbody tr').forEach(row => {
    const model = row.cells[0].textContent.toLowerCase();
    row.style.display = model.includes(filter) ? '' : 'none';
  });
}
</script>
</body>
</html>
"""

    output_path.write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build firmware manifest for all Axis models")
    parser.add_argument("--urls-only", action="store_true", help="Just print download URLs")
    parser.add_argument("--output-dir", type=str, default=_default_firmware_dir(),
                        help=f"Output directory (default: {_default_firmware_dir()})")
    parser.add_argument("--concurrency", type=int, default=20,
                        help="Max concurrent version checks (default: 20)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Scraping model lists from Axis FTP...")

    # Scrape both directories
    mpqt_models = asyncio.run(scrape_model_list(_FTP_MPQT))
    print(f"  MPQT: {len(mpqt_models)} models")

    pacs_models = asyncio.run(scrape_model_list(_FTP_PACS))
    print(f"  PACS: {len(pacs_models)} models")

    total = len(mpqt_models) + len(pacs_models)
    print(f"  Total: {total} models\n")

    # Check versions for all models
    print("Checking latest firmware versions (this may take a minute)...")
    models_by_base = {
        _FTP_MPQT: mpqt_models,
        _FTP_PACS: pacs_models,
    }
    results = asyncio.run(check_all_versions(models_by_base, args.concurrency))

    if args.urls_only:
        for model in sorted(results.keys()):
            _, _, url = results[model]
            print(url)
        return

    # Generate manifest
    manifest = {
        "generated": datetime.now().isoformat(),
        "total_models": len(results),
        "models": {
            model: {"version": v, "source": "PACS" if _FTP_PACS in b else "MPQT", "url": u}
            for model, (v, b, u) in sorted(results.items())
        },
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nManifest: {manifest_path}")

    # Generate URL list
    urls_path = output_dir / "urls.txt"
    urls_path.write_text(
        "\n".join(results[m][2] for m in sorted(results.keys())) + "\n",
        encoding="utf-8",
    )
    print(f"URL list: {urls_path}")

    # Generate HTML page
    html_path = output_dir / "download_page.html"
    generate_html(results, html_path)
    print(f"Download page: {html_path}")

    print(f"\nOpen {html_path} in your browser to download firmware.")
    print("You must be logged into axis.com first.")


if __name__ == "__main__":
    main()
