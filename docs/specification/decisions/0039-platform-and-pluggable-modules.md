# ADR-0039 — Platform + pluggable modules (devices is module #1)

**Status:** Accepted (2026-06-19)
**Relates to:** ADR-0027 (pluggable control families) — this generalizes that
family seam from the executor layer up to the whole product surface (MCP tools,
REST routers, nav, prompt). Sets up ADR-0040 (ACS Pro module, PR2).

## Context

ADMZ fused two things: a **platform** (auth/principals, audit, the two-gate
confirmation core, the unified task store, the chatbot host + per-principal MCP
pool, the web shell + Axis Signal design system) and exactly **one module**
(Axis edge devices: the VAPIX executor, the `axis-api-atlas` catalog, discovery,
snapshot/drift/config-history). The user wants to manage *other* Axis software
the same way — first **Axis Camera Station Pro** (ACS Pro, the VMS) — so the
natural move is to make device-management an explicit **module #1** behind a
small platform, then add ACS Pro as **module #2**.

The execution spine was already family-threaded
(`operations.execute_gated_operation(family=…)` →
`catalog.get_risk_level(family, op)` → confirm gate →
`executors[family].execute`), and the atlas already models ACS Pro
(`axis-api-atlas/data/acs-pro/`). The remaining coupling was cosmetic
(hardcoded nav, hardcoded "VAPIX" prompt strings) plus the fact that the MCP
tool handlers were inline on the 3,500-line `ADMZMCPServer`.

## Decision

Introduce a **module contract** and a **module registry**, and make the
platform surfaces (MCP, REST, web nav, chatbot prompt) compose modules rather
than hardcode the one device module.

### The contract (`admz/modules/{contract,registry}.py`)

`contract.py` imports only stdlib + typing (concrete types under
`TYPE_CHECKING`), so the stdio MCP subprocess and the leaf-light
`admz.operations` layer can import it without dragging in FastAPI / the catalog
package / any executor. A test (`test_modules_import_isolation`) enforces this.

A **`Module`** carries `id`, `family`, `title`, `catalog_family`, and factories
the platform calls and merges: `executors()`, `mcp_tools() -> [ToolSpec]`,
`routers()`, `nav_section(ctx) -> NavSection`, `build_prompt_section(ctx)`,
`task_handlers()`, and **`self_heals()`**. A **`ToolSpec(tool, handler)`** pairs
an `mcp.types.Tool` schema with a *free async function* `(ToolCtx, args)`.
**`ModuleRegistry.discover()`** does an explicit, ordered import of each
module's `get_module()` (no entry-point magic) and exposes merge helpers
(`executors_for_all`, `tool_specs_all`, `routers_all`, `nav_sections_all`,
`prompt_sections_all`, `task_handlers_all`, `self_heals(family)`). It is built once in
`components.build_components` and stored on `Components`, so MCP, web, and the
chatbot all read one registered set without a global.

### Nav model (user decision 2026-06-19)

The sidebar is a list of **sections**:
- **Core** is pinned at the top with no header/divider: Console, Devices, Tasks,
  Audit log, Settings (fixed order).
- **Tags move UNDER Devices** as a child sub-nav (`NavItem.children`) — no
  longer a standalone "Tags" section below the divider.
- Each **module** contributes its own divider-separated section (optional header
  + 1..N items) via `nav_section()`. None in PR1 (devices folds into Core); ACS
  Pro adds Cameras/Recordings/Servers in PR2.

`templating.build_nav` emits `nav.sections`; `base.html` loops them instead of
hardcoding the five items.

### `self_heals()` — the one behaviour generalization

Edge devices relearn scheme/auth on the wire and the gate persists the
corrected connectivity profile. Server targets (ACS Pro) authenticate per
connection and must NOT have their stored auth rewritten. So
`operations.run_execution_tail` now gates `_persist_learned_auth` on the
executor's `self_heals()` (default **True** on `BaseExecutor`; a no-op for
VAPIX, the seam for ACS Pro to return False). A module's `self_heals()` must
agree with its executor's.

**This gate decides whether a relearned profile is *persisted*; it cannot
decide whether a credential was *spent*.** By the time `learned_auth` reaches
`run_execution_tail`, the request that produced it has already been sent. So a
constraint on *what may be learned* has to live in the executor, before the
retry is issued — see the #171 amendment in
[ADR-0007](0007-per-protocol-auth.md), which bounds the challenge-driven relearn
away from Basic-over-plaintext. Do not attempt to enforce that class of rule
here: this side of the boundary is structurally too late.

### MCP dispatch is now table-driven

`call_tool`'s 52-arm `if/elif name ==` chain became a single lookup into
`admz/mcp/dispatch.TOOL_HANDLERS`; handlers are free `(ctx, args)` functions. In
this PR they are **shims** delegating to the existing bound `_method`s, so it is
a pure refactor — but it is what lets a device tool's body relocate into the
module with a one-line change later. The outer wrapper (arg validation,
anonymous-block gate, error-envelope mapping, finally-audit) is byte-identical;
a snapshot test freezes the 52-tool wire order and asserts the dispatch table
equals the advertised set.

### Prompt seam

`build_system_prompt` gained a `{module_sections}` slot (default empty); the
chat + voice hosts pass `build_module_prompt_sections()`. Empty in the
device-only deployment → the assembled prompt is byte-identical. ACS Pro fills
it with serial/MAC correlation guidance in PR2.

## Scope of PR1 vs the follow-up

**In PR1 (this ADR):** the contract + registry, registry-built executors,
table-driven MCP dispatch + frozen order snapshot, data-driven nav (tags under
Devices), the `{module_sections}` prompt seam, the `self_heals()`
generalization, and the `devices` module declaring its executor + (later) tools.
No user-facing behaviour change beyond the nav restructure; the full suite stays
green at every commit.

**Deferred to a focused fast-follow (PR1.5):** physically relocating the device
*implementation* into `admz/modules/devices/` (the VAPIX executor file, the
device REST routers, the MCP handler **bodies**, `discovery/`/`snapshot/`/
`firmware/`/`provisioning`/`recovery`/`device_facts`, and the VAPIX prompt body
+ roster builders), each behind a re-export shim. This is mechanical but has
per-file sharp edges — e.g. `test_firmware` monkeypatches
`admz.executor.vapix._UPLOAD_ROOT`, which a *transparent* re-export shim cannot
preserve (the moved function reads its own module's global, not the shim's), so
those moves need either test updates or a re-export that rebinds the patched
name. Doing it as its own increment keeps the architecture review (this PR) free
of a 15-file mechanical diff, and the table-driven dispatch + module contract
make each later move a localized change on a proven foundation.

## Consequences

- A new module (ACS Pro, Axis Audio Manager Pro, …) is added by writing
  `admz/modules/<id>/` with a `get_module()` and appending one
  `register_module()` line in `discover()` — it then reaches MCP, REST, nav, and
  the prompt through the same merge helpers.
- The platform no longer assumes a single self-healing family.
- The MCP tool list and dispatch can't drift (snapshot + coverage tests).
- Until PR1.5, the device implementation still lives at its historical import
  paths; the `devices` module *constructs* the executor and *declares* its
  contract, but the bodies haven't moved. This is intentional and green.
