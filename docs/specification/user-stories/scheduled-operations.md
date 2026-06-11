# User stories: scheduled operations

Recurring, unattended actions ADMZ performs on a timer — without an
operator (or an LLM) initiating each run. Snapshots already work this
way; **configuration audits** want the same treatment, and the list of
useful periodic jobs only grows from there (certificate-expiry checks,
firmware-availability checks, credential-rotation reminders, repo
housekeeping).

## Terminology

A **scheduled job** is an operator-defined recurring action — a
`(job_type, interval, scope)` triple that ADMZ runs on a timer and
records the outcome of. Distinct from:

- **System background loops** (the `HealthMonitor` reachability poller,
  temp-credential cleanup, the MCP-pool idle reaper) — fixed-purpose
  singletons, not operator-defined, not per-job tunable. They stay as
  they are; this story is not about folding them in.
- **Just-in-time actions** — operator- or LLM-initiated, one-shot, on
  demand (e.g. asking the chatbot to "audit the lobby cameras now").
  See [drift-and-monitoring](drift-and-monitoring.md) US-DM-007.

## Design note: one scheduler, many job types 📋

Today `admz/snapshot/scheduler.py::SnapshotScheduler` runs **only**
snapshots — `_execute_schedule()` hardcodes `engine.snapshot_fleet(...)`,
and `SnapshotSchedule` carries only snapshot params. But the reusable
machinery is all there: interval parsing, JSON persistence
(`~/.admz/schedules.json`), per-job asyncio loops, `run_now`,
enable/disable, `next_run` tracking.

The recommended direction is to **generalize it into a single job
scheduler** rather than bolt on a parallel `DriftScheduler`:

- `ScheduledJob` carries `job_type` (`snapshot` | `drift_audit` | …)
  plus job-specific params and a `scope` (tag / device list / Org /
  Site / Group).
- A handler registry maps each `job_type` → an async handler
  (`snapshot` → `snapshot_fleet`, `drift_audit` → `check_fleet_drift`
  + persist results, …).
- `_execute_schedule()` dispatches by `job_type`; the loop,
  persistence, and management surface are reused unchanged.
- New periodic capabilities register a handler — no new scheduler per
  feature.

To be captured as an ADR (`decisions/00XX-unified-job-scheduler.md`).

## US-SCHED-001 — Operator defines a recurring job

**As an** operator, **I want to** tell ADMZ "do X every N" once and have
it run on that cadence unattended.

**Acceptance criteria:**
1. A job is created with a `job_type`, a human interval (`30m`, `2h`,
   `1d` — parsed by the existing `parse_interval`), a `scope`, and an
   optional description.
2. The job persists across restarts (today: `~/.admz/schedules.json`).
3. `next_run` is tracked and visible; the job fires on its interval and
   updates `last_run` / `last_result`.
4. Creating a job is itself **not** a scheduled action — it's an
   ordinary CRUD call (REST / MCP / web UI).

**Related requirements:** [scheduling](../requirements/scheduling.md).

## US-SCHED-002 — Many job types share one scheduler

**As an** ADMZ developer adding a new periodic capability, **I want to**
register a handler against the existing scheduler instead of writing a
new background-loop subsystem.

**Acceptance criteria:** 📋 (planned — see Design note).
1. `job_type` is an open set; `snapshot` and `drift_audit` ship first.
2. A handler is `async (job, components) -> result_summary`.
3. Unknown `job_type` on load is logged and skipped, never crashes the
   scheduler.
4. The four management operations (list / enable-disable / run-now /
   delete) work uniformly across all job types.

**Related requirements:** [scheduling](../requirements/scheduling.md),
[extensibility](../requirements/extensibility.md).

## US-SCHED-003 — Scheduled jobs run without an LLM

**As a** security-conscious operator, **I want** recurring jobs to
execute through ADMZ's own engines, not by spinning up an LLM
conversation on a timer.

**Acceptance criteria:**
1. A scheduled `drift_audit` calls `DriftDetector.check_fleet_drift`
   directly — no Gemini call, no token cost, no MCP subprocess.
2. Scheduled execution is attributed in the audit log to a synthetic
   `scheduler` principal (not `anonymous`, not a user), so the
   who-did-what trail distinguishes automated runs from operator runs.
3. The just-in-time path (operator asks the chatbot to audit *now*)
   still goes through the LLM/MCP surface — same engine underneath,
   different initiator.

