# ADR-0040 — Axis Camera Station Pro module (read-only v1)

**Status:** Accepted (2026-06-19)
**Builds on:** ADR-0039 (platform + pluggable modules), ADR-0035 (Negotiate SSPI).

## Context

ADMZ manages Axis edge devices. The next domain to manage is **Axis Camera
Station Pro** (ACS Pro), the VMS. With the module platform (ADR-0039) in place,
ACS Pro becomes **module #2** (`admz/modules/acs_pro/`). The atlas already models
the ACS Pro HTTP-JSON Facade API (`axis-api-atlas/data/acs-pro/`,
`/Acs/Api/<Facade>/<Operation>` on port 29204), and every ACS device carries a
`MacAddress` — a deterministic join to ADMZ's `mac_address` (ADR-0036).

## Decision

A read-only ACS Pro module whose **entire footprint is opt-in**: until an
operator connects a server from **Settings → Modules**, ACS Pro adds nothing to
the sidebar, the chatbot, or the prompt.

### Enablement (the user's "no UI space unless used" requirement)

One JSON blob in `fleet_settings["acs_pro"]` = `{enabled, server_url, port,
verify_tls}`. There is **no password field** — ACS authenticates with the ADMZ
process's own Windows identity via Negotiate. The module's `nav_section()`,
`mcp_tools()`, and `build_prompt_section()` all return empty unless
`acs_enabled()`. The executor is always registered (cheap) so the family
resolves, but nothing *visible* appears until connected. The Settings "Modules"
card has a **Test connection** button (a read-only api-version probe) that works
against a server *before* it's saved/enabled.

### Auth — Negotiate as the process identity

`admz/modules/acs_pro/negotiate.py` is an outbound SPNEGO initiator that reuses
the `win_sspi` SSPI ctypes (the mirror of the ADR-0035 acceptor's loopback test
client): `AcquireCredentialsHandle(OUTBOUND)` + `InitializeSecurityContext` for
SPN `HTTP/<host>`, emitting `Authorization: Negotiate <base64>` and running the
NTLM challenge leg. No ACS password is stored or logged. **Caveat:** outbound
Negotiate authenticates as whatever Windows account the ADMZ process runs as — in
the single-operator local deploy that *is* the operator (the intent).
Authenticating as a *different* operator from a shared service is the Kerberos
double-hop (S4U constrained delegation) — out of scope.

**NTLM is connection-bound.** A local ACS server challenges with NTLM (not
Kerberos — no HTTP SPN registered), which is a multi-leg handshake tied to one
TCP connection: request-1 carries the type-1 token → `401` + type-2 challenge in
`WWW-Authenticate: Negotiate <b64>` → request-2 carries the type-3 token →
`200`. The executor therefore holds **one keep-alive `httpx.Client`** across both
legs; a fresh connection per leg makes the server reject the type-3 token (it
surfaced as an opaque `400` until fixed). ACS also reports its error type in the
HTTP **reason phrase** (often with an empty body), so the executor surfaces that.

### Executor — `acs-pro` family, `self_heals() == False`

`AcsProExecutor(BaseExecutor)` POSTs JSON to `<base>/Acs/Api/<Facade>/<Op>`,
tolerates ACS's self-signed cert **per connection only** (an explicit `verify`
flag, never a global relaxation), and degrades to a clean failed `StepResult` on
auth-unavailable / unreachable / non-2xx. `self_heals() == False` (ADR-0039), so
the gate never rewrites stored auth for this family — a server target
authenticates per request.

### Tools (read-only) + correlation

The module contributes six MCP tools (gated on enabled): `acs_get_api_version`,
`acs_get_system`, `acs_list_devices`, `acs_list_cameras`,
`acs_get_recording_status`, and the headline **`acs_find_camera_for_device`** —
which reads an ADMZ device's MAC, lists ACS devices + cameras, and matches on
`MacAddress` (serial fallback) to return the ACS camera(s). A prompt section
teaches the LLM the MAC join so "is the lobby camera in ACS?" chains naturally.

The MCP `list_tools`/dispatch now append `module_registry.tool_specs_all()` after
the frozen 52 device tools; with ACS disabled that set is empty, so the device
wire order is unchanged (snapshot test holds). A `/acs` page (server status +
camera list) renders only when enabled and redirects to Settings otherwise.

## Scope

**In v1:** enablement + Settings Modules card, the Negotiate executor, the six
read-only tools + correlation, the gated `/acs` page + "Cameras" nav item, the
prompt section, and unit tests for all of it (config/gating/correlation/executor
with mocked transport + the MCP surface growth).

**Out of scope (this version):** mutating ACS operations (StartRecording, PTZ,
schedules) — the gate is ready for them behind confirmation later; a persisted
device↔camera cross-reference table; multi-user S4U delegation.

**Live-verified (2026-06-19)** against a real ACS Pro 6.16 server (API 2.43) on
the dev box: Negotiate/NTLM authenticated end-to-end as the operator;
`GetApiVersion`/`GetSystem`/`GetDeviceList`/`GetCameraList` returned real data;
and `acs_find_camera_for_device` correlated the live ADMZ fleet to ACS by MAC —
including a multi-sensor P3748-PLVE → 4 cameras and speakers (C1710, C1110-E) →
device-matched with zero cameras, exactly as intended.
