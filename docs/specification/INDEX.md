# Specification Index

Complete table of contents for the ADMZ specification.

## Entry points

- **[README.md](README.md)** — what this directory is and how to read it
- **[process.md](process.md)** — how the spec and GitHub issues work together (requirements as source of truth, issues as the work queue); the two-loop async workflow
- **[orchestration.md](orchestration.md)** — the master-agent session model: who runs each loop, session naming/roles, `status:` labels, worktree safety, validation gates
- **[00-overview.md](00-overview.md)** — mission, scope, non-goals
- **[glossary.md](glossary.md)** — terms and abbreviations

## Personas

Who ADMZ is built for. Each persona drives a set of user stories and requirements.

- [Experience Center operator](personas/experience-center-operator.md) — the original driver of the snapshot/restore work
- [Enterprise fleet operator](personas/enterprise-fleet-operator.md) — Vault-backed, hundreds-of-devices use case
- [LLM agent](personas/llm-agent.md) — the AI consumer of the MCP surface
- [Web-Chatbot user](personas/web-chatbot-user.md) ✅ — the operator who doesn't run their own agent (expected primary persona; the chatbot is live)
- [Security-conscious operator](personas/security-conscious-operator.md) — the human at the keyboard who cares about safety gates
- [Catalog contributor](personas/catalog-contributor.md) — an external developer adding new operations, protocols, or backends

## User stories

Workflows the system must support. Grouped by area.

