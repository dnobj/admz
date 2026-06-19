# ADR-0037 — Unify Schedules + Recovery into one "Tasks" model

**Status:** Accepted (2026-06-18)
**Supersedes the storage half of:** ADR-0026 (unified job scheduler) and the
trigger-based pending-action store added for needs_setup recovery.

## Context

ADMZ had two parallel "deferred automated work" subsystems that are the same
idea with different *when* clauses:

- **Schedules** (`admz/snapshot/scheduler.py`) — time-based, recurring
  (`job_type` ∈ snapshot/drift_audit/survey), stored in `~/.admz/schedules.json`,
  evaluated by the `SnapshotScheduler` interval loop, surfaced on the Schedules
  page.
- **Recovery / pending actions** (`admz/fleet/pending_actions.py`) —
  detection-based, one-shot (`trigger` = `on_needs_setup`), stored in the SQLite
  `pending_device_actions` table, evaluated by the health-monitor sweep, surfaced
  on the device-detail Recovery card.

Two stores, two evaluators, two UIs, two sets of MCP tools — for one concept.

## Decision

A **task** is one unit of deferred/automated work with a **trigger** that is
either a **schedule** (time-based, recurring) or a **detection** (event-based,
one-shot), plus an **action** and a **target**. All tasks live in one SQLite
`tasks` table (`admz/tasks/store.py`) and dispatch through one handler registry
(`admz/tasks/handlers.py`, keyed by `action_type`).

The two **evaluators stay separate** — the scheduler interval loop fires schedule
tasks; the health-monitor sweep fires detection tasks (you can't cheaply check a
clock from the sweep, or device-state from a timer) — but they read one store.

### Why SQLite, not JSON

The old `schedules.json` needed a merge-on-save + 30s reconcile-from-disk hack
(KL-SCH-006) so the web server and the chatbot's MCP subprocess didn't clobber
each other. A single SQLite table with WAL + atomic conditional `UPDATE` gives
cross-process safety for free — the same fire-once claim the pending store already
used. So the merge is a *net simplification*: that hack is deleted.

### Migration

`admz/tasks/migrate.py` runs once at startup: it imports `schedules.json` →
schedule tasks (then renames the file to `.migrated` as a backup) and
`pending_device_actions` rows → detection tasks (leaving the old table intact).
Idempotent (skips ids already present), non-destructive, dry-runnable against a
copy of the live DB.

### Back-compat

`SnapshotSchedule` + the `/api/schedules*` routes + `/api/devices/{id}/recovery|
pending|cancel` routes + the `create_snapshot_schedule…` / `queue_device_recovery…`
MCP tools all remain, delegating to the unified store. New surfaces: `/api/tasks*`
REST, the `list_tasks` MCP tool (one view of both kinds), the **Tasks** page
(`/tasks`; `/schedules` 307-redirects), and a "When" column that reads "every 6h"
for schedules vs "when factory-defaulted" for detections.

## Consequences

- One mental model + one place to see all automated work.
- The fragile schedules.json cross-process code is gone.
- The two evaluators remain (correct — different trigger domains).
- `await_device_recovery` (live "is it back yet?" polling) is unchanged — it's not
  a task.

## Out of scope

- Trigger kinds beyond schedule + the existing detections (cron expressions,
  webhooks) — the model leaves room; not built here.
- Auto-creating recovery tasks without operator approval (unchanged: detect +
  offer).
