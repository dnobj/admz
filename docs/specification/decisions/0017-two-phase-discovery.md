# ADR-0017: Two-phase discovery (broadcast, then enrich)

**Status:** Accepted, in production.
**Date:** Original design 2026-02 (`NETWORK_DISCOVERY_RESEARCH.md`).

## Context

The seven discovery protocols split into two categories:

- **Broadcast/multicast** — mDNS, SSDP, ONVIF (WS-Discovery), ARP, ping.
  These hit the whole local segment in one shot. No prior knowledge
  of who's out there.
- **Point-to-point enrichment** — HTTP probe, SNMP query. These need
  an IP to talk to. Running them against every IP in a /16 would
  open thousands of futile TCP connections.

Two design choices:

1. **Run everything in parallel.** Simple but expensive — HTTP probe
   blasts every IP in the subnet whether or not anything's there.
2. **Phase 1: broadcast → collect IPs. Phase 2: enrich only those
   IPs.** More plumbing, less waste.

## Decision

**Two-phase** orchestration in `DiscoveryOrchestrator.discover()`:

1. **Phase 1** — broadcast protocols run concurrently. `asyncio.gather`
   over mDNS, SSDP, ONVIF, ARP scanner, and (optionally) ping sweep.
   Results aggregate into a set of `(IP, MAC)` candidates.
2. **Phase 2** — enrichment protocols run against the candidate IPs
   from phase 1. HTTP probe checks for AXIS headers + basicdeviceinfo;
   SNMP queries sysDescr + sysName.
3. **Merge** — all per-protocol observations fuse by MAC (ADR-0016).

Each protocol is independently togglable via the
`discover_network_devices` MCP tool's per-protocol booleans or the
CLI's `--no-*` flags. Failure of one protocol doesn't abort the others
(`DiscoveryProtocolBase.safe_discover()` wraps every attempt in
try/except + timeout).

## Consequences

**Positive:**
- Phase 2 only touches IPs actually responding to phase 1. A /16 with
  20 devices makes 20 enrichment requests, not 65,536.
- On restricted networks where ARP / mDNS / SSDP are blocked, phase 1
  still surfaces something (ping, ONVIF), and phase 2 enriches what
  it found. Discovery degrades gracefully rather than abruptly
  failing.
- Phase 2 protocols (HTTP probe, SNMP) can be slower per-request
  without affecting overall wall time — they're targeted, not blasted.

**Negative:**
- Two-phase code is harder to read than "fan out everything in one
  gather." The orchestrator is ~60 lines; well-commented but not
  trivial.
- A device that responds only to phase-2 enrichment (e.g. a device
  reachable via HTTP but silent on broadcast protocols) is invisible.
  Operators with that case can manually add the device — discovery
  is a convenience, not a hard requirement for device registration.

## References

- [NETWORK_DISCOVERY_RESEARCH.md](../../NETWORK_DISCOVERY_RESEARCH.md) — "Recommended discovery order"
- ADR-0016 — merge by MAC (the fusion key the two phases produce)
- Requirements: [discovery.md](../requirements/discovery.md), [performance.md](../requirements/performance.md)
- Code: `admz/discovery/orchestrator.py`
