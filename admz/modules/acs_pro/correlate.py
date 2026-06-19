"""Correlate an ADMZ device to its ACS Pro camera (ADR-0040).

Pure functions (no I/O) so they're fully unit-testable. The deterministic join
key is the **MAC address**: ADMZ stores each slot's installed-unit MAC
(``mac_address``, ADR-0036), and ACS Pro's ``DeviceListFacade:GetDeviceList``
returns ``Devices[].MacAddress``. Serial number is a secondary key if both
sides expose it.

Given the ADMZ device + ACS device/camera lists, find the ACS device with the
matching MAC, then the cameras hanging off that ACS device.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from admz.device_registry import canonical_mac


def _idval(v: Any) -> str:
    """ACS ids arrive either as a bare string or ``{"Id": "..."}``."""
    if isinstance(v, dict):
        return str(v.get("Id") or v.get("id") or "")
    return str(v or "")


def correlate_device_to_cameras(
    admz_device: Dict[str, Any],
    acs_devices: List[Dict[str, Any]],
    acs_cameras: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return a match record:

    ``{matched, match_key, admz_mac, acs_device, cameras}`` where ``cameras`` is
    the list of ACS cameras on the matched ACS device (empty if unmatched).
    """
    admz_mac = canonical_mac(
        admz_device.get("mac_address") or admz_device.get("device_id") or ""
    )
    admz_serial = (admz_device.get("serial_number") or "").strip().lower()

    matched_dev: Optional[Dict[str, Any]] = None
    match_key = ""

    # Primary: MAC.
    if admz_mac:
        for d in acs_devices:
            if canonical_mac(d.get("MacAddress") or "") == admz_mac:
                matched_dev, match_key = d, "mac"
                break

    # Secondary: serial number (only if MAC missed and both sides have one).
    if matched_dev is None and admz_serial:
        for d in acs_devices:
            ser = (d.get("SerialNumber") or d.get("DeviceSerialNumber") or "")
            if ser and str(ser).strip().lower() == admz_serial:
                matched_dev, match_key = d, "serial"
                break

    cameras: List[Dict[str, Any]] = []
    if matched_dev is not None:
        acs_dev_id = _idval(matched_dev.get("DeviceId"))
        for c in acs_cameras:
            if _idval(c.get("DeviceId")) == acs_dev_id and acs_dev_id:
                cameras.append(
                    {
                        "camera_id": _idval(c.get("CameraId")),
                        "name": c.get("Name"),
                        "model": c.get("Model"),
                    }
                )

    return {
        "matched": matched_dev is not None,
        "match_key": match_key,
        "admz_mac": admz_mac,
        "acs_device": (
            {
                "device_id": _idval(matched_dev.get("DeviceId")),
                "name": matched_dev.get("Name"),
                "model": matched_dev.get("Model"),
                "mac": matched_dev.get("MacAddress"),
                "address": matched_dev.get("Address"),
            }
            if matched_dev is not None
            else None
        ),
        "cameras": cameras,
    }
