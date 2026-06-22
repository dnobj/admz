# Spike plan: ACS Pro action-rule reader (Firebird DB)

**Status:** proposed spike — NOT yet built. Opt-in, read-only, gated on operator-supplied DB access.
**Related:** ADR-0040 (ACS Pro module), ADR-0041 (activity/observability), `admz/events/acs_ingest.py`
(anonymous, recording-only firing ingest), `admz/modules/acs_pro/webhook.py` (the supported real-time
firing path — but requires a one-time per-rule "Send HTTP Notification" action).

## Two goals (the DB is the only path to either without touching the rule)

1. **Named rule inventory** — list configured action rules (name + condition + action). [original goal]
2. **Generic firing detection WITHOUT modifying the rule** — detect when *any* action rule fires,
   regardless of its action. Established (live, 2026-06-22) that ACS exposes **no** such signal via its
   API: every recorded/event-log/alarm/event/audit/trigger/data-search facade read returns an opaque
   `400` (only recording-action firings surface, via `RecordedEventFacade`); the only Axis-documented
   firing notification is the per-rule "Send HTTP Notification" action (the **webhook**, now built —
   real-time + rule-named, but it *is* a one-time per-rule edit). So for rules the operator can't/won't
   edit, the **only** no-modification option is reading the ACS DB directly for a firing/alarm/event-log
   row. This spike must determine whether such a queryable table exists and is stable.

## Why

ADMZ can already see ACS Pro action rules **fire** (the `acs` event source — polled from the
recorded-events log), but those firings are **anonymous**: a firing carries `{Start, End, CameraId,
Type:"Action Rule"}` and **no rule name or definition id**. We want a **named inventory** of the
configured ACS action rules (name + condition + action), which would let us:

- name each anonymous firing ("ACS rule *Front-door-after-hours* fired on camera X"),
- track ACS rule **drift** alongside device action-rule drift,
- let an operator build detections scoped to a *specific* ACS rule.

### Why not the API (already proven)

- **No rule facade.** Probed ~12 candidate facades (`ActionRuleFacade`, `RuleFacade`,
  `TriggerFacade`, …); every one returns an identical `400 CommunicationException` — and so does a
  *known* facade with a wrong method, so ACS gives no signal to distinguish "no such facade" from
  "wrong name." The external Facade vocabulary is undiscoverable (same wall that blocked
  push-subscription).
- **Neither event log names rules.** The recorded-events "Action Rule" type is anonymous; the
  system `EventLogFacade` log over 30 days holds only recording/camera/disk events — zero rule
  entries.

So the **only** ground-truth source for rule definitions is the ACS server's own database.

## What the database is

- ACS Pro stores config + recordings in **Firebird** embedded databases (`.FDB` files; the search
  surfaced `ACS_RECORDINGS.FDB`). Action rules are configured under *Configuration → Recordings and
  events → Action rules* and persisted server-side.
- Firebird is typically **local to the ACS server** (embedded / localhost `gds_db` 3050), not
  exposed on the network by default. Default SYSDBA creds are often locked down by the installer.
- The schema is **undocumented, unsupported, and version-specific** — Axis can change it across ACS
  Pro releases with no notice.

## Spike objectives (read-only, low-blast-radius)

1. **Locate** the config DB on the ACS host (the `.FDB` alongside `ACS_RECORDINGS.FDB`, e.g. an
   `ACS.FDB` / config DB) and confirm the Firebird version.
2. **Connect read-only against a COPY** of the file (never the live DB) with a Firebird client
   (`fdb`/`firebird-driver` Python lib, or `isql`), enumerate tables, and locate the action-rule
   table(s): rule name, enabled flag, condition (trigger/event + camera), action (recording/output/
   notification/…).
3. **Correlate** a couple of known rules (e.g. the user's test rules) DB-row ↔ ACS-client UI ↔ the
   anonymous firing's `CameraId`, to confirm we can resolve firing → named rule.
4. **Hunt for a firing/alarm/event-log table (goal 2).** Look for a table that records *every* rule
   trigger (not just recordings/alarms) — candidate names: `*ALARM*`, `*EVENT*LOG*`, `*RULE*LOG*`,
   `*TRIGGER*`, `*AUDIT*`. **Verify by firing**: with the user's "test" rule (external-HTTPS trigger,
   non-recording), snapshot the table, fire the rule via `TriggerFacade:ActivateDeactivateTrigger`,
   re-snapshot, and check for a new row that names the rule. If a row appears, this is the
   no-modification generic firing signal — a poller over this table feeds the same `source="acs"`
   event path as the webhook.
5. **Decide**: is the schema stable/clear enough to read safely? Document the exact tables/columns,
   and whether the firing table (4) exists. If it doesn't, the webhook remains the only firing path.

## Approach / steps

1. **Access (operator-provided).** The operator supplies: ACS host filesystem access (or a DB
   export), the config `.FDB` path, and read-only Firebird credentials. ADMZ does **not** hunt for
   creds and does **not** touch the live DB.
2. **Snapshot.** Work against a **copy** of the `.FDB` (Firebird allows copying when the service is
   stopped, or use `gbak` to back up). All spike reads hit the copy.
3. **Schema map.** `isql -x` / query `RDB$RELATIONS` to list tables; grep for `RULE`, `ACTION`,
   `TRIGGER`, `EVENT`. Dump the candidate rows for the known test rules.
4. **Prototype reader.** A throwaway script (`tools/acs_firebird_probe.py`, not shipped) that opens
   the copy read-only and prints `{rule_id, name, enabled, condition, action, cameras}`.
5. **Report.** Tables/columns used, stability assessment, and a go/no-go for a shipped reader.

## If it's viable — integration sketch (separate, gated capability)

- New optional module surface `admz/modules/acs_pro/rules_db.py`: a **read-only** Firebird reader
  behind its own fleet flag (`acs_rules_db_enabled`) + operator-supplied connection (path + creds,
  stored like other secrets, **never** logged).
- `acs_list_action_rules()` → `[{id, name, enabled, condition, action, cameras}]`.
- Enrich the anonymous firing ingest: map a firing's `CameraId` (+ time) to the most likely
  configured rule → fill `data.rule_name`. (Best-effort; ambiguous when a camera has multiple rules.)
- Optional: an "ACS action rules" read-only panel on `/acs`, and ACS-rule drift tracking.

## Risks & guardrails

- **Unsupported/fragile:** schema can change between ACS Pro versions → reader must degrade to a
  clean "unavailable" (never crash) and be version-gated.
- **Live-DB safety:** read the **copy** only; opening the live embedded DB concurrently with the ACS
  service risks lock contention/corruption. Hard rule: no writes, ever; no live-file handles.
- **Credentials:** DB creds are sensitive — stored encrypted, redacted everywhere, supplied by the
  operator. ADMZ never discovers or brute-forces them.
- **Scope creep:** this is a **read** capability only. ACS rule *editing* stays out of scope (the
  ACS client owns it).

## Decision gate

Ship a reader only if the spike shows: (a) a copy can be opened read-only without disturbing ACS,
(b) the action-rule tables are clearly identifiable, and (c) firing→rule correlation works on the
known test rules. Otherwise: keep the anonymous-firing ingest (already shipped) and revisit if Axis
exposes a rules API in a future ACS Pro release.
