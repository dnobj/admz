"""
Catalog resolver — maps (device, intent) to filtered operation docs.

This is the brain of query_catalog. Given a device and a task intent,
it finds the relevant operations, filters by device capabilities,
and returns documentation the LLM can read.
"""

import logging
from typing import Any, Dict, List, Optional

from admz.catalog.loader import CatalogLoader
from admz.catalog.models import ResolverResult

logger = logging.getLogger(__name__)

# Synonyms for fuzzy intent matching.  Maps common words/phrases to
# canonical task-index keys.
_INTENT_SYNONYMS: Dict[str, List[str]] = {
    "resolution": ["change-resolution"],
    "set resolution": ["change-resolution"],
    "image size": ["change-resolution"],
    "compression": ["change-compression"],
    "quality": ["change-compression"],
    "framerate": ["change-framerate"],
    "fps": ["change-framerate"],
    "frame rate": ["change-framerate"],
    "rotate": ["rotate-image"],
    "rotation": ["rotate-image"],
    "flip": ["rotate-image"],
    "mirror": ["rotate-image"],
    "stream profile": ["configure-stream-profile"],
    "stream": ["configure-stream-profile"],
    "hostname": ["set-hostname"],
    "host name": ["set-hostname"],
    "network": ["configure-network"],
    "ip": ["configure-ip"],
    "ip address": ["configure-ip"],
    "dns": ["configure-dns"],
    "ntp": ["configure-ntp"],
    "time server": ["configure-ntp"],
    "timezone": ["set-timezone"],
    "time zone": ["set-timezone"],
    "time": ["check-time"],
    "date": ["check-time"],
    "device info": ["get-device-info"],
    "model": ["get-device-info"],
    "serial": ["get-device-info"],
    "firmware": ["check-firmware"],
    "firmware version": ["check-firmware"],
    "identify": ["identify-device"],
    "apis": ["discover-apis"],
    "capabilities": ["discover-apis"],
    "what can": ["discover-apis"],
    "user": ["manage-users"],
    "users": ["manage-users"],
    "account": ["manage-users"],
    "add user": ["add-user"],
    "create user": ["add-user"],
    "remove user": ["remove-user"],
    "delete user": ["remove-user"],
    "change password": ["change-password"],
    "update password": ["change-password"],
    "set password": ["change-password", "add-user"],
    "rotate password": ["change-password"],
    "factory reset": ["factory-reset"],
    "factory default": ["factory-reset"],
    "reset": ["factory-reset"],
    "upgrade firmware": ["upgrade-firmware"],
    "firmware upgrade": ["upgrade-firmware"],
    "update firmware": ["upgrade-firmware"],
    "flash firmware": ["upgrade-firmware"],
    "rollback firmware": ["rollback-firmware"],
    "firmware rollback": ["rollback-firmware"],
    "firmware status": ["check-firmware"],
    "commit firmware": ["commit-firmware"],
    "reboot": ["reboot-device"],
    "restart": ["reboot-device"],
    "disk": ["manage-storage"],
    "disks": ["manage-storage"],
    "storage": ["manage-storage"],
    "sd card": ["manage-storage"],
    "format disk": ["manage-storage"],
    "format sd": ["manage-storage"],
    "job": ["check-disk-job"],
    "disk job": ["check-disk-job"],
    "format job": ["check-disk-job"],
    "recording": ["manage-recordings"],
    "recordings": ["manage-recordings"],
    "continuous recording": ["manage-recordings"],
    # Wave 1: Snapshot + System Health + Disk
    "snapshot": ["take-snapshot"],
    "take snapshot": ["take-snapshot"],
    "grab image": ["take-snapshot"],
    "capture image": ["take-snapshot"],
    "jpeg": ["take-snapshot"],
    "jpg": ["take-snapshot"],
    "still image": ["take-snapshot"],
    "system ready": ["check-system-ready"],
    "ready": ["check-system-ready"],
    "boot status": ["check-system-ready"],
    "heartbeat": ["check-heartbeat"],
    "keepalive": ["check-heartbeat"],
    "health check": ["check-heartbeat"],
    "stream status": ["stream-status"],
    "active streams": ["stream-status"],
    "viewers": ["stream-status"],
    "who is watching": ["stream-status"],
    "overlay modifiers": ["check-overlay-modifiers"],
    "overlay variables": ["check-overlay-modifiers"],
    "text overlay": ["check-overlay-modifiers", "manage-overlays"],
    "disk health": ["manage-storage"],
    "disk check": ["manage-storage"],
    "check disk": ["manage-storage"],
    "repair disk": ["manage-storage"],
    "mount disk": ["manage-storage"],
    "unmount disk": ["manage-storage"],
    "disk capabilities": ["manage-storage"],
    # Wave 2: Image & Optics Control
    "day night": ["configure-daynight"],
    "daynight": ["configure-daynight"],
    "night mode": ["configure-daynight"],
    "ir cut": ["configure-daynight"],
    "ir filter": ["configure-daynight"],
    "night filter": ["configure-daynight"],
    "optics": ["control-optics"],
    "lens": ["control-optics"],
    "focus": ["manage-focus"],
    "autofocus": ["manage-focus"],
    "auto focus": ["manage-focus"],
    "zoom": ["control-optics"],
    "magnification": ["control-optics"],
    "view area": ["manage-view-areas"],
    "view areas": ["manage-view-areas"],
    "digital ptz": ["manage-view-areas"],
    "dptz": ["manage-view-areas"],
    "orientation": ["set-orientation"],
    "tilt angle": ["set-orientation"],
    "camera angle": ["set-orientation"],
    "privacy mask": ["manage-privacy-masks"],
    "privacy filter": ["manage-privacy-masks"],
    "privacy": ["manage-privacy-masks"],
    "pencil": ["manage-privacy-masks"],
    # Wave 3: Config-REST Security
    "certificate": ["manage-certificates"],
    "certificates": ["manage-certificates"],
    "tls": ["manage-certificates"],
    "ssl": ["manage-certificates"],
    "csr": ["manage-certificates"],
    "ca cert": ["manage-certificates"],
    "https cert": ["manage-certificates"],
    "ssh": ["manage-ssh"],
    "ssh user": ["manage-ssh"],
    "ssh key": ["manage-ssh"],
    "ssh access": ["manage-ssh"],
    "firewall": ["manage-firewall"],
    "firewall rules": ["manage-firewall"],
    "acl": ["manage-firewall"],
    "ip filter": ["manage-firewall"],
    "access control": ["manage-firewall"],
    # Wave 4: Config-REST Infra + Network
    "snmp": ["configure-snmp"],
    "snmp v3": ["configure-snmp"],
    "snmp trap": ["configure-snmp"],
    "snmp community": ["configure-snmp"],
    "time config": ["configure-time-modern"],
    "set time": ["configure-time-modern"],
    "set date": ["configure-time-modern"],
    "persistent log": ["manage-persistent-log"],
    "write log": ["manage-persistent-log"],
    "log message": ["manage-persistent-log"],
    "vlan": ["configure-vlan"],
    "add vlan": ["configure-vlan"],
    "remove vlan": ["configure-vlan"],
    "proxy": ["configure-proxy"],
    "http proxy": ["configure-proxy"],
    "802.1x": ["configure-8021x"],
    "8021x": ["configure-8021x"],
    "dot1x": ["configure-8021x"],
    "ipv6": ["configure-ipv6"],
    "mdns": ["configure-mdns"],
    "bonjour": ["configure-mdns"],
    "friendly name": ["configure-mdns"],
    "http header": ["configure-http-headers"],
    "custom header": ["configure-http-headers"],
    "cors": ["configure-http-headers"],
    # Wave 5: PTZ + Apps + Guard Tours
    "recorded tour": ["manage-guard-tours-recorded"],
    "recorded guard tour": ["manage-guard-tours-recorded"],
    "guard tour recorded": ["manage-guard-tours-recorded"],
    "play tour": ["manage-guard-tours-recorded"],
    "app config": ["configure-application"],
    "application config": ["configure-application"],
    "allow unsigned": ["configure-application"],
    "allow root": ["configure-application"],
    "app license": ["manage-app-license"],
    "application license": ["manage-app-license"],
    "license key": ["manage-app-license"],
    "power": ["configure-power"],
    "poe": ["configure-power"],
    "power profile": ["configure-power"],
    "power consumption": ["configure-power"],
    "power status": ["configure-power"],
    "network share": ["manage-network-shares"],
    "nas": ["manage-network-shares"],
    "smb": ["manage-network-shares"],
    "cifs": ["manage-network-shares"],
    "remote storage": ["manage-network-shares"],
    # Wave 6: Specialized Hardware
    "siren": ["control-siren"],
    "alarm siren": ["control-siren"],
    "strobe": ["control-siren"],
    "alarm light": ["control-siren"],
    "wiper": ["control-wiper"],
    "washer": ["control-wiper"],
    "clear view": ["control-wiper"],
    "clean lens": ["control-wiper"],
    "temperature": ["monitor-temperature"],
    "heater": ["monitor-temperature"],
    "fan": ["monitor-temperature"],
    "thermal": ["monitor-temperature"],
    "led": ["control-leds"],
    "status led": ["control-leds"],
    "indicator light": ["control-leds"],
    "shock": ["monitor-shock"],
    "vibration": ["monitor-shock"],
    "tamper": ["monitor-shock"],
    "shock detection": ["monitor-shock"],
    "media clip": ["manage-media-clips"],
    "audio clip": ["manage-media-clips"],
    "play clip": ["manage-media-clips"],
    "play audio": ["manage-media-clips"],
    "announcement": ["manage-media-clips"],
    # Wave 7: Zipstream, Audio, Serial, RAID
    "zipstream": ["configure-zipstream"],
    "bandwidth": ["configure-zipstream"],
    "compression strength": ["configure-zipstream"],
    "gop": ["configure-zipstream"],
    "dynamic fps": ["configure-zipstream"],
    "audio stream": ["audio-streaming"],
    "microphone": ["audio-streaming"],
    "speaker": ["audio-streaming"],
    "audio receive": ["audio-streaming"],
    "audio transmit": ["audio-streaming"],
    "serial": ["serial-port"],
    "serial port": ["serial-port"],
    "rs232": ["serial-port"],
    "rs485": ["serial-port"],
    "raid": ["manage-raid"],
    "raid status": ["manage-raid"],
    "raid array": ["manage-raid"],
    # SOAP certificate management
    "soap certificate": ["manage-certificates-soap"],
    "self-signed cert": ["manage-certificates-soap", "manage-certificates"],
    "create certificate": ["manage-certificates-soap", "manage-certificates"],
    "delete certificate": ["manage-certificates-soap", "manage-certificates"],
    "client certificate": ["manage-certificates-soap"],
    "ca certificate": ["manage-certificates-soap", "manage-certificates"],
    # Entry service (service discovery)
    "services": ["discover-services"],
    "what services": ["discover-services"],
    "service discovery": ["discover-services"],
    "supported services": ["discover-services"],
    # Action service
    "action rule": ["manage-actions"],
    "action template": ["manage-actions"],
    "action configuration": ["manage-actions"],
    # Event service
    "event": ["manage-events-soap"],
    "events": ["manage-events-soap"],
    "event topic": ["manage-events-soap"],
    "event instance": ["manage-events-soap"],
    # Syslog
    "syslog": ["configure-syslog"],
    "remote syslog": ["configure-syslog"],
    "remote log": ["configure-syslog"],
    # Light control (augment existing)
    "light control": ["control-lights"],
    "illumination": ["control-lights"],
    "ir led": ["control-lights"],
    "white light": ["control-lights"],
    "light intensity": ["control-lights"],
    "angle of illumination": ["control-lights"],
    # LLDP
    "lldp": ["configure-lldp"],
    "lldp neighbor": ["configure-lldp"],
    "lldp status": ["configure-lldp"],
    # Network settings (config-rest)
    "network config rest": ["configure-network-rest"],
}