**Related requirements:** [scheduling](../requirements/scheduling.md),
[security](../requirements/security.md).

## US-SCHED-004 — Manage schedules without editing files

**As an** operator, **I want to** list, enable, disable, run-now, and
delete scheduled jobs from the surfaces I already use.

**Acceptance criteria:**
1. CRUD over REST (`/api/schedules`), MCP (`*_snapshot_schedule` tools,
   generalized), and the web UI.
2. **Run-now** triggers an immediate execution independent of the
   interval (the existing `run_now` already does this for snapshots).
3. Disable pauses a job without deleting its definition or history.
4. Writes follow the post-CR-3 pattern: `require_authenticated_principal`
   + audit every mutation.

**Related requirements:** [scheduling](../requirements/scheduling.md),
[web-api](../requirements/web-api.md), [authentication](../requirements/authentication.md).

## US-SCHED-005 — Scheduled job outcomes are observable

**As an** operator, **I want to** see whether last night's jobs ran and
what they found, without tailing logs.

**Acceptance criteria:** 📋 (partial today).
1. Each job exposes `last_run`, `next_run`, and a `last_result` summary
   (snapshots already do this).
2. For `drift_audit`, the run records *which devices drifted* to a
   queryable store — closing the "no drift-history table" gap in
   [drift-and-monitoring](drift-and-monitoring.md).
3. The web UI shows a schedules dashboard: each job's cadence, last
   outcome, and a drill-in to the last run's detail.
4. (Future) per-job alerting hooks (webhook / email / syslog) so a
   "drift appeared" transition can notify the operator's stack.

**Related requirements:** [observability](../requirements/observability.md),
[scheduling](../requirements/scheduling.md).

## US-SCHED-006 — Hierarchy-scoped jobs

**As an** operator of a multi-Site deployment, **I want to** schedule a
job against a whole Org, Site, or Group — not just a tag.

**Acceptance criteria:** 📋 (depends on the Org/Site/Group hierarchy).
1. A job's `scope` accepts `org_id` / `site_id` alongside (ADR-0032: tags, not groups)
   the existing `tag_filter` / `device_ids`.
2. "Audit the Chicago AEC lobby every hour" resolves to the devices in
   that Group at run time (membership is dynamic — devices added to the
   Group later are included automatically).
3. A scheduled snapshot for a Site commits into that Site's Org repo
   (per the per-Org-repo hierarchy design), not a global one.

**Related requirements:** [scheduling](../requirements/scheduling.md);
hierarchy (see the Org/Site/Group requirements).

## US-SCHED-007 — Scheduled configuration audit (flagship job type)

**As an** enterprise fleet operator, **I want** ADMZ to audit my fleet's
configuration on a schedule and tell me what drifted — without me
remembering to check.

**Acceptance criteria:** 📋 (planned — the first new `job_type`).
1. `job_type="drift_audit"` runs `check_fleet_drift(scope)` on its
   interval.
2. Results persist (which devices drifted, which fields) to a queryable
   store; a clean run is recorded too (so "nothing drifted" is a
   positive signal, not silence).
3. Reuses the existing `drift_alerts` transition logic
   (`appeared` / `changed` / `cleared`) so the schedule emits *changes*,
   not the same standing drift every hour.
4. No LLM in the loop (US-SCHED-003).

**Related requirements:** [drift-detection](../requirements/drift-detection.md),
[scheduling](../requirements/scheduling.md).

## Known limitations

- 📋 **The scheduler is snapshot-only today.** Generalizing to
  arbitrary `job_type`s (this story) is not yet built; for now
  `drift_audit` and other periodic jobs must be scripted externally
  via cron + `python -m admz` / REST.
- 📋 **No schedules dashboard in the web UI.** Schedules are managed via
  REST/MCP; `list_schedules` returns them but there's no rendered view.
- ⚠️ **Scheduler runs in-process.** Jobs are asyncio tasks inside the
  ADMZ server process; if the process is down, schedules don't fire and
  there's no catch-up/backfill on restart (the next interval is computed
  fresh). Acceptable for a single long-running instance; a durable
  job-queue would be a larger future change.
- ⚠️ **`run_now` and the interval loop can race** on the same job (a
  known concurrency gap flagged in the reliability review) — a per-job
  lock is the fix.
