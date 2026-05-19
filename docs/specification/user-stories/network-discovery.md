# User stories: network discovery

Finding Axis devices on the local network without manually typing IPs or serials. Seven discovery protocols, two-phase orchestration, merge-by-MAC. The starting point for any onboarding workflow that isn't "I already know the IP."

## US-ND-001 — Scan the local subnet from the CLI

**As an** operator on a fresh install, **I want to** run a one-shot command and see every Axis device on my network with model, firmware, and which protocols saw it.

**Acceptance criteria:**
1. `python -m admz discover --axis-only` enumerates devices via mDNS, SSDP, ONVIF, ARP, HTTP probe, and SNMP (ping disabled by default).
2. Output is a human-readable table: IP, MAC, model, type, protocols-that-saw-it.
3. `--json` returns the same data as machine-readable JSON for piping into other tools.
4. Per-protocol toggles (`--no-mdns`, `--no-ssdp`, `--no-onvif`, `--no-arp`, `--enable-ping`, `--no-http`, `--no-snmp`) let operators skip protocols that are noisy or restricted on their network.
5. `--subnet 10.0.0.0/16` constrains the ARP scan to a specific subnet for larger networks.
6. Axis devices (identified by MAC OUI) are sorted to the top of the output.

**Related requirements:** [discovery](../requirements/discovery.md).

**Related decisions:** [ADR-0016](../decisions/0016-merge-discovery-by-mac.md), [ADR-0017](../decisions/0017-two-phase-discovery.md).

## US-ND-002 — Scan via the MCP tool (agent-driven)

**As an** LLM agent helping a user onboard a new fleet, **I want to** call `discover_network_devices` and get the same data the CLI returns, so I can present it conversationally.

**Acceptance criteria:**
1. `discover_network_devices(timeout=5.0, axis_only=false, subnet=None, enable_ping=false)` returns `{success, count, devices: [...]}`.
2. Per-device fields include: `ip_address`, `mac_address`, `hostname`, `model`, `serial_number`, `firmware_version`, `device_type`, `is_axis`, `vapix_available`, `factory_default`, `discovered_by` (protocol list).
3. Discovered devices are **never auto-registered.** The agent must explicitly call `register_discovered_device(...)` for each one.
4. The tool is read-only on the network side — no traffic that modifies any device.

**Related requirements:** [discovery](../requirements/discovery.md), [mcp-server](../requirements/mcp-server.md).

## US-ND-003 — Discovery + provisioning in one workflow

**As an** operator onboarding new factory-default cameras, **I want to** discover, register, and provision admin users in one fluid sequence.

**Acceptance criteria:**
1. Discovery returns factory-default devices (HTTP probe sees the `Axis-Setup: vapix` header / 401-with-Negotiate).
2. The operator calls `register_discovered_device(device_id, ip_address, ...)` for each one to be managed — typically using MAC as device_id.
3. `provision_device(device_id, password=...)` then probes auth state and either creates the admin user (factory-default) or stores the existing credentials.
4. The flow surfaces the per-device outcome (`status: provisioned | already_authenticated | unreachable | auth_failed`) so the operator can spot devices needing manual attention.

**Related requirements:** [discovery](../requirements/discovery.md), [credential-storage](../requirements/credential-storage.md).

**Related stories:** [device-onboarding](device-onboarding.md).

## US-ND-004 — Protocol-by-protocol resilience

**As an** operator on a restricted network, **I want** discovery to keep working even when some protocols are blocked.

**Acceptance criteria:**
1. Each protocol runs as an independent task wrapped by `safe_discover()`. A single protocol's failure (timeout, permission error, library exception) does not abort the others.
2. The orchestrator emits one log line per failing protocol so the operator can see what was blocked.
3. Phase-2 enrichment (HTTP probe, SNMP) runs only against IPs found in phase 1 — restricted networks where ARP/mDNS are blocked won't see enrichment overhead on every IP in the subnet.
4. ARP fallback to OS `arp -a` table when scapy lacks privileges — discovery degrades gracefully on hosts where it isn't running as admin/root.

**Related requirements:** [discovery](../requirements/discovery.md), [reliability](../requirements/reliability.md).

## US-ND-005 — Identifying non-Axis devices on the LAN

**As an** integrator deploying ADMZ in a customer network, **I want to** see ALL discovered devices (not just Axis ones) so I can detect rogue cameras or document the existing fleet.

**Acceptance criteria:**
1. Omitting `--axis-only` includes every responding device in the output.
2. Non-Axis devices are still returned with whatever metadata each protocol surfaced.
3. The `is_axis` field distinguishes them; `discovered_by` reveals which protocols picked them up.

## Known limitations

- ⚠️ **Unbounded fan-out at very large subnet scale.** Discovery itself doesn't currently semaphore phase-2 enrichment. A /16 with thousands of hosts opens many simultaneous HTTPS connections; tighten the subnet (`--subnet`) for those environments. Fleet *snapshot* concurrency is now bounded (Phase 3D), but discovery isn't yet.
- ⚠️ **No auto-registration.** Intentional. Operators (or LLM agents) must approve each device before it enters the registry.
- 📋 **Persistent discovery cache.** Each `discover_network_devices` call is independent; results are not cached. A future enhancement could keep a "last seen" timestamp per MAC for sparse networks where some devices respond only occasionally.
