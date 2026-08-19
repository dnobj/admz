# ADR-0063 — Capability knowledge is local-first: probe once, record, revalidate on change; the atlas advises and never suppresses a probe

**Status:** Proposed (2026-08-18). Plan-first; implementation issues follow the merge.
**Relates to:** ADR-0015 (pluggable facets — the selection contract this extends), ADR-0029 (the
atlas capability matrix — what this stops treating as authoritative for *this* device), ADR-0030
(survey / contributor mode — amended alongside: probing is for everyone, contribution is exclusive),
ADR-0031 (drift vs baseline — whose compare learns to say "unverified"), ADR-0036 (slot vs unit —
why capability rows are forgotten on a hardware rebind), ADR-0042 (`ADMZ_HOME` — where the store
lives), #357 (`reachable_no_api` — the same class), #123 (continuous device-knowledge validation —
whose open question this answers), #428 (per-device state that must not outlive the device).

## Context

The hourly drift audit probed `sip:getSIPAccounts` on the T8516 PoE switch and logged an ERROR
traceback. A switch has no SIP. The audit did it again an hour later, and every hour since.

### Nothing asks before probing

Facet selection (`snapshot/facets/base.py`, ADR-0015) matches a facet to a device by `applies_to`
criteria — `device_types`, `model_patterns`, `families`, `min_firmware`. In practice only `families`
is used, and `api_family` is **never written** by anything, so every device defaults to `"vapix"` and
every API-backed facet matches every device, PoE switches included. Seven facets issue their own
API call (`sip`, `ntp`, `time_api`, `event_schedules`, `event_mqtt_bridge`, `action_rules`,
`applications`); on a device without that API each call fails, the engine **drops the failure
silently** (`engine._read_extra_ops` has no else branch), records the facet **`success=True, {}`**,
and the scheduler repeats it next cycle. Nothing in `drift_reports` says it happened. The SIP facet's
own docstring calls this graceful; it is graceful in the way a leak is quiet.

Two further defects ride on the same code. A facet that *did* capture a baseline and whose API
later fails transiently reads every stored key as `<missing>` and reports the **whole facet as
drifted**. And `drift.py` iterates *live* facets only, so a baseline facet that is absent from the
live read is never visited — it vanishes from the compare rather than being reported.

### The atlas knows, and cannot be trusted to say no

The atlas holds per-model, per-firmware capability snapshots sourced from each device's own
`api-discovery`, with a genuinely tri-state resolver (`None` never looked / `False` probed-absent /
`True`). The obvious design — consult the atlas, skip what it says is absent — was the first draft
of this ADR. It is wrong, on the data:

- **Partial snapshots exist and are indistinguishable from complete ones.** The 2026-02 snapshots
  were taken legacy-only (no DCA run) and therefore lack every DCA-only api id — `action-rules`,
  `event-schedules`. A device at *exact* firmware 12.8.54 resolves `action-rules: False`. Skipping on
  that would suppress the very probe that corrects it, permanently.
- **The tie-break picks partials.** `get_latest_snapshot` orders by probe date and breaks ties by
  list order; the Q3538-SLVE has two same-day snapshots and the first is a 30-API DCA-only capture
  — it reports `sip`, `ntp`, `mqtt-client` as `False` over the 95-API full one.
- **ADMZ never passes firmware correctly.** The registry stores `firmware_version`; the resolver
  reads `firmware`. So every ADMZ lookup hits the tie-break above.
- SOAP api ids appear in zero snapshots and are always `False`.

So an atlas negative is a claim about a model, made from a snapshot that may be partial, matched to
a firmware that may be wrong. It is good evidence for *what to expect* and bad evidence for *what
to skip*. A skip that is wrong costs a facet its drift coverage silently, forever; a probe that was
unnecessary costs one request. Those are not symmetric.

### ADMZ has no memory of what it has probed

Survey mode (ADR-0030) already calls `getApiList` and DCA discovery on every device it surveys — and
then diffs the result against the *installed atlas* and ships it outward as a PR. Nothing is kept
locally. `diff_snapshot` has no local history to compare to; an unchanged device produces no
artifact at all. The loop closes in the atlas, weeks later, if the PR merges. It never closes here.

The firmware half of this is the same shape: `fleet/health.py` computes the firmware delta on every
sweep, uses it only to skip a redundant registry write, and discards it. The detection is real; the
firing is not. #123 assumed that seam existed.

## Decision

**One local store of device-truth, written by ADMZ's own reads, consulted before every probe.
Unknown means probe. The atlas advises; it never suppresses a probe.**

### The store

`device_capabilities(device_id, probe_key, supported, firmware, source, reason, fail_streak,
observed_at, expires_at)`, primary key `(device_id, probe_key)`, in the same SQLite file as every
other per-device store and on #428's cascade list. `probe_key` is derived from the operation the
facet reads — the catalog `api_id` for that operation's API where one exists, else the API name —
so **no facet declares anything**, and operations whose API has no `api_id` (`applications-list.cgi`,
`param.cgi`) are learnable too.

