# Overview

## Mission

**ADMZ — Axis Device Management Zone — is a configuration-as-code platform for fleets of Axis network devices, designed to be safely driven by both humans and LLM agents.**

It rests on four pillars:

1. **A device registry** with encrypted credential storage (SQLite default, Vault optional).
2. **A YAML-driven operation catalog** describing what each Axis device can do, organized by API endpoint, classified by risk.
3. **A safe execution engine** that turns catalog operations into authenticated HTTP calls, with two-gate approval for anything destructive.
4. **A git-backed configuration store** that snapshots device state, supports diff and restore, and treats device configuration as a versioned, branchable, reviewable asset.

The system exposes these pillars through two surfaces: an **MCP server** (the primary entry point, designed for LLM consumption) and a **FastAPI REST API + web UI** (the human entry point).

## Why this exists

Operating an Axis fleet — whether it's six demo cameras at an Experience Center, a thousand devices at a stadium, or a hundred mixed access-control and audio devices at a corporate campus — currently means:

- Logging into each device's web UI individually.
- Manually tracking which device runs which firmware, which configuration, which password.
- Re-configuring devices from memory or screenshots after a demo, customer visit, or change.
- Having no good way to diff two configurations, roll one back, or fork a known-good config as a baseline.
- Trusting individual operators to remember which operations are reversible and which are not.
- Having no defensible audit trail of what was changed when, and by whom.

ADMZ addresses all of this by providing programmatic, catalog-driven, auditable, LLM-safe management of those fleets — with safety gates baked into the operation model itself rather than bolted on as policy.

## Scope

### In scope

- Any Axis network device that speaks VAPIX or ONVIF: cameras (PTZ, fixed, thermal, body-worn), encoders, audio devices (network speakers, intercoms), access control devices, network switches, I/O modules, radar, AXIS Camera Station servers, body-worn cameras.
- Credential storage and rotation (manual; automated rotation is a planned capability).
- Network discovery on a local subnet (seven protocols: ARP, mDNS, SSDP, ONVIF, ping, HTTP probe, SNMP).
- Single-step and multi-step operations against devices via a curated catalog.
- Configuration snapshot, restore, diff, drift detection, scheduled snapshots, and branching.
- An MCP server tool surface that LLM agents can drive safely.
- A REST API + web UI mirroring the MCP surface for human operators.
- Firmware download from Axis public FTP and LTS upgrade-path computation.
- Extension points for new API families, new discovery protocols, new snapshot facets, and new registry backends.

### Explicit non-goals

ADMZ deliberately **does not**:

- **Replace VMS or video recording systems.** It manages device *configuration*, not video streams or stored video.
- **Manage ACAP application lifecycle directly.** Applications can be discovered and their configuration snapshotted, but installing/upgrading the ACAP runtime itself is out of scope (it may be integrated via the catalog later).
- **Federate multiple Experience Centers / fleets.** One ADMZ instance owns one fleet. Multi-fleet federation is out of scope.
- **Run its own scheduler daemon.** Schedules execute as asyncio tasks inside the MCP/API process.
- **Provide multi-tenant access control with per-user roles inside ADMZ itself.** Authentication-to-ADMZ is currently absent and is a known gap (see [requirements/security.md](requirements/security.md)).
- **Manage non-Axis devices.** The architecture is family-pluggable in principle (`BaseExecutor`), but no non-VAPIX executor exists or is planned.
- **Serve as a real-time monitoring or alerting platform.** Drift detection is poll-based; there is no continuous webhook/event-driven monitoring loop.

## Goals (in priority order)

Adapted from `docs/EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md` §2, which enumerates the git-shaped goals that drive the architecture:

1. **Diff** — see exactly what changed between two configurations, or two devices.
2. **History** — every change preserved, attributed, timestamped.
3. **Restore** — bring a device back to any previous configuration.
4. **Fork** — copy a working configuration to a new device as a starting point.
5. **Branch** — maintain parallel configurations (demo-A, demo-B, experimental).
6. **Pull request** — propose configuration changes, review, discuss, approve.
7. **Blame** — find who last touched a particular setting and why.
8. **CI validation** — block bad configurations before they're applied.
9. **Tags** — named snapshots ("pre-Q3-customer-visit", "fw-12-baseline").
10. **Cherry-pick** — apply one specific change across a fleet.

A design decision that conflicts with these goals must justify itself or lose. The architecture (catalog + executor + plans + snapshot + git repo) exists *to make these goals possible* for Axis device fleets.

## Constraints

- **Python 3.8+.** No 3.10+-only syntax in core paths.
- **Local-first.** ADMZ runs alongside the operator (laptop, on-premises server, container in the operator's network). It is not a hosted service.
- **One instance per fleet.** No clustering, no replication. The SQLite/Vault store and the config-repo together represent the fleet's state.
- **Both surfaces equivalent.** Anything an LLM can do via MCP, a human can do via the REST API + web UI. Conversely, anything that exists only in the web UI (e.g. setting the confirmation password) is deliberately not exposed to MCP.
- **Stable serialization.** Snapshots taken twice from an unchanged device must produce byte-identical commits, or the diff layer is useless.
- **Catalog is data, not code.** Adding a new VAPIX operation must be a YAML-only change. Adding a new device family must be a plugin-only change.

## Architecture at a glance

```
                    ┌─────────────────────────────┐
   entry points  →  │  MCP server / FastAPI app   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
   orchestrators →  │  PlanEngine   SnapshotEngine│
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼─────────────────────┐
              │                    │                     │
  primitives  ▼                    ▼                     ▼
       ┌─────────────┐      ┌──────────────┐      ┌────────────┐
       │ Executor    │      │   Catalog    │      │  GitRepo   │
       │ (per API    │      │  (loader +   │      │            │
       │  family)    │      │   resolver)  │      │            │
       └──────┬──────┘      └──────────────┘      └────────────┘
              │
              ▼
     ┌─────────────────┐
     │ DeviceRegistry  │ (backend: SQLite or Vault)
     └─────────────────┘
```

Lower layers never import from higher layers. The MCP server is the only place that wires the pieces together. The REST API does the same wiring (via `AppContext`) for the human surface.

See [requirements/extensibility.md](requirements/extensibility.md) for the four documented extension points.

## Document status conventions

Throughout the spec, items are tagged:

- ✅ **Implemented** — present and exercised.
- 🚧 **Partial** — present but with known limitations, called out where they apply.
- 📋 **Planned** — described in the spec but not yet built.
- ⚠️ **Known gap** — known divergence between spec and code, listed for tracking.

Where the spec and the code disagree silently, that's a bug in one or the other.
