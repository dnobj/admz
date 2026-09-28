# ADR-0073 — The MCP server is a tool server, not a runtime

**Status:** Accepted — 2026-09-28 (the owner's decision on #375) · **Shipped:** 2026-09-28, with this record
**Relates to:** [ADR-0037](0037-unified-tasks.md) (one task store; the scheduler loop and the health sweep evaluate it) · [ADR-0052](0052-advanced-capability-switches.md) (`runtime.no_scheduler` is an `internal` capability) · review-2026-06-10 H-1 (pool subprocesses stopped starting a scheduler) · GH #172 (standalone MCP kept its scheduler)

## Context

`python -m admz mcp` runs in two roles:

- **A pool subprocess.** The web service spawns one per principal for the chat and voice console, with `ADMZ_MCP_NO_SCHEDULER=1`.
- **Standalone.** An MCP client such as Claude Desktop launches it over stdio, and it lives as long as that client's session.

Since H-1 a pool subprocess starts no scheduler. A standalone one still did (GH #172 kept it on purpose), but it ran none of the rest of the web service's startup (#375):

- no legacy task-store migration and no task context;
- no health monitor, event ingest or ACS pollers;
- none of the store maintenance.

So its background work was half-wired: schedules migrated from an older install were never imported, and a deferred action that needed the task context would fail.

Worse, **the scheduler has no cross-process claim.** Each process runs one loop per task: it sleeps until `next_run`, runs the task, and only then writes the next time (`admz/snapshot/scheduler.py`, `_schedule_loop`). A standalone MCP beside the web service on the same data therefore fires every schedule twice.

Nothing on the owner's machine launches a standalone MCP: checked on 2026-09-28, no MCP client configuration references ADMZ. The production service runs the web app.

## Decision

**The web service is ADMZ's only runtime.** No MCP process, pool or standalone, starts the scheduler or any other background owner: the health monitor, event ingest, the ACS pollers, or store maintenance.

- **Tools keep using the shared stores.** A schedule created or changed through a tool is written to the task store, and the web service's scheduler picks it up: its reconcile loop adopts and drops tasks across processes.
- **`run_snapshot_schedule` still runs inline** in the MCP process, as any tool call does. So every MCP process installs the module task handlers (GH #172). Before this, a pool subprocess skipped that, and running a module action from chat failed with "no handler registered".
- **`ADMZ_MCP_NO_SCHEDULER` / `runtime.no_scheduler` stays, as the pool-subprocess marker.** The temporary-credential TTL ceiling reads it. Its name is historical.
- **The schedule tool's description, the startup log and the MCP docs say who runs schedules.**

## Consequences

- **An install running only `python -m admz mcp`, with no web service, runs no schedules, health sweeps or deferred actions.** That is now said, rather than being half-true. Running ADMZ that way on purpose would need the runtime extracted and a single-owner lock first, which is a new decision.
- **The rest of #375's list no longer applies to an MCP process.** The health monitor, ingest, pollers, maintenance, the capability boot audit and the backend close all belong to the runtime, and an MCP process is not one.

## Alternative considered

**Full runtime parity:** move the web service's startup into a shared `admz/runtime.py` and run it in standalone MCP too. The owner chose against it on 2026-09-28. It is the larger change, and beside the web service it would duplicate the health monitor, the event streams and the pollers on top of the scheduler. It would therefore need a single-owner lock as well, and nothing here runs ADMZ without the web service.
