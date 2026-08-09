# ADR-0027: Pluggable control families and ConfigCollector / Actuator split

**Status:** Accepted (forward-looking / anticipatory — defines the seams for work not yet built).
**Date:** 2026-06-04.
**Relates to:** ADR-0015 (pluggable facets), ADR-0011 (pluggable backends), ADR-0017 (discovery protocols), [requirements/multi-target-support.md](../requirements/multi-target-support.md)

---

## Context

ADMZ was designed around a single control family: **VAPIX** — the HTTP API
shared by almost all Axis network devices. The executor, catalog, facets, and
snapshot engine all default to `family="vapix"`. The abstraction seams for
multiple families already exist and are used in production:

- `catalog/<family>/{cgi,rest,ws}/…` — the catalog loader and resolver accept
  a `family` parameter; `CatalogLoader` picks up any family directory
  automatically.
- `admz/executor/base.py::BaseExecutor` is an ABC with a `family` property;
  its docstring names `'acs'` as an example future family.
- `admz/snapshot/engine.py::SnapshotEngine` holds an `executors` dict and
  dispatches via `self.executors.get(family)`.
- `admz/snapshot/facets/base.py::DeviceCriteria` filters on `families`,
  `device_types`, `model_patterns`, and `min_firmware` — the matching logic
  reads `device_info.get("api_family", "vapix")`.

Two new target classes are now anticipated:

1. **2N intercoms** — an Axis-acquired product line with its own JSON HTTP API
   (`/api/…`). Structurally similar to VAPIX (HTTP, per-device, credential-based)
   but a different protocol with a unified `/api/config` backup/restore endpoint.

2. **Axis Camera Station Pro (ACS Pro)** — a Windows VMS whose configuration
   cannot be acquired by calling a single HTTP operation. Config is spread across
   SQL databases, config files, and a partial Web API. ACS Pro is a *system* that
   may contain N managed cameras, not a box; the flat "device = host + creds"
   record cannot express this. It also requires a different connection model
   (host-side agent, WinRM, or direct SQL connection) rather than anonymous HTTP
   CGI.

These two cases expose a structural assumption that was hidden when VAPIX was
the only family: **`VapixExecutor` quietly plays two roles** — it *acquires*
configuration (snapshot reads) and *actuates* changes (writes). For VAPIX those
happen through the same transport; for ACS they do not, and collapsing them
would create awkward or unsafe designs.

---

## Decision

### 1. Persist `control_family` and `device_type` on every target record

Today `family` is a parameter passed at call time, defaulting to `"vapix"`.
This is adequate when every device is VAPIX; it breaks down once a 2N device
must auto-route to a different executor, or an ACS server must route to a
collector that does not use the VAPIX executor at all.

A `control_family` field (string, e.g. `"vapix"`, `"twon"`, `"acs"`) and a
`device_type` field (typed taxonomy — see FR-MT-001 in
[multi-target-support.md](../requirements/multi-target-support.md)) are added
to every device/target record in the registry. The snapshot engine reads
`control_family` from the record rather than accepting `family` as a caller-
supplied parameter. The facet matching logic already reads `api_family` from
`device_info`; persisting it closes the gap.

### 2. Formalize two pluggable interfaces where today there is one

Alongside the existing `BaseExecutor` (which handles the *actuation* path):

**`ConfigCollector`** — "produce a normalized facet bundle for a target."

```python
class ConfigCollector(ABC):
    @property
    @abstractmethod
    def family(self) -> str: ...

    @abstractmethod
    async def collect(
        self,
        target: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Return a raw_responses dict suitable for facet serialization."""
```

The VAPIX implementation wraps the existing executor + `param.cgi:list`
call — no behavior change. The 2N implementation calls `/api/config`. The ACS
implementation is a **multi-source collector** that queries the relevant
database(s), reads config files, and optionally hits the Web API, then
normalizes all of it into the same raw_responses shape that existing facets
already consume. The git / diff / drift / restore pipeline sees no difference.

