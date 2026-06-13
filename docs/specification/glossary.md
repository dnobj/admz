# Glossary

Terms, abbreviations, and concepts used throughout the ADMZ specification and codebase.

## A

**ACAP** — Axis Camera Application Platform. The application runtime on Axis devices. ADMZ may interact with installed ACAPs via the catalog but does not manage the ACAP runtime itself.

**Account** — A username + password (+ optional metadata: type, purpose) stored against a device in the registry. A device may have multiple accounts (e.g. `default`, `service`, `viewer`).

**ADR** — Architecture Decision Record. The format used in [decisions/](decisions/) for capturing load-bearing design choices.

**API family** — A category of executors. Currently the only family is `vapix`; the design supports adding others (e.g. `acs`, `aoa`) by implementing `BaseExecutor` and creating a `catalog/<family>/` namespace.

**API generation** — Within the VAPIX family, the kind of HTTP shape an operation uses. Four generations: `legacy-cgi`, `json-rpc`, `config-rest`, `soap`.

**AppContext** — The shared bundle of orchestration objects (registry, catalog, executors, plan engine, snapshot engine, scheduler) used by the FastAPI surface. Initialized once per process in the lifespan handler.

**ARP** — Address Resolution Protocol. Used in discovery to find devices on the local subnet by their MAC address.

**At-rest encryption** — Encryption of credentials in the SQLite store using Fernet (AES-128-CBC + HMAC-SHA256). The key lives in `~/.admz/admz.key`.

**Audit log** — A record of who did what to which device when. ✅ Implemented as a SQLite-backed store (`admz/audit.py`); `record_event` is called across the MCP, REST, and confirm-approval surfaces.

**Axis OS** — The operating system on Axis devices. LTS milestones: 8.40, 9.80, 10.12, 11.11. Major-version upgrades typically must go through LTS milestones.

## B

**BaseExecutor** — The abstract base class for API-family executors. Concrete: `VapixExecutor`. Each defines `family` and async `execute(operation, device, credentials, params)`.

**Baseline** — The commit an operator has *blessed* as a device's intended configuration, named by the device's `baseline_sha` pointer (ADR-0031). Drift is measured against it and `restore` replays it by default. Distinct from the latest snapshot (which moves git HEAD) and from an [observation](#o) (what an audit merely recorded). Set by `snapshot` or by an explicit accept/promote.

**Bonjour** — Apple's name for the mDNS+DNS-SD service-discovery stack. ADMZ uses mDNS discovery to find Axis devices that announce `_axis-video._tcp.local.`.

## C

**Capture session** — A short-lived token bound to a device (or several) for out-of-band credential entry. The user opens `/capture/{token}` in a browser and submits the password directly — the LLM never sees it.

**Capabilities (module)** — A separate per-model API support registry distinct from the operation catalog. Each model has firmware-version snapshots of which APIs it reports via `apidiscovery.cgi`. Lets the resolver pre-check whether a model+firmware combination supports a given operation. 🚧 WIP.

**Catalog** — The YAML-driven repository of operation definitions under `catalog/`. Organized by API family → endpoint → operation. Each operation YAML describes one thing the system can do.

**Catalog-in-the-loop** — The MCP pattern where the LLM calls `query_catalog` first, gets back filtered operation specs, then calls `execute_operation`. Constrains the LLM to known-good operations rather than free-form HTTP construction.

**CatalogLoader** — The component that reads YAML files from disk and caches `_cgi_cache`, `_operation_cache`, `_index_cache`.

**CatalogResolver** — Maps (device, intent string) to a filtered list of catalog operations with parameter docs. Used by `query_catalog`.

**CGI** — Common Gateway Interface. The first generation of Axis APIs uses `/axis-cgi/{name}.cgi` URLs with query parameters or form data.

**config-rest** — The third generation of Axis APIs: REST endpoints under `/config/rest/{service}/v{N}` with JSON bodies.

**Confirm token** — A single-use token issued when a gated operation or plan is attempted. TTL 5 minutes. ✅ Unified: a single SQLite-backed `ConfirmStore` (`admz/api/confirm_store.py`) backs every gated path — single ops and plans, MCP and REST and the in-chat widget — so confirmation sessions are cross-process. (`url_*`-gated plans also serialize their steps into the session so the approving process can reconstruct and run them.)

**Confirm level** — One of `none`, `llm_confirm`, `url_only`, `url_and_password`. Mapped per risk class via fleet settings.

## D

**Device** — An Axis network device known to the registry. Identified by a `device_id` (typically the MAC address). Has `device_info` (model, host, tags, location) and zero or more accounts.

**Device family** — The category of an Axis device: camera, encoder, speaker, intercom, access-control, switch, radar, I/O module, etc.

**DeviceRegistry** — The ABC defining the credential-storage contract. Concrete: `SQLiteDeviceRegistry`, `VaultDeviceRegistry`. The factory picks one based on `DEVICE_REGISTRY_BACKEND`.

**Discovery** — Finding Axis devices on the network. Seven protocols, two-phase orchestrator, merge-by-MAC.

**DiscoveryOrchestrator** — Runs the seven protocols in two phases (broadcast then HTTP/SNMP enrichment) and merges results.

**DriftDetector** — Compares a device's live state against its **baseline** (the commit named by the device's `baseline_sha`), not git HEAD (ADR-0031). Produces a `DriftReport`; `no_baseline=True` when the device has no blessed baseline yet.

