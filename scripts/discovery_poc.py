#!/usr/bin/env python3
"""
Proof-of-concept: mDNS and SSDP discovery on Windows.

Demonstrates raw-socket approaches that bypass the zeroconf library's
issues with Windows ProactorEventLoop and fix the SSDP non-blocking
socket problem.

Run:
    python scripts/discovery_poc.py
"""

import asyncio
import socket
import struct
import sys
import time
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# DNS wire-format helpers (just enough to build PTR queries and parse answers)
# ---------------------------------------------------------------------------

def _build_dns_query(name: str, qtype: int = 12) -> bytes:
    """Build a minimal DNS query packet.

    Args:
        name: DNS name like '_axis-video._tcp.local.'
        qtype: 12 = PTR, 255 = ANY
    """
    # Header: ID=0, flags=0 (standard query), QDCOUNT=1
    header = struct.pack("!HHHHHH", 0x0000, 0x0000, 1, 0, 0, 0)
    # Question section
    qname = b""
    for label in name.rstrip(".").split("."):
        qname += bytes([len(label)]) + label.encode("ascii")
    qname += b"\x00"
    question = qname + struct.pack("!HH", qtype, 1)  # class IN
    return header + question


def _parse_dns_name(data: bytes, offset: int) -> Tuple[str, int]:
    """Parse a DNS name from *data* starting at *offset*, handling compression."""
    labels = []
    jumped = False
    original_offset = offset
    max_jumps = 20
    jumps = 0

    while True:
        if offset >= len(data):
            break
        length = data[offset]
        if (length & 0xC0) == 0xC0:
            # Pointer
            if not jumped:
                original_offset = offset + 2
            pointer = struct.unpack("!H", data[offset:offset + 2])[0] & 0x3FFF
            offset = pointer
            jumped = True
            jumps += 1
            if jumps > max_jumps:
                break
        elif length == 0:
            offset += 1
            break
        else:
            offset += 1
            labels.append(data[offset:offset + length].decode("ascii", errors="replace"))
            offset += length

    name = ".".join(labels)
    return name, (original_offset if jumped else offset)


def _parse_dns_txt(data: bytes, rdlength: int, rdata_offset: int) -> Dict[str, str]:
    """Parse DNS TXT record data into key=value pairs."""
    props: Dict[str, str] = {}
    pos = rdata_offset
    end = rdata_offset + rdlength
    while pos < end:
        txt_len = data[pos]
        pos += 1
        if txt_len == 0:
            continue
        txt = data[pos:pos + txt_len].decode("utf-8", errors="replace")
        pos += txt_len
        if "=" in txt:
            k, _, v = txt.partition("=")
            props[k.lower()] = v
    return props


def _parse_mdns_response(data: bytes) -> List[dict]:
    """Parse an mDNS response packet, extracting all resource records."""
    if len(data) < 12:
        return []

    _id, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", data[:12])
    offset = 12

    # Skip questions
    for _ in range(qdcount):
        _name, offset = _parse_dns_name(data, offset)
        offset += 4  # skip QTYPE + QCLASS

    records = []
    total_rr = ancount + nscount + arcount
    for _ in range(total_rr):
        if offset >= len(data):
            break
        name, offset = _parse_dns_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        rdata_offset = offset

        rec = {
            "name": name,
            "type": rtype,
            "class": rclass & 0x7FFF,  # mask cache-flush bit
            "ttl": ttl,
            "rdlength": rdlength,
        }

        if rtype == 1:  # A record
            if rdlength == 4:
                rec["address"] = socket.inet_ntoa(data[rdata_offset:rdata_offset + 4])
        elif rtype == 12:  # PTR
            ptr_name, _ = _parse_dns_name(data, rdata_offset)
            rec["target"] = ptr_name
        elif rtype == 16:  # TXT
            rec["txt"] = _parse_dns_txt(data, rdlength, rdata_offset)
        elif rtype == 33:  # SRV
            if rdlength >= 6:
                priority, weight, port = struct.unpack("!HHH", data[rdata_offset:rdata_offset + 6])
                target, _ = _parse_dns_name(data, rdata_offset + 6)
                rec["priority"] = priority
                rec["weight"] = weight
                rec["port"] = port
                rec["target"] = target
        elif rtype == 28:  # AAAA
            pass  # skip IPv6

        offset = rdata_offset + rdlength
        records.append(rec)

    return records


def _normalise_mac(mac: str) -> str:
    """Normalise a MAC address to AA:BB:CC:DD:EE:FF format."""
    clean = mac.upper().replace("-", ":").replace(".", "")
    if ":" not in clean and len(clean) == 12:
        clean = ":".join(clean[i:i + 2] for i in range(0, 12, 2))
    return clean


# ---------------------------------------------------------------------------
# mDNS raw-socket discovery
# ---------------------------------------------------------------------------

