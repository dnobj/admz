# Requirements: performance

Scaling thresholds, bounded fan-out, hot-path costs. What ADMZ does
when the fleet is small vs medium vs large.

## Target sizes

| Persona / scenario | Typical scale | What ADMZ optimizes for |
|---|---|---|
| Single operator / dev install | 1–10 devices | Zero-config, fast startup |
| Experience Center | 10–200 devices | Snapshot/restore round-trip <30 s |
| Small enterprise | 100–500 devices | Fleet snapshot + drift sweep <5 min |
| Large enterprise | 500–5,000 devices | Bounded concurrency, no FD exhaustion |
| Very large (10k+) | beyond design point | Out of scope for v1 |

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-PERF-001 — Bounded fleet-snapshot concurrency ✅ (Phase 3D)
`SnapshotEngine.snapshot_fleet` uses an asyncio semaphore to cap
in-flight device snapshots. Configurable via
`ADMZ_SNAPSHOT_FLEET_CONCURRENCY` (default 50). Prevents FD
exhaustion + device-side connection-limit issues at scale.

### FR-PERF-002 — Catalog cached after first load ✅
`CatalogLoader` caches `_cgi_cache`, `_operation_cache`,
`_index_cache` per-instance. Subsequent lookups are O(1) dict hits.
Cold-load takes ~50ms for the current ~250 operations on typical
hardware.

### FR-PERF-003 — Short-lived SQLite connections (no cross-thread issues) ✅ (Phase 3A)
Per-call connections (WAL mode) for the registry, capture store,
confirm store, fleet settings, audit log, API keys. Bounded memory,
no long-lived connection thread-safety risk.

### FR-PERF-004 — Two-phase discovery skips dead IPs ✅
Phase 2 enrichment (HTTP probe, SNMP) only runs against IPs phase 1
saw respond. A /16 with 20 live devices triggers 20 enrichment
requests, not 65,536.

### FR-PERF-005 — Plan engine parallelizes by device ✅
`PlanEngine._execute_fleet_parallel` runs per-device step sequences
concurrently when no cross-device dependencies exist. Each device
runs its own steps sequentially within its task.

## Non-functional requirements

### NFR-PERF-001 — Single-device snapshot completes in <5 s ✅
Typical: 6 facets × ~200ms HTTP round-trip = ~1.2 s + git commit
(~0.5 s) = sub-2 s for cameras on a LAN. Measured on the test fleet.

### NFR-PERF-002 — Fleet snapshot of 100 devices completes in <30 s ✅
With concurrency cap 50, two batches × ~2s per device = ~4 s + git
commit. Bound is network latency to the slowest device, not ADMZ.

### NFR-PERF-003 — MCP tool calls return in <500 ms for non-network ops ✅
Registry queries, catalog lookups, audit reads — all in-process SQLite
or YAML disk reads. Negligible compared to network-bound device
operations.

## Known limitations

### KL-PERF-001 — Discovery enrichment is unbounded ⚠️
The Phase 2 enrichment in `DiscoveryOrchestrator` fans out
unboundedly across phase-1 candidate IPs. Fine at 100-IP scale;
problematic at 10,000 IPs (large flat subnets). Mitigation: use
`--subnet` to constrain. A semaphore in discovery (matching Phase
3D's snapshot semaphore) is a small follow-up.

### KL-PERF-002 — Nickname lookup is O(N) ⚠️
`SQLiteDeviceRegistry.get_device_by_nickname` decodes every row's
JSON and compares. Linear scan over the device list. Fine at
thousands; painful at millions. Adding an index on a normalized
nickname column would be a 5-line schema migration; deferred until
someone hits the limit.

### KL-PERF-003 — API key auth is O(N) over active keys ⚠️
Each `Authorization: Bearer` request PBKDF2-verifies against every
active key until a match is found. At 600k iterations per check and
N active keys, request latency grows linearly with N. Sane at ~tens
of keys; painful at hundreds. Mitigation path: add an HMAC "lookup
hash" column for O(1) indexed lookup; deferred. See
[authentication.md](authentication.md) KL-AUTH-001.

### KL-PERF-004 — No connection-pool limits for executor ⚠️
`httpx.AsyncClient` is instantiated per `execute()` call with no
shared pool. Functionally correct, slightly wasteful on TCP handshake
costs. A long-lived shared pool would reduce per-operation latency
but adds lifecycle complexity (close on shutdown, retry on stale
pool entries). Deferred.

### KL-PERF-005 — `param.cgi` reads return ~thousands of keys ⚠️
A camera's full `param.cgi?action=list` response is dozens of KB.
Snapshot uses it; that's fine. But the LLM context cost of dumping
it to chat is high — the catalog operation has
`response.format: text` and the resolver doesn't pass the raw dump
into LLM context by default.

## References

- ADRs: [0017](../decisions/0017-two-phase-discovery.md) — two-phase discovery for performance
- Cross-cutting reqs: [reliability.md](reliability.md), [configuration.md](configuration.md)
- Code: `admz/snapshot/engine.py` (fleet semaphore), `admz/plans/engine.py` (fleet-parallel), `admz/discovery/orchestrator.py`
