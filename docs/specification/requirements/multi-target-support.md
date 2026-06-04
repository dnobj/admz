# Requirements: multi-target support (Tier 1–3 device and system types)

ADMZ's primary target is and will remain Axis access network devices — mostly
cameras, but also non-camera access devices (speakers, access controllers, I/O
modules, radar). This document captures the requirements for extending ADMZ
beyond that baseline to two additional target classes: **2N intercoms** and
**Axis Camera Station Pro (ACS Pro)**, and for the shared plumbing that makes
both possible.

See [ADR-0027](../decisions/0027-pluggable-control-families-and-config-collectors.md)
for the architectural decision that defines the `ConfigCollector` / `Actuator`
split and the three-tier model. See [extensibility.md](extensibility.md) for the
existing pluggable extension points these requirements build on.

Related background: [EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md](../../EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md)
§3 "Scope: all device types, not just cameras" articulates the original intent
that the facet architecture be device-type-agnostic.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

All requirements in this file are **📋 planned** unless marked otherwise.

---

## Functional requirements

### Foundation (Phase 0 — required by all tiers)

#### FR-MT-001 — Typed target taxonomy on device records 📋
Every device/target record in the registry carries:
- `device_type` (string enum): `camera`, `encoder`, `speaker`, `io-module`,
  `radar`, `intercom-2n`, `access-controller`, `vms-acs`. Discovery
  populates this for VAPIX devices today (`admz/discovery/models.py::DeviceType`);
  the persisted field on the registry record normalizes to the same vocabulary.
- `control_family` (string): the `ConfigCollector` / `Actuator` family key —
  `"vapix"`, `"twon"`, `"acs"`.
- `connection_method` (string): `"http"` (default), `"agent"`, `"sql"`, `"winrm"`.
  Non-HTTP methods are ACS-specific; all other targets default to `"http"`.

Migration: existing records backfill `device_type=camera`,
`control_family=vapix`, `connection_method=http` where these fields are absent.
The schema change is additive (nullable with defaults). See NFR-MT-001.

#### FR-MT-002 — Auto-routing by control_family 📋
The snapshot engine and plan engine resolve the correct `ConfigCollector` and
`Actuator` by reading `control_family` from the device record, rather than
accepting `family` as a caller-supplied parameter that defaults to `"vapix"`.
Callers (MCP tools, scheduler, REST API) that previously passed an explicit
`family` parameter are updated to omit it; the record is the authority.

#### FR-MT-003 — ConfigCollector pluggable interface 📋
`admz/snapshot/collector.py::ConfigCollector` declares:
- `family` property (string)
- `collect(target, credentials) -> Dict[str, Any]` — returns a `raw_responses`
  dict that the existing facet `serialize()` methods can consume unchanged.

`VapixConfigCollector` wraps the existing executor + `param.cgi:list` call,
preserving the current behavior. New families add new collector implementations.
The snapshot engine dispatches via a collector registry keyed by `family`.

#### FR-MT-004 — Parent-system relationship for VMS targets 📋
A target record may carry a nullable `parent_system_id` (FK to another target
record with `device_type=vms-acs`). This expresses the relationship between an
ACS-managed camera and the ACS server that manages it — important for
understanding which devices overlap between the ADMZ-managed fleet and the
ACS-managed fleet. This field is null for all non-VMS targets.

---

### Tier 1 — Non-camera VAPIX devices (speakers, access controllers, I/O, radar)

#### FR-MT-005 — Expanded VAPIX catalog coverage 📋
Additional catalog YAML operations under `catalog/vapix/` covering:
- Audio (network speakers): volume, equalizer, SIP config, scheduled playback,
  audio clip management.
- Access control (A-series controllers): schedules, door configurations, access
  rules, reader configurations, I/O port configurations.
- Radar: detection zone configuration, sensitivity profiles.

No architecture change. Work is content — new YAML files and facet adapters.
The D4200-VE strobe-siren integration already demonstrated end-to-end VAPIX for
a non-camera device and serves as the precedent pattern.

#### FR-MT-006 — Facet adapters for non-camera VAPIX device types 📋
New `FacetAdapter` subclasses with `DeviceCriteria` that scope them to the
relevant `device_type` values (e.g. `families=["vapix"]`,
`device_types=["speaker"]`). The existing facet registry and
`get_facets_for_device` dispatch already handle this — no engine change.

---

### Tier 2 — 2N intercoms

#### FR-MT-007 — 2N control family 📋
A `twon` family implemented as:
- `catalog/twon/rest/…` — YAML operation definitions for the 2N JSON HTTP API.
- `TwoNExecutor(BaseExecutor)` registered in the executor map (family `"twon"`).
- `TwoNConfigCollector(ConfigCollector)` — calls the 2N `/api/config` backup
  endpoint; the single-endpoint snapshot is simpler than VAPIX.
- `twon` facet adapters with `DeviceCriteria(families=["twon"],
  device_types=["intercom-2n"])`.

