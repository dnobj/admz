# Requirements: firmware

Download firmware from Axis public FTP, compute LTS-milestone
upgrade paths, drive `firmwaremanagement.cgi` for upgrade and
rollback.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-FW-001 — Public FTP downloader ✅
`admz/firmware/downloader.py` fetches firmware `.bin` files from
the two Axis public mirrors:
- `MPQT` — cameras, encoders, radar, speakers
- `PACS` — intercoms, door controllers, I/O relays, network
  switches

Layout: `{BASE}/{MODEL}/latest/{MODEL}.bin` and
`{BASE}/{MODEL}/{VER}/{MODEL}.bin`. The downloader tries MPQT
first, falls back to PACS based on model prefix.

### FR-FW-002 — Local firmware cache ✅
Downloaded firmware lands in `~/.admz/firmware/`. The cache is
keyed by `(model, version)`. `list_cached_firmware()` enumerates
available files; `import_firmware(path)` ingests an out-of-band
.bin (for models not on the public FTP).

### FR-FW-003 — Upgrade path computation ✅
`admz/firmware/upgrade_path.py::compute_upgrade_path(current,
target)` returns the list of intermediate LTS versions that must
be installed between `current` and `target`. Skipping LTS
milestones can corrupt config; the device may auto-rollback.

The known LTS milestones table (`LTS_MILESTONES`) covers AXIS OS
8.40 / 9.80 / 10.12 / 11.11. New milestones land in this constant.

### FR-FW-004 — Upgrade via firmwaremanagement.cgi ✅
The catalog operation `firmwaremanagement.cgi:upgrade` posts the
firmware binary to the device. Risk-level `dangerous`. Wrapped by
the plan engine like any other write — snapshot first (FR-PLN-008),
explicit confirmation per fleet policy (FR-PLN-007).

### FR-FW-005 — Rollback to factory firmware ✅
`firmwaremanagement.cgi:rollback` reverts to the device's factory
firmware. Risk-level `dangerous`; intentionally irreversible
(`rollback: none`).

### FR-FW-006 — Firmware status query ✅
`firmwaremanagement.cgi:status` returns current version, factory
version, time of last upgrade. Read-only, used to drive the
upgrade-path computation and as the post-upgrade verification
step.

### FR-FW-007 — Errors classified for friendly handling ✅
The downloader raises three classes:
- `FirmwareNotAvailableError` — model not on public FTP (suggest
  manual download from axis.com/support/device-software)
- `FirmwareLoginRequiredError` — FTP redirected to login (auth
  layer changed on the public mirror)
- `FirmwareDownloadError` — generic network / IO failure

The CLI and MCP wrap these to surface actionable messages.

### FR-FW-008 — Firmware operations exposed via MCP and REST ✅
- MCP: `download_firmware(model, version?)`,
  `import_firmware(path, model, version)`,
  `list_cached_firmware()`
- REST: `GET /api/v2/firmware`, `POST /api/v2/firmware/download`,
  `POST /api/v2/firmware/import`

Upgrade itself goes through the plan engine
(`create_plan(template="firmware_upgrade", device=..., target=...)`)
so the LTS-stair, snapshot, and confirmation gates all apply.

## Non-functional requirements

### NFR-FW-001 — Download is resumable / re-runnable ✅
Re-downloading the same `(model, version)` reuses the cached file
if it exists and matches. Partial downloads are deleted before
retry. No HTTP range-request resume — files are 100–300 MB and a
fresh download takes seconds on a fast link.

### NFR-FW-002 — Upgrade timeouts honor expected duration ✅
The upgrade step uses an extended timeout (default 300s).
Firmware upload + flash takes several minutes on most models. See
[ADR-0018](../decisions/0018-expect-timeout-semantics.md).

### NFR-FW-003 — Firmware files never leak through the API ✅
The REST endpoints return metadata (path, size, version), not the
binary itself. To distribute firmware between hosts the operator
uses normal file transfer; the API isn't a CDN.

## Known limitations

### KL-FW-001 — Not all models are on the public FTP ⚠️
Newer / specialty models may require axis.com login. The
downloader detects this and raises `FirmwareLoginRequiredError`;
operators fall back to `import_firmware` after manual download.
No automated authenticated FTP support.

### KL-FW-002 — LTS milestone table is hand-maintained ⚠️
`LTS_MILESTONES` is a Python constant. A new LTS release requires
a code change. CI doesn't validate the table against the Axis
release feed. Frequency is low (every ~2 years) so the cost is
small.

### KL-FW-003 — Upgrade path stair doesn't parallelize ⚠️
Multi-step upgrades (8.x → 9 LTS → 10 LTS → 11 LTS → target) run
sequentially per device — each stair waits for the device to reboot
and respond before the next. A fleet-wide upgrade has wall time =
slowest device. The fleet semaphore caps how many devices are
upgrading concurrently, not the per-device stair.

### KL-FW-004 — No firmware signature verification at our layer ⚠️
The device itself verifies the firmware signature on upload; ADMZ
doesn't pre-verify locally. A tampered .bin in
`~/.admz/firmware/` would be rejected by the device but the
download itself isn't checksum-validated by ADMZ. The Axis FTP
serves over HTTPS, which is the protection.

### KL-FW-005 — No post-upgrade re-snapshot is automatic ⚠️
After an upgrade plan completes, drift detection may surface
benign config representation changes that the new firmware emits.
Operators typically re-snapshot post-upgrade; this isn't
automated. Planned as a template option (`re_snapshot=true`).

## References

- ADRs: [0005](../decisions/0005-two-gate-plan-approval.md), [0012](../decisions/0012-snapshot-on-plans.md), [0018](../decisions/0018-expect-timeout-semantics.md)
- Cross-cutting: [reliability.md](reliability.md), [security.md](security.md)
- Sibling: [plans.md](plans.md), [catalog.md](catalog.md)
- Code: `admz/firmware/`