A row is **stale** when `firmware != current` or `expires_at < now`. Keyed by firmware, a firmware
upgrade makes every row stale with no invalidation code; the next audit re-probes. Rows are
forgotten on a hardware rebind (ADR-0036: the row describes the *unit*, the key is the *slot*).

### Selection — in the engine, not the adapter index

`get_facets_for_device` stays the **static** adapter index; nine callers (restore, drift's canonical
keys, demos) need it unfiltered, and a skipped facet must not vanish from restore. The capability
view is applied **only** where reads are issued: a facet's extra read is skipped iff a non-stale row
says `supported = 0`. Anything else — present, unknown, stale, expired — probes.

### The learner — the audit's own reads, classified with a same-cycle control

Every extra-read outcome is recorded. The classification uses the control the engine already has:
the shared `param.cgi` dump. **If the dump succeeded this cycle, the device is readable now, and a
specific operation failing is evidence about that operation**, not about the network.

| outcome | meaning | TTL |
|---|---|---|
| 2xx | `present` | until firmware change |
| 404 / 405 / 501 / 400 / 410, or a JSON-RPC error | `absent` | 7 days |
| 401 / 403 / 5xx / parse / transport / timeout **on a readable device** | `absent_unconfirmed` | 24h · 2^(streak−1), capped at 7 days |
| anything, device **not** readable this cycle | indeterminate | no row |

The third row is the one that matters. The T8516's failure is an `httpx.ReadError` — a transport
error. A rule that said "transport → no record" (the first draft of this ADR) would never have
learned the one device this ADR is written for, while every test stayed green. `absent` rows expire
so that an API enabled later — an ACAP install is the clear case — is noticed within a week; the
drift audit is already periodic, so that IS the cadence.

### Honesty in the result

`FacetResult.status ∈ {ok, skipped, failed}`; `success` remains `status == ok`. Drift enumerates
**baseline** facets as well as live ones: a baseline facet that is now `skipped` is reported as
`facets_absent` — it *is* drift, rendered honestly, and it produces **no `DriftField`**, because the
revert builder must never write to an API the device does not have. A baseline facet that `failed`
is `facets_unverified` — not drift; that is the latent bug, closed. `skipped` is a settled state: it
never makes a snapshot `PARTIAL`, for the same reason `reachable_no_api` does not increment
`consecutive_failures`.

### Survey is for everyone; contribution is exclusive

The full enumeration — the device's own `apidiscovery.cgi:getApiList`, through the executor, so it
reaches a `limited_api` device — runs for every install: after credentials resolve on add, on
firmware change, on a 30-day cadence, on demand. It writes **positives only** (getApiList is
legacy-only; its absence is the partial-snapshot problem locally), and a positive clears an
`absent` row. Contributing the result to the atlas stays behind `survey.contributor`, including the
"Run now" path that today pushes with a stored PAT while the capability is off. ADR-0030 is amended
to say what the code does.

### Firmware change becomes an event

At the health sweep's existing delta and at the engine's own fact refresh: `firmware_changed` when
the prior value was non-empty and differs (audit row, enqueue a survey); `firmware_observed` when it
was first seen. The engine lifts `root.Properties.Firmware.Version` from the raw dump before the
volatile filter drops it, so a device the health monitor cannot authenticate to still gets a
firmware key.

## What this does not do

- **It does not make the atlas irrelevant.** The atlas remains the shared, cross-fleet record and
  the MCP `check_api_support` tool's fallback. It simply answers *after* the local row and *never*
  decides to skip. Three atlas-side defects (tie-break, partial-snapshot provenance, SOAP ids) are
  filed there, not fixed here.
- **It does not fix `api_family` never being written**, or make `device_types` / `model_patterns`
  live criteria. Those are real and separate.
- **It does not retire `reachable_no_api` / `limited_api`.** They describe the device; this describes
  its APIs. The two should agree more often once this ships, which is a check worth adding later.

## Consequences

**The T8516 stops erroring after one cycle**, with no new traffic: the audit's own failed reads are
the learning. The class — probing a device for a surface it lacks — closes for every facet at once.

**Drift gets more honest and slightly louder.** A facet that used to vanish from the compare now
appears as `facets_absent`. That *is* a change in what operators see, and it is the correct one: a
baseline facet the device no longer answers for is drift. The signature only changes when the list
is non-empty, so existing signatures do not all flip on deploy.

**A new store, with the usual obligations.** Call-time `_db_path` (the #258 rule), on #428's cascade
list, isolated by the test `ADMZ_HOME` redirect. Forgotten on rebind.

**The survey's meaning shifts.** It was "a thing contributors run"; it becomes "a thing ADMZ does to
know its own fleet", with contribution as the opt-in tail. That matches the owner's framing and
what the code already mostly did.

**What would falsify this.** If, after a month, `absent` rows are almost never present on devices
that have snapshots in the atlas — i.e. the atlas negative would have been right every time — then
"the atlas never suppresses" cost a probe per device per API for nothing, and an exact-match skip
gated on snapshot completeness (`"api-discovery" in snap.apis`, per-api source from `apis_detail`)
is worth adding. The local store makes that measurable: compare its `absent` rows to the atlas.
