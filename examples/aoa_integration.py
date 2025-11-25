#!/usr/bin/env python3
"""
Example: Integrating ADMZ (Axis Device Manager) with AOA Agent (MCP Server).

This example shows how to use ADMZ in an MCP server for Axis Object Analytics.
The key benefit: credentials are never exposed to the LLM, only device IDs.

Prerequisites:
- Vault server with devices configured
- aoa-config package installed (optional, for demonstration)
"""

import os
from typing import Dict, Any
from admz import create_device_registry
from admz.exceptions import DeviceNotFoundError, AccountNotFoundError


# Initialize the device registry once at module level
# This registry will be used by all MCP tools
registry = None


def initialize_registry():
    """Initialize the device registry (call this at server startup)."""
    global registry
    if registry is None:
        registry = create_device_registry()
        print("✓ Device registry initialized")


def get_device_credentials(device_id: str, account_id: str = "aoa-agent") -> Dict[str, Any]:
    """
    Get device credentials by ID.

    This is a helper function that your MCP tools will use internally.
    The LLM never sees the credentials, only the device ID.

    Args:
        device_id: Device identifier (e.g., 'front-door')
        account_id: Account to use (defaults to 'aoa-agent')

    Returns:
        Dictionary with host, username, password

    Raises:
        DeviceNotFoundError: If device doesn't exist
        AccountNotFoundError: If account doesn't exist
    """
    if registry is None:
        initialize_registry()

    return registry.get_credentials(device_id, account_id)


# ============================================================================
# MCP Tool Examples (Pseudo-code - adapt to your MCP framework)
# ============================================================================

def mcp_tool_list_scenarios(device_id: str) -> Dict[str, Any]:
    """
    MCP Tool: List AOA scenarios for a device.

    The LLM only sees device_id parameter, never credentials!

    Args:
        device_id: Device identifier (exposed to LLM)

    Returns:
        List of scenarios
    """
    try:
        # Get credentials server-side (NOT exposed to LLM)
        creds = get_device_credentials(device_id)

        # Use credentials to connect to device
        # (Assuming aoa-config package is available)
        from aoa_config import AOAClient

        client = AOAClient(
            host=creds["host"],
            username=creds["username"],
            password=creds["password"],
        )

        # Get scenarios
        scenarios = client.list_scenarios()

        return {
            "device_id": device_id,
            "scenarios": scenarios,
        }

    except DeviceNotFoundError:
        return {"error": f"Device '{device_id}' not found in registry"}
    except AccountNotFoundError:
        return {"error": f"AOA agent account not configured for '{device_id}'"}
    except Exception as e:
        return {"error": f"Failed to connect to device: {str(e)}"}


def mcp_tool_create_scenario(
    device_id: str,
    scenario_name: str,
    scenario_type: str,
    **kwargs,
) -> Dict[str, Any]:
    """
    MCP Tool: Create a new AOA scenario.

    Args:
        device_id: Device identifier (exposed to LLM)
        scenario_name: Name for the scenario (exposed to LLM)
        scenario_type: Type of scenario (exposed to LLM)
        **kwargs: Additional scenario parameters (exposed to LLM)

    Returns:
        Result of scenario creation
    """
    try:
        creds = get_device_credentials(device_id)

        from aoa_config import AOAClient

        client = AOAClient(
            host=creds["host"],
            username=creds["username"],
            password=creds["password"],
        )

        # Create scenario
        result = client.create_scenario(scenario_name, scenario_type, **kwargs)

        return {
            "device_id": device_id,
            "scenario_name": scenario_name,
            "result": "success",
            "details": result,
        }

    except Exception as e:
        return {"error": str(e)}


