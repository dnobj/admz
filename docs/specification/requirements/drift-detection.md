# Requirements: drift detection

Compare a device's live state against the configuration stored in
git. Surface field-level differences so operators can decide:
re-snapshot, restore, or investigate.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-DRF-001 — DriftReport is the unit of result ✅
`admz/snapshot/models.py::DriftReport`:
- `device_id`, `has_drift`
- `fields` — list of `DriftField` (facet, dotted path, expected,
  actual)
- `facets_checked`, `facets_drifted`, `timestamp`

Empty `fields` + `has_drift=False` means "in sync." Each
`DriftField` is a single point of disagreement, so a report with
20 changed values has 20 entries.

### FR-DRF-002 — Drift is measured against the baseline ✅
`admz/snapshot/drift.py::DriftDetector.check_drift(device_id,
baseline_sha=None)` reads the device's live state via the same facet
adapters that captured the snapshot (FR-SNP-002), and compares it
against the YAML at the device's **baseline commit** (`baseline_sha`
from the registry, ADR-0031) — NOT git HEAD. With no baseline set, the
report carries `no_baseline=True` ("nothing blessed to compare",
distinct from "in sync").

### FR-BAS-001 — Per-device baseline / observation pointers ✅
The `devices` row carries `baseline_sha` (the blessed baseline commit),
`latest_observed_sha`, and `last_observed_at`
(`DeviceRegistry.set_config_pointers`, SQLite-backed; the Vault backend
is stubbed per H-4 and callers degrade best-effort). Git stays the
source of truth for config bytes (ADR-0014); these are pointers + status
only. A one-time idempotent backfill (`components._backfill_baselines`)
pins existing config-bearing devices to HEAD.

### FR-BAS-002 — Snapshot blesses the baseline; restore replays it ✅
`snapshot_device`/`snapshot_fleet` set `baseline_sha = HEAD` after a
successful capture ("this state is good now"). `RestoreBuilder` and the
`restore_device` tool/route default to the device's `baseline_sha` (an
explicit ref still overrides) — so "revert the drift" is `restore_device`
with `ref` omitted. The accept path is `accept_baseline` (FR-BAS-004).

### FR-BAS-004 — Accept/promote a baseline ✅
`accept_baseline(device_id, commit_sha?)` (MCP) and
`POST /api/snapshot/accept-baseline` (REST, authenticated like restore)
re-point `baseline_sha` to a chosen commit — default: the device's
latest recorded observation. The target must hold committed config for
the device (`git_repo.list_facets_at`), else the call is rejected
immediately. The MCP tool is **widget-gated** (ADR-0034): it returns a
blocked envelope with a `confirm_token`; the re-pointing executes only
when the user approves `/confirm/{token}` (a url_only ACTION session).
Metadata-only: no device traffic, no git writes; audited.

### FR-BAS-003 — Audits record observations ✅
Every `check_drift` probes the device once and records what it observed
into the git config repo as an `Audit: <device_id>` commit
(commit-on-change — an unchanged device records nothing new; the commit
skips the auto-push so frequent audits don't churn the remote). The
observation advances `latest_observed_sha`/`last_observed_at` but NEVER
`baseline_sha`. Observations are recorded even for devices with no
baseline yet — they're promotable later. The drift diff then runs
observation-vs-baseline, and the report carries `observed_sha` plus the
alert transition (if any) so schedulers don't re-process the alert
store. Registry-managed pointer fields are excluded from the committed
`device.yaml` (they're DB state *about* the repo; writing them back
would defeat commit-on-change).

### FR-BAS-005 — Restore plans gate at the widget and skip non-writable keys ✅
Three properties, all verified live on the P3288 (AXIS OS 12):
- **Always gated**: every step `RestoreBuilder` emits declares
  `risk_level: "service-affecting"`, and `PlanEngine.create_plan` honors a
  step dict's declared risk as a **raise-only floor** over the catalog's —
  so `execute_gated_plan` blocks restore plans with the url_only confirm
  widget (ADR-0034). Without the floor, `param.cgi:update` (catalog-risk
  "normal") let a whole-config restore run ungated. The floor can never
  *lower* catalog risk (no self-degating by plan authors).
- **Restore-safe params only**: facet deserializers skip what the device
  can't or must not accept — masked secrets (`'******'`; writing the mask
  back would corrupt the real secret), `Volatile*` runtime keys, and
  per-facet `RESTORE_EXCLUDE` entries (read-only mirrors like `Time.NTP.*`,
  structural constants like `Image.I*.Source/Type`, live interface state
  like `Network.eth0.*`). Skipped keys stay **serialized** — drift on them
  is real, observable change — and surface as plan warnings so the operator
  knows what a restore cannot revert.
