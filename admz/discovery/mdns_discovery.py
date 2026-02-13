"""
mDNS / Zeroconf / Bonjour device discovery.

Browses for Axis-specific service types on the local network:
  - _axis-video._tcp.local.
  - _http._tcp.local.

On non-Windows platforms, uses the ``zeroconf`` library (``AsyncServiceBrowser``).
On Windows, uses a raw-socket mDNS implementation because the default
``ProactorEventLoop`` prevents ``zeroconf`` from receiving UDP multicast
datagrams reliably.  The raw-socket approach sends DNS PTR queries to the
mDNS multicast group (224.0.0.251:5353) and parses the response packets
directly.

Requires (non-Windows only): pip install zeroconf
"""

import asyncio
import logging
import socket
import struct
import sys
import time
from typing import Dict, List, Optional, Tuple

from admz.discovery.base import DiscoveryProtocolBase
from admz.discovery.models import (
    DiscoveredDevice,
    DiscoveryProtocol,
    DeviceType,
    is_axis_mac,
)

logger = logging.getLogger(__name__)

# Service types to browse.  The first is Axis-specific; the second is
# generic HTTP which sometimes catches Axis devices too.
AXIS_SERVICE_TYPES = [
    "_axis-video._tcp.local.",
]

GENERAL_SERVICE_TYPES = [
    "_http._tcp.local.",
]

MDNS_MULTICAST_ADDR = "224.0.0.251"
MDNS_PORT = 5353


# ---------------------------------------------------------------------------
# DNS wire-format helpers
# ---------------------------------------------------------------------------

def _build_dns_query(name: str, qtype: int = 12) -> bytes:
    """Build a minimal DNS query packet.

    Args:
        name: DNS name like ``_axis-video._tcp.local.``
        qtype: 12 = PTR, 255 = ANY
    """
    # Header: ID=0, flags=0 (standard query), QDCOUNT=1
    header = struct.pack("!HHHHHH", 0x0000, 0x0000, 1, 0, 0, 0)
    qname = b""
    for label in name.rstrip(".").split("."):
        qname += bytes([len(label)]) + label.encode("ascii")
    qname += b"\x00"
    question = qname + struct.pack("!HH", qtype, 1)  # class IN
    return header + question


def _parse_dns_name(data: bytes, offset: int) -> Tuple[str, int]:
    """Parse a DNS name from *data* starting at *offset*, handling compression."""
    labels: List[str] = []
    jumped = False
    original_offset = offset
    max_jumps = 20
    jumps = 0

    while True:
        if offset >= len(data):
            break
        length = data[offset]
        if (length & 0xC0) == 0xC0:
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
        if pos >= len(data):
            break
        txt_len = data[pos]
        pos += 1
        if txt_len == 0:
            continue
        if pos + txt_len > len(data):
            break
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

    _id, flags, qdcount, ancount, nscount, arcount = struct.unpack(
        "!HHHHHH", data[:12]
    )
    offset = 12

    # Skip question section
    for _ in range(qdcount):
        if offset >= len(data):
            break
        _name, offset = _parse_dns_name(data, offset)
        offset += 4  # QTYPE + QCLASS

    records: List[dict] = []
    total_rr = ancount + nscount + arcount
    for _ in range(total_rr):
        if offset >= len(data):
            break
        name, offset = _parse_dns_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype, rclass, ttl, rdlength = struct.unpack(
            "!HHIH", data[offset:offset + 10]
        )
        offset += 10
        rdata_offset = offset

        rec: dict = {
            "name": name,
            "type": rtype,
            "class": rclass & 0x7FFF,
            "ttl": ttl,
            "rdlength": rdlength,
        }

        if rtype == 1 and rdlength == 4:  # A record
            rec["address"] = socket.inet_ntoa(data[rdata_offset:rdata_offset + 4])
        elif rtype == 12:  # PTR
            ptr_name, _ = _parse_dns_name(data, rdata_offset)
            rec["target"] = ptr_name
        elif rtype == 16:  # TXT
            rec["txt"] = _parse_dns_txt(data, rdlength, rdata_offset)
        elif rtype == 33 and rdlength >= 6:  # SRV
            priority, weight, port = struct.unpack(
                "!HHH", data[rdata_offset:rdata_offset + 6]
            )
            target, _ = _parse_dns_name(data, rdata_offset + 6)
            rec["priority"] = priority
            rec["weight"] = weight
            rec["port"] = port
            rec["target"] = target

        offset = rdata_offset + rdlength
        records.append(rec)

    return records