def mcp_resource_list_devices() -> str:
    """
    MCP Resource: List available devices.

    This allows the LLM to discover which devices are available.
    Returns device metadata but NO credentials!

    Returns:
        JSON string with device list
    """
    import json

    if registry is None:
        initialize_registry()

    devices = registry.list_devices()

    # Return only non-sensitive information
    device_list = []
    for device in devices:
        device_list.append(
            {
                "id": device["device_id"],
                "location": device.get("location", "Unknown"),
                "host": device.get("host"),  # IP is not sensitive
                "model": device.get("model", "Unknown"),
                "tags": device.get("tags", []),
            }
        )

    return json.dumps({"devices": device_list}, indent=2)


# ============================================================================
# Demo: Simulating LLM Interaction
# ============================================================================

def demo_llm_workflow():
    """
    Demonstrate how the LLM interacts with the system.

    The LLM only sees:
    1. Device IDs (from resource)
    2. Tool parameters (device_id, scenario configs)

    The LLM NEVER sees:
    1. Passwords
    2. Usernames
    3. Raw credentials
    """
    print("=" * 70)
    print("Demo: LLM Workflow with ADMZ (Axis Device Manager)")
    print("=" * 70)

    # Initialize
    initialize_registry()

    # Step 1: LLM discovers available devices
    print("\n[LLM] Step 1: Discover available devices")
    print("         Resource: aoa://devices/list")
    devices_json = mcp_resource_list_devices()
    print(f"\n[SYSTEM] Returns:\n{devices_json}")

    # Parse to simulate LLM reading the response
    import json

    devices = json.loads(devices_json)["devices"]
    if not devices:
        print("\nNo devices available. Run scripts/setup_vault_example.sh first.")
        return

    device_id = devices[0]["id"]

    # Step 2: LLM calls tool with device ID
    print(f"\n[LLM] Step 2: List scenarios for '{device_id}'")
    print(f"         Tool: list_scenarios(device_id='{device_id}')")

    # Server resolves credentials internally (LLM never sees this!)
    try:
        creds = get_device_credentials(device_id)
        print(f"\n[SYSTEM] (Internal) Resolved credentials:")
        print(f"           Host: {creds['host']}")
        print(f"           Username: {creds['username']}")
        print(f"           Password: {'*' * 10} (hidden from LLM)")
    except Exception as e:
        print(f"\n[SYSTEM] Error: {e}")
        return

    # Simulate tool execution (without actual device connection)
    print(f"\n[SYSTEM] Connecting to device at {creds['host']}...")
    print("[SYSTEM] (Would execute: client.list_scenarios())")

    print(f"\n[SYSTEM] Returns to LLM:")
    print(
        """         {
           "device_id": "front-door",
           "scenarios": [
             {"id": 1, "name": "Front Door Motion", "type": "motion"},
             {"id": 2, "name": "Person Detection", "type": "object"}
           ]
         }"""
    )

    # Step 3: LLM processes result
    print("\n[LLM] Step 3: Respond to user")
    print('         "I found 2 scenarios configured on the front-door device:"')
    print('         "  1. Front Door Motion (motion detection)"')
    print('         "  2. Person Detection (object detection)"')

    print("\n" + "=" * 70)
    print("Key Security Features:")
    print("=" * 70)
    print("✓ LLM only sees device IDs and public metadata")
    print("✓ Credentials resolved server-side, never in LLM context")
    print("✓ Full audit trail in Vault of credential access")
    print("✓ Fine-grained access control via Vault policies")
    print("=" * 70)


# ============================================================================
# Main
# ============================================================================

def main():
    """Run the demo."""
    if not os.getenv("VAULT_ADDR"):
        print("Error: VAULT_ADDR environment variable not set")
        print("\nSet up your environment:")
        print("  export VAULT_ADDR='http://127.0.0.1:8200'")
        print("  export VAULT_TOKEN='<your-token>'")
        print("  # Or use AppRole:")
        print("  export VAULT_ROLE_ID='<role-id>'")
        print("  export VAULT_SECRET_ID='<secret-id>'")
        return

    demo_llm_workflow()


if __name__ == "__main__":
    main()
