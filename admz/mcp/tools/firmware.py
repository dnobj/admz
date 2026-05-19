"""MCP Tool definitions: firmware download / import / cache."""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="download_firmware",
        description=(
            "Download firmware for an Axis device from the public FTP, "
            "or check the latest available version. Also computes the "
            "required upgrade path (LTS milestones) if the device's "
            "current firmware version is known. The downloaded file can "
            "be used with execute_operation(firmwaremanagement.cgi:upgrade). "
            "Not all models are available on the public FTP — when a model "
            "is missing, suggests manual download from axis.com/support."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": (
                        "Device model name (e.g. 'P3245-V', 'C1710'). "
                        "If not provided, resolved from device_id."
                    ),
                },
                "device_id": {
                    "type": "string",
                    "description": (
                        "Device ID in registry. Used to resolve model "
                        "and current firmware version for upgrade path."
                    ),
                },
                "version": {
                    "type": "string",
                    "description": (
                        "Specific firmware version to download. "
                        "If omitted, downloads the latest."
                    ),
                },
                "check_only": {
                    "type": "boolean",
                    "description": (
                        "If true, only check the latest version and "
                        "upgrade path without downloading."
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="import_firmware",
        description=(
            "Scan a local directory (default: ~/Downloads) for Axis "
            "firmware .bin files and import them into the firmware cache. "
            "Identifies firmware by filename pattern and cross-references "
            "against the manifest of known Axis models. Use scan_only=true "
            "to preview what would be imported without copying. Imported "
            "files can then be used with "
            "execute_operation(firmwaremanagement.cgi:upgrade)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": (
                        "Directory to scan for .bin files. "
                        "Defaults to ~/Downloads if omitted."
                    ),
                },
                "scan_only": {
                    "type": "boolean",
                    "description": (
                        "If true, just show what firmware files were "
                        "found without importing them."
                    ),
                    "default": False,
                },
                "device_id": {
                    "type": "string",
                    "description": (
                        "If provided, only import firmware matching "
                        "this device's model."
                    ),
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="list_cached_firmware",
        description=(
            "List all firmware .bin files in the local firmware cache "
            "(~/.admz/firmware/). Shows filename, size, and path for "
            "each cached file."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]