The `twon` family is implemented **before** ACS to prove the multi-family seam
works end-to-end with a real second protocol of moderate complexity.

#### FR-MT-008 — 2N discovery enrichment 📋
The HTTP probe discovery protocol (`admz/discovery/http_probe.py`) is extended
to identify 2N devices by their API fingerprint (e.g. `/api/system/info`
response shape) and set `device_type=intercom-2n`, `control_family=twon` when a
2N device is detected. Discovery sets `connection_method=http`.

---

### Tier 3 — Axis Camera Station Pro (VMS)

#### FR-MT-009 — Multiple ACS servers per site 📋
A single site may have **more than one ACS Pro server**. The data model must
support N ACS-server records per site from the start — a 1:1 assumption per
site is incorrect. ACS server records are site-scoped targets within the
Org → Site → Group hierarchy (see [hierarchy.md](hierarchy.md)). There is no
maximum enforced at the data layer; the UI and CLI should make it clear that
multiple servers are expected.

#### FR-MT-010 — ACS target record fields 📋
In addition to the standard `device_type=vms-acs`, `control_family=acs`,
`connection_method` (one of `agent`, `winrm`, `sql` — see FR-MT-012), ACS
records carry:
- `acs_version` (string, optional) — ACS Pro version string; used to select
  the appropriate collector adapter.
- `site_id` (FK) — the Site this ACS server belongs to (required; no ACS
  record can be site-less).

#### FR-MT-011 — ACS ConfigCollector (read-only phase first) 📋
`AcsConfigCollector(ConfigCollector)` collects ACS configuration and normalizes
it into the standard facet schema. The collector is implemented **read-only
first** — no write path — so that ACS config can be versioned, diffed, and
audited in git before any actuation is attempted.

The collector is a multi-source collector: it coordinates across database
queries, config file reads, and optionally the ACS Web API. The exact sources
and schema are determined by the discovery spike (FR-MT-013); this requirement
records the interface contract, not the implementation.

Output: a `raw_responses` dict consumed by ACS-specific facet adapters
(FR-MT-014), producing the same normalized YAML that the existing git /
diff / drift / restore pipeline expects.

#### FR-MT-012 — ACS connection method 📋
ADMZ must reach the Windows host running ACS Pro via one of:
- **`agent`** — a lightweight host-side agent process that executes queries
  locally and returns results to ADMZ.
- **`winrm`** — Windows Remote Management; ADMZ issues remote commands.
- **`sql`** — direct SQL connection to the ACS database instance.

The connection method is stored on the ACS target record (`connection_method`
field) and is selected per-deployment. The correct method is determined by the
discovery spike (FR-MT-013). All three are listed as options; at least one must
be supported for a viable implementation.

#### FR-MT-013 — ACS discovery spike (pre-condition) 📋
Before any ACS implementation work begins, a time-boxed spike must answer the
following. Note that the spike now covers **both** the config-read path
(FR-MT-011 / FR-MT-012, ADR-0027) and the **demo / activity tracking path**
([ADR-0028](../decisions/0028-demo-activity-tracking-shared-substrate.md)) —
both efforts consume the same ACS access layer, so the spike pays for both.

**Config sources (required for ADR-0027 / FR-MT-011 / FR-MT-012):**
1. Which database engine(s) does ACS Pro use? Where do instances live on the
   Windows host? Is the schema documented and stable across ACS Pro versions?
2. Which config files complement the database(s), and where are they located
   on the host?
3. What does the ACS Pro Web API expose for *configuration* (vs runtime state
   only)? Is there a supported config export/import endpoint?
4. Which connection method (agent / WinRM / SQL) is viable for ADMZ's
   deployment model and maintainable across ACS versions?

**Audit / security log sources (required for ADR-0028 — demo activity tracking):**
5. Where does ACS Pro persist its audit and security logs — database table,
   flat log files, or a dedicated events/log API? Is more than one source
   needed to capture the full activity picture?
6. Does ACS Pro support push / subscribe access to its audit or security log
   stream, or is polling the only viable access model? What is the practical
   polling granularity and lag?

Results of the spike are captured in a `LEARN-acs-config-sources.md` document
before any FR-MT-011 / FR-MT-012 implementation is planned. The learnings
document should cover both config-source findings and log-source findings, since
both the config-read and demo-tracking efforts depend on this same spike.
**Do not assert ACS internals as known fact until this spike is complete.**

#### FR-MT-014 — ACS facet adapters 📋
New `FacetAdapter` subclasses with `DeviceCriteria(families=["acs"])` covering
(at minimum, subject to spike findings):
- Managed camera roster
- Recording schedules and profiles
- Storage allocation
- User accounts and permission assignments
- Smart search / analytics configurations

The facet names and normalized shapes follow the existing facet conventions
(ADR-0013, ADR-0015). Passwords and private keys are never captured
(NFR-SNP-001, ADR-0014).