def _get_local_ip() -> str:
    """Return the local IP used for the default route.

    We connect to a public unicast address (not a multicast address)
    because on Windows with Hyper-V/WSL virtual NICs, connecting to a
    multicast address may route through the wrong interface.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # UDP connect does not send packets; it just determines the
        # outgoing interface via the routing table.
        s.connect(("8.8.8.8", 53))
        return s.getsockname()[0]
    except OSError:
        return "0.0.0.0"
    finally:
        s.close()


# ---------------------------------------------------------------------------
# MDNSDiscovery class
# ---------------------------------------------------------------------------

class MDNSDiscovery(DiscoveryProtocolBase):
    """Discover devices via mDNS/Zeroconf multicast."""

    @property
    def name(self) -> str:
        return "mDNS/Zeroconf"

    async def discover(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        # On Windows, always use the raw-socket approach because the
        # default ProactorEventLoop silently breaks zeroconf's UDP multicast.
        if sys.platform == "win32":
            return await self._discover_raw(timeout)

        # Non-Windows: try zeroconf first, fall back to raw sockets.
        try:
            return await self._discover_zeroconf(timeout)
        except Exception:
            logger.warning(
                "zeroconf-based mDNS discovery failed; falling back to raw sockets",
                exc_info=True,
            )
            return await self._discover_raw(timeout)

    # ------------------------------------------------------------------
    # Raw-socket mDNS (Windows-safe, no external dependencies)
    # ------------------------------------------------------------------

    async def _discover_raw(self, timeout: float) -> List[DiscoveredDevice]:
        """mDNS discovery using raw UDP sockets.

        Works with the Windows ProactorEventLoop because all blocking I/O
        runs inside ``loop.run_in_executor``.
        """
        local_ip = _get_local_ip()
        logger.debug("Raw mDNS discovery on %s", local_ip)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((local_ip, MDNS_PORT))

        # Join the mDNS multicast group on the local interface
        mreq = struct.pack(
            "4s4s",
            socket.inet_aton(MDNS_MULTICAST_ADDR),
            socket.inet_aton(local_ip),
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(0.5)

        loop = asyncio.get_event_loop()

        # Send PTR queries for all service types
        all_types = AXIS_SERVICE_TYPES + GENERAL_SERVICE_TYPES
        for stype in all_types:
            query = _build_dns_query(stype, qtype=12)
            try:
                sock.sendto(query, (MDNS_MULTICAST_ADDR, MDNS_PORT))
            except OSError as exc:
                logger.debug("mDNS sendto failed for %s: %s", stype, exc)

        # Collect responses in a blocking thread
        stop_time = time.monotonic() + timeout

        def _recv_loop() -> List[Tuple[str, list]]:
            results: List[Tuple[str, list]] = []
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

        all_responses = await loop.run_in_executor(None, _recv_loop)

        # Cleanup
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
        except OSError:
            pass
        sock.close()

        # Assemble DiscoveredDevice objects
        return self._build_devices_from_records(all_responses, local_ip)

    def _build_devices_from_records(
        self,
        all_responses: List[Tuple[str, list]],
        local_ip: str,
    ) -> List[DiscoveredDevice]:
        """Parse raw mDNS records into DiscoveredDevice instances."""
        # Flatten all records
        flat_records: List[dict] = []
        for _src_ip, records in all_responses:
            flat_records.extend(records)

        # Collect PTR targets (service instance names)
        instance_names: set = set()
        for rec in flat_records:
            if rec["type"] == 12 and "target" in rec:
                instance_names.add(rec["target"])

        # Build lookup by record name
        records_by_name: Dict[str, List[dict]] = {}
        for rec in flat_records:
            records_by_name.setdefault(rec["name"], []).append(rec)

        devices: Dict[str, DiscoveredDevice] = {}

        for inst in instance_names:
            ip: Optional[str] = None
            mac: Optional[str] = None
            hostname: Optional[str] = None
            txt_props: Dict[str, str] = {}
            service_type = ""

            # Determine the service type from the PTR record name
            for rec in flat_records:
                if rec["type"] == 12 and rec.get("target") == inst:
                    service_type = rec["name"]
                    break

            # Gather SRV and TXT records for this instance
            for rec in records_by_name.get(inst, []):
                if rec["type"] == 33:  # SRV
                    hostname = rec.get("target", "").rstrip(".")
                elif rec["type"] == 16:  # TXT
                    txt_props.update(rec.get("txt", {}))

            # Resolve hostname -> IP via A records
            if hostname:
                for hname in [hostname + ".", hostname]:
                    for rec in records_by_name.get(hname, []):
                        if rec["type"] == 1 and "address" in rec:
                            ip = rec["address"]
                            break
                    if ip:
                        break

            # Skip entries with no IP or matching the local machine
            if not ip or ip == local_ip:
                continue

            # Extract MAC from TXT
            raw_mac = txt_props.get("macaddress") or txt_props.get("mac")
            if raw_mac:
                mac = _normalise_mac(raw_mac)

            key = mac or ip
            dev = devices.get(key)
            if dev is None:
                dev = DiscoveredDevice(ip_address=ip, mac_address=mac)
                devices[key] = dev

            dev.ip_address = dev.ip_address or ip
            dev.mac_address = dev.mac_address or mac
            dev.mdns_name = (hostname or "") + "." if hostname else None
            dev.hostname = hostname or None

            if service_type and service_type not in dev.mdns_services:
                dev.mdns_services.append(service_type)
            if DiscoveryProtocol.MDNS not in dev.discovered_by:
                dev.discovered_by.append(DiscoveryProtocol.MDNS)

            # Populate metadata from TXT records
            dev.model = dev.model or txt_props.get("model")
            dev.serial_number = dev.serial_number or txt_props.get("serialnumber")
            dev.firmware_version = dev.firmware_version or txt_props.get("firmware")
            dev.friendly_name = (
                dev.friendly_name
                or txt_props.get("friendlyname")
                or inst.split(".")[0]
            )

            # Detect Axis
            if mac and is_axis_mac(mac):
                dev.is_axis = True
                dev.manufacturer = "Axis Communications"
            if "_axis-video" in service_type:
                dev.is_axis = True
                dev.manufacturer = "Axis Communications"
                if dev.device_type == DeviceType.UNKNOWN:
                    dev.device_type = DeviceType.CAMERA

        # Merge entries that share the same IP but were keyed differently
        # (e.g. one keyed by MAC from _axis-video, another by IP from _http).
        merged: Dict[str, DiscoveredDevice] = {}
        for dev in devices.values():
            ip = dev.ip_address
            if not ip:
                merged[dev.mac_address or id(dev)] = dev
                continue

            # Check if any existing merged entry already has this IP
            found = False
            for existing in merged.values():
                if existing.ip_address == ip:
                    existing.merge(dev)
                    found = True
                    break
            if not found:
                merged[dev.mac_address or ip] = dev

        return list(merged.values())

    # ------------------------------------------------------------------
    # Zeroconf-based mDNS (non-Windows)
    # ------------------------------------------------------------------

    async def _discover_zeroconf(self, timeout: float) -> List[DiscoveredDevice]:
        """mDNS discovery using the ``zeroconf`` library."""
        try:
            from zeroconf import IPVersion, ServiceStateChange, Zeroconf
            from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf
        except ImportError:
            logger.warning(
                "zeroconf library not installed -- falling back to raw sockets. "
                "Install with: pip install zeroconf"
            )
            return await self._discover_raw(timeout)

        devices: Dict[str, DiscoveredDevice] = {}

        class _Listener:
            def __init__(self, azc: AsyncZeroconf):
                self.azc = azc

            def _handle(
                self,
                zeroconf: Zeroconf = None,
                service_type: str = "",
                name: str = "",
                state_change: ServiceStateChange = None,
                **kwargs,
            ) -> None:
                if state_change != ServiceStateChange.Added:
                    return
                asyncio.ensure_future(self._resolve(zeroconf, service_type, name))

            async def _resolve(
                self, zc: Zeroconf, service_type: str, name: str
            ) -> None:
                info = await self.azc.async_get_service_info(service_type, name)
                if info is None:
                    return

                addresses = info.parsed_addresses(IPVersion.V4Only)
                if not addresses:
                    return

                ip = addresses[0]
                mac: Optional[str] = None

                # Extract props from TXT records
                props = {
                    k.decode() if isinstance(k, bytes) else k: (
                        v.decode() if isinstance(v, bytes) else v
                    )
                    for k, v in (info.properties or {}).items()
                }
                mac = props.get("macaddress") or props.get("mac")
                if mac:
                    mac = _normalise_mac(mac)

                key = mac or ip
                dev = devices.get(key)
                if dev is None:
                    dev = DiscoveredDevice(ip_address=ip, mac_address=mac)
                    devices[key] = dev

                dev.ip_address = dev.ip_address or ip
                dev.mac_address = dev.mac_address or mac
                dev.mdns_name = info.server
                dev.hostname = (info.server or "").rstrip(".")

                if service_type not in dev.mdns_services:
                    dev.mdns_services.append(service_type)
                if DiscoveryProtocol.MDNS not in dev.discovered_by:
                    dev.discovered_by.append(DiscoveryProtocol.MDNS)

                dev.model = dev.model or props.get("model")
                dev.serial_number = dev.serial_number or props.get("serialnumber")
                dev.firmware_version = dev.firmware_version or props.get("firmware")
                dev.friendly_name = (
                    dev.friendly_name
                    or props.get("friendlyname")
                    or info.name.split(".")[0]
                )

                if mac and is_axis_mac(mac):
                    dev.is_axis = True
                    dev.manufacturer = "Axis Communications"
                if "_axis-video" in service_type:
                    dev.is_axis = True
                    dev.manufacturer = "Axis Communications"
                    if dev.device_type == DeviceType.UNKNOWN:
                        dev.device_type = DeviceType.CAMERA

        azc = AsyncZeroconf(ip_version=IPVersion.V4Only)
        listener = _Listener(azc)

        all_types = AXIS_SERVICE_TYPES + GENERAL_SERVICE_TYPES
        browsers = []
        for stype in all_types:
            browser = AsyncServiceBrowser(
                azc.zeroconf,
                stype,
                handlers=[listener._handle],
            )
            browsers.append(browser)

        await asyncio.sleep(timeout)

        for browser in browsers:
            await browser.async_cancel()
        await azc.async_close()

        return list(devices.values())


def _normalise_mac(mac: str) -> str:
    """Normalise a MAC address to ``AA:BB:CC:DD:EE:FF`` format."""
    clean = mac.upper().replace("-", ":").replace(".", "")
    if ":" not in clean and len(clean) == 12:
        clean = ":".join(clean[i:i + 2] for i in range(0, 12, 2))
    return clean