async def discover_mdns(
    local_ip: str,
    service_types: Optional[List[str]] = None,
    timeout: float = 5.0,
) -> List[dict]:
    """Discover devices via raw mDNS multicast queries.

    Works on Windows with ProactorEventLoop by running blocking socket
    I/O in a thread pool executor.
    """
    if service_types is None:
        service_types = ["_axis-video._tcp.local."]

    MDNS_ADDR = "224.0.0.251"
    MDNS_PORT = 5353

    # Create UDP socket bound to the specific local interface
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((local_ip, MDNS_PORT))

    # Join multicast group on the specific interface
    mreq = struct.pack(
        "4s4s",
        socket.inet_aton(MDNS_ADDR),
        socket.inet_aton(local_ip),
    )
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    # Use a blocking timeout for the recv thread
    sock.settimeout(0.5)

    loop = asyncio.get_event_loop()

    # Send PTR queries for each service type
    for stype in service_types:
        query = _build_dns_query(stype, qtype=12)
        try:
            sock.sendto(query, (MDNS_ADDR, MDNS_PORT))
        except OSError as exc:
            print(f"  [mDNS] sendto failed for {stype}: {exc}")

    # Collect responses in a thread (blocking recv with short timeout)
    all_records: List[Tuple[str, list]] = []
    stop_time = time.monotonic() + timeout

    def _recv_loop():
        """Blocking recv loop running in executor thread."""
        results = []
        while time.monotonic() < stop_time:
            try:
                data, addr = sock.recvfrom(8192)
                records = _parse_mdns_response(data)
                if records:
                    results.append((addr[0], records))
            except socket.timeout:
                continue
            except OSError:
                continue
        return results

    all_records = await loop.run_in_executor(None, _recv_loop)

    # Leave multicast group and close
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
    except OSError:
        pass
    sock.close()

    # Aggregate: collect PTR targets, then match SRV/TXT/A records
    devices: Dict[str, dict] = {}  # keyed by service instance name

    # First pass: gather all records from all responses
    flat_records: List[dict] = []
    for _src_ip, records in all_records:
        flat_records.extend(records)

    # Find PTR records (service instance announcements)
    instance_names = set()
    for rec in flat_records:
        if rec["type"] == 12 and "target" in rec:
            instance_names.add(rec["target"])

    # Build a lookup by record name
    records_by_name: Dict[str, List[dict]] = {}
    for rec in flat_records:
        records_by_name.setdefault(rec["name"], []).append(rec)

    # For each service instance, gather SRV, TXT, A records
    for inst in instance_names:
        dev: dict = {"instance": inst, "ip": None, "mac": None, "model": None,
                     "serial": None, "hostname": None, "txt": {}}

        # SRV record -> hostname + port
        for rec in records_by_name.get(inst, []):
            if rec["type"] == 33:  # SRV
                dev["hostname"] = rec.get("target", "").rstrip(".")
                dev["port"] = rec.get("port")
            elif rec["type"] == 16:  # TXT
                dev["txt"].update(rec.get("txt", {}))

        # A record for the hostname -> IP
        hostname_dotted = dev["hostname"] + "." if dev["hostname"] else ""
        hostname_plain = dev["hostname"] or ""
        for hname in [hostname_dotted, hostname_plain]:
            for rec in records_by_name.get(hname, []):
                if rec["type"] == 1 and "address" in rec:
                    dev["ip"] = rec["address"]
                    break
            if dev["ip"]:
                break

        # Also look for A records from the source IPs
        if not dev["ip"]:
            for rec in flat_records:
                if rec["type"] == 1 and "address" in rec:
                    # Check if the name matches our hostname
                    if hostname_plain and rec["name"].rstrip(".").lower() == hostname_plain.lower():
                        dev["ip"] = rec["address"]
                        break

        # Extract metadata from TXT
        txt = dev["txt"]
        dev["mac"] = txt.get("macaddress") or txt.get("mac")
        if dev["mac"]:
            dev["mac"] = _normalise_mac(dev["mac"])
        dev["model"] = txt.get("model")
        dev["serial"] = txt.get("serialnumber") or txt.get("serial")

        key = dev["mac"] or dev["ip"] or inst
        if key not in devices:
            devices[key] = dev
        else:
            # Merge
            existing = devices[key]
            for k, v in dev.items():
                if v and not existing.get(k):
                    existing[k] = v

    return list(devices.values())


# ---------------------------------------------------------------------------
# SSDP discovery (fixed socket handling)
# ---------------------------------------------------------------------------

SSDP_MULTICAST = "239.255.255.250"
SSDP_PORT = 1900

M_SEARCH_TEMPLATE = (
    "M-SEARCH * HTTP/1.1\r\n"
    "HOST: 239.255.255.250:1900\r\n"
    'MAN: "ssdp:discover"\r\n'
    "MX: {mx}\r\n"
    "ST: {st}\r\n"
    "\r\n"
)