**Drift** — A device whose live state has diverged from its **baseline** configuration. Caused by manual edits at the device's own web UI, third-party tools, or restore failures.

## E

**ExecutionPlan** — A staged, validated multi-step plan. Has steps with dependencies, a failure policy, and a risk summary. Created via `create_plan`, runs via `execute_plan`.

**Executor** — A class that turns a catalog operation + device + credentials + params into an HTTP request, sends it, parses the response, returns a `StepResult`. The `VapixExecutor` handles all four VAPIX generations.

**Expect-timeout** — A catalog-declared response shape (`response.expect_timeout: true`) marking operations like `restart` and `factory-reset` where the device disappearing *is* the success signal.

**Experience Center** — Axis's customer demonstration facility. The original driver of the snapshot/restore work.

## F

**Facet** — A logical slice of a device's configuration, captured by a `FacetAdapter`. Examples: `image`, `network`, `time_config`, `stream_profiles`, `users`, `events`. Pluggable by decorating with `@register_facet`.

**FacetAdapter** — The ABC for snapshot facets. Each declares `applies_to:list[DeviceCriteria]`, `read_ops`, `restore_order`, and `serialize/deserialize`.

**Factory default** — A freshly-factory-reset Axis device with no credentials set. ADMZ's credential probe detects this via the device's response to unauthenticated requests.

**FailurePolicy** — How a plan handles a failed step. Values: `stop` (only one implemented), `skip_dependents` (declared, behaves as `continue`), `continue` (declared, behaves as `continue`). 🚧

**Family** — See "API family."

**Fernet** — A symmetric encryption recipe from the `cryptography` library. ADMZ uses it to encrypt passwords in the SQLite store.

**Fleet** — The collection of devices known to one ADMZ instance.

**Fleet capture session** — A capture session for setting a fleet-wide value (not a per-device credential), e.g. the default password used during provisioning.

**Fleet settings** — Key-value pairs in SQLite that govern fleet-wide behavior: default passwords, confirmation levels, the `get_credentials` toggle.

**Fork (device config)** — Copy one device's configuration as the starting point for another device, via the snapshot repo.

## G

**Generation** — See "API generation."

**GitRepo** — The thin wrapper around `git` subprocess calls used by the snapshot subsystem.

## H

**Hint (knowledge)** — A free-form bit of advice the knowledge resolver returns alongside catalog operations. Useful for surfacing device-specific quirks ("this switch doesn't speak VAPIX").

## I

**Intent** — A free-form natural-language phrase the LLM passes to `query_catalog`. The resolver maps it to relevant operations.

## J

**json-rpc** — The second generation of VAPIX APIs. POST JSON body to a CGI endpoint; the body contains `{"apiVersion", "method", "params"}`.

## K

**Knowledge** — A product/series/product-line YAML registry of advice for the LLM (`catalog/knowledge/`). Separate from the operation catalog.

## L

**legacy-cgi** — The first generation of VAPIX APIs. GET with query parameters, or POST with form data.

**Live** — A device's *current* on-the-wire configuration, obtained by probing it. Ephemeral — known only at the moment of a snapshot/audit/drift check. Compared against the [baseline](#b) to detect [drift](#d).

**LLM agent** — Any AI consumer of the MCP server (Claude, GPT-driven agent, custom Anthropic SDK client, etc.). One of the six personas.

**LLM-confirm** — The default confirmation level for `service-affecting` operations. The LLM presents the change and waits for the user's natural-language "yes."

**LTS** — Long-Term Support. Axis OS LTS milestones: 8.40, 9.80, 10.12, 11.11. Used by the upgrade-path computation.

## M

**MAC merge** — The discovery strategy of using MAC address as the primary key when merging results from multiple protocols.

