# Plan: advanced capability switches — one registry for hidden, dangerous, and privileged-install features

Status: **complete — all three slices shipped.** Slice 1 PR
[#134](https://github.com/dnobj/admz/pull/134), slice 2 PR
[#136](https://github.com/dnobj/admz/pull/136), slice 3 closes GH
[#132](https://github.com/dnobj/admz/issues/132). The decision this plan
produced is recorded as
[ADR-0052](../specification/decisions/0052-advanced-capability-switches.md);
where this plan and the ADR differ, **the ADR wins** — it was written from the
shipped code.
Blocks marked *"as shipped"* / *"Correction from slice 1"* record where the
implementation departed from what is written around them; **they win**, and slice 2
should be built against them rather than the surrounding prose.
The five open decisions are **RESOLVED** (Master, 2026-07-28) — see
[Master resolutions](#master-resolutions) at the end, which supersede the
recommendations in the Open-decisions section. In short: the registry
**declares, it does not enforce**; `/settings/advanced` is read-only under
`ADMZ_AUTH_BACKEND=none`; `ADMZ_MCP_NO_SCHEDULER` is class `internal`; this
ADR takes **0052** (0051 goes to demo-inference, which is further along); and
`ADMZ_AUTH_BACKEND` appears as read-only context, not a registry row.

## Goal

Give ADMZ **one declared place** where powerful, dangerous, or privileged-install
capabilities live, so an operator can answer *"what non-default powers is this
installation running with?"* without reading source.

The pattern already exists — nine times, each invented separately. This plan does not
add capabilities. It adds a **registry** that declares the ones we have, a **hidden,
reveal-gated surface** for the few that are runtime-toggleable, and **five specific
places** where an active dangerous capability becomes impossible to miss.

## Non-goals

- **Not a security boundary.** This is the issue's explicit framing and it drives
  every design choice below. Anyone who can set an environment variable, edit
  `fleet_settings`, or restart the Windows service already owns the machine. The
  registry prevents **accidents** and makes **state legible**. Nothing here should be
  described, tested, or reviewed as a defence against an attacker.
- **Not a replacement for the confirmation gate (ADR-0034).** Advanced capabilities
  *modify* how gates behave — who may approve, whether a background loop runs. They
  never remove a gate. Test 18 exists to prove the gate still fires with the most
  dangerous capability active.
- **Not a config-management system.** 53 of the 64 `ADMZ_*` env vars are ordinary
  config (paths, timeouts, auth backend, model names). They stay exactly as they are.
  Pulling them into the registry would dilute the signal the registry exists to give.
- **No new capabilities.** #131 (ACS rule writing) is the first *new* one, and it
  lands by registering — not in this plan.
- **No change to how any existing flag is read.** Every env var keeps its name and its
  meaning. `tools/dev_auto_approve.py` and `tests/conftest.py` are untouched (one
  deliberate exception, below).

---

## Current state — the inventory, with evidence

### The numbers

A scan of `admz/` + `tools/` for `os.getenv` / `os.environ` reads plus the
`*_ENV = "ADMZ_…"` constant idiom finds **64 distinct `ADMZ_*` env vars actually
read**, across 33 files. A further **5 are test-only** (`ADMZ_E2E_API_KEY`,
`ADMZ_E2E_BASE_URL`, `ADMZ_LIVE_CHAT_TESTS`, `ADMZ_CHAT_TEST_URL`,
`ADMZ_CHAT_TEST_RETRIES` — `tests/e2e/conftest.py:36` and friends) and **one is
written, not read**, by ADMZ for a child process (`ADMZ_GH_TOKEN`,
`admz/snapshot/git_repo.py:517`, consumed by the generated askpass script at
`:131-134`). Three names that *look* like env vars are not: `ADMZ_VERSION` is an
import alias (`admz/survey/runner.py:21`), `ADMZ_WEBHOOK_PATH` is a module constant
(`admz/demos/inference/observability.py:78`), and `ADMZ_PRINCIPAL_` is a docstring
prefix. The issue's "68" and this "64 + 5 + 1" are the same population counted
differently.

Of those 64, **9 are capability switches**. The rest are ordinary config.

### The capability candidates (evidence)

| Flag / switch | Read at | What it does | Class |
|---|---|---|---|
| `ADMZ_DEV_AUTO_APPROVE` | `tools/dev_auto_approve.py:65` (const), `:79` | Guards the standalone approver that completes `url_*` gates unattended. **Never appropriate in production.** | dev-only |
| `ADMZ_DISABLE_ONBOARDING_PROBES` | `admz/onboarding.py:39` (const), `:65` | Suppresses the network probes onboarding runs against a new device | test-suppressor |
| `ADMZ_DISABLE_GITHUB_APP_PUSH` | `admz/github_app/push.py:28` | Short-circuits before minting a real installation token / pushing | test-suppressor |
| `ADMZ_MCP_NO_SCHEDULER` | `admz/mcp/server.py:4522`; set by ADMZ at `admz/chatbot/mcp_pool.py:116`, `admz/chatbot/voice.py:223` | Stops a pool subprocess from starting a second scheduler (H-1 dup-scheduler fix) | internal role |
| `ADMZ_ACS_FIREBIRD` | `admz/modules/acs_pro/firebird.py:58` (env) **or** `acs_firebird_enabled` setting at `:60` | Direct reads of the ACS Firebird database — unsupported, version-specific schema | privileged |
| `ADMZ_EVENT_INGEST` | `admz/events/config.py:74` (env) **or** `event_ingest_enabled` setting at `:77` | Opens device-direct VAPIX WebSockets fleet-wide | privileged |
| `ADMZ_ACS_EVENT_INGEST` | `admz/events/config.py:59` (env) **or** `acs_event_ingest_enabled` setting at `:62` | Polls the ACS recorded-event log for action-rule firings | privileged |
| Survey / contributor mode | `admz/survey/secrets.py:87-88` — setting `survey_mode_enabled` only, **no env** | Privileged installs that survey devices and open upstream PRs (ADR-0030). Callers: `admz/survey/runner.py:88`, `admz/api/routes/survey.py:76` | privileged |
| ACS action-rule **writing** (#131) | *not built* | Direct Firebird **writes** | dangerous |

Two flags that read like capabilities and are **not**: `ADMZ_DEV_API_KEY`
(`tools/dev_auto_approve.py:201`) and `ADMZ_DEV_CONFIRM_PASSWORD`
(`tools/dev_auto_approve.py:66`) are **credential inputs** to the auto-approver, not
switches. They stay env-only and undeclared; the registry references them as the
`dev.auto_approve` entry's documented companions so the docs live in one place.

### Flags deliberately left as ordinary config

Worth naming, because each is a plausible candidate someone will re-raise:

- **`ADMZ_AUTH_BACKEND=none`** (`admz/api/main.py:72`) — already has its own dedicated
  loud startup WARNING (`main.py:57-86`, called from the lifespan at `:93`). It is a
  *deployment posture*, not a switch, and duplicating it into the registry would make
  every dev box show a red chip permanently. The registry should *reference* it in the
  advanced page's context ("this install also runs anonymous auth"), not own it.
- **`ADMZ_AUTH_INSECURE_BIND_OK`** (`admz/__main__.py:241`) — already refuses to start
  without it and prints a WARNING with it (`__main__.py:243-259`). Same reasoning.
- **`ADMZ_VERIFY_SSL`** (`admz/ssl_config.py:40`) — `False` is the *default*
  (`ssl_config.py:11`), so nearly every install would light the indicator. Turning it
  *on* raises safety. Not a capability.
- **`ADMZ_LDAP_BIND_PASSWORD`**, **`ADMZ_GEMINI_API_KEY`** — credentials.
- Everything else: paths (`ADMZ_HOME`, `ADMZ_DB_PATH`, … `admz/paths.py:29-72`),
  timeouts, retry counts, model names, git author identity, CORS origins.

### The two precedents worth copying

**Module enablement (ADR-0039/0040)** — the model. `admz/modules/acs_pro/config.py:68-74`
is one function, `acs_enabled()`, and *every* factory in the module consults it, so ACS
Pro contributes **zero** nav, tools, or prompt until connected
(`admz/modules/registry.py:49-53` registers it unconditionally; the surface self-gates).
Config is one JSON blob in `fleet_settings` under a single key (`config.py:18`), with
**no** password field. The lesson: **one predicate, consulted everywhere, and no
footprint until it returns True.**

**Survey / contributor mode (ADR-0030)** — the counter-example that still works.
`admz/survey/secrets.py:87-88` is a plain fleet-setting read; its seven keys are all in
`PROTECTED_SETTING_KEYS` (`admz/fleet_settings.py:75-81`) so MCP and anonymous callers
cannot write them; the PAT is Fernet-encrypted under the registry's own key
(`secrets.py:40-51`). It has a Settings page (`/settings/survey`,
`admz/api/routes/survey.py:90`) linked from the main Settings card
(`admz/api/templates/settings.html:182-186`). The lesson: **the storage and protection
pattern is right; only the *declaration* is missing** — nothing anywhere says "survey
mode is a privileged capability."

**The hybrid already exists too.** `admz/events/config.py:56-64` and `:72-79` read
**env OR setting**, defaulting off, wrapped in `try/except` so a settings-store failure
can never break startup. `admz/modules/acs_pro/firebird.py:57-60` does the same. This
is the shape the registry should generalize, not invent.

### The gate model the switches must not touch

ADR-0034 removed flat refusals: **every** destructive action routes through the
link/widget gate, including registry actions like `delete_device` and
`accept_baseline`, which get `url_only` **action sessions** that "fleet-level overrides
do not soften". Plan steps can only ever *raise* their risk floor, never lower it
(`RestoreBuilder` / `PlanEngine.create_plan`). An advanced capability that lowered a
gate would be reversing an ADR that was written after a real incident. The registry
therefore only ever affects **who may satisfy a gate** (the dev approver) or **whether
a background loop runs** — never whether the gate exists.

### Three different truthiness parses, today

This matters for migration:

| Site | Parse | Consequence |
|---|---|---|
| `admz/onboarding.py:65` | `if os.getenv(_DISABLE_ENV):` — **any non-empty string** | `ADMZ_DISABLE_ONBOARDING_PROBES=0` currently means **ON**. A latent footgun. |
| `admz/github_app/push.py:28`, `admz/mcp/server.py:4522`, `admz/events/config.py:59,74`, `admz/modules/acs_pro/firebird.py:58` | `== "1"` | `=true` does nothing |
| `admz/survey/secrets.py:88`, `admz/events/config.py:62,77`, `admz/modules/acs_pro/firebird.py:60` (setting side) | `in ("1","true","yes","on")` | the intended behaviour |

### What is missing

No inventory. No shared danger classification. No audit row when a capability is
enabled. No startup line saying which are active. `/api/health`
(`admz/api/main.py:322-354`) returns version + registry state and nothing about mode.
And the sharpest gap: **`ADMZ_DEV_AUTO_APPROVE` is read only inside
`tools/dev_auto_approve.py`.** The tool posts to the real endpoint
(`dev_auto_approve.py:241`) exactly as a human's browser does — the server cannot tell
the difference, and has no idea the capability exists. It writes its own loud
`dev.auto_approve` audit row afterwards (`:166-189`), which is good practice and also
the only trace.

---

## Design

### 1. The registry — `admz/capabilities.py`

One new module, **leaf-light**: stdlib + typing only at import time, with
`fleet_settings` and `audit` imported lazily inside functions. This is the discipline
`admz/modules/contract.py:15-19` documents and `test_modules_import_isolation`
enforces — the stdio MCP subprocess and the `operations` layer must be able to ask
"is this capability on?" without dragging in FastAPI or an executor.

```python
@dataclass(frozen=True)
class Capability:
    id: str                       # "dev.auto_approve" — dotted, stable, the audit key
    title: str                    # "Dev auto-approver"
    description: str              # one operator-readable sentence
    danger: str                   # dev-only | dangerous | privileged | test-suppressor | internal
    production_appropriate: bool  # False → WARNING at startup + red chip when active
    enable_via: Tuple[str, ...]   # ("env",) or ("env", "setting") or ("setting",)
    env_var: str = ""             # the EXISTING name, unchanged
    setting_key: str = ""         # fleet_settings key; required iff "setting" in enable_via
    companion_env: Tuple[str, ...] = ()   # credentials/inputs, documented not declared
    since: str = ""               # ADR / issue provenance, e.g. "ADR-0030"
    notes: str = ""               # why it exists; what breaks if you leave it on
```

`CAPABILITIES: Tuple[Capability, ...]` is one module-level literal — the same shape as
`PROTECTED_SETTING_KEYS` (`fleet_settings.py:51-91`) and `EXPECTED_TOOL_ORDER`
(`tests/test_mcp_tool_order.py:20`): a table you read top to bottom to know the whole
truth.

**Danger classes — five, deliberately few:**

| Class | Meaning | Production? |
|---|---|---|
| `dev-only` | Never appropriate outside development | ❌ loud |
| `dangerous` | Writes outside ADMZ's normal gated write paths | ❌ loud |
| `privileged` | Legitimate but a privileged install profile | ⚠️ amber |
| `test-suppressor` | Turns *off* production behaviour for determinism | ❌ loud |
| `internal` | Set by ADMZ for its own subprocesses; never operator-facing | ✅ silent |

**Public surface:**

```python
def get(cap_id) -> Optional[Capability]
def is_active(cap_id) -> bool                                # THE read path — env, then setting
def source_of(cap_id) -> str                                 # "" | "env" | "setting"
def active_capabilities() -> List[ActiveCapability]          # id + capability + source
def active_ids() -> List[str]                                # what /api/health reports
def set_enabled(cap_id, on, principal, *, reason) -> None    # setting-enablable only (slice 2)
def startup_lines() -> List[Tuple[int, str]]                 # (loglevel, message) — no logging here
def truthy(raw) -> bool                                      # ONE parse: {"1","true","yes","on"}
```

> **Naming, as shipped (slice 1).** The read predicates are `is_active` /
> `active_capabilities`, not `is_enabled` / `active`. `is_enabled` is already the
> name of three *existing* module-level predicates that stay
> (`secrets.is_enabled`, and by analogy `config.event_ingest_enabled`,
> `firebird.firebird_enabled`), so reusing it for the registry would have made
> `capabilities.is_enabled` and `secrets.is_enabled` two different things one
> import apart. There are deliberately **no aliases** — one name per concept.

`is_active` reads **env first, then setting** — matching `events/config.py:59-64`
exactly (env wins; a setting cannot turn off an env-forced capability). Unknown ids
return `False` and log once. Every settings read is wrapped in `try/except` and
degrades to env-only: config must never break a request, the house rule visible at
`acs_pro/config.py:48` and `events/config.py:79`.

`startup_lines()` returns data, not log calls, so it is trivially testable and the API
process, the MCP process, and the CLI banner can each emit it their own way.

### 2. Enablement mechanism — **both, declared per capability, asymmetric by danger**

The real constraint, stated plainly:

- **Env var**: requires a service restart (ADR-0042 — Shawl-supervised `admz` service
  running as LocalSystem), invisible to the UI, and **unattributable** — nobody knows
  who set it or when.
- **Settings store**: runtime-changeable, attributable, auditable — and reachable from
  a web page.

Neither is right for everything, and the registry does not need to pick one globally.
It needs to make the choice **declared** rather than accidental. The rule:

> **`dev-only`, `dangerous`, and `test-suppressor` capabilities are `("env",)` —
> env-only, by design, so they cannot be enabled from a browser.
> `privileged` capabilities are `("env", "setting")` — runtime-toggleable.**

Reasoning:

1. **The most dangerous ones must not be a click.** `dev.auto_approve` lets a robot
   satisfy a human-only gate; `acs.rule_write` (#131) writes an unsupported database
   directly. Requiring an env var + a service restart means enabling either is a
   deliberate act by someone with service control on the box, not a checkbox anyone
   with a browser and a reveal group can find. This costs nothing operationally — you
   only ever enable these while setting up a dev/test rig, which is a restart moment
   anyway.
2. **Privileged capabilities must be stoppable at runtime.** Survey mode and event
   ingest run **background loops that contact devices**. If one misbehaves at 2am the
   operator needs to stop it now, not after a service restart. They are also already
   shipped as settings (`survey/secrets.py:87`, `events/config.py:63,79`) — making them
   env-only would be a regression.
3. **The LLM can never enable anything.** Every `setting_key` in the registry joins
   `PROTECTED_SETTING_KEYS` (`fleet_settings.py:51`), which the MCP `set_fleet_setting`
   tool and unauthenticated REST callers already refuse (`is_protected_setting`, `:94`).
   That is structural, not policy — the same mechanism that already protects the seven
   survey keys.
4. **Test-suppressors are env-only** because they must be settable *before* import by
   `tests/conftest.py:25,32`, before any DB exists.

Survey mode gains an env alias (`ADMZ_SURVEY_MODE`) it never had, so a locked-down
privileged install can force it on without a writable settings row. Purely additive;
the setting stays authoritative when the env var is unset.

> **Correction from slice 1, as shipped.** `survey.contributor` is declared
> `enable_via=("setting",)` — **not** `("env","setting")` — until slice 2. The env
> alias above does not exist yet, and slice 1 changes no call site, so declaring
> `ADMZ_SURVEY_MODE` would have made the registry *lie*: setting it would light the
> capability in `/api/health`, the startup log, and the chip while
> `survey/secrets.py` carried on reading only the setting and survey mode stayed
> off. A registry whose first release reports a switch that does nothing is worth
> less than no registry. **Slice 2 adds `ADMZ_SURVEY_MODE` and flips the row to
> `("env","setting")` in the same commit as the call-site delegation**, which is
> the first moment the declaration becomes true.
>
> Consequence for the invariant test (test 12): the privileged half of the
> asymmetry rule is asserted as **`"setting" in enable_via`**, not
> `enable_via == ("env","setting")`. That is the operative property anyway —
> privileged capabilities must stay *runtime-toggleable* so a misbehaving
> background loop can be stopped without a service restart. The strict half
> (`dev-only` / `dangerous` / `test-suppressor` / `internal` ⟹ `("env",)`) is
> asserted exactly, because that is the half that keeps the dangerous switches
> out of a browser.

### 3. Hiding — three layers, and a name for what each buys

1. **No link, no nav, ever.** `/settings/advanced` is not referenced from
   `settings.html` and is not in `_assemble_nav_sections`
   (`admz/api/templating.py:268-345`). You reach it by typing the URL. A test asserts
   the string `/settings/advanced` does not appear in the rendered `/settings` HTML.
2. **A reveal gate, not just obscurity.** The route calls
   `require_reveal_permission` (`admz/authz.py:139-160`) — the same
   `ADMZ_REVEAL_GROUPS` / `Administrators` bar that guards plaintext device
   credentials. This is the existing, tested "you must be an admin to see the scary
   thing" primitive; reusing it is free. Under `ADMZ_AUTH_BACKEND=none` there is no
   identity, so the anonymous fallback (`authz.py:119-120`) applies: the page renders
   **read-only** — you can see what is active, you cannot toggle anything. That keeps
   the diagnostic value on a dev box while removing the accident path (see
   [Open decision 2](#open-decisions-for-the-owner)).
3. **A typed acknowledgement for every toggle.** Turning a capability on from that page
   requires typing its `id` into a confirm field, so no stray click enables anything,
   and the POST carries a free-text `reason` that lands in the audit row. Deliberately
   **not** the ADR-0034 `url_*` gate: that gate exists for device-affecting operations
   and reusing it for a config toggle would muddy the model the issue says not to
   replace.

**Rejected:** a magic query param (`?advanced=1` — bookmarkable, shareable, screenshot-
leakable); a build-time flag (undiagnosable at runtime, which defeats the point); a
separate port (deployment complexity for no gain).

### 4. Loudness — five specific places

1. **Startup log.** `_log_active_capabilities()` in `admz/api/main.py`, called from the
   lifespan immediately after `_warn_anonymous_auth_backend()` (`main.py:93`), on the
   existing `admz.security` logger. Exactly one INFO line when clean
   (`advanced capabilities: none`), and one **WARNING per capability** when any
   `production_appropriate=False` one is active, naming the capability, its source
   (`env`/`setting`), and what it does. The same call goes in the MCP server entrypoint
   (`admz/mcp/server.py`) — the MCP subprocess is a separate process with its own env —
   and into the `python -m admz api` banner (`admz/__main__.py:403`, printed to stderr
   so it survives a piped stdout).
2. **Audit at enable-time.** `set_enabled` writes `capability.enable` /
   `capability.disable` via the existing `audit.record_event` helper
   (`admz/audit.py:280-307`), with `resource=f"capability:{id}"` and
   `details={danger, source, reason}`. **Env-enabled capabilities cannot be audited at
   enable-time** — there is no event and no actor. They get a once-per-boot
   `capability.active` row with `requester="system"` instead, written from the same
   startup hook. Saying this plainly matters: the audit answer for an env capability is
   "it was on at boot", not "alice turned it on".
   **Correction from slice 1, as shipped: `test-suppressor` capabilities get no boot
   row** (`capabilities._boot_auditable`). A suppressor being active is a test-harness
   artifact — `tests/conftest.py:25,32` sets both before any app exists — not a power
   an operator granted, and the audit trail exists to record the latter. The other
   three loudness channels (startup WARNING, `/api/health`, the chip) still cover
   suppressors in full, so no operator-facing signal is lost. It also removes a real
   hazard: every store binds its DB path at import, so a boot-time writer firing under
   the two suite-wide suppressors would have written into the operator's real audit
   database from any test that forgets to isolate `ADMZ_HOME` — the project's standing
   test-isolation lesson. The predicate is an *exclusion* (`not
   production_appropriate and danger != "test-suppressor"`), not an allow-list, so a
   danger class added later is audited by default.
3. **Persistent console indicator.** A chip in the topbar of `base.html`
   (`:19-86`, beside the theme/notifications buttons), rendered from a new
   `nav.advanced` key populated in the `templating.py` nav builder. Red for
   `dev-only`/`dangerous`/`test-suppressor`, amber for `privileged`, absent when
   `active_capabilities()` is empty (so a normal install sees nothing, ever). Because it lives in
   `base.html` it appears on every page **and** behind the console dock. Clicking it
   goes to `/settings/advanced` — which is how the page gets legitimately discovered
   once something is already on.
4. **Diagnostics output.** `GET /api/health` (`admz/api/main.py:322`) gains
   `"advanced_capabilities": ["dev.auto_approve", …]` — **ids only, never values**, so
   a `curl` or a support bundle answers "what mode was this running in?" without auth
   games. `GET /api/capabilities` (authenticated) returns the full declaration table
   plus enabled/source for the advanced page and for support.
5. **The chat surface.** When any `production_appropriate=False` capability is active,
   the chatbot's system prompt gains a one-line fragment ("this installation is running
   with `dev.auto_approve` ON — approvals may be completed by an automated approver").
   Without it the model confidently tells the operator "waiting for your approval" when
   a robot is about to approve it — the exact class of confusion the `role='event'`
   console notes were added to fix.

### 5. Migration

| Today | Registered as | Class | `enable_via` | Call-site change |
|---|---|---|---|---|
| `ADMZ_DEV_AUTO_APPROVE` | `dev.auto_approve` | dev-only | `("env",)` | none in slice 1–2; `tools/dev_auto_approve.py` keeps its own guard (`:65,79`) |
| `ADMZ_DISABLE_ONBOARDING_PROBES` | `test.no_onboarding_probes` | test-suppressor | `("env",)` | `onboarding.py:65` → `capabilities.is_active(...)` |
| `ADMZ_DISABLE_GITHUB_APP_PUSH` | `test.no_github_push` | test-suppressor | `("env",)` | `github_app/push.py:28` → `is_active(...)` |
| `ADMZ_MCP_NO_SCHEDULER` | `runtime.no_scheduler` | internal | `("env",)` | `mcp/server.py:4522` → `is_active(...)`; setters unchanged ([Open decision 3](#open-decisions-for-the-owner)) |
| `ADMZ_ACS_FIREBIRD` / `acs_firebird_enabled` | `acs.firebird_read` | privileged | `("env","setting")` | `firebird.py:57-60` body → `is_active(...)` |
| `ADMZ_EVENT_INGEST` / `event_ingest_enabled` | `events.device_ingest` | privileged | `("env","setting")` | `events/config.py:72-79` body → `is_active(...)` |
| `ADMZ_ACS_EVENT_INGEST` / `acs_event_ingest_enabled` | `events.acs_poll` | privileged | `("env","setting")` | `events/config.py:56-64` body → `is_active(...)` |
| `survey_mode_enabled` | `survey.contributor` | privileged | `("setting",)` in slice 1 → `("env","setting")` in slice 2 (see the correction above) | `survey/secrets.py:87-88` body → `is_active(...)`; `KEY_ENABLED` re-exported |
| *(#131)* | `acs.rule_write` | **dangerous** | `("env",)` | declared here, built there |

**Backward compatibility is the load-bearing requirement**, and it is achieved by
keeping every env var name, every setting key, and every default identical. The public
predicates (`secrets.is_enabled`, `config.event_ingest_enabled`,
`firebird.firebird_enabled`) keep their names and signatures and become one-line
delegations, so their ~20 existing callers are untouched. `tests/conftest.py:25,32`,
every `monkeypatch.setenv` in the suite, and `tools/dev_auto_approve.py` all keep
working with no edit.

**One deliberate behaviour change, and it needs the owner's nod:** unifying on
`truthy()` = `{"1","true","yes","on"}` makes `ADMZ_DISABLE_ONBOARDING_PROBES=0` mean
**off** where it currently means **on** (`onboarding.py:65` treats any non-empty string
as true). This is a bug fix — nobody sets a disable flag to `0` intending to disable
probes — and `conftest.py:25` sets `"1"`, so the suite is unaffected. It gets its own
test (test 2b) so the change is recorded rather than discovered.

**A registry that drifts is worse than no registry**, so migration ships with an
enforcement test (test 12b): scan `admz/` + `tools/` for `ADMZ_*` env reads and assert
every name is either declared in `CAPABILITIES` or listed in an explicit
`ORDINARY_CONFIG` tuple in the same file. Adding an env var then forces a one-line,
reviewed classification decision — which is the real deliverable of this issue.

### 6. MCP / API surface

**REST**

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/capabilities` | Full declaration table + `{enabled, source}`. `require_authenticated_principal`. Read-only. |
| `POST` | `/api/capabilities/{id}` | `{enabled, reason, confirm_id}`. Refuses env-only ids with 409 and an explanatory message; `require_reveal_permission`; writes the audit row. |
| `GET` | `/api/health` | Gains `advanced_capabilities: [id, …]`. Unauthenticated, ids only. |
| `GET` | `/settings/advanced` | The hidden page. Unlinked, reveal-gated, read-only for anonymous. |

**MCP** — exactly **one** new tool, in a new `admz/mcp/tools/capabilities.py`:

- `get_advanced_capabilities` — read-only; returns active ids, their danger class,
  source, and description.

**There is deliberately no enable/disable tool, and there never should be.** The model
must not be able to turn on a capability that changes how its own gates behave. This is
enforced twice: no tool exists, and every `setting_key` is in `PROTECTED_SETTING_KEYS`
so even `set_fleet_setting` is refused. Test 11 asserts no tool name matches
`set_.*capabilit`.

Adding a tool touches the frozen wire order, so `EXPECTED_TOOL_ORDER`
(`tests/test_mcp_tool_order.py:20`) must be updated **in the same commit** —
`test_mcp_tool_order.py:7` says so, and `tests/test_acs_pro_module.py:286-290` asserts
the device tools stay a prefix. That is why the tool lands in slice 3, not slice 1.

---

## File-level implementation

### New

| Path | Contents |
|---|---|
| `admz/capabilities.py` | `Capability`, `CAPABILITIES`, `ORDINARY_CONFIG`, `truthy`, `is_active`, `source_of`, `active_capabilities`, `set_enabled`, `startup_lines`. Stdlib-only imports |
| `admz/api/routes/capabilities.py` | `GET /api/capabilities`, `POST /api/capabilities/{id}` |
| `admz/api/templates/advanced_settings.html` | The hidden page: one row per capability — id, description, danger badge, enabled/source, and a typed-ack toggle for settings-enablable ones only |
| `admz/mcp/tools/capabilities.py` | `TOOLS` = `[get_advanced_capabilities]` (slice 3) |
| `tests/test_advanced_capabilities.py`, `tests/test_capabilities_migration.py`, `tests/test_advanced_settings_page.py` | See test plan. **Not** `tests/test_capabilities.py` — that name is already taken by the atlas *device*-capabilities suite (`axis_api_atlas.capabilities`), an entirely different concept |
| `docs/specification/decisions/00NN-advanced-capability-switches.md` | New ADR (number: see [Open decision 4](#open-decisions-for-the-owner)) |

### Changed

| Path | Change |
|---|---|
| `admz/api/main.py:93` | Call `_log_active_capabilities()` beside `_warn_anonymous_auth_backend()`; write the once-per-boot `capability.active` audit rows |
| `admz/api/main.py:322-354` | `/api/health` gains `advanced_capabilities` (ids only) |
| `admz/api/main.py` (router block) | Include the capabilities router |
| `admz/mcp/server.py` (startup) | Emit the same startup lines to stderr |
| `admz/mcp/server.py:4522` | `ADMZ_MCP_NO_SCHEDULER` read → `capabilities.is_active("runtime.no_scheduler")` |
| `admz/__main__.py:403` | Print active capabilities under the "Starting ADMZ API server" banner |
| `admz/onboarding.py:65` | → `capabilities.is_active("test.no_onboarding_probes")` (`_DISABLE_ENV` kept as a doc constant) |
| `admz/github_app/push.py:28` | → `capabilities.is_active("test.no_github_push")` |
| `admz/events/config.py:56-64, 72-79` | Bodies delegate; `event_ingest_enabled` / `acs_event_ingest_enabled` names and signatures unchanged |
| `admz/modules/acs_pro/firebird.py:57-60` | Body delegates; `firebird_enabled` unchanged |
| `admz/survey/secrets.py:87-88` | `is_enabled` delegates to `capabilities.is_active("survey.contributor")`; its own name + `KEY_ENABLED` unchanged. Same commit adds the `ADMZ_SURVEY_MODE` env alias and flips the row to `("env","setting")` |
| `admz/fleet_settings.py:51-91` | Add the capability setting keys to `PROTECTED_SETTING_KEYS` (they are already there for survey; add the three event/firebird keys) |
| `admz/api/routes/web.py:596` | `/settings` context unchanged — **no** link added (deliberate) |
| `admz/api/templating.py` (nav builder) | Populate `nav.advanced` from `capabilities.active_capabilities()`, inside a `try/except` like the module-nav block at `:324-344` |
| `admz/api/templates/base.html:19-86` | The topbar chip |
| `admz/chatbot` prompt builder | One-line fragment when a non-production-appropriate capability is active |
| `admz/mcp/tools/__init__.py:35-60` | Register `capabilities.TOOLS` (slice 3) |
| `tests/test_mcp_tool_order.py:20` | `EXPECTED_TOOL_ORDER` += `get_advanced_capabilities` (slice 3, same commit) |
| `docs/DEV_AUTO_APPROVE.md`, `README.md:258` | Cross-reference the registry |

---

## Test plan

Every store binds its DB path at import, so tests must isolate `ADMZ_HOME` /
`ADMZ_DB_PATH` or they pollute the real database — the standing house lesson. All
capability tests pass an explicit `db_path` or monkeypatch the env before touching
`fleet_settings`.

### Success cases

1. `is_active` is True iff the env var is set, for each env-only capability
   (monkeypatch on and off).
2. **Legacy parity — one test per migrated flag.** With only the *old* env var set, the
   *real* call site still behaves as before: onboarding probes skipped
   (`onboarding.py`), `installation_token_for_push()` returns `None`, the MCP server
   does not start a scheduler, `firebird_enabled()` True, `event_ingest_enabled()` True.
   This is the backward-compatibility guarantee; it must be a test, not a promise.
2b. `ADMZ_DISABLE_ONBOARDING_PROBES=0` now means **off** — the one recorded behaviour
   change.
3. `active_capabilities()` is `[]` on a clean env; returns exactly the enabled set otherwise.
4. **Env beats setting**: setting `false` + env set → enabled, `source == "env"`
   (matches `events/config.py:59` semantics).
5. Setting-only path: with no env var, writing the setting flips `is_active`;
   `source == "setting"`.
6. `/api/health` lists ids and never leaks a value or a setting name.
7. `set_enabled` writes exactly one `capability.enable` audit row carrying principal,
   danger class, source, and the operator's reason.
8. Startup emits one WARNING per non-production-appropriate active capability and
   exactly one INFO line when clean (`caplog`).
9. `/settings/advanced` returns 200 for a reveal-group principal; the rendered
   `/settings` page contains no `/settings/advanced` string; `nav.sections` contains no
   advanced entry.
10. The topbar chip renders iff `active_capabilities()` is non-empty, with the right severity class.
11. MCP exposes `get_advanced_capabilities` and **no** tool matching `set_.*capabilit`;
    `EXPECTED_TOOL_ORDER` matches the live list.
12. **Table invariants**: ids unique and dotted; `danger` in the allowed set;
    description non-empty; `"setting" in enable_via` ⟺ `setting_key` non-empty **and**
    present in `PROTECTED_SETTING_KEYS`; `dev-only`/`dangerous` ⟹ `enable_via ==
    ("env",)` and `production_appropriate is False`. *As shipped:* the strict
    `enable_via == ("env",)` half is asserted for `dev-only`, `dangerous`,
    `test-suppressor`, **and** `internal`; the privileged half is asserted as
    `"setting" in enable_via` (see the `survey.contributor` correction above).
    `production_appropriate` is pinned to the danger class in both directions —
    kept as an explicit field rather than a derived property so that adding a
    class is a decision, not a silent reclassification.
12b. **Drift guard**: every `ADMZ_*` env read found by scanning `admz/` + `tools/` is
    either declared in `CAPABILITIES` or listed in `ORDINARY_CONFIG`. *As shipped:*
    plus a third bucket, `NOT_ENV_VARS`, for the three `ADMZ_*` identifiers that are
    not env vars at all (an import alias, a module constant, a docstring prefix), so
    "unclassified" stays distinguishable from "not applicable"; and `admz/capabilities.py`
    itself is excluded from the scan — it *is* the classification, so naming a planned
    env var in a docstring would otherwise fail the guard. A companion assertion proves
    no literal `ADMZ_*` env read can hide in the excluded file.

### Failure cases

13. Unknown capability id → `is_active` returns `False`, logs once, never raises.
14. Garbage setting value (`"maybe"`, `""`, `"0"`) → off.
15. `fleet_settings` raising (patched to throw) → `is_active` still answers from env
    and does not propagate; a page that renders the chip still renders.
16. MCP `set_fleet_setting` refuses each capability setting key (protected-keys path).
17. Anonymous principal: `POST /api/capabilities/{id}` → 403; `GET` of the advanced
    page renders read-only with no toggle controls.
18. **The gate still holds.** With `dev.auto_approve` enabled server-side, an
    `url_only` operation still returns `blocked: true` with a confirm token — the
    capability changes *who may approve*, never *whether approval is required*
    (ADR-0034).
19. `set_enabled("dev.auto_approve", True, …)` raises (env-only), and `POST
    /api/capabilities/dev.auto_approve` returns 409 with a message naming the env var
    and the required restart.

### Manual, on the live deployment

- Start the service clean: `/api/health` shows `advanced_capabilities: []`, no chip,
  one INFO startup line.
- Enable `events.device_ingest` from `/settings/advanced`: chip appears amber on every
  page, audit log shows `capability.enable` attributed to the Windows principal, and
  the ingest loop actually starts (no restart).
- Set `ADMZ_DEV_AUTO_APPROVE=1` on the service and restart: chip goes red, startup log
  carries the WARNING, `/api/health` lists it, and `tools/dev_auto_approve.py`
  continues to work exactly as documented in `docs/DEV_AUTO_APPROVE.md`.
- Confirm `/settings` still shows no route to the advanced page.

---

## PR slicing

**Slice 1 — the registry + read-only surfaces.** ✅ **SHIPPED** (PR
[#134](https://github.com/dnobj/admz/pull/134)) *(small, zero behavioural risk,
independently useful — merged alone)*
`admz/capabilities.py` with the full declaration table, `is_active`/`active_capabilities`/
`startup_lines`/`truthy`, the startup logging in `api/main.py` + `mcp/server.py` +
`__main__.py`, the `/api/health` id list, and tests 1, 3, 4, 8, 12, 12b, 13, 14, 15 in
`tests/test_advanced_capabilities.py`.
**No call site is changed** — the registry *declares* the flags while the existing code
still reads them, so nothing can regress. This alone answers the issue's core question
and gives #131 something to register against.

Three deviations from this plan landed with it, each recorded inline above:
the read predicates are `is_active` / `active_capabilities`; `survey.contributor`
is `("setting",)` until slice 2 adds `ADMZ_SURVEY_MODE`; and `test-suppressor`
capabilities warn but write no boot audit row. One addition beyond the plan:
the three event/firebird setting keys joined `PROTECTED_SETTING_KEYS` in slice 1
rather than slice 2, because invariant test 12 cannot pass without them.

**Left for slice 2, still true as written below:** every call site still reads its
own env var with its own truthiness parse, so `truthy()` is *available* but not yet
*adopted* — `ADMZ_DISABLE_ONBOARDING_PROBES=0` still means **on** at
`onboarding.py:65`, and `ADMZ_EVENT_INGEST=true` still means **off** at
`events/config.py:74`. For the values anyone actually uses (`1` / unset) the
registry and the call sites agree; the divergence is exotic-values-only and
disappears with the delegation.

**Slice 2 — call-site migration, audit, and the hidden surface.**
The nine call sites delegate to `is_active`; `set_enabled` + the audit rows;
`PROTECTED_SETTING_KEYS` additions; `GET /api/capabilities` + `POST
/api/capabilities/{id}`; `/settings/advanced` behind `require_reveal_permission`; the
topbar chip. Tests 2, 2b, 5, 6, 7, 9, 10, 16, 17, 18, 19. The bulk of the work and all
of the compatibility risk lives here, behind slice 1's already-merged declarations.

**Slice 3 — chat/MCP surface + docs.** ✅ **SHIPPED**
`get_advanced_capabilities` (+ `EXPECTED_TOOL_ORDER`, the `MIGRATED_TOOLS`
count, and the per-domain split test in the same commit), the system-prompt
block, ADR-0052, and the doc cross-references. Test 11.

Two things landed differently from the text above, both deliberate:

* **The read shape is single-sourced, not mirrored by hand.**
  `capabilities.describe()` / `capabilities.snapshot()` now shape the row, and
  `routes/capabilities._row` is a one-line delegation to the first. The plan
  described two readers agreeing; the code has one shaping function with two
  callers, so they cannot drift. `DANGER_SEVERITY` moved into the registry with
  it (the route keeps the name importable — the template renders
  `row.severity`). The MCP payload omits `reveal_groups`, because `admz.authz`
  imports FastAPI and the registry must stay importable in the stdio
  subprocess — and because nothing on that surface can toggle anything, so who
  may toggle is not its business.
* **The prompt block is gated on `production_appropriate`, not on "any active
  capability".** A survey/ingest install is a legitimate profile; narrating it
  every turn is the alarm fatigue the chip rules already avoid. `privileged`
  and `internal` capabilities therefore stay out of the prompt and remain
  readable via the tool.

**After:** #131 lands as a *registration* — a row in `CAPABILITIES` plus its
implementation, with no new bespoke env-var handling. That is the proof the abstraction
earned its place.

## Acceptance criteria

- An operator can answer *"what non-default powers is this installation running with?"*
  from any one of: the startup log, `curl /api/health`, the topbar chip, or the chat
  console — without reading source.
- Every dev/dangerous/privileged switch that exists today is declared in exactly one
  table, with a danger class and a production verdict.
- `dev.auto_approve` and `acs.rule_write` **cannot** be enabled from a web page, by
  design and by test.
- The LLM cannot enable any capability: no MCP write tool exists, and every capability
  setting key is protected.
- A production install running with a non-production-appropriate capability shows a red
  chip on every page, a startup WARNING, an entry in `/api/health`, and a
  `capability.active` audit row at every boot.
- Every existing env var keeps working with no edit to `tools/dev_auto_approve.py` or
  `tests/conftest.py`; the one intentional truthiness change is tested and documented.
- Adding a new `ADMZ_*` env var fails CI until it is classified (test 12b).
- Confirmation-gate behaviour is provably unchanged (test 18).
- Full suite green; `test_modules_import_isolation` still passes (the registry is
  leaf-light).

## Risks

| Risk | Mitigation |
|---|---|
| **The registry drifts from reality** — someone adds an env flag and never registers it. This is the failure mode that makes registries worthless | Test 12b scans the source and fails until the name is classified. Cheap, and it also keeps this plan's inventory from rotting |
| Unifying truthiness changes behaviour at `onboarding.py:65` (any-non-empty → the standard set) | Scoped to exactly one flag, tested both ways (2b), documented as an intentional fix. `conftest.py:25` sets `"1"` so the suite is unaffected |
| The hidden page becomes the *discovery* mechanism for dangerous features | It is unlinked and reveal-gated; the chip that leads to it only appears when something is already on; the dangerous ones are not toggleable there at all |
| A privileged capability gets toggled by an LLM or an anonymous caller | `PROTECTED_SETTING_KEYS` + `require_reveal_permission` + no MCP write tool — three independent mechanisms, all pre-existing |
| Chip fatigue: a dev box with three suppressors on shows a permanent red chip and everyone stops seeing it | `internal`-class capabilities never chip; test-suppressors are only set by the test suite, which has no UI. In practice a dev *server* shows a chip only for `dev.auto_approve` — which is the point |
| Import-cycle or import-weight regression (`capabilities` is imported by `onboarding`, `events`, `mcp/server`, the nav builder) | Stdlib-only at import; `fleet_settings`/`audit` imported inside functions, the pattern at `acs_pro/config.py:32-36`; `test_modules_import_isolation` covers it |
| Scope creep into "make `dev.auto_approve` server-enforced" | Explicitly out of scope; captured as [Open decision 1](#open-decisions-for-the-owner) |
| ADR number collision with the demo-inference plan (which also claims 0051) | Resolve at merge; see [Open decision 4](#open-decisions-for-the-owner) |

---

## Open decisions for the owner

**1. Should the server *enforce* dev auto-approval, or only declare it?**
Today `ADMZ_DEV_AUTO_APPROVE` is read **only** in `tools/dev_auto_approve.py:65,79`.
The tool posts to the real `/api/chat/confirm/{token}` (`:241`) exactly as a human's
browser does, so the server cannot distinguish the two; the only trace is the extra
`dev.auto_approve` audit row the tool writes itself (`:166-189`). Registering the
capability makes the state *legible* but changes nothing.
Making the server **require** `dev.auto_approve` before accepting an approval marked as
coming from the dev approver would be real hardening — but it needs the tool to
identify itself (a header the server trusts), and it edges toward the "security
boundary" the issue explicitly disclaims. **Recommendation: not in this plan**; land it
as a follow-up issue if wanted. Needs your call because it is the single biggest
functional difference between "registry" and "registry with teeth".

**2. `/settings/advanced` under `ADMZ_AUTH_BACKEND=none` — read-only, or 403?**
The deployment runs `windows-local`, so reveal groups work there. A dev box at
`ADMZ_AUTH_BACKEND=none` has no identity at all. **Recommendation: read-only** — you
can see what is active (the diagnostic value, which is the whole point) but there are
no toggles. The alternative (403 for anonymous) is stricter but makes the page useless
on exactly the machines where these switches get used.

**3. Does `ADMZ_MCP_NO_SCHEDULER` belong in the registry at all?**
It is set by **ADMZ itself** for its own subprocesses (`chatbot/mcp_pool.py:116`,
`chatbot/voice.py:223`) as the H-1 duplicate-scheduler fix, not by an operator. It is a
*runtime role*, not an advanced capability. **Recommendation: register it as class
`internal`** — it shows in `/api/capabilities` and support output (useful when
diagnosing "why didn't the schedule fire?") but never chips and never appears as a
toggle. Leaving it out entirely is also defensible.

**4. New ADR, or extend ADR-0039?**
**Recommendation: a new ADR.** The registry is a platform-level concept (it governs
env vars, settings, audit, and the UI), not a module concern. Number: next free after
0050 — but note `docs/plans/demo-inference.md` also claims **0051**, so whichever lands
second takes 0052.

**5. Should `ADMZ_AUTH_BACKEND=none` appear on the advanced page as context?**
It is not a capability (see the inventory) and already warns at startup, but an
operator reading "what mode is this in?" arguably wants it in the same view.
**Recommendation: show it on the page as a read-only context line, not as a registry
entry** — no chip, no `/api/health` entry, no toggle.

---

## Master resolutions

Settled by the Master session 2026-07-28 under the owner's standing instruction to
proceed without per-decision approval. These supersede the recommendations above.

**1. Declare, do not enforce (dev auto-approval).** The registry records that
`dev.auto_approve` is active and makes that fact loud; it does **not** make the
server verify who is approving. Rationale: the issue's non-goals say plainly this
is *not a security boundary* — anyone who can set environment variables already
owns the machine. Enforcement would require the approving tool to identify itself,
which is an authentication mechanism wearing a registry's clothes, and it would
buy nothing against the only threat model that matters here (accidents, not
attackers). The door stays open: if a future deployment genuinely needs the server
to refuse robot approvals, that is its own issue with its own design, not a
quietly-added parameter here.

*Consequence to state honestly in the docs:* on an install running
`ADMZ_DEV_AUTO_APPROVE`, a `url_only` gate is still a real gate — it just may be
satisfied by a script rather than a human. The registry's job is to make sure
nobody is surprised by that.

**2. `/settings/advanced` under `ADMZ_AUTH_BACKEND=none` → read-only.** The page's
diagnostic value ("what powers is this box running with?") is highest precisely on
an unauthenticated dev box, and a hard 403 would hide it exactly where it helps
most. Toggling still requires the reveal permission, which an anonymous backend
cannot satisfy — so the page informs and refuses to act.

**3. `ADMZ_MCP_NO_SCHEDULER` → class `internal`.** It is a runtime role marker ADMZ
sets for its own subprocesses (`mcp_pool.py:116`, `voice.py:223`), not an operator
choice. Visible in diagnostics so a confusing "why didn't the scheduler run"
question is answerable; never chipped, never toggleable.

**4. ADR number → 0052.** `docs/plans/demo-inference.md` also claimed 0051 and is
several slices ahead, so it keeps it. Update this plan's slice-3 reference
accordingly.

**5. `ADMZ_AUTH_BACKEND` → read-only context, not a registry row.** It already
warns at startup (`_warn_anonymous_auth_backend`), and registering it would leave
every development box permanently chipped — which trains operators to ignore the
chip, defeating its purpose. Showing it as context on the advanced page gives the
information without the alarm fatigue.

### Also adopted from the plan's findings

**Unify truthiness parsing on `{"1","true","yes","on"}`.** `onboarding.py:65` uses
bare `if os.getenv(...)`, so `ADMZ_DISABLE_ONBOARDING_PROBES=0` currently means
**enabled** — a genuine latent footgun found during planning. This is the one
intentional behaviour change; it ships with its own test, and `conftest.py:25`
already sets `"1"` so the suite is unaffected.