def _parse_ssdp_response(data: str) -> Optional[Dict[str, str]]:
    """Parse an SSDP HTTP-like response into a header dict."""
    headers: Dict[str, str] = {}
    for line in data.split("\r\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().upper()] = value.strip()
    return headers if headers else None


async def discover_ssdp(
    local_ip: str,
    search_targets: Optional[List[str]] = None,
    timeout: float = 5.0,
) -> List[dict]:
    """Discover devices via SSDP M-SEARCH.

    Uses a blocking socket with a short timeout in a thread executor,
    which reliably receives responses on Windows (unlike the non-blocking
    sock.settimeout(0) approach).
    """
    if search_targets is None:
        search_targets = ["ssdp:all"]

    # Create the socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Bind to the local interface so responses come back here
    sock.bind((local_ip, 0))

    # Set a short blocking timeout (NOT 0 / non-blocking)
    sock.settimeout(0.5)

    loop = asyncio.get_event_loop()

    # Send M-SEARCH for each target
    mx = max(1, int(timeout) - 1)
    for st in search_targets:
        msg = M_SEARCH_TEMPLATE.format(mx=mx, st=st).encode()
        try:
            sock.sendto(msg, (SSDP_MULTICAST, SSDP_PORT))
        except OSError as exc:
            print(f"  [SSDP] sendto failed for {st}: {exc}")

    # Collect responses in a thread with blocking recv + short timeout
    stop_time = time.monotonic() + timeout

    def _recv_loop():
        results = []
        while time.monotonic() < stop_time:
            try:
                data, addr = sock.recvfrom(4096)
                text = data.decode(errors="replace")
                headers = _parse_ssdp_response(text)
                if headers:
                    results.append((addr[0], headers))
            except socket.timeout:
                continue
            except OSError:
                continue
        return results

    responses = await loop.run_in_executor(None, _recv_loop)
    sock.close()

    # Deduplicate by IP
    devices: Dict[str, dict] = {}
    for ip, headers in responses:
        if ip not in devices:
            devices[ip] = {
                "ip": ip,
                "location": headers.get("LOCATION"),
                "server": headers.get("SERVER"),
                "usn": headers.get("USN"),
                "st": headers.get("ST"),
                "is_axis": False,
            }
        else:
            dev = devices[ip]
            dev["location"] = dev["location"] or headers.get("LOCATION")
            dev["server"] = dev["server"] or headers.get("SERVER")
            dev["usn"] = dev["usn"] or headers.get("USN")

        # Check for Axis
        server = (headers.get("SERVER") or "").lower()
        if "axis" in server:
            devices[ip]["is_axis"] = True

    return list(devices.values())


# ---------------------------------------------------------------------------
# Determine local IP
# ---------------------------------------------------------------------------

def get_local_ip() -> str:
    """Get the local IP address used for the default route.

    Connects to a public unicast address (not multicast) because on
    Windows with Hyper-V/WSL, multicast destinations may route through
    the wrong interface.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 53))
        return s.getsockname()[0]
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    local_ip = get_local_ip()
    print(f"Local IP: {local_ip}")
    print("=" * 70)

    # --- mDNS Discovery ---
    print("\n[mDNS] Sending PTR query for _axis-video._tcp.local. ...")
    mdns_devices = await discover_mdns(
        local_ip=local_ip,
        service_types=["_axis-video._tcp.local."],
        timeout=5.0,
    )
    print(f"[mDNS] Found {len(mdns_devices)} device(s):\n")
    for dev in mdns_devices:
        print(f"  IP:       {dev.get('ip', 'N/A')}")
        print(f"  MAC:      {dev.get('mac', 'N/A')}")
        print(f"  Model:    {dev.get('model', 'N/A')}")
        print(f"  Serial:   {dev.get('serial', 'N/A')}")
        print(f"  Hostname: {dev.get('hostname', 'N/A')}")
        print(f"  TXT:      {dev.get('txt', {})}")
        print()

    # --- SSDP Discovery ---
    print("=" * 70)
    print("\n[SSDP] Sending M-SEARCH for ssdp:all ...")
    ssdp_devices = await discover_ssdp(
        local_ip=local_ip,
        search_targets=["ssdp:all"],
        timeout=5.0,
    )
    print(f"[SSDP] Found {len(ssdp_devices)} device(s):\n")
    for dev in ssdp_devices:
        axis_tag = " [AXIS]" if dev.get("is_axis") else ""
        print(f"  IP:       {dev.get('ip', 'N/A')}{axis_tag}")
        print(f"  Server:   {dev.get('server', 'N/A')}")
        print(f"  Location: {dev.get('location', 'N/A')}")
        print(f"  USN:      {dev.get('usn', 'N/A')}")
        print()

    # --- Summary ---
    print("=" * 70)
    print("\nSummary:")
    mdns_ips = {d["ip"] for d in mdns_devices if d.get("ip")}
    ssdp_ips = {d["ip"] for d in ssdp_devices if d.get("ip")}
    all_ips = mdns_ips | ssdp_ips
    print(f"  mDNS found: {len(mdns_devices)} devices (IPs: {sorted(mdns_ips)})")
    print(f"  SSDP found: {len(ssdp_devices)} devices (IPs: {sorted(ssdp_ips)})")
    print(f"  Total unique IPs: {len(all_ips)}")
    both = mdns_ips & ssdp_ips
    if both:
        print(f"  Found by BOTH protocols: {sorted(both)}")


if __name__ == "__main__":
    asyncio.run(main())
