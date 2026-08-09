# User stories: firmware operations

Fetching firmware binaries from Axis's public FTP, computing LTS-aware upgrade paths for cross-major-version jumps, and applying firmware updates to devices.

## US-FW-001 — Look up the latest firmware for a model

**As an** operator preparing to update cameras, **I want to** see what firmware version is current for a model without manually browsing the Axis FTP.

**Acceptance criteria:**
1. `download_firmware(model="P3245-V", check_only=true)` returns `{model, latest_version, upgrade_path}` without downloading.
2. The lookup checks both Axis FTP bases — `MPQT` (cameras, encoders, radar, speakers) and `PACS` (intercoms, door controllers, network switches) — automatically chooses the right one based on model prefix.
3. If the model isn't published on the public FTP, the response includes `FirmwareNotAvailableError` so the operator knows manual download (Axis customer portal) is needed.

**Related requirements:** [firmware](../requirements/firmware.md).

## US-FW-002 — Download and cache firmware

**As an** operator preparing a firmware upgrade, **I want to** fetch the `.bin` to local cache before touching any devices.

**Acceptance criteria:**
1. `download_firmware(model="P3245-V", version="12.8.54")` fetches the binary from the Axis FTP into `~/.admz/firmware/`.
2. `already_cached: true` is returned if the file is already there — no redundant download.
3. Network or auth errors surface as structured exceptions (`FirmwareDownloadError`, `FirmwareLoginRequiredError`) rather than tracebacks.
4. The cache survives ADMZ restarts (it's on disk).

**Related requirements:** [firmware](../requirements/firmware.md).

## US-FW-003 — Compute an LTS-aware upgrade path

**As an** operator with devices on Axis OS 9.x looking to upgrade to 12.x, **I want** ADMZ to compute which intermediate LTS versions are required, **so that** I don't accidentally try to jump multiple major versions at once.

**Acceptance criteria:**
1. `compute_upgrade_path(current="9.20.1", target="12.8.54")` returns the ordered list of
   **intermediates only**: `["9.80", "10.12", "11.11"]`. It excludes both the current and
   the target version by contract, and the elements carry no `" (LTS)"` suffix.

   Two neighbouring functions produce the other shapes this criterion used to describe
   (#204): the MCP layer appends the target to build a full path, and `format_upgrade_path`
   adds the `(LTS)` labels for display. No single callable returns
   `["9.80 (LTS)", …, "12.8.54"]` — a caller that expected the target as the last element
   got a silently short list rather than an error.
2. Same-major upgrades return an empty intermediate-list (direct path).
3. Downgrades return an empty list with a note (manual handling required).
4. The known LTS milestones (`[(8, 40), (9, 80), (10, 12), (11, 11)]`) are documented + testable; future LTS milestones extend the list.
5. The upgrade-path is included in the `download_firmware` response when the target version is known.

**Related requirements:** [firmware](../requirements/firmware.md).

## US-FW-004 — Import locally-downloaded firmware

**As an** operator with air-gapped or login-gated firmware (downloaded from the Axis customer portal manually), **I want to** point ADMZ at a local directory and have it ingest the files.

**Acceptance criteria:**
1. `import_firmware(directory="~/Downloads", scan_only=false)` walks the directory for `.bin` files.
2. Filenames matching known model patterns are copied into the ADMZ firmware cache.
3. `scan_only=true` previews what would be copied without changing anything.
4. The response lists `imported` and `skipped` per file with reasons.

**Related requirements:** [firmware](../requirements/firmware.md).

## US-FW-005 — List cached firmware

**As an** operator checking what's already on disk, **I want** a quick inventory of cached firmware.

**Acceptance criteria:**
1. `list_cached_firmware()` returns
   `{success, firmware_dir, total_files, files: [{filename, size_bytes, size_mb, path}, ...]}`.
   The count key is `total_files`. (#204: every key in this criterion was wrong before —
   `count`, `model`, `version`, `file_name`, `file_path`, `file_size` are none of them real.)
2. **No model normalization happens here.** The listing globs `*.bin` and reports raw
   filenames; it never parses a model, which follows from there being no `model` field to
   normalize. Normalization does exist, but on the *download* path, where the model name
   becomes part of the cached filename.

## US-FW-006 — Apply firmware to a device

**As an** operator with cached firmware and intent to upgrade, **I want to** push the `.bin` to a device and have it install.

**Acceptance criteria:**
1. `execute_operation(device_id, operation_id="firmwaremanagement.cgi:upgrade", params={"firmware_file": "~/.admz/firmware/P3245-V-12.8.54.bin"})` initiates the upgrade.

   **The parameter name is load-bearing.** `upgrade.yaml`'s body template is `file: "{firmware_file}"`, and the executor resolves the placeholder name, then `firmware_file`, then `file` (`admz/executor/vapix.py`). A key matching none of those — `file_path`, which this document specified until #204 — does not bind, **and does not error**: the unmatched key is merged into the JSON envelope's `params` instead, so the multipart request goes out with no file attached.
2. The operation is classified `dangerous` in the catalog — `confirm_token` flow applies. Operator must explicitly approve.
3. The executor uses multipart upload with an extended timeout — `upgrade.yaml` sets `request.timeout: 600`, because firmware uploads take minutes.
4. **The upgrade operation does *not* declare `response.expect_timeout`.** Only three operations do — `factory-reset`, `hard-factory-reset` and `restart` — so a timeout during an upgrade is surfaced as a timeout, not converted to "device rebooting, expected". This document claimed the opposite until #204, which is the wrong expectation to hold during a `dangerous` operation: an operator told the timeout is benign may not check whether the upgrade actually landed.
5. The operator should call `firmwaremanagement.cgi:status` afterwards (read-only) to confirm the new version — which, given point 4, is how you establish what happened rather than a nicety.

**Related requirements:** [firmware](../requirements/firmware.md), [executor](../requirements/executor.md).

## US-FW-007 — Cross-major upgrade as a plan

**As an** operator needing to upgrade a device three major versions, **I want** ADMZ to build a multi-step plan that walks through the LTS milestones.

**Acceptance criteria:** 🚧 (partial — building the plan is manual today).

The pieces exist:
- `compute_upgrade_path` knows the LTS stops.
- `download_firmware` for each intermediate version works.
- `execute_operation` for `firmwaremanagement.cgi:upgrade` works per device.

What's not yet built:
- A `create_firmware_upgrade_plan(device_id, target_version)` MCP tool that stitches them together with the right `depends_on` chain and per-step `firmwaremanagement.cgi:status` checks.

For now, the LLM can do this with multiple tool calls; a dedicated helper would smooth it.

## Known limitations

- ⚠️ **Login-gated firmware** (versions that require the Axis customer portal login) is not auto-downloadable. `FirmwareLoginRequiredError` tells the operator to fetch manually + use `import_firmware`.
- 🚧 **Fleet-wide upgrades** require N individual `execute_operation` calls. A `firmware_upgrade_fleet` plan-builder would batch the work; not yet built.
- 📋 **Rollback after firmware** — Axis devices don't expose a "downgrade to previous" API in the same way. Rollback for firmware is a "boot into recovery + reflash" operation outside ADMZ's scope.
- ⚠️ **Long-running upload timing** — firmware uploads can take minutes per device. The catalog operation declares `timeout_override` accordingly, but operators running concurrent upgrades should watch their network.
