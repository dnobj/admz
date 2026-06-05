# Axis API Atlas — Maintenance & Discovery Runbook

> **Purpose.** This document directs an **agent or human contributor with network
> access to Axis devices** to *discover, update, and verify* the Axis API Atlas —
> a ready-to-execute, semantically-indexed catalog of Axis device APIs plus a
> per-model / per-firmware capability matrix. It is intended to be an **ongoing,
> multi-contributor effort**: each contributor covers the device models and
> firmware versions they can reach, and contributions are additive and
> merge-friendly.
>
> This runbook currently lives in the ADMZ repo, where the Atlas originated. It
> is written to travel with the Atlas if/when it is extracted into a standalone
> repository (proposed name: **`axis-api-atlas`** — see ADR-0029).

---

## 1. What the Atlas is (three layers)

| Layer | Where | What it holds | How it's produced |
|---|---|---|---|
| **Executable catalog** | `catalog/<family>/{cgi,rest,ws}/…` | Per-operation specs: path, method, request-body template with `{param:type}`, response shape, `risk_level`, `requires.auth_level` | Hand-authored YAML; can be *seeded* deterministically from OpenAPI |
| **Semantic layer** | `admz/catalog/resolver.py` synonyms, `catalog/vapix/index/{by-task,by-risk}.yaml`, `catalog/knowledge/**` | Intent→operation mapping, tags, device-class hints | Reasoning (LLM-assisted + human review) |
| **Capability matrix** | `catalog/capabilities/models/<model>.yaml` + `_api_id_map.yaml` | `(model, firmware) → {api_id: version}` + `apis_detail` (legacy + DCA/REST, state, OpenAPI link) | **Auto-discovered** from live devices via `tools/refresh_capabilities.py` |

A contributor with a device they can reach **always** updates the capability
matrix (mechanical, read-only). They **optionally** extend the executable +
semantic layers when discovery surfaces an API the catalog doesn't yet cover.

---

## 2. Prerequisites

- Network reachability to one or more Axis devices (IP/hostname).
- Valid device credentials (operator/admin). **Credentials are NEVER committed.**
- The repo + a Python env with `httpx` and `pyyaml` (ADMZ's `.venv` has both).
- Know each device's intended **model** and **firmware** (the tool reads these
  from the device, but you use them to sanity-check coverage).

---

## 3. The discovery loop (run per device)

### Step 1 — Refresh the capability matrix (mechanical, read-only, always do this)

```
# Inside ADMZ (resolves host + credentials from the registry):
python tools/refresh_capabilities.py --device-id <DEVICE_ID>

# Standalone (explicit host + credentials):
python tools/refresh_capabilities.py --host 192.168.1.220 --user root --password '<pw>'

# Preview without writing:
python tools/refresh_capabilities.py --host … --user … --password … --dry-run
```

This queries **both** discovery mechanisms and writes a firmware-stamped snapshot
to `catalog/capabilities/models/<model>.yaml`:

- **Legacy** `POST /axis-cgi/apidiscovery.cgi` `getApiList` — CGI / JSON-RPC APIs.
- **DCA** `GET /config/discover/apis` — the RESTful APIs incl. **beta** (AXIS OS
  ≥ 12.3). This is the one that surfaces newer/beta APIs (e.g. `siren-and-light`
  `v2beta`) that the legacy mechanism omits.

It is **idempotent**: re-running for the same `(model, firmware)` replaces that
snapshot; a new firmware appends a new snapshot (building the matrix over time).
It is **read-only** — only discovery GET/list calls, never a state change.

### Step 2 — Detect coverage gaps

Compare what the device reports against what the executable catalog already
covers. A gap is any **api_id (or version/state)** present in the new snapshot's
`apis_detail` that has **no corresponding operations** under `catalog/<family>/…`.
Pay special attention to:
- **DCA/REST APIs** (`apis_detail.<id>.dca`) — these are fully OpenAPI-described
  and may not be in the catalog at all yet.
- **New major versions / beta** of an API the catalog has only at an older version
  (e.g. catalog has `siren_and_light.cgi` 1.0; device also exposes REST `v2beta`).

### Step 3 — Seed executable catalog entries for gaps (deterministic first)

For a DCA/REST API gap, pull its OpenAPI spec and draft operations deterministically:

```
GET /config/discover/apis/<api_id>/v<major>/openapi.json
```

From the spec, each `path` + `method` + parameter schema maps directly to a draft
catalog operation (path, method, `{param:type}` template, response shape). Emit
these as **draft YAML** — do not hand-wave the request shape; copy it from the spec.
Set a **safe-default risk**: `GET`→`read-only`; `POST/PUT/PATCH`→`service-affecting`
(pending review); `DELETE` or paths containing `reboot|reset|factory|restore|firmware`
→ `dangerous`. **Never** default an unclassified write to `normal`.

