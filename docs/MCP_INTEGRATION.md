# ADMZ MCP Integration Guide

## Table of Contents

- [What is MCP?](#what-is-mcp)
- [Why MCP for ADMZ?](#why-mcp-for-admz)
- [Installation](#installation)
- [Configuration](#configuration)
- [Available Tools](#available-tools)
- [Usage Examples](#usage-examples)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## What is MCP?

The Model Context Protocol (MCP) is an open protocol that standardizes how applications provide context to Large Language Models (LLMs). It enables LLMs to securely interact with external systems, databases, and APIs through a unified interface.

Key benefits:
- **Standardized**: Works with any MCP-compatible LLM client (Claude Code, Cline, etc.)
- **Secure**: Tools are explicitly defined with clear boundaries
- **Extensible**: Easy to add new capabilities
- **Auditable**: All interactions can be logged and monitored

## Why MCP for ADMZ?

The ADMZ MCP server enables LLMs to:

1. **Discover devices** - Search and list devices in your registry
2. **Retrieve credentials** - Securely access device credentials when needed
3. **Manage devices** - Register, update, and remove devices
4. **Manage accounts** - Add and remove device accounts
5. **Search intelligently** - Find devices by tags, location, model, etc.

This allows for natural language interactions like:
- "Show me all outdoor cameras in Building A"
- "Get the credentials for the front door camera"
- "Add a new device called lobby-camera with these settings..."

## Installation

### Prerequisites

1. Python 3.8 or higher
2. ADMZ library installed
3. MCP Python SDK

### Install Dependencies

```bash
# Install ADMZ with MCP support
pip install -e /path/to/AxisSecrets

# Install MCP SDK
pip install mcp
```

### Verify Installation

```bash
# Test the MCP server starts correctly
python -m admz mcp
```

You should see:
```
Starting ADMZ MCP server...
MCP server ready for connections
```

Press `Ctrl+C` to stop.

## Configuration

### For Claude Code

1. Create or edit your Claude Code MCP configuration file:
   - **macOS/Linux**: `~/.config/claude-code/mcp.json`
   - **Windows**: `%APPDATA%\claude-code\mcp.json`

2. Add the ADMZ server configuration:

```json
{
  "mcpServers": {
    "admz": {
      "command": "python",
      "args": ["-m", "admz", "mcp"],
      "cwd": "/path/to/AxisSecrets",
      "env": {
        "VAULT_ADDR": "https://vault.example.com",
        "VAULT_TOKEN": "your-vault-token-here",
        "VAULT_MOUNT_POINT": "secret",
        "VAULT_PATH_PREFIX": "devices"
      }
    }
  }
}
```

3. Update the configuration values:
   - `cwd`: Full path to your AxisSecrets directory
   - `VAULT_ADDR`: Your Vault server URL
   - `VAULT_TOKEN`: Your Vault authentication token
   - `VAULT_MOUNT_POINT`: KV mount point (default: "secret")
   - `VAULT_PATH_PREFIX`: Device path prefix (default: "devices")

4. Restart Claude Code to load the new configuration

### Alternative Authentication Methods

#### Using AppRole Authentication

```json
{
  "mcpServers": {
    "admz": {
      "command": "python",
      "args": ["-m", "admz", "mcp"],
      "cwd": "/path/to/AxisSecrets",
      "env": {
        "VAULT_ADDR": "https://vault.example.com",
        "VAULT_ROLE_ID": "your-role-id",
        "VAULT_SECRET_ID": "your-secret-id",
        "VAULT_MOUNT_POINT": "secret",
        "VAULT_PATH_PREFIX": "devices"
      }
    }
  }
}
```

#### Using Environment Variables

If you already have Vault environment variables set, you can omit them from the config:

```json
{
  "mcpServers": {
    "admz": {
      "command": "python",
      "args": ["-m", "admz", "mcp"],
      "cwd": "/path/to/AxisSecrets"
    }
  }
}
```

Then set in your shell:
```bash
export VAULT_ADDR=https://vault.example.com
export VAULT_TOKEN=your-token
```

### For Other MCP Clients

The ADMZ MCP server uses stdio transport and is compatible with any MCP client. Refer to your client's documentation for configuration instructions.

## Available Tools

### 1. list_devices

List all devices in the registry without credentials.

**Parameters**: None

**Returns**:
```json
{
  "success": true,
  "count": 5,
  "devices": [
    {
      "device_id": "front-door",
      "host": "192.168.1.100",
      "nickname": "Front Door Camera",
      "model": "AXIS P1365",
      "location": "Building A - Main Entrance",
      "tags": ["entrance", "outdoor"]
    }
  ]
}
```

### 2. get_device

Get detailed information about a specific device.

**Parameters**:
- `device_id` (string, required): Device ID or nickname

**Returns**:
```json
{
  "success": true,
  "device": {
    "device_id": "front-door",
    "host": "192.168.1.100",
    "nickname": "Front Door Camera",
    "model": "AXIS P1365",
    "serial_number": "ACCC1234567",
    "firmware_version": "10.12.1",
    "location": "Building A - Main Entrance",
    "tags": ["entrance", "outdoor"]
  }
}
```

### 3. search_devices

Search devices by tags, location, or model.

**Parameters**:
- `tags` (array, optional): Filter by tags
- `location` (string, optional): Filter by location
- `model` (string, optional): Filter by model

**Example**:
```json
{
  "tags": ["outdoor", "entrance"],
  "location": "Building A"
}
```

**Returns**:
```json
{
  "success": true,
  "count": 2,
  "devices": [...],
  "filters": {
    "tags": ["outdoor", "entrance"],
    "location": "Building A"
  }
}
```

### 4. list_accounts

List all accounts for a device (without passwords).

**Parameters**:
- `device_id` (string, required): Device ID

**Returns**:
```json
{
  "success": true,
  "device_id": "front-door",
  "count": 2,
  "accounts": [
    {
      "account_id": "default",
      "username": "admin",
      "account_type": "admin",
      "purpose": "Full administrative access",
      "permissions": ["read", "write", "admin"]
    },
    {
      "account_id": "aoa-agent",
      "username": "aoa-service",
      "account_type": "service",
      "purpose": "AoA monitoring service account",
      "permissions": ["read"]
    }
  ]
}
```

### 5. get_credentials

Get credentials for a specific device and account.

**Parameters**:
- `device_id` (string, required): Device ID
- `account_id` (string, optional): Account ID (default: "default")
- `requester` (string, optional): Who is requesting (for audit logs)

**Returns**:
```json
{
  "success": true,
  "device_id": "front-door",
  "account_id": "default",
  "credentials": {
    "username": "admin",
    "password": "secure-password-here",
    "host": "192.168.1.100",
    "account_type": "admin",
    "permissions": ["read", "write", "admin"]
  }
}
```

**Security Note**: This tool retrieves sensitive credentials. Use with caution and ensure audit logging is enabled.

### 6. register_device

Register a new device in the registry.

**Parameters**:
- `device_id` (string, required): Unique device identifier
- `device_info` (object, required): Device metadata
- `accounts` (object, optional): Initial accounts

**Example**:
```json
{
  "device_id": "new-camera-1",
  "device_info": {
    "host": "192.168.1.200",
    "nickname": "New Camera",
    "model": "AXIS M3067-P",
    "location": "Building B",
    "tags": ["new", "indoor"]
  },
  "accounts": {
    "default": {
      "username": "admin",
      "password": "initial-password",
      "account_type": "admin",
      "purpose": "Administrative access"
    }
  }
}
```

### 7. add_account

Add a new account to an existing device.

**Parameters**:
- `device_id` (string, required): Device ID
- `account_id` (string, required): Account identifier
- `account_data` (object, required): Account credentials and metadata

**Example**:
```json
{
  "device_id": "front-door",
  "account_id": "monitoring",
  "account_data": {
    "username": "monitor",
    "password": "monitor-password",
    "account_type": "service",
    "purpose": "Monitoring service account",
    "permissions": ["read"]
  }
}
```

### 8. update_device

Update device information.

**Parameters**:
- `device_id` (string, required): Device ID
- `updates` (object, required): Fields to update

**Example**:
```json
{
  "device_id": "front-door",
  "updates": {
    "firmware_version": "10.12.2",
    "location": "Building A - Side Entrance",
    "tags": ["entrance", "outdoor", "upgraded"]
  }
}
```

### 9. delete_device

Remove a device from the registry.

**Parameters**:
- `device_id` (string, required): Device ID to delete

**Warning**: This deletes all device information and accounts. Cannot be undone.

### 10. delete_account

Remove an account from a device.

**Parameters**:
- `device_id` (string, required): Device ID
- `account_id` (string, required): Account ID to delete

**Warning**: This deletes the account credentials. Cannot be undone.

## Usage Examples

### Example 1: Discovery

User: "Show me all outdoor cameras"

Claude:
```
Let me search for outdoor cameras in your registry.

[Uses search_devices with tags: ["outdoor"]]

I found 5 outdoor cameras:
1. Front Door Camera (front-door) - Building A
2. Back Entrance (back-door) - Building A
3. Parking Lot Camera (parking-1) - Parking Area
...
```

### Example 2: Credential Retrieval

User: "I need to configure the front door camera. Get me the admin credentials."

Claude:
```
I'll retrieve the admin credentials for the front door camera.

[Uses get_credentials with device_id: "front-door", account_id: "default"]

Credentials for front-door (default account):
- Host: 192.168.1.100
- Username: admin
- Password: [secure-password-displayed]

You can now connect to the camera's web interface at https://192.168.1.100
```

### Example 3: Device Registration

User: "Register a new camera with ID 'lobby-cam', IP 192.168.1.150, model AXIS M3067-P, located in the main lobby, tagged as indoor and entrance. Set up an admin account with username 'admin' and password 'Secure123!'"

Claude:
```
I'll register the new camera in your device registry.

[Uses register_device with appropriate parameters]

Successfully registered device 'lobby-cam':
- Host: 192.168.1.150
- Model: AXIS M3067-P
- Location: Main Lobby
- Tags: indoor, entrance
- Admin account created

The device is now available in your registry.
```

### Example 4: Account Management

User: "Add a monitoring service account to the lobby camera with username 'monitor' and password 'Monitor123!'"

Claude:
```
I'll add the monitoring service account to the lobby camera.

[Uses add_account]

Successfully added monitoring account to 'lobby-cam':
- Account ID: monitoring
- Username: monitor
- Type: service
- Purpose: Monitoring service account

The monitoring service can now access this camera.
```

### Example 5: Complex Search

User: "Find all AXIS P1365 cameras in Building A that are outdoors"

Claude:
```
Let me search for cameras matching those criteria.

[Uses search_devices with model: "AXIS P1365", location: "Building A", tags: ["outdoor"]]

Found 2 matching cameras:
1. Front Door Camera (front-door)
   - Model: AXIS P1365
   - Location: Building A - Main Entrance
   - IP: 192.168.1.100

2. Side Entrance (side-door)
   - Model: AXIS P1365
   - Location: Building A - Side Entrance
   - IP: 192.168.1.101
```

## Security Considerations

### 1. Credential Access Control

The MCP server retrieves credentials from your backend (Vault) and returns them to the LLM. Consider:

- **Audit Logging**: All credential retrievals should be logged
- **Access Policies**: Use Vault policies to restrict which credentials can be accessed
- **Requester Tracking**: Pass the `requester` parameter to track who is accessing credentials

### 2. Environment Variables

Store sensitive configuration in environment variables, not in the MCP config file:

```bash
# Good - environment variables
export VAULT_TOKEN=your-token

# Bad - hardcoded in config
"env": {
  "VAULT_TOKEN": "hvs.CAESIJ..."
}
```

### 3. Network Security

- Use HTTPS for Vault connections
- Enable TLS certificate verification
- Use VPN or secure networks when accessing the MCP server

### 4. Least Privilege

Configure Vault policies to grant minimum necessary permissions:

```hcl
# Vault policy example - read-only access
path "secret/data/devices/*/device_info" {
  capabilities = ["read"]
}

path "secret/data/devices/*/accounts/*" {
  capabilities = ["read"]
}

# No write permissions
```

### 5. Audit Trail

Enable comprehensive logging:

```python
# Add to your MCP server configuration
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('admz-mcp.log'),
        logging.StreamHandler()
    ]
)
```

## Troubleshooting

### Server Won't Start

**Problem**: Error when starting MCP server

**Solutions**:

1. Check Python version:
   ```bash
   python --version  # Should be 3.8+
   ```

2. Verify dependencies:
   ```bash
   pip install mcp
   pip install -e /path/to/AxisSecrets
   ```

3. Check Vault configuration:
   ```bash
   python -c "from admz import create_device_registry; r = create_device_registry(); print('OK')"
   ```

### Authentication Failures

**Problem**: Vault authentication errors

**Solutions**:

1. Verify Vault address is correct:
   ```bash
   curl $VAULT_ADDR/v1/sys/health
   ```

2. Check token validity:
   ```bash
   vault token lookup
   ```

3. Test AppRole credentials:
   ```bash
   vault write auth/approle/login \
     role_id=$VAULT_ROLE_ID \
     secret_id=$VAULT_SECRET_ID
   ```

### Device Not Found

**Problem**: "DeviceNotFound" error

**Solutions**:

1. List all devices to verify the ID:
   ```
   [Use list_devices tool]
   ```

2. Check for typos in device ID

3. Try searching by nickname:
   ```
   [Use get_device with nickname instead]
   ```

### Permission Denied

**Problem**: "PermissionDenied" error

**Solutions**:

1. Check Vault policies:
   ```bash
   vault token capabilities secret/data/devices/device-id
   ```

2. Verify mount point and path prefix configuration

3. Ensure the backend supports the operation (some operations may not be implemented)

### MCP Client Connection Issues

**Problem**: Claude Code doesn't see ADMZ tools

**Solutions**:

1. Verify MCP config file location and syntax:
   ```bash
   cat ~/.config/claude-code/mcp.json | python -m json.tool
   ```

2. Check server starts in isolation:
   ```bash
   python -m admz mcp
   ```

3. Restart Claude Code completely

4. Check Claude Code logs for MCP errors

### Tool Execution Errors

**Problem**: Tools fail with "InternalError"

**Solutions**:

1. Check ADMZ MCP server logs for details

2. Test the registry directly:
   ```python
   from admz import create_device_registry
   r = create_device_registry()
   print(r.list_devices())
   ```

3. Verify backend connectivity and permissions

## Advanced Configuration

### Custom Backend

If using a custom backend implementation:

```json
{
  "mcpServers": {
    "admz": {
      "command": "python",
      "args": ["-m", "admz", "mcp"],
      "cwd": "/path/to/AxisSecrets",
      "env": {
        "DEVICE_REGISTRY_BACKEND": "custom",
        "CUSTOM_BACKEND_CONFIG": "value"
      }
    }
  }
}
```

### Development Mode

For development with auto-reload:

```json
{
  "mcpServers": {
    "admz-dev": {
      "command": "python",
      "args": ["-m", "admz", "mcp"],
      "cwd": "/path/to/AxisSecrets",
      "env": {
        "PYTHONUNBUFFERED": "1",
        "LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

### Multiple Environments

Configure different servers for different environments:

```json
{
  "mcpServers": {
    "admz-prod": {
      "command": "python",
      "args": ["-m", "admz", "mcp"],
      "cwd": "/path/to/AxisSecrets",
      "env": {
        "VAULT_ADDR": "https://vault.prod.example.com",
        "VAULT_PATH_PREFIX": "prod-devices"
      }
    },
    "admz-staging": {
      "command": "python",
      "args": ["-m", "admz", "mcp"],
      "cwd": "/path/to/AxisSecrets",
      "env": {
        "VAULT_ADDR": "https://vault.staging.example.com",
        "VAULT_PATH_PREFIX": "staging-devices"
      }
    }
  }
}
```

## Getting Help

- **Documentation**: `/path/to/AxisSecrets/docs/`
- **Issues**: Report issues on your project repository
- **MCP Protocol**: https://modelcontextprotocol.io/

## Contributing

To extend the MCP server with new tools:

1. Add tool definition to `list_tools()` in `/mnt/c/AxisSecrets/admz/mcp/server.py`
2. Implement handler method (e.g., `_my_new_tool()`)
3. Add routing in `call_tool()`
4. Update this documentation

## License

See the main project LICENSE file.
