"""
MCP server implementation for ADMZ device management.

This server provides tools for LLMs to interact with the ADMZ device registry,
enabling credential management, device discovery, and device operations.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from admz import create_device_registry
from admz.device_registry import DeviceRegistry
from admz.api.capture import capture_store, CaptureStatus
from admz.exceptions import (
    DeviceNotFoundError,
    AccountNotFoundError,
    PermissionDeniedError,
    BackendError,
    AxisSecretsError,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ADMZMCPServer:
    """
    MCP server for ADMZ device management.

    Provides tools for LLMs to interact with device registry including:
    - Device discovery and search
    - Credential retrieval
    - Device registration and management
    - Account management
    """

    def __init__(self, registry: Optional[DeviceRegistry] = None):
        """
        Initialize ADMZ MCP server.

        Args:
            registry: Device registry instance. If None, will create from environment.
        """
        self.server = Server("admz")
        self.registry = registry or create_device_registry()

        # Register tool handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register MCP tool handlers."""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available ADMZ tools."""
            return [
                Tool(
                    name="list_devices",
                    description=(
                        "List all devices in the registry. Returns device information "
                        "without credentials. Useful for discovering available devices."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="get_device",
                    description=(
                        "Get detailed information about a specific device by ID or nickname. "
                        "Returns device metadata without credentials."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID (e.g., 'front-door') or nickname",
                            },
                        },
                        "required": ["device_id"],
                    },
                ),
                Tool(
                    name="search_devices",
                    description=(
                        "Search devices by tags, location, model, or other criteria. "
                        "Returns matching devices without credentials."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by tags (e.g., ['entrance', 'outdoor'])",
                            },
                            "location": {
                                "type": "string",
                                "description": "Filter by location (e.g., 'Building A')",
                            },
                            "model": {
                                "type": "string",
                                "description": "Filter by device model",
                            },
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="list_accounts",
                    description=(
                        "List all accounts for a specific device. Returns account metadata "
                        "including usernames and purposes, but not passwords."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID",
                            },
                        },
                        "required": ["device_id"],
                    },
                ),
                Tool(
                    name="get_credentials",
                    description=(
                        "Get credentials for a specific device and account. "
                        "Returns username, password, and other authentication details. "
                        "Use with caution - this retrieves sensitive information."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account ID (default: 'default')",
                                "default": "default",
                            },
                            "requester": {
                                "type": "string",
                                "description": "Identifier of who is requesting access (for audit)",
                            },
                        },
                        "required": ["device_id"],
                    },
                ),
                Tool(
                    name="register_device",
                    description=(
                        "Register a new device in the registry. Requires device information "
                        "and optionally account credentials."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Unique device identifier",
                            },
                            "device_info": {
                                "type": "object",
                                "description": "Device metadata (host, model, location, etc.)",
                            },
                            "accounts": {
                                "type": "object",
                                "description": "Optional accounts dictionary (account_id -> account_data)",
                            },
                        },
                        "required": ["device_id", "device_info"],
                    },
                ),
                Tool(
                    name="add_account",
                    description=(
                        "Add a new account to an existing device. Requires device_id, "
                        "account_id, and account credentials."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier",
                            },
                            "account_data": {
                                "type": "object",
                                "description": "Account data (username, password, permissions, etc.)",
                            },
                        },
                        "required": ["device_id", "account_id", "account_data"],
                    },
                ),
                Tool(
                    name="update_device",
                    description=(
                        "Update device information. Can update any device metadata fields "
                        "like location, tags, firmware version, etc."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID",
                            },
                            "updates": {
                                "type": "object",
                                "description": "Fields to update",
                            },
                        },
                        "required": ["device_id", "updates"],
                    },
                ),
                Tool(
                    name="delete_device",
                    description=(
                        "Remove a device from the registry. This will delete all device "
                        "information and associated accounts. Use with caution."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID to delete",
                            },
                        },
                        "required": ["device_id"],
                    },
                ),
                Tool(
                    name="delete_account",
                    description=(
                        "Remove an account from a device. This will delete the account "
                        "credentials. Use with caution."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account ID to delete",
                            },
                        },
                        "required": ["device_id", "account_id"],
                    },
                ),
                Tool(
                    name="capture_credentials",
                    description=(
                        "Generate a secure one-time URL where the user can enter device "
                        "credentials in their browser, OUTSIDE the chat context. "
                        "Credentials entered via this URL never appear in the LLM context. "
                        "Present the returned URL to the user as a clickable link. "
                        "The ADMZ web server must be running (default: http://localhost:8000)."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID to store credentials for",
                            },
                            "account_id": {
                                "type": "string",
                                "description": "Account identifier (default: 'default')",
                                "default": "default",
                            },
                            "account_type": {
                                "type": "string",
                                "description": "Account type (e.g. 'service', 'admin')",
                                "default": "service",
                            },
                            "purpose": {
                                "type": "string",
                                "description": "Description of what this account is for",
                                "default": "",
                            },
                            "base_url": {
                                "type": "string",
                                "description": "Base URL of the ADMZ web server",
                                "default": "http://localhost:8000",
                            },
                        },
                        "required": ["device_id"],
                    },
                ),
                Tool(
                    name="check_capture_status",
                    description=(
                        "Check whether a credential capture session has been completed. "
                        "Returns status only — never returns the actual credentials. "
                        "Use after presenting a capture_credentials URL to the user."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "token": {
                                "type": "string",
                                "description": "The capture session token returned by capture_credentials",
                            },
                        },
                        "required": ["token"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> List[TextContent]:
            """Handle tool calls."""
            try:
                # Route to appropriate handler
                if name == "list_devices":
                    result = await self._list_devices()
                elif name == "get_device":
                    result = await self._get_device(arguments["device_id"])
                elif name == "search_devices":
                    result = await self._search_devices(arguments)
                elif name == "list_accounts":
                    result = await self._list_accounts(arguments["device_id"])
                elif name == "get_credentials":
                    result = await self._get_credentials(
                        arguments["device_id"],
                        arguments.get("account_id", "default"),
                        arguments.get("requester"),
                    )
                elif name == "register_device":
                    result = await self._register_device(
                        arguments["device_id"],
                        arguments["device_info"],
                        arguments.get("accounts"),
                    )
                elif name == "add_account":
                    result = await self._add_account(
                        arguments["device_id"],
                        arguments["account_id"],
                        arguments["account_data"],
                    )
                elif name == "update_device":
                    result = await self._update_device(
                        arguments["device_id"],
                        arguments["updates"],
                    )
                elif name == "delete_device":
                    result = await self._delete_device(arguments["device_id"])
                elif name == "delete_account":
                    result = await self._delete_account(
                        arguments["device_id"],
                        arguments["account_id"],
                    )
                elif name == "capture_credentials":
                    result = await self._capture_credentials(
                        arguments["device_id"],
                        arguments.get("account_id", "default"),
                        arguments.get("account_type", "service"),
                        arguments.get("purpose", ""),
                        arguments.get("base_url", "http://localhost:8000"),
                    )
                elif name == "check_capture_status":
                    result = await self._check_capture_status(
                        arguments["token"],
                    )
                else:
                    raise ValueError(f"Unknown tool: {name}")

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except DeviceNotFoundError as e:
                error = {"error": "DeviceNotFound", "message": str(e)}
                return [TextContent(type="text", text=json.dumps(error, indent=2))]
            except AccountNotFoundError as e:
                error = {"error": "AccountNotFound", "message": str(e)}
                return [TextContent(type="text", text=json.dumps(error, indent=2))]
            except PermissionDeniedError as e:
                error = {"error": "PermissionDenied", "message": str(e)}
                return [TextContent(type="text", text=json.dumps(error, indent=2))]
            except NotImplementedError as e:
                error = {"error": "NotImplemented", "message": str(e)}
                return [TextContent(type="text", text=json.dumps(error, indent=2))]
            except BackendError as e:
                error = {"error": "BackendError", "message": str(e)}
                return [TextContent(type="text", text=json.dumps(error, indent=2))]
            except AxisSecretsError as e:
                error = {"error": "ADMZError", "message": str(e)}
                return [TextContent(type="text", text=json.dumps(error, indent=2))]
            except Exception as e:
                logger.exception(f"Unexpected error in {name}")
                error = {"error": "InternalError", "message": str(e)}
                return [TextContent(type="text", text=json.dumps(error, indent=2))]

    async def _list_devices(self) -> Dict[str, Any]:
        """List all devices."""
        devices = self.registry.list_devices()
        return {
            "success": True,
            "count": len(devices),
            "devices": devices,
        }

    async def _get_device(self, device_id: str) -> Dict[str, Any]:
        """Get device information by ID or nickname."""
        # Try by device_id first
        if self.registry.device_exists(device_id):
            device = self.registry.get_device_info(device_id)
            device["device_id"] = device_id
            return {
                "success": True,
                "device": device,
            }

        # Try by nickname
        device = self.registry.get_device_by_nickname(device_id)
        if device:
            return {
                "success": True,
                "device": device,
            }

        raise DeviceNotFoundError(f"Device not found: {device_id}")

    async def _search_devices(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Search devices by criteria."""
        all_devices = self.registry.list_devices()

        # Apply filters
        matched = []
        for device in all_devices:
            match = True

            # Filter by tags
            if "tags" in filters:
                device_tags = device.get("tags", [])
                if not any(tag in device_tags for tag in filters["tags"]):
                    match = False

            # Filter by location
            if "location" in filters:
                if device.get("location") != filters["location"]:
                    match = False

            # Filter by model
            if "model" in filters:
                if device.get("model") != filters["model"]:
                    match = False

            if match:
                matched.append(device)

        return {
            "success": True,
            "count": len(matched),
            "devices": matched,
            "filters": filters,
        }

    async def _list_accounts(self, device_id: str) -> Dict[str, Any]:
        """List accounts for a device."""
        accounts = self.registry.list_accounts(device_id)
        return {
            "success": True,
            "device_id": device_id,
            "count": len(accounts),
            "accounts": accounts,
        }

    async def _get_credentials(
        self,
        device_id: str,
        account_id: str,
        requester: Optional[str],
    ) -> Dict[str, Any]:
        """Get credentials for a device account."""
        credentials = self.registry.get_credentials(
            device_id,
            account_id,
            requester,
        )
        return {
            "success": True,
            "device_id": device_id,
            "account_id": account_id,
            "credentials": credentials,
        }

    async def _register_device(
        self,
        device_id: str,
        device_info: Dict[str, Any],
        accounts: Optional[Dict[str, Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Register a new device."""
        self.registry.add_device(device_id, device_info, accounts)
        return {
            "success": True,
            "message": f"Device '{device_id}' registered successfully",
            "device_id": device_id,
        }

    async def _add_account(
        self,
        device_id: str,
        account_id: str,
        account_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add an account to a device."""
        self.registry.add_account(device_id, account_id, account_data)
        return {
            "success": True,
            "message": f"Account '{account_id}' added to device '{device_id}'",
            "device_id": device_id,
            "account_id": account_id,
        }

    async def _update_device(
        self,
        device_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update device information."""
        # Get current device info
        device_info = self.registry.get_device_info(device_id)

        # Merge updates
        device_info.update(updates)

        # Re-register device with updated info
        # Note: This assumes the backend supports updating
        # In practice, you might need to implement update_device method
        # For now, we'll use add_device which should update if exists
        self.registry.add_device(device_id, device_info)

        return {
            "success": True,
            "message": f"Device '{device_id}' updated successfully",
            "device_id": device_id,
            "updates": updates,
        }

    async def _delete_device(self, device_id: str) -> Dict[str, Any]:
        """Delete a device."""
        self.registry.remove_device(device_id)
        return {
            "success": True,
            "message": f"Device '{device_id}' deleted successfully",
            "device_id": device_id,
        }

    async def _delete_account(
        self,
        device_id: str,
        account_id: str,
    ) -> Dict[str, Any]:
        """Delete an account from a device."""
        self.registry.remove_account(device_id, account_id)
        return {
            "success": True,
            "message": f"Account '{account_id}' deleted from device '{device_id}'",
            "device_id": device_id,
            "account_id": account_id,
        }

    async def _capture_credentials(
        self,
        device_id: str,
        account_id: str,
        account_type: str,
        purpose: str,
        base_url: str,
    ) -> Dict[str, Any]:
        """Create a credential capture session and return the URL."""
        if not self.registry.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        session = capture_store.create_session(
            device_id=device_id,
            account_id=account_id,
            account_type=account_type,
            purpose=purpose,
        )

        base_url = base_url.rstrip("/")
        url = f"{base_url}/capture/{session.token}"

        return {
            "success": True,
            "message": (
                "Credential capture URL generated. "
                "Present this link to the user — credentials entered via "
                "this URL will NOT appear in the chat context."
            ),
            "url": url,
            "token": session.token,
            "device_id": device_id,
            "account_id": account_id,
            "expires_in_seconds": int(session.ttl),
        }

    async def _check_capture_status(self, token: str) -> Dict[str, Any]:
        """Check whether a capture session has been completed."""
        session = capture_store.get_session(token)
        if session is None:
            return {
                "success": True,
                "status": "expired_or_not_found",
                "message": "This capture session has expired or does not exist.",
            }

        status = session.effective_status.value
        result: Dict[str, Any] = {
            "success": True,
            "status": status,
            "device_id": session.device_id,
            "account_id": session.account_id,
        }

        if status == "completed":
            result["message"] = (
                f"Credentials for {session.device_id}/{session.account_id} "
                "have been saved successfully."
            )
        elif status == "pending":
            result["message"] = "Waiting for the user to enter credentials."
        else:
            result["message"] = "This capture session has expired."

        return result

    async def run(self):
        """Run the MCP server with stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            logger.info("ADMZ MCP server starting...")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def main():
    """Main entry point for MCP server."""
    try:
        server = ADMZMCPServer()
        await server.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception("Server error")
        raise


if __name__ == "__main__":
    asyncio.run(main())
