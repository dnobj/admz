# Experience Center Configuration Management

**Status:** Design sketch — capturing an idea, not a finalized spec
**Origin:** Conversation at the Axis Experience Center, 2026-05-15
**Last updated:** 2026-05-15 (decisions from review folded in)

---

## 1. The idea

The Axis Experience Center has a fleet of Axis network devices — cameras,
intercoms, speakers, access controllers, AOA scenarios — that get reconfigured
constantly for demos, customer visits, training sessions, and experiments.
There's no good way today to:

- Snapshot a device's full configuration so it can be restored later
- See what changed between two demo setups
- Roll back a device when a demo breaks it
- Fork "the lobby camera config" as the starting point for a new camera
- Review configuration changes before they hit the floor
- Tell visitors "here's exactly how this demo was configured" with receipts

A git repository of configurations — managed *through* ADMZ — would solve
all of these. Configurations become versioned, diffable, branchable assets.

This doc captures what that looks like and how it fits with the rest of
ADMZ (which has so far been focused on VAPIX command execution).

---

## 2. Goals (priorities, in order)

The features we want from git are the priorities. Everything else exists to
make these work:

1. **Diff** — see exactly what changed between two snapshots, or two devices
2. **History** — every config change is preserved, attributed, and timestamped
3. **Restore** — bring a device back to any previous configuration
4. **Fork** — copy a working configuration to a new device as a starting point
5. **Branch** — maintain parallel configurations (demo-A, demo-B, experimental)
6. **Pull request** — propose config changes, review, discuss, approve
7. **Blame** — find who last touched a particular setting and why
8. **CI validation** — block bad configs before they're applied
9. **Tags** — named snapshots ("pre-Q3-customer-visit", "fw-12-baseline")
10. **Cherry-pick** — apply one specific change across a fleet

If a design decision conflicts with any of these, the design loses.

---

## 3. The core question: where do configurations live?

ADMZ already has a database (SQLite by default). That database holds:

- Device registry (device_id, host, model, location, tags, ...)
- Encrypted credentials per device + account
- (eventually) audit logs, sessions, etc.

The new question is: where do *configurations* live?

### Scope: all device types, not just cameras

Cameras are the most common devices, but ADMZ supports the full Axis range
— access controllers, intercoms, network speakers, radar, AXIS Camera
Station servers, body-worn cameras, and whatever comes next. The
snapshot/restore system must handle all of them from the start, not
camera-first with others added later.

Each device type has a different shape of configuration, but the
architecture (facets + serializers + raw fallback + plan-based restore)
works the same way for all of them. The facets just differ.

### What "configuration" means here

A configuration is not credentials. It's the device's operational state.
The list below is illustrative, not exhaustive — new device types and new
firmware will keep adding to it.

**For cameras / video devices:**
- The full `param.cgi` parameter tree (image, network, time, events, ...)
- Stream profiles
- User accounts (the *list* — usernames, roles — not the passwords)
- Event/action rule definitions
- View areas, privacy masks
- AOA scenarios and parameters
- Installed ACAP applications (names + versions + their config)
- Network settings (IP, DNS, NTP — separate from credentials)
- Public certificates and trust anchors
- Firmware version (for restore compatibility)

**For access control devices (A1601, A1610, etc.):**
- Schedules
- Cardholder *schema* (not the actual cards — those are operational data)
- Door configurations
- Access rules / time zones
- Wiegand / OSDP reader configurations
- I/O port configurations

**For intercoms / network speakers:**
- SIP configuration
- Audio profiles (volume, equalizer)
- Pre-recorded audio clips (as artifacts)
- Scheduled audio playback

**For AXIS Camera Station servers:**
- Recording schedules
- Connected camera roster
- Storage allocation
- User permissions
- Smart search / analytics configurations

**For any device type:**
- Firmware version + model + hardware revision (for restore compatibility)
- Time/NTP configuration

The architecture must be open to new facets: a new device family, a new
firmware revision, or a new product line should be addable without
rewriting anything. See §6 "Facets are pluggable" below.

### Beyond the device itself

The git repo is also the right place for things *about* the device that
the device doesn't know about itself:

- Operator notes (per device or per setup)
- Physical installation photos
- Floor plans / network topology diagrams
- Demo scripts ("for the conference room demo, show stream A then play
  audio clip B")
- Customer-visit logs (who saw which configuration when)
- Calibration data (camera angle, focus distance, mount type)
- Integration notes ("this camera feeds into this VMS analytic")
- NDA / customer-tracking metadata where relevant

Some of these are free-form Markdown, some are structured YAML. The repo
has room for both. See the revised structure in §5.

### Three options

**Option A: Database is the source of truth, git is a derived artifact**

ADMZ stores config in the DB. A separate "export to git" job serializes
DB rows into YAML files and commits them. Git is read-only mirror.

- ✅ One source of truth for queries
- ❌ Loses git's editing model — you can't `git diff`, fix in YAML, merge back
- ❌ PRs become advisory only; the DB is still where reality lives
- ❌ Forking a device's config = copying DB rows, not branching files
- ❌ Most of the git superpowers (priorities 4-10) don't work

**Option B: Git is the source of truth, no DB for config**

Configs live only in git. ADMZ clones the repo, reads YAML, applies it.
DB only holds credentials, audit logs, runtime state.

- ✅ All git superpowers work natively
- ✅ Clear separation: secrets in DB, configs in git
- ✅ Restore = `git checkout` then apply
- ❌ Loses fast queries ("show me all cameras with H.265 enabled")
- ❌ Requires a repo to be configured to do *anything* configuration-related
- ❌ Live drift detection needs a separate "current state" cache anyway

**Option C: Git is the source of truth, DB is a query cache** ← recommended

Configs live in git. ADMZ also maintains a denormalized DB cache for fast
queries, drift detection, and UI rendering. The cache is rebuilt from git
on every commit. Writes always go through git first; the cache trails.

- ✅ All git superpowers preserved
- ✅ Fast queries via the cache
- ✅ Drift detection becomes "compare device state to git HEAD"
- ✅ DB rebuild from git is a recoverable, replayable operation
- ❌ Cache invalidation complexity (mitigated: it's a one-way mirror)
- ❌ Two stores to keep consistent

**Recommendation: Option C.** It preserves the git workflow as the primary
editing model while keeping the DB for what it's good at. The DB never
disagrees with git — if it does, git wins, and the cache is rebuilt.

### What stays in the DB regardless

These do **not** belong in git, even with encryption:

- **Credentials** (passwords, API tokens, private keys). Git history is
  forever; a key leak compromises every credential ever stored. Keep
  these in the DB with strong encryption and short rotation cycles.
- **Audit logs.** Append-only operational events; not a config concern.
- **Capture sessions, short-lived tokens, in-flight plan state.**
- **The encryption key reference for credentials** (path, KMS ARN, etc.).

These **can** go in git:

- Device registry (manifest YAML per device — model, host, tags, location)
- All operational configuration (the things in §3 "What configuration means")
- Shared profiles / templates
- Per-device notes and documentation

---

## 4. Artifact format

A device's configuration is not one file. It's a tree of facets, each of
which has a natural canonical form.

### Hybrid format: normalized YAML + raw dumps

For every facet, we keep two things in git:

1. **Normalized YAML** — clean, alphabetically-ordered, diff-friendly,
   editable by hand. This is what humans read and PRs review.
2. **Raw API response** — the unmodified VAPIX response, preserved as the
   ultimate source of truth. Used for restore (replay) and as a safety
   net if normalization is lossy.

The normalized form is generated *from* the raw form. The reverse direction
is also possible (edit YAML, regenerate request), but raw is authoritative
when they disagree.

This dual-form approach trades some redundancy for two big wins:

- **Diffs are clean.** Raw `param.cgi` dumps are line-noise. YAML is not.
- **Restore is faithful.** Replaying the raw response handles edge cases
  (encoding quirks, unknown parameters) that normalized YAML might drop.

### Stable serialization rules

For diffs to be useful, serialization must be deterministic:

- Keys sorted alphabetically (always)
- No timestamps in committed files (timestamps go in commit metadata)
- No volatile fields (`uptime`, `cpu_load`, `temperature`)
- Whitespace normalized
- Floating-point precision pinned
- Empty collections written explicitly (`users: []`, not omitted)

A snapshot taken twice from an unchanged device must produce a byte-identical
commit, or the diff layer is useless.

---

## 5. Repository structure

```
axis-experience-center-configs/
├── README.md
├── manifest.yaml                        # fleet roster, top-level metadata
├── fleet/
│   ├── camera-lobby-01/
│   │   ├── config/                      # normalized, human-friendly
│   │   │   ├── image.yaml
│   │   │   ├── network.yaml
│   │   │   ├── time.yaml
│   │   │   ├── stream-profiles.yaml
│   │   │   ├── users.yaml               # usernames + roles, NO passwords
│   │   │   ├── events.yaml
│   │   │   ├── view-areas.yaml
│   │   │   ├── privacy-masks.yaml
│   │   │   └── aoa/
│   │   │       └── scenarios.yaml
│   │   ├── raw/                         # original API responses
│   │   │   ├── param-cgi-dump.txt
│   │   │   ├── api-discovery.json
│   │   │   ├── stream-profiles.json
│   │   │   └── ...
│   │   ├── artifacts/                   # binary or near-binary
│   │   │   ├── certificates/            # public certs only
│   │   │   ├── installed-acaps.yaml
│   │   │   ├── audio-clips/             # for speakers/intercoms
│   │   │   └── photos/                  # physical installation
│   │   ├── docs/                        # per-device extras
│   │   │   ├── notes.md                 # free-form
│   │   │   ├── calibration.yaml         # mount, angle, focus
│   │   │   ├── integration.yaml         # which systems use this device
│   │   │   └── demo-scripts.md          # how to demo this device
│   │   └── device.yaml                  # model, firmware, location, tags
│   ├── camera-lobby-02/
│   ├── a1601-front-entrance/            # access controller
│   └── ...
├── profiles/                            # shared, reusable baselines
│   ├── lobby-camera-baseline/           # literal copy on fork
│   ├── conference-room-baseline/
│   └── demo-presentation-mode/
├── topology/                            # fleet-wide artifacts
│   ├── network-diagram.md
│   ├── floor-plan.png
│   └── integrations.yaml                # which devices feed which systems
├── schemas/                             # JSON schemas for CI validation
│   └── ...
└── .github/
    ├── workflows/
    │   ├── validate-config.yaml
    │   └── nightly-snapshot.yaml
    ├── CODEOWNERS
    └── pull_request_template.md
```

Notes on structure:

- **One device per directory.** Makes branching, forking, and `git mv`
  (when a device is replaced) all natural.
- **`config/` separate from `raw/`.** Reviewers look at `config/`; restore
  uses `raw/`.
- **`profiles/` for shared baselines.** A new lobby camera starts as a copy
  of `profiles/lobby-camera-baseline/`. Diffs to the profile show device-specific
  drift.
- **`.github/` for CI.** Validate every PR before it can be merged or applied.

---

## 6. ADMZ integration

This feature is a new top-level capability in ADMZ, alongside the catalog,
plan engine, and discovery. It reuses what's already there.

### New module: `admz/snapshot/`

```
admz/snapshot/
├── __init__.py
├── models.py            # Snapshot, Facet, DriftReport dataclasses
├── engine.py            # orchestrates snapshot per device
├── facets/              # one adapter per facet (pluggable, see below)
│   ├── __init__.py      # facet registry
│   ├── base.py          # FacetAdapter ABC
│   ├── image.py
│   ├── network.py
│   ├── stream_profiles.py
│   ├── users.py
│   ├── access_schedules.py
│   ├── sip.py
│   └── ...              # add new facets here
├── restore.py           # YAML → execution plan
├── drift.py             # detects device vs git divergence
├── git_repo.py          # thin git wrapper (clone, commit, push, diff)
└── scheduler.py         # cron-like scheduled snapshots
```

### Facets are pluggable

A facet adapter is the bridge between a device's API and the git-stored
YAML. Each adapter is independent and registered at startup. The adapter
declares:

- **Applies to**: which device types / API families / firmware ranges
- **Read operation**: which catalog operation(s) populate it
- **Write operations**: how to apply the facet during restore
- **Order hints**: "apply network last", "apply firmware first"
- **Serialize**: raw API response → canonical YAML
- **Deserialize**: YAML → parameters for the write operation

```python
class FacetAdapter(ABC):
    name: str                       # e.g. "stream_profiles"
    applies_to: list[DeviceCriteria]  # model patterns, families
    read_ops: list[str]             # catalog operation IDs
    write_ops: list[str]
    restore_order: int              # smaller = apply earlier

    def serialize(self, raw_responses: dict) -> dict: ...
    def deserialize(self, yaml_doc: dict) -> list[dict]: ...
```

This means:

- **New device type** → add new adapters, nothing else changes
- **New firmware adds a parameter** → extend the existing adapter, or add
  a new adapter that targets the firmware range
- **Unknown fields** → adapters fall back to passing raw data through
  in a generic `extra.yaml` so nothing is lost
- **Facets are discoverable** → at snapshot time, the engine asks every
  registered adapter "do you apply to this device?" and runs the ones
  that say yes. No global facet list to maintain.

This is the same pluggable pattern as the catalog's executor families
(VAPIX, ACS, AOA), just one layer down.

### What each piece does

**`engine.py` — snapshot orchestration**

For one device:

1. Look up device + credentials from ADMZ registry
2. Run a sequence of read-only operations from the catalog (the "snapshot
   plan" — see below)
3. Pass each raw response to the serializer
4. Write `config/`, `raw/`, `device.yaml` for the device
5. Detect changes vs current HEAD
6. Commit + push (if anything changed)

**`facets/` — normalization (pluggable, see above)**

Per-facet adapters that take a raw API response and produce normalized
YAML. The set of adapters is open-ended; the engine discovers which ones
apply at runtime. See "Facets are pluggable" above.

**`restore.py` — generates an execution plan**

Reads YAML or raw from git, builds a multi-step plan via the existing
plan engine, returns it for approval. Order matters: e.g., network settings
last (or device disconnects), users carefully (don't lock yourself out),
firmware first if it changes.

**`drift.py` — device vs git comparison**

Takes a snapshot *without committing*, diffs against HEAD, returns a
structured report: facet, parameter, current value, expected value.
The MCP tool surface returns this as a readable summary.

**`git_repo.py` — git wrapper**

Wraps a configured git remote. Clones lazily, keeps a working copy in
`$ADMZ_CONFIG_REPO_PATH`, commits with sensible messages, pushes.
Signed commits if a key is configured.

**`scheduler.py` — periodic snapshots**

Triggers `engine.snapshot(device_id)` on a schedule. Per-device or
per-tag policies. Reuses async, no separate daemon required.

### The "snapshot plan"

A snapshot is just a special read-only execution plan. It runs against
the catalog like any other plan, except:

- All steps are read-only (catalog `risk_level: read_only`)
- No approval needed (read-only ops never require it)
- Results are collected, not just acknowledged
- The "executor" routes results to the serializer instead of returning
  them to the LLM

This means snapshots leverage the existing plan engine — parallelism,
failure policy, retries, all free. A fleet snapshot of 100 devices is
just a 100-device plan with no dependencies between devices.

### Restore as a plan

Restore is symmetric. Read YAML/raw from git, build a write plan, hand
to the existing plan engine. The same two-gate approval applies
(semantic + mechanical risk check). Dangerous operations in a restore
(factory reset, firmware change) get blocked exactly like in any other
plan.

### New MCP tools

Building on the existing catalog tools:

- `snapshot_device(device_id)` — snapshot one device, commit to git
- `snapshot_fleet(filter?)` — bulk snapshot, optionally filtered by tag
- `restore_device(device_id, ref)` — propose a plan to restore device to
  a given git ref (sha, tag, branch)
- `diff_device(device_id, ref_a, ref_b?)` — human-readable diff between
  two refs (default `ref_b` = current device state)
- `check_drift(device_id?)` — report devices that diverge from git HEAD
- `fork_device_config(source_device, target_device, overrides?)` — copy
  one device's config to another, with field overrides (host, etc.)
- `apply_profile(device_id, profile_name)` — propose a plan that brings
  a device in line with a shared profile

### DB-cache contract

The DB stores a **cached view** of git's state:

- `device_config_cache` table: `(device_id, facet, value_json, git_sha)`
- Rebuilt on every commit to the repo
- Indexed for queries ("find all devices with H.264 main profile")
- Never edited directly — only by `git_repo.commit_hook()` or full rebuild

Queries hit the cache. Edits go through git → trigger rebuild → cache
updates. A consistency check job verifies cache == git on a schedule.

The credential store in the DB is **completely separate** from the cache.
The two should not share tables or transactions.

---

## 7. Workflows

### A. Daily fleet snapshot (scheduled)

1. Scheduler fires at 02:00
2. Engine queues a fleet snapshot plan for every device with tag `auto-snapshot`
3. Plan executes in parallel across devices
4. For each device: read facets, normalize, write files
5. `git add -A` in repo, commit only if anything changed:
   `"Nightly snapshot — 2026-05-15"`
6. Push to remote
7. Drift summary emitted (which devices changed since yesterday)

### B. Pre-customer-visit baseline

1. Operator: `tag-snapshot --tag pre-customer-visit-acme-corp`
2. Engine snapshots all `experience-center` devices
3. Commit, then `git tag pre-customer-visit-acme-corp HEAD`
4. After visit: `restore-tag pre-customer-visit-acme-corp` reverts everything

### C. "Make camera-conference-03 like camera-conference-01"

1. Operator: `fork-config camera-conference-01 → camera-conference-03`
2. New directory `fleet/camera-conference-03/` is created from `-01/`
3. Device-specific fields (host, hostname, IP) are overridden
4. Operator opens a PR on the config repo
5. Reviewer approves
6. PR merge triggers `apply` for the new device

### D. Drift detection

1. Hourly drift check runs against tagged devices
2. For each device: live snapshot (in memory only), diff vs git HEAD
3. If diff is non-empty, report:
   - `camera-lobby-02: stream-profiles.yaml differs (someone changed bitrate)`
4. Operator decides: accept drift (snapshot + commit) or revert (restore)

### E. Demo branch

1. Operator branches the config repo: `git checkout -b demo/customer-x`
2. Edits configs in the branch as needed
3. Applies the branch to devices: `apply-branch demo/customer-x`
4. After demo: `apply-branch main` reverts to baseline
5. Optionally merges valuable demo changes back to main via PR

---

## 8. CI on the config repo

The config repo can use GitHub Actions to validate every PR:

- **Schema validation** — does every facet match its JSON schema?
- **Cross-reference checks** — do stream profile references in `events.yaml`
  actually exist in `stream-profiles.yaml`?
- **Compliance** — every device has NTP configured? Min firmware version?
  Required tags present?
- **Secret-scanning** — fail if any facet looks like it contains a credential
- **Dry-run** — generate the restore plan and check for forbidden operations
  (no factory resets without explicit approval label)

CI failures block the merge. The PR can't be applied to devices until
CI is green.

---

## 9. Risks and open questions

**Secrets leaking into snapshots.** `param.cgi` dumps may include things
that look like configuration but are actually sensitive (private keys,
HMAC seeds, SIP credentials). The serializer needs an explicit allowlist
or strong denylist. Default to denying unknown sensitive-looking fields.

**Certificates and private keys.** Public certs can go in git. Private
keys cannot — those go in the DB credential store, referenced by ID
from the cert YAML.

**Repo bloat.** 100 devices × daily snapshots × multiple years = a lot of
commits. Probably fine for git, but: do we want squash-on-merge for
nightly snapshots? Shallow clones for the working copy? Open question.

**Restore order.** Network changes can disconnect the device. Firmware
upgrades reboot it. Users can lock you out. The restore plan needs
sequencing rules per facet, with the dangerous facets last (and
network changes via a "safe net" mechanism, like rollback-on-disconnect).

**Live edit detection.** Someone logging in to the device's web UI and
changing things won't trigger anything in ADMZ. Drift detection catches
it after the fact, but real-time would require either polling or webhook
support on the device (which Axis devices have, partially).

**Multi-tenancy.** If we have multiple Experience Centers (or multiple
customers using ADMZ this way), do they share one repo? Probably not —
one repo per "fleet" (= one ADMZ instance) is cleaner. Profiles can be
copied across repos manually for now.

**Who owns the repo?** ADMZ is a tool; the repo is data. The repo
should belong to the Experience Center org, not be embedded in ADMZ.
ADMZ is configured to push to it (URL + creds), and the repo's
`CODEOWNERS` controls who can approve PRs.

**Schema drift across firmware.** A new firmware version adds parameters.
The serializer needs to handle unknown fields gracefully — pass them
through in `raw/` and add them to YAML in a generic section. Adapters
can catch up later.

---

## 10. Phased roadmap

Each phase is independently useful. Don't build the whole thing before
shipping something.

### Phase 1: Manual snapshot of one device → committed to local git

- `admz/snapshot/engine.py` skeleton
- Pluggable facet adapter framework
- Initial adapters: a few high-value facets across **at least two device
  types** (e.g. camera image + network, access controller schedules) to
  prove the architecture is genuinely device-type-agnostic
- `git_repo.py` with local-only mode (no remote yet)
- "Pass-through unknown fields to `extra.yaml`" so devices with no
  adapter still get a useful snapshot
- MCP tool: `snapshot_device(device_id)`
- Output: a working repo with one device's config (any device type)

### Phase 2: Restore + diff

- `restore.py` builds a plan from raw responses
- MCP tools: `restore_device`, `diff_device`
- Two-gate approval already works via plan engine
- Test loop: snapshot → modify → restore → verify identity

### Phase 3: Fleet snapshot + remote repo + CI

- Parallel fleet snapshot via plan engine
- Configure remote (GitHub) and push
- GitHub Actions for schema validation
- MCP tool: `snapshot_fleet`

### Phase 4: Drift detection + scheduled snapshots

- `drift.py` and `scheduler.py`
- Nightly snapshots become a real workflow
- MCP tool: `check_drift`

### Phase 5: Forking + profiles + branches

- `fork_device_config`, `apply_profile`
- Branch-based demo workflows
- PR-driven configuration changes become the norm

### Phase 6: DB cache for queries

- `device_config_cache` table
- Auto-rebuild on commit
- Query MCP tools that hit the cache, not git

---

## 11. Where this overlaps with the existing project

This isn't a separate product — it leans hard on what's already in ADMZ:

| ADMZ piece | How snapshot/restore uses it |
|---|---|
| Device registry | Source of truth for device list, host, credentials |
| Catalog (CGI organization) | Defines *what* to read for each facet |
| Catalog (risk levels) | Restore plans inherit the two-gate safety |
| Plan engine | Snapshot = read plan, restore = write plan |
| Plan engine (parallel) | Fleet snapshots in parallel come for free |
| VAPIX executor | Used for both reads and writes |
| Discovery | Optional: auto-add discovered devices to the repo |
| Out-of-band credential capture | New devices need creds before first snapshot |
| MCP tools (catalog-in-the-loop) | Add new tools for snapshot/restore/diff |

The only genuinely new things are: the serializer/restore layer, the git
adapter, the DB cache for queries, and the scheduler. Everything else is
reuse.

---

## 12. Resolved decisions

The following questions were resolved in review on 2026-05-15:

- **DB vs git as source of truth**: git wins. DB becomes a query cache.
- **Device scope**: all device types from the start (cameras, access
  controllers, intercoms, speakers, AXIS Camera Station, etc.). The
  architecture is device-type-agnostic via pluggable facets.
- **Repo scope**: one repo per Experience Center.
- **Secret redaction**: allowlist (only known-safe fields make it into
  serialized YAML; everything else stays in `raw/` with restricted
  access or is filtered entirely).
- **Commit signing**: not needed.
- **Branch-based demo workflows**: deferred. Tag + restore is enough
  for now; revisit later if the workflow proves valuable.
- **Profiles**: literal file copies. Templating may be needed for
  specific fields later but isn't built in from day one.
- **Facets must be open-ended**: settings vary widely, new products
  arrive constantly. The architecture should let new facets be added
  as adapters without changing the engine.
- **Beyond device config**: the repo also holds operator notes,
  installation photos, demo scripts, network diagrams, calibration
  data — anything per-device or per-fleet that's useful to version.

## 13. Still open

- What goes in the allowlist for each facet? (Done per-facet, as adapters
  are written; document the rules.)
- How to handle facets the device exposes but no adapter exists for —
  pass-through via `extra.yaml` is the default; what's the UX for
  surfacing "here's a facet we don't normalize yet"?
- Schema for `device.yaml` — needs to cover any Axis device, not just
  cameras.
- Restore-order rules: which facets must be applied first vs last for
  each device type? (Network last for everything, but the rest varies.)
- Whether to put `topology/` (floor plans, integration diagrams) in the
  same repo or a sibling repo.

---

*This is a working document. Edit freely.*