**`Actuator`** (the renamed / clarified role of `BaseExecutor`) — "apply a
change." The interface contract is unchanged; the name makes the distinction
explicit. For ACS, the actuator is a guarded operation routed through the
plans engine (multi-step + rollback, ADR-0012) and two-gate approval
(ADR-0005) — those gates matter *more* for a VMS than for a single camera,
not less.

Both interfaces follow the same pluggable-registry shape as executors
(ADR-0011), facets (ADR-0015), discovery protocols (ADR-0017), and job
handlers (ADR-0026). Knowing one is most of knowing the others.

### 3. Adopt a typed target taxonomy

The flat "device = box" model is extended with:

- **`device_type`** (enum): `camera | encoder | speaker | io-module | radar |
  intercom-2n | access-controller | vms-acs`. The discovery layer already
  populates a `DeviceType` enum for Axis VAPIX devices; 2N intercoms and ACS
  servers are added to the same taxonomy.
- **`control_family`** (string): the `ConfigCollector` / `Actuator` family
  key — `"vapix"`, `"twon"`, `"acs"`.
- **`connection_method`** (string): how the target is reached — `"http"` (most
  devices), `"agent"` (host-side agent process on the Windows server),
  `"sql"` (direct database connection), or `"winrm"`. Only ACS uses the
  non-HTTP methods.
- **`parent_system_id`** (nullable FK): for ACS-managed cameras that overlap
  with devices ADMZ manages directly, records the ACS server that owns them.
  A single site may have **multiple ACS servers** — ACS server records are
  site-scoped entities within the Org → Site → Group hierarchy
  (see [hierarchy.md](../requirements/hierarchy.md)).

### 4. Sequence of work (recommended)

| Phase | Work | Why this order |
|-------|------|----------------|
| **0** | Persist `control_family` + `device_type` on device records; add typed taxonomy | Cheap, required by everything below; `get_facets_for_device` already wants this |
| **1** | Grow VAPIX catalog / facets for audio, access controllers, radar | Pure content; no architecture change (see Tier 1 note below) |
| **2** | `twon` family: `catalog/twon/rest/…`, `TwoNExecutor`, `TwoNCollector`, `twon` facets | Proves multi-family end-to-end; 2N is simpler than ACS |
| **3a** | ACS read path: `AcsCollector` that snapshots ACS config into git, **no write path** | Low risk; real value (versioning, drift, audit) before any writes |
| **3b** | ACS write path: `AcsActuator` behind plans + approval | Only after 3a is solid and the DB/file schema is understood |

---

## Tier notes

**Tier 1 — non-camera VAPIX devices** (speakers, A-series access controllers,
I/O modules, radar): already fit the existing architecture. The D4200-VE
strobe-siren work demonstrated end-to-end VAPIX for a non-camera device. The
only work is content (more catalog YAML ops, more facet adapters, model hints
in `DeviceCriteria`). No architecture change.

**Tier 2 — 2N intercoms**: a new `twon` family that drops into every existing
seam. 2N exposes a JSON HTTP API and a single `/api/config` backup/restore
endpoint — straightforward to snapshot. The one genuine addition is
`control_family` persistence on the device record (Phase 0 above).

**Tier 3 — ACS Pro**: the genuine architectural stretch, for three reasons:

1. ACS is not a device; it is a *system* containing a config graph of managed
   cameras, recording profiles, schedules, users, and access rules. The flat
   "device = box + creds" record needs the `parent_system_id` relation and
   `device_type=vms-acs` to express this.
2. There is no single config surface. Configuration is distributed across one
   or more SQL databases, multiple config files, and a partial Web API. The
   `AcsCollector` must be a multi-source collector — it cannot delegate to a
   single catalog operation.
3. Actuation is heterogeneous and high-blast-radius. Writing to an ACS server
   may involve the Web API, database edits, or service restarts, reached over
   a non-HTTP transport. The plans engine + two-gate approval is mandatory, not
   optional.

---

## Open questions (ACS — flagged for discovery spike, not asserted as fact)

The following must be resolved by investigation before ACS work begins.
Do not treat any of the following as known:

