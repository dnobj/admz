"""#200 — no template or stylesheet may load a subresource from another origin.

## Why this test exists at all

Before #200 the templates loaded ``https://unpkg.com/lucide@latest`` on all
nine pages containing a ``type="password"`` input — the Windows sign-in form,
the credential capture forms, and the ADR-0034 confirmation-gate password
prompt. Nothing in the suite would have noticed, and nothing would notice the
next one either. Vendoring fixes today; this fixes tomorrow.

Two measurements from that investigation are worth keeping, because they are
why the *other* candidate fixes were rejected:

* ``@latest`` resolved with ``Cache-Control: max-age=60``. It is not "adopted
  eventually" — it is re-resolved roughly once a minute, so a newly published
  version reaches the operator's browser within about a minute.
* The Google Fonts ``css2`` endpoint serves **UA-dependent** content: 24,770
  bytes for a Chrome user-agent versus 470 for a legacy IE one, different
  SHA-384. A single ``integrity`` attribute cannot cover both browsers, so
  "pin + SRI" was structurally incapable of closing that one.

## The vacuity shape

A scanner that finds nothing is indistinguishable from a scanner that looks
nowhere. So :func:`test_the_scanner_actually_scans` asserts the sweep really
walked a plausible number of files and really parsed subresources out of them,
and :func:`test_the_vendored_asset_is_referenced` asserts the replacement is
present rather than merely that the CDN tag is absent — deleting the tag
outright would otherwise pass.

Mutation-checked by adding an external ``<script>`` to a template and
confirming this file goes red.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / "admz" / "api" / "templates"
STATIC = REPO_ROOT / "admz" / "api" / "static"
VENDOR = STATIC / "vendor"

#: Tags whose ``src``/``href``/``data`` attribute causes the browser to FETCH
#: something. ``<a href>`` is deliberately absent: that is navigation, not a
#: subresource, and ADMZ legitimately links to github.com and to localhost.
_SUBRESOURCE_TAG_ATTR = re.compile(
    r"<(script|link|img|iframe|source|audio|video|embed|object)\b[^>]*?"
    r"\b(src|href|data)\s*=\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE | re.DOTALL,
)
_CSS_IMPORT = re.compile(r"@import\s+url\(\s*[\"']?([^\"')]+)", re.IGNORECASE)
_CSS_URL = re.compile(r"\burl\(\s*[\"']?([^\"')]+)", re.IGNORECASE)

#: A URL is external if it names a scheme or is protocol-relative.
_EXTERNAL = re.compile(r"^\s*(?:[a-z][a-z0-9+.-]*:)?//", re.IGNORECASE)


def _is_external(url: str) -> bool:
    u = url.strip()
    if u.lower().startswith("data:"):
        return False  # inline payload, not a network fetch
    return bool(_EXTERNAL.match(u))


def _scan() -> tuple[list[tuple[str, str, str]], int]:
    """Return (violations, subresources_seen).

    ``violations`` are ``(file, tag_or_kind, url)``.
    """
    violations: list[tuple[str, str, str]] = []
    seen = 0
    for path in sorted(TEMPLATES.rglob("*.html")):
        src = path.read_text(encoding="utf-8", errors="replace")
        for tag, _attr, url in _SUBRESOURCE_TAG_ATTR.findall(src):
            seen += 1
            if _is_external(url):
                violations.append((str(path.relative_to(REPO_ROOT)), tag, url))
    for path in sorted(STATIC.rglob("*.css")):
        src = path.read_text(encoding="utf-8", errors="replace")
        for url in _CSS_IMPORT.findall(src) + _CSS_URL.findall(src):
            seen += 1
            if _is_external(url):
                violations.append(
                    (str(path.relative_to(REPO_ROOT)), "css-url", url)
                )
    return violations, seen


class TestNoExternalSubresources:
    def test_no_template_or_stylesheet_loads_an_external_subresource(self):
        violations, _ = _scan()
        assert not violations, (
            "External subresource(s) found. Vendor the asset under "
            "admz/api/static/vendor/ and record it in vendor/manifest.json "
            "(see #200 — an unpinned CDN script ran on every page with a "
            "password field):\n"
            + "\n".join(f"  {f}: <{t}> -> {u}" for f, t, u in violations)
        )

    def test_the_scanner_actually_scans(self):
        """Anti-vacuity: a scanner that looks nowhere finds nothing.

        If the template directory moves or the regex stops matching, the test
        above would go quietly green. Pin both the corpus and the parse.
        """
        violations, seen = _scan()
        html = list(TEMPLATES.rglob("*.html"))
        assert len(html) > 20, f"only {len(html)} templates found — wrong path?"
        assert seen > 10, (
            f"parsed only {seen} subresource references across {len(html)} "
            "templates — the regex is probably no longer matching"
        )

    def test_the_vendored_asset_is_referenced(self):
        """Absence of the CDN tag is not the same as presence of the fix.

        Deleting the script tag outright would satisfy the sweep while
        silently removing every icon in the UI.
        """
        refs = [
            p.name
            for p in TEMPLATES.rglob("*.html")
            if "/static/vendor/lucide-" in p.read_text(encoding="utf-8")
        ]
        assert sorted(refs) == ["base.html", "console_base.html", "login.html"], (
            f"expected the three shells to reference the vendored bundle, got {refs}"
        )


class TestVendorProvenance:
    """A vendored blob with no provenance is its own problem."""

    def test_manifest_exists_and_is_complete(self):
        manifest = json.loads((VENDOR / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["assets"], "manifest lists no assets"
        for asset in manifest["assets"]:
            for field in ("name", "version", "file", "source_url",
                          "sha256", "sri", "bytes", "vendored_on", "license"):
                assert asset.get(field), f"{asset.get('name')}: missing {field}"

    def test_every_vendored_file_matches_its_recorded_hash(self):
        """The local stand-in for SRI.

        SRI protects a *fetch*; there is no fetch any more. This protects the
        checked-in bytes instead — a corrupted or quietly-swapped vendor file
        fails here rather than in a browser.
        """
        manifest = json.loads((VENDOR / "manifest.json").read_text(encoding="utf-8"))
        for asset in manifest["assets"]:
            path = VENDOR / asset["file"]
            assert path.is_file(), f"{asset['file']} is missing"
            raw = path.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == asset["sha256"], (
                f"{asset['file']} does not match its recorded sha256"
            )
            assert len(raw) == asset["bytes"]
            expect_sri = "sha384-" + base64.b64encode(
                hashlib.sha384(raw).digest()
            ).decode()
            assert asset["sri"] == expect_sri

    def test_every_vendored_file_is_listed(self):
        """The inventory cannot drift: a file dropped into vendor/ without a
        manifest entry has no provenance and fails here."""
        manifest = json.loads((VENDOR / "manifest.json").read_text(encoding="utf-8"))
        listed = {a["file"] for a in manifest["assets"]}
        docs = {"manifest.json", "README.md"}
        on_disk = {p.name for p in VENDOR.iterdir()
                   if p.is_file() and p.name not in docs}
        assert on_disk == listed, (
            f"vendor/ and manifest.json disagree — "
            f"unlisted: {sorted(on_disk - listed)}, missing: {sorted(listed - on_disk)}"
        )


class TestSecurityHeaders:
    """The header must actually be emitted; a CSP that is present but wrong,
    or absent on the page that matters, reads as protection and is not."""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
        monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
        from fastapi.testclient import TestClient
        import admz.api.main as main_module
        with TestClient(main_module.app) as c:
            yield c

    @pytest.mark.parametrize(
        "path", ["/login", "/", "/static/css/admz.css", "/definitely-not-a-route"]
    )
    def test_csp_is_present_everywhere(self, client, path):
        r = client.get(path)
        csp = r.headers.get("content-security-policy", "")
        assert csp, f"{path} ({r.status_code}) carried no CSP"
        assert "default-src 'self'" in csp

    def test_csp_forbids_an_external_script_source(self, client):
        """The property #200 is actually about."""
        csp = client.get("/login").headers["content-security-policy"]
        script = [d for d in csp.split(";") if d.strip().startswith("script-src")]
        assert script, "no script-src directive"
        assert "unpkg" not in script[0]
        assert "https:" not in script[0], (
            "script-src admits an arbitrary https: source"
        )

    def test_unsafe_inline_is_retained_deliberately(self):
        """Pins the trade-off rather than leaving it implied.

        'unsafe-inline' is required by 16 inline <script> blocks and 32 inline
        on*= handlers. Removing it without converting those breaks the UI.
        This policy is WEAK against XSS and COMPLETE against external script
        loads; if that changes, it should change on purpose.
        """
        from admz.security_headers import CONTENT_SECURITY_POLICY
        assert "script-src 'self' 'unsafe-inline'" in CONTENT_SECURITY_POLICY

    def test_no_unsafe_eval(self):
        """Audited: no eval/new Function anywhere, including vendored lucide."""
        from admz.security_headers import CONTENT_SECURITY_POLICY
        assert "unsafe-eval" not in CONTENT_SECURITY_POLICY

    def test_other_headers(self, client):
        h = client.get("/login").headers
        assert h.get("x-content-type-options") == "nosniff"
        assert h.get("x-frame-options") == "DENY"
        assert h.get("referrer-policy") == "same-origin"
