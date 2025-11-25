# ADMZ MCP Server Quick Start

The ADMZ MCP (Model Context Protocol) server enables LLMs like Claude to interact with your device registry through natural language.

## Quick Start

### 1. Install Dependencies

```bash
pip install mcp
```

### 2. Test the Server

```bash
python -m admz mcp
```

You should see:
```
Starting ADMZ MCP server...
MCP server ready for connections
```

Press `Ctrl+C` to stop.

### 3. Configure Claude Code

Edit your MCP configuration file:
- **macOS/Linux**: `~/.config/claude-code/mcp.json`
- **Windows**: `%APPDATA%\claude-code\mcp.json`

Use this template (update paths and credentials):

```json
{
  "mcpServers": {
    "admz": {
      "command": "python",
      "args": ["-m", "admz", "mcp"],
      "cwd": "/mnt/c/AxisSecrets",
      "env": {
        "VAULT_ADDR": "https://vault.example.com",
        "VAULT_TOKEN": "your-vault-token-here"
      }
    }
  }
}
```

See `scripts/mcp-config.json` for a complete example.

### 4. Restart Claude Code

Restart Claude Code to load the new configuration.

### 5. Try It Out

Ask Claude things like:
- "List all devices in the ADMZ registry"
- "Show me outdoor cameras in Building A"
- "Get the credentials for the front door camera"
- "Register a new device called lobby-cam at 192.168.1.150"

## Available Tools

The MCP server provides 10 tools:

1. **list_devices** - List all devices
2. **get_device** - Get device by ID/nickname
3. **search_devices** - Search by tags/location/model
4. **list_accounts** - List accounts for a device
5. **get_credentials** - Get device credentials
6. **register_device** - Add new device
7. **add_account** - Add account to device
8. **update_device** - Update device info
9. **delete_device** - Remove device
10. **delete_account** - Remove account

## Full Documentation

See [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) for:
- Detailed tool documentation
- Usage examples
- Security considerations
- Troubleshooting guide
- Advanced configuration

## Architecture

```
Claude Code (or other MCP client)
    ↓
MCP Protocol (stdio transport)
    ↓
ADMZ MCP Server (admz/mcp/server.py)
    ↓
Device Registry (admz/device_registry.py)
    ↓
Backend (Vault, etc.)
```

## Security Note

The MCP server can retrieve sensitive credentials. Always:
- Use secure Vault tokens with appropriate policies
- Enable audit logging
- Use least-privilege access controls
- Monitor credential access

## Support

- Documentation: `docs/MCP_INTEGRATION.md`
- Example Config: `scripts/mcp-config.json`
- Issues: Report on project repository

## License

See LICENSE file.