- [Device onboarding](user-stories/device-onboarding.md) — manual, discovery-driven, and provision flows
- [Credential management](user-stories/credential-management.md) — capture, probe, rotate, temp creds
- [Snapshot and restore](user-stories/snapshot-and-restore.md) — capturing, restoring, forking device configs
- [LLM-driven configuration](user-stories/llm-driven-configuration.md) — catalog query → execute → confirm
- [Chatbot-driven workflows](user-stories/chatbot-driven-workflows.md) ✅ — what the bundled chat client delivers
- [Network discovery](user-stories/network-discovery.md) — finding devices on the local network
- [Demo workflows](user-stories/demo-workflows.md) — Experience Center-specific demo/tag/restore patterns, plus inferring the demos a site already runs (US-DW-013)
- [Drift and monitoring](user-stories/drift-and-monitoring.md) — configuration audits (just-in-time + scheduled), detecting and reconciling unauthorized changes
- [Fleet monitoring](user-stories/fleet-monitoring.md) ✅ — "which devices are online right now?" from a maintained status table
- [Device recovery](user-stories/device-recovery.md) ✅ — "is it back up yet?" after an approved reboot (#49)
- [Scheduled operations](user-stories/scheduled-operations.md) ✅ — recurring unattended jobs (snapshots, configuration audits, survey) on one job-type scheduler
- [Survey contribution](user-stories/survey-contribution.md) ✅ — contribute redacted device knowledge upstream to axis-api-atlas
- [Firmware operations](user-stories/firmware-operations.md) — fetch, plan upgrades, apply

## Requirements

What the system must do, per capability area. Each file has Functional Requirements (FR-*), Non-Functional Requirements (NFR-*), and Known Gaps.

### Capability requirements

- [Core platform](requirements/core-platform.md) — registry ABC, factory, exceptions
- [Credential storage](requirements/credential-storage.md) — Fernet/Vault backends, capture sessions, temp creds
- [Discovery](requirements/discovery.md) — seven protocols, orchestrator, merge-by-MAC
- [Catalog](requirements/catalog.md) — YAML format, families, risk levels, indices
- [Executor](requirements/executor.md) — four API generations, auth resolution, request building
- [Plans](requirements/plans.md) — validation, dependencies, failure policies, rollback
- [Snapshot and restore](requirements/snapshot-restore.md) — facets, git repo, hybrid YAML/raw
- [Drift detection](requirements/drift-detection.md)
- [Fleet health](requirements/fleet-health.md) ✅ — background reachability monitor, current-status table
- [Device recovery](requirements/device-recovery.md) ✅ — live-poll a device back after a reboot (#49 v1)
- [Scheduling](requirements/scheduling.md)
- [Survey / contributor mode](requirements/survey.md) ✅ — opt-in, redacted catalog contributions via GitHub PR (ADR-0030)
- [Knowledge and capabilities](requirements/knowledge-and-capabilities.md) — product hints and per-model API support
- [Firmware](requirements/firmware.md) — downloader, upgrade-path
- [MCP server](requirements/mcp-server.md) — tool surface, gating
- [Web API](requirements/web-api.md) — REST surface
- [Web UI](requirements/web-ui.md)
- [Web chatbot](requirements/web-chatbot.md) ✅ — bundled Gemini-powered chat client (manual MCP tool loop)
- [Organization hierarchy](requirements/hierarchy.md) ✅ — Org → Site → Device, with tags as the grouping primitive (ADR-0032)
- [Multi-target support](requirements/multi-target-support.md) 📋 — 2N intercoms, ACS Pro VMS, typed target taxonomy, ConfigCollector / Actuator split

### Cross-cutting requirements

- [Authentication](requirements/authentication.md) — Windows IWA, API keys, LDAP groups (Phase 4)
- [Security](requirements/security.md) — auth, encryption, gating, audit
- [Observability](requirements/observability.md) — logging, metrics, audit log
- [Reliability](requirements/reliability.md) — error handling, retries, concurrency
- [Performance](requirements/performance.md) — scaling thresholds
- [Extensibility](requirements/extensibility.md) — the four pluggable extension points
- [Configuration](requirements/configuration.md) — environment variables and paths

## Decision records

Architecture decision records (ADRs) capturing the *why* behind load-bearing design choices. ADR template: Status / Context / Decision / Consequences.

### Catalog & operation model

- [0001 — Organize catalog by CGI, not by category](decisions/0001-organize-catalog-by-cgi.md)
- [0002 — One YAML file per operation](decisions/0002-one-yaml-per-operation.md)
- [0003 — YAML catalog, not generated code](decisions/0003-yaml-not-generated-code.md)
- [0004 — Tags live only in index files](decisions/0004-tags-in-index.md)
- [0019 — Inverted index files for routing](decisions/0019-inverted-index-files.md)
- [0029 — Axis API Atlas as a maintained, reusable asset (DCA-refreshed capability matrix + standalone extraction)](decisions/0029-axis-api-atlas-as-maintained-reusable-asset.md) ✅ — also see the [maintenance runbook](../AXIS_API_ATLAS_MAINTENANCE.md)
- [0030 — Survey / contributor mode (distributed read-only API discovery → axis-api-atlas PRs)](decisions/0030-survey-contributor-mode.md) ✅

### Safety & gating

- [0005 — Two-gate plan approval (semantic + mechanical)](decisions/0005-two-gate-plan-approval.md)
- [0006 — Multi-level confirmation by risk class](decisions/0006-multi-level-confirmation.md)
- [0018 — Risk-aware "expect-timeout" semantics for reboot ops](decisions/0018-expect-timeout-semantics.md)
- [0020 — Protected fleet settings keys not writable from MCP](decisions/0020-protected-fleet-settings.md)
- [0052 — Advanced capability switches: one declared registry, five loudness surfaces, zero enforcement](decisions/0052-advanced-capability-switches.md) ✅ — ten dev/dangerous/privileged switches declared in one table (`admz/capabilities.py`) that *is* the read path; enablement asymmetric by danger class (env-only for `dev-only`/`dangerous`/`test-suppressor`/`internal` so they can never be a click in a browser, env-or-setting for `privileged` so a background loop stays stoppable without a restart); loud at startup, in the audit log, on a topbar chip, in `/api/health` + `GET /api/capabilities` + the read-only `get_advanced_capabilities` MCP tool, and in the chat prompt. Explicitly **not** a security boundary, and never softens a confirmation gate (ADR-0034) (#132)

- [0053 — Fleet settings are deny-by-default for the LLM: writability is declared, not withheld](decisions/0053-llm-writable-fleet-settings.md) ✅ — inverts ADR-0020's enumerated deny-list after it failed four times in the same direction (#152, #168, #195, #203). A setting is unwritable by the chat model unless declared in `LLM_WRITABLE_SETTING_KEYS` (`admz/setting_policy.py`), which holds exactly two keys — the fleet credential pair — validated by attempted falsification across prompts, demos, docs and tests. `default_password` becomes capture-only, matching what FR-MCP-008 already required. The decisive evidence is that three independent enumerations of the unprotected keys returned 8, 10 and 18, each missing keys the others found, so the guard test enumerates from behaviour (AST, constant-resolving) rather than from names. Purpose-built gated tools (`set_event_ingest`) stay outside the model by design; `python -m admz settings` ships alongside so the nine orphaned keys keep an operator path. Adds no confirmation gate and removes none (ADR-0034 untouched) (#212)

### Authentication (Phase 4)

- [0021 — Windows IWA via reverse proxy](decisions/0021-windows-iwa-via-reverse-proxy.md)
- [0022 — API keys for agents](decisions/0022-api-keys-for-agents.md)
- [0023 — LDAP group enrichment](decisions/0023-ldap-group-enrichment.md)

### Entry-point surfaces

- [0024 — Bundled web chatbot](decisions/0024-bundled-web-chatbot.md) ✅ (live)
- [0025 — Gemini for the chatbot (manual MCP tool loop)](decisions/0025-gemini-chatbot-mcp-native.md) ✅ (amended — shipped the manual tool loop, not SDK-native MCP; default gemini-2.5-flash)

### Authentication & secrets

- [0007 — Per-protocol auth detection and storage](decisions/0007-per-protocol-auth.md)
- [0009 — Out-of-band credential capture via one-time URL](decisions/0009-oob-credential-capture.md)
- [0010 — Fernet at-rest encryption with auto-generated keys](decisions/0010-fernet-encryption.md)
- [0014 — Configurations in git, credentials never in git](decisions/0014-config-in-git-creds-in-db.md)

### Interfaces

- [0008 — Both MCP and REST API surfaces](decisions/0008-mcp-and-rest-surfaces.md)

### Backends & extensibility

- [0011 — Pluggable registry backends (SQLite default, Vault optional)](decisions/0011-pluggable-backends.md)
- [0015 — Pluggable snapshot facets](decisions/0015-pluggable-facets.md)
- [0027 — Pluggable control families and ConfigCollector / Actuator split](decisions/0027-pluggable-control-families-and-config-collectors.md) 📋 — 2N intercom and ACS Pro support; typed target taxonomy; multi-family snapshot pipeline

### Snapshot/restore

- [0012 — Snapshot/restore implemented on top of the plan engine](decisions/0012-snapshot-on-plans.md)
- [0013 — Hybrid YAML + raw artifact format](decisions/0013-hybrid-yaml-and-raw.md)
- [0055 — Order-insensitive drift comparison (`normalize_doc`)](decisions/0055-order-insensitive-drift-comparison.md) ✅ — drift flattens both sides to dotted keys and compares strings, so a value *serialized* differently reports as a change that means nothing. Observed live: an action rule's `and`-joined XPath clauses came back in a different order after a scenario round-trip (ADMZ's own writer reorders them), and the facet is read-only, so the operator's only option was *accept baseline* — which the next activation undid. Facets may now declare a canonical form via `FacetAdapter.normalize_doc`, applied to **both** the live doc and the git-stored baseline, mirroring how the ignore list already works: normalising only on capture would leave every existing baseline drifting until re-captured, a silent no-op indistinguishable from the fix working. Only *provable* equivalences may be collapsed — clauses sort as a multiset (a set would hide a dropped duplicate) and splitting is bracket-aware (an XPath predicate contains `and`). List-valued fields (`actionParameters`, the `condition` list) stay order-sensitive: exposed, unproven, deliberately still reported (#215, #228)
- [0026 — Unified job scheduler](decisions/0026-unified-job-scheduler.md) ✅ — generalized the snapshot-only scheduler to a `job_type` handler registry; ships snapshot, drift_audit, and survey job types

### Activity tracking & monitoring

- [0028 — Demo / activity tracking as a bounded module on ADMZ's shared substrate](decisions/0028-demo-activity-tracking-shared-substrate.md) 📋 — AEC demo-session detection and reporting; reuses ACS layer, inventory, and UI chrome; runs as a separate, independently-deployable module
- [0046 — Demos (the experience-center unit of work)](decisions/0046-demos.md) ✅ — the demo as a first-class object composing Scenario (config) + detections (signal); readiness as a pure rollup over the drift/health caches; Prepare/End delegate to a shared gated scenario core. ADR-0041 Layer 4, phase 1 (liveness deferred)
- [0047 — Demo-owned config fragments (composition + attribution)](decisions/0047-demo-config-fragments.md) ✅ — a demo owns a sparse key-set over each device's base; expected = base ⊕ active demos' keys; every drifted key attributed (set-by-demo / demo-broken / looks-like-demo / unclaimed) — the mechanical answer to "drifted or deliberately changed?". Capture from the drift diff; adopt without pushing; accept-baseline guard. Slices 1–2 shipped (activation pushes staged)
- [0051 — Infer the demos that already exist: deterministic collection, agent narration](decisions/0051-demo-inference.md) ✅ — read the registry, snapshots and ACS action rules into a weighted evidence graph, cluster it into scored **proposals** in their own tables (never `demos`, which drift attribution walks), and let the agent narrate name + purpose from the evidence; confirm composes the existing demo/rule write cores and writes no fragments. Two live findings drive the constants: zero rule-expressed topology on the reference fleet, and corroborating evidence does not chain (#124)

### Discovery

- [0016 — Merge discovery results by MAC](decisions/0016-merge-discovery-by-mac.md)
- [0017 — Two-phase discovery (broadcast then enrich)](decisions/0017-two-phase-discovery.md)

### Deployment & runtime layout

- [0042 — Machine-level data directory (ADMZ_HOME) + Windows-service deployment](decisions/0042-machine-level-data-directory.md) ✅ — all state under one `ADMZ_HOME` resolved call-time by `admz/paths.py` (specific `ADMZ_*_PATH` overrides still win); on Windows, `C:\ProgramData\admz` with the service supervised by Shawl as LocalSystem, so no user profile and no stored service password
- [0054 — Production gets its own clone and its own venv: separating what runs from what is being changed](decisions/0054-separate-production-tree-and-venv.md) 📋 — ADR-0042 decided where production's *data* lives; this decides where its *code and interpreter* live, after one tree and one venv serving production, staging and every test run produced a live contradiction: rebuilding the venv for `master` breaks staging (60 commits stale), leaving it crash-loops production on restart (mcp 2.x code, mcp 1.26 venv). Production moves to a dedicated **clone** (not a worktree — worktrees share `.git`) at a deliberate SHA with a venv built from that SHA's `requirements.txt`; the service's `--cwd` and interpreter are repointed and nothing else about it changes. Deployment stops being "someone pulled" and becomes `scripts/deploy-prod.ps1`, whose step 4 — import the new code on the new venv *before* the service is stopped — is the point of the whole record. The host owns what it runs (detached HEAD + `deployed.log`), not a tag. Explicitly does **not** separate `ADMZ_HOME`, git config, gh identities, the fleet, or the machine. Blocked on #235; absorbs #173

## Plans

Approved implementation plans for staged work (design fixed, build pending — tracked as GitHub issues).

- [Separate the production tree and venv from the dev workspace](plans/dev-prod-split.md) — ADR-0054 slices: build a pinned production clone + its own venv, repoint the Shawl service's two paths, replace the implicit `git pull` deployment with `scripts/deploy-prod.ps1` (six steps, of which step 4's pre-stop smoke check is the one that matters), bring `setup-admz-service.ps1` into the repo and rewrite `DEPLOYMENT_WINDOWS.md` around the deployment that actually runs (#173). Staging's own venv deferred with a stated trigger; blocked on #235
- [Demo setup wizard](plans/demo-setup-wizard.md) — ADR-0047 slice 3+: fragment activation pushes with state-flip-on-completion (fixes the scenario marker-timing bug), demo-aware rules with auto-attached trigger signals, and the guided chat setup surface (`demo_setup_status` + gated `set_event_ingest`)

## Reviews

Point-in-time production-readiness reviews and their follow-up trackers.

- [review-2026-06-10.md](review-2026-06-10.md) — exhaustive architecture / security / vestigial-code / duplication / docs review, with a prioritized action plan and per-finding status
- [review-followup.md](review-followup.md) — the 2026-05-17 review's follow-up tracker

## Reading paths by role

- **"I'm onboarding to ADMZ"** → README → overview → personas → user-stories → glossary.
- **"I'm running the requirements / implementation loops"** → [process](process.md) → the spec area you're working in.
- **"I'm implementing a GitHub issue"** → [process](process.md) → the requirement/story IDs the issue references → related decisions.
- **"I'm adding a feature"** → overview → relevant capability requirement → related decisions.
- **"I'm adding a catalog operation"** → catalog requirement → decisions 0001–0004 → existing YAML in `catalog/vapix/`.
- **"I'm adding a new device family"** → extensibility requirement → decisions 0011, 0015, 0027 → multi-target-support requirement.
- **"I'm building demo / activity tracking or monitoring/reporting"** → ADR-0028 → multi-target-support (FR-MT-013 spike) → personas/experience-center-operator → observability requirement → hierarchy requirement.
- **"I'm hardening security"** → security requirement → decisions 0005, 0006, 0009, 0010, 0014, 0020.
