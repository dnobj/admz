# ADR-0016: Merge discovery results by MAC address

**Status:** Accepted, in production.
**Date:** Original design 2026-02 (`NETWORK_DISCOVERY_RESEARCH.md`).

## Context

ADMZ runs seven discovery protocols in parallel (mDNS, SSDP, ONVIF,
ARP, ping, HTTP probe, SNMP). The same device often shows up in
multiple results — mDNS sees a hostname, ONVIF sees a model + serial,
HTTP probe sees firmware version, ARP sees the MAC. The orchestrator
has to fuse these per-protocol observations into one `DiscoveredDevice`
record per real device.

The fusion key must be **unique per physical device** and **observable
by enough protocols** to actually merge anything.

## Decision

Merge results by **MAC address**. When a device's MAC isn't yet known
(e.g. mDNS reported a hostname before ARP picked up the IP→MAC
binding), use IP as a fallback merge key.

The orchestrator collects results from all protocols, groups by MAC
(or IP fallback), and unifies the per-protocol fields into a single
`DiscoveredDevice` instance via `DiscoveredDevice.merge()`. The merge
is field-by-field: each field takes the first non-empty value seen.

The two-phase ordering (ADR-0017) ensures broadcast protocols (mDNS,
ARP, SSDP, ONVIF) run before enrichment (HTTP probe, SNMP), so MACs
are typically known by the time enrichment runs against IPs.

## Consequences

**Positive:**
- MAC is universal: every IP device has one, every protocol that
  reports any per-device metadata also has access to it (directly
  via ARP / SSDP / mDNS / ONVIF, or indirectly via the IP-to-MAC
  table after phase 1).
- Stable identity across discovery runs — the same physical device
  produces the same merged record run after run, even if its IP
  changes (DHCP renewal, port move).
- The merged record's `is_axis` field is True if **any** signal
  said so — MAC OUI match, mDNS service announcement, HTTP probe
  AXIS header, etc.

**Negative:**
- IP-only fallback merges two devices with the same IP, which can
  happen briefly across NAT or after a DHCP collision. Rare in
  practice on a LAN segment; the merged record might transiently
  carry one device's hostname with another's model. The next run
  catches up.
- Devices with multiple NICs (some AXIS Camera Stations) appear
  twice — once per MAC. The operator chooses one to register.

## References

- [NETWORK_DISCOVERY_RESEARCH.md](../../NETWORK_DISCOVERY_RESEARCH.md)
- ADR-0017 — two-phase discovery (the ordering that makes MAC merging work)
- Requirements: [discovery.md](../requirements/discovery.md)
- Code: `admz/discovery/orchestrator.py`, `admz/discovery/models.py::DiscoveredDevice.merge`
