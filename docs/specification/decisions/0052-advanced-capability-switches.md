# ADR-0052 — Advanced capability switches: one declared registry, five loudness surfaces, zero enforcement

**Status:** Accepted (2026-07-31). Closes issue #132 (PRs #134 slice 1, #136
slice 2, and this slice). Implementation plan:
`docs/plans/advanced-switches.md`, whose *Master resolutions* section settled
the five open decisions on 2026-07-28. (Numbering note: 0051 was reserved for
demo inference, which was further along; this work takes **0052**.)
**Relates to:** ADR-0034 (confirmation gates — the model a capability may
never touch), ADR-0020 (protected fleet-settings keys — the mechanism that
keeps the LLM out), ADR-0039/0040 (module enablement — the "one predicate,
zero footprint until enabled" pattern this generalizes), ADR-0030 (survey /
contributor mode — the privileged profile that now registers rather than
carrying its own enablement), ADR-0042 (the Shawl-supervised service, which is
why an env var means a restart).

## Context

ADMZ had accumulated **nine** powerful, dangerous, or privileged-install
switches, each invented separately: an env var here, a fleet setting there, and
three different truthiness parses between them. `ADMZ_DEV_AUTO_APPROVE` let an
unattended script complete confirmation gates meant for a human.
`ADMZ_ACS_FIREBIRD` read an unsupported embedded database. Survey mode ran a
background loop that contacted devices and pushed to GitHub under a stored PAT.
Two suppressors silently turned production behaviour *off*.

Every one of them was discoverable only by reading source. There was no
inventory, no shared danger classification, no audit row when one became
active, and no startup line naming the ones in force. The operator's question —
***"what non-default powers is this installation running with?"*** — had no
answer short of a code review. On a machine that manages a live Axis fleet and
a live ACS install, that is the wrong place for that question to live.

The danger is not uniform, and lumping it together would have been useless:

| Class | What it means | Example |
|---|---|---|
| `dev-only` | Never appropriate outside development | `dev.auto_approve`, `dev.test_auth` |
| `dangerous` | Writes outside ADMZ's normal gated write paths | `acs.rule_write` (#131) |
| `privileged` | Legitimate, but a privileged install profile | `survey.contributor`, `events.device_ingest` |
| `test-suppressor` | Turns production behaviour *off* for determinism | `test.no_onboarding_probes` |
| `internal` | ADMZ sets it for its own subprocesses | `runtime.no_scheduler` |

Two existing patterns were worth copying rather than reinventing. Module
enablement (ADR-0039/0040) is **one predicate consulted everywhere**, so ACS
Pro contributes zero nav, tools, or prompt until connected. Survey mode
(ADR-0030) already had the right *storage* discipline — protected keys,
Fernet-encrypted PAT — and only lacked a *declaration* saying it was a
privileged capability at all.

## Decision

**One registry declares every advanced capability; the declaration is the read
path; enablement is asymmetric by danger class; and the whole thing is loud in
five places. It declares — it does not enforce.**

### 1. One table, and it is the read path

`admz/capabilities.py` holds `CAPABILITIES`, a module-level tuple of frozen
`Capability` dataclasses — id, title, description, danger class, production
verdict, how it is enabled, the *existing* env var / setting key unchanged,
companion credentials, provenance, and notes on what breaks if you leave it on.
Read top to bottom, it is the whole truth, in the same spirit as
`PROTECTED_SETTING_KEYS` and `EXPECTED_TOOL_ORDER`.

Slice 2 made the declaration load-bearing: every migrated call site delegates
to `is_active(id)`, so the registry can no longer disagree with the code it
describes, and there is exactly **one** truthiness parse
(`{"1","true","yes","on"}`) where there were three. Env is checked before
setting — a setting can never turn off an env-forced capability.

The module is **leaf-light**: stdlib only at import, with `fleet_settings` and
`audit` imported lazily inside functions, because the stdio MCP subprocess, the
`operations` layer, and the nav builder all have to ask "is this on?" without
dragging in FastAPI.

### 2. Enablement is asymmetric, and the asymmetry is the point

> **`dev-only`, `dangerous`, `test-suppressor` and `internal` capabilities are
> `("env",)` — environment variable only. `privileged` capabilities keep a
> setting, so they stay runtime-toggleable.**

This is the decision most likely to be re-litigated, so the reasoning is
recorded in full:

