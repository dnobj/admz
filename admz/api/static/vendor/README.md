# Vendored third-party browser assets

Everything here is **third-party code checked into the repo on purpose**. It is
served from `/static/vendor/` and is the reason `admz/api/templates/` loads no
subresource from another origin.

## Why vendored rather than pinned + SRI (GH-200)

The templates used to load `https://unpkg.com/lucide@latest`, unpinned, with no
Subresource Integrity, on all nine pages containing a `type="password"` input —
the Windows sign-in form, the credential capture forms, and the ADR-0034
confirmation-gate password prompt. Two measurements decided the fix:

- **`@latest` resolved with `Cache-Control: max-age=60`.** That is not "adopted
  eventually"; it is re-resolved roughly once a minute, so a newly published
  version reaches the operator's browser within about a minute of publication.
- **The Google Fonts `css2` endpoint serves UA-dependent content** — 24,770
  bytes for a Chrome user-agent versus 470 for a legacy IE one, with different
  SHA-384. No single `integrity` attribute covers both browsers, so "pin + SRI"
  was *structurally incapable* of closing that subresource. Those fonts were
  dropped rather than vendored, because `--sans` and `--mono` in `admz.css`
  already carry complete fallback stacks.

## The rules

1. **Every file here has an entry in `manifest.json`** — name, version, the
   exact `source_url` it came from, `sha256`, an `sri` hash, byte count, date,
   and licence. `tests/test_no_external_subresources.py` fails if a file is
   present without an entry, or if its bytes stop matching the recorded hash.
   The hash is the local stand-in for SRI: there is no fetch left to protect,
   so it protects the checked-in bytes instead.
2. **The version is in the filename** (`lucide-1.28.0.min.js`). An update is
   then visible in the diff as an add plus a delete, not as an opaque blob
   change, and the template reference has to move with it.
3. **Nothing here is edited by hand.** If a local change is ever unavoidable,
   fork it into `static/` as first-party code instead — do not leave modified
   third-party bytes claiming a upstream provenance they no longer have.

## Updating an asset

```sh
V=1.29.0        # the new version
curl -sfo admz/api/static/vendor/lucide-$V.min.js \
  https://unpkg.com/lucide@$V/dist/umd/lucide.min.js

python - <<'EOF'
import base64, hashlib, json, pathlib
V = "1.29.0"
p = pathlib.Path(f"admz/api/static/vendor/lucide-{V}.min.js")
raw = p.read_bytes()
m = json.loads(pathlib.Path("admz/api/static/vendor/manifest.json").read_text())
a = next(a for a in m["assets"] if a["name"] == "lucide")
a.update(version=V, file=p.name, bytes=len(raw),
         source_url=f"https://unpkg.com/lucide@{V}/dist/umd/lucide.min.js",
         sha256=hashlib.sha256(raw).hexdigest(),
         sri="sha384-" + base64.b64encode(hashlib.sha384(raw).digest()).decode())
pathlib.Path("admz/api/static/vendor/manifest.json").write_text(
    json.dumps(m, indent=2) + "\n")
EOF

git rm admz/api/static/vendor/lucide-1.28.0.min.js
# then update the three template references and run:
python -m pytest tests/test_no_external_subresources.py -q
```

The three shells referencing it are `base.html`, `console_base.html` and
`login.html`. The test asserts all three, so a partial update fails.

## Why lucide is not tree-shaken

ADMZ uses 92 distinct icons and ships the whole 404 KB UMD bundle. Tree-shaking
would need a bundler, and there is **no JS build toolchain in this repo** — no
`package.json`, no bundler config. Introducing one would make the update path
"install node dependencies and run a build" inside a Python project, which is
the kind of step that stops being run. 404 KB served over loopback is the
cheaper trade. If a bundler ever arrives for other reasons, revisit it.
