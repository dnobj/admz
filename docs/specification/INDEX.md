# Specification Index

Complete table of contents for the ADMZ specification.

## Entry points

- **[README.md](README.md)** — what this directory is and how to read it
- **[process.md](process.md)** — how the spec and GitHub issues work together (requirements as source of truth, issues as the work queue); the two-loop async workflow
- **[orchestration.md](orchestration.md)** — the master-agent session model: who runs each loop, session naming/roles, `status:` labels, worktree safety, validation gates
- **[00-overview.md](00-overview.md)** — mission, scope, non-goals
- **[glossary.md](glossary.md)** — terms and abbreviations
- **[../ENVIRONMENT.md](../ENVIRONMENT.md)** — every `ADMZ_*` environment variable, grouped by the decision it belongs to rather than alphabetically. Covers the three that define staging (`ADMZ_AUTO_PUSH` — **default ON** — `ADMZ_HEALTH_INTERVAL_SECONDS`, `ADMZ_PORT`), whose *effects* were documented while their names were not; and gives each switch that weakens a guarantee a plain statement of what it gives up. The capability registry (`admz/capabilities.py`, ADR-0052) remains the enforced source for classification; this is the human-facing half (#181)
- **[../ACCEPTANCE.md](../ACCEPTANCE.md)** — the manual acceptance pass: twelve operator-visible checks to run before believing a release is sound. Derived from the user stories below, and deliberately scoped to what the ~3,700-test suite *structurally cannot* catch — a collapse that never reaches the rows (#263), a subresource loaded from a CDN (#200), a suite pointed at production (#180). Not a substitute for the suite, and it says so.

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
- [0034 — One human gate: every destructive action goes through the link/widget approval](decisions/0034-uniform-widget-gating.md) ✅ — risk → level (`none` / `llm_confirm` / `url_only` / `url_and_password`), single-sourced in `admz/confirm_policy.py` and resolved through `operations.resolve_confirmation` (`confirm_store` re-exports the table, it no longer defines it). Capabilities may change *who* may approve; they never remove a gate
- [0052 — Advanced capability switches: one declared registry, five loudness surfaces, zero enforcement](decisions/0052-advanced-capability-switches.md) ✅ — ten dev/dangerous/privileged switches declared in one table (`admz/capabilities.py`) that *is* the read path; enablement asymmetric by danger class (env-only for `dev-only`/`dangerous`/`test-suppressor`/`internal` so they can never be a click in a browser, env-or-setting for `privileged` so a background loop stays stoppable without a restart); loud at startup, in the audit log, on a topbar chip, in `/api/health` + `GET /api/capabilities` + the read-only `get_advanced_capabilities` MCP tool, and in the chat prompt. Explicitly **not** a security boundary, and never softens a confirmation gate (ADR-0034) (#132)

- [0053 — Fleet settings are deny-by-default for the LLM: writability is declared, not withheld](decisions/0053-llm-writable-fleet-settings.md) ✅ — inverts ADR-0020's enumerated deny-list after it failed four times in the same direction (#152, #168, #195, #203). A setting is unwritable by the chat model unless declared in `LLM_WRITABLE_SETTING_KEYS` (`admz/setting_policy.py`), which holds exactly two keys — the fleet credential pair — validated by attempted falsification across prompts, demos, docs and tests. `default_password` becomes capture-only, matching what FR-MCP-008 already required. The decisive evidence is that three independent enumerations of the unprotected keys returned 8, 10 and 18, each missing keys the others found, so the guard test enumerates from behaviour (AST, constant-resolving) rather than from names. Purpose-built gated tools (`set_event_ingest`) stay outside the model by design; `python -m admz settings` ships alongside so the nine orphaned keys keep an operator path. Adds no confirmation gate and removes none (ADR-0034 untouched) (#212)
- [0059 — Gate provisioning at the decision point, not at the entry points](decisions/0059-gate-provisioning-at-the-decision-point.md) 📋 — **Proposed, docs-only.** #299 gated the two discovery-driven provisioning paths on the distinction *the device is chosen before the call* (leave ungated) versus *chosen by a scan* (gate). That reasoning is correct about a **human** caller and collapses for an **LLM** one, which can call `discover_network_devices` (an ungated read) and then name what it just found — the same actor chooses the set *and* makes the "explicit, singular" call, so the two categories are not distinguishable at the call site. The proof is in the gate table: `register_discovered_device` is gated while `register_device`, reaching the same `pwdgrp.cgi:add-user`/`group=root` write, is not; three of the five callers of `onboard_device_credentials` are ungated and two of those are model-reachable. Moves the gate to `onboard_device_credentials`, the function that *decides* to provision — and specifically to the branch at `onboarding.py:133`, because whether provisioning happens is **not knowable without contacting the device** (`read_systemready` → `needsetup`), so an entry-side check would fire on every add while a branch-side one fires only on a factory-defaulted unit, after four reads and no writes. `provision_factory_default` stays deliberately ungated for exactly the reason `discovery/gated.py` gives (nothing can approve a widget for the scheduled reprovision task) — and #299's decisive objection does not reach one level up, because `_run_reprovision` calls it **directly** (`tasks/handlers.py:225`) and never through `onboard_device_credentials`. Carries the approved-context decision: a `ContextVar` set once by `execute_approved_session` (inherited by the survey's background task because `asyncio.create_task` copies the context) over an explicit `approved_by=` kwarg, recording that the kwarg's redeeming property is that it fails **closed** while the ContextVar's `try/finally` is load-bearing and fails **open** if a token leaks. Distinct from #313, which refuted gating the lower-level `_execute_on_host` (that would gate temp-account *cleanup*); this ADR does **not** close #313 (#199, #299, #313)


### Authentication (Phase 4)

- [0021 — Windows IWA via reverse proxy](decisions/0021-windows-iwa-via-reverse-proxy.md)
- [0022 — API keys for agents](decisions/0022-api-keys-for-agents.md)
- [0023 — LDAP group enrichment](decisions/0023-ldap-group-enrichment.md)
- [0033 — Sign in with the box's Windows credentials (`windows-local` backend)](decisions/0033-windows-local-credential-auth.md) ✅ — ctypes `LogonUserW`, no new dependencies; the house pattern every later Win32 module follows
- [0035 — "Continue as the signed-in Windows user": in-process Negotiate SSO at the login page](decisions/0035-negotiate-sso-login.md) ✅ — and the UAC token-filtering trap it hit live (KL-AUTH-009), which is why group membership is read from the directory rather than the logon token

### Entry-point surfaces

- [0024 — Bundled web chatbot](decisions/0024-bundled-web-chatbot.md) ✅ (live)
- [0025 — Gemini for the chatbot (manual MCP tool loop)](decisions/0025-gemini-chatbot-mcp-native.md) ✅ (amended — shipped the manual tool loop, not SDK-native MCP; default gemini-2.5-flash)
- [0038 — Chat conversation history (named, listable conversations)](decisions/0038-chat-conversation-history.md) ✅

### Authentication & secrets

- [0007 — Per-protocol auth detection and storage](decisions/0007-per-protocol-auth.md) — amended 2026-08-04 (#171): the `WWW-Authenticate` header the profile is detected from is attacker-controlled, so the executor refuses to **learn** Basic from a challenge on a non-TLS channel. Narrow on purpose — it does not refuse to *use* a configured Basic-over-HTTP profile (the operator's escape hatch), and is not a downgrade ratchet, which would strand a legitimately reconfigured camera and still leak
- [0009 — Out-of-band credential capture via one-time URL](decisions/0009-oob-credential-capture.md)
- [0010 — Fernet at-rest encryption with auto-generated keys](decisions/0010-fernet-encryption.md)
- [0014 — Configurations in git, credentials never in git](decisions/0014-config-in-git-creds-in-db.md)

### Interfaces

- [0008 — Both MCP and REST API surfaces](decisions/0008-mcp-and-rest-surfaces.md)

### Backends & extensibility

- [0011 — Pluggable registry backends (SQLite default, Vault optional)](decisions/0011-pluggable-backends.md)
- [0015 — Pluggable snapshot facets](decisions/0015-pluggable-facets.md)
- [0027 — Pluggable control families and ConfigCollector / Actuator split](decisions/0027-pluggable-control-families-and-config-collectors.md) 📋 — 2N intercom and ACS Pro support; typed target taxonomy; multi-family snapshot pipeline
- [0039 — Platform + pluggable modules (devices is module #1)](decisions/0039-platform-and-pluggable-modules.md) ✅ — a module adds **zero footprint until enabled**: one predicate, consulted everywhere. Also owns `self_heals()`, the gate deciding whether a relearned auth profile is persisted — and which structurally cannot decide whether a credential was *spent* (ADR-0007 #171)
- [0040 — Axis Camera Station Pro module (read-only v1)](decisions/0040-acs-pro-module.md) ✅
- [0041 — Activity / observability layer: log search, a cross-source event timeline, and event-pattern detections](decisions/0041-activity-observability-module.md)

### Snapshot/restore

- [0012 — Snapshot/restore implemented on top of the plan engine](decisions/0012-snapshot-on-plans.md)
- [0013 — Hybrid YAML + raw artifact format](decisions/0013-hybrid-yaml-and-raw.md)
- [0031 — Live / Observation / Baseline: separating "what we saw" from "what we bless"](decisions/0031-live-observation-baseline.md) ✅
- [0044 — Config scenarios (baseline-stable alternate configs)](decisions/0044-config-scenarios.md) ✅
- [0049 — Cache the drift diff at detection time](decisions/0049-drift-diff-cache.md) ✅
- [0055 — Order-insensitive drift comparison (`normalize_doc`)](decisions/0055-order-insensitive-drift-comparison.md) ✅ — drift flattens both sides to dotted keys and compares strings, so a value *serialized* differently reports as a change that means nothing. Observed live: an action rule's `and`-joined XPath clauses came back in a different order after a scenario round-trip (ADMZ's own writer reorders them), and the facet is read-only, so the operator's only option was *accept baseline* — which the next activation undid. Facets may now declare a canonical form via `FacetAdapter.normalize_doc`, applied to **both** the live doc and the git-stored baseline, mirroring how the ignore list already works: normalising only on capture would leave every existing baseline drifting until re-captured, a silent no-op indistinguishable from the fix working. Only *provable* equivalences may be collapsed — clauses sort as a multiset (a set would hide a dropped duplicate) and splitting is bracket-aware (an XPath predicate contains `and`). List-valued fields (`actionParameters`, the `condition` list) stay order-sensitive: exposed, unproven, deliberately still reported (#215, #228)
- [0056 — Drift attribution annotates, never suppresses](decisions/0056-drift-attribution-annotates-never-suppresses.md) ✅ — ADMZ's own gated, approved, audited writes were reported as unexplained drift, one flat row per parameter: the C1710's "36 changes" are really 3 rules created via chat on 2026-07-18. Drift rows are now annotated at READ time with the audit row that explains them, and `action_rules` rows group per rule. The boundary is the whole record: a matched row is **still drift** — the audit row holds the tool *arguments*, never the resulting config, so a match proves ADMZ wrote to that rule once and says nothing about whether the current value is what ADMZ wrote; auto-accepting would hide a later on-device edit to the same rule. Attribution therefore adds a separate key and never touches `bucket` (ADR-0047's `demo_set` already suppresses through it), `real_fields` or `has_drift`. Three match strengths, each hedged in the operator-facing copy: rule id (exact, deletes today — the create path discards the id until #230 PR 2), rule name (the only retroactive key, neither unique nor rename-stable), device+time. Applied below `to_summary()` so the MCP tool gets it too, and never cached. Grouping needed no backend change: `flatten()` only joins segments with dots, so the rule id survives verbatim in `path` (#230)
- [0026 — Unified job scheduler](decisions/0026-unified-job-scheduler.md) ✅ — generalized the snapshot-only scheduler to a `job_type` handler registry; ships snapshot, drift_audit, and survey job types

### Activity tracking & monitoring

- [0028 — Demo / activity tracking as a bounded module on ADMZ's shared substrate](decisions/0028-demo-activity-tracking-shared-substrate.md) 📋 — AEC demo-session detection and reporting; reuses ACS layer, inventory, and UI chrome; runs as a separate, independently-deployable module
- [0046 — Demos (the experience-center unit of work)](decisions/0046-demos.md) ✅ — the demo as a first-class object composing Scenario (config) + detections (signal); readiness as a pure rollup over the drift/health caches; Prepare/End delegate to a shared gated scenario core. ADR-0041 Layer 4, phase 1 (liveness deferred)
- [0047 — Demo-owned config fragments (composition + attribution)](decisions/0047-demo-config-fragments.md) ✅ — a demo owns a sparse key-set over each device's base; expected = base ⊕ active demos' keys; every drifted key attributed (set-by-demo / demo-broken / looks-like-demo / unclaimed) — the mechanical answer to "drifted or deliberately changed?". Capture from the drift diff; adopt without pushing; accept-baseline guard. Slices 1–2 shipped (activation pushes staged)
- [0051 — Infer the demos that already exist: deterministic collection, agent narration](decisions/0051-demo-inference.md) ✅ — read the registry, snapshots and ACS action rules into a weighted evidence graph, cluster it into scored **proposals** in their own tables (never `demos`, which drift attribution walks), and let the agent narrate name + purpose from the evidence; confirm composes the existing demo/rule write cores and writes no fragments. Two live findings drive the constants: zero rule-expressed topology on the reference fleet, and corroborating evidence does not chain (#124)
- [0037 — Unify Schedules + Recovery into one "Tasks" model](decisions/0037-unified-tasks.md) ✅ — supersedes the `schedules.json` store
- [0043 — Device event action rules from natural language](decisions/0043-device-event-action-rules.md) ✅
- [0048 — Watch-scoped event capture + a transient preview feed](decisions/0048-watch-scoped-event-capture.md) ✅
- [0050 — Demo setup wizard: activation pushes, rule↔demo correlation, guided setup](decisions/0050-demo-setup-wizard.md) ✅ — amended 2026-08-04 (#198): the Phase C checklist's `observed` flag means "present as of the last audit", not a live probe

- [0057 — ACS firings gate on identity, not on a clock](decisions/0057-acs-firings-gate-on-identity-not-a-clock.md) ✅ — the ACS action-rule poller stores every row it fetches but fires a detection only for rows newer than a high-water mark, so a firing lands in the Activity feed while its detection provably never runs and every health surface reports the poller fine. The mark is also seeded from the **ADMZ host** clock and compared against **ACS server** timestamps, and ACS exposes no server-time op — so the skew is not merely uncorrected, it is unmeasurable by construction. Firing now gates on `EventStore.append`'s `INSERT OR IGNORE` return (the store already answers "have I seen this?" durably), with a `_seeded` boolean preserving ADR-0041's startup contract — historical firings seed the feed and never fire — which is why the naive "just use `inserted`" fix was rejected: on first enablement it would fire 30 minutes of retroactive rules, including pre-authorized service-affecting ones. No clock comparison remains in the fire path. The lookback window becomes a **self-healing retry buffer** (every poll re-fetches it), so a swallowed store error must *not* be papered over with a seen-set — that would defeat the retry and reintroduce #209's defect class. Residual skew still shrinks the query window (`utc_anchor` is local-clock) and is measured via `apparent_skew_ms` rather than corrected. `AcsFirebirdPoller` is the worked precedent: it seeds from the source's own monotonic id and fires every returned row (#210)

- [0058 — The detection evaluator degrades to its last good rules, never drops the event](decisions/0058-the-detection-evaluator-degrades-never-drops.md) ✅ — `DetectionEvaluator.evaluate` is the `on_event` callback for **every** event source, and it has exactly one way to raise: the unguarded `_refresh()` whose `DetectionStore.list()` propagates a sqlite error. Everything else is already swallowed — the per-rule loop is wrapped, `_fire` is a detached task. When it does raise it raises *before any rule is evaluated*, so one unreadable rule cache silently drops a firing that may have matched several enabled detections, and on four of the five call paths there is no way to get it back (a WS event arrives once; the Firebird poller advances its cursor before firing; the webhook swallows with a bare `except: pass`). The evaluator now keeps its last good rule list, leaves its version cursor alone and warns once per streak — the shape #249 gave the sibling `WatchGate._refresh` — so `evaluate` becomes total and all five paths are fixed without adding state to any poller. Trade: a rule disabled one refresh cycle ago can fire once, versus today dropping the event and firing *nothing*; `pre_authorized` still gates and a test pins the staleness deliberately. Rejects #255's three candidates — fire-before-append (whose stated crash cost is not real, `_seeded` already closes it, while its actual cost moves duplicate risk onto the *more* likely write failure), a re-fire set (not the rejected seen-set — it fails open, not closed — but it repairs the one path that already has a retry buffer), and bare accept (unassessable: warn-once latch, no counter). `fire_failed_total` is retained as the standing alarm, structurally zero on the current wiring (#255)

### Discovery

- [0016 — Merge discovery results by MAC](decisions/0016-merge-discovery-by-mac.md)
- [0017 — Two-phase discovery (broadcast then enrich)](decisions/0017-two-phase-discovery.md)
- [0036 — Slot vs unit device identity (stable slot + replaceable hardware)](decisions/0036-slot-unit-device-identity.md)
- [0032 — Tags replace the device Group level (Org and Site stay)](decisions/0032-tags-replace-groups.md) ✅ — tags are the grouping primitive; Org → Site → Device is the hierarchy that remains

### Deployment & runtime layout

- [0042 — Machine-level data directory (ADMZ_HOME) + Windows-service deployment](decisions/0042-machine-level-data-directory.md) ✅ — all state under one `ADMZ_HOME` resolved call-time by `admz/paths.py` (specific `ADMZ_*_PATH` overrides still win); on Windows, `C:\ProgramData\admz` with the service supervised by Shawl as LocalSystem, so no user profile and no stored service password
- [0054 — Production gets its own clone and its own venv: separating what runs from what is being changed](decisions/0054-separate-production-tree-and-venv.md) 📋 — ADR-0042 decided where production's *data* lives; this decides where its *code and interpreter* live, after one tree and one venv serving production, staging and every test run produced a live contradiction: rebuilding the venv for `master` breaks staging (60 commits stale), leaving it crash-loops production on restart (mcp 2.x code, mcp 1.26 venv). Production moves to a dedicated **clone** (not a worktree — worktrees share `.git`) at a deliberate SHA with a venv built from that SHA's `requirements.txt`; the service's `--cwd` and interpreter are repointed and nothing else about it changes. Deployment stops being "someone pulled" and becomes `scripts/deploy-prod.ps1`, whose step 4 — import the new code on the new venv *before* the service is stopped — is the point of the whole record. The host owns what it runs (detached HEAD + `deployed.log`), not a tag. Explicitly does **not** separate `ADMZ_HOME`, git config, gh identities, the fleet, or the machine. Blocked on #235; absorbs #173
- [0045 — GitHub App "Connect GitHub" flow for config-repo backup](decisions/0045-github-app-backup.md) ✅

## Plans

Approved implementation plans for staged work (design fixed, build pending — tracked as GitHub issues).

- [Separate the production tree and venv from the dev workspace](../plans/dev-prod-split.md) — [ADR-0054](decisions/0054-separate-production-tree-and-venv.md), **shipped 2026-08-04**. Slices: build a pinned production clone + its own venv, repoint the Shawl service's two paths, replace the implicit `git pull` deployment with `scripts/deploy-prod.ps1` (six steps, of which step 4's pre-stop smoke check is the one that matters), bring `setup-admz-service.ps1` into the repo and rewrite `DEPLOYMENT_WINDOWS.md` around the deployment that actually runs (#173). Staging's own venv deferred with a stated trigger. (Was blocked on #235/#236, since completed.)
- [Read-only fleet account sweep](../plans/fleet-account-sweep.md) — finding temp device accounts that predate #315's persistence fix. **Authorized** (`q_70025d93`) and not yet run. Blocked on a catalog addition: there is no `pwdgrp.cgi` read operation, so the enumeration path the authorization assumed does not exist. Should share a production maintenance window with #165, which needs the same atlas reinstall.
- [Demo setup wizard](plans/demo-setup-wizard.md) — ADR-0047 slice 3+: fragment activation pushes with state-flip-on-completion (fixes the scenario marker-timing bug), demo-aware rules with auto-attached trigger signals, and the guided chat setup surface (`demo_setup_status` + gated `set_event_ingest`)
- [ACS poller watermark](plans/acs-poller-watermark.md) — ADR-0057: replace the ACS action-rule poller's local-clock high-water mark with store-identity firing plus a `_seeded` boolean, settling the three decisions #210 left open — the clock-domain question (removed, not answered), what `more` should do (surface it; paging deferred with reasons), and what `ts_ms == 0` means (fire it, store a poll-time fallback so retention cannot reap it, make it loud). Corrects the orientation pass's own `_seed_ms` proposal, which was still a local-clock value gating remote-clock events (#210)
- [Detection lost to an unreadable rule cache](plans/acs-refire-on-callback-failure.md) — ADR-0058: #255 asked whether to fix the un-retried `on_event` failure with fire-before-append, a bounded re-fire set, or by accepting it. All three are rejected: `evaluate` has a single raise path (`_refresh`), so the defect is in the evaluator, not the poller, and fixing it there closes the gap on all five event paths — including the three with no retry buffer and the two that fail silently — while adding no state to any poller. Carries the corrected cost model for fire-before-append and the failure-direction argument that a re-fire set is *not* the seen-set ADR-0057 rejected (#255)

- [Move the provisioning gate to the decision point](plans/provisioning-gate-decision-point.md) — ADR-0059 build slices: the gate moves from the two discovery entry points to `onboard_device_credentials`'s `needsetup` branch, so the register/onboard asymmetry cannot recur. Settles what the ADR left open (blocked envelope carries device id + host only — the factory-default device's own metadata is attacker-supplied; callers pass the envelope up unchanged rather than each wording their own), **corrects the ADR's five-row caller table to the four call sites that exist on master**, and slices the fail-open `ContextVar` in on its own with both hazard tests plus a static no-bare-`set()` lint, before any behaviour changes. Does not close #313 (#199 item 3, #193)
- [Stores must resolve their DB path at call time](plans/lazy-store-singletons.md) — ADR-0042 amendment: #258 asked which lazy-singleton idiom should win across ~110 import sites. **Both lose.** Measured: the four stores already converted to `get_x()` bind at *first use* and never rebind — behaviourally identical to the eager ones, because it is the caching in `__init__`, not the timing, that freezes the path. The fix is a call-time `_db_path` property plus schema-ensure moved into `_connect()`, which delivers *both* properties (no import-time I/O **and** a honoured `ADMZ_DB_PATH`) for **0 call-site changes** against ~110 — prototyped on `fleet_settings` and reverted. Scope is 17 store modules, not 110 sites; `fleet_settings` goes second, neither proving ground nor victory lap. Carries the anti-vacuity test design ("no store connected" is trivially true if nothing imported anything) and a `CONVERTED | PENDING` inventory latch so store #18 cannot escape mid-conversion (#258)
- [Advanced capability switches](../plans/advanced-switches.md) — ADR-0052: one registry (`admz/capabilities.py`) for every dangerous or privileged switch, so a new one is declared rather than inventing another env var; loud in all five capability surfaces
- [Demo inference](../plans/demo-inference.md) — ADR-0051 build slices: deterministic collection, agent narration
- [Invert the fleet-setting allow-list](../plans/invert-setting-allowlist.md) — ADR-0053: deny-by-default for the LLM after an enumerated deny-list failed four times in the same direction (#152, #168, #195, #203)
- [Demo modal restyle](../plans/demo-modal-restyle.md) — UI slice
- [git UTF-8 decode](../plans/git-utf8-decode.md) — decoding `git` output explicitly rather than by locale
- [Refuse to learn Basic over plaintext HTTP from a device challenge](plans/auth-downgrade-defence.md) — ADR-0007 amendment: #171 reported that a device (or anyone answering at its address) can drive self-heal from Digest down to Basic-over-HTTP, putting the stored admin password on the wire in base64, permanently. Confirmed by in-process measurement — and the measurement also settles the design: `httpx.BasicAuth` sends the credential **preemptively**, so **the leak precedes the acceptance check**, and anything acting at persistence time is too late. One sub-claim of #171 is disproved (refusing 443 is *not* sufficient; `_method_for_scheme` looks up the *new* scheme's method, so the `ConnectError` flip yields digest — the challenge header is the only credential-leaking input). The fix is deliberately **narrow** — refuse only `offered == "basic" and scheme == "http"`, proceed without learning rather than raise — because the blanket ratchet strands a legitimately reconfigured camera, breaks `test_method_relearn_digest_to_basic`, and still leaks: the #250 shape. Carries the operator pin (blocked on a prerequisite: MCP `update_device` takes an unconstrained `updates` and is ungated, so the profile is already model-writable), a key-only audit row on `_persist_learned_auth` following #276's allow-list precedent, a recommendation **against** the unauthenticated probe with reasons, and five named residual leaks the rule does not close (#171)

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
- **"I'm about to accept a release"** → [ACCEPTANCE.md](../ACCEPTANCE.md) → the user story behind any check that fails → file the issue with a regression test the suite would have caught it with.
