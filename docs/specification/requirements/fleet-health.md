# Requirements: fleet health monitoring

Answer "which devices are online right now?" without operators firing ad-hoc
checks. A background monitor polls every registered device on an interval and
keeps a single current-status row per device in the shared SQLite DB; the MCP
and REST surfaces read that table.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-HLT-001 — Current-state-only health store ✅
`admz/fleet/health.py::DeviceHealthStore` keeps one row per device in the
`device_health` SQLite table: `status`, `last_check`, `last_seen_online`,
`latency_ms`, `consecutive_failures`, `last_error`, and (when an
authenticated probe succeeded) `uptime_seconds` + `bootid`. No history is
kept here — "right now, which devices are reachable?" is a single-row read.
Full history is the audit log's / a future time-series store's job.

### FR-HLT-002 — Coarse reachability status ✅
`DeviceHealthStatus` ∈ `online` | `unreachable` (no TCP connect) |
`limited_api` (host answered, the JSON-RPC probe did not, but an authenticated
legacy-CGI read **did** — manageable, just not over the probed surface) |
`reachable_no_api` (host answered, and **nothing** ADMZ can read did) |
`auth_failed` (TCP up, VAPIX rejected creds) | `needs_setup` (reachable but
factory-defaulted) | `no_credentials` (TCP up, no usable stored credential —
FR-HLT-011, [ADR-0064](../decisions/0064-a-device-admz-cannot-authenticate-to-is-never-online.md)) |
`unknown` (never checked).
Status reflects the last successful probe; `last_seen_online` is the
**reachability** clock — it advances on every result that proved the host
answered (`online`, `limited_api`, `auth_failed`, `needs_setup`,
`reachable_no_api`, `no_credentials`), so
operators can read "was online 2 minutes ago" for flapping devices. It says
the host replied; it asserts nothing about what ADMZ verified.

### FR-HLT-003 — Two-tier probe ✅
`probe_device` (`admz/fleet/health.py`):
1. **Authenticated tier** — if stored credentials + catalog + executor are
   available, call `systemready.cgi:systemReady`. Success → `online` with
   `uptime_seconds`/`bootid`; `401` → `auth_failed` **only once a second,
   independent auth-required op has also refused** (GH #150 — see
   FR-HLT-010); connect failure → `unreachable`; any other failure → the
   reachability confirmation of FR-HLT-009.
2. **TCP tier** — otherwise a bare TCP connect to the device's effective
   port (`_probe_port`: an explicit `port`, else 443 when the learned scheme
   is https, else 80). Connect fail → `unreachable`. Connect OK with a
   usable credential → `online` (no uptime info); with none → FR-HLT-011.
The TCP fallback means a device with no stored creds still yields a
reachability signal, filed `no_credentials` (FR-HLT-011) — the host answered,
and ADMZ has no way in — or `needs_setup` when the unauthenticated read says so.

### FR-HLT-011 — A device with no usable credential is `no_credentials`, never `online` ✅
[ADR-0064](../decisions/0064-a-device-admz-cannot-authenticate-to-is-never-online.md), #443.
A device that is registered, whose host answers TCP, and for which ADMZ holds
no usable stored credential (the Tier-1 predicate: an account with a non-empty
password) is `no_credentials`. It is **settled** (`_STABLE_STATUSES`; the
failure counter does not climb), it stamps `last_seen_online` (the host
answered), it is amber and in the **attention** bucket, and `event_for_status`
maps it to `None` — no `on_online` task may fire for a device ADMZ cannot
authenticate to. A device *with* credentials that reaches the TCP tier only
because the catalog or executor is unavailable stays `online`: the value keys
on credential absence, not on which tier answered. Absence is something the
registry *says* (`AccountNotFoundError`/`DeviceNotFoundError`), never something
a lookup *fails* to say: on any other error the sweep keeps the previous record
with `last_error="credential lookup failed: …"`. Only the `default` account
counts (`recovery` and `at_*` rows are invisible, as they are to the Tier-1
guard today). A factory-default unit is **`needs_setup`**, not
`no_credentials`: with no usable credential the TCP tier asks `systemready`
unauthenticated — the op needs no credential by design — and `needsetup=yes`
wins, so the existing CTA and `on_needs_setup` trigger apply.