- **Chunked updates**: large `param.cgi:update` calls split into ~1500-byte
  steps so the GET query string stays under device URI limits (observed:
  HTTP 414 at ~344 image params).

### FR-DRF-003 — Field-level diffing via flatten ✅
Both stored and live facet outputs are flattened to dotted-key
strings (`network.dns.servers.0 = "8.8.8.8"`), which gives stable
per-field diffs even when nested. The flattening is in
`admz/snapshot/drift.py::_flatten`.

### FR-DRF-004 — Inspect arbitrary refs via the diff surface ✅
Drift compares only against the baseline. To ask "what changed since
last Tuesday?", use the diff surface (`GET /api/snapshot/diff`,
`git_repo.diff`/`log`), which accepts any git-resolvable name — a SHA,
a tag (`pre-firmware-upgrade`), or `HEAD@{2026-04-01}`.

### FR-DRF-005 — Fleet-wide drift sweep ✅
`check_fleet_drift(device_ids=None, tag_filter=None)` runs drift checks
across many devices concurrently — each compared against **its own**
baseline — bounded by the same fleet semaphore as snapshot (FR-SNP-004).
Returns a list of DriftReports; the caller filters to `has_drift=True`.

### FR-DRF-006 — Drift checks never modify the device ✅
`check_drift` issues only read operations against the device — it's
safe to schedule against the whole fleet hourly. (Since ADR-0031
slice 2 it DOES append observation commits to the git repo —
FR-BAS-003 — but never the baseline pointer.) Acting on the report —
restoring or accepting the new state — is an explicit follow-up.

### FR-DRF-007 — Per-facet skip when unstored ✅
If a facet has never been snapshotted (no file in git), it's
skipped, not flagged as drift. `facets_checked` counts only facets
with stored baselines. This lets operators roll out drift checks
incrementally as new facet adapters land.

### FR-DRF-008 — Drift exposed via MCP and REST ✅
Actual surface (corrected — earlier revisions cited a `/api/v2/...`
surface and `check_device_drift` tool that never shipped):
- MCP: `check_drift(device_id?, tag_filter?)` — one tool covers both
  single-device and fleet (omit `device_id` for a fleet sweep); plus
  `diff_device(device_id, ref_a, ref_b)` for historical snapshot-to-
  snapshot diffs.
- REST: `GET /api/snapshot/drift?device_id=&tag_filter=`,
  `GET /api/snapshot/diff/{device_id}?ref_a=&ref_b=`.

Both surface the DriftReport JSON; agents typically narrow the
result to `fields` matching a particular path before acting.

### FR-DRF-011 — Fleet drift glance + freshness stamp ✅
The roster surfaces show **last-known** drift, not a live probe (a
genuine check costs a per-device round-trip — too slow to run when a
roster of N devices loads). One shared helper,
`admz/snapshot/drift_status.py::drift_status_for(device_info, signature)`,
maps the `baseline_sha` pointer + the cached `drift_signatures` row to
`{state, count, checked_at}` (state ∈ `none|unchecked|in_sync|drifted`),
so the two views can never disagree:
- **Fleet** (`/devices`) reads `GET /api/fleet/drift` — a pure cache
  read sibling of `/api/fleet/health` (`{total, counts, devices[]}`) —
  client-side, painting a compact badge per device, an "as of …"
  freshness stamp from `checked_at`, the real **Drifted** stat, and a
  drift filter. This is the *glance* ("should I care?").