class CatalogResolver:
    """Maps (device, intent) to relevant operation documents."""

    def __init__(self, loader: CatalogLoader):
        self.loader = loader

    def resolve(
        self,
        device_id: str,
        intent: str,
        family: str = "vapix",
        device_info: Optional[Dict[str, Any]] = None,
    ) -> ResolverResult:
        """
        Resolve an intent to filtered operation docs for a device.

        Args:
            device_id: Device identifier.
            intent: User intent string (e.g., "set resolution").
            family: API family (default "vapix").
            device_info: Device metadata from registry. If provided,
                used for capability filtering.

        Returns:
            ResolverResult with operations, parameter groups, and metadata.
        """
        # 1. Map intent to task index keys
        task_keys = self._match_intent(intent, family)

        if not task_keys:
            return ResolverResult(
                operations=[],
                parameter_groups=[],
                device={"device_id": device_id, **(device_info or {})},
                risk_summary={},
                notes=[f"No matching operations found for intent: '{intent}'"],
            )

        # 2. Collect all file paths from matched task keys
        task_index = self.loader.load_index(family, "by-task")
        file_paths: List[str] = []
        for key in task_keys:
            paths = task_index.get(key, [])
            for p in paths:
                if p not in file_paths:
                    file_paths.append(p)

        # 3. Load all referenced files
        loaded = self.loader.load_files(family, file_paths)

        # 4. Separate operations from parameter groups
        operations: List[Dict[str, Any]] = []
        parameter_groups: List[Dict[str, Any]] = []
        risk_counts: Dict[str, int] = {}
        notes: List[str] = []

        for fp, data in loaded.items():
            if not data:
                continue

            # Enrich with CGI metadata
            cgi_name = data.get("cgi")
            if cgi_name:
                cgi_meta = self.loader.get_cgi_metadata(family, cgi_name)
                if cgi_meta:
                    data["_endpoint"] = cgi_meta.endpoint
                    data["_generation"] = cgi_meta.generation
                    data["_auth"] = cgi_meta.auth

            # Parameter group files have a "group" key
            if "group" in data:
                # Filter by device capabilities if we have info
                if device_info and not self._device_supports_group(
                    data, device_info
                ):
                    continue
                parameter_groups.append(data)
            elif "id" in data:
                # Operation file
                risk = data.get("risk_level", "normal")
                risk_counts[risk] = risk_counts.get(risk, 0) + 1

                # Add warnings for risky operations
                if risk == "dangerous":
                    desc = data.get("danger_description", "")
                    notes.append(f"WARNING: {data['id']} is dangerous. {desc}")
                elif risk == "service-affecting":
                    impact = data.get("service_impact", "")
                    notes.append(f"Note: {data['id']} may affect service. {impact}")

                operations.append(data)

        # 5. Also load _api.yaml for each referenced API
        cgi_names = set()
        for op in operations:
            if op.get("cgi"):
                cgi_names.add(op["cgi"])
        for pg in parameter_groups:
            if pg.get("cgi"):
                cgi_names.add(pg["cgi"])

        cgi_metadata = {}
        for cgi_name in cgi_names:
            meta = self.loader.get_cgi_metadata(family, cgi_name)
            if meta:
                cgi_metadata[cgi_name] = {
                    "endpoint": meta.endpoint,
                    "generation": meta.generation,
                    "auth": meta.auth,
                    "min_firmware": meta.min_firmware,
                }

        # Attach CGI metadata to each operation for the LLM
        for op in operations:
            cgi_name = op.get("cgi")
            if cgi_name and cgi_name in cgi_metadata:
                op["_cgi"] = cgi_metadata[cgi_name]

        device_data = {"device_id": device_id}
        if device_info:
            device_data.update(device_info)

        return ResolverResult(
            operations=operations,
            parameter_groups=parameter_groups,
            device=device_data,
            risk_summary=risk_counts,
            notes=notes,
        )

    def _match_intent(self, intent: str, family: str) -> List[str]:
        """
        Map a user intent string to task index keys.

        Uses synonym table first, then falls back to substring match
        against index keys.
        """
        intent_lower = intent.lower().strip()

        # 1. Check synonyms (exact match on intent)
        if intent_lower in _INTENT_SYNONYMS:
            return _INTENT_SYNONYMS[intent_lower]

        # 2. Check if intent contains a synonym key
        matched = []
        for synonym, keys in _INTENT_SYNONYMS.items():
            if synonym in intent_lower:
                for k in keys:
                    if k not in matched:
                        matched.append(k)
        if matched:
            return matched

        # 3. Direct match against task index keys
        task_index = self.loader.load_index(family, "by-task")
        direct = []
        for key in task_index:
            # Check if intent words appear in the key or vice versa
            key_words = set(key.replace("-", " ").split())
            intent_words = set(intent_lower.replace("-", " ").split())
            if key_words & intent_words:
                direct.append(key)
        if direct:
            return direct

        # 4. If the intent looks like it might be an index key, try it
        slug = intent_lower.replace(" ", "-")
        if slug in task_index:
            return [slug]

        return []

    def _device_supports_group(
        self, group_data: Dict[str, Any], device_info: Dict[str, Any]
    ) -> bool:
        """Check if a device supports a parameter group."""
        requires = group_data.get("requires", {})
        if not requires:
            return True

        # Check required properties
        device_props = device_info.get("properties", {})
        for prop in requires.get("properties", []):
            if device_props and prop not in device_props:
                return False

        return True

    def list_available_tasks(self, family: str = "vapix") -> List[str]:
        """List all task keys in the index."""
        task_index = self.loader.load_index(family, "by-task")
        return sorted(task_index.keys())