### Step 4 — Enrich (reasoning: LLM-assisted, human-reviewed)

The deterministic draft is *callable* but not yet *findable or safety-classified*.
Add, with human review:
- **Intent synonyms / `by-task` entries** so natural-language requests resolve to
  the operation (this is where discoverability bugs live — see the siren/`streamstatus`
  history).
- **Confirmed `risk_level`** (upgrade/downgrade the safe default with judgment).
- **`params_doc` + `notes`**: required fields, array-vs-scalar gotchas, "call
  getCapabilities first", mutually-exclusive forms, etc.
- **Knowledge hints** (`catalog/knowledge/**`) for device-class behavior, attributed
  to a **capability predicate** (functionClass + min firmware) or series/product-line —
  NOT a single model.

### Step 5 — Verify

- **Idempotency:** re-run Step 1 — it should produce no diff churn.
- **Executability (read-only only):** spot-check that a few newly-cataloged
  **read-only** operations actually return data against the live device.
  **Do NOT run service-affecting or dangerous operations during verification
  without explicit human approval.**
- **Per-device value limits:** remember the API's *presence* generalizes by
  (firmware + capability), but its *valid values* (colors, intensities, patterns,
  ranges) are device-specific — confirm those via the API's own `getCapabilities`,
  never assume from another model.

### Step 6 — Commit & PR

- One model file per change where possible; keys are sorted for clean diffs.
- Commit message: `caps: <MODEL> @ <FIRMWARE> — <what changed>` (e.g.
  `caps: C1110-E @ 12.9.57 — add DCA snapshot; siren-and-light v2beta`).
- Snapshots are **additive**: never delete another contributor's model/firmware
  snapshot. Multiple contributors covering different models merge cleanly.

---

## 4. Safety rules (non-negotiable)

1. **Discovery is read-only.** The refresh tool and OpenAPI fetches only read.
2. **Never run service-affecting or dangerous operations** (reboot, restore,
   factory-reset, firmware, network/credential changes) during verification
   without explicit, per-operation human approval.
3. **Never commit credentials**, tokens, or device-specific secrets. Snapshots
   record `device_id`/serial for provenance — that is acceptable; passwords are not.
4. **Respect the device.** Discovery is a handful of GETs; don't hammer a device
   or a fleet in tight loops.
5. **Beta APIs are beta.** Record them (state: `beta`), but flag that Axis can
   change them; prefer the documented/`official` API for the executable catalog
   when one exists, and note the alternative.

---

## 5. Coverage: how to know what's missing

The Atlas is only as broad as the devices contributors have scanned. To reason
about gaps:

- **Models with no file:** any Axis model you can reach that has no
  `catalog/capabilities/models/<model>.yaml`.
- **Firmware gaps:** a model file whose `snapshots` don't include a firmware you
  can now reach (APIs/versions change across firmware — capture each).
- **Discovered-but-not-cataloged APIs:** entries in a snapshot's `apis_detail`
  with no operations under `catalog/<family>/…` (especially DCA/REST + beta).
- **Stale legacy-only snapshots:** snapshots captured before DCA discovery existed
  will lack `apis_detail`/REST/beta entries — re-run Step 1 to enrich them.

A good periodic contribution is simply: "I have model X on firmware Y — here's its
refreshed snapshot," even with no catalog changes. The matrix compounds in value
as coverage grows.

---

## 6. Snapshot schema (reference)

```yaml
model: C1110-E
series: c11
snapshots:
  - firmware: 12.9.57
    discovered: '2026-06-05'
    device_id: B8A44FB0BDA1        # provenance only; never a secret
    api_count: 72
    apis:                          # back-compat flat map: id -> version (legacy preferred)
      siren-and-light: '1.0'
      findmydevice: '1.1'
      ...
    apis_detail:                   # full picture per API + source
      siren-and-light:
        legacy: { version: '1.0', status: official }     # apidiscovery.cgi
        dca:                                              # /config/discover (REST)
          major: v2
          version: 2.0.0-beta.15
          state: beta
          rest_api: /config/rest/siren-and-light/v2beta
          openapi: /config/discover/apis/siren-and-light/v2/openapi.json
```

`apis` is consumed by the existing capability resolver (don't drop it). `apis_detail`
is the richer source of truth and is safe to extend — consumers ignore unknown keys.

---

## 7. Definition of done (per device, per session)

- [ ] `capabilities/models/<model>.yaml` has a snapshot for the device's current firmware.
- [ ] Re-running discovery yields no diff (idempotent).
- [ ] Any newly-discovered DCA/REST/beta API is at least recorded in `apis_detail`.
- [ ] Catalog gaps either drafted (deterministic) + flagged for enrichment, or logged as a known gap.
- [ ] No credentials committed; commit message names model + firmware.
