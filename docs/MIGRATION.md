# ADMZ Migration Guide - v1 to v2

This guide covers upgrading from ADMZ v1 to v2, including breaking changes, path migrations, and code updates.

## Overview

ADMZ v2 introduces several important changes:
- **Path Structure**: Vault paths changed from `cameras/*` to `devices/*`
- **Terminology**: "Cameras" renamed to "Devices" throughout the codebase
- **New Features**: Nicknames, FastAPI REST API, MCP server integration
- **Import Changes**: Package renamed from `axis_secrets` to `admz`

## Breaking Changes

### 1. Vault Path Structure

**v1 Structure:**
```
secret/cameras/{device_id}/device_info
secret/cameras/{device_id}/accounts/{account_id}
```

**v2 Structure:**
```
secret/devices/{device_id}/device_info
secret/devices/{device_id}/accounts/{account_id}
```

### 2. Python Package Name

**v1:**
```python
from axis_secrets import create_camera_registry

registry = create_camera_registry()
```

**v2:**
```python
from admz import create_device_registry

registry = create_device_registry()
```

### 3. Method Names

| v1 Method | v2 Method | Notes |
|-----------|-----------|-------|
| `create_camera_registry()` | `create_device_registry()` | Factory function renamed |
| `list_cameras()` | `list_devices()` | Consistency with device terminology |
| `get_camera_info()` | `get_device_info()` | Method renamed |
| `camera_exists()` | `device_exists()` | Method renamed |
| `add_camera()` | `add_device()` | Method renamed |
| `remove_camera()` | `remove_device()` | Method renamed |

### 4. Parameter Names

| v1 Parameter | v2 Parameter | Affected Methods |
|--------------|--------------|------------------|
| `camera_id` | `device_id` | All methods |

### 5. Environment Variables

**Unchanged** - All environment variables remain the same:
- `VAULT_ADDR`
- `VAULT_TOKEN`
- `VAULT_ROLE_ID`
- `VAULT_SECRET_ID`
- `VAULT_MOUNT_POINT`
- `VAULT_PATH_PREFIX` (still defaults to "devices" but can be customized)

## Migration Steps

### Step 1: Run Vault Migration Script

The migration script handles moving data from v1 to v2 paths in Vault.

```bash
# Set Vault credentials
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='your-token'

# Dry run first (recommended)
python scripts/migrate_v1_to_v2.py --dry-run

# Review the output, then run actual migration
python scripts/migrate_v1_to_v2.py
```

**What the script does:**
1. Discovers all devices at `cameras/*` paths
2. Reads device_info and all accounts for each device
3. Adds default nicknames if missing (uses device_id)
4. Writes data to new `devices/*` paths
5. Verifies migration success
6. Optionally deletes old paths

**Script Options:**
```bash
# Custom mount point
python scripts/migrate_v1_to_v2.py --mount-point=custom-secret

# Skip cleanup of old paths
python scripts/migrate_v1_to_v2.py --no-cleanup

# Get help
python scripts/migrate_v1_to_v2.py --help
```

### Step 2: Update Python Dependencies

Update your `requirements.txt`:

**v1:**
```
hvac>=2.0.0
flask>=3.0.0
```

**v2:**
```
hvac>=2.0.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
jinja2>=3.1.2
python-multipart>=0.0.6
mcp>=0.9.0
```

Install new dependencies:
```bash
pip install -r requirements.txt
```

### Step 3: Update Import Statements

Update your Python code to use new imports:

**Before (v1):**
```python
from axis_secrets import create_camera_registry
from axis_secrets.backends.vault_backend import VaultCameraRegistry
from axis_secrets.exceptions import CameraNotFoundError
```

**After (v2):**
```python
from admz import create_device_registry
from admz.backends.vault_backend import VaultDeviceRegistry
from admz.exceptions import DeviceNotFoundError
```

**Find and Replace Guide:**
```bash
# In your codebase, replace:
axis_secrets → admz
create_camera_registry → create_device_registry
VaultCameraRegistry → VaultDeviceRegistry
CameraNotFoundError → DeviceNotFoundError
camera_id → device_id
camera_exists → device_exists
list_cameras → list_devices
get_camera_info → get_device_info
add_camera → add_device
remove_camera → remove_device
```

### Step 4: Update Method Calls

**Before (v1):**
```python
from axis_secrets import create_camera_registry

registry = create_camera_registry()

# List all cameras
cameras = registry.list_cameras()

# Get camera info
camera = registry.get_camera_info('front-door')

# Check if camera exists
if registry.camera_exists('front-door'):
    print("Camera found")

# Get credentials
creds = registry.get_credentials(
    camera_id='front-door',
    account_id='aoa-agent'
)
```