- **Configuration** (`/configuration`) renders the same badge + stamp
  alongside the config-governance columns (baseline presence, last
  snapshot) it alone shows — the *workbench* ("what changed, what do I
  do?"). The Fleet "Audit all" link is the glance→workbench handoff.

Both expose a **"Check drift"** button that runs the live
`GET /api/snapshot/drift` fleet sweep (which warms the signature cache
via `process_report`) and repaints — the on-demand path to "make it
current" without a background poller. Keeping the cache warm
automatically remains the opt-in `drift_audit` scheduler job (FR-DRF-009).

Earlier the Fleet drift column was a hardcoded `No baseline` placeholder
with a hardcoded `0` Drifted stat (never wired to any source); this
replaced both with the real cache read + freshness.

### FR-DRF-009 — Scheduled configuration audit 🚧
A recurring, unattended configuration audit — the operator-facing
framing of a scheduled fleet drift sweep. Rather than a bespoke drift
scheduler, it rides the unified job scheduler as `job_type="drift_audit"`
(see [scheduling](scheduling.md) FR-SCH-010/011, ADR-0026):
1. ✅ Runs `check_fleet_drift(scope)` on its interval — no LLM, no MCP
   subprocess (attributed to the `scheduler` principal, FR-SCH-013).
2. 📋 Persists per-device results (including clean runs, so "nothing
   drifted" is a recorded positive, not silence). Today only
   *transitions* are persisted (in `drift_alerts`); clean-run
   evidence is not yet recorded — deferred follow-up.
3. ✅ Reuses the `drift_alerts` transition logic (`appeared` / `changed` /
   `cleared`) so each run emits *changes*, not the standing drift set.
4. 📋 `scope` is hierarchy-aware (`org_id`/`site_id`; ADR-0032 — no group level) alongside
   `tag_filter` / `device_ids`. Today scope is `tag_filter` + `device_ids`
   only; hierarchy fields land with FR-SCH-012 when Org/Site/Group
   Slice 2 lands.

### FR-DRF-010 — Drift-alert history is queryable via API ✅
`DriftAlertStore.list_alerts(...)` already persists transitions
(KL-DRF-004) and is now surfaced via:
- MCP: `get_drift_alerts(device_id?, since?, transitions?, limit?)`
- REST: `GET /api/drift/alerts?device_id=&since=&transition=&limit=`
Both are read-only, anonymous-allowed + audited; `device_id` flows
through `validate_identifier` (CR-5); `transition` is validated
against the {appeared, changed, cleared} allow-list; `since`
accepts ISO-8601 or unix timestamps; `limit` caps at 1000.
Implemented in `admz/api/routes/drift.py` and
`admz.mcp.server._get_drift_alerts`. This is the read side of
US-SCHED-005 (observable outcomes).

### FR-DRF-012 — A facet reports `ok`, `skipped` or `failed` — never success-with-nothing 📋
Today a facet whose API read fails serialises `{}` and is recorded `success=True`. Under
[ADR-0063](../decisions/0063-capability-knowledge-is-local-first.md) `FacetResult.status ∈
{ok, skipped, failed}` (`success` ≡ `ok`): `skipped` when the local capability record says the
device lacks the API, `failed` when the read was attempted and did not succeed. `skipped` is a
settled state and never makes a snapshot `PARTIAL`.

### FR-DRF-013 — Drift enumerates baseline facets, and distinguishes absent from unverified 📋
The compare visits every facet in the **baseline**, not only those present in the live read. A
baseline facet that is now `skipped` is `facets_absent` — it **is** drift, reported honestly, and it
produces **no `DriftField`**, because the revert builder must never write to an API the device does
not have. A baseline facet that `failed` is `facets_unverified` — **not** drift. This closes the
latent defect where a transient API failure read every stored key as `<missing>` and reported the
whole facet drifted, and the one where an absent facet vanished from the compare entirely. The drift
signature includes `facets_absent` only when non-empty, so existing signatures do not all change on
deploy.

## Non-functional requirements

### NFR-DRF-001 — No side effects on the device ✅
Drift checks issue only the read operations that the facet
adapters use during snapshot. No state-changing call ever fires
from `check_drift`.

### NFR-DRF-002 — Normalized comparison is firmware-tolerant ✅
The compared values are the *normalized* facet outputs, not raw
VAPIX response strings. Whitespace differences, key ordering, and
representation quirks (e.g. `"true"` vs `"yes"`) are absorbed by
the facet adapter.

## Known limitations

### KL-DRF-001 — String-equality compare ⚠️
The diff treats every value as a string after flatten. Numeric
fields like `image.fps = 30` vs `30.0` would surface as drift.
None of the current facets emit ambiguous numerics, but this is a
latent issue if a new facet does.

### KL-DRF-002 — No "accept current state" shortcut ✅
Resolved by ADR-0031 slice 3: `accept_baseline` (FR-BAS-004) is the
one-call shortcut — it blesses the latest recorded observation (or an
explicit commit) as the baseline, as an explicit, audited event.
Running a fresh `snapshot_device` still works and does the same
re-pointing as a side effect.

### KL-DRF-003 — Drift sweep cost grows with fleet × facets ⚠️
A fleet of 500 devices with 6 facets each is ~3000 read calls per
sweep. The semaphore caps in-flight concurrency, but wall-clock
time still scales linearly. See KL-PERF-001.

### KL-DRF-004 — Transition alerting on top of pull-based checks ✅
Resolved in Phase 8. `admz/snapshot/drift_alerts.py` hooks into
every `DriftDetector.check_drift` call and compares the report
against the last-known drift signature for that device. Three
transitions are recorded:

  - `appeared` — device was in sync; drift fields appeared.
  - `changed` — drift set or values changed.
  - `cleared` — drift is gone.

The first observation for a device is the baseline — no alert.
Alerts persist to the `drift_alerts` SQLite table with timestamp,
device, transition, field counts, signature hash, and a one-line
summary. Operators query via `DriftAlertStore.list_alerts(since=…,
device_id=…, transitions=…, limit=…)`.

### KL-DRF-005 — Restore cannot revert everything drift can see ⚠️
By design, drift observes more than restore can write (FR-BAS-005):
- **Read-only mirrors** (e.g. `Time.NTP.Server` on AXIS OS — NTP config
  moved to `ntp.cgi`) drift visibly but can't be reverted via
  `param.cgi`; a future facet could map them to their JSON-API setters.
- **Live-only keys** (e.g. stream profiles an external VMS created after
  the baseline) show as drift, but restore only *writes* baseline keys —
  it never deletes extras. Accepting the observed state is the way to
  absorb them.
- **State-dependent params**: `Network.Resolver.NameServer*/Search` are
  writable on static-DNS devices but answer 401 under DHCP — the static
  exclude list skips them unconditionally, so static-DNS restores lose
  DNS settings (revisit if a fleet needs that).
The restore plan's warnings enumerate every skipped key per facet, so
none of this is silent. The protected-param exclude lists were verified
live on a P3288 (AXIS OS 12); other models may expose additional
protected params, which fail their chunk's step loudly at execution.

The check itself is still pull-based — drift sweeps via the
scheduler or operator-initiated checks feed the alert log
naturally. `clear_baseline(device_id)` lets an operator accept
the current state as the new baseline without manually editing
the DB.

A true push-based notifier (webhook, chat alert, Slack) is the
next layer up — not in Phase 8.

### KL-BAS-001 — Observation history is append-only ⚠️
Audit observations accumulate in the config repo forever (ADR-0031
slice 4 decision). Automated "thinning" of old observations was
deliberately **rejected**: every commit is an ancestor of HEAD, so
thinning means history rewriting — which would silently invalidate
pinned `baseline_sha` pointers and violate the maintenance module's
no-rewrite policy. Growth is bounded in practice by commit-on-change
(an unchanged device records nothing) plus pack-only `git gc`
(KL-SNP-004 tooling); `maintenance.commit_intent_stats` shows the
audit/snapshot/baseline commit mix. If a repo genuinely outgrows its
disk, compaction is a documented human-led operation (archive the
repo, re-init from current state, re-snapshot fresh baselines) —
never automatic.

## References

- ADRs: [0012](../decisions/0012-snapshot-on-plans.md), [0014](../decisions/0014-config-in-git-creds-in-db.md), [0015](../decisions/0015-pluggable-facets.md), [0026](../decisions/0026-unified-job-scheduler.md)
- User stories: [drift-and-monitoring](../user-stories/drift-and-monitoring.md), [scheduled-operations](../user-stories/scheduled-operations.md)
- Cross-cutting: [observability.md](observability.md), [performance.md](performance.md)
- Sibling: [snapshot-restore.md](snapshot-restore.md), [scheduling.md](scheduling.md)
- Code: `admz/snapshot/drift.py`, `admz/snapshot/drift_alerts.py`
