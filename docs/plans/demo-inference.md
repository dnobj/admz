# Plan: infer existing demos from fleet + ACS state

Status: **implemented** — GH [#124](https://github.com/dnobj/admz/issues/124), shipped
as four slices (PRs #129 ACS rule anatomy, #130 evidence graph, #135 clustering +
proposals + confirm, and the agent narration surface). The design decision record is
[ADR-0051](../specification/decisions/0051-demo-inference.md); the user story is
`US-DW-013`. Two live findings changed the algorithm against what this plan assumed —
**zero rule-expressed topology** on the reference fleet (so `include_weak` defaults to
**true**, not false) and **corroborating evidence does not chain** (hence
`DENSITY_MIN_CORROBORATING` and `OVERLAP_MIN_LINKS`, neither of which is described
below). The ADR is authoritative where the two disagree.

The three product decisions are **RESOLVED** (owner, 2026-07-22) — see
[Resolved decisions](#resolved-decisions). In short: **(a)** confirmation is
**chat-driven** with rich tooling; **(b)** proposals **suggest owned config keys as
evidence** and never write fragments; **(c)** the run is **operator-invoked at any
time**, with no automatic ongoing re-inference in v1.

## Goal

When ADMZ arrives in an experience centre that already runs demos, **read the
environment and propose the demo inventory** instead of asking the operator to
re-describe it. Deterministic collection assembles a device↔rule graph from
sources ADMZ already reads; a deterministic, auditable clustering pass turns that
graph into scored **proposals**; the agent narrates name and purpose on top; a
human confirms, and the confirmed proposal becomes a real ADR-0046 demo through
the existing write cores.

The shape is #123's: *scripts collect, the agent interprets.* Nothing about the
clustering is a black box — every proposal carries the exact edges, weights and
score breakdown that produced it.

## Non-goals

- **No silent creation.** A proposal is never a demo until a human confirms it.
  Nothing writes to `demos` without an explicit confirm.
- **No new device-touch path.** Collection reads registry rows, git facets, and
  ACS read-only sources. It issues no VAPIX write and no ACS write (that is #127's
  problem, deliberately kept separate).
- **No ACS rule editing / beacon instrumentation.** This plan *reports* firing
  observability; remediating a blind rule is #127.
- **Not "is the demo running right now?"** — that is ADR-0041 Layer 4. This plan
  produces the inventory and the per-rule observability report that Layer 4 needs.
- **No LLM in the collection path.** The agent may rename and narrate; it never
  decides membership.

---

## Current state — what already exists (with evidence)

### The demo record today

`admz/demos/store.py:24-37` — one SQLite table, fixed columns:

```
demos(id, name, narrative, tag, device_ids_json, roles_json, config_source,
      signals_json, enabled, created_by, created_at, active, rules_json)
```

`Demo` (`store.py:46-82`) is that plus semantics: scope is **a tag OR an explicit
device list, tag wins** (`service.py:31-43`); `roles` is `{device_id: free-text
role}`; `signals` is `[{label, topic|category, device_id|role}]`; `rules`
(`store.py:66-70`) is a **system-managed** membership list
`[{device_id, rule_id, rule_name, condition_id, condition_topic, created_at}]`
deliberately excluded from `DEMO_FIELDS` (`actions.py:23-24`) so a metadata edit
cannot clobber it. New columns are added by idempotent try-ALTER
(`store.py:124-137`) — the house migration pattern.

**Consequence for this plan:** a proposal must NOT live in `demos`. Anything in
that table is enumerated by `list_demos`, rendered on `/demos`, rolled into
readiness, and — critically — walked by `fragments.attribution_maps`
(`fragments.py:213-252`) on **every drift check**. A half-believed guess must
never participate in drift attribution. Separate table.

### Fragments (ADR-0047) are *captured*, never authored

`fragments.py:302-340` writes `demos/<demo_id>/roles/<role>.yaml` in the config
repo. Values are the flattened strings drift compares, and capture runs a **live
drift check per device** (`actions.py:179`) so the recorded value is the device's
real one. `validate_assignment` (`fragments.py:143-189`) refuses a `set` key when
`field.expected == MISSING` → `"not-in-baseline"` (`fragments.py:177-180`), when
the facet is not param-writable, or when an ignore rule covers it.

**Consequence:** at first run there is no baseline and therefore no drift diff, so
there is *nothing to capture*. Auto-capturing fragments at inference time is not
merely undesirable — it is mechanically impossible on the flagship first-run path.
**Resolved [DECISION b]:** proposals therefore carry `suggested_owned_keys[]` as
read-only evidence and never write fragments.

### The "wizard" (ADR-0050) is a checklist, not a page

`admz/demos/wizard.py` is 131 lines of read-only status: `setup_status(ctx, demo)`
assembles devices/roles, fragment counts, rule status, signal last-seen and ingest
state, then emits ordered `next_actions` strings naming the exact remaining tool
calls (`wizard.py:104-130`). It is surfaced only as the `demo_setup_status` MCP
tool (`admz/mcp/tools/demos.py:221`). **There is no wizard template** — `ls
admz/api/templates/` has no `wizard.html`, and `grep -ril wizard` over `admz/`
returns only `demos/activation.py`, `mcp/server.py`, `plans/*` and docs.

**Consequence:** "slot a confirmation step into the existing wizard" is not
available. A wizard *page* would be net-new. The cheap hosts are the `/demos` page
(whose empty state today reads "No demos yet. Define one" — `demos.html:69-71`)
and the chat console. **Resolved [DECISION a]: chat-driven review** — no wizard
page is built in v1; a `/demos` section stays an optional slice-4 nicety.

### `correlate.py` correlates *devices to cameras*, not rules to demos

`admz/modules/acs_pro/correlate.py` is 89 lines of pure functions with one job:
given an ADMZ device + the ACS device/camera lists, find the ACS device with the
matching MAC and the cameras hanging off it (`correlate.py:27-89`). It is the
**join primitive** this plan builds on, and it is already correct:

- normalizes both sides through `canonical_mac` (`correlate.py:37-38, 48`),
- falls back to `SerialNumber` / `DeviceSerialNumber` (`correlate.py:53-58`),
- unwraps ACS ids that arrive either bare or as `{"Id": ...}` (`correlate.py:20-24`).

The rule↔demo correlation from #114 is a **different** mechanism and lives in
`demos/actions.py:290-336` (`attach_rule_to_demo`) / `339-368`
(`detach_rule_from_demo`): given a rule ADMZ **just created**, record membership on
a demo, auto-derive a signal from its `condition_topic` (deduped on topic+device),
and implicitly bind the device into scope. It is bookkeeping over a known rule, not
inference over unknown ones.

**Consequence:** there is no existing inference to extend — but `attach_rule_to_demo`
is the exact write the confirm step needs, unchanged. Inference supplies the same
rule dict shape the rule executor supplies today.

### What the ACS reader returns today vs what inference needs

`firebird.list_rules` (`firebird.py:142-164`) returns **`{id, name, enabled,
actions[]}`** where `actions[]` is a set of `DISCRIMINATOR` labels. It reads
`RULE(ID, NAME, IS_ENABLED)` and `ACTION(RULE_ID, ACTION_TYPE, DISCRIMINATOR)`,
hides the auto-generated `Predefined*` per-camera rules, and **never touches the
`TRIGGER` table**. There is no device linkage in the output at all.

The columns inference needs are already documented as present:
`docs/ACS_FIREBIRD_RULE_READER_SPIKE.md:14-17` records `ACTION` carrying
`URL/METHOD/BODY` (HTTP-notify), `MESSAGE`, `PORT_ID/NEW_STATE` (I/O), and a
`"TRIGGER"` table of conditions; the #124 comment of 2026-07-22 02:52 adds the
trigger detail per type (`DEVICE_ID`, `TOPIC_FILTER`, `CONTENT_FILTER`,
`CAMERA_ID`, `BUTTON_CONFIGURATION_ID`, `TRIGGER_NAME`).

Two mechanical notes for the implementer:

1. `"TRIGGER"`, `"TIMESTAMP"` and `"VALUE"` are Firebird reserved words and must be
   quoted (`firebird.py:184-186`).
2. **`_read` copies the entire `.FDB` per SELECT** (`firebird.py:103-132`,
   `shutil.copy2` at line 117). A naive `rule_anatomy` issuing four queries would
   copy a 22 MB database four times. The reader needs a `_read_many(db, [(sql,
   params), …])` that copies once and runs N cursors. This is a required change,
   not an optimization.

Degradation is already house-standard and must be preserved verbatim:
`GET /api/acs/rules` returns `{success: true, available: false, reason}` — never an
error — when Firebird is disabled or absent (`routes.py:145-167`), gated by
`firebird_enabled()` (`firebird.py:57-60`) and `firebird_available()`
(`firebird.py:86-97`). The whole ACS module surface is separately gated by
`acs_enabled()` (`config.py:68-74`).

### Device-side rules are already surveyed, with a firmware asymmetry

- **Snapshot path (preferred):** `ActionRulesFacet` (`snapshot/facets/action_rules.py:41-79`)
  reads `action-rules:listRules` through the `extra_read_ops` seam and serializes
  the **full rule objects** keyed by id, minus volatile fields. It is written to
  `fleet/{device_id}/config/action_rules.yaml` and read back with
  `git_repo.read_facet(device_id, "action_rules", ref)` (`git_repo.py:606-617`) —
  exactly what `wizard.py:30` does. **Gated to AXIS OS ≥ 12** (`action_rules.py:51`);
  older firmware yields an empty facet, gracefully.
- **Live SOAP path (fallback):** `rules/runner.py:250-263` (`GetActionRules`) parses
  to `{rule_id, name, enabled, primary_action}` (`runner.py:65-102`) — works on older
  firmware but carries **no condition topic**, i.e. names only.

**Consequence:** on OS 12 devices inference gets conditions and actions; on older
devices it gets names. The algorithm must treat a name-only rule as weaker evidence
by construction, not by accident.

### Free per-device attributes already in the snapshot

`rules/capabilities.py:150-165` (`device_applications`) returns `{acap_name: status}`
from the `applications` facet — installed analytics apps and whether they are
Running. `capabilities.py:140-147` maps topics to publishing ACAPs, and
`check_condition_publisher` / `condition_caution` (`capabilities.py:177-227`) encode
the #111 dead-rule knowledge. All of it is cache-only.

### The device key, and why normalization is mandatory

`device_id` is the **stable ADMZ slot** (ADR-0036); `mac_address` is the currently
installed unit. When the slot id is MAC-shaped, `add_device` backfills
`mac_address = device_id` (`backends/sqlite_backend.py:436-438`). `canonical_mac`
(`device_registry.py:11-23`) strips `: - . space` and uppercases, so
`"AC:CC:8E:E6:E7:EE"` and `"ACCC8EE6E7EE"` compare equal.

**On Axis devices the MAC is the serial number** — `routes/devices.py:457-461` mints
`mac_address` from `facts["serial_number"]` after `canonical_mac` when it is 12 hex
digits. So `CameraListFacade`'s `DeviceSerialNumber` (noted in the #124 comment of
03:11) is a *third equivalent spelling* of the same join value, and
`correlate.py:53-58` already accepts it.

**Never compare raw strings.** Every join goes through `canonical_mac`.

### Survey / discovery / onboarding — what a "deep survey" actually costs

A deep survey is an **orchestration of three existing calls**, not new probing:

| Step | Existing entry point |
|---|---|
| Discover | `discovery/orchestrator.py:158` `discover_devices(...)` — 7 protocols, two-phase, merged by MAC |
| Credential | `onboarding.py:49` `onboard_device_credentials(...)` — stored-verify → needsetup provision → fleet pair → capture widget |
| Config + rules + ACAPs | `snapshot/engine.py:227` `snapshot_fleet(...)` / `:171` `snapshot_device(...)` — writes every facet incl. `action_rules` + `applications` |

Note `admz/survey/` is the **atlas contributor** pipeline (ADR-0030: bundles → atlas
PR), unrelated to this feature. Do not overload the word in code: use `evidence`.

### No first-run concept exists

`grep -rn "first_run\|first-run\|setup_complete\|onboarded"` over `admz/` returns one
unrelated comment in `operations.py:337`. There is no install-state flag and no
first-run route. "Runs at first install" must therefore be an **explicit operator
action** (a button / a tool call), optionally remembered by a new fleet setting.
**Resolved [DECISION c]: operator-invoked at any time** — no install-state flag is
built; the explicit run covers the first-install moment.

---

## Data model

Two new tables in the control-plane DB, both created idempotently in the store's
`_ensure_table`, mirroring `demos/store.py:120-140`. **No change to the `demos`
table.**

### `demo_inference_runs` — provenance and the raw graph

```
id            TEXT PRIMARY KEY     -- uuid4 hex[:12]
started_at    REAL
finished_at   REAL
created_by    TEXT                 -- str(principal)
acs_available INTEGER              -- 0/1
acs_reason    TEXT                 -- the degradation reason when 0
device_count  INTEGER
rule_count    INTEGER
graph_json    TEXT                 -- the full evidence graph (nodes + edges)
params_json   TEXT                 -- thresholds/weights in force for this run
```

The graph is stored because it is the audit trail behind every score, and because
re-inference (out of scope for v1 per resolved **[DECISION c]**) is a diff against the previous run. `params_json`
pins the weights so an old proposal stays explainable after the constants change.

### `demo_proposals` — one candidate demo

```
id              TEXT PRIMARY KEY   -- deterministic: sha1(run_id + sorted member ids)[:12]
run_id          TEXT
name            TEXT               -- deterministic name; agent may overwrite
purpose         TEXT               -- narrative guess (agent-written, may be '')
device_ids_json TEXT               -- ADMZ device_ids, sorted
roles_json      TEXT               -- {device_id: "detector"|"responder"|"recorder"|…}
rules_json      TEXT               -- [{source:"device"|"acs", device_id, rule_id, rule_name,
                                   --   condition_id, condition_topic, actions[], observability{}}]
evidence_json   TEXT               -- [{kind, weight, detail, source}] — the "why"
suggested_owned_keys_json TEXT     -- [{device_id, facet, path, reason}] — READ-ONLY
                                   --   evidence per resolved [DECISION b]; confirm
                                   --   never writes these as fragments
score           REAL               -- 0..1
confidence      TEXT               -- high | medium | low
flags_json      TEXT               -- ["no_topology", "acs_absent", "name_only", …]
overlaps_json   TEXT               -- [{proposal_id, device_ids}]
status          TEXT               -- proposed | confirmed | dismissed | superseded
demo_id         TEXT               -- set on confirm
created_at      REAL
decided_at      REAL
decided_by      TEXT
```

`roles` / `rules` / `signals` use the **same shapes the demo already uses**, so
confirm is a copy, not a translation. `id` is content-derived so a re-run over an
unchanged environment reproduces the same ids (idempotent re-inference).

### One additive change to demo rule membership

`attach_rule_to_demo` (`actions.py:290-336`) records `{device_id, rule_id, …}` and
`wizard._rules_status` (`wizard.py:19-38`) then checks whether `rule_id` appears in
that device's `action_rules` facet. **An ACS rule has no ADMZ device and would read
`observed: false` forever** — a permanent false "your rule vanished".

Fix: membership entries gain `"source": "device" | "acs"` (default `"device"`), and
`_rules_status` returns `observed: None` for `source != "device"`. `rules_json` is
JSON and `_row_to_demo` (`store.py:85-97`) tolerates missing keys, so **this is not
a schema migration** — two small code edits.

---

## The inference algorithm

Pure, deterministic, no I/O — the same testability contract as `correlate.py` and
`demos/readiness.py`. All constants live as named module-level values and are echoed
into `params_json` and the API response.

### 1. Nodes

One node per ADMZ device from `registry.list_devices()`:
`{device_id, mac (canonical), name, model, tags, acaps}` where `acaps` comes from
`capabilities.device_applications` (cache-only).

### 2. Rules, resolved to devices

- **Device rules** — from `read_facet(device_id, "action_rules")`; already keyed by
  ADMZ device. Full condition/action objects on OS 12; name-only via the SOAP
  fallback otherwise.
- **ACS rules** — from the new `firebird.rule_anatomy()`. Each rule yields
  `trigger_devices` and `action_devices` as **ACS ids**, resolved to ADMZ
  `device_id` by:
  1. ACS `DeviceId` → `MacAddress` from the live `DeviceListFacade:GetDeviceList`
     (the supported path `correlate.py` already uses), then `canonical_mac` match
     against `mac_address` / `device_id`;
  2. fallback to the Firebird `DEVICE` table's MAC column;
  3. fallback to `DeviceSerialNumber` (Axis serial == MAC).
  Each resolution records `join_method` so the evidence line can say how it matched.

A rule that resolves to **zero** ADMZ devices is reported as `unattached` in the run
report — surfaced, never silently dropped (usually means the camera is in ACS but
not yet in ADMZ).

### 3. Edges (device↔device, weighted, each carrying its evidence)

| id | Signal | Weight | Class |
|---|---|---|---|
| `E1` | ACS rule triggering on device A and acting on device B | **1.00** | topology |
| `E2` | Two devices in the same ACS rule (multi-trigger or multi-target) | **0.90** | topology |
| `E3` | Device rule on A whose action references B (URL/host/SIP target matching B's IP/host/MAC) | **0.80** | topology |
| `E4` | Shared non-trivial ADMZ tag (ADR-0032) | **0.50** | grouping |
| `E5` | Distinctive shared token across rule names / device nicknames | **0.40** | naming |

`E3` reuses the identity-matching idea of `fragments.device_local_hits`
(`fragments.py:116-140`) in reverse: scan an action's parameter values for *another*
device's IP / host / MAC (bare and separated forms), requiring ≥ 4 characters to
avoid junk hits.

`E5` tokenizes on non-alphanumerics, lowercases, drops a stopword list (`axis`,
`rule`, `camera`, `test`, `new`, `demo`, `default`, `predefined`, model numbers,
pure digits) and keeps tokens appearing on **≥ 2 and ≤ 40 % of** nodes — distinctive,
not universal.

Edges below `EDGE_MIN = 0.40` are dropped.

### 4. Seed clusters

Connected components over the kept edges.

### 5. Split runaway components

The failure mode is one hub camera wired into everything. If a component exceeds
`MAX_CLUSTER_DEVICES = 8` **or** its edge density
(`2·edges / (n·(n−1))`) is below `DENSITY_MIN = 0.30`, cut bridging edges in
deterministic order (weight ascending, then the sorted device-id pair) until every
part satisfies both. Record every cut as a `split` evidence item so the operator can
see the component was broken up and why.

### 6. Score (published, auditable)

```
score = 0.40 · topology_cohesion   # min(1, topo_edges / max(1, n-1))
      + 0.25 · rule_density        # min(1, named_rules / max(1, n))
      + 0.10 · name_cohesion       # fraction of members sharing the top token
      + 0.10 · tag_cohesion        # fraction sharing the most common tag
      + 0.15 · firing_recency      # 1.0 seen firing <7d, 0.5 <30d, 0 otherwise
```

`confidence = high (≥ 0.70) | medium (≥ 0.45) | low (< 0.45)`.

Two hard caps, from the Master's directives and the evidence above:

- **Topology must corroborate naming.** A cluster whose only edges are `E4`/`E5`
  gets `flags: ["no_topology"]` and is capped at `low`. It is returned only when the
  caller passes `include_weak=true` (default **false**) — see *Open decisions*.
- **No ACS → cap at `medium`** for any cluster with no cross-device topology edge,
  with an explicit evidence line: *"ACS not connected — no cross-device rule topology
  available."*

### 7. Overlaps are kept, not resolved

A device in two clusters stays in **both**; each proposal records the other in
`overlaps`. This is correct under ADR-0046: baseline demos on the same device
coexist by design (`0046-demos.md:59-61`), and the only real exclusivity — same-key
fragment overlap between *active* demos — is already enforced at adopt time with a
409 naming the holder (`actions.py:252-260`, `fragments.py:273-296`).

### 8. Deterministic naming, agent narration

Fallback name = the top distinctive token, title-cased, plus a role hint
(`"Loitering detection"`, else `"<Model> demo (n devices)"`). It is **always stored**,
so the whole feature works with no LLM at all. The agent then rewrites `name` and
writes `purpose` from the evidence bundle, grounded by `list_rule_capabilities`
(#111) for human condition/action labels. Agent output is stored in the same fields
but the proposal always renders "proposed name" beside the evidence, so a narrated
guess is never mistaken for a fact.

### 9. Firing-observability report (per rule, pure function)

From the #124 comments of 2026-07-22, classified deterministically from the rule's
trigger type and action types:

| Rule shape | Channel | Notes |
|---|---|---|
| Trigger is DeviceEvent / Motion / ObjectDetection | `device_event_direct` | Subscribe to the same topic via ADR-0041 `ws-data-stream` — **zero ACS touch** |
| Action records | `recording_sequence` | `ACS_RECORDINGS.RECORDING_SEQUENCE` is rule-attributed |
| Action raises alarm | `acs_log_alarm` | The shipped poller (`firebird.read_new_firings`, `RULE_ID <> 0` per #125/#126) |
| Action sets I/O output | `device_event` | Target device's own output event |
| Action is HTTP notify at ADMZ | `webhook` | `modules/acs_pro/webhook.py` |
| Mobile notify / door-station / PTZ only | `blind` | Remediation is #127 |

Fidelity caveat carried verbatim into the report: observing the trigger event is not
proof the rule's full condition (`REQUIRE_ALL_TRIGGERS`, schedule gate, all
`CONTENT_FILTER`s) passed — it answers *"did the triggering condition occur"*, which
for single-trigger demo rules is usually equivalent.

### 10. Suggested owned keys (evidence only — resolved [DECISION b])

A proposal reports the config its linked rules *depend on*, so the operator can see
what the demo probably owns without ADMZ claiming anything. Derived deterministically,
each entry carrying its `reason`:

| Signal | Suggested key | Reason string |
|---|---|---|
| Rule trigger topic names an ACAP/analytics app (e.g. `…/sfh_detector/…`) | that app's config facet on the trigger device | `"trigger topic <t> is produced by <app>"` |
| Trigger is Motion / ObjectDetection | the device's analytics scenario/profile keys (cf. #121) | `"rule triggers on <detector> for this device"` |
| Action targets an I/O port | that port's config on the target device | `"rule drives output port <n>"` |
| Rule references a device-side event rule | that rule's own facet entry | `"demo's rule chain includes this device rule"` |

Written to `suggested_owned_keys_json` and rendered in the chat review. **Never
written as fragments on confirm** — the demo is created with an empty fragment set and
`demo_setup_status` (`wizard.py:110-111`) already emits the correct next action for
capturing them later through the normal drift-based path. Keys that would be refused
by `validate_assignment` (read-only facet, ignore-rule covered) are still *listed*,
flagged `not_capturable`, so the report stays honest.

---

## File-level implementation

### New

| Path | Contents |
|---|---|
| `admz/demos/inference/__init__.py` | Leaf-light re-exports only |
| `admz/demos/inference/graph.py` | `collect_graph(ctx, *, include_acs=True) -> dict` — the only I/O module |
| `admz/demos/inference/cluster.py` | **Pure**: `build_edges`, `seed_clusters`, `split_component`, `score_cluster`, `propose(graph, params) -> [Proposal]`. All constants here |
| `admz/demos/inference/observability.py` | **Pure**: `classify_rule(anatomy_row) -> {channels[], blind}` |
| `admz/demos/proposals.py` | `DemoProposal` + `ProposalStore` + `RunStore` — direct mirror of `demos/store.py` (per-call connections, ctor `db_path`, lazy singleton) |
| `admz/demos/inference/confirm.py` | `confirm_proposal_core` / `dismiss_proposal_core` — compose existing cores |
| `tests/test_demo_inference_cluster.py`, `tests/test_demo_inference_graph.py`, `tests/test_demo_proposals.py`, `tests/test_acs_rule_anatomy.py` | See test plan |

### Changed

| Path | Change |
|---|---|
| `admz/modules/acs_pro/firebird.py` | Add `_read_many(db, queries)` (one copy, N cursors — see `:103-132`); add `rule_anatomy(reader=None)` joining `RULE` + `ACTION` + `"TRIGGER"` (+ `DEVICE` for the MAC fallback), quoting reserved words; keep `list_rules` unchanged for existing callers |
| `admz/modules/acs_pro/routes.py` | `GET /api/acs/rules?anatomy=1` returns the anatomy under the identical `{success, available, reason, rules}` degradation shape (`:145-167`) |
| `admz/demos/wizard.py:19-38` | Skip observation for membership entries with `source != "device"`; return `observed: None` |
| `admz/demos/actions.py:290-336` | `attach_rule_to_demo` persists `source` (default `"device"`); no other behaviour change |
| `admz/api/routes/demos.py` | New inference endpoints (below) + `/demos` page context gains `proposals` |
| `admz/mcp/tools/demos.py` + `admz/mcp/dispatch.py` | New tools (below) |
| `admz/api/templates/demos.html` | *(optional, slice 4)* "Proposed demos" section — the resolved UX is chat-driven; this is a nicety, not a requirement |
| `admz/chatbot` prompt (`# Demos` section) | An "inferring existing demos" sequence, hooked into the compound-intent rule as ADR-0050 Phase C did |
| `docs/specification/decisions/00NN-demo-inference.md` | New ADR recording the proposal model, the scoring contract, and the never-silent rule |
| `docs/specification/user-stories/demo-workflows.md` | New story: *US-DW-0NN — ADMZ already knows my demos* |

## API / MCP surface

REST (all under the existing demos router, authenticated principal):

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/demos/inference/runs` | Runs collection + clustering. Writes only proposals — touches no device, so it is **inert metadata**: authenticated principal, no confirmation gate (same bar as demo CRUD, `0046-demos.md:126`) |
| `GET` | `/api/demos/inference/runs` / `/runs/{id}` | Run header + graph (the audit trail) |
| `GET` | `/api/demos/proposals` | `?status=proposed` default |
| `GET` | `/api/demos/proposals/{id}` | Full evidence + score breakdown + observability |
| `POST` | `/api/demos/proposals/{id}/confirm` | Body may override `name`/`purpose`/`device_ids`/`roles`. Creates the demo |
| `POST` | `/api/demos/proposals/{id}/dismiss` | Records `decided_by`/`decided_at` — dismissals are remembered so re-inference doesn't re-propose |

MCP tools (mirroring the REST cores, as every demo tool already does):

- `infer_demos` — run inference; returns the proposal list with evidence.
- `list_demo_proposals` — read-only. **As shipped this is the only proposal read tool**:
  the planned separate `get_demo_proposal` was folded into it, so a single proposal is
  read with `list_demo_proposals(proposal=…)` (#206). A REST handler of that name does
  exist in `admz/api/routes/demos.py`, which is what makes the stale line here
  plausible-looking; there is no MCP tool.
- `confirm_demo_proposal` — creates a real demo (see gating note).
- `dismiss_demo_proposal`.
- ~~`acs_rule_anatomy`~~ — **not shipped as an MCP tool** (#206). The capability landed as
  a REST query parameter instead: `GET /api/acs/rules?anatomy=1`, over
  `admz/modules/acs_pro/firebird.py::rule_anatomy`.

**Gating.** Run/list/dismiss are inert. `confirm_demo_proposal` creates a demo and
attaches rule membership — inert by the ADR-0046 bar — **unless** it also captures
fragments, which is drift-affecting and therefore must route through
`demos/gated.py::gate_demo_write` exactly as `assign_demo_fragment` and `adopt_demo`
do (`gated.py:27-42`), with the console-UI exemption (`is_interactive`,
`gated.py:18-24`). Under the **resolved [DECISION b]** (suggest-only, no fragment writes) confirm is
not drift-affecting, so it stays **ungated and simple**.

## Migrations

- `demo_inference_runs` + `demo_proposals`: `CREATE TABLE IF NOT EXISTS` in
  `_ensure_table`, same as `demos/store.py:120-140`. No backfill.
- `demos` table: **untouched**.
- Rule-membership `source`: JSON field inside the existing `rules_json` — no DDL.
- Rollback = drop the two tables; nothing else references them.

---

## Test plan (automated)

Pure-function tests need no ACS, no device, no network — the `Reader`-seam pattern
from `tests/test_acs_firebird.py` and the `DemoStore(tmp_path)` ctor-injection pattern
from `tests/test_rule_demo_correlation.py`. **Every store takes an explicit
`db_path`**: singletons bind their path at import, so a test that relies on the
default would pollute the real DB.

### Success cases

1. `rule_anatomy` via injected reader: joins `RULE` + `ACTION` + `"TRIGGER"`, hides
   `Predefined*`, quotes reserved words, and issues **one** DB copy for N queries.
2. **MAC join regression:** ACS `MacAddress` `"AC:CC:8E:E6:E7:EE"` matches ADMZ
   `device_id` `"ACCC8EE6E7EE"`; `DeviceSerialNumber` fallback matches when
   `MacAddress` is absent; `join_method` is reported.
3. **Two-device topology:** an ACS rule triggering on a camera and acting on a
   speaker produces one cluster of two devices, `confidence: high`, `E1` in evidence.
4. **Isolation:** three devices with no shared rule/tag/name produce three
   single-device proposals (or none — assert the documented behaviour), never one
   blob.
5. **Name-only rejection:** two devices sharing only a name token produce **no**
   proposal by default, and a `no_topology`-flagged `low` proposal with
   `include_weak=true`.
6. **Overlap:** a hub camera in two rule groups yields two proposals, each naming the
   other in `overlaps`, with the camera in both.
7. **Determinism:** the same graph clustered twice gives identical proposal ids,
   ordering, and scores.
8. **Observability classifier:** a fixture matching the local 12-rule specimen from
   the #124 comment classifies as 2 alarm-observable, 4 record-observable, 3
   device-event-observable, 4 blind, with one rule carrying both record and alarm.
9. **Confirm:** proposal → `create_demo_core` called with the proposal's fields,
   `attach_rule_to_demo` invoked per rule (signals derived from `condition_topic`,
   device implicitly bound), `status` flips to `confirmed`, `demo_id` recorded, audit
   row written.
10. **Degraded (ACS absent):** `acs_enabled()` False → graph reports
    `available: false` + reason, device-rule proposals still produced, confidence
    capped at `medium`, and an evidence line names the degradation.

### Failure cases

11. Firebird raises → `{available: false, reason}`, never an exception (mirrors
    `routes.py:160-166`).
12. Device on AXIS OS < 12: `read_facet` returns `None` → the device still
    contributes tag/ACAP/name evidence; no crash, no phantom rules.
13. ACS rule whose `DEVICE_ID` resolves to no ADMZ device → listed as `unattached`
    in the run report, excluded from clustering, not dropped silently.
14. Confirming an already-confirmed proposal → `DemoActionError(status=409)`.
15. Confirming a proposal whose devices were deleted since the run → missing devices
    skipped and reported; the demo is created from what remains (mirrors
    `service.resolve_devices`' tolerance, `service.py:41-43`); if nothing remains,
    409 with a clear message.
16. **Cluster-explosion guard:** a synthetic graph where one device touches 40 rules
    must split into components each ≤ `MAX_CLUSTER_DEVICES`, deterministically.
17. Malformed `action_rules` YAML / unparsable ACS action row → skipped with a
    warning; the run completes.
18. `include_weak=false` + a graph of *only* weak edges → zero proposals and a run
    report explaining why (not an empty 500).

## Test plan (manual, on the live deployment)

Read-only until the confirm step; the deployment on :4242 is **production**.

1. `POST /api/demos/inference/runs` with ACS connected. Compare the proposals against
   the operator's actual demo inventory — record precision/recall by hand in the PR.
2. Inspect the run graph: every ACS rule from the 12-rule specimen must appear, each
   with a resolved trigger device or an `unattached` note.
3. Confirm the single highest-confidence proposal. Verify on `/demos` that the demo
   renders with its devices, roles, rule membership and auto-derived signals, and
   that `demo_setup_status` returns sensible `next_actions`.
4. Set `acs_firebird_enabled=0`, re-run: proposals still produced from device rules,
   confidences capped, degradation reason visible.
5. Re-run inference unchanged: proposal ids stable; the dismissed proposal from step
   1 is not re-proposed.
6. Confirm nothing was written to ACS (rule count and `RULE.VERSION` unchanged) and
   no device was touched (no new plan, no drift transition).

---

## PR slicing

**Slice 1 — ACS rule anatomy reader** (small, self-contained, independently useful).
`firebird._read_many` + `rule_anatomy()` + `GET /api/acs/rules?anatomy=1` + the
`observability.classify_rule` pure function + tests through the injected `Reader`.
No new concept surfaced to the operator; the `/acs` page can immediately show what
each rule actually does. Merges alone.

**Slice 2 — the evidence graph.** `demos/inference/graph.py` + `demo_inference_runs`
+ `GET/POST /api/demos/inference/*` (graph only, no proposals) + the read-only
`survey_demo_evidence` tool. Degradation paths and the MAC-join resolver land here
with their tests. Already valuable: the agent can reason over the graph directly.

**Slice 3 — clustering, proposals, confirm.** `cluster.py` (pure) + `proposals.py`
+ `infer_demos` / `list_demo_proposals` / `confirm_demo_proposal` /
`dismiss_demo_proposal` + the `source` field on rule membership + the
`wizard._rules_status` fix. The bulk of the test plan lands here.

**Slice 4 — agent narration surface.** The chatbot prompt sequence and review flow
(the resolved **chat-driven** confirmation UX), the new ADR (**0051**) and the user
story. The `/demos` "Proposed demos" section is **optional** here, not required.

## Acceptance criteria

- Running inference on a fleet with ACS connected proposes demos that a human
  recognizes, and **every** proposal shows its member devices, its rules, its
  evidence items with weights, its score breakdown, and its confidence.
- No demo is ever created without an explicit human confirm. `demos` is untouched
  until confirm; drift attribution never sees a proposal.
- Re-running inference over an unchanged environment reproduces identical proposal
  ids and ordering; dismissed proposals are not re-proposed.
- With ACS absent (or Firebird disabled) inference still runs, reports the
  degradation with a reason, and caps confidence — it never errors.
- A confirmed proposal produces a demo whose rule membership and signals are wired by
  the **existing** `attach_rule_to_demo`, and which `demo_setup_status` can report on.
- Each proposal carries a per-rule firing-observability verdict, including the count
  of `blind` rules (the #127 hand-off).
- No new device-touch path and no ACS write anywhere in the feature.
- Full suite green; new pure modules covered by tests that need neither ACS nor a
  device.

## Risks

| Risk | Mitigation |
|---|---|
| **ACS `DEVICE_ID` ↔ live-API `DeviceId` equivalence is UNVERIFIED** — the entire ACS join rests on it | Implement the resolver with all three paths (API DeviceId→MacAddress, Firebird `DEVICE` MAC, `DeviceSerialNumber`) and report `join_method`. **Verify this first in the implementation session** — it is the one unproven assumption |
| Firebird schema is unsupported and version-specific (`ACS_FIREBIRD_RULE_READER_SPIKE.md:133-135`) | Select explicit columns; catch per-table and degrade to `{available: false, reason}`; never crash a page |
| Copy-per-SELECT cost (22 MB × N) — `firebird.py:117` | `_read_many` copies once; measure and record the run duration in the run header |
| Clustering produces one giant blob, or confetti | The split guard (`MAX_CLUSTER_DEVICES`, `DENSITY_MIN`) plus test 16 and test 4; all thresholds are named constants, tunable without touching logic |
| Agent invents a purpose the evidence doesn't support | The deterministic name is always stored and displayed; narration is labelled a guess; evidence is always shown beside it |
| Operator confirms a wrong proposal | Confirm is editable (name/devices/roles overridable in the body); demo delete is cheap and touches no device (`0046-demos.md:129`) |
| Proposals silently rot as the fleet changes | Content-derived ids + the run graph make re-inference a diff; `superseded` status is reserved for it |
| Scope creep into #127 (beacon) | This plan only *reports* blind rules; the remediation button is explicitly out of scope |

---

## Resolved decisions

Settled by the owner 2026-07-22, after the current-state findings above.

**[DECISION a] — Confirmation UX → CHAT-DRIVEN, with rich context/tooling.**
The operator's reasoning: *working out how device/ACS configuration flows up into a
"demo" will almost certainly require LLM review* — so the review belongs where the
model can explain itself, not in a static form. The deterministic evidence graph and
score sit underneath; the agent narrates each proposal, names it, surfaces the
evidence and the firing-observability verdict, and calls `confirm_demo_proposal`.
Near-zero net-new UI (no wizard page exists to extend anyway). Custom console widgets
for a proposal card are a **possible later refinement**, not v1. A `/demos`
"Proposed demos" section stays a nice-to-have in slice 4, not a requirement.

**[DECISION b] — Owned config → SUGGEST KEYS AS EVIDENCE; never write fragments.**
Auto-capture is mechanically impossible on the flagship path: capture only accepts
keys that are **currently drifted** (`actions.py:179` takes `check_drift` and skips
`"not-drifted"`; `fragments.py:177-180` refuses `"not-in-baseline"`). At first run the
baseline is snapshotted *from* live state, so live == baseline, zero drift, nothing
capturable. But the analysis is still valuable, so a proposal carries
`suggested_owned_keys[]` — candidate config keys the linked rules depend on
(analytics/ACAP/event config), each with its reasoning — as **read-only evidence**.
Confirming creates the demo with devices, roles, rules and signals and an **empty
fragment set**; the keys become real fragments later through the normal capture path
once the operator has deliberately changed something. ADR-0047 semantics are
unchanged (a demo owns what *differs* from baseline), and `demo_setup_status` already
emits the right next action (`wizard.py:110-111`).

**[DECISION c] — v1 scope → OPERATOR-INVOKED, ANY TIME; no automatic re-inference.**
Reconciles the owner's "first-run only" intent (keep v1 small, land the flagship
moment) with the finding that **no first-run concept exists** — restricting to
first-run would mean *building* an install-state flag purely to disable a capability.
So: an explicit operator-invoked run (tool + endpoint) that naturally covers the
first-install moment. Out of scope for v1: automatic detection of demo-like
structures appearing later (the #122 attention-surface use case). `superseded`
handling and dismissal-respect stay in the model so that later slice is cheap.

### Engineering decisions to settle at implementation

1. **Weak (name/tag-only) clusters: drop or surface?** Plan assumes *surface behind
   `include_weak=true`, capped at `low`, flagged `no_topology`* — honest without
   polluting the default view. Confirm at review.
2. **Firing-recency in the score (0.15 weight).** Needs a bounded historical read;
   `read_new_firings` is incremental-from-id (`firebird.py:176-189`). If a
   `recent_firings(since_ts, limit)` proves awkward, drop the term to 0 for v1 and
   redistribute to topology — the plan's tests do not depend on it.
3. **Single-device proposals.** A one-device demo is legitimate (a speaker
   announcement). Assumed **allowed** when it has ≥ 1 named rule; a device with no
   rules and no distinctive naming is not proposed.
4. **Role assignment vocabulary.** `roles` is free-form by design
   (`store.py:54-55`). Inference assigns `detector` (trigger side), `responder`
   (action side), `recorder` (record action target); the operator can rename.
5. **Where the ADR number lands** — next free number after 0050.
