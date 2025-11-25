#!/usr/bin/env python3
"""
Example: Managing devices programmatically.

This example shows how to:
1. Add new devices to Vault
2. Add accounts to devices
3. Update device information
4. Remove devices and accounts

Note: This requires appropriate Vault permissions (write/delete).
"""

import os
from admz import create_device_registry
from admz.exceptions import BackendError


def main():
    print("=" * 70)
    print("Device Management Example")
    print("=" * 70)

    # Verify environment
    if not os.getenv("VAULT_ADDR"):
        print("\nError: VAULT_ADDR not set")
        return

    # Create registry
    print("\nConnecting to Vault...")
    registry = create_device_registry()
    print("✓ Connected\n")

    # Example 1: Add a new device
    print("=" * 70)
    print("Example 1: Adding a New Device")
    print("=" * 70)

    device_id = "warehouse-cam-1"

    # Check if device already exists
    if registry.device_exists(device_id):
        print(f"\n✓ Device '{device_id}' already exists")
    else:
        print(f"\nAdding device '{device_id}'...")

        device_info = {
            "host": "192.168.2.50",
            "ip_address": "192.168.2.50",
            "serial_number": "ACCC99887766",
            "mac_address": "AC:CC:8E:99:88:77",
            "firmware_version": "11.9.55",
            "model": "AXIS Q1656-LE",
            "warranty_expiration": "2027-03-15",
            "location": "Warehouse - Bay 5",
        }

        # Add device info and accounts
        accounts = {
            "aoa-agent": {
                "username": "aoa_service",
                "password": "change_me_warehouse_1",
                "account_type": "service",
                "purpose": "AOA configuration service account",
                "permissions": "operator,admin",
            },
            "backup-service": {
                "username": "backup_svc",
                "password": "change_me_backup_1",
                "account_type": "service",
                "purpose": "Automated backup service",
                "permissions": "viewer",
            },
            "admin": {
                "username": "root",
                "password": "change_me_admin_1",
                "account_type": "admin",
                "purpose": "Administrative access",
                "permissions": "administrator",
            },
        }

        try:
            registry.add_device(device_id, device_info, accounts)
            print(f"✓ Device '{device_id}' added successfully")
            print(f"  - Device info stored")
            print(f"  - {len(accounts)} accounts created")
        except BackendError as e:
            print(f"✗ Failed to add device: {e}")

    # Example 2: Add an additional account to existing device
    print("\n" + "=" * 70)
    print("Example 2: Adding an Account to Existing Device")
    print("=" * 70)

    if registry.device_exists(device_id):
        account_id = "monitoring-service"

        if registry.account_exists(device_id, account_id):
            print(f"\n✓ Account '{account_id}' already exists")
        else:
            print(f"\nAdding account '{account_id}' to '{device_id}'...")

            account_data = {
                "username": "monitor_svc",
                "password": "change_me_monitor",
                "account_type": "service",
                "purpose": "Real-time monitoring dashboard",
                "permissions": "viewer",
            }

            try:
                registry.add_account(device_id, account_id, account_data)
                print(f"✓ Account '{account_id}' added successfully")
            except BackendError as e:
                print(f"✗ Failed to add account: {e}")

    # Example 3: List devices and their accounts
    print("\n" + "=" * 70)
    print("Example 3: Listing Devices")
    print("=" * 70)

    devices = registry.list_devices()
    print(f"\nFound {len(devices)} devices:")

    for device in devices:
        print(f"\n  Device: {device['device_id']}")
        print(f"    Location: {device.get('location', 'N/A')}")
        print(f"    Model: {device.get('model', 'N/A')}")
        print(f"    Host: {device.get('host', 'N/A')}")

        # List accounts for this device
        accounts = registry.list_accounts(device["device_id"])
        print(f"    Accounts ({len(accounts)}):")
        for account in accounts:
            print(
                f"      - {account['account_id']} ({account.get('account_type', 'N/A')})"
            )

    # Example 4: Get credentials for an account
    print("\n" + "=" * 70)
    print("Example 4: Retrieving Credentials")
    print("=" * 70)

    if registry.device_exists(device_id):
        print(f"\nGetting credentials for '{device_id}' / 'aoa-agent'...")

        try:
            creds = registry.get_credentials(device_id, "aoa-agent")
            print("✓ Credentials retrieved:")
            print(f"  Host: {creds['host']}")
            print(f"  Username: {creds['username']}")
            print(f"  Password: {'*' * 15} (hidden)")
            print(f"  Account Type: {creds.get('account_type', 'N/A')}")
        except Exception as e:
            print(f"✗ Failed: {e}")

    # Example 5: Remove an account
    print("\n" + "=" * 70)
    print("Example 5: Removing an Account (Optional)")
    print("=" * 70)

    # Uncomment to actually remove:
    # if registry.account_exists(device_id, "monitoring-service"):
    #     print(f"\nRemoving account 'monitoring-service' from '{device_id}'...")
    #     try:
    #         registry.remove_account(device_id, "monitoring-service")
    #         print("✓ Account removed")
    #     except Exception as e:
    #         print(f"✗ Failed: {e}")
    # else:
    #     print(f"\nAccount 'monitoring-service' does not exist")

    print("\n(Account removal commented out - uncomment in code to test)")

    # Example 6: Remove a device
    print("\n" + "=" * 70)
    print("Example 6: Removing a Device (Optional)")
    print("=" * 70)

    # Uncomment to actually remove:
    # if registry.device_exists(device_id):
    #     print(f"\nRemoving device '{device_id}'...")
    #     try:
    #         registry.remove_device(device_id)
    #         print("✓ Device removed (including all accounts)")
    #     except Exception as e:
    #         print(f"✗ Failed: {e}")
    # else:
    #     print(f"\nDevice '{device_id}' does not exist")

    print("\n(Device removal commented out - uncomment in code to test)")

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print("""
This example demonstrated:
  ✓ Adding devices with device info and accounts
  ✓ Adding additional accounts to devices
  ✓ Listing devices and accounts
  ✓ Retrieving credentials
  ✓ Removing accounts and devices (code provided, commented out)

Notes:
  - All operations require appropriate Vault permissions
  - Use device-admin policy for full write access
  - Removal operations are commented out by default for safety
  - Always change default passwords in production!
    """)


if __name__ == "__main__":
    main()
