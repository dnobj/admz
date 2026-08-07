# User stories: device onboarding

How devices get added to ADMZ. Three paths exist — manual, discovery-driven, and provision-driven — for different starting conditions.

## US-DO-001 — Manual single-device registration

**As an** Experience Center operator **with** a known camera IP, model, and credentials, **I want to** add the device to ADMZ from the web UI **so that** I can manage it without using the device's own admin page.

**Acceptance criteria:**
1. The web UI `/add-device` page accepts: `device_id`, `host` (IP or hostname), `model`, `location`, `tags`, and optionally a `default` account with `username` + `password`.
2. On submit, the device appears in `/api/devices` and the credential is encrypted at rest in `admz.db`.
3. The plaintext password never appears in the device's `info` JSON, nor in the device list response, nor in server logs.

**Related requirements:** [core-platform](../requirements/core-platform.md), [credential-storage](../requirements/credential-storage.md), [security](../requirements/security.md).

## US-DO-002 — Manual single-device registration (LLM)

**As an** LLM agent **with** a user-provided IP and password, **I want to** register a device via the `register_device` MCP tool followed by `add_account` **so that** my user doesn't have to switch surfaces.

**Acceptance criteria:**
1. The LLM may call `register_device(device_id, device_info)` and receive `{success, device_id}`.
2. The LLM may call `add_account(device_id, account_id, account_data)` where `account_data` includes the password.
3. Subsequent operations against the device honor the stored credential without the LLM having to handle it again.
4. The LLM cannot retrieve the password afterwards — no MCP tool returns stored plaintext (`get_credentials` was removed, CR-1; `create_temp_credentials` returns a separate short-lived account).

**Related requirements:** [mcp-server](../requirements/mcp-server.md), [security](../requirements/security.md).

## US-DO-003 — Out-of-band credential entry

**As an** operator **with** an LLM-driven workflow, **I want to** enter a device's password in a browser form **so that** the password never enters the LLM's chat context.

**Acceptance criteria:**
1. The LLM calls `capture_credentials(device_id, …)` and receives `{success, url, token, expires_in_seconds}`.
2. The URL `/capture/{token}` renders a form labelled with the device ID and purpose.
3. On submit, the credential is stored in the registry; the form returns a confirmation page.
4. The LLM polls `check_capture_status(token)` and sees `status: completed` — but never sees the password itself.
5. Tokens are single-use, 256 bits of entropy, and expire after 10 minutes by default.
6. Batch capture (a single token for many `device_ids`) is supported for fleet provisioning.

**Related requirements:** [credential-storage](../requirements/credential-storage.md), [security](../requirements/security.md).

**Related decisions:** [0009 — OOB capture](../decisions/0009-oob-credential-capture.md).

## US-DO-004 — Discovery-driven registration

**As an** operator on a fresh network, **I want to** scan the local subnet for Axis devices and register the ones I recognize **so that** I don't have to type IPs and serials by hand.

**Acceptance criteria:**
1. `python -m admz discover --axis-only` (or the MCP `discover_network_devices` tool) returns a list of devices with IP, MAC, model, firmware, and which protocols saw each one.
2. Discovered devices are **not** auto-registered — the operator must explicitly call `register_discovered_device(device_id, ip_address, …)`.
3. The discovery merges results across 7 protocols (mDNS, SSDP, ONVIF, ARP, ping, HTTP probe, SNMP) by MAC address.
4. Axis devices (identified by MAC OUI) are sorted first in the results.

**Related requirements:** [discovery](../requirements/discovery.md).

**Related decisions:** [0016 — merge by MAC](../decisions/0016-merge-discovery-by-mac.md), [0017 — two-phase discovery](../decisions/0017-two-phase-discovery.md).

## US-DO-005 — Auto-provision a factory-default device

**As an** operator looking at a brand-new camera, **I want** ADMZ to set up the admin user automatically **so that** I don't have to use the device's first-boot web page.

**Acceptance criteria:**
1. The LLM (or REST caller) invokes `provision_device(host=…, username="root", password=…)`.
2. ADMZ probes the device:
   - **Factory default** → calls `pwdgrp.cgi:add-user` to create the admin user; stores credentials in the registry.
   - **Legacy default `root/pass`** → stores credentials; if `force_change=True`, rotates the password.
   - **Authenticated already** → stores the supplied credentials if they work.
   - **Unreachable** → returns a structured error with `host` and `detail`.
3. Generated passwords default to 24 chars (mixed case + digit) and are **never returned in the tool response** — nor retrievable afterwards (`get_credentials` was removed, CR-1). ADMZ uses the stored credential internally; for ad-hoc device access, mint a short-lived account via `create_temp_credentials`.
4. Per-protocol auth (`http`: digest, `https`: basic, etc.) is auto-detected via `WWW-Authenticate` and stored on the device profile so the executor uses the right scheme.

**Related requirements:** [mcp-server](../requirements/mcp-server.md), [credential-storage](../requirements/credential-storage.md), [discovery](../requirements/discovery.md).

**Related decisions:** [0007 — per-protocol auth](../decisions/0007-per-protocol-auth.md).

## US-DO-006 — Bulk-import a fleet from discovery

**As an** enterprise fleet operator with **hundreds** of devices, **I want to** discover, register, and provision in bulk **so that** initial deployment isn't a per-device chore.

**Acceptance criteria:**
1. `discover_network_devices(subnet="10.0.0.0/16")` enumerates devices on the larger network.
2. For each discovered device, `register_discovered_device` adds it to the registry.
3. For each registered factory-default device, `provision_device` is called.
4. A fleet-default password set via `set_fleet_setting("default_password", …)` is used during provisioning when no per-device password is supplied.
5. The fleet-default password is **set via the OOB `/capture/fleet/{token}` flow** — never typed into the LLM chat.

**Related requirements:** [discovery](../requirements/discovery.md), [mcp-server](../requirements/mcp-server.md), [performance](../requirements/performance.md).

## Known limitations (as of 2026-05)

- ⚠️ **No authentication on the web UI / REST API.** The OOB capture flow protects passwords from the LLM, but anyone on the same network can submit to `/capture/{token}` if they intercept the URL. Tokens are high-entropy, but adding API auth (Phase 4) is the durable fix.
- ⚠️ **Unbounded fan-out at fleet scale.** Discovery and provisioning open one task per host with no semaphore — fine at 100 devices, problematic at 1000+ (see `performance.md`).
- 📋 **No device de-duplication policy.** If discovery returns the same device twice (e.g. via two NICs), the operator must merge them manually.