- Which database engine(s) does ACS Pro use? Where do instances live on the
  Windows host? Is the schema stable across ACS Pro versions, and if not, over
  what version range?
- Which config files complement the database(s), and where are they located?
- What does the ACS Pro Web API expose for *configuration* (vs runtime state)?
  Is there a supported config export / import endpoint?
- Connection model: host-side agent process vs remote WinRM vs direct SQL
  connection — which is viable and supportable for ADMZ's deployment model?

A spike / discovery workitem should answer these before any ACS implementation
is planned.

---

## Consequences

**Positive:**
- The git / diff / drift / restore pipeline is reused unchanged for 2N and
  ACS config — the `ConfigCollector` interface ensures the facet layer sees a
  uniform `raw_responses` dict regardless of how it was acquired.
- Two-gate approval and the plans engine (already battle-tested for cameras)
  apply to ACS actuation automatically — the safety architecture gets more
  valuable as target blast-radius increases.
- The pluggable-registry shape is consistent with every other extension point
  in ADMZ (ADR-0011, ADR-0015, ADR-0017, ADR-0026). Contributors extending one
  already know the others.
- Phase 0 (persist `control_family`) is cheap, low-risk, and unblocks all
  subsequent tiers.
- The ACS read-only path (Phase 3a) delivers real value — versioning, diff,
  drift, audit — with no write risk.

**Negative / trade-offs:**
- Introducing `ConfigCollector` as a distinct interface from `Actuator` adds a
  second abstract base to document and keep consistent. The split is justified
  by ACS but adds surface area.
- `control_family` on the device record is a schema migration (additive, null-
  defaulting to `"vapix"`). The migration is straightforward but must be
  coordinated with the Org → Site → Group migration work
  ([hierarchy.md](../requirements/hierarchy.md) FR-HIER-007 / NFR-HIER-001).
- ACS work carries **pre-condition risk**: if the DB schema is unstable across
  ACS Pro versions, the `AcsCollector` may need per-version adapters. This
  risk is why Phase 3a is a read-only, spike-first approach.
- A site with multiple ACS servers (see FR-MT-009 in
  [multi-target-support.md](../requirements/multi-target-support.md)) means
  the data model must support N ACS-server records per site from the start —
  a 1:1 assumption would require a breaking migration later.

---

## Alternatives considered

**Keep `family` as a caller-supplied parameter, don't persist it.**
Rejected: works when VAPIX is the only family; fails once a 2N device must
auto-route to the correct collector and a caller (scheduler, MCP tool) cannot
know which family to pass.

**Extend `VapixExecutor` to cover 2N and ACS inside one class.**
Rejected: the three protocols are different enough (auth, transport, request
shape, error model) that a single class would become a poorly-organized
branching tree. The executor ABC exists precisely to avoid this.

**Separate snapshot pipelines per family (no shared `ConfigCollector`).**
Rejected: it would duplicate the entire git / diff / drift / restore stack per
family. The `ConfigCollector` interface exists so only acquisition differs; the
rest of the pipeline is shared unchanged.

**Build ACS write path before read path.**
Rejected: the read path is lower risk, delivers audit value independently, and
gives the team time to understand ACS internals thoroughly before any writes.

---

## References

- Requirements: [multi-target-support.md](../requirements/multi-target-support.md) (all FR-MT-*)
- Architecture seams used here: `admz/executor/base.py`, `admz/snapshot/engine.py`,
  `admz/snapshot/facets/base.py`, `admz/catalog/loader.py`
- Related ADRs: [0011](0011-pluggable-backends.md), [0015](0015-pluggable-facets.md),
  [0017](0017-two-phase-discovery.md), [0026](0026-unified-job-scheduler.md)
- Safety gates this ADR depends on: [0005](0005-two-gate-plan-approval.md),
  [0006](0006-multi-level-confirmation.md), [0012](0012-snapshot-on-plans.md)
- Hierarchy interaction: [requirements/hierarchy.md](../requirements/hierarchy.md)
- Design background: [EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md](../../EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md) §3 "Scope: all device types"
- Extensibility contracts: [requirements/extensibility.md](../requirements/extensibility.md)
