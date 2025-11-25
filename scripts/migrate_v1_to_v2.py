#!/usr/bin/env python3
"""
ADMZ Phase 1 - Vault Migration Script

Migrates data from v1 path structure (secret/cameras/*) to v2 (secret/devices/*).

This script:
- Reads all data from secret/cameras/* paths
- Migrates to secret/devices/* with new structure
- Preserves all existing data
- Adds default nicknames if missing
- Verifies migration success
- Offers to backup/delete old paths
- Supports dry-run mode
- Provides progress reporting

Usage:
    # Dry run (no changes)
    python migrate_v1_to_v2.py --dry-run

    # Live migration
    python migrate_v1_to_v2.py

    # With custom mount point
    python migrate_v1_to_v2.py --mount-point=custom-secret

    # Skip cleanup of old paths
    python migrate_v1_to_v2.py --no-cleanup
"""

import os
import sys
import argparse
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    import hvac
    from hvac.exceptions import InvalidPath, Forbidden, VaultError
except ImportError:
    print("ERROR: hvac library not installed. Run: pip install hvac>=2.0.0")
    sys.exit(1)


class MigrationStats:
    """Track migration statistics."""

    def __init__(self):
        self.devices_found = 0
        self.devices_migrated = 0
        self.accounts_migrated = 0
        self.errors = []
        self.warnings = []

    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)

    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)

    def print_summary(self):
        """Print migration summary."""
        print("\n" + "=" * 70)
        print("MIGRATION SUMMARY")
        print("=" * 70)
        print(f"Devices found:     {self.devices_found}")
        print(f"Devices migrated:  {self.devices_migrated}")
        print(f"Accounts migrated: {self.accounts_migrated}")
        print(f"Warnings:          {len(self.warnings)}")
        print(f"Errors:            {len(self.errors)}")

        if self.warnings:
            print("\nWARNINGS:")
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.errors:
            print("\nERRORS:")
            for error in self.errors:
                print(f"  - {error}")

        print("=" * 70 + "\n")


