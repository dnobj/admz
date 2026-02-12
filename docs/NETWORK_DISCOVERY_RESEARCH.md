# Network Discovery Research — ADMZ

## Current State Assessment

ADMZ v2.0.0 is a credential management system for Axis devices backed by
HashiCorp Vault. **It has no network discovery capabilities today.** Devices
must be manually registered via the REST API, MCP tools, or the web UI.

### What We Already Have

| Capability | Status | Implementation |
|---|---|---|
| Secrets management | **Working** | HashiCorp Vault KV v2 via `hvac` (`admz/backends/vault_backend.py`) |
| Device registry (IP, MAC, serial, model, tags, location) | **Working** | `DeviceRegistry` ABC + `VaultDeviceRegistry` |
| MCP server interface | **Working** | 10 tools in `admz/mcp/server.py` (list, get, search, CRUD) |
| REST API | **Working** | FastAPI in `admz/api/` with OpenAPI docs |
| Web UI | **Working** | Jinja2 templates for browsing devices |
| Network discovery | **Missing** | No protocol implementations |
| Device configuration cache | **Missing** | No local cache of VAPIX config |
| VAPIX execution | **Missing** | No VAPIX client |

### Architecture Reminder

```
┌─────────────────────────────────────────────────────┐
│  MCP Client  (Claude Code, custom agent, etc.)      │
└──────────────┬──────────────────────────────────────┘
               │ MCP protocol (stdio / SSE)
┌──────────────▼──────────────────────────────────────┐
│  ADMZ MCP Server                                     │
│  ┌────────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Device Reg │ │ Discovery│ │ VAPIX Executor    │  │
│  │ (Vault)    │ │ (NEW)    │ │ (future)          │  │
│  └────────────┘ └──────────┘ └───────────────────┘  │
└──────────────────────────────────────────────────────┘
```

---

## Network Discovery Protocols — Comprehensive Review

### Layer 2 — Link Layer

| Protocol | Standard | Scope | How It Works | Axis Support |
|---|---|---|---|---|
| **ARP** | RFC 826 | Local subnet | Broadcast "who has IP X?" — owner replies with MAC. ARP table scanning reveals all active hosts. | All IP devices respond to ARP |
| **LLDP** | IEEE 802.1AB | Direct link (one hop) | Devices periodically broadcast TLVs (type-length-value) with identity, port, VLAN, capabilities. Vendor-neutral. | Axis cameras support LLDP |
| **CDP** | Cisco proprietary | Direct link (one hop) | Similar to LLDP but Cisco-only. Uses multicast `01:00:0C:CC:CC:CC`. | Not applicable (Cisco infrastructure only) |

### Layer 3 — Network Layer