**After (v2):**
```python
from admz import create_device_registry

registry = create_device_registry()

# List all devices
devices = registry.list_devices()

# Get device info
device = registry.get_device_info('front-door')

# Check if device exists
if registry.device_exists('front-door'):
    print("Device found")

# Get credentials
creds = registry.get_credentials(
    device_id='front-door',
    account_id='aoa-agent'
)
```

### Step 5: Add Nicknames (Optional but Recommended)

v2 introduces nicknames for easier device identification:

```python
from admz import create_device_registry

registry = create_device_registry()

# Get device and check if it has a nickname
device = registry.get_device_info('front-door')
if 'nickname' not in device:
    # Add a nickname via Vault CLI or API
    print(f"Consider adding a nickname for {device['device_id']}")

# Or get device by nickname
device = registry.get_device_by_nickname('Main Entrance Camera')
```

To add nicknames to existing devices:

```bash
# Via Vault CLI
vault kv patch secret/devices/front-door/device_info nickname="Main Entrance Camera"

# Via Python API
from admz import create_device_registry
registry = create_device_registry()

# Read current device info
device_info = registry.get_device_info('front-door')

# Add nickname
device_info['nickname'] = 'Main Entrance Camera'

# Write back (this requires proper vault permissions)
# Use vault CLI or update via management script
```

### Step 6: Update Configuration Files

If you have configuration files referencing the old structure:

**MCP Server Config (before):**
```json
{
  "mcpServers": {
    "axis-secrets": {
      "command": "python",
      "args": ["-m", "axis_secrets.mcp_server"]
    }
  }
}
```

**MCP Server Config (after):**
```json
{
  "mcpServers": {
    "admz": {
      "command": "python",
      "args": ["-m", "admz.mcp_server"],
      "env": {
        "VAULT_ADDR": "http://127.0.0.1:8200",
        "VAULT_TOKEN": "your-token"
      }
    }
  }
}
```

### Step 7: Update Tests

Update your test code:

**Before (v1):**
```python
from axis_secrets import create_camera_registry
from axis_secrets.exceptions import CameraNotFoundError

def test_get_camera():
    registry = create_camera_registry()
    camera = registry.get_camera_info('test-camera')
    assert camera['host'] == '192.168.1.10'
```

**After (v2):**
```python
from admz import create_device_registry
from admz.exceptions import DeviceNotFoundError

def test_get_device():
    registry = create_device_registry()
    device = registry.get_device_info('test-device')
    assert device['host'] == '192.168.1.10'
```

## New Features in v2

### 1. FastAPI REST API

v2 includes a production-ready REST API:

```bash
# Start the API server
cd admz
uvicorn api.main:app --reload --port 8000

# Access interactive docs
open http://localhost:8000/docs
```

**Available Endpoints:**
- `GET /devices` - List all devices
- `GET /devices/{device_id}` - Get device info
- `GET /devices/by-nickname/{nickname}` - Get device by nickname
- `GET /devices/{device_id}/accounts` - List accounts
- `GET /devices/{device_id}/accounts/{account_id}/credentials` - Get credentials
- `POST /devices` - Add new device
- `PUT /devices/{device_id}/nickname` - Update nickname
- `DELETE /devices/{device_id}` - Remove device
- `GET /health` - Health check

### 2. MCP Server Integration

v2 includes a full MCP server for AI agent integration:

```python
# Configure in Claude Code
{
  "mcpServers": {
    "admz": {
      "command": "python",
      "args": ["-m", "admz.mcp_server"],
      "env": {
        "VAULT_ADDR": "http://127.0.0.1:8200",
        "VAULT_TOKEN": "your-token"
      }
    }
  }
}
```

**MCP Tools Available:**
- `list_devices` - List all available devices
- `get_device_info` - Get detailed device information
- `get_credentials` - Get credentials for a specific account
- `search_devices_by_tag` - Search devices by tags

See [MCP_INTEGRATION.md](MCP_INTEGRATION.md) for complete documentation.

### 3. Device Nicknames

Add human-readable nicknames to devices:

```python
device_info = {
    'host': '192.168.1.10',
    'nickname': 'Main Entrance Camera',  # New in v2
    'model': 'AXIS P3245-LVE',
    'location': 'Main Entrance'
}

# Get device by nickname
device = registry.get_device_by_nickname('Main Entrance Camera')
```

### 4. Enhanced Error Handling

v2 includes more specific exception types:

```python
from admz.exceptions import (
    DeviceNotFoundError,
    AccountNotFoundError,
    PermissionDeniedError,
    AuthenticationError,
    ConfigurationError,
    BackendError
)

try:
    device = registry.get_device_info('unknown')
except DeviceNotFoundError as e:
    print(f"Device not found: {e}")
except PermissionDeniedError as e:
    print(f"Access denied: {e}")
```

## Rollback Plan

If you need to rollback to v1:

### Option 1: Keep Both Paths

During migration, you can choose not to cleanup old paths:

```bash
# Migrate but keep old paths
python scripts/migrate_v1_to_v2.py --no-cleanup
```

This allows both v1 and v2 applications to work simultaneously.

### Option 2: Restore from Backup

If you deleted old paths, restore from Vault backup:

```bash
# Restore from Vault snapshot
vault operator raft snapshot restore backup.snap
```

### Option 3: Re-create Old Paths

```bash
# List all devices in new path
vault kv list secret/devices

# For each device, copy back to old path
vault kv get -format=json secret/devices/front-door/device_info | \
  vault kv put secret/cameras/front-door/device_info -

# Copy accounts
vault kv list secret/devices/front-door/accounts
vault kv get -format=json secret/devices/front-door/accounts/aoa-agent | \
  vault kv put secret/cameras/front-door/accounts/aoa-agent -
```

## Verification Checklist

After migration, verify:

- [ ] All devices appear in `vault kv list secret/devices`
- [ ] Device info includes all original fields plus nickname
- [ ] All accounts migrated successfully
- [ ] Python code updated to use `admz` imports
- [ ] All `camera_*` references changed to `device_*`
- [ ] Tests pass with new API
- [ ] MCP server configured (if using)
- [ ] FastAPI server starts and responds
- [ ] Old paths removed (or marked for cleanup)
- [ ] Documentation updated

## Testing Your Migration

Run these tests after migration:

```python
from admz import create_device_registry

registry = create_device_registry()

# Test 1: List all devices
devices = registry.list_devices()
print(f"Found {len(devices)} devices")

# Test 2: Get device info
for device in devices:
    device_id = device['device_id']
    device_info = registry.get_device_info(device_id)
    print(f"✓ {device_id}: {device_info.get('nickname', device_id)}")

    # Test 3: List accounts
    accounts = registry.list_accounts(device_id)
    print(f"  Accounts: {[a['account_id'] for a in accounts]}")

    # Test 4: Get credentials
    if accounts:
        account_id = accounts[0]['account_id']
        creds = registry.get_credentials(device_id, account_id)
        print(f"  ✓ Retrieved credentials for {account_id}")

print("\nMigration verification complete!")
```

## Getting Help

If you encounter issues during migration:

1. **Check the logs**: Look for error messages in the migration script output
2. **Verify Vault permissions**: Ensure your token has read/write access to both paths
3. **Run in dry-run mode**: Use `--dry-run` to see what would happen
4. **Backup first**: Always backup Vault before migration
5. **Contact support**: Open an issue at https://github.com/yourusername/admz/issues

## Common Migration Issues

### Issue 1: Permission Denied

**Error:** `Access denied to devices path`

**Solution:** Ensure your Vault token has permissions for both old and new paths:

```hcl
path "secret/data/cameras/*" {
  capabilities = ["read", "list"]
}

path "secret/data/devices/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
```

### Issue 2: Missing Nicknames

**Error:** Devices missing nickname field after migration

**Solution:** The migration script adds default nicknames (device_id). Update manually:

```bash
vault kv patch secret/devices/front-door/device_info nickname="Main Entrance"
```

### Issue 3: Import Errors

**Error:** `ModuleNotFoundError: No module named 'axis_secrets'`

**Solution:** Update all imports from `axis_secrets` to `admz`

### Issue 4: Old Paths Not Deleted

**Error:** Both old and new paths exist

**Solution:** This is intentional during migration. Delete manually if needed:

```bash
# List old paths
vault kv list secret/cameras

# Delete old device
vault kv metadata delete secret/cameras/front-door/device_info
vault kv metadata delete secret/cameras/front-door/accounts/aoa-agent
```

## Summary

Key changes in v2:
1. ✅ Vault paths: `cameras/*` → `devices/*`
2. ✅ Package: `axis_secrets` → `admz`
3. ✅ Methods: `*_camera*` → `*_device*`
4. ✅ New: FastAPI REST API
5. ✅ New: MCP server integration
6. ✅ New: Device nicknames
7. ✅ New: Enhanced error handling

The migration script handles Vault data migration automatically. Code updates can be done with simple find/replace operations.
