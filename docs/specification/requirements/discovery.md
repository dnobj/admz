# Requirements: discovery

Finding Axis devices on the local network. Seven protocols, two-phase
orchestration, merge-by-MAC, soft-fail per protocol.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-DISC-001 — Seven discovery protocols ✅
Each is a separate module under `admz/discovery/` implementing
`DiscoveryProtocolBase`:

| Protocol | What it sees | Notes |
|---|---|---|
| mDNS | `_axis-video._tcp.local.` and `_http._tcp.local.` | Windows path uses raw sockets; non-Windows uses zeroconf |
| SSDP | UPnP M-SEARCH responses | Optional XML description fetch for richer metadata |
| ONVIF (WS-Discovery) | NetworkVideoTransmitter via UDP multicast | Library: `WSDiscovery` |
| ARP scanner | scapy ARP scan + OS `arp -a` fallback | Falls back when no admin/root |
| Ping sweep | ICMP via system `ping` | Opt-in (disabled by default) |
| HTTP probe | `Server`, `AXIS-Setup` headers, basicdeviceinfo | Phase-2 enrichment |
| SNMP | sysDescr + sysName | Phase-2 enrichment |

### FR-DISC-002 — Two-phase orchestration ✅
`DiscoveryOrchestrator.discover()`:
- Phase 1: broadcast protocols (mDNS, SSDP, ONVIF, ARP, ping) run
  concurrently
- Phase 2: enrichment (HTTP probe, SNMP) runs only against IPs phase 1
  found

See [ADR-0017](../decisions/0017-two-phase-discovery.md).

### FR-DISC-003 — Merge-by-MAC ✅
Results from multiple protocols fuse into a single `DiscoveredDevice`
keyed by MAC. IP fallback when MAC not yet known. Each field takes
the first non-empty value. See
[ADR-0016](../decisions/0016-merge-discovery-by-mac.md).

### FR-DISC-004 — Soft-fail per protocol ✅
`DiscoveryProtocolBase.safe_discover()` wraps each protocol's
`discover()` in try/except + timeout. One protocol's failure doesn't
abort the others.

### FR-DISC-005 — Per-protocol togglable ✅
The MCP tool accepts per-protocol booleans
(`enable_mdns`, `enable_ssdp`, `enable_onvif`, `enable_arp`,
`enable_ping`, `enable_http_probe`, `enable_snmp`). The CLI exposes
matching `--no-*` flags and `--enable-ping`.

### FR-DISC-006 — Axis OUI detection ✅
`AXIS_OUI_PREFIXES` set in `admz/discovery/models.py`.
`is_axis_mac(mac)` returns True for MACs starting with any registered
Axis OUI. Used by `--axis-only` filter and result sorting (Axis
devices first).

### FR-DISC-007 — Active credential probing ✅
`admz/discovery/credential_probe.py::probe_credentials(host, ...)`:
- Tries no-auth → legacy `root/pass` → user-supplied passwords
- Returns `ProbeStatus`: `FACTORY_DEFAULT`, `AUTHENTICATED`,
  `AUTH_FAILED`, `UNREACHABLE`
- Detects per-protocol auth methods via `_detect_auth_schemes`
- Handles AXIS OS 12+ factory-default 401-with-`Axis-Setup` quirk
- Separate from passive discovery (FR-DISC-001 to 006); credential
  probing is on-demand and per-host.

### FR-DISC-008 — Discovered devices are not auto-registered ✅
`discover_network_devices` returns the list. Operators (or LLM agents)
explicitly call `register_discovered_device(device_id, ip_address, ...)`
for each one to be managed. In the console, the operator can instead
select devices in the discovery widget and add them together
(FR-DISC-011). A scan never registers anything by itself.

### FR-DISC-009 — MAC-based IP reconciliation ✅
`reconcile_device_addresses` (MCP) runs a discovery scan and updates any
*already-registered* device whose MAC now answers at a different IP — DHCP
moved it. It follows the MAC (the `device_id`), not the stale IP, so it
self-corrects the registry without re-registering anything. Core:
`admz/discovery/reconcile.py::reconcile_device_ips(registry, discovered)`,
which returns the list of `{device_id, old_host, new_ip}` changes. This is the
discovery-side fix for the "device moved IP → ADMZ says unreachable" failure
(the real-world I8016: `.207` → `.208`). Devices discovery didn't see are left
untouched; nothing is auto-registered.