The sweep **classifies and never resolves**: it does not re-run onboarding,
try entry credentials, or open capture sessions (NFR-HLT-002; ADR-0034's one
gate) — the one exception being a *pre-authorised* detection task (ADR-0037's
`reprovision` on `on_needs_setup`), which is an approval deferred to a trigger,
not a sweep decision. Leaving the state is the operator's — capture from the device page or
the chat card — or a deliberate `onboard_device` re-run. The seven-hour trace
that forced this: an A1210 registered without credentials read `online` on
every surface until a baseline capture happened to need a password.

### FR-HLT-012 — A refused credential is retried on an escalating hold ✅
[ADR-0065](../decisions/0065-a-refused-credential-is-not-retried-on-a-fixed-cadence.md), #469.
Once a credential has been condemned (`auth_failed`, corroborated per
FR-HLT-008/010), the sweep stops sending it on every cadence. The wait starts at
one interval — so the first retry lands on the normal cadence — and doubles per
refusal, capped at a fleet-settable ceiling (default 30 minutes). The reduction
is exactly the ceiling divided by the interval: **30× fewer** credentialed
operations at the default cadence, about 144 a day instead of 4,320. The
ceiling is a **chosen** number, not a measured one, and is the first thing to
revisit when [ADR-0064](../decisions/0064-a-device-admz-cannot-authenticate-to-is-never-online.md)
decision 7's lockout measurement exists.

A held sweep re-derives a status **only from credential-free evidence**: a
failed TCP connect is `unreachable`; an unauthenticated `systemready` reporting
`needsetup=yes` is `needs_setup`, so the pre-authorised trigger still fires; and
otherwise the last **credential verdict** — `auth_failed` — is carried forward.
It does not fall through to the TCP tier and let that decide: a device in a hold
holds a credential by definition, so that tier would file `online` (FR-HLT-003
§2) and fire `on_online` against a device ADMZ cannot authenticate to, the
failure FR-HLT-011 exists to prevent. The unauthenticated read is the one
FR-HLT-011 uses, but from a call site of its own — FR-HLT-011's sits in the
credential-less branch, which a held device never reaches. It needs a catalog
and an executor and is suppressed by the ADR-0063 capability record, so a
factory reset is usually seen during a hold, not always; that is one more reason
the hold stays time-bounded.

