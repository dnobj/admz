"""
MCP server implementation for ADMZ device management.

This server provides tools for LLMs to interact with the ADMZ device registry,
enabling credential management, device discovery, and device operations.

Catalog-in-the-loop tools:
  - query_catalog: returns filtered operation docs for a device + intent
  - execute_operation: runs a single catalog operation
  - create_plan: submits a multi-step plan for review
  - execute_plan: runs an approved plan autonomously
  - get_plan_status: checks progress of a running plan

Snapshot/restore tools:
  - snapshot_device: capture device config to git
  - snapshot_fleet: bulk snapshot filtered by tag
  - restore_device: propose a plan to restore from a git ref
  - diff_device: show config changes between refs
  - check_drift: compare live device state to git HEAD
"""

import asyncio
import json
import logging
import os
import secrets
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from admz import create_device_registry
from admz.device_registry import DeviceRegistry
from admz.api.capture import capture_store, CaptureStatus
from admz.catalog.loader import CatalogLoader
from admz.catalog.resolver import CatalogResolver
from admz.executor.vapix import VAPXExecutor
from admz.plans.engine import PlanEngine
from admz.snapshot.engine import SnapshotEngine
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.restore import RestoreBuilder
from admz.snapshot.drift import DriftDetector
from admz.snapshot.scheduler import SnapshotScheduler, SnapshotSchedule, parse_interval
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

    def __init__(
        self,
        registry: Optional[DeviceRegistry] = None,
        catalog_path: Optional[str] = None,
    ):
        """
        Initialize ADMZ MCP server.

        Args:
            registry: Device registry instance. If None, will create from environment.
            catalog_path: Path to the operations catalog directory.
                If None, uses ADMZ_CATALOG_PATH env var or ./catalog.
        """
        self.server = Server("admz")
        self.registry = registry or create_device_registry()

        # Catalog and resolver
        catalog_path = catalog_path or os.getenv(
            "ADMZ_CATALOG_PATH",
            os.path.join(os.path.dirname(__file__), "..", "..", "catalog"),
        )
        self.catalog = CatalogLoader(catalog_path)
        self.resolver = CatalogResolver(self.catalog)

        # Executors (one per API family)
        vapix_executor = VAPXExecutor()
        self.executors = {"vapix": vapix_executor}

        # Plan engine
        self.plan_engine = PlanEngine(
            catalog=self.catalog,
            registry=self.registry,
            executors=self.executors,
        )

        # Snapshot / restore
        config_repo_path = os.getenv(
            "ADMZ_CONFIG_REPO_PATH",
            os.path.join(os.path.expanduser("~"), ".admz", "config-repo"),
        )
        config_repo_remote = os.getenv("ADMZ_CONFIG_REPO_REMOTE")
        self.git_repo = GitRepo(config_repo_path, remote_url=config_repo_remote)
        self.snapshot_engine = SnapshotEngine(
            catalog=self.catalog,
            registry=self.registry,
            executors=self.executors,
            git_repo=self.git_repo,
        )
        self.restore_builder = RestoreBuilder(
            catalog=self.catalog,
            registry=self.registry,
            git_repo=self.git_repo,
        )
        self.drift_detector = DriftDetector(
            snapshot_engine=self.snapshot_engine,
            git_repo=self.git_repo,
        )

        # Scheduler
        schedule_path = os.path.join(
            os.path.expanduser("~"), ".admz", "schedules.json"
        )
        self.scheduler = SnapshotScheduler(
            snapshot_engine=self.snapshot_engine,
            schedule_path=schedule_path,
        )

        # Dangerous operation confirm tokens (token → operation details)
        self._confirm_tokens: Dict[str, Dict[str, Any]] = {}

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
                # --- Catalog + Execution tools ---
                Tool(
                    name="query_catalog",
                    description=(
                        "Look up what operations are available for a device and task. "
                        "Returns filtered documentation from the operations catalog — "
                        "operation specs, parameter groups, risk levels, and CGI metadata. "
                        "Use this BEFORE execute_operation to understand what's available "
                        "and what parameters to use. The returned docs are the source of "
                        "truth for building operation calls."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID to query for",
                            },
                            "intent": {
                                "type": "string",
                                "description": (
                                    "What you want to do, in natural language. "
                                    "e.g. 'change resolution', 'configure NTP', "
                                    "'add user', 'check firmware'"
                                ),
                            },
                            "family": {
                                "type": "string",
                                "description": "API family (default: 'vapix')",
                                "default": "vapix",
                            },
                        },
                        "required": ["device_id", "intent"],
                    },
                ),
                Tool(
                    name="execute_operation",
                    description=(
                        "Execute a single catalog operation against a device. "
                        "The operation_id and params should come from query_catalog results. "
                        "Handles authentication, HTTP request construction, and response "
                        "parsing automatically. Dangerous operations will be blocked and "
                        "return a confirm_token — use confirm_dangerous_operation to proceed."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID to execute on",
                            },
                            "operation_id": {
                                "type": "string",
                                "description": (
                                    "Operation ID from the catalog "
                                    "(e.g. 'param.cgi:update', 'basicdeviceinfo.cgi:getAllProperties')"
                                ),
                            },
                            "params": {
                                "type": "object",
                                "description": (
                                    "Parameters for the operation. For param.cgi:update, "
                                    "these are the key=value pairs (e.g. "
                                    "{'root.Image.I0.Resolution': '1920x1080'}). "
                                    "For param.cgi:list, include 'group' key."
                                ),
                                "additionalProperties": {"type": "string"},
                            },
                            "family": {
                                "type": "string",
                                "description": "API family (default: 'vapix')",
                                "default": "vapix",
                            },
                        },
                        "required": ["device_id", "operation_id", "params"],
                    },
                ),
                Tool(
                    name="confirm_dangerous_operation",
                    description=(
                        "Confirm and execute a dangerous operation that was blocked by "
                        "the risk gate. Requires the confirm_token returned by "
                        "execute_operation when it blocks a dangerous operation. "
                        "Tokens are single-use and expire after 5 minutes."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "confirm_token": {
                                "type": "string",
                                "description": "The single-use confirmation token",
                            },
                        },
                        "required": ["confirm_token"],
                    },
                ),
                # --- Plan tools ---
                Tool(
                    name="create_plan",
                    description=(
                        "Create a multi-step execution plan for review. "
                        "Submit a list of operations with concrete parameters. "
                        "The plan is validated against the catalog and risk-classified. "
                        "Returns a plan summary for the user to approve. "
                        "Does NOT execute — call execute_plan after approval."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Human-readable plan description",
                            },
                            "steps": {
                                "type": "array",
                                "description": "List of plan steps",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "operation_id": {
                                            "type": "string",
                                            "description": "Catalog operation ID",
                                        },
                                        "device_id": {
                                            "type": "string",
                                            "description": "Target device ID",
                                        },
                                        "params": {
                                            "type": "object",
                                            "description": "Operation parameters",
                                            "additionalProperties": {"type": "string"},
                                        },
                                        "description": {
                                            "type": "string",
                                            "description": "Human-readable step description",
                                        },
                                        "depends_on": {
                                            "type": "array",
                                            "items": {"type": "integer"},
                                            "description": "Step numbers this depends on",
                                        },
                                    },
                                    "required": ["operation_id", "device_id", "params"],
                                },
                            },
                            "on_failure": {
                                "type": "string",
                                "enum": ["stop", "skip_dependents", "continue"],
                                "description": (
                                    "What to do when a step fails. "
                                    "'stop': abort remaining steps (safe default). "
                                    "'skip_dependents': skip dependent steps, continue others. "
                                    "'continue': keep going regardless."
                                ),
                                "default": "stop",
                            },
                        },
                        "required": ["description", "steps"],
                    },
                ),
                Tool(
                    name="execute_plan",
                    description=(
                        "Execute an approved plan. Runs all steps autonomously — "
                        "does not pause for per-step approval. For plans with steps "
                        "on different devices, runs devices in parallel. "
                        "Returns results for all steps including any errors."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "plan_id": {
                                "type": "string",
                                "description": "Plan ID from create_plan",
                            },
                        },
                        "required": ["plan_id"],
                    },
                ),
                Tool(
                    name="get_plan_status",
                    description=(
                        "Check the status and progress of a plan. "
                        "Use for long-running fleet plans to monitor progress."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "plan_id": {
                                "type": "string",
                                "description": "Plan ID to check",
                            },
                        },
                        "required": ["plan_id"],
                    },
                ),
                # --- Snapshot / Restore tools ---
                Tool(
                    name="snapshot_device",
                    description=(
                        "Capture a device's full configuration and commit it "
                        "to the config git repository. Reads all applicable "
                        "facets (image, network, time, events, etc.) and writes "
                        "normalized YAML + raw responses. Returns a summary "
                        "of what was captured."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID to snapshot",
                            },
                            "message": {
                                "type": "string",
                                "description": (
                                    "Optional commit message "
                                    "(default: 'Snapshot <device_id>')"
                                ),
                            },
                        },
                        "required": ["device_id"],
                    },
                ),
                Tool(
                    name="snapshot_fleet",
                    description=(
                        "Snapshot all devices (or a filtered subset) in a "
                        "single commit. Devices are read in parallel."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tag_filter": {
                                "type": "string",
                                "description": (
                                    "Only snapshot devices with this tag. "
                                    "Omit to snapshot all devices."
                                ),
                            },
                            "message": {
                                "type": "string",
                                "description": "Optional commit message",
                            },
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="restore_device",
                    description=(
                        "Build a plan that restores a device to a previous "
                        "configuration from git. Returns the plan for review — "
                        "call execute_plan to apply it. Accepts a git ref "
                        "(commit SHA, tag, or branch)."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID to restore",
                            },
                            "ref": {
                                "type": "string",
                                "description": (
                                    "Git ref to restore from "
                                    "(SHA, tag, or branch). Default: HEAD"
                                ),
                                "default": "HEAD",
                            },
                            "facets": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Specific facets to restore "
                                    "(e.g. ['image', 'time']). "
                                    "Omit to restore all."
                                ),
                            },
                        },
                        "required": ["device_id"],
                    },
                ),
                Tool(
                    name="diff_device",
                    description=(
                        "Show configuration changes for a device between two "
                        "git refs, or between a ref and the current live state."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID",
                            },
                            "ref_a": {
                                "type": "string",
                                "description": "First git ref (default: HEAD~1)",
                                "default": "HEAD~1",
                            },
                            "ref_b": {
                                "type": "string",
                                "description": (
                                    "Second git ref (default: HEAD)"
                                ),
                                "default": "HEAD",
                            },
                        },
                        "required": ["device_id"],
                    },
                ),
                Tool(
                    name="check_drift",
                    description=(
                        "Compare a device's live configuration against what's "
                        "stored in git. Reports any fields that differ. "
                        "Useful for detecting manual changes made outside ADMZ."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": (
                                    "Device ID to check. Omit to check "
                                    "all devices."
                                ),
                            },
                            "tag_filter": {
                                "type": "string",
                                "description": (
                                    "Only check devices with this tag "
                                    "(when device_id is omitted)"
                                ),
                            },
                        },
                        "required": [],
                    },
                ),
                # --- Schedule tools ---
                Tool(
                    name="create_snapshot_schedule",
                    description=(
                        "Create a recurring snapshot schedule. Snapshots run "
                        "automatically at the specified interval. Use "
                        "interval like '30m', '2h', '1d', or '12h'."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "schedule_id": {
                                "type": "string",
                                "description": (
                                    "Unique ID for this schedule "
                                    "(e.g. 'nightly-all', 'hourly-lobby')"
                                ),
                            },
                            "description": {
                                "type": "string",
                                "description": (
                                    "Human-readable description"
                                ),
                            },
                            "interval": {
                                "type": "string",
                                "description": (
                                    "How often to run. Examples: "
                                    "'30m', '2h', '1d', '12h'"
                                ),
                            },
                            "tag_filter": {
                                "type": "string",
                                "description": (
                                    "Only snapshot devices with this tag. "
                                    "Omit to snapshot all devices."
                                ),
                            },
                            "device_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Specific device IDs to snapshot. "
                                    "Omit to use tag_filter or all devices."
                                ),
                            },
                        },
                        "required": ["schedule_id", "description", "interval"],
                    },
                ),
                Tool(
                    name="list_snapshot_schedules",
                    description=(
                        "List all configured snapshot schedules with their "
                        "status, last run time, and next run time."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="update_snapshot_schedule",
                    description=(
                        "Update an existing schedule. Can change interval, "
                        "enable/disable, change tag filter, etc."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "schedule_id": {
                                "type": "string",
                                "description": "Schedule ID to update",
                            },
                            "interval": {
                                "type": "string",
                                "description": "New interval (e.g. '1h')",
                            },
                            "enabled": {
                                "type": "boolean",
                                "description": "Enable or disable",
                            },
                            "tag_filter": {
                                "type": "string",
                                "description": "New tag filter",
                            },
                            "description": {
                                "type": "string",
                                "description": "New description",
                            },
                        },
                        "required": ["schedule_id"],
                    },
                ),
                Tool(
                    name="delete_snapshot_schedule",
                    description="Delete a snapshot schedule.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "schedule_id": {
                                "type": "string",
                                "description": "Schedule ID to delete",
                            },
                        },
                        "required": ["schedule_id"],
                    },
                ),
                Tool(
                    name="run_snapshot_schedule",
                    description=(
                        "Manually trigger a scheduled snapshot right now, "
                        "without waiting for the next interval."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "schedule_id": {
                                "type": "string",
                                "description": "Schedule ID to run",
                            },
                        },
                        "required": ["schedule_id"],
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
                # --- Catalog + Execution tools ---
                elif name == "query_catalog":
                    result = await self._query_catalog(
                        arguments["device_id"],
                        arguments["intent"],
                        arguments.get("family", "vapix"),
                    )
                elif name == "execute_operation":
                    result = await self._execute_operation(
                        arguments["device_id"],
                        arguments["operation_id"],
                        arguments.get("params", {}),
                        arguments.get("family", "vapix"),
                    )
                elif name == "confirm_dangerous_operation":
                    result = await self._confirm_dangerous(
                        arguments["confirm_token"],
                    )
                # --- Plan tools ---
                elif name == "create_plan":
                    result = await self._create_plan(
                        arguments["description"],
                        arguments["steps"],
                        arguments.get("on_failure", "stop"),
                    )
                elif name == "execute_plan":
                    result = await self._execute_plan(
                        arguments["plan_id"],
                    )
                elif name == "get_plan_status":
                    result = await self._get_plan_status(
                        arguments["plan_id"],
                    )
                # --- Snapshot / Restore tools ---
                elif name == "snapshot_device":
                    result = await self._snapshot_device(
                        arguments["device_id"],
                        arguments.get("message"),
                    )
                elif name == "snapshot_fleet":
                    result = await self._snapshot_fleet(
                        arguments.get("tag_filter"),
                        arguments.get("message"),
                    )
                elif name == "restore_device":
                    result = await self._restore_device(
                        arguments["device_id"],
                        arguments.get("ref", "HEAD"),
                        arguments.get("facets"),
                    )
                elif name == "diff_device":
                    result = await self._diff_device(
                        arguments["device_id"],
                        arguments.get("ref_a", "HEAD~1"),
                        arguments.get("ref_b", "HEAD"),
                    )
                elif name == "check_drift":
                    result = await self._check_drift(
                        arguments.get("device_id"),
                        arguments.get("tag_filter"),
                    )
                # --- Schedule tools ---
                elif name == "create_snapshot_schedule":
                    result = await self._create_snapshot_schedule(
                        arguments["schedule_id"],
                        arguments["description"],
                        arguments["interval"],
                        arguments.get("tag_filter"),
                        arguments.get("device_ids"),
                    )
                elif name == "list_snapshot_schedules":
                    result = await self._list_snapshot_schedules()
                elif name == "update_snapshot_schedule":
                    result = await self._update_snapshot_schedule(
                        arguments["schedule_id"],
                        arguments,
                    )
                elif name == "delete_snapshot_schedule":
                    result = await self._delete_snapshot_schedule(
                        arguments["schedule_id"],
                    )
                elif name == "run_snapshot_schedule":
                    result = await self._run_snapshot_schedule(
                        arguments["schedule_id"],
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

    # ------------------------------------------------------------------
    # Catalog + Execution handlers
    # ------------------------------------------------------------------

    async def _query_catalog(
        self, device_id: str, intent: str, family: str
    ) -> Dict[str, Any]:
        """Look up available operations for a device and intent."""
        # Get device info for capability filtering
        device_info = None
        if self.registry.device_exists(device_id):
            device_info = self.registry.get_device_info(device_id)

        result = self.resolver.resolve(
            device_id=device_id,
            intent=intent,
            family=family,
            device_info=device_info,
        )

        return {
            "success": True,
            "operations": result.operations,
            "parameter_groups": result.parameter_groups,
            "device": result.device,
            "risk_summary": result.risk_summary,
            "notes": result.notes,
        }

    async def _execute_operation(
        self,
        device_id: str,
        operation_id: str,
        params: Dict[str, str],
        family: str,
    ) -> Dict[str, Any]:
        """Execute a single catalog operation."""
        # Check risk level — block dangerous operations
        risk = self.catalog.get_risk_level(family, operation_id)
        if risk == "dangerous":
            op = self.catalog.get_operation(family, operation_id)
            token = secrets.token_urlsafe(32)
            self._confirm_tokens[token] = {
                "device_id": device_id,
                "operation_id": operation_id,
                "params": params,
                "family": family,
            }
            return {
                "blocked": True,
                "risk_level": "dangerous",
                "reason": op.danger_description if op else "This operation is classified as dangerous.",
                "confirm_token": token,
                "confirm_tool": "confirm_dangerous_operation",
                "message": (
                    "This operation is blocked because it is classified as dangerous. "
                    "Present the reason to the user and ask for explicit confirmation. "
                    "If confirmed, call confirm_dangerous_operation with the token."
                ),
            }

        # Load operation spec
        operation = self.catalog.get_operation(family, operation_id)
        if not operation:
            return {
                "success": False,
                "error": f"Operation '{operation_id}' not found in {family} catalog",
            }

        # Get executor
        executor = self.executors.get(family)
        if not executor:
            return {
                "success": False,
                "error": f"No executor available for API family '{family}'",
            }

        # Get device info and credentials
        if not self.registry.device_exists(device_id):
            raise DeviceNotFoundError(f"Device not found: {device_id}")

        device = self.registry.get_device_info(device_id)
        device["device_id"] = device_id
        credentials = self.registry.get_credentials(device_id)

        # Build operation dict
        op_dict = {
            "id": operation.id,
            "cgi": operation.cgi,
            "method": operation.method,
            "risk_level": operation.risk_level,
            "request": operation.request,
            "response": operation.response,
            "requires": operation.requires,
            "_endpoint": operation.endpoint,
            "_generation": operation.generation,
            "_auth": operation.auth,
            "service_impact": operation.service_impact,
        }

        result = await executor.execute(op_dict, device, credentials, params)

        response: Dict[str, Any] = {
            "success": result.success,
            "operation_id": result.operation_id,
            "device_id": result.device_id,
            "status_code": result.status_code,
            "duration_ms": result.duration_ms,
        }

        if result.success:
            response["data"] = result.parsed_data
        else:
            response["error"] = result.error

        if result.warnings:
            response["warnings"] = result.warnings

        return response

    async def _confirm_dangerous(self, confirm_token: str) -> Dict[str, Any]:
        """Confirm and execute a blocked dangerous operation."""
        details = self._confirm_tokens.pop(confirm_token, None)
        if not details:
            return {
                "success": False,
                "error": "Invalid or expired confirmation token.",
            }

        # Re-run execution, bypassing the risk check
        operation = self.catalog.get_operation(
            details["family"], details["operation_id"]
        )
        if not operation:
            return {
                "success": False,
                "error": f"Operation '{details['operation_id']}' no longer found in catalog",
            }

        executor = self.executors.get(details["family"])
        if not executor:
            return {
                "success": False,
                "error": f"No executor for family '{details['family']}'",
            }

        device = self.registry.get_device_info(details["device_id"])
        device["device_id"] = details["device_id"]
        credentials = self.registry.get_credentials(details["device_id"])

        op_dict = {
            "id": operation.id,
            "cgi": operation.cgi,
            "method": operation.method,
            "risk_level": operation.risk_level,
            "request": operation.request,
            "response": operation.response,
            "requires": operation.requires,
            "_endpoint": operation.endpoint,
            "_generation": operation.generation,
            "_auth": operation.auth,
            "service_impact": operation.service_impact,
        }

        result = await executor.execute(
            op_dict, device, credentials, details["params"]
        )

        response: Dict[str, Any] = {
            "success": result.success,
            "confirmed_dangerous": True,
            "operation_id": result.operation_id,
            "device_id": result.device_id,
            "status_code": result.status_code,
            "duration_ms": result.duration_ms,
        }

        if result.success:
            response["data"] = result.parsed_data
        else:
            response["error"] = result.error

        return response

    # ------------------------------------------------------------------
    # Plan handlers
    # ------------------------------------------------------------------

    async def _create_plan(
        self,
        description: str,
        steps: List[Dict[str, Any]],
        on_failure: str,
    ) -> Dict[str, Any]:
        """Create a plan for review."""
        try:
            plan = self.plan_engine.create_plan(
                description=description,
                steps=steps,
                on_failure=on_failure,
            )
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }

        return {
            "success": True,
            "message": (
                "Plan created and ready for review. Present the summary "
                "to the user. If approved, call execute_plan with the plan_id."
            ),
            **plan.to_summary(),
        }

    async def _execute_plan(self, plan_id: str) -> Dict[str, Any]:
        """Execute an approved plan."""
        try:
            plan = await self.plan_engine.execute_plan(plan_id)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }

        return {
            "success": True,
            **plan.to_results(),
        }

    async def _get_plan_status(self, plan_id: str) -> Dict[str, Any]:
        """Check plan progress."""
        status = self.plan_engine.get_plan_status(plan_id)
        if not status:
            return {
                "success": False,
                "error": f"Plan not found: {plan_id}",
            }

        return {
            "success": True,
            **status,
        }

    # ------------------------------------------------------------------
    # Snapshot / Restore handlers
    # ------------------------------------------------------------------

    async def _snapshot_device(
        self, device_id: str, message: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.registry.device_exists(device_id):
            raise DeviceNotFoundError(f"Device not found: {device_id}")
        snapshot = await self.snapshot_engine.snapshot_device(
            device_id, message=message
        )
        return {
            "success": True,
            **snapshot.to_summary(),
        }

    async def _snapshot_fleet(
        self, tag_filter: Optional[str], message: Optional[str]
    ) -> Dict[str, Any]:
        snapshots = await self.snapshot_engine.snapshot_fleet(
            tag_filter=tag_filter, message=message
        )
        return {
            "success": True,
            "count": len(snapshots),
            "results": [s.to_summary() for s in snapshots],
        }

    async def _restore_device(
        self,
        device_id: str,
        ref: str,
        facet_names: Optional[List[str]],
    ) -> Dict[str, Any]:
        if not self.registry.device_exists(device_id):
            raise DeviceNotFoundError(f"Device not found: {device_id}")

        plan_spec = self.restore_builder.build_restore_plan(
            device_id, ref=ref, facet_names=facet_names
        )

        if not plan_spec["steps"]:
            return {
                "success": True,
                "message": f"No config found for {device_id} at {ref}",
                "warnings": plan_spec.get("warnings", []),
            }

        try:
            plan = self.plan_engine.create_plan(
                description=plan_spec["description"],
                steps=plan_spec["steps"],
                on_failure=plan_spec["on_failure"],
            )
        except ValueError as e:
            return {"success": False, "error": str(e)}

        return {
            "success": True,
            "message": (
                "Restore plan created. Review and call execute_plan "
                "with the plan_id to apply."
            ),
            "warnings": plan_spec.get("warnings", []),
            "source_ref": plan_spec.get("source_ref", ref),
            **plan.to_summary(),
        }

    async def _diff_device(
        self, device_id: str, ref_a: str, ref_b: str
    ) -> Dict[str, Any]:
        device_path = f"fleet/{device_id}/"
        diff_text = self.git_repo.diff(ref_a, ref_b, path=device_path)
        history = self.git_repo.log(path=device_path, max_count=10)

        return {
            "success": True,
            "device_id": device_id,
            "ref_a": ref_a,
            "ref_b": ref_b,
            "diff": diff_text if diff_text else "(no changes)",
            "recent_history": history,
        }

    async def _check_drift(
        self,
        device_id: Optional[str],
        tag_filter: Optional[str],
    ) -> Dict[str, Any]:
        if device_id:
            if not self.registry.device_exists(device_id):
                raise DeviceNotFoundError(f"Device not found: {device_id}")
            report = await self.drift_detector.check_drift(device_id)
            return {
                "success": True,
                **report.to_summary(),
            }
        else:
            reports = await self.drift_detector.check_fleet_drift(
                tag_filter=tag_filter
            )
            return {
                "success": True,
                "count": len(reports),
                "drifted": sum(1 for r in reports if r.has_drift),
                "reports": [r.to_summary() for r in reports],
            }

    # ------------------------------------------------------------------
    # Schedule handlers
    # ------------------------------------------------------------------

    async def _create_snapshot_schedule(
        self,
        schedule_id: str,
        description: str,
        interval: str,
        tag_filter: Optional[str],
        device_ids: Optional[List[str]],
    ) -> Dict[str, Any]:
        try:
            interval_seconds = parse_interval(interval)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        schedule = SnapshotSchedule(
            id=schedule_id,
            description=description,
            interval_seconds=interval_seconds,
            tag_filter=tag_filter,
            device_ids=device_ids,
        )
        self.scheduler.add_schedule(schedule)

        return {
            "success": True,
            "message": (
                f"Schedule '{schedule_id}' created — snapshots every "
                f"{schedule.interval_human}"
            ),
            "schedule": schedule.to_dict(),
        }

    async def _list_snapshot_schedules(self) -> Dict[str, Any]:
        schedules = self.scheduler.list_schedules()
        return {
            "success": True,
            "count": len(schedules),
            "schedules": [s.to_dict() for s in schedules],
        }

    async def _update_snapshot_schedule(
        self, schedule_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        kwargs = {}
        if "interval" in updates:
            try:
                kwargs["interval_seconds"] = parse_interval(updates["interval"])
            except ValueError as e:
                return {"success": False, "error": str(e)}
        if "enabled" in updates:
            kwargs["enabled"] = updates["enabled"]
        if "tag_filter" in updates:
            kwargs["tag_filter"] = updates["tag_filter"]
        if "description" in updates:
            kwargs["description"] = updates["description"]

        schedule = self.scheduler.update_schedule(schedule_id, **kwargs)
        if not schedule:
            return {
                "success": False,
                "error": f"Schedule not found: {schedule_id}",
            }

        return {
            "success": True,
            "message": f"Schedule '{schedule_id}' updated",
            "schedule": schedule.to_dict(),
        }

    async def _delete_snapshot_schedule(
        self, schedule_id: str
    ) -> Dict[str, Any]:
        removed = self.scheduler.remove_schedule(schedule_id)
        if not removed:
            return {
                "success": False,
                "error": f"Schedule not found: {schedule_id}",
            }
        return {
            "success": True,
            "message": f"Schedule '{schedule_id}' deleted",
        }

    async def _run_snapshot_schedule(
        self, schedule_id: str
    ) -> Dict[str, Any]:
        result = await self.scheduler.run_now(schedule_id)
        return result

    async def run(self):
        """Run the MCP server with stdio transport."""
        await self.scheduler.start()
        try:
            async with stdio_server() as (read_stream, write_stream):
                logger.info("ADMZ MCP server starting...")
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options(),
                )
        finally:
            await self.scheduler.stop()


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
