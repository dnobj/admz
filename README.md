# ADMZ - Axis Device Manager

A production-ready device management and credential system for Axis devices with HashiCorp Vault backend, FastAPI REST API, and MCP integration.

## Features

- **Multi-Account Support**: Manage multiple accounts per device (service accounts, admin accounts, etc.)
- **Device Cataloging**: Track device metadata (serial numbers, firmware, MAC addresses, warranty info, nicknames)
- **Vault-Native**: Built on HashiCorp Vault for enterprise-grade security
- **REST API**: FastAPI-based REST API for device and credential management
- **MCP Integration**: Model Context Protocol server for AI agent integration
- **Access Control**: Fine-grained permissions using Vault policies
- **Audit Logging**: Full audit trail of all credential access
- **Flexible**: Extensible design for future backends (AWS Secrets Manager, Azure Key Vault)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/admz.git
cd admz

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

## Quick Start

### Option 1: FastAPI REST API

```bash
# Set up Vault connection
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='your-token'

# Start the FastAPI server
cd admz
uvicorn api.main:app --reload --port 8000

# API available at: http://localhost:8000
# Interactive docs: http://localhost:8000/docs
```

The REST API provides endpoints for:
- Listing and managing devices
- Adding/removing accounts
- Retrieving credentials securely
- Complete device catalog management
- Health checks and status

See [QUICKSTART.md](QUICKSTART.md) for detailed API examples.

### Option 2: MCP Server (AI Agent Integration)

```bash
# Configure MCP server in your Claude Code config
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

# The MCP server provides AI-accessible tools for:
# - Device discovery and listing
# - Credential retrieval
# - Device information queries
```

See [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) for complete MCP setup.

### Option 3: Python API

```python
from admz import create_device_registry

# Create registry (uses Vault backend)
registry = create_device_registry()

# Get credentials for a specific account
creds = registry.get_credentials(
    device_id='front-door',
    account_id='aoa-agent'
)

# Get device information
device = registry.get_device_info('front-door')
print(f"Device: {device['model']} ({device['nickname']}) at {device['location']}")

# List all devices
devices = registry.list_devices()

# Get device by nickname
device = registry.get_device_by_nickname('Main Entrance Camera')

# List accounts for a device
accounts = registry.list_accounts('front-door')
```

## Configuration

Set environment variables:

```bash
export VAULT_ADDR=https://vault.company.com
export VAULT_TOKEN=hvs.xxxxx
# Or use AppRole authentication
export VAULT_ROLE_ID=your-role-id
export VAULT_SECRET_ID=your-secret-id
```

## Documentation

- [QUICKSTART.md](QUICKSTART.md) - Quick start guide with examples
- [AXIS_SECRETS_PROJECT.md](AXIS_SECRETS_PROJECT.md) - Complete project documentation
- [docs/VAULT_SETUP.md](docs/VAULT_SETUP.md) - Vault configuration guide
- [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) - MCP server integration
- [docs/MIGRATION.md](docs/MIGRATION.md) - Migration guide from v1 to v2

## Migration from v1 to v2

If you're upgrading from an earlier version that used `cameras/*` paths in Vault:

```bash
# Run the migration script (dry-run first)
python scripts/migrate_v1_to_v2.py --dry-run

# Then run the actual migration
python scripts/migrate_v1_to_v2.py
```

See [docs/MIGRATION.md](docs/MIGRATION.md) for complete migration instructions.

## License

MIT License - See LICENSE file