- **The dangerous ones must not be a click.** `dev.auto_approve` lets a robot
  satisfy a gate meant for a human; `acs.rule_write` writes an unsupported,
  version-specific schema that ACS itself caches. Requiring an env var **plus a
  service restart** (ADR-0042 — the Shawl-supervised `admz` service) means
  enabling either is a deliberate act by somebody with service control on the
  box, not something a browser and a group membership can reach. It costs
  nothing operationally: you only ever enable these while setting up a dev rig,
  which is a restart moment anyway.
- **The privileged ones must be stoppable without a restart.** Survey mode,
  device event ingest and the ACS poller run **background loops that contact
  devices**. If one misbehaves at 2am the operator needs it stopped *now*, not
  after a service restart — so they keep a fleet setting and the reveal-gated
  toggle. They were already shipped as settings; making them env-only would
  have been a regression.
- **Test-suppressors are env-only** for a mechanical reason: `tests/conftest.py`
  must set them *before import*, when no database exists.
- **The LLM can never enable anything.** Every `setting_key` in the registry is
  in `PROTECTED_SETTING_KEYS` (ADR-0020), which `set_fleet_setting` and
  unauthenticated REST callers already refuse. Structural, not policy — the
  same mechanism that has protected the survey keys since ADR-0030.

### 3. Loud in five places

1. **Startup log.** `startup_lines()` returns `(level, message)` *data*, not log
   calls, so the API process, the MCP subprocess and the CLI banner each emit it
   their own way and all three stay testable. One INFO line when clean; one
   **WARNING per active capability** that is not production-appropriate.
2. **Audit.** `set_enabled` writes an attributed `capability.enable` /
   `capability.disable` row. An env-enabled capability *cannot* be audited at
   enable-time — there is no event and no actor — so it gets a once-per-boot
   `capability.active` row attributed to `system`. The honest audit answer for
   an env capability is "it was on at boot", not "alice turned it on".
   `test-suppressor` capabilities are excluded from the boot row: a suppressor
   being on is a test-harness artifact, not a granted power, and a boot-time
   writer firing under the two suite-wide suppressors would have written into
   the operator's real audit database from any test that forgot to isolate
   `ADMZ_HOME`.
3. **A topbar chip on every page** — red for the loud classes, amber for
   `privileged`, absent when nothing is active, so an ordinary install never
   sees it. It is also how the hidden page gets legitimately discovered once
   something is already on.
4. **Diagnostics.** `GET /api/health` gains `advanced_capabilities: [id, …]` —
   ids only, unauthenticated, so `curl` answers "what mode was this running
   in?". `GET /api/capabilities` (authenticated) returns the full table plus
   live state, and the `get_advanced_capabilities` MCP tool returns the *same
   shape* from the same shaping function.
5. **The chat surface.** When a non-production-appropriate capability is active,
   the system prompt gains a block naming it and what it changes. On an
   ordinary install the builder returns `""` and the prompt is byte-identical
   to before the slot existed (the same conditional contract ADR-0039/0051
   sections keep). Without it, the model confidently tells the operator
   "waiting for your approval" while a script is approving it.

### 4. Hidden, but not by obscurity alone

`/settings/advanced` is unlinked (not on `/settings`, not in the nav), gated by
`require_reveal_permission` — the same bar that guards plaintext device
credentials — and every toggle requires typing the capability's id plus a
free-text reason that lands in the audit row. Under `ADMZ_AUTH_BACKEND=none`
there is no identity to check, so the page renders **read-only**: its
diagnostic value is highest on exactly the unauthenticated dev box where these
switches get used, and a hard 403 would hide it there. It informs; it refuses
to act.

### 5. Read-only on the MCP surface, permanently

Exactly one tool, `get_advanced_capabilities`, mirroring the REST read. **There
is deliberately no enable/disable tool and there never should be** — these
switches change how the model's own gates behave, so a write tool would put the
LLM one call away from enabling its own approver. Enforced twice on purpose: no
tool exists, *and* every setting key is protected, so removing one half does
not open the hole. The reasoning lives in `admz/mcp/tools/capabilities.py`
beside the code, not only here, so a future contributor does not "complete the
pair" in good faith.

### 6. This is not a security boundary

Stated as a decision, not a caveat, because it drove every choice above:
**anyone who can set an environment variable, edit `fleet_settings`, or restart
the Windows service already owns the machine.** The registry exists to prevent
**accidents** and to make **state legible**. Nothing here should be described,
tested, or reviewed as a defence against an attacker.