### FR-DISC-010 — A scan is kept server-side and says what is already registered 📋
`discover_network_devices` saves each scan (principal, subnet, `axis_only`, every device
with its registry fields) to `discovery_scans` and keeps it for 24 hours. The result
gains `scan_id`, `scan_url`, `axis_count`, `new_axis_count`, `factory_default_count`,
and per device `registered_device_id`, matched by canonical MAC, the same rule the deep
survey uses. `GET /api/discovery/scans/{scan_id}` returns a scan only to the principal
that ran it, and computes registration state when it is read, so a device added after the
scan shows as registered. A scan run under the `mcp-standalone` principal is not saved.
A scan is a record of one run, not an accumulating cache (KL-DISC-002 stands). See
[ADR-0072](../decisions/0072-discovered-devices-are-added-from-the-chat-in-one-click.md).

### FR-DISC-011 — Selected discovered devices are added under one approval 📋
`POST /api/discovery/scans/{scan_id}/add` takes the selected device ids and opens **one**
`add_discovered_devices` action session. The request is refused before any side effect when
it is cross-origin, and refused outright when the scan belongs to another principal or is
more than 60 minutes old.

- **Validation is all-or-nothing.** Every id must be an Axis device in the scan, with an
  IP and an identity (canonical MAC, or a 12-hex serial), and not registered. Duplicates
  collapse, and a batch holds at most 20 devices. One bad id rejects the request and
  creates nothing.
- **The session comes from the scan row, not the request body.** It is created through
  `gate_scan_write`, so its level is the operator-configurable provisioning level. Its
  sentence names every device by id and IP and states the account writes.
- **Approval is the existing `POST /api/chat/confirm/{token}`.**

On approval, each device is handled in turn:

1. **Identity is checked first.** `basicdeviceinfo.cgi:getAllUnrestrictedProperties` is
   read without authentication at the scanned host, and its `SerialNumber` is compared
   with the device id. A mismatch or no answer skips that device and writes nothing to it.
2. **Registration.** The device is registered unless something registered it since the scan.
3. **Onboarding runs under the one approval,** at most four devices at a time. The action
   is in both provisioning-authority lists, so no nested per-device card is raised. A
   device left needing credentials gets a capture session.

**Success means every listed device was registered and ended with working credentials.**
Otherwise the result names each device and what it lacks. The `confirm.approve` row
carries `added_devices`, `provisioned_devices` and `failed_devices`. See
[ADR-0072](../decisions/0072-discovered-devices-are-added-from-the-chat-in-one-click.md).

## Non-functional requirements

### NFR-DISC-001 — Discovery is read-only on the network ✅
Discovery never modifies any device. The active credential probe
(FR-DISC-007) is read-only against the device's auth surface — it
sends candidate creds, observes responses, never writes anything.

### NFR-DISC-002 — Library dependencies are independently loadable ✅
`zeroconf`, `scapy`, `pysnmp`, `WSDiscovery`, `httpx` are listed in
`requirements.txt`. Each protocol gracefully degrades when its
library isn't installed (logs warning, returns empty).

### NFR-DISC-003 — Windows compatibility ✅
The mDNS path on Windows uses raw socket DNS PTR queries instead of
zeroconf's AsyncServiceBrowser (which doesn't play well with
ProactorEventLoop). SSDP uses 0.5s blocking timeout in an executor
to dodge Windows non-blocking-socket issues.

## Known limitations

### KL-DISC-001 — Phase-2 fan-out is unbounded ⚠️
At /16-scale subnets the enrichment phase opens many concurrent
HTTPS connections. Mitigation: use `--subnet` to constrain. A
semaphore (matching the Phase 3D snapshot semaphore) is a planned
follow-up — see [performance.md](performance.md) KL-PERF-001.

### KL-DISC-002 — No persistent device cache ⚠️
Each discovery call is independent. Devices that respond only
intermittently may be missed in a single scan. A "last seen" cache
would let a sparse-response network accumulate findings across runs.

### KL-DISC-003 — ARP fallback to OS arp -a is platform-specific ⚠️
Parses `arp -a` output, which has different formats on Windows / Unix.
Tested on both but new OS variants could break the parser.

### KL-DISC-004 — Phase-2 protocols can't see phase-1-invisible devices ⚠️
A device reachable only via HTTP probe (not mDNS/SSDP/ARP) is invisible
to the orchestrator. Operators add such devices manually.

## References

- ADRs: [0016](../decisions/0016-merge-discovery-by-mac.md), [0017](../decisions/0017-two-phase-discovery.md), [0007](../decisions/0007-per-protocol-auth.md), [0072](../decisions/0072-discovered-devices-are-added-from-the-chat-in-one-click.md)
- Cross-cutting: [reliability.md](reliability.md), [performance.md](performance.md)
- Design notes: [NETWORK_DISCOVERY_RESEARCH.md](../../NETWORK_DISCOVERY_RESEARCH.md)
- Code: `admz/discovery/`
