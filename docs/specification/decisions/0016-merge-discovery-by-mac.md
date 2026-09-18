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

## Amendment 2026-09-17 — a record without a MAC joins its device

The IP fallback above was implemented as a separate key, not as a way to join a device's MAC record. SSDP reports a serial number and a model but never a MAC, so every Axis device SSDP answered for was listed twice. The mDNS/ARP record sat under the MAC and the SSDP record under the IP, both with the same device id. The console's discovery widget made it visible: 10 of 29 rows in the owner's first scan were duplicates.

`_merge_all` now does what this record decided:

- **Records with a MAC go first.** Every record that has a MAC is merged before any record that lacks one, whatever the protocol order. The key is the canonical 12-hex MAC, so `aa:bb:…` and `AA-BB-…` are one device.
- **A record without a MAC then joins its device.** It joins the record whose MAC is its serial number, because an Axis serial *is* the MAC. Failing that, it joins the one MAC record at its IP.
- **Otherwise it keeps its own IP key, as before.** That happens when two MAC records hold the IP, which is ambiguous, or when the two records disagree about identity: an Axis serial naming a different MAC, or two different serial numbers.
- **An Axis claim joined only by IP does not override another vendor's MAC.** The "any signal says Axis" rule in *Consequences* still holds for records that share a MAC or whose serial is the MAC. A claim that arrives only through an IP join has no Axis identity behind it, so it does not make a non-Axis MAC an Axis device, nor lend it an Axis manufacturer or device type. The case that forced this was the PC running ADMZ. It answered SSDP with a SERVER header naming Axis software, and would otherwise have been offered as an Axis device to add.

The accepted negative above is unchanged, and still bounded. A record without a MAC can now be merged, by IP, into a *different* device's MAC record only when that IP had just one MAC holder during the scan. Conflicting identities are never merged.

## References

- [NETWORK_DISCOVERY_RESEARCH.md](../../NETWORK_DISCOVERY_RESEARCH.md)
- ADR-0017 — two-phase discovery (the ordering that makes MAC merging work)
- Requirements: [discovery.md](../requirements/discovery.md)
- Code: `admz/discovery/orchestrator.py`, `admz/discovery/models.py::DiscoveredDevice.merge`