Two consequences follow directly. First, the registry **declares, it does not
enforce**: `ADMZ_DEV_AUTO_APPROVE` is still read only by
`tools/dev_auto_approve.py`, which posts to the real confirmation endpoint
exactly as a browser does — the server cannot tell the difference and is not
made to try. Making it try would require the tool to identify itself, which is
an authentication mechanism wearing a registry's clothes, and it would buy
nothing against the only threat model that matters here. Second, a capability
never softens ADR-0034: at most it changes *who may satisfy* a gate or *what
runs in the background*; a gate that exists still fires, still needs its link
and password, and still lands its `confirm.approve` audit row.

## Consequences

**Good**

- The issue's question is answerable from any of four places without reading
  source: the startup log, `curl /api/health`, the topbar chip, or the chat
  console — and now from an agent's tool call during a diagnosis.
- One truthiness parse replaced three. Two exotic values changed meaning *on
  purpose*: `ADMZ_DISABLE_ONBOARDING_PROBES=0` used to mean **on** (a bare
  `if os.getenv(...)`) and now means off; `ADMZ_EVENT_INGEST=true` used to mean
  **off** (`== "1"`) and now means on. Both are recorded, tested fixes.
- New dangerous features **register** instead of inventing another env var —
  #131 (ACS rule writing) is already declared and not yet built, which is the
  abstraction proving its worth before its first user arrives.
- A drift guard scans `admz/` + `tools/` for `ADMZ_*` reads and fails until
  every name is classified as a capability, as `ORDINARY_CONFIG`, or as
  `NOT_ENV_VARS`. Adding an env var now forces a one-line reviewed decision —
  which is the real deliverable, because a registry that silently goes stale is
  worse than no registry.

**Costs and risks accepted**

- **Chip fatigue** is the live risk: a box with three suppressors on shows a
  permanent red chip and everyone stops seeing it. Mitigated by keeping
  `internal` silent, keeping `ADMZ_AUTH_BACKEND` out of the registry entirely
  (it already warns at startup, and registering it would flag every dev box
  forever), and by telling the chat surface to mention a capability when it is
  load-bearing rather than every turn.
- **The registry can lie if a call site forgets to delegate.** Slice 2 removed
  that gap for all nine; the invariant tests and the drift guard keep it
  closed, but the failure mode is real and worth naming.
- **The hidden page could become a discovery mechanism** for dangerous
  features. It is unlinked and reveal-gated, the chip that leads to it only
  appears once something is already on, and the dangerous rows are not
  toggleable there at all.
- **`production_appropriate` is an explicit field**, not derived from the
  danger class, so adding a class is a decision rather than a silent
  reclassification. The invariant test pins the two together in both
  directions.

## Out of scope (named, not hidden)

- **Server-enforced dev auto-approval.** Making the server refuse approvals not
  from a human is a different feature with a different threat model; it needs
  the approving tool to identify itself. If a deployment genuinely needs it,
  that is its own issue.
- **A capability that lowers a confirmation gate.** Not deferred — *excluded*.
  ADR-0034 was written after a real incident; a switch that reversed it would
  be reversing that lesson.
- **Pulling ordinary config into the registry.** 53 of the 64 `ADMZ_*` env vars
  are paths, timeouts, model names and credentials. Registering them would
  dilute exactly the signal the registry exists to give.
- **An MCP write tool.** Excluded permanently, for the reasons in §5.

## Rollout

Three slices, each independently useful:

1. **PR #134** — the registry, the read predicates, `startup_lines()`, the
   `/api/health` id list, and the table-invariant + drift-guard tests. No call
   site changed, so nothing could regress.
2. **PR #136** — call-site migration to `is_active`, `set_enabled` + the audit
   rows, `GET/POST /api/capabilities`, the reveal-gated `/settings/advanced`
   page, and the topbar chip. All of the compatibility risk, behind slice 1's
   already-merged declarations.
3. **This slice** — the read-only `get_advanced_capabilities` MCP tool, the
   conditional chat-prompt block, this ADR, and the doc cross-references.

A tenth capability, `dev.test_auth`, landed between slices 2 and 3 (PR #141) as
a *registration* rather than a bespoke flag — the first outside proof the
abstraction earned its place. Its synthetic principal is deliberately
unprivileged, and `admz/__main__.py` refuses to start the server at all when it
is active on a non-loopback bind, with no override.
