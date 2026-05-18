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

Discovery tools:
  - discover_network_devices: scan the local network for Axis devices
  - register_discovered_device: add a discovered device to the registry

Schedule tools:
  - create/update/delete/list/run_snapshot_schedule: manage recurring snapshots
"""

import asyncio
import json
import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional

CONFIRM_TOKEN_TTL_SECONDS = 300  # 5 minutes

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from admz import create_device_registry
from admz.device_registry import DeviceRegistry
from admz.api.capture import capture_store
from admz.api.confirm_store import PROTECTED_SETTING_KEYS
from admz.discovery.credential_probe import probe_credentials, ProbeStatus
from admz.fleet_settings import fleet_settings
from admz.catalog.loader import CatalogLoader
from admz.catalog.resolver import CatalogResolver
from admz.knowledge.loader import KnowledgeLoader
from admz.knowledge.resolver import KnowledgeResolver
from admz.capabilities.loader import CapabilitiesLoader
from admz.capabilities.resolver import CapabilitiesResolver
from admz.executor.vapix import VapixExecutor
from admz.firmware.downloader import (
    download_firmware as fetch_firmware,
    get_latest_version,
    list_cached_firmware,
    scan_firmware_files,
    import_firmware_files,
    default_download_dirs,
    _DEFAULT_FIRMWARE_DIR,
    FirmwareNotAvailableError,
    FirmwareDownloadError,
    FirmwareLoginRequiredError,
    normalize_model_for_ftp,
)
from admz.firmware.upgrade_path import (
    compute_upgrade_path,
    format_upgrade_path,
)
from admz.mcp.temp_credentials import TempCredentialManager
from admz.plans.engine import PlanEngine
from admz.snapshot.engine import SnapshotEngine
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.restore import RestoreBuilder
from admz.snapshot.drift import DriftDetector
from admz.snapshot.scheduler import SnapshotScheduler, SnapshotSchedule, parse_interval
from admz.discovery import discover_devices as run_network_discovery
from admz.exceptions import (
    ADMZError,
    DeviceNotFoundError,
    AccountNotFoundError,
    PermissionDeniedError,
    BackendError,
)

# Configure logging — respects ADMZ_LOG_LEVEL env var
from admz.logging_config import configure_logging
configure_logging()
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

        # Knowledge base
        self.knowledge_loader = KnowledgeLoader(catalog_path)
        self.knowledge_resolver = KnowledgeResolver(self.knowledge_loader)

        # Capabilities (per-model API support registry)
        self.capabilities_loader = CapabilitiesLoader(catalog_path)
        self.capabilities_resolver = CapabilitiesResolver(self.capabilities_loader)

        # Executors (one per API family)
        vapix_executor = VapixExecutor(
            retries=int(os.getenv("ADMZ_VAPIX_RETRIES", "1"))
        )
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

        # Temporary credential manager
        self.temp_creds = TempCredentialManager()

        # Register tool handlers
        self._register_handlers()

    def _is_get_credentials_enabled(self) -> bool:
        """Check if the get_credentials tool is enabled via fleet setting."""
        return fleet_settings.get("tool_get_credentials_enabled") == "true"

    def _register_handlers(self):
        """Register MCP tool handlers."""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available ADMZ tools."""
            tools = [
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
                        "The ADMZ web server must be running (default: http://localhost:8000). "
                        "Supports batch mode: pass device_ids to save the same credentials "
                        "to multiple devices with a single form submission."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID to store credentials for",
                            },
                            "device_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "List of device IDs for batch credential capture. "
                                    "One form submission saves the same credentials to all devices."
                                ),
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
                        "required": [],
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
                    name="query_knowledge",
                    description=(
                        "Look up product-specific knowledge and hints for a device. "
                        "Returns hints from the product hierarchy (product → series → "
                        "product line) about API support, limitations, and device-specific "
                        "workflows. Use this to understand device capabilities before "
                        "attempting operations."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID to query for",
                            },
                            "topic": {
                                "type": "string",
                                "description": (
                                    "Optional topic to filter by. "
                                    "e.g. 'vapix-support', 'poe', 'audio'"
                                ),
                                "default": "",
                            },
                        },
                        "required": ["device_id"],
                    },
                ),
                Tool(
                    name="check_api_support",
                    description=(
                        "Check whether a device supports a specific catalog API based on its "
                        "model + firmware. Looks up the pre-populated capabilities snapshot for "
                        "the device's model and reports whether the requested API is available "
                        "(and at what version). Returns supported=false with notes when the "
                        "model has no capabilities file, no snapshot for the firmware, or the "
                        "API isn't in the snapshot. Useful for filtering plan steps before "
                        "execution rather than discovering at execute time that a device doesn't "
                        "speak the API. Omit api_id to retrieve the full snapshot."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID to check",
                            },
                            "api_id": {
                                "type": "string",
                                "description": (
                                    "Catalog api_id (from an _api.yaml file) to check support "
                                    "for. Omit to return the full snapshot of supported APIs."
                                ),
                            },
                        },
                        "required": ["device_id"],
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
                        "Returns results for all steps including any errors. "
                        "Plans containing dangerous-risk steps require "
                        "confirm_dangerous=true; otherwise the call returns "
                        "{blocked: true, reason: 'plan_contains_dangerous_steps', "
                        "error: '...'} listing the offending steps so the user "
                        "can explicitly approve them."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "plan_id": {
                                "type": "string",
                                "description": "Plan ID from create_plan",
                            },
                            "confirm_dangerous": {
                                "type": "boolean",
                                "description": (
                                    "Set to true to confirm execution of a plan "
                                    "that contains any dangerous-risk step. The "
                                    "user must explicitly approve this — do not "
                                    "set without their consent."
                                ),
                                "default": False,
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
                # --- Credential probe tool ---
                Tool(
                    name="test_device_credentials",
                    description=(
                        "Test credentials against a device by probing its VAPIX "
                        "basicdeviceinfo endpoint. Tries no-auth (factory default), "
                        "legacy defaults (root/pass), and optionally user-supplied "
                        "credentials. Returns status without exposing passwords. "
                        "If store=true and credentials work, saves them to the registry."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "host": {
                                "type": "string",
                                "description": "IP/hostname to probe",
                            },
                            "device_id": {
                                "type": "string",
                                "description": (
                                    "Resolve host from registry if host not provided"
                                ),
                            },
                            "username": {
                                "type": "string",
                                "description": "Single username to try",
                            },
                            "password": {
                                "type": "string",
                                "description": "Single password to try",
                            },
                            "passwords": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "List of passwords to try with 'root' username (max 5)"
                                ),
                            },
                            "store": {
                                "type": "boolean",
                                "description": (
                                    "If true and credentials work, save to registry"
                                ),
                                "default": False,
                            },
                        },
                        "required": [],
                    },
                ),
                # --- Discovery tools ---
                Tool(
                    name="discover_network_devices",
                    description=(
                        "Scan the local network for Axis cameras and other devices "
                        "using mDNS, SSDP, ONVIF, ARP, HTTP/VAPIX, and SNMP. "
                        "Returns discovered devices with metadata. "
                        "Devices are NOT automatically registered — use "
                        "register_discovered_device to add a specific one."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "timeout": {
                                "type": "number",
                                "description": "Per-protocol timeout in seconds (default: 5.0)",
                                "default": 5.0,
                            },
                            "axis_only": {
                                "type": "boolean",
                                "description": "Only return Axis devices (default: false)",
                                "default": False,
                            },
                            "subnet": {
                                "type": "string",
                                "description": (
                                    "Subnet for ARP scan in CIDR "
                                    "(e.g. '192.168.1.0/24'). Auto-detected if omitted."
                                ),
                            },
                            "enable_ping": {
                                "type": "boolean",
                                "description": (
                                    "Enable ICMP ping sweep (slow). Default: false"
                                ),
                                "default": False,
                            },
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="register_discovered_device",
                    description=(
                        "Add a previously-discovered device to the registry. "
                        "Provide the discovery result fields. The device will "
                        "be created without credentials — use capture_credentials "
                        "to set them via the out-of-band URL flow."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Unique device ID to assign",
                            },
                            "ip_address": {
                                "type": "string",
                                "description": "Device IP address",
                            },
                            "mac_address": {
                                "type": "string",
                                "description": "MAC address (optional)",
                            },
                            "model": {
                                "type": "string",
                                "description": "Device model (optional)",
                            },
                            "hostname": {
                                "type": "string",
                                "description": "Hostname / friendly name",
                            },
                            "device_type": {
                                "type": "string",
                                "description": (
                                    "Device type from discovery "
                                    "(e.g. 'camera', 'speaker')"
                                ),
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Tags to apply",
                            },
                        },
                        "required": ["device_id", "ip_address"],
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
                # --- Fleet settings tools ---
                Tool(
                    name="get_fleet_settings",
                    description=(
                        "List all fleet-wide settings. Returns key-value pairs "
                        "for configuration that applies across all managed devices."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="set_fleet_setting",
                    description=(
                        "Set a fleet-wide setting. Known keys: "
                        "'default_password' — password used by provision_device "
                        "instead of generating a random one. "
                        "Set value to empty string to delete the setting. "
                        "For password settings, omit 'value' to generate a "
                        "secure capture URL where the user can enter the "
                        "password outside the chat (never touches LLM context)."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "Setting key (e.g. 'default_password')",
                            },
                            "value": {
                                "type": "string",
                                "description": (
                                    "Setting value. Empty string deletes the key. "
                                    "Omit for password keys to get a capture URL instead."
                                ),
                            },
                        },
                        "required": ["key"],
                    },
                ),
                # --- Provisioning tool ---
                Tool(
                    name="provision_device",
                    description=(
                        "Provision credentials on an Axis device. Probes the device first, "
                        "then takes the appropriate action based on its state: "
                        "(1) Factory-default: creates an admin user with a password. "
                        "(2) Legacy default password (root/pass): stores creds, suggests rotation. "
                        "(3) Unknown password: returns error — use capture_credentials instead. "
                        "Password priority: explicit param > fleet default_password setting > auto-generated. "
                        "Generated passwords are stored in the registry and NEVER returned in the response. "
                        "Use get_credentials to retrieve them afterward. "
                        "If only host is provided (no device_id), auto-registers the device using "
                        "its MAC address (= serial number) as the device_id."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Existing device ID in registry",
                            },
                            "host": {
                                "type": "string",
                                "description": (
                                    "IP/hostname to probe. If device doesn't exist, "
                                    "auto-registers using MAC as device_id."
                                ),
                            },
                            "username": {
                                "type": "string",
                                "description": "Username for the account (default: 'root')",
                                "default": "root",
                            },
                            "password": {
                                "type": "string",
                                "description": (
                                    "Specific password to set. If omitted, uses fleet "
                                    "default_password setting, or generates a secure one."
                                ),
                            },
                            "force_change": {
                                "type": "boolean",
                                "description": (
                                    "If true, change the password even if stored creds "
                                    "already work. Useful for rotating passwords."
                                ),
                                "default": False,
                            },
                        },
                        "required": [],
                    },
                ),
                # --- Firmware tool ---
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
                # --- Temporary credentials tools ---
                Tool(
                    name="create_temp_credentials",
                    description=(
                        "Create a short-lived user account on a device. Returns "
                        "temporary credentials the LLM can use directly — the real "
                        "admin password never leaves the server. The account is "
                        "automatically removed after the TTL expires."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Target device",
                            },
                            "ttl_seconds": {
                                "type": "integer",
                                "description": (
                                    "Lifetime in seconds (min 60, max 3600, default 300)"
                                ),
                                "default": 300,
                            },
                            "permissions": {
                                "type": "string",
                                "enum": ["viewer", "operator", "admin"],
                                "description": "Permission level for the temporary account",
                            },
                        },
                        "required": ["device_id", "permissions"],
                    },
                ),
                Tool(
                    name="cleanup_temp_credentials",
                    description=(
                        "Manage temporary device credentials. "
                        "No args → list all active temp credentials (metadata only, no passwords). "
                        "device_id only → remove all expired creds for that device. "
                        "device_id + username → remove a specific temp user immediately."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "Device ID to clean up",
                            },
                            "username": {
                                "type": "string",
                                "description": "Specific temp username to remove",
                            },
                        },
                        "required": [],
                    },
                ),
            ]

            # Filter out get_credentials when disabled
            if not self._is_get_credentials_enabled():
                tools = [t for t in tools if t.name != "get_credentials"]

            return tools

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
                    if not self._is_get_credentials_enabled():
                        result = {
                            "error": "ToolDisabled",
                            "message": (
                                "get_credentials is disabled. An admin can enable it "
                                "in the web UI at /confirm-settings. Consider using "
                                "create_temp_credentials instead."
                            ),
                        }
                    else:
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
                    result = await self._capture_credentials(arguments)
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
                elif name == "query_knowledge":
                    result = await self._query_knowledge(
                        arguments["device_id"],
                        arguments.get("topic", ""),
                    )
                elif name == "check_api_support":
                    result = await self._check_api_support(
                        arguments["device_id"],
                        arguments.get("api_id"),
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
                        arguments.get("confirm_dangerous", False),
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
                # --- Credential probe ---
                elif name == "test_device_credentials":
                    result = await self._test_credentials(arguments)
                # --- Discovery tools ---
                elif name == "discover_network_devices":
                    result = await self._discover_network_devices(arguments)
                elif name == "register_discovered_device":
                    result = await self._register_discovered_device(arguments)
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
                # --- Fleet settings ---
                elif name == "get_fleet_settings":
                    result = await self._get_fleet_settings()
                elif name == "set_fleet_setting":
                    result = await self._set_fleet_setting(
                        arguments["key"], arguments.get("value"),
                    )
                # --- Provisioning ---
                elif name == "provision_device":
                    result = await self._provision_device(arguments)
                # --- Firmware ---
                elif name == "download_firmware":
                    result = await self._download_firmware(arguments)
                elif name == "import_firmware":
                    result = await self._import_firmware(arguments)
                elif name == "list_cached_firmware":
                    result = await self._list_cached_firmware()
                # --- Temporary credentials ---
                elif name == "create_temp_credentials":
                    result = await self._create_temp_credentials(arguments)
                elif name == "cleanup_temp_credentials":
                    result = await self._cleanup_temp_credentials(arguments)
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
            except ADMZError as e:
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
        """Search devices by criteria. String fields use case-insensitive
        substring matching to be friendly to LLM-built queries."""
        all_devices = self.registry.list_devices()

        location_q = (filters.get("location") or "").lower()
        model_q = (filters.get("model") or "").lower()
        wanted_tags = filters.get("tags") or []

        matched = []
        for device in all_devices:
            if wanted_tags:
                device_tags = device.get("tags") or []
                if not any(tag in device_tags for tag in wanted_tags):
                    continue

            if location_q:
                if location_q not in (device.get("location") or "").lower():
                    continue

            if model_q:
                if model_q not in (device.get("model") or "").lower():
                    continue

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
        self.registry.update_device(device_id, updates)
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
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a credential capture session and return the URL.

        Supports single device (device_id) or batch (device_ids).
        """
        device_ids = arguments.get("device_ids") or []
        device_id = arguments.get("device_id", "")
        account_id = arguments.get("account_id", "default")
        account_type = arguments.get("account_type", "service")
        purpose = arguments.get("purpose", "")
        base_url = arguments.get("base_url", "http://localhost:8000")

        # Build the full list of target devices
        if device_ids:
            all_ids = device_ids
        elif device_id:
            all_ids = [device_id]
        else:
            return {
                "success": False,
                "error": "Either 'device_id' or 'device_ids' must be provided",
            }

        # Validate all devices exist
        missing = [did for did in all_ids if not self.registry.device_exists(did)]
        if missing:
            raise DeviceNotFoundError(
                f"Device(s) not found: {', '.join(missing)}"
            )

        primary_device_id = all_ids[0]

        session = capture_store.create_session(
            device_id=primary_device_id,
            account_id=account_id,
            account_type=account_type,
            purpose=purpose,
            device_ids=all_ids if len(all_ids) > 1 else None,
        )

        base_url = base_url.rstrip("/")
        url = f"{base_url}/capture/{session.token}"

        result: Dict[str, Any] = {
            "success": True,
            "message": (
                "Credential capture URL generated. "
                "Present this link to the user — credentials entered via "
                "this URL will NOT appear in the chat context."
            ),
            "url": url,
            "token": session.token,
            "device_id": primary_device_id,
            "account_id": account_id,
            "expires_in_seconds": int(session.ttl),
        }

        if len(all_ids) > 1:
            result["device_ids"] = all_ids
            result["device_count"] = len(all_ids)
            result["message"] = (
                f"Batch credential capture URL generated for {len(all_ids)} devices. "
                "Present this link to the user — one form submission saves "
                "credentials to all listed devices."
            )

        return result

    async def _check_capture_status(self, token: str) -> Dict[str, Any]:
        """Check whether a capture session has been completed."""
        # Try device credential session first
        session = capture_store.get_session(token)
        if session is not None:
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

        # Try fleet setting session
        fleet_session = capture_store.get_fleet_session(token)
        if fleet_session is not None:
            status = fleet_session.effective_status.value
            result = {
                "success": True,
                "status": status,
                "setting_key": fleet_session.setting_key,
                "type": "fleet_setting",
            }
            if status == "completed":
                result["message"] = (
                    f"Fleet setting '{fleet_session.setting_key}' "
                    "has been saved successfully."
                )
            elif status == "pending":
                result["message"] = "Waiting for the user to enter the value."
            else:
                result["message"] = "This capture session has expired."
            return result

        return {
            "success": True,
            "status": "expired_or_not_found",
            "message": "This capture session has expired or does not exist.",
        }

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

        # Also check knowledge base for relevant hints.
        # Always check "vapix-support" when querying a VAPIX catalog, since
        # some devices (e.g. switches) don't support VAPIX at all.
        # Also check the specific intent in case it matches a knowledge topic.
        seen_hint_ids = set()
        knowledge_notes = []
        topics_to_check = [intent]
        if family == "vapix":
            topics_to_check.append("vapix-support")
        for topic in topics_to_check:
            knowledge = self.knowledge_resolver.resolve(
                device_id=device_id,
                topic=topic,
                device_info=device_info,
            )
            for hint in knowledge.hints:
                if hint.id not in seen_hint_ids:
                    seen_hint_ids.add(hint.id)
                    knowledge_notes.append(
                        f"[{hint.source_level}] {hint.summary}: {hint.text.strip()}"
                    )

        return {
            "success": True,
            "operations": result.operations,
            "parameter_groups": result.parameter_groups,
            "device": result.device,
            "risk_summary": result.risk_summary,
            "notes": result.notes + knowledge_notes,
        }

    async def _query_knowledge(
        self, device_id: str, topic: str
    ) -> Dict[str, Any]:
        """Look up product-specific knowledge and hints for a device."""
        device_info = None
        if self.registry.device_exists(device_id):
            device_info = self.registry.get_device_info(device_id)

        result = self.knowledge_resolver.resolve(
            device_id=device_id,
            topic=topic,
            device_info=device_info,
        )

        hints = [
            {
                "id": h.id,
                "topic": h.topic,
                "summary": h.summary,
                "text": h.text,
                "tags": h.tags,
                "source_level": h.source_level,
                "source_file": h.source_file,
            }
            for h in result.hints
        ]

        return {
            "success": True,
            "device_id": result.device_id,
            "model": result.model,
            "hints": hints,
            "levels_loaded": result.levels_loaded,
            "notes": result.notes,
        }

    async def _check_api_support(
        self,
        device_id: str,
        api_id: Optional[str],
    ) -> Dict[str, Any]:
        """Check whether a device supports a specific catalog API based on its
        model + firmware. When api_id is omitted, returns the full snapshot of
        supported APIs for the device."""
        device_info = None
        if self.registry.device_exists(device_id):
            device_info = self.registry.get_device_info(device_id)
        else:
            return {
                "success": False,
                "error": f"Device '{device_id}' not found in registry",
            }

        if api_id:
            result = self.capabilities_resolver.check_api_support(
                device_id=device_id,
                catalog_api_id=api_id,
                device_info=device_info,
            )
        else:
            result = self.capabilities_resolver.get_all_apis(
                device_id=device_id,
                device_info=device_info,
            )

        snapshot_summary: Optional[Dict[str, Any]] = None
        if result.snapshot is not None:
            snapshot_summary = {
                "firmware": result.snapshot.firmware,
                "discovered": result.snapshot.discovered,
                "api_count": result.snapshot.api_count,
            }
            if not api_id:
                snapshot_summary["apis"] = result.snapshot.apis

        return {
            "success": True,
            "device_id": result.device_id,
            "model": result.model,
            "firmware": result.firmware,
            "api_id": api_id,
            "supported": result.supported,
            "api_version": result.api_version,
            "snapshot": snapshot_summary,
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
            self._purge_expired_confirm_tokens()
            self._confirm_tokens[token] = {
                "device_id": device_id,
                "operation_id": operation_id,
                "params": params,
                "family": family,
                "issued_at": time.time(),
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
        try:
            credentials = self.registry.get_credentials(device_id)
        except AccountNotFoundError:
            credentials = {"username": "", "password": ""}

        op_dict = operation.to_executor_dict()

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

    def _purge_expired_confirm_tokens(self) -> None:
        now = time.time()
        expired = [
            tok
            for tok, details in self._confirm_tokens.items()
            if now - details.get("issued_at", 0) > CONFIRM_TOKEN_TTL_SECONDS
        ]
        for tok in expired:
            self._confirm_tokens.pop(tok, None)

    async def _confirm_dangerous(self, confirm_token: str) -> Dict[str, Any]:
        """Confirm and execute a blocked dangerous operation."""
        self._purge_expired_confirm_tokens()
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
        try:
            credentials = self.registry.get_credentials(details["device_id"])
        except AccountNotFoundError:
            credentials = {"username": "", "password": ""}

        op_dict = operation.to_executor_dict()

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

    async def _execute_plan(
        self, plan_id: str, confirm_dangerous: bool = False
    ) -> Dict[str, Any]:
        """Execute an approved plan. Plans with dangerous steps require
        ``confirm_dangerous=True`` — see PlanEngine.execute_plan for the
        rationale."""
        try:
            plan = await self.plan_engine.execute_plan(
                plan_id, confirm_dangerous=confirm_dangerous
            )
        except PermissionError as e:
            # Plan-level dangerous-step gate refused; surface a structured
            # envelope analogous to execute_operation's blocked response.
            return {
                "success": False,
                "blocked": True,
                "reason": "plan_contains_dangerous_steps",
                "error": str(e),
                "retry_with": {"confirm_dangerous": True},
            }
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
    # Credential probe handler
    # ------------------------------------------------------------------

    async def _test_credentials(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Probe a device with no-auth, legacy defaults, and/or user creds."""
        host = arguments.get("host")
        device_id = arguments.get("device_id")

        if not host:
            if not device_id:
                return {
                    "success": False,
                    "error": "Either 'host' or 'device_id' must be provided",
                }
            if not self.registry.device_exists(device_id):
                raise DeviceNotFoundError(f"Device not found: {device_id}")
            device_info = self.registry.get_device_info(device_id)
            host = device_info.get("host") or device_info.get("ip_address")
            if not host:
                return {
                    "success": False,
                    "error": f"Device '{device_id}' has no host/IP address",
                }

        credentials_list = []
        username = arguments.get("username")
        password = arguments.get("password")
        if username and password:
            credentials_list.append((username, password))

        passwords = arguments.get("passwords") or []
        for pw in passwords[:5]:
            credentials_list.append(("root", pw))

        result = await probe_credentials(
            host,
            credentials_list=credentials_list if credentials_list else None,
        )

        response = result.to_dict(include_credentials=False)
        response["success"] = True

        store = arguments.get("store", False)
        if store and device_id and result.status in (
            ProbeStatus.FACTORY_DEFAULT,
            ProbeStatus.AUTHENTICATED,
        ):
            if not self.registry.device_exists(device_id):
                response["store_error"] = f"Device '{device_id}' not found in registry"
            else:
                account_data = {
                    "username": result.username or "root",
                    "password": result.password or "",
                    "account_type": "service",
                    "purpose": "Auto-stored by credential probe",
                }
                try:
                    if self.registry.account_exists(device_id, "default"):
                        self.registry.remove_account(device_id, "default")
                    self.registry.add_account(device_id, "default", account_data)
                    response["stored"] = True
                    response["stored_device_id"] = device_id
                    response["stored_account_id"] = "default"
                except Exception as e:
                    response["store_error"] = str(e)

                # Store detected auth info in device profile
                auth_updates: Dict[str, Any] = {}
                if result.auth_method:
                    auth_updates["auth_method"] = result.auth_method
                if result.auth:
                    auth_updates["auth"] = result.auth
                if auth_updates:
                    try:
                        self.registry.update_device_info(
                            device_id, auth_updates
                        )
                    except Exception:
                        pass

        return response

    # ------------------------------------------------------------------
    # Discovery handlers
    # ------------------------------------------------------------------

    async def _discover_network_devices(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        devices = await run_network_discovery(
            timeout=arguments.get("timeout", 5.0),
            axis_only=arguments.get("axis_only", False),
            subnet=arguments.get("subnet"),
            enable_ping=arguments.get("enable_ping", False),
        )
        return {
            "success": True,
            "count": len(devices),
            "devices": [
                {
                    "ip_address": d.ip_address,
                    "mac_address": d.mac_address,
                    "hostname": d.hostname,
                    "model": d.model,
                    "serial_number": d.serial_number,
                    "firmware_version": d.firmware_version,
                    "manufacturer": d.manufacturer,
                    "friendly_name": d.friendly_name,
                    "device_type": d.device_type.value,
                    "is_axis": d.is_axis,
                    "vapix_available": d.vapix_available,
                    "factory_default": d.factory_default,
                    "discovered_by": [p.value for p in d.discovered_by],
                }
                for d in devices
            ],
        }

    async def _register_discovered_device(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        device_id = arguments["device_id"]
        device_info = {
            "host": arguments["ip_address"],
            "ip_address": arguments["ip_address"],
            "mac_address": arguments.get("mac_address", ""),
            "model": arguments.get("model", ""),
            "hostname": arguments.get("hostname", ""),
            "nickname": arguments.get("hostname", ""),
            "device_type": arguments.get("device_type", "unknown"),
            "tags": arguments.get("tags", []),
        }
        self.registry.add_device(device_id, device_info)
        return {
            "success": True,
            "message": (
                f"Device '{device_id}' registered. Use capture_credentials "
                "to set credentials via the out-of-band URL flow."
            ),
            "device_id": device_id,
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

    # ------------------------------------------------------------------
    # Fleet settings handlers
    # ------------------------------------------------------------------

    async def _get_fleet_settings(self) -> Dict[str, Any]:
        from admz.fleet_settings import mask_settings_for_display

        settings = fleet_settings.list_all()
        return {
            "success": True,
            "count": len(settings),
            "settings": mask_settings_for_display(settings),
        }

    async def _set_fleet_setting(
        self, key: str, value: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set, delete, or capture a fleet-wide setting."""
        # Block writes to protected keys from MCP
        if key in PROTECTED_SETTING_KEYS:
            return {
                "success": False,
                "error": (
                    f"Setting '{key}' is protected and can only be changed "
                    "via the web UI at /confirm-settings."
                ),
            }

        # No value provided for a password key → generate capture URL
        if value is None and "password" in key.lower():
            base_url = os.getenv("ADMZ_BASE_URL", "http://localhost:8000")
            session = capture_store.create_fleet_session(
                setting_key=key,
                label="Fleet default password for device provisioning",
            )
            url = f"{base_url}/capture/fleet/{session.token}"
            return {
                "success": True,
                "action": "capture",
                "key": key,
                "capture_url": url,
                "token": session.token,
                "expires_in_seconds": int(session.ttl),
                "message": (
                    "Open the URL to enter the password securely. "
                    "The password never appears in the chat."
                ),
            }

        if value is None:
            return {
                "success": False,
                "error": "Value is required for non-password settings.",
            }

        if not value:
            deleted = fleet_settings.delete(key)
            return {
                "success": True,
                "action": "deleted" if deleted else "not_found",
                "key": key,
            }

        fleet_settings.set(key, value)
        display_value = value
        if "password" in key.lower():
            display_value = f"{'*' * min(len(value), 8)} ({len(value)} chars)"
        return {
            "success": True,
            "action": "set",
            "key": key,
            "value": display_value,
        }

    # ------------------------------------------------------------------
    # Provisioning handler
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_device_password(length: int = 24) -> str:
        while True:
            pw = secrets.token_urlsafe(length)[:length]
            if (any(c.isupper() for c in pw) and
                    any(c.islower() for c in pw) and
                    any(c.isdigit() for c in pw)):
                return pw

    @staticmethod
    def _serial_to_mac(serial: str) -> str:
        s = serial.upper().replace(":", "").replace("-", "")
        if len(s) != 12:
            return serial
        return ":".join(s[i:i + 2] for i in range(0, 12, 2))

    async def _execute_on_host(
        self,
        host: str,
        operation_id: str,
        params: Dict[str, str],
        *,
        credentials: Optional[Dict[str, str]] = None,
        auth_method: str = "digest",
        auth: Optional[Dict[str, str]] = None,
        family: str = "vapix",
    ) -> tuple:
        operation = self.catalog.get_operation(family, operation_id)
        if not operation:
            return False, f"Operation '{operation_id}' not found in {family} catalog"

        executor = self.executors.get(family)
        if not executor:
            return False, f"No executor for family '{family}'"

        device: Dict[str, Any] = {
            "host": host,
            "device_id": f"_host_{host}",
            "auth_method": auth_method,
            "port": 80,
        }
        # Use structured auth dict if provided, otherwise build from auth_method
        if auth:
            device["auth"] = auth
        else:
            device["auth"] = {"http": auth_method, "https": auth_method, "scheme": "http"}

        creds = credentials or {"username": "", "password": ""}

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
            "base_path": operation.base_path,
            "path": operation.path,
        }

        result = await executor.execute(op_dict, device, creds, params)
        if result.success:
            return True, None
        return False, result.error or f"HTTP {result.status_code}"

    def _store_provisioned_creds(
        self, device_id: str, username: str, password: str,
    ) -> None:
        account_data = {
            "username": username,
            "password": password,
            "account_type": "admin",
            "purpose": "Provisioned by provision_device",
        }
        if self.registry.account_exists(device_id, "default"):
            self.registry.remove_account(device_id, "default")
        self.registry.add_account(device_id, "default", account_data)

    async def _provision_device(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        device_id = arguments.get("device_id")
        host = arguments.get("host")
        username = arguments.get("username", "root")
        user_password = arguments.get("password")
        force_change = arguments.get("force_change", False)

        if not host and not device_id:
            return {
                "success": False,
                "error": "Either 'host' or 'device_id' must be provided",
            }

        if device_id and not host:
            if not self.registry.device_exists(device_id):
                raise DeviceNotFoundError(f"Device not found: {device_id}")
            device_info = self.registry.get_device_info(device_id)
            host = device_info.get("host") or device_info.get("ip_address")
            if not host:
                return {
                    "success": False,
                    "error": f"Device '{device_id}' has no host/IP address",
                }

        probe = await probe_credentials(host)

        if probe.status == ProbeStatus.UNREACHABLE:
            return {
                "success": False,
                "status": "unreachable",
                "host": host,
                "detail": probe.detail,
            }

        auto_registered = False
        if not device_id:
            serial = (probe.device_info or {}).get("serial_number")
            if serial and len(serial.replace(":", "").replace("-", "")) == 12:
                device_id = self._serial_to_mac(serial)
            else:
                return {
                    "success": False,
                    "error": (
                        "Could not determine device serial/MAC from probe. "
                        "Register the device manually and use device_id instead."
                    ),
                    "host": host,
                    "device_info": probe.device_info,
                }

            if not self.registry.device_exists(device_id):
                reg_info = {
                    "host": host,
                    "ip_address": host,
                    "mac_address": device_id,
                    "serial_number": serial,
                    "model": (probe.device_info or {}).get("model", ""),
                    "firmware_version": (probe.device_info or {}).get(
                        "firmware_version", ""
                    ),
                    "nickname": (probe.device_info or {}).get(
                        "friendly_name", ""
                    ),
                    "manufacturer": "Axis Communications",
                    "tags": ["axis", "auto-registered"],
                }
                self.registry.add_device(device_id, reg_info)
                auto_registered = True

        password_source = "provided"
        if user_password:
            new_password = user_password
        else:
            fleet_default = fleet_settings.get("default_password")
            if fleet_default:
                new_password = fleet_default
                password_source = "fleet_default"
            else:
                new_password = self._generate_device_password()
                password_source = "generated"

        if probe.status == ProbeStatus.FACTORY_DEFAULT:
            ok, error = await self._execute_on_host(
                host, "pwdgrp.cgi:add-user",
                params={
                    "username": username,
                    "password": new_password,
                    "group": "root",
                    "secondary_groups": "admin:operator:viewer:ptz",
                },
                auth_method="none",
            )
            if not ok:
                return {
                    "success": False,
                    "status": "vapix_error",
                    "device_id": device_id,
                    "action_taken": "create_user_failed",
                    "error": error,
                }

            self._store_provisioned_creds(device_id, username, new_password)
            # Device now requires auth — store per-protocol info from probe
            auth_updates: Dict[str, Any] = {"auth_method": "digest"}
            if probe.auth:
                auth_updates["auth"] = probe.auth
            self.registry.update_device_info(device_id, auth_updates)

            return {
                "success": True,
                "status": "provisioned",
                "action_taken": "created_user",
                "device_id": device_id,
                "host": host,
                "username": username,
                "password_source": password_source,
                "auto_registered": auto_registered,
                "detail": (
                    f"Created admin user '{username}' on factory-default "
                    f"device. Credentials stored. Use get_credentials to "
                    f"retrieve the password."
                ),
            }

        if probe.status == ProbeStatus.AUTHENTICATED:
            # Store detected auth info from probe
            auth_updates_auth: Dict[str, Any] = {}
            if probe.auth_method:
                auth_updates_auth["auth_method"] = probe.auth_method
            if probe.auth:
                auth_updates_auth["auth"] = probe.auth
            if auth_updates_auth:
                self.registry.update_device_info(
                    device_id, auth_updates_auth
                )

            if not force_change:
                self._store_provisioned_creds(
                    device_id, probe.username, probe.password
                )
                return {
                    "success": True,
                    "status": "already_configured",
                    "action_taken": "stored_existing_credentials",
                    "device_id": device_id,
                    "host": host,
                    "username": probe.username,
                    "auto_registered": auto_registered,
                    "detail": (
                        f"Device authenticated with legacy defaults as "
                        f"'{probe.username}'. Credentials stored. Consider "
                        f"using force_change=true to rotate the password."
                    ),
                }

            ok, error = await self._execute_on_host(
                host, "pwdgrp.cgi:update-user",
                params={
                    "username": username,
                    "password": new_password,
                },
                credentials={
                    "username": probe.username,
                    "password": probe.password,
                },
                auth_method=probe.auth_method or "digest",
                auth=probe.auth,
            )
            if not ok:
                self._store_provisioned_creds(
                    device_id, probe.username, probe.password
                )
                return {
                    "success": False,
                    "status": "vapix_error",
                    "device_id": device_id,
                    "action_taken": "password_change_failed",
                    "error": error,
                    "detail": (
                        "Password change failed, but old credentials "
                        "were stored successfully."
                    ),
                }

            self._store_provisioned_creds(device_id, username, new_password)

            return {
                "success": True,
                "status": "provisioned",
                "action_taken": "changed_password",
                "device_id": device_id,
                "host": host,
                "username": username,
                "password_source": password_source,
                "auto_registered": auto_registered,
                "detail": (
                    f"Changed password for '{username}'. New credentials "
                    f"stored. Use get_credentials to retrieve the password."
                ),
            }

        if probe.status == ProbeStatus.AUTH_FAILED:
            if probe.auth_method:
                self.registry.update_device_info(
                    device_id, {"auth_method": probe.auth_method}
                )
            return {
                "success": False,
                "status": "auth_failed",
                "device_id": device_id,
                "host": host,
                "auto_registered": auto_registered,
                "detail": (
                    "Cannot authenticate with any known credentials. "
                    "Use capture_credentials to provide the password "
                    "manually, or use test_device_credentials with "
                    "specific passwords to probe further."
                ),
            }

        return {
            "success": False,
            "status": probe.status.value,
            "device_id": device_id,
            "detail": probe.detail,
        }

    # ------------------------------------------------------------------
    # Firmware handler
    # ------------------------------------------------------------------

    async def _download_firmware(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Download firmware or check latest version with upgrade path info."""
        model = arguments.get("model")
        device_id = arguments.get("device_id")
        version = arguments.get("version")
        check_only = arguments.get("check_only", False)

        current_version = None

        # Resolve model and current version from device registry
        if device_id and not model:
            if not self.registry.device_exists(device_id):
                raise DeviceNotFoundError(f"Device not found: {device_id}")
            device_info = self.registry.get_device_info(device_id)
            model = device_info.get("model")
            current_version = device_info.get("firmware_version")
            if not model:
                return {
                    "success": False,
                    "error": (
                        f"Device '{device_id}' has no model info. "
                        "Provide 'model' parameter directly."
                    ),
                }
        elif device_id:
            # model provided explicitly, but still get current version
            if self.registry.device_exists(device_id):
                device_info = self.registry.get_device_info(device_id)
                current_version = device_info.get("firmware_version")

        if not model:
            return {
                "success": False,
                "error": "Either 'model' or 'device_id' must be provided.",
            }

        # Check latest version on FTP
        latest = await get_latest_version(model)
        target_version = version or latest

        # Build upgrade path info
        upgrade_info: Dict[str, Any] = {}
        if current_version and target_version:
            intermediates = compute_upgrade_path(current_version, target_version)
            path_display = format_upgrade_path(
                current_version, target_version, intermediates
            )
            full_path = intermediates + [target_version]
            upgrade_info = {
                "current_version": current_version,
                "target_version": target_version,
                "upgrade_path": full_path,
                "direct_upgrade": len(intermediates) == 0,
                "upgrade_path_display": path_display,
            }
            if intermediates:
                upgrade_info["message"] = (
                    f"This upgrade requires {len(intermediates)} intermediate "
                    f"LTS step(s): {path_display}"
                )
            else:
                upgrade_info["message"] = (
                    f"Direct upgrade: {path_display}"
                )

        if check_only:
            result: Dict[str, Any] = {
                "success": True,
                "check_only": True,
                "model": normalize_model_for_ftp(model),
                "latest_version": latest,
            }
            if not latest:
                result["warning"] = (
                    f"Model '{model}' not found on public FTP. "
                    "Download manually from https://www.axis.com/support/device-software"
                )
            if upgrade_info:
                result["upgrade"] = upgrade_info
            return result

        # Download firmware
        try:
            fw = await fetch_firmware(model=model, version=version)
        except FirmwareLoginRequiredError:
            result = {
                "success": False,
                "error": "login_required",
                "model": normalize_model_for_ftp(model),
                "version": target_version,
                "message": (
                    f"Firmware download for {normalize_model_for_ftp(model)} "
                    f"requires an Axis account. Download the firmware "
                    f"manually from https://www.axis.com/support/device-software "
                    f"and provide the local file path for the upgrade."
                ),
            }
            if upgrade_info:
                result["upgrade"] = upgrade_info
            return result
        except FirmwareNotAvailableError as e:
            result = {
                "success": False,
                "error": str(e),
                "model": normalize_model_for_ftp(model),
                "suggestion": (
                    "Download manually from "
                    "https://www.axis.com/support/device-software"
                ),
            }
            if upgrade_info:
                result["upgrade"] = upgrade_info
            return result
        except FirmwareDownloadError as e:
            return {
                "success": False,
                "error": str(e),
                "model": normalize_model_for_ftp(model),
            }

        result = {
            "success": True,
            "model": fw.model,
            "version": fw.version,
            "file_path": fw.file_path,
            "file_size": fw.file_size,
            "file_size_mb": round(fw.file_size / (1024 * 1024), 1)
            if fw.file_size
            else None,
            "url": fw.url,
            "already_cached": fw.already_cached,
        }
        if upgrade_info:
            result["upgrade"] = upgrade_info
        return result

    async def _import_firmware(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Scan a directory for firmware files and optionally import them."""
        directory = arguments.get("directory")
        scan_only = arguments.get("scan_only", False)
        device_id = arguments.get("device_id")

        # Resolve directory — default to ~/Downloads
        if not directory:
            download_dirs = default_download_dirs()
            if not download_dirs:
                return {
                    "success": False,
                    "error": "No Downloads directory found. Provide 'directory' parameter.",
                }
            directory = download_dirs[0]

        # If device_id provided, resolve model for filtering
        filter_model = None
        if device_id:
            if not self.registry.device_exists(device_id):
                raise DeviceNotFoundError(f"Device not found: {device_id}")
            device_info = self.registry.get_device_info(device_id)
            model = device_info.get("model")
            if model:
                filter_model = normalize_model_for_ftp(model)

        if scan_only:
            scanned = scan_firmware_files(directory)
            if filter_model:
                scanned = [s for s in scanned if s.model == filter_model]
            return {
                "success": True,
                "scan_only": True,
                "directory": directory,
                "files_found": len(scanned),
                "files": [
                    {
                        "filename": s.filename,
                        "file_path": s.file_path,
                        "file_size": s.file_size,
                        "file_size_mb": round(s.file_size / (1024 * 1024), 1),
                        "model": s.model,
                        "version": s.version,
                        "already_cached": s.already_cached,
                    }
                    for s in scanned
                ],
            }

        # Import mode
        result = await import_firmware_files(directory)

        # Filter results if device_id was provided
        if filter_model:
            result.imported = [
                (src, dst) for src, dst in result.imported
                if filter_model in src
            ]
            result.skipped = [
                (src, reason) for src, reason in result.skipped
                if filter_model in src
            ]
            result.errors = [
                (src, err) for src, err in result.errors
                if filter_model in src
            ]

        return {
            "success": True,
            "directory": directory,
            "imported": [
                {"source": src, "cached_at": dst}
                for src, dst in result.imported
            ],
            "skipped": [
                {"source": src, "reason": reason}
                for src, reason in result.skipped
            ],
            "errors": [
                {"source": src, "error": err}
                for src, err in result.errors
            ],
            "summary": (
                f"Imported {len(result.imported)}, "
                f"skipped {len(result.skipped)}, "
                f"errors {len(result.errors)}"
            ),
        }

    async def _list_cached_firmware(self) -> Dict[str, Any]:
        """List all firmware files in the local cache."""
        cached = list_cached_firmware()
        return {
            "success": True,
            "firmware_dir": _DEFAULT_FIRMWARE_DIR,
            "total_files": len(cached),
            "files": cached,
        }

    # ------------------------------------------------------------------
    # Temporary credentials handlers
    # ------------------------------------------------------------------

    # Permissions → VAPIX group mapping
    _PERM_MAP = {
        "admin":    {"group": "root",  "sgrp": "admin:operator:viewer:ptz"},
        "operator": {"group": "users", "sgrp": "operator:viewer:ptz"},
        "viewer":   {"group": "users", "sgrp": "viewer"},
    }

    async def _create_temp_credentials(
        self, arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a short-lived user account on a device."""
        device_id = arguments["device_id"]
        ttl = arguments.get("ttl_seconds", 300)
        permissions = arguments["permissions"]

        # Validate TTL
        ttl = max(60, min(3600, int(ttl)))

        # Validate permissions
        if permissions not in self._PERM_MAP:
            return {
                "success": False,
                "error": f"Invalid permissions '{permissions}'. Use: viewer, operator, admin",
            }

        # Per-device limit
        active_count = self.temp_creds.count_active_for_device(device_id)
        if active_count >= self.temp_creds.max_per_device:
            return {
                "success": False,
                "error": (
                    f"Device '{device_id}' already has {active_count} active temp "
                    f"credentials (max {self.temp_creds.max_per_device}). "
                    "Use cleanup_temp_credentials to remove expired ones first."
                ),
            }

        # Get admin credentials from registry (never returned to LLM)
        if not self.registry.device_exists(device_id):
            raise DeviceNotFoundError(f"Device not found: {device_id}")

        device_info = self.registry.get_device_info(device_id)
        host = device_info.get("host") or device_info.get("ip_address")
        if not host:
            return {
                "success": False,
                "error": f"Device '{device_id}' has no host/IP configured.",
            }

        try:
            admin_creds = self.registry.get_credentials(device_id, "default")
        except (AccountNotFoundError, Exception):
            return {
                "success": False,
                "error": (
                    f"No admin credentials stored for '{device_id}'. "
                    "Use capture_credentials or provision_device first."
                ),
            }

        # Generate temp username and password
        username = self.temp_creds.generate_username()
        password = self.temp_creds.generate_password()
        perm = self._PERM_MAP[permissions]

        # Create user on device via pwdgrp.cgi
        params = {
            "user": username,
            "pwd": password,
            "grp": perm["group"],
            "sgrp": perm["sgrp"],
            "comment": "ADMZ temp account",
        }

        success, error = await self._execute_on_host(
            host,
            "pwdgrp.cgi:add-user",
            params,
            credentials=admin_creds,
        )

        if not success:
            return {
                "success": False,
                "error": f"Failed to create temp user on device: {error}",
            }

        # Track in manager
        from admz.mcp.temp_credentials import TempCredential
        cred = TempCredential(
            device_id=device_id,
            username=username,
            password=password,
            group=perm["group"],
            ttl_seconds=ttl,
        )
        self.temp_creds.register(cred)

        return {
            "success": True,
            "device_id": device_id,
            "username": username,
            "password": password,
            "permissions": permissions,
            "ttl_seconds": ttl,
            "expires_at": cred.expires_at_iso,
            "message": (
                f"Temporary {permissions} account created. "
                f"It will be automatically removed after {ttl} seconds."
            ),
        }

    async def _cleanup_temp_credentials(
        self, arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """List or remove temporary credentials."""
        device_id = arguments.get("device_id")
        username = arguments.get("username")

        # No args → list all active temp credentials
        if not device_id and not username:
            active = self.temp_creds.list_active()
            return {
                "success": True,
                "action": "list",
                "count": len(active),
                "credentials": active,
            }

        # device_id + username → remove specific temp user immediately
        if device_id and username:
            cred = self.temp_creds.remove(device_id, username)
            if not cred:
                return {
                    "success": False,
                    "error": f"No tracked temp credential for {username}@{device_id}",
                }

            # Remove from device
            removed = await self._remove_temp_user(cred)
            return {
                "success": True,
                "action": "removed",
                "device_id": device_id,
                "username": username,
                "device_cleanup": "success" if removed else "failed",
            }

        # device_id only → remove all expired for that device
        if device_id:
            expired = [
                c for c in self.temp_creds.get_expired()
                if c.device_id == device_id
            ]
            results = []
            for cred in expired:
                self.temp_creds.remove(cred.device_id, cred.username)
                removed = await self._remove_temp_user(cred)
                results.append({
                    "username": cred.username,
                    "device_cleanup": "success" if removed else "failed",
                })
            return {
                "success": True,
                "action": "cleanup",
                "device_id": device_id,
                "removed_count": len(results),
                "results": results,
            }

        return {"success": False, "error": "Invalid argument combination."}

    async def _remove_temp_user(self, cred) -> bool:
        """Remove a temp user from the device. Returns True on success."""
        try:
            device_info = self.registry.get_device_info(cred.device_id)
            host = device_info.get("host") or device_info.get("ip_address")
            if not host:
                return False

            admin_creds = self.registry.get_credentials(cred.device_id, "default")
            success, _ = await self._execute_on_host(
                host,
                "pwdgrp.cgi:remove-user",
                {"user": cred.username},
                credentials=admin_creds,
            )
            return success
        except Exception as e:
            logger.warning(
                "Failed to remove temp user %s from %s: %s",
                cred.username, cred.device_id, e,
            )
            return False

    async def _temp_credential_cleanup_loop(self):
        """Background loop that removes expired temp credentials from devices."""
        try:
            while True:
                await asyncio.sleep(30)
                expired = self.temp_creds.get_expired()
                for cred in expired:
                    if not cred.should_retry_cleanup:
                        # Give up after max attempts
                        logger.warning(
                            "Giving up on temp user %s@%s after %d cleanup attempts",
                            cred.username, cred.device_id, cred.cleanup_attempts,
                        )
                        self.temp_creds.remove(cred.device_id, cred.username)
                        continue

                    removed = await self._remove_temp_user(cred)
                    if removed:
                        self.temp_creds.remove(cred.device_id, cred.username)
                        logger.info(
                            "Cleaned up temp user %s from %s",
                            cred.username, cred.device_id,
                        )
                    else:
                        cred.cleanup_attempts += 1
        except asyncio.CancelledError:
            # Server shutting down — attempt final cleanup of all active creds
            logger.info("Shutting down: cleaning up all temp credentials...")
            for cred in self.temp_creds.get_all():
                await self._remove_temp_user(cred)

    async def run(self):
        """Run the MCP server with stdio transport."""
        await self.scheduler.start()
        cleanup_task = asyncio.create_task(self._temp_credential_cleanup_loop())
        try:
            async with stdio_server() as (read_stream, write_stream):
                logger.info("ADMZ MCP server starting...")
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options(),
                )
        finally:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
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