| Protocol | Standard | Scope | How It Works | Axis Support |
|---|---|---|---|---|
| **ICMP Ping Sweep** | RFC 792 | Any routable subnet | Send ICMP Echo Request to a range; live hosts reply. Simple but noisy; no service identification. | All IP devices (unless ICMP blocked) |
| **ARP Scan** | — | Local subnet | Send ARP requests for every IP in a /24; responses map IP→MAC. More reliable than ping (can't be firewalled on local subnet). | All IP devices |

### Layer 7 — Application Layer (Zero-Config / Consumer)

| Protocol | Standard | Port/Address | How It Works | Axis Support |
|---|---|---|---|---|
| **mDNS / Bonjour** | RFC 6762 | UDP 5353 / `224.0.0.251` | Devices announce `hostname.local` via multicast DNS. Combined with DNS-SD (RFC 6763) for service discovery. Apple Bonjour, Linux Avahi, Windows 10+. | **Yes** — Axis cameras announce via Bonjour/Zeroconf |
| **DNS-SD** | RFC 6763 | (over mDNS) | Two-step: PTR query finds service instances, SRV+TXT queries resolve host/port/metadata. | **Yes** — Axis devices register `_axis-video._tcp.local` services |
| **SSDP / UPnP** | UPnP Forum | UDP 1900 / `239.255.255.250` | M-SEARCH multicast discovers devices; devices respond with location URL pointing to XML device description. | **Yes** — Axis cameras respond to UPnP/SSDP |
| **WS-Discovery** | OASIS / ONVIF | UDP 3702 / `239.255.255.250` | SOAP-over-UDP multicast Probe; devices respond with endpoint references. Foundation of ONVIF discovery. | **Yes** — All ONVIF-compliant Axis cameras |
| **LLMNR** | RFC 4795 | UDP 5355 / `224.0.0.252` | Windows link-local name resolution. Deprecated in favor of mDNS in Windows 10+. | Not directly relevant |
| **NetBIOS** | RFC 1001/1002 | UDP 137-139 | Legacy Windows name resolution. Being phased out. | Not directly relevant |

### Layer 7 — Application Layer (Enterprise / Management)

| Protocol | Standard | Scope | How It Works | Axis Support |
|---|---|---|---|---|
| **SNMP** | RFC 3411-3418 | Any routable | Poll devices via UDP 161; agents respond with MIB data (model, serial, firmware, interfaces). SNMPv3 adds auth+encryption. | **Yes** — Axis cameras have SNMP agents |
| **ONVIF** | ONVIF Profiles S/G/T | Via WS-Discovery + HTTP | WS-Discovery finds devices; then SOAP calls to `/onvif/device_service` retrieve capabilities, profiles, and configuration. | **Yes** — Axis co-founded ONVIF. Profile S/T/G support. |
| **VAPIX** | Axis proprietary | HTTP/HTTPS | Axis's own REST-like API. Device identification possible via HTTP response header `AXIS-Setup:vapix`. Full device info via `/axis-cgi/basicdeviceinfo.cgi`. | **Yes** — All Axis devices |

---

## Axis-Specific Discovery Path

Axis cameras support a rich set of discovery mechanisms. The recommended
discovery order (most reliable to most speculative):

### 1. ONVIF / WS-Discovery (Primary — Camera-Specific)
- Sends a WS-Discovery Probe for `tdn:NetworkVideoTransmitter`
- Returns ONVIF XAddrs (service endpoints) for each camera
- Can then query `GetDeviceInformation` for model, serial, firmware
- **Library**: `WSDiscovery` (PyPI) + `onvif-python` or `python-onvif-zeep`

### 2. mDNS / Zeroconf / Bonjour (Primary — Zero-Config)
- Browse for `_axis-video._tcp.local.` services
- Returns hostname, IP, port, and TXT records with metadata
- Also catches non-ONVIF Axis devices (encoders, I/O modules, speakers)
- **Library**: `zeroconf` (PyPI, v0.148+, pure Python, asyncio)

### 3. SSDP / UPnP (Primary — Consumer Protocol)
- M-SEARCH for `ssdp:all` or `urn:axis-com:service:BasicService:1`
- Parse response headers for LOCATION URL → fetch XML device description
- Returns model, serial, friendly name, manufacturer
- **Library**: `async-upnp-client` (PyPI, asyncio) or raw socket

### 4. ARP Scan (Secondary — Subnet Sweep)
- ARP scan the local subnet to find all live MAC addresses
- Filter by Axis OUI prefixes: `00:40:8C`, `AC:CC:8E`, `B8:A4:4F`, etc.
- Provides IP + MAC mapping; no service info
- **Library**: `scapy` (requires root/raw socket privileges)

### 5. ICMP Ping Sweep (Secondary — Host Liveness)
- Ping all IPs in a subnet range
- Responders are live hosts but identity unknown
- Follow up with HTTP probe on port 80/443 for VAPIX header
- **Library**: `pythonping` or `subprocess` with system `ping`

### 6. VAPIX HTTP Probe (Tertiary — Axis Identification)
- For discovered IPs, HTTP GET to port 80
- Check response header for `Server: Boa/...` or axis identifiers
- Hit `/axis-cgi/basicdeviceinfo.cgi` for full device info (requires auth)
- Factory-default devices respond with `AXIS-Setup:vapix` header
- **Library**: `httpx` or `aiohttp`

### 7. SNMP Query (Tertiary — Enterprise Enrichment)
- Query `sysDescr.0` (OID 1.3.6.1.2.1.1.1.0) for device description
- Query `sysName.0` for hostname
- Axis-specific MIBs available for detailed info
- **Library**: `pysnmp` or `easysnmp`

---

## Recommended Python Libraries

| Library | Protocol | PyPI | Python | Async | Notes |
|---|---|---|---|---|---|
| `zeroconf` | mDNS/DNS-SD | `zeroconf>=0.148.0` | 3.11+ | Yes | Pure Python, production-grade, used by Home Assistant |
| `async-upnp-client` | SSDP/UPnP | `async-upnp-client>=0.40.0` | 3.11+ | Yes | Full UPnP stack, used by Home Assistant |
| `WSDiscovery` | WS-Discovery | `WSDiscovery>=2.0.0` | 3.9+ | No | ONVIF device discovery |
| `scapy` | ARP/raw packets | `scapy>=2.5.0` | 3.8+ | Limited | Requires root for ARP; powerful but heavy |
| `httpx` | HTTP probing | `httpx>=0.27.0` | 3.8+ | Yes | Modern HTTP client, connection pooling |
| `pysnmp` | SNMP | `pysnmp>=6.0.0` | 3.8+ | Yes | Pure Python SNMPv1/v2c/v3 |

---

## Discovery Module Architecture

```
admz/discovery/
├── __init__.py              # Public API: discover_devices()
├── models.py                # DiscoveredDevice dataclass, enums
├── base.py                  # Abstract DiscoveryProtocol interface
├── arp_scanner.py           # ARP-based subnet scanning
├── mdns_discovery.py        # mDNS/Zeroconf/Bonjour browser
├── ssdp_discovery.py        # SSDP/UPnP M-SEARCH
├── onvif_discovery.py       # WS-Discovery for ONVIF cameras
├── ping_sweep.py            # ICMP ping sweep
├── http_probe.py            # VAPIX HTTP header probing
├── snmp_query.py            # SNMP sysDescr enrichment
└── orchestrator.py          # Runs all protocols, merges & deduplicates
```

### Core Design Principles

1. **Merge by MAC address** — MAC is the universal device identifier across
   protocols. All discovery results are keyed by MAC and merged.
2. **Async-first** — All protocols run concurrently via `asyncio.gather()`.
3. **Graceful degradation** — Each protocol is optional; missing libraries
   or insufficient privileges (e.g., no root for ARP) are handled gracefully.
4. **Progressive enrichment** — Start with fast protocols (mDNS, SSDP),
   then enrich with slower ones (SNMP, HTTP probe).

---

## Axis OUI (MAC Address Prefixes)

Known Axis Communications MAC prefixes for ARP filtering:

| OUI Prefix | Registered To |
|---|---|
| `00:40:8C` | Axis Communications AB |
| `AC:CC:8E` | Axis Communications AB |
| `B8:A4:4F` | Axis Communications AB |

---

## Security Considerations

- **ARP scanning** requires raw socket privileges (root or `CAP_NET_RAW`)
- **SNMP** community strings should be treated as secrets (store in Vault)
- **ONVIF** disabled by default on Axis firmware >= v5.40
- **Discovery protocols** should be disabled after deployment per Axis hardening guide
- **VAPIX probe** on factory-default devices reveals device info without auth
- All discovered devices should be cross-referenced with the Vault registry

---

## References

- [Axis OS Hardening Guide](https://help.axis.com/en-us/axis-os-hardening-guide)
- [Axis ONVIF Support](https://www.axis.com/onvif)
- [SSDP - Wikipedia](https://en.wikipedia.org/wiki/Simple_Service_Discovery_Protocol)
- [Zero-configuration networking - Wikipedia](https://en.wikipedia.org/wiki/Zero-configuration_networking)
- [mDNS - RFC 6762](https://en.wikipedia.org/wiki/Multicast_DNS)
- [WS-Discovery - WSDiscovery PyPI](https://pypi.org/project/WSDiscovery/)
- [zeroconf PyPI](https://pypi.org/project/zeroconf/)
- [Scapy - Network Scanner](https://thepythoncode.com/article/building-network-scanner-using-scapy)
- [Microsoft Defender Device Discovery](https://learn.microsoft.com/en-us/defender-endpoint/device-discovery-faq)
- [Auvik - Comprehensive Guide to Network Discovery](https://www.auvik.com/franklyit/blog/what-is-network-discovery/)
- [Network Discovery Best Practices - TechTarget](https://www.techtarget.com/searchnetworking/tip/Network-device-discovery-best-practices-other-than-ping-sweeps)
- [Home Assistant Network Discovery](https://developers.home-assistant.io/docs/network_discovery/)
- [onvif-python PyPI](https://pypi.org/project/onvif-python/)
