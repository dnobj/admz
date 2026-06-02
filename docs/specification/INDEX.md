# Specification Index

Complete table of contents for the ADMZ specification.

## Entry points

- **[README.md](README.md)** — what this directory is and how to read it
- **[00-overview.md](00-overview.md)** — mission, scope, non-goals
- **[glossary.md](glossary.md)** — terms and abbreviations

## Personas

Who ADMZ is built for. Each persona drives a set of user stories and requirements.

- [Experience Center operator](personas/experience-center-operator.md) — the original driver of the snapshot/restore work
- [Enterprise fleet operator](personas/enterprise-fleet-operator.md) — Vault-backed, hundreds-of-devices use case
- [LLM agent](personas/llm-agent.md) — the AI consumer of the MCP surface
- [Web-Chatbot user](personas/web-chatbot-user.md) 📋 — the operator who doesn't run their own agent (expected primary persona)
- [Security-conscious operator](personas/security-conscious-operator.md) — the human at the keyboard who cares about safety gates
- [Catalog contributor](personas/catalog-contributor.md) — an external developer adding new operations, protocols, or backends

## User stories

Workflows the system must support. Grouped by area.

- [Device onboarding](user-stories/device-onboarding.md) — manual, discovery-driven, and provision flows
- [Credential management](user-stories/credential-management.md) — capture, probe, rotate, temp creds
- [Snapshot and restore](user-stories/snapshot-and-restore.md) — capturing, restoring, forking device configs
- [LLM-driven configuration](user-stories/llm-driven-configuration.md) — catalog query → execute → confirm
- [Chatbot-driven workflows](user-stories/chatbot-driven-workflows.md) 📋 — what the bundled chat client will deliver
- [Network discovery](user-stories/network-discovery.md) — finding devices on the local network
- [Demo workflows](user-stories/demo-workflows.md) — Experience Center-specific demo/tag/restore patterns
- [Drift and monitoring](user-stories/drift-and-monitoring.md) — detecting and reconciling unauthorized changes
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
- [Scheduling](requirements/scheduling.md)
- [Knowledge and capabilities](requirements/knowledge-and-capabilities.md) — product hints and per-model API support
- [Firmware](requirements/firmware.md) — downloader, upgrade-path
- [MCP server](requirements/mcp-server.md) — tool surface, gating
- [Web API](requirements/web-api.md) — REST surface
- [Web UI](requirements/web-ui.md)
- [Web chatbot](requirements/web-chatbot.md) 🚧 — bundled Gemini-powered chat client (Phase 5)
- [Organization hierarchy](requirements/hierarchy.md) 📋 — Org → Site → Group → Device (draft skeleton)

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

### Safety & gating

- [0005 — Two-gate plan approval (semantic + mechanical)](decisions/0005-two-gate-plan-approval.md)
- [0006 — Multi-level confirmation by risk class](decisions/0006-multi-level-confirmation.md)
- [0018 — Risk-aware "expect-timeout" semantics for reboot ops](decisions/0018-expect-timeout-semantics.md)
- [0020 — Protected fleet settings keys not writable from MCP](decisions/0020-protected-fleet-settings.md)

### Authentication (Phase 4)

- [0021 — Windows IWA via reverse proxy](decisions/0021-windows-iwa-via-reverse-proxy.md)
- [0022 — API keys for agents](decisions/0022-api-keys-for-agents.md)
- [0023 — LDAP group enrichment](decisions/0023-ldap-group-enrichment.md)

### Entry-point surfaces

- [0024 — Bundled web chatbot](decisions/0024-bundled-web-chatbot.md) 🚧 (accepted, Phase 5 in progress)
- [0025 — Gemini 3.1 + native MCP for the chatbot](decisions/0025-gemini-chatbot-mcp-native.md) 🚧

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

### Snapshot/restore

- [0012 — Snapshot/restore implemented on top of the plan engine](decisions/0012-snapshot-on-plans.md)
- [0013 — Hybrid YAML + raw artifact format](decisions/0013-hybrid-yaml-and-raw.md)

### Discovery

- [0016 — Merge discovery results by MAC](decisions/0016-merge-discovery-by-mac.md)
- [0017 — Two-phase discovery (broadcast then enrich)](decisions/0017-two-phase-discovery.md)

## Reading paths by role

- **"I'm onboarding to ADMZ"** → README → overview → personas → user-stories → glossary.
- **"I'm adding a feature"** → overview → relevant capability requirement → related decisions.
- **"I'm adding a catalog operation"** → catalog requirement → decisions 0001–0004 → existing YAML in `catalog/vapix/`.
- **"I'm adding a new device family"** → extensibility requirement → decisions 0011, 0015.
- **"I'm hardening security"** → security requirement → decisions 0005, 0006, 0009, 0010, 0014, 0020.
