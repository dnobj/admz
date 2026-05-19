# Requirements: snapshot and restore

Capture a device's full configuration into a normalized, git-tracked
form; replay that configuration back onto the same device or a
peer.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-SNP-001 — DeviceSnapshot is the unit of capture ✅
`admz/snapshot/models.py::DeviceSnapshot`:
- `device_id`, `device_info`
- `facets` — list of `FacetResult` (one per facet adapter)
- `timestamp`, `status` (`in_progress` / `completed` / `failed` /
  `partial`), `git_sha`

A snapshot is "complete" only if every facet succeeded; partial
snapshots are captured but flagged so restore can refuse them.

### FR-SNP-002 — Pluggable facet adapters ✅
`admz/snapshot/facets/base.py::FacetAdapter` declares the contract
(`name`, `capture(device, credentials)`, `restore(device,
credentials, normalized)`). Built-in facets:

| Facet | What it captures |
|---|---|
| `network` | hostname, IP config, NTP, DNS |
| `image` | resolution, fps, exposure, white balance |
| `stream_profiles` | named stream presets |
| `time_config` | timezone, NTP sources |
| `users` | accounts and groups (passwords NOT captured) |
| `events` | event/action rules |

See [ADR-0015](../decisions/0015-pluggable-facets.md).

### FR-SNP-003 — SnapshotEngine orchestrates per-device capture ✅
`admz/snapshot/engine.py::SnapshotEngine`:
- `snapshot_device(device_id)` — runs all facet adapters
- `snapshot_fleet(device_ids=None, family=None, tags=None)` — runs
  many devices concurrently bounded by `fleet_concurrency`
- Each facet runs in parallel within a single device snapshot;
  per-facet failures don't abort the others (analogous to
  discovery's soft-fail)

### FR-SNP-004 — Bounded fleet concurrency ✅
`ADMZ_SNAPSHOT_FLEET_CONCURRENCY` (default 4) caps in-flight
device snapshots when running `snapshot_fleet`. Env var or ctor
arg; invalid env values fall back to default with a warning. Phase
3D, validated by [test_fleet_concurrency.py](../../tests/test_fleet_concurrency.py).

### FR-SNP-005 — Git-backed snapshot store ✅
`admz/snapshot/git_repo.py::SnapshotRepo` writes each device's
snapshot to `~/.admz/configs/<device_id>/<facet>.yaml` and commits.
Configs are versioned; snapshot diffs are git diffs. See
[ADR-0014](../decisions/0014-config-in-git-creds-in-db.md).

### FR-SNP-006 — Fleet snapshot is one commit ✅
`git_repo.commit_fleet_snapshot(snapshots, message)` produces a
single commit covering every device in the fleet snapshot — easier
to audit ("the 2026-05-15 fleet snapshot") than per-device commits.

### FR-SNP-007 — Restore builder produces a plan ✅
`admz/snapshot/restore.py::RestoreBuilder.build_restore_plan(
device_id, target_git_sha)` returns an `ExecutionPlan` (FR-PLN-001)
that, when executed, brings the device to the configuration in the
target commit. Restore is not a special path — it reuses the plan
engine, so the same confirmation gates apply.

### FR-SNP-008 — Cross-device clone ✅
`build_clone_plan(source_device_id, target_device_id,
source_git_sha=None)` produces a plan that applies one device's
config to another. Per-device fields (IP address, hostname, MAC)
are filtered out; the rest copies. Used in Experience Center
"replicate this camera" demos.

### FR-SNP-009 — Snapshots before plan execution ✅
The plan engine calls `snapshot_engine.snapshot_device` before any
step with `risk_level >= normal` and stores the resulting
`git_sha` in `ExecutionPlan.rollback_steps` metadata. See
[ADR-0012](../decisions/0012-snapshot-on-plans.md) and
FR-PLN-008.

### FR-SNP-010 — Snapshot status reflects facet failures ✅
A snapshot with one or more failed facets has status `partial` and
is not eligible to be the source for `build_clone_plan`. The user
sees which facets failed and can either rerun the snapshot or
restrict the clone to facets that succeeded.

## Non-functional requirements

### NFR-SNP-001 — Snapshots never include credentials ✅
The `users` facet captures account names + groups but not
passwords. There is no facet that captures the device's own
password or any operator-supplied credential. The git repo is
config-only by design — credentials live in the (separate)
device registry. See ADR-0014.

### NFR-SNP-002 — Snapshot output is normalized ✅
Facets emit a stable dict shape, not the raw VAPIX response.
Normalization lets restore on a different firmware revision still
work (within reason), and lets `git diff` be readable.

### NFR-SNP-003 — Per-device snapshots survive other failures ✅
`snapshot_fleet` doesn't abort if one device times out. The
failed device's snapshot has status `failed`; the rest complete
and commit.

## Known limitations

### KL-SNP-001 — Facet coverage is partial ⚠️
Six facets exist (network, image, stream_profiles, time_config,
users, events). Many VAPIX surfaces aren't yet captured: SSH keys,
overlays, applications/ACAP, certificates, audio config,
access-control configurations, recording rules. Adding a facet is
the documented extension point (NFR-EXT-002).

### KL-SNP-002 — Restore is not idempotent across firmware versions ⚠️
A snapshot from firmware 11.x restored to a 12.x device generally
works but isn't guaranteed — VAPIX semantics drift between major
firmware releases. The restore plan flags steps that target an
operation not present in the device's firmware (KL-CAT-004).

### KL-SNP-003 — Clone filters per-device fields ⚠️
The clone path strips IP / hostname / MAC. New per-device fields
landing in future facets need to be added to the filter list — no
schema-driven mechanism yet.

### KL-SNP-004 — No automated retention; manual gc available 🚧
The git repo grows monotonically. A fleet of 500 devices snapshotted
daily for a year produces a large repo.

Phase 6 added a maintenance surface to mitigate disk overhead
without rewriting history:

- `admz/snapshot/maintenance.py` — `get_repo_stats()` reports
  disk usage + commit count; `run_gc(repo, aggressive=…)` packs
  loose objects via ``git gc --prune=now``. Non-destructive — no
  commits are dropped.
- CLI: ``admz maintenance stats`` and ``admz maintenance gc
  [--aggressive]``. Operators can wire these into cron for
  weekly/monthly runs.
- Fleet settings ``snapshot_gc_enabled`` / ``snapshot_gc_aggressive``
  carry the operator's preference (in-process scheduling of
  maintenance jobs is still a follow-up).

True retention (history rewrite, ``git filter-repo``) is
deliberately out of scope — it's a human-led operation, not
something ADMZ does behind the operator's back.

## References

- ADRs: [0012](../decisions/0012-snapshot-on-plans.md), [0014](../decisions/0014-config-in-git-creds-in-db.md), [0015](../decisions/0015-pluggable-facets.md)
- Cross-cutting: [extensibility.md](extensibility.md), [reliability.md](reliability.md)
- Sibling: [drift-detection.md](drift-detection.md), [scheduling.md](scheduling.md), [plans.md](plans.md)
- Code: `admz/snapshot/`