#### FR-MT-015 — ACS Actuator (write phase — after read phase is solid) 📋
`AcsActuator(BaseExecutor)` implements writes to ACS Pro. Work begins only
after FR-MT-011 is shipped, stable, and the ACS config sources are well
understood from operational experience.

Actuation constraints:
- All writes flow through the plans engine (ADR-0012) with multi-step
  dependency tracking and rollback.
- Two-gate approval (ADR-0005) applies; ACS operations are classified at
  `service-affecting` or `dangerous` risk level given the blast radius of
  a VMS-level change.
- The connection method used for writes matches the `connection_method` on
  the ACS target record.

#### FR-MT-016 — ACS-managed camera cross-reference 📋
Where a camera that ADMZ manages directly (as a VAPIX device) also appears
in an ACS server's managed camera roster, ADMZ records the relationship via
`parent_system_id` on the camera's device record (FR-MT-004). The UI and MCP
surface expose this link so operators can understand the full management picture.
ADMZ does not attempt to arbitrate conflicts between VAPIX-direct management
and ACS management; it records and surfaces them.

---

## Non-functional requirements

### NFR-MT-001 — Additive schema migration 📋
The `control_family`, `device_type`, `connection_method`, and
`parent_system_id` columns are added to the device record table as nullable
columns with safe defaults (`control_family="vapix"`,
`device_type="unknown"`, `connection_method="http"`, `parent_system_id=null`).
No existing column is dropped or retyped. Migration is forward-only and
idempotent, and is coordinated with the Org → Site → Group migration
([hierarchy.md](hierarchy.md) NFR-HIER-001).

### NFR-MT-002 — Non-VAPIX families do not break VAPIX behavior 📋
Adding `twon` and `acs` families must not change the behavior of existing VAPIX
targets. The `control_family` field defaults to `"vapix"` for all existing
records; the VAPIX collector and executor are unchanged.

### NFR-MT-003 — Credentials for non-VAPIX targets stored identically 📋
2N and ACS credentials use the same Fernet-encrypted registry storage as VAPIX
credentials. The credential type distinguishes them (e.g. `twon_basic`,
`acs_windows_account`), but the storage and retrieval interface is unchanged.
See [credential-storage.md](credential-storage.md).

### NFR-MT-004 — ACS config collection never stores credentials in git 📋
ACS facet adapters follow NFR-SNP-001: user account names and roles may be
captured; passwords, API tokens, and private keys must never appear in the git-
tracked snapshot. Windows service account names are treated as non-sensitive;
their passwords are not.

### NFR-MT-005 — Spike findings documented before ACS implementation 📋
No code for FR-MT-011 through FR-MT-015 is merged to the main branch until the
spike document (FR-MT-013) exists, has been reviewed, and any ACS-internal
claims in the implementation plan are traceable to spike findings rather than
assumptions.

---

## Known gaps / open questions

### KL-MT-001 — ACS schema stability unknown ⚠️📋
If the ACS Pro database schema changes across major versions, the
`AcsConfigCollector` may need per-version adapters. This risk is not yet
characterized and is a primary goal of the discovery spike (FR-MT-013).

### KL-MT-002 — 2N API surface not yet catalogued ⚠️📋
The 2N JSON HTTP API has not been comprehensively reviewed against the ADMZ
catalog format. The Tier 2 work must include a catalog authoring pass before
implementation. Likely starting point: `/api/config`, `/api/system/info`,
`/api/audio`, `/api/sip`.

### KL-MT-003 — No multi-family discovery protocol today ⚠️📋
The current seven discovery protocols (`admz/discovery/`) identify Axis VAPIX
devices. FR-MT-008 adds 2N fingerprinting to the HTTP probe, but a first-class
2N discovery protocol (e.g. mDNS service type used by 2N) may be worth a
separate protocol implementation. Deferred to the Tier 2 implementation spike.

### KL-MT-004 — ACS-managed camera overlap arbitration is unspecified ⚠️📋
FR-MT-016 records the cross-reference relationship but does not specify what
ADMZ does when a VAPIX snapshot and an ACS snapshot of the "same camera"
disagree. Conflict surfacing is the v1 approach; arbitration policy is
explicitly deferred.

---

## References

- ADR: [0027 — Pluggable control families and ConfigCollector / Actuator split](../decisions/0027-pluggable-control-families-and-config-collectors.md)
- Extension point contracts: [extensibility.md](extensibility.md) (FR-EXT-001…005)
- Hierarchy interaction: [hierarchy.md](hierarchy.md) (FR-HIER-002 Site entity, NFR-HIER-001 migration)
- Snapshot pipeline this plugs into: [snapshot-restore.md](snapshot-restore.md)
- Safety gates: ADR-0005, ADR-0006, ADR-0012
- Background: [EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md](../../EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md)
- Code seams: `admz/executor/base.py`, `admz/snapshot/engine.py`,
  `admz/snapshot/facets/base.py` (`DeviceCriteria.families`),
  `admz/discovery/models.py` (`DeviceType`)