**MCP** — Model Context Protocol. The protocol used by LLM agents to invoke ADMZ tools.

**MCP server** — The primary entry point for LLM-driven ADMZ use. Implemented in `admz/mcp/server.py`. Exposes 47 tools (see `docs/MCP_TOOLS_REFERENCE.md`).

**mDNS** — Multicast DNS. Used by Axis devices to announce themselves via Bonjour/Zeroconf.

## N

**Nickname** — A human-friendly name for a device, optionally stored in `device_info`. Lookable via the registry.

**Normalized YAML** — The diff-friendly, alphabetically-ordered, serialization of a facet's configuration. Stored under `fleet/{device_id}/config/`.

## O

**Observation** — The configuration an audit (or snapshot) actually *saw* and recorded to git, named by a device's `latest_observed_sha` (ADR-0031). Audits append observations (commit-on-change) **without** moving the [baseline](#b); any observation can later be promoted to baseline. Contrast [live](#l) (not yet recorded) and [baseline](#b) (blessed).

**Operation** — A single thing the system can do against a device. Defined by one YAML file in the catalog. Identified by `cgi:action` (e.g. `param.cgi:update`, `cert:listCertificates`).

**Operation ID** — The string identifier of a catalog operation. Format: `<cgi-or-rest-or-soap-name>:<action>`.

**ONVIF** — Open Network Video Interface Forum. An industry standard for IP camera discovery and control. ADMZ uses WS-Discovery to find ONVIF-compliant Axis devices.

**OOB** — Out-of-band. As in "out-of-band credential capture" — the user enters credentials in a browser form, separate from the LLM channel.

**Orchestrator** — See "DiscoveryOrchestrator."

**Organization (Org)** — The top level of the device hierarchy: *who owns the cameras*. Owns the git config repo (`repo_path`, optional `repo_remote_url`) and is the tenant/isolation boundary. Contains Sites. A `default` Org is bootstrapped on first run (adopting the legacy `~/.admz/config-repo/`). See ADR-0032 and [hierarchy.md](requirements/hierarchy.md).

**OUI** — Organizationally Unique Identifier. The first three bytes of a MAC address. Used to identify devices as Axis-manufactured.

## P

**param.cgi** — The single largest VAPIX endpoint. Exposes the entire device parameter tree (root.Image, root.Network, root.Time, etc.) as a key-value namespace.

**PlanEngine** — Validates and executes multi-step plans. Owns the `_plans` in-memory dict (per-process). For `url_*`-gated plans the full step data is also serialized into the confirm session (`plan_steps_json`), so a different process — e.g. the uvicorn web server approving a plan created in a chat MCP subprocess — can reconstruct and execute it.

**PlanStep** — One step in a plan. Has `operation_id`, `device_id`, `params`, optional `depends_on`.

**Pluggable** — Capable of being extended without modifying core code. ADMZ has four documented pluggable extension points: API families, discovery protocols, snapshot facets, registry backends.

**Probe (credential)** — Active testing of a device with no-auth, legacy defaults, and user-supplied credentials. Separate from passive discovery.

**Protected settings keys** — A set of fleet-setting keys (`confirm_level_*`, `confirm_password_hash`, `tool_get_credentials_enabled`) that the MCP server refuses to write. Only the web UI may change them.

**Provision** — Bring a new device under management: probe credentials, create or rotate admin user, store creds in registry.

## R

**Raw artifact** — The unmodified API response from a device, kept alongside the normalized YAML in the snapshot repo for faithful replay.

**Read-only** — The lowest risk classification. Operations that only read state; never gated.

**Registry** — See "DeviceRegistry."

**Resolver** — See "CatalogResolver" or "KnowledgeResolver."

**Restore** — Replay a captured configuration back to the device. Implemented as a write plan generated from git YAML by `RestoreBuilder`.

**RestoreBuilder** — Reads facet YAMLs from git, generates a list of write operations, hands off to the plan engine.

**Risk level** — One of `read-only`, `normal`, `service-affecting`, `dangerous`. Declared per operation in the catalog YAML. Drives the confirmation flow.

**Rollback** — Reverting a plan's effects. Currently only `param.cgi:update` operations support automatic rollback via pre-read snapshotting; rollback steps are generated but not auto-executed. 🚧

## S

**Schedule** — A recurring snapshot, persisted to `~/.admz/schedules.json`. Runs as an asyncio task.

**SDK (Anthropic / MCP)** — The Python library used to build the MCP server.