class VaultMigrator:
    """Handles migration from v1 to v2 vault structure."""

    def __init__(
        self,
        vault_addr: str,
        vault_token: str,
        mount_point: str = "secret",
        dry_run: bool = False,
    ):
        """
        Initialize the vault migrator.

        Args:
            vault_addr: Vault server URL
            vault_token: Vault authentication token
            mount_point: KV mount point (default: 'secret')
            dry_run: If True, don't make any changes
        """
        self.vault_addr = vault_addr
        self.mount_point = mount_point
        self.dry_run = dry_run
        self.stats = MigrationStats()

        # Initialize Vault client
        print(f"Connecting to Vault at {vault_addr}...")
        try:
            self.client = hvac.Client(url=vault_addr, token=vault_token)
            if not self.client.is_authenticated():
                raise Exception("Authentication failed")
            print("Successfully authenticated to Vault\n")
        except Exception as e:
            print(f"ERROR: Failed to connect to Vault: {e}")
            sys.exit(1)

    def read_secret(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Read a secret from Vault KV v2.

        Args:
            path: Path to secret (without mount point)

        Returns:
            Secret data or None if not found
        """
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=self.mount_point
            )
            return response["data"]["data"]
        except InvalidPath:
            return None
        except Exception as e:
            self.stats.add_error(f"Failed to read {path}: {e}")
            return None

    def write_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """
        Write a secret to Vault KV v2.

        Args:
            path: Path to secret (without mount point)
            data: Secret data

        Returns:
            True if successful
        """
        if self.dry_run:
            print(f"  [DRY RUN] Would write to: {path}")
            return True

        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path, secret=data, mount_point=self.mount_point
            )
            return True
        except Exception as e:
            self.stats.add_error(f"Failed to write {path}: {e}")
            return False

    def list_secrets(self, path: str) -> List[str]:
        """
        List secrets at a path.

        Args:
            path: Path to list (without mount point)

        Returns:
            List of secret names (or empty list if path doesn't exist)
        """
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=path, mount_point=self.mount_point
            )
            return response["data"]["keys"]
        except InvalidPath:
            return []
        except Exception as e:
            self.stats.add_error(f"Failed to list {path}: {e}")
            return []

    def delete_secret(self, path: str) -> bool:
        """
        Delete a secret and all versions from Vault.

        Args:
            path: Path to secret (without mount point)

        Returns:
            True if successful
        """
        if self.dry_run:
            print(f"  [DRY RUN] Would delete: {path}")
            return True

        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path, mount_point=self.mount_point
            )
            return True
        except Exception as e:
            self.stats.add_error(f"Failed to delete {path}: {e}")
            return False

    def migrate_device(self, device_id: str) -> bool:
        """
        Migrate a single device from v1 to v2 structure.

        V1 structure:
            cameras/{device_id}/device_info
            cameras/{device_id}/accounts/{account_id}

        V2 structure:
            devices/{device_id}/device_info
            devices/{device_id}/accounts/{account_id}

        Args:
            device_id: Device identifier

        Returns:
            True if migration successful
        """
        print(f"\nMigrating device: {device_id}")
        print("-" * 70)

        old_base = f"cameras/{device_id}"
        new_base = f"devices/{device_id}"

        # Step 1: Read device_info from old path
        old_device_info_path = f"{old_base}/device_info"
        device_info = self.read_secret(old_device_info_path)

        if not device_info:
            self.stats.add_error(f"Could not read device_info for {device_id}")
            return False

        print(f"  Found device_info: {device_info.get('host', 'N/A')}")

        # Step 2: Add default nickname if missing
        if "nickname" not in device_info:
            device_info["nickname"] = device_id
            self.stats.add_warning(f"Added default nickname '{device_id}' for {device_id}")

        # Step 3: Write device_info to new path
        new_device_info_path = f"{new_base}/device_info"
        if not self.write_secret(new_device_info_path, device_info):
            return False

        print(f"  Migrated device_info to: {new_device_info_path}")

        # Step 4: Migrate all accounts
        old_accounts_path = f"{old_base}/accounts"
        account_ids = self.list_secrets(old_accounts_path)

        if not account_ids:
            self.stats.add_warning(f"No accounts found for {device_id}")
        else:
            print(f"  Found {len(account_ids)} account(s)")

            for account_id in account_ids:
                account_id = account_id.rstrip("/")
                old_account_path = f"{old_accounts_path}/{account_id}"
                new_account_path = f"{new_base}/accounts/{account_id}"

                account_data = self.read_secret(old_account_path)
                if not account_data:
                    self.stats.add_error(f"Could not read account {device_id}/{account_id}")
                    continue

                if self.write_secret(new_account_path, account_data):
                    print(f"    - Migrated account: {account_id}")
                    self.stats.accounts_migrated += 1

        self.stats.devices_migrated += 1
        return True

    def verify_migration(self, device_id: str) -> bool:
        """
        Verify that a device was migrated correctly.

        Args:
            device_id: Device identifier

        Returns:
            True if verification successful
        """
        old_base = f"cameras/{device_id}"
        new_base = f"devices/{device_id}"

        # Verify device_info
        old_device_info = self.read_secret(f"{old_base}/device_info")
        new_device_info = self.read_secret(f"{new_base}/device_info")

        if not new_device_info:
            self.stats.add_error(f"Verification failed: {device_id} device_info not found in new location")
            return False

        # Verify all accounts
        old_accounts_path = f"{old_base}/accounts"
        account_ids = self.list_secrets(old_accounts_path)

        for account_id in account_ids:
            account_id = account_id.rstrip("/")
            old_account = self.read_secret(f"{old_accounts_path}/{account_id}")
            new_account = self.read_secret(f"{new_base}/accounts/{account_id}")

            if not new_account:
                self.stats.add_error(f"Verification failed: {device_id}/{account_id} not found in new location")
                return False

            # Verify credentials match (excluding nickname which may have been added)
            for key in ["username", "password"]:
                if key in old_account and old_account[key] != new_account.get(key):
                    self.stats.add_error(f"Verification failed: {device_id}/{account_id} {key} mismatch")
                    return False

        return True

    def cleanup_old_path(self, device_id: str) -> bool:
        """
        Delete old v1 paths after successful migration.

        Args:
            device_id: Device identifier

        Returns:
            True if cleanup successful
        """
        old_base = f"cameras/{device_id}"

        # Delete all accounts
        old_accounts_path = f"{old_base}/accounts"
        account_ids = self.list_secrets(old_accounts_path)

        for account_id in account_ids:
            account_id = account_id.rstrip("/")
            self.delete_secret(f"{old_accounts_path}/{account_id}")

        # Delete device_info
        self.delete_secret(f"{old_base}/device_info")

        return True

    def run(self, cleanup: bool = True) -> bool:
        """
        Run the full migration process.

        Args:
            cleanup: If True, delete old paths after successful migration

        Returns:
            True if migration successful
        """
        mode = "[DRY RUN] " if self.dry_run else ""
        print(f"{mode}Starting ADMZ v1 -> v2 Migration")
        print("=" * 70)
        print(f"Vault Address:  {self.vault_addr}")
        print(f"Mount Point:    {self.mount_point}")
        print(f"Source Path:    cameras/*")
        print(f"Target Path:    devices/*")
        print(f"Cleanup Old:    {cleanup}")
        print("=" * 70)

        # Step 1: Discover all devices in old structure
        print("\nPhase 1: Discovery")
        print("-" * 70)
        device_ids = self.list_secrets("cameras")

        if not device_ids:
            print("No devices found at 'cameras/' path")
            print("\nPossible reasons:")
            print("  - Already migrated to v2")
            print("  - No devices in vault yet")
            print("  - Incorrect vault path or permissions")
            return True

        self.stats.devices_found = len(device_ids)
        print(f"Found {self.stats.devices_found} device(s) to migrate:")
        for device_id in device_ids:
            device_id = device_id.rstrip("/")
            print(f"  - {device_id}")

        # Step 2: Migrate each device
        print("\nPhase 2: Migration")
        print("-" * 70)

        for device_id in device_ids:
            device_id = device_id.rstrip("/")
            self.migrate_device(device_id)

        # Step 3: Verify migration
        if not self.dry_run:
            print("\nPhase 3: Verification")
            print("-" * 70)

            verification_failed = False
            for device_id in device_ids:
                device_id = device_id.rstrip("/")
                if not self.verify_migration(device_id):
                    verification_failed = True
                    print(f"  [FAIL] {device_id}")
                else:
                    print(f"  [OK] {device_id}")

            if verification_failed:
                print("\nVerification failed! Old paths will NOT be deleted.")
                cleanup = False

        # Step 4: Cleanup old paths
        if cleanup and not self.dry_run:
            print("\nPhase 4: Cleanup")
            print("-" * 70)

            response = input("\nDelete old 'cameras/*' paths? (yes/no): ")
            if response.lower() == "yes":
                for device_id in device_ids:
                    device_id = device_id.rstrip("/")
                    if self.cleanup_old_path(device_id):
                        print(f"  Cleaned up: cameras/{device_id}")
                    else:
                        print(f"  Failed to clean up: cameras/{device_id}")
            else:
                print("Skipping cleanup. Old paths remain in vault.")

        # Print summary
        self.stats.print_summary()

        return len(self.stats.errors) == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate ADMZ data from v1 (cameras/*) to v2 (devices/*)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (recommended first)
  python migrate_v1_to_v2.py --dry-run

  # Live migration
  python migrate_v1_to_v2.py

  # Custom mount point
  python migrate_v1_to_v2.py --mount-point=custom-secret

  # Skip cleanup
  python migrate_v1_to_v2.py --no-cleanup

Environment Variables:
  VAULT_ADDR   - Vault server URL (required)
  VAULT_TOKEN  - Vault authentication token (required)
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )

    parser.add_argument(
        "--mount-point",
        default="secret",
        help="Vault KV mount point (default: secret)",
    )

    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't delete old paths after migration",
    )

    args = parser.parse_args()

    # Get Vault configuration from environment
    vault_addr = os.getenv("VAULT_ADDR")
    vault_token = os.getenv("VAULT_TOKEN")

    if not vault_addr:
        print("ERROR: VAULT_ADDR environment variable not set")
        print("\nSet it with: export VAULT_ADDR='http://127.0.0.1:8200'")
        sys.exit(1)

    if not vault_token:
        print("ERROR: VAULT_TOKEN environment variable not set")
        print("\nSet it with: export VAULT_TOKEN='your-token'")
        sys.exit(1)

    # Create migrator and run
    migrator = VaultMigrator(
        vault_addr=vault_addr,
        vault_token=vault_token,
        mount_point=args.mount_point,
        dry_run=args.dry_run,
    )

    success = migrator.run(cleanup=not args.no_cleanup)

    if args.dry_run:
        print("\nDry run complete. Run without --dry-run to perform migration.")
        sys.exit(0)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
