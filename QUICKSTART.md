# Quick Start Guide

Get started with ADMZ (Axis Device Manager) in 5 minutes!

## Prerequisites

- Python 3.8+
- HashiCorp Vault server (or Docker)
- Axis devices to manage

## Step 1: Start Vault (Development)

```bash
# Option A: Use Docker
docker run --cap-add=IPC_LOCK -d --name=vault -p 8200:8200 \
  -e 'VAULT_DEV_ROOT_TOKEN_ID=myroot' \
  hashicorp/vault:latest

export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='myroot'

# Option B: Install Vault locally
# Download from https://www.vaultproject.io/downloads
vault server -dev
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='<root-token-from-output>'
```

## Step 2: Install ADMZ

```bash
# Clone repository
git clone https://github.com/yourusername/admz.git
cd admz

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Step 3: Set Up Example Devices

```bash
# Run the setup script
bash scripts/setup_vault_example.sh

# This will:
# - Configure Vault policies
# - Create AppRole credentials
# - Add two example devices (front-door, parking-1)
# - Display credentials for your application
```

Save the VAULT_ROLE_ID and VAULT_SECRET_ID from the output!

## Step 4: Start the FastAPI Server

```bash
# Set Vault credentials
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='your-token'

# Start the FastAPI server
cd admz
uvicorn api.main:app --reload --port 8000

# Server will be available at:
# - API: http://localhost:8000
# - Interactive docs: http://localhost:8000/docs
# - OpenAPI spec: http://localhost:8000/openapi.json
```

## Step 5: Test the REST API

```bash
# List all devices
curl http://localhost:8000/devices

# Get device information
curl http://localhost:8000/devices/front-door

# Get device by nickname
curl http://localhost:8000/devices/by-nickname/Main%20Entrance

# Get credentials (requires authentication)
curl http://localhost:8000/devices/front-door/accounts/aoa-agent/credentials

# List accounts for a device
curl http://localhost:8000/devices/front-door/accounts

# Health check
curl http://localhost:8000/health
```

## Step 6: Set Up MCP Server (Optional)

Configure the MCP server in your Claude Code config:

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

See [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) for complete MCP setup.

## Step 7: Use in Your Application (Python API)

```python
from admz import create_device_registry

# Create registry (uses environment variables)
registry = create_device_registry()

# Get credentials for a device account
creds = registry.get_credentials(
    device_id='front-door',
    account_id='aoa-agent'
)

# Use credentials with Axis device
print(f"Connect to {creds['host']} with {creds['username']}")
```

## Next Steps

### Add Your Own Devices

```python
from admz import create_device_registry

registry = create_device_registry()

# Add a device
registry.add_device(
    device_id='my-device',
    device_info={
        'host': '192.168.1.100',
        'ip_address': '192.168.1.100',
        'serial_number': 'ACCC12345678',
        'model': 'AXIS P3245-LVE',
        'location': 'My Location',
        'nickname': 'Lobby Camera',
    },
    accounts={
        'aoa-agent': {
            'username': 'aoa_user',
            'password': 'secure_password',
            'account_type': 'service',
            'purpose': 'AOA configuration',
        }
    }
)
```

### Use with FastAPI

The REST API supports all CRUD operations:

```bash
# Add a device via API
curl -X POST http://localhost:8000/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "my-device",
    "device_info": {
      "host": "192.168.1.100",
      "nickname": "Lobby Camera",
      "model": "AXIS P3245-LVE"
    }
  }'

# Update device nickname
curl -X PUT http://localhost:8000/devices/my-device/nickname \
  -H "Content-Type: application/json" \
  -d '{"nickname": "Main Lobby Camera"}'
```

### Integrate with AI Agents

The MCP server allows AI agents to discover and interact with devices:

Key points:
- LLM only sees device IDs and nicknames, never credentials
- Credentials resolved server-side
- Full audit trail in Vault
- Natural language queries supported

### Run Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with coverage
pytest --cov=axis_secrets --cov-report=html
```

### Production Deployment

For production use:

1. **Set up production Vault**
   - Enable TLS
   - Configure proper authentication (AppRole)
   - Set up audit logging
   - See `docs/VAULT_SETUP.md`

2. **Configure access control**
   - Create separate policies for each application
   - Use principle of least privilege
   - Example policies in `docs/VAULT_SETUP.md`

3. **Set environment variables**
   ```bash
   export VAULT_ADDR='https://vault.company.com'
   export VAULT_ROLE_ID='<production-role-id>'
   export VAULT_SECRET_ID='<production-secret-id>'
   ```

4. **Update camera passwords**
   - Change all default passwords
   - Use strong, unique passwords
   - Consider password rotation policies

## Troubleshooting

### "Vault address not configured"

```bash
export VAULT_ADDR='http://127.0.0.1:8200'
```

### "Authentication failed"

```bash
# Check your token
vault token lookup

# Or verify AppRole credentials
echo $VAULT_ROLE_ID
echo $VAULT_SECRET_ID
```

### "Permission denied"

- Check that your Vault token/AppRole has the correct policies
- Run `vault token lookup` to see attached policies
- See `docs/VAULT_SETUP.md` for policy examples

### "No cameras found"

- Run `bash scripts/setup_vault_example.sh` to add example cameras
- Or manually add cameras using `examples/manage_cameras.py`

## Getting Help

- **Documentation**: See `AXIS_SECRETS_PROJECT.md` for complete documentation
- **MCP Guide**: See `docs/MCP_INTEGRATION.md` for AI agent integration
- **Migration Guide**: See `docs/MIGRATION.md` for upgrading from v1
- **Examples**: Check the `examples/` directory
- **Issues**: https://github.com/yourusername/admz/issues

## What's Next?

- Explore the FastAPI interactive docs at `http://localhost:8000/docs`
- Set up the MCP server for AI agent integration
- Read the full documentation in `AXIS_SECRETS_PROJECT.md`
- Set up Vault policies for your use case (see `docs/VAULT_SETUP.md`)
- Integrate with your Axis device projects!
