#!/usr/bin/env python3
"""
Basic usage example for ADMZ (Axis Device Manager).

This example shows how to:
1. Connect to Vault
2. List available devices
3. Get device credentials
4. Get device information

Prerequisites:
- Vault server running with devices configured
- Environment variables set:
  - VAULT_ADDR: Vault server URL
  - VAULT_TOKEN: Vault auth token (or VAULT_ROLE_ID + VAULT_SECRET_ID)
"""

import os
from admz import create_device_registry
from admz.exceptions import DeviceNotFoundError, AccountNotFoundError


def main():
    # Verify environment is configured
    if not os.getenv("VAULT_ADDR"):
        print("Error: VAULT_ADDR environment variable not set")
        print("Example: export VAULT_ADDR='http://127.0.0.1:8200'")
        return

    if not (os.getenv("VAULT_TOKEN") or (os.getenv("VAULT_ROLE_ID") and os.getenv("VAULT_SECRET_ID"))):
        print("Error: Authentication not configured")
        print("Set either VAULT_TOKEN or VAULT_ROLE_ID + VAULT_SECRET_ID")
        return

    # Create device registry (auto-detects Vault from environment)
    print("Connecting to Vault...")
    registry = create_device_registry()
    print("✓ Connected to Vault\n")

    # List all devices
    print("=" * 60)
    print("Available Devices")
    print("=" * 60)
    devices = registry.list_devices()

    if not devices:
        print("No devices found in registry.")
        print("\nRun scripts/setup_vault_example.sh to add example devices.")
        return

    for device in devices:
        print(f"\nDevice ID: {device['device_id']}")
        print(f"  Location: {device.get('location', 'N/A')}")
        print(f"  Host: {device.get('host', 'N/A')}")
        print(f"  Model: {device.get('model', 'N/A')}")
        print(f"  Serial: {device.get('serial_number', 'N/A')}")
        print(f"  Firmware: {device.get('firmware_version', 'N/A')}")
        if 'tags' in device:
            print(f"  Tags: {device['tags']}")

    # Select first device for detailed examples
    device_id = devices[0]["device_id"]
    print(f"\n{'=' * 60}")
    print(f"Detailed Example: {device_id}")
    print("=" * 60)

    # Get device information
    print("\nDevice Information:")
    device_info = registry.get_device_info(device_id)
    for key, value in device_info.items():
        if key != "device_id":
            print(f"  {key}: {value}")

    # List accounts for this device
    print("\nAvailable Accounts:")
    accounts = registry.list_accounts(device_id)

    if not accounts:
        print("  No accounts configured for this device")
        return

    for account in accounts:
        print(f"\n  Account ID: {account['account_id']}")
        print(f"    Username: {account.get('username', 'N/A')}")
        print(f"    Type: {account.get('account_type', 'N/A')}")
        print(f"    Purpose: {account.get('purpose', 'N/A')}")

    # Get credentials for the first account
    account_id = accounts[0]["account_id"]
    print(f"\n{'=' * 60}")
    print(f"Getting Credentials: {device_id} / {account_id}")
    print("=" * 60)

    try:
        creds = registry.get_credentials(device_id, account_id)
        print("\n✓ Credentials retrieved successfully")
        print(f"  Host: {creds['host']}")
        print(f"  Username: {creds['username']}")
        print(f"  Password: {'*' * len(creds['password'])} (hidden)")
        print(f"  Account Type: {creds.get('account_type', 'N/A')}")

        # Example: Use credentials to connect to camera
        print("\n" + "=" * 60)
        print("Example: Using Credentials")
        print("=" * 60)
        print(f"""
# In your application, you would use these credentials like this:

import requests

response = requests.get(
    f"http://{creds['host']}/axis-cgi/param.cgi?action=list",
    auth=(creds['username'], creds['password'])
)

# Or with the Axis AOA client:
from aoa_config import AOAClient

client = AOAClient(
    host=creds['host'],
    username=creds['username'],
    password=creds['password']
)
scenarios = client.list_scenarios()
""")

    except DeviceNotFoundError as e:
        print(f"\n✗ Device not found: {e}")
    except AccountNotFoundError as e:
        print(f"\n✗ Account not found: {e}")
    except Exception as e:
        print(f"\n✗ Error: {e}")

    # Demonstrate checking if device/account exists
    print("\n" + "=" * 60)
    print("Checking Existence")
    print("=" * 60)

    if registry.device_exists(device_id):
        print(f"✓ Device '{device_id}' exists")

    if registry.account_exists(device_id, account_id):
        print(f"✓ Account '{account_id}' exists for device '{device_id}'")

    if not registry.device_exists("non-existent-device"):
        print("✓ Correctly reports non-existent device")

    print("\n" + "=" * 60)
    print("Example Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