**Sensitive prefixes** — Param-tree prefixes (`root.HTTPS.PrivateKey`, `root.Network.Wireless.WPA.`, `root.RemoteService.`) that are never written to the snapshot repo.

**Serial number** — Often equal to or derivable from the MAC address on Axis devices. Used as the primary device identifier in some flows.

**Session (web)** — A server-side login session minted by `/login` under the `windows-local` backend (ADR-0033): Windows credentials validated in-process via `LogonUserW`, a 256-bit bearer token in the `admz_session` cookie (stored hashed in `web_sessions`), sliding TTL, revoked on logout. The session snapshots the Principal incl. the account's Windows group memberships. SSO sign-ins (see **SSO (Negotiate)**) mint the identical session.

**SSO (Negotiate)** — "Continue as the signed-in Windows user" on the login page (ADR-0035): the browser and Windows complete a Kerberos/NTLM handshake over HTTP `Negotiate` at `GET /login/sso`, handled in-process by SSPI (`admz/win_sspi.py`) — no password typed, no IIS, no new dependencies. Falls back to the credential form on any failure; disable with `ADMZ_SSO_NEGOTIATE=0`.

**Site** — The second level of the device hierarchy: *which site (usually a local network) the cameras are installed on*. Belongs to exactly one Organization; every device belongs to exactly one Site. The sidebar's site switcher scopes the fleet view. Below Site there is no Group level — devices are organized with **tags** (ADR-0032).

**Service-affecting** — Risk classification for operations that may interrupt service but are recoverable. E.g. restart, network reconfiguration, baseline restore. Default confirm level: `url_only` (the on-screen approval widget).

**SOAP** — Simple Object Access Protocol. The fourth generation of VAPIX APIs (WSDL-based web services under `/vapix/services`).

**Slot / Unit** — The device-identity model (ADR-0036). The **slot** is the stable ADMZ identity (`device_id`) — git config is keyed by it, so it survives hardware replacement; the **unit** is the currently-installed physical device, identified by `mac_address`. "Replace hardware" rebinds a slot to a new unit (`POST /api/devices/{id}/replace-hardware`) and the slot's config/baseline follow automatically. `device_id`'s value is historically the first unit's MAC, but is semantically the slot — there is no separate `slot_id` surrogate.

**Tombstone (config)** — A `Removed: <device_id>` commit (writing `fleet/{device_id}/REMOVED.yaml`) that records a deliberate device deletion in the git config repo while keeping its history, distinct from a device that merely went stale (ADR-0036, reusing the ADR-0031 Audit-commit pattern).

**SnapshotEngine** — Orchestrates per-device snapshots: runs facet reads, sanitizes, writes to git.

**SnapshotScheduler** — The asyncio-driven scheduler for recurring snapshots.

**SSDP** — Simple Service Discovery Protocol. Used by UPnP, supported by Axis devices.

**StepResult** — The result of a single executor call: success/failure, status code, parsed data, warnings, duration.

## T

**Tag** — A free-form string label on a device, and the device-grouping primitive (ADR-0032 — it replaced the former Group level). Drives the web sidebar/`?tag=` filtering, scheduling/drift/snapshot scoping (`tag_filter`), and search. Exact membership, case-sensitive. Not to be confused with `Principal.groups` (user-identity RBAC).

**TempCredential** — A short-lived device user account created by `create_temp_credentials`, auto-cleaned up by the background loop. Username pattern: `at_<8 hex>`.

**Two-gate** — The safety model where every write operation passes through two independent gates: (1) semantic — LLM/user reviews the change in natural language; (2) mechanical — catalog risk-level check that can block even after user approval.

## U

**Untracked / WIP** — Files in the working tree but not yet committed. As of 2026-05-17 the repo has ~158 such files (SOAP catalog, capabilities module, confirm_store, temp_credentials, etc.).

## V

**VAPIX** — Axis's proprietary device API. Four generations: legacy-cgi, json-rpc, config-rest, soap.

**VapixExecutor** — The concrete executor for VAPIX operations. Lives in `admz/executor/vapix.py`.

**Vault (HashiCorp)** — The optional alternative backend for the device registry. Activated by `DEVICE_REGISTRY_BACKEND=vault`.

**Volatile prefixes** — Param-tree prefixes (`root.Properties.System.Soc.`, `root.Properties.Firmware.`) that are stripped from snapshots because they change without configuration intent.

## W

**WS-Discovery** — Web Services Dynamic Discovery. The SOAP-over-UDP multicast protocol ONVIF uses for device discovery.

## Z

**Zeroconf** — Zero-configuration networking. The Python library used for mDNS discovery on non-Windows platforms.
