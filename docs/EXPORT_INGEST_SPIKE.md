# Spike: the native "export device settings" endpoint — one-call config capture?

**Status: ✅ ENDPOINT FOUND & VALIDATED (2026-06-22, read-only probes on Q3538-SLVE, AXIS OS
12.10.68). Recommendation: DON'T adopt as the capture path (yet) — keep per-facet reads; the
aggregate export is a great future *cross-check* source.**

## What we found

The AXIS OS web UI's "export device settings" file (sections `param.v2`, `action-rules.v2`,
`event-schedules.v2`, `event-mqtt-bridge.v2`, `time.v2`) is exactly the **config-rest aggregate
export**:

| Endpoint (GET, read-only) | Returns |
|---|---|
| **`/config/rest/$export`** | ALL entities in one call — the export file's exact structure, keyed `<entity>.<version>` |
| `/config/rest/param/v2beta/$export` | the param tree as structured JSON (`param:exportParams`, already in the atlas) |
| `/config/rest/action-rules/v2beta/$export` | `{recipients, rules}` |
| `/config/rest/event-schedules/v2beta/$export` | `{schedules: [...]}` |
| `/config/rest/event-mqtt-bridge/v2beta/$export` | `{publication, subscription}` (entity also has importConfig) |
| `/config/rest/time/v2/$export` | `{timeZone: {dhcp, iana, posix}}` |

Auth: normal VAPIX admin (digest). No `device-settings` API exists (`/config/rest/device-settings/v1/$export` → 404).

## Why NOT adopt it as the snapshot capture path (v1)

1. **Coverage is narrower than ADMZ's capture.** The aggregate only covers config-rest entities.
   ADMZ additionally tracks: ACAP run-state (`applications-list.cgi`), users (`pwdgrp`), NTP
   (`ntp.cgi` — a JSON-RPC CGI, absent from the aggregate), and the full legacy param semantics
   our facet excludes/secret filters are tuned for.
2. **Secrets.** The native export includes values ADMZ deliberately redacts (observed in a real
   export: SNMP `V1ReadCommunity`/`V1WriteCommunity`, ACAP `AlarmAction*` fields). Ingesting it
   raw would re-open the leak the capture-time secret filter closed; filtering it means
   re-implementing per-entity knowledge — at which point per-facet reads are equivalent work.
3. **Shape mismatch.** `param.v2` is nested JSON with `*Collection` arrays, not the flat
   `key=value` tree the param facets, ignore rules, and targeted revert are built around.
   Adapting would touch every param facet for no capture-fidelity gain.
4. **Availability.** Config-rest `$export` needs AXIS OS 12-era firmware; per-facet reads degrade
   per-facet on older devices (facet simply absent), which is the behavior we want.

## Where it IS useful (future)

- **Config cross-check / completeness audit**: one call yields Axis's own opinion of "all
  settings" — diffing its entity list against our facet coverage flags surfaces we don't track
  yet (that's how event-schedules/MQTT/time were prioritized).
- **`$import` (per-entity)**: `event-mqtt-bridge` ships `importConfig`; if other entities grow
  `$import`, whole-entity restore could ride the same seam as `build_revert_ops`.
- **Fleet templating**: exporting a golden device's `/config/rest/$export` and importing entity
  sections on peers is a plausible future "apply profile" fast path (secrets caveat applies).

## Handling note

Treat exported files as **sensitive** (they carry community strings and app credential fields
verbatim). Don't commit them; the sample used for facet development lives outside the repo.