A held sweep observed nothing about the credential, so the failure counter of
FR-HLT-007 does not climb (GH #138). It does advance `last_check` and the
reachability clock, because the host answered; it reports the TCP round-trip as
latency; and it suffixes the hold onto the condemnation text rather than
replacing it, idempotently, because that text is what routes an operator to
capture.

The hold covers a **condemned** credential only. An uncorroborated 401 files
`reachable_no_api` (FR-HLT-009/010) after spending two credentialed operations,
and that state neither holds nor escalates: ADMZ does not know the credential is
bad, so it keeps asking on the cadence. That is a deliberate limit of this
requirement, not an oversight.

The hold is cleared by a stored-credential write for the `default` account — the
one the sweep authenticates with — so an operator who enters a password is not
made to wait out the ceiling; by any outcome that answers the credential
question (`online`, `limited_api`, `needs_setup`, `no_credentials`); and by the
explicit sweep (`POST /api/fleet/health/sweep`), which must always mean what it
says. It is **not** cleared by `unreachable`, so a flapping device does not
restart the escalation. A clear that lands while a probe is in flight wins over
the sweep's own write. The streak and the deadline are persisted and exposed on
the read surfaces of FR-HLT-006, so an operator can see when the next credential
check is due.

### FR-HLT-009 — Reachability is never inferred from an API failure ✅
"Is the host up?" and "can ADMZ speak its API?" are separate questions and
never share a verdict (GH #138). When the authenticated tier fails with
anything other than a connect-class error — an unparsable body, an unexpected
content type, an unexpected-but-valid HTTP status — `probe_device` **confirms
reachability with a TCP connect** rather than reading the error string:
connect OK → the API question below, connect fail → `unreachable`. So
`unreachable` keeps its documented meaning (the host did not answer), and a
record can never carry a measured `latency_ms` while claiming the device is
unreachable.

**"Connect-class" means the executor's own two host verdicts, matched by
message prefix** — `Connection failed:` (`httpx.ConnectError`, which covers
refused, DNS, no-route and TLS-handshake failures) and `Request timed out`
(`httpx.TimeoutException`) — and nothing else (GH #461). The rule used to
match keywords anywhere in the text, and `"Server disconnected without sending
a response"` contains `connect`: a device that drops an unknown JSON-RPC post
was filed `unreachable` before the TCP probe and the legacy read ran, so it
could never become `limited_api` and its capability record could never be
taught. A keyword is not a verdict; every other error text is a statement about
ADMZ's ability to speak the device's API and is settled on evidence below. A
dead host produces only a connect error or a connect timeout — both fast-path
verdicts — so no dead fleet member pays an extra probe for this.

**"Can ADMZ speak its API?" is itself two questions (GH #357).** Once TCP
confirms the host is up, the probe asks the legacy-CGI surface
(`param.cgi:list`, the same op the 401 corroboration already uses) before
concluding anything:

| Legacy read | Status | Bucket |
|---|---|---|
| answers | `limited_api` | **online** — ADMZ reads and tracks this device |
| also fails | `reachable_no_api` | needs attention — genuinely unmanageable |
| refuses the credentials (401/403) | `auth_failed` — once a second auth-required op, or this sweep's own JSON probe, has settled the credential question; table below (GH #462) | needs attention — a credential problem, routed like any other |

The first two advance `last_seen_online` and neither accumulates
`consecutive_failures` — they are settled states, not failing probes.
`auth_failed` advances `last_seen_online` too (the host answered) but counts as
a failed probe. The extra call costs nothing on a healthy sweep: it runs only on
a path that has already failed.

Real-world case, and the one that forced the split: the **AXIS T8516** PoE
switch. It answers HTTP in ~80 ms, serves HTML where the JSON-RPC probe expects
JSON — and answers `param.cgi` perfectly, which is why ADMZ commits four config
facets from it every audit cycle and tracks 245 drift alerts against its
baseline. It was nonetheless reported as `reachable_no_api`, i.e. unmanageable,
**while being managed**. Because that status is settled by design it never
escalated, and because it never cleared either, the device sat in *needs
attention* permanently with `consecutive_failures = 0` — a device parked there
can no longer signal a real fault, which is alert fatigue built into the data
model rather than the UI. (The earlier 10,795-consecutive-failures counter on
this same switch was the #138 half of the story; #357 is the other half.)

**A refused legacy read is a credential question, not an API one (GH #462).**
Until #463 this branch asked the legacy read one question — *did it return
parameter data?* — and never inspected it for a 401, so a `limited_api` device
whose stored password had been rotated read as `reachable_no_api` ("lost its
API surface") on every sweep, never `auth_failed`, and nothing routed the
operator to capture. A refusal is now corroborated against
`basicdeviceinfo.cgi:getAllProperties` — the same one-op-is-not-proof
discipline as FR-HLT-008 and FR-HLT-010 — **with one deliberate difference**:
this branch is only ever entered because the JSON surface did not answer (or
the ADR-0063 record says it is absent, #460), and the corroborator is a
JSON-RPC op. A legacy-only device — the T8516 itself — can never answer it. A
JSON surface that is *demonstrably not there to ask* is therefore the same
case as a corroborator missing from the catalog, and gets the verdict
`_corroborate_rejection` already gives that case: the legacy read's refusal is
the only evidence this device can give, and a false alarm is safer than a
missed one. Which failures mean "not there to ask" is drawn on **ADR-0063's own
line**, with one distinction the ADR does not need — *device-wide* against
*op-specific*. The two shapes a legacy-only device produces — a transport
refusal after TCP accepted, and a 2xx body that is not JSON — are device-wide
(every JSON POST fails that way), and are the only shapes on which this sweep's
own `systemready` failure may settle the question by itself. The ADR's absent
status codes (400/404/405/410/501, reused by name) are about one endpoint: from
the corroborator they mean the device does not have it — the catalog-missing
case in another form; from `systemready` they say nothing about
`basicdeviceinfo` (firmware 6.50–9.49 has the latter and not the former), so
the corroborator is still asked. A JSON-RPC error object at 2xx — `1100:
Internal error` or `2004: Method not supported` alike — is a JSON surface
answering in JSON over an HTTP layer that accepted the credentials, and never
condemns. ADR-0063 files the two device-wide shapes as *unconfirmed* absence
with a short lease rather than a 7-day row; the health status is re-evaluated
every sweep, so it acts on the same evidence one sweep at a time, and — like
the ADR — never reads a live surface's bad moment as a missing one.

| Evidence | Verdict |
|---|---|
| this sweep's own JSON probe already failed in a **device-wide** missing-surface shape (transport drop after TCP accepted; a 2xx body that is not JSON) | the JSON surface was asked this sweep and was not there — **no second JSON op is sent**; `auth_failed`, error naming this sweep's evidence. A 404-class or JSON-error answer from `systemready` is op-specific and does not qualify: the corroborator is asked |
| the corroborator refuses too (401/403, or the anchored 401 text) | `auth_failed`, error naming both ops |
| the corroborator authenticates (2xx) | `reachable_no_api`, "credentials look valid"; its identity facts ride along for the sweep to flush |
| the corroborator cannot be served by this device — the surface is gone (the same two shapes) or the endpoint is not there (an ADR-0063 absent status code) | `auth_failed`, single-op judgement, error saying the device has no JSON surface to corroborate with |
| the corroborator is absent from the catalog | `auth_failed`, single-op judgement, error saying so — never "both refused" for an op that was not sent |
| the corroborator has a bad moment — a 5xx, a 4xx ADR-0063 does not call absent (408, 429), any JSON-RPC error object at 2xx (`1100: Internal error`, `2004: Method not supported`), or the executor errors | `reachable_no_api`, "NOT condemned" — transient; the next sweep asks again |

On a sweep where the JSON probe was skipped on the capability record there is
no fresh evidence, so the corroborator is asked; the legacy read is the *only*
read there, so this is where a rotated password on a switch is caught at all.
A legacy-only device whose password stays rotated logs one executor transport
WARNING per sweep — from whichever JSON op the sweep sends — until the password
is fixed; that is a true symptom of a state that needs the operator. Known
blind spot: a reverse proxy in front of a legacy-only device would answer the
JSON op with a 502, which is a bad moment, not a missing surface — no such
deployment exists here. The implementation is the source of truth
(`admz/fleet/health.py`, `_corroborate_legacy_refusal`, `_json_surface_gone`,
`_json_answer_kind`).

### FR-HLT-008 — Auth-aware: a `systemready` 200 is not proof of valid creds ✅
On some Axis firmware `systemready.cgi:systemReady` answers `200` **without
validating credentials**, so a device with a wrong/stale stored password would
otherwise show a misleading `online`. After a successful systemready, the probe
issues an **auth-required** call (`AUTH_CHECK_OP`,
`basicdeviceinfo.cgi:getAllProperties`, via `_confirm_credentials`). The extra
call fires only for already-reachable devices, and is skippable via the
`health_verify_credentials` fleet setting (default on) for fleets of
intentionally low-privilege accounts. This is the gap that masked the
real-world I8016 case (right IP, stale password — was shown "online").

**A `401` from that one call is not proof of bad credentials** (GH #149). It is
corroborated against a second, independent auth-required op
(`CORROBORATION_OP`, `param.cgi:list`) before the password is condemned, so
`_confirm_credentials` is **tri-state**, not a boolean:

| Both ops refuse | → `auth_failed`, error naming *both* ops |
| The corroborator is absent from the catalog | → `auth_failed`, deliberately — a stale password must not read as healthy because the second op is unavailable; the error says so, never "both refused" (#464) |
| The corroborator authenticates (2xx) | → stays **`online`**; a `health_probe` marker records which op works here, so it is preferred next probe |
| The corroborator errors or answers oddly | → **status is not moved at all** (the ONLINE path; the failure branch's rule is FR-HLT-009's table) |

> **Corrected 2026-08-04 (#214).** This requirement was marked ✅ while
> describing the **pre-#154 rule** — *"a `401`/`403` flips the status to
> `auth_failed`"* — which is the single-401 condemnation that PR #154 replaced,
> and the exact behaviour that parked an AXIS P8815-2 at `auth_failed` with
> 18,004 consecutive failures while it was fully manageable. A reader
> "restoring" the documented rule would reintroduce that bug. `CORROBORATION_OP`,
> `AUTH_CHECK_OP` and the `health_probe` marker appeared **zero** times in
> `docs/` before this correction.
>
> The marker itself selects probe **order only** — it never skips verification.
> A marker meaning "trust this device without an auth check" would make a stale
> password on a marked device invisible, which is #149's own complaint inverted.

**The implementation is the source of truth for the outcome table**
(`admz/fleet/health.py`, `_corroborate_rejection`); when it and this paragraph
disagree, believe the code.

### FR-HLT-010 — A `systemready` 401 is corroborated too ✅
FR-HLT-008 covers the *credential-check* op. `probe_device` has a **second**
place where a 401 became a fleet-visible `auth_failed`: the `systemready` call
itself, in the authenticated tier of FR-HLT-003. Until GH #150 that branch
condemned the stored credentials on one op's evidence — the same inference #149
disproved on a real AXIS P8815-2.

It now reuses the same `_corroborate_rejection` helper, so:

| Both ops refuse | → `auth_failed`, error naming *both* ops |
| The corroborator authenticates (2xx) | → `reachable_no_api` — the host answered and the password is demonstrably fine; ADMZ simply cannot read this device's readiness |
| The corroborator errors or answers oddly | → not condemned; classified on TCP evidence |
| The corroborator is absent from the catalog | → `auth_failed`, deliberately (see FR-HLT-008's reasoning: a genuinely stale password must not read as healthy because the second op is unavailable); the error says the corroborator was not in the catalog and this is single-op judgement — never that it refused (#464) |

The corroborating call only ever runs on a path that has already failed, so a
healthy device pays nothing for it.

**Ordering — why a `systemready` 401 still cannot reach `needs_setup`.** #150
noted that this branch returns before the needsetup check, putting a
factory-defaulted device out of reach of the #70/#71 deferred-recovery
triggers. The observation is right and the obvious remedy does not work:
`needsetup` is read out of **systemready's own parsed body** (and
`fleet/systemready.py::read_systemready` likewise returns `None` unless
`result.success`), so a 401 carries no needsetup signal at all. Reordering
would evaluate `needsetup = False` against an empty body and fall through to
the same place. **When `systemready` 401s the signal does not exist anywhere in
ADMZ**, because `systemready` *is* the auth-free signal.

So the fix removes the wrong verdict rather than relocating it. Recovering
`needs_setup` from that state would need a new signal — an unauthenticated
`systemready` retry being the obvious candidate — which is deliberately not
built: the scenario (systemready 401ing while another op authenticates) has
**never been observed on a real device**, and that is precisely why #150 was
split out of #149.

### FR-HLT-004 — Single background loop, opt-in ✅
`HealthMonitor` is one async loop per process (shared between the MCP and
REST surfaces like SnapshotScheduler), bounded by an asyncio semaphore
(`ADMZ_HEALTH_*` / fleet-setting tunable; default interval 60 s, timeout 5 s,
concurrency 8). It is **off by default** — operators flip
`health_monitor_enabled=true` (fleet setting) to start it; no server restart
needed (FastAPI lifespan checks at startup, and the web UI can start/stop it).
The loop re-reads its interval each cycle, so changing the interval doesn't
require a restart. `start()` is idempotent (calling twice doesn't spawn two
loops).

### FR-HLT-005 — On-demand sweep ✅
`HealthMonitor.sweep_once()` probes every device once and returns the count;
it is public so operators (and tests) can force a sweep without waiting for
the interval. Surfaced over REST as `POST /api/fleet/health/sweep`.

### FR-HLT-006 — Read surface: MCP + REST ✅
- MCP: `get_device_health(device_id)` and `get_fleet_health()` (the latter
  returns per-device entries + `counts` by status). Both read the cache.
- REST: `GET /api/devices/{device_id}/health`, `GET /api/fleet/health`
  (entries + summary counts), `POST /api/fleet/health/sweep`
  (`admz/api/routes/health.py`).
Devices the monitor hasn't checked report `status="unknown"` with a note
pointing at the fleet flag / the sweep endpoint.

### FR-HLT-007 — Failure-counter continuity across sweeps ✅
Each sweep carries the prior `last_seen_online` forward **when the new probe
didn't establish one** (a fresh reachability stamp is never overwritten by a
stale one) and increments `consecutive_failures` when a probe fails, so a
device down for several cycles shows a rising failure count rather than
resetting each sweep. `online`, `limited_api` and `reachable_no_api` reset the
counter — all three are settled answers, not failures (`no_credentials` joins
them under FR-HLT-011: settled, *and* in the attention bucket). Note that
"settled" and "needs attention" are **different questions asked of the same
enum**: all four are settled, and two of them — `reachable_no_api` and
`no_credentials` — belong in the attention bucket. Both
predicates were individually correct while the T8516 stayed parked (#357), so
give a new status the right answer to each rather than making one match the
other.

## Non-functional requirements

### NFR-HLT-001 — Bounded, non-hostile polling ✅
Concurrency is capped by the shared fleet semaphore so health sweeps don't
fight snapshot sweeps or hammer the network. The interval floors at 5 s
(anything faster is rejected) and the per-device timeout clamps to [1, 60] s.
📋 **(FR-HLT-012, ADR-0065)** "Non-hostile" *will also* bound what a sweep
spends on a device that has already refused it: a condemned credential retried
on an escalating hold rather than on the cadence. As this requirement stands
today it bounds the polling rate and not the authentication rate.

### NFR-HLT-002 — Probe is read-only ✅
Both probe tiers only read (`systemReady` or a TCP connect that writes
nothing to the socket). A health sweep never changes device state.

## Known limitations

### KL-HLT-001 — Cache lags reboots ⚠️
The table is interval-polled, so immediately after a reboot it can still show
the pre-reboot status until the next sweep. For the "did it come back?"
question right after a restart, use `await_device_recovery`
([device-recovery.md](device-recovery.md)), which live-polls instead.

### KL-HLT-002 — One monitor per process ⚠️
Like the scheduler, the monitor is per-process state. The uvicorn process is
the intended owner; pool-spawned MCP subprocesses should not run their own
(see the scheduler's `ADMZ_MCP_NO_SCHEDULER` pattern — the health monitor is
gated behind its opt-in fleet flag, which subprocesses inherit but typically
leave off).

### KL-HLT-004 — `limited_api` / `reachable_no_api` are only reachable from the authenticated tier ⚠️
Both statuses are produced when the *authenticated* probe gets an unusable
answer. The credential-less TCP tier reports a bare connect as `online`
(FR-HLT-003 §2). This entry declined to reclassify that — "no credentials
stored yet" is a different situation from "this device doesn't speak VAPIX",
and "awaiting credential capture" sounded like a short, visible interval —
until #443 showed a device *awaiting capture* for seven hours with no capture
pending. **That refusal is superseded by FR-HLT-011 / ADR-0064** ✅ (shipped 2026-09-06): the
credential-less device becomes `no_credentials`, a state of its own, distinct
from both `online` and "doesn't speak VAPIX". Per-device-class probes (a plain
`GET /` for a T85, say) and per-class credential verification remain GH #15.

The #357 split narrows what is left here rather than closing it: the probe now
consults a **second real surface** (`param.cgi`) before declaring a device
unmanageable, so the common T85 case is classified from evidence instead of
from one op's parse failure. What it still does not do is read the device's
*capability profile* to decide which surfaces to try at all — #15's territory,
and the reason a device class ADMZ has never met can still be judged against an
operation it was never going to answer.

### KL-HLT-003 — No push alerting ⚠️
Health is pull-based current-state. Transition alerting (online→unreachable
notifications, webhooks) is not built here; drift has a transition log
(`drift_alerts`) but health does not yet.

## References

- User stories: [fleet-monitoring](../user-stories/fleet-monitoring.md)
- Sibling: [device-recovery.md](device-recovery.md), [scheduling.md](scheduling.md),
  [drift-detection.md](drift-detection.md), [mcp-server.md](mcp-server.md)
- Cross-cutting: [reliability.md](reliability.md), [performance.md](performance.md)
- Code: `admz/fleet/health.py`, `admz/api/routes/health.py`
