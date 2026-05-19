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
for each one to be managed.

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

- ADRs: [0016](../decisions/0016-merge-discovery-by-mac.md), [0017](../decisions/0017-two-phase-discovery.md), [0007](../decisions/0007-per-protocol-auth.md)
- Cross-cutting: [reliability.md](reliability.md), [performance.md](performance.md)
- Design notes: [NETWORK_DISCOVERY_RESEARCH.md](../../NETWORK_DISCOVERY_RESEARCH.md)
- Code: `admz/discovery/`
