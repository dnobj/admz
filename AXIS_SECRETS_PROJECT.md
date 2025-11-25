# ADMZ - Axis Device Manager

A production-ready device management and credential system for Axis devices with HashiCorp Vault backend, FastAPI REST API, and MCP integration.

## Overview

**ADMZ (Axis Device Manager)** provides a comprehensive solution for managing Axis device credentials, metadata, and access across multiple projects and hundreds of devices. Built on HashiCorp Vault for enterprise-grade security, ADMZ includes a FastAPI REST API and Model Context Protocol (MCP) server for seamless AI agent integration.

### Design Philosophy

1. **Vault-Native**: Built on HashiCorp Vault for enterprise-grade secrets management
2. **Security-first**: Credentials never exposed to LLMs or application logs
3. **Scalable**: Designed to manage from 1 to 1000+ devices
4. **API-driven**: FastAPI REST API for language-agnostic integration
5. **AI-ready**: MCP server for seamless AI agent integration
6. **Multi-project**: Single credential store shared across all Axis device projects

## Problem Statement

When building AI agents and automation tools for Axis devices, you need:

- **Credential Management**: Store IP, username, password for each device
- **Device Cataloging**: Track metadata (model, location, firmware, nicknames)
- **Scale**: Handle dozens to hundreds of devices
- **Security**: Never pass credentials to LLMs as tool parameters
- **Rotation**: Update passwords without redeploying applications
- **Audit**: Track who accessed which device credentials when
- **Multi-project**: Share credentials across MCP servers, agents, automation scripts
- **API Access**: RESTful API for non-Python integrations

Current approaches don't scale:
- ❌ Hardcoded credentials: Insecure, doesn't scale
- ❌ Individual .env files: Management nightmare at scale
- ❌ Passing credentials as parameters: Exposes to LLMs and logs
- ❌ Database without encryption: Security risk
- ❌ No API: Limited to Python-only integration

**ADMZ solves this** with a Vault-backed system, REST API, and MCP integration.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│  (AI Agents, MCP Clients, Web Apps, Scripts, etc.)          │
└──────────────────────┬───────────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
    ┌─────────┐  ┌─────────┐  ┌──────────┐
    │   MCP   │  │FastAPI  │  │ Python   │
    │ Server  │  │REST API │  │   API    │
    └────┬────┘  └────┬────┘  └────┬─────┘
         │            │            │
         └────────────┼────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │   ADMZ Core Library    │
         │  • DeviceRegistry      │
         │  • get_credentials()   │
         │  • list_devices()      │
         │  • get_device_info()   │
         └───────────┬────────────┘
                     │
                     ▼
         ┌────────────────────────┐
         │  HashiCorp Vault       │
         │  KV v2 Secrets Engine  │
         │  secret/devices/*      │
         └────────────────────────┘
```

### Key Components

#### 1. Core Library: DeviceRegistry Interface

```python
class DeviceRegistry(ABC):
    @abstractmethod
    def get_credentials(
        device_id: str,
        account_id: str = 'default',
        requester: str = None
    ) -> dict

    @abstractmethod
    def get_device_info(device_id: str) -> dict

    @abstractmethod
    def list_devices() -> list

    @abstractmethod
    def list_accounts(device_id: str) -> list

    @abstractmethod
    def device_exists(device_id: str) -> bool

    @abstractmethod
    def account_exists(device_id: str, account_id: str) -> bool

    @abstractmethod
    def get_device_by_nickname(nickname: str) -> Optional[dict]
```

#### 2. FastAPI REST API

Production-ready REST API for device management:

**Key Endpoints:**
- `GET /devices` - List all devices
- `GET /devices/{device_id}` - Get device information
- `GET /devices/by-nickname/{nickname}` - Get device by nickname
- `GET /devices/{device_id}/accounts` - List accounts for device
- `GET /devices/{device_id}/accounts/{account_id}/credentials` - Get credentials
- `POST /devices` - Add new device
- `PUT /devices/{device_id}/nickname` - Update device nickname
- `DELETE /devices/{device_id}` - Remove device
- `GET /health` - Health check endpoint

**Features:**
- OpenAPI documentation at `/docs`
- Automatic request validation
- Error handling and logging
- CORS support for web clients
- Async/await for performance

#### 3. MCP Server

Model Context Protocol server for AI agent integration:

**MCP Tools:**
- `list_devices` - List available devices
- `get_device_info` - Get device details
- `get_credentials` - Retrieve credentials
- `search_devices_by_tag` - Search by tags

**Features:**
- Zero credential exposure to LLMs
- Server-side credential resolution
- Full Vault audit trail
- Natural language device discovery

See [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) for complete documentation.

#### 4. HashiCorp Vault Backend

Enterprise-grade secrets management with multi-account support:

```yaml
# cameras.yaml
cameras:
  front-door:
    # Device information and metadata
    device_info:
      host: 192.168.1.10
      ip_address: 192.168.1.10
      serial_number: "ACCC12345678"
      mac_address: "AC:CC:8E:12:34:56"
      firmware_version: "11.8.67"
      model: "AXIS P3245-LVE"
      warranty_expiration: "2026-12-31"

    # Network configuration
    network:
      vlan: "VLAN_100"
      subnet: "192.168.1.0/24"

    # Location and organizational metadata
    location: "Main Entrance"
    tags: ["entrance", "public"]

    # Multiple accounts per device
    accounts:
      vault-service:
        username: vault_svc
        password: ${FRONT_DOOR_VAULT_SVC_PASS}
        account_type: service
        purpose: "Vault-managed automation account"
        permissions: ["operator"]

      aoa-agent:
        username: aoa_agent
        password: ${FRONT_DOOR_AOA_PASS}
        account_type: service
        purpose: "AOA configuration agent"
        permissions: ["operator", "admin"]

      admin:
        username: root
        password: ${FRONT_DOOR_ADMIN_PASS}
        account_type: admin
        purpose: "Manual configuration and troubleshooting"
        permissions: ["administrator"]

  parking-1:
    device_info:
      host: 192.168.1.11
      ip_address: 192.168.1.11
      serial_number: "ACCC87654321"
      mac_address: "AC:CC:8E:87:65:43"
      firmware_version: "11.8.67"
      model: "AXIS Q1656-LE"
      warranty_expiration: "2025-06-15"

    network:
      vlan: "VLAN_200"
      subnet: "192.168.1.0/24"

    location: "Parking Lot A"
    tags: ["parking", "vehicle-detection"]

    accounts:
      backup-service:
        username: backup_svc
        password: ${PARKING_1_BACKUP_PASS}
        account_type: service
        purpose: "Automated backup service"
        permissions: ["viewer"]

      admin:
        username: root
        password: ${PARKING_1_ADMIN_PASS}
        account_type: admin
        purpose: "Administrative access"
        permissions: ["administrator"]
```

**Features:**
- ✅ Environment variable substitution for passwords
- ✅ File-based, easy to edit
- ✅ Git-friendly (credentials in env vars, not in file)
- ✅ Fast local development
- ⚠️ No audit logging
- ⚠️ No automatic rotation
- ⚠️ No access control

Enterprise-grade secrets management with multi-account support:

```bash
# Store device info (no secrets)
vault kv put secret/devices/front-door/device_info \
    host=192.168.1.10 \
    ip_address=192.168.1.10 \
    serial_number=ACCC12345678 \
    mac_address=AC:CC:8E:12:34:56 \
    firmware_version=11.8.67 \
    model="AXIS P3245-LVE" \
    nickname="Main Entrance Camera" \
    location="Main Entrance" \
    tags="entrance,public"

# Store account credentials (separated by account)
vault kv put secret/devices/front-door/accounts/aoa-agent \
    username=aoa_agent \
    password=secret123 \
    account_type=service \
    purpose="AOA configuration agent" \
    permissions="operator,admin"

vault kv put secret/devices/front-door/accounts/admin \
    username=root \
    password=adminpass456 \
    account_type=admin \
    purpose="Manual configuration" \
    permissions="administrator"
```

**Vault Path Structure (v2):**
```
secret/
└── devices/
    ├── front-door/
    │   ├── device_info          # Device metadata (no credentials)
    │   │                        # Includes: host, model, nickname, location
    │   └── accounts/
    │       ├── aoa-agent         # Account credentials
    │       ├── vault-service     # Account credentials
    │       └── admin             # Account credentials
    └── parking-1/
        ├── device_info
        └── accounts/
            ├── backup-service
            └── admin
```

**Note:** The path structure changed from `cameras/*` to `devices/*` in v2. See [docs/MIGRATION.md](docs/MIGRATION.md) for migration instructions.

**Features:**
- ✅ Encryption at rest and in transit
- ✅ Audit logging (who accessed what, when)
- ✅ Access control (IAM policies)
- ✅ Automatic rotation
- ✅ Secret versioning
- ✅ Temporary credentials (leased access)
- ✅ Compliance ready (SOC2, HIPAA, PCI-DSS)

#### 4. Factory Pattern

```python
# Auto-detect backend from environment
registry = create_camera_registry()

# Or specify explicitly
registry = create_camera_registry('yaml')
registry = create_camera_registry('vault')
```

## Integration with Axis AOA Agent

The **axis-aoa-agent** project uses Axis Secrets to manage camera credentials:

### Before (Credentials as Parameters)

```python
# ❌ Credentials visible to LLM
@mcp.tool()
def list_scenarios(
    camera_host: str,      # Exposed to LLM
    camera_username: str,  # Exposed to LLM
    camera_password: str   # Exposed to LLM! Security risk!
):
    client = AOAClient(camera_host, camera_username, camera_password)
    return client.list_scenarios()
```

**Problems:**
- Credentials in LLM prompts and logs
- Must store credentials in agent code or config
- Hard to manage at scale

### After (Using Axis Secrets)

```python
# ✅ Only camera ID exposed to LLM
from axis_secrets import create_camera_registry

registry = create_camera_registry()

@mcp.tool()
def list_scenarios(camera_id: str):  # Just an identifier!
    # Resolve credentials server-side (never exposed to LLM)
    creds = registry.get_credentials(camera_id)

    client = AOAClient(
        host=creds['host'],
        username=creds['username'],
        password=creds['password']
    )

    return client.list_scenarios()
```

**LLM sees:**
```
"List scenarios for front-door camera"
  ↓
Tool call: list_scenarios(camera_id="front-door")
  ↓
Server resolves: 192.168.1.10 / root / secret123
  ↓
Returns scenario list
```

**Benefits:**
- ✅ Credentials never in LLM context
- ✅ Audit trail of camera access
- ✅ Centralized credential management
- ✅ Easy to rotate passwords

### MCP Resource for Camera Discovery

```python
@mcp.resource("aoa://cameras/list")
def cameras_resource():
    """List available cameras (LLM can discover cameras)"""
    cameras = registry.list_cameras()  # No passwords!
    return json.dumps(cameras)
```

LLM response:
```json
[
  {
    "id": "front-door",
    "location": "Main Entrance",
    "host": "192.168.1.10",
    "tags": ["entrance", "public"]
  },
  {
    "id": "parking-1",
    "location": "Parking Lot A",
    "tags": ["parking", "vehicle-detection"]
  }
]
```

## Multi-Project Support

Axis Secrets is designed to be used by **multiple projects**, not just AOA configuration:

### Example Projects Using Axis Secrets

#### 1. Axis AOA Agent (Object Analytics)
```python
from axis_secrets import create_camera_registry
from aoa_config import AOAClient

registry = create_camera_registry()
creds = registry.get_credentials('front-door')
client = AOAClient(**creds)
client.create_motion_scenario(...)
```

#### 2. Axis VMS Tools (Video Management)
```python
from axis_secrets import create_camera_registry
import requests

registry = create_camera_registry()
creds = registry.get_credentials('parking-1')

# Control PTZ
response = requests.get(
    f"http://{creds['host']}/axis-cgi/com/ptz.cgi",
    auth=(creds['username'], creds['password']),
    params={'pan': 90, 'tilt': 45}
)
```

#### 3. Axis Analytics Pipeline (Event Processing)
```python
from axis_secrets import create_camera_registry

registry = create_camera_registry()

# Process events from multiple cameras
for camera_info in registry.list_cameras():
    if 'analytics' in camera_info['tags']:
        creds = registry.get_credentials(camera_info['id'])
        subscribe_to_events(creds)
```

#### 4. Axis Backup Service (Snapshot/Recording)
```python
from axis_secrets import create_camera_registry

registry = create_camera_registry()

# Backup all parking lot cameras
parking_cameras = [
    cam for cam in registry.list_cameras()
    if 'parking' in cam['tags']
]

for camera in parking_cameras:
    creds = registry.get_credentials(camera['id'])
    create_snapshot(creds)
```

### Shared Credential Store

All projects share the same credential store:

```
┌─────────────────────────────────────────┐
│      Axis Secrets (Central Store)      │
│                                         │
│  cameras.yaml  OR  HashiCorp Vault      │
└────────────┬────────────────────────────┘
             │
   ┌─────────┼─────────┬─────────┬────────┐
   │         │         │         │        │
   ▼         ▼         ▼         ▼        ▼
 AOA      VMS      Analytics  Backup   Custom
Agent    Tools    Pipeline   Service   Tools
```

**Benefits:**
- Single source of truth for credentials
- Update password once, all projects get it
- Centralized audit logging
- Consistent tagging and metadata

## Implementation Phases

### Phase 1: Complete ✅

**Status**: COMPLETE

**Deliverables:**
1. ✅ Abstract `DeviceRegistry` interface with multi-account support
2. ✅ `VaultDeviceRegistry` implementation
3. ✅ AppRole and Token authentication support
4. ✅ Multi-account credential management
5. ✅ Device catalog with nicknames
6. ✅ FastAPI REST API with OpenAPI docs
7. ✅ MCP server for AI agent integration
8. ✅ Vault setup documentation and scripts
9. ✅ Migration script (v1 to v2)
10. ✅ Comprehensive documentation

**Features:**
- Production-ready Vault backend
- RESTful API for device management
- MCP server for AI agents
- Device nicknames for easy identification
- Multi-account credential management
- Full audit logging via Vault
- Migration tools for v1 users

### Phase 2: Advanced Features (Future Roadmap)

**Planned enhancements:**
1. Web UI for device registry management
2. AWS Secrets Manager backend support
3. Azure Key Vault backend support
4. Credential rotation automation
5. Temporary access (time-limited credentials)
6. Enhanced RBAC with custom policies
7. CLI tool for device management
8. Webhook notifications for credential changes
9. Integration with Axis device discovery
10. Bulk device import/export tools

## Migration Path

### Development → Production

**Development (YAML):**
```bash
# .env
CAMERA_REGISTRY_BACKEND=yaml
CAMERA_REGISTRY_FILE=cameras.yaml

# cameras.yaml
cameras:
  cam1:
    host: 192.168.1.10
    username: root
    password: ${CAM1_PASS}
```

**Production (Vault):**
```bash
# .env
CAMERA_REGISTRY_BACKEND=vault
VAULT_ADDR=https://vault.company.com
VAULT_TOKEN=<service-token>

# Vault (one-time migration)
vault kv put secret/cameras/cam1 \
    host=192.168.1.10 \
    username=root \
    password=secret123
```

**Application code: UNCHANGED!**

```python
# Same code works with both backends
registry = create_camera_registry()
creds = registry.get_credentials('cam1')
```

## Security Model

### YAML Backend Security

**Threats mitigated:**
- ✅ Passwords not in version control (env vars)
- ✅ File permissions restrict access
- ✅ Credentials never in application logs

**Limitations:**
- ⚠️ No encryption at rest
- ⚠️ No audit logging
- ⚠️ File-based access control only

### Vault Backend Security

**Threats mitigated:**
- ✅ Encryption at rest (AES-256)
- ✅ Encryption in transit (TLS)
- ✅ Audit logging (all access logged)
- ✅ Fine-grained access control (policies)
- ✅ Credential rotation
- ✅ Temporary access (TTL/leases)
- ✅ Emergency revocation

**Compliance:**
- ✅ SOC 2 Type II
- ✅ HIPAA
- ✅ PCI-DSS
- ✅ ISO 27001

## Usage Examples

### Basic Usage

```python
from axis_secrets import create_camera_registry

# Create registry (backend from environment)
registry = create_camera_registry()

# Get credentials
creds = registry.get_credentials('front-door')
print(creds)
# {
#     'host': '192.168.1.10',
#     'username': 'root',
#     'password': 'secret123',
#     'location': 'Main Entrance',
#     'model': 'AXIS Q1656'
# }

# List cameras
cameras = registry.list_cameras()
for camera in cameras:
    print(f"{camera['id']}: {camera['location']} ({camera['host']})")

# Check if camera exists
if registry.camera_exists('parking-1'):
    print("Camera found!")
```

### Integration with AOA Agent

```python
from axis_secrets import create_camera_registry
from aoa_config import AOAClient

registry = create_camera_registry()

def get_aoa_client(camera_id: str) -> AOAClient:
    """Get AOA client for camera by ID"""
    creds = registry.get_credentials(camera_id)
    return AOAClient(
        host=creds['host'],
        username=creds['username'],
        password=creds['password']
    )

# Use in MCP tools
client = get_aoa_client('front-door')
scenarios = client.list_scenarios()
```

### Filtering by Tags

```python
# Get all parking lot cameras
parking_cameras = [
    cam for cam in registry.list_cameras()
    if 'parking' in cam.get('tags', [])
]

for camera in parking_cameras:
    creds = registry.get_credentials(camera['id'])
    process_parking_camera(creds)
```

### Error Handling

```python
try:
    creds = registry.get_credentials('unknown-camera')
except KeyError as e:
    print(f"Camera not found: {e}")
    # Handle missing camera

try:
    registry = create_camera_registry('vault')
except ValueError as e:
    print(f"Vault authentication failed: {e}")
    # Fall back to YAML
    registry = create_camera_registry('yaml')
```

## API Reference

### CameraRegistry Interface

```python
class CameraRegistry(ABC):
    """Abstract interface for camera credential storage"""

    @abstractmethod
    def get_credentials(camera_id: str) -> Dict[str, str]:
        """
        Get camera credentials.

        Args:
            camera_id: Unique camera identifier (e.g., 'front-door')

        Returns:
            Dictionary with keys:
                - host: Camera IP or hostname
                - username: Authentication username
                - password: Authentication password
                - location: (optional) Physical location
                - model: (optional) Camera model
                - tags: (optional) List of tags

        Raises:
            KeyError: Camera not found
        """

    @abstractmethod
    def list_cameras() -> List[Dict[str, str]]:
        """
        List all cameras (without passwords).

        Returns:
            List of camera metadata dictionaries
        """

    @abstractmethod
    def camera_exists(camera_id: str) -> bool:
        """Check if camera is registered"""

    def add_camera(camera_id: str, credentials: Dict[str, str]) -> None:
        """Add or update camera (optional, not all backends support)"""
        raise NotImplementedError("This registry is read-only")

    def remove_camera(camera_id: str) -> None:
        """Remove camera (optional)"""
        raise NotImplementedError("This registry is read-only")
```

### Factory Function

```python
def create_camera_registry(backend: str = None) -> CameraRegistry:
    """
    Create camera registry based on configuration.

    Args:
        backend: 'yaml', 'vault', or None (auto-detect from CAMERA_REGISTRY_BACKEND env)

    Returns:
        CameraRegistry instance

    Environment Variables:
        CAMERA_REGISTRY_BACKEND: Backend type ('yaml' or 'vault')
        CAMERA_REGISTRY_FILE: Path to YAML file (for YAML backend)
        VAULT_ADDR: Vault server URL (for Vault backend)
        VAULT_TOKEN: Vault authentication token (for Vault backend)
        VAULT_MOUNT_POINT: KV mount point (default: 'secret')
        VAULT_PATH_PREFIX: Path prefix for cameras (default: 'cameras')

    Examples:
        # Auto-detect from environment
        registry = create_camera_registry()

        # Explicit backend
        registry = create_camera_registry('yaml')
        registry = create_camera_registry('vault')
    """
```

## Configuration

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `CAMERA_REGISTRY_BACKEND` | Backend type | `yaml` | `vault` |
| `CAMERA_REGISTRY_FILE` | YAML config file path | `cameras.yaml` | `/etc/cameras.yaml` |
| `VAULT_ADDR` | Vault server URL | `http://localhost:8200` | `https://vault.company.com` |
| `VAULT_TOKEN` | Vault auth token | (none) | `hvs.xxxxx` |
| `VAULT_MOUNT_POINT` | KV secrets mount | `secret` | `cameras-kv` |
| `VAULT_PATH_PREFIX` | Path prefix in Vault | `cameras` | `axis/cameras` |

### YAML Configuration Format

```yaml
cameras:
  <camera-id>:
    host: <ip-or-hostname>
    username: <auth-username>
    password: <password-or-env-var>
    location: <optional-description>
    model: <optional-model-name>
    tags:
      - <tag1>
      - <tag2>
```

**Example:**
```yaml
cameras:
  lobby-main:
    host: 192.168.1.50
    username: root
    password: ${LOBBY_MAIN_PASS}
    location: "Main Lobby - North Wall"
    model: "AXIS P3245-LVE"
    tags: ["entrance", "lobby", "facial-recognition"]

  warehouse-bay-3:
    host: 10.0.2.15
    username: operator
    password: ${WH_BAY3_PASS}
    location: "Warehouse - Loading Bay 3"
    model: "AXIS Q1656-LE"
    tags: ["warehouse", "vehicle-detection", "loading-bay"]
```

## Repository Structure

```
axis-secrets/
├── README.md
├── LICENSE
├── setup.py
├── requirements.txt
├── .gitignore
├── axis_secrets/
│   ├── __init__.py
│   ├── camera_registry.py       # Abstract interface
│   ├── factory.py                # create_camera_registry()
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── yaml_backend.py       # YAMLCameraRegistry
│   │   └── vault_backend.py      # VaultCameraRegistry
│   └── exceptions.py
├── tests/
│   ├── test_yaml_backend.py
│   ├── test_vault_backend.py
│   └── test_factory.py
├── examples/
│   ├── basic_usage.py
│   ├── aoa_integration.py
│   └── multi_project.py
└── docs/
    ├── YAML_SETUP.md
    ├── VAULT_SETUP.md
    └── MIGRATION_GUIDE.md
```

## Installation

### From PyPI (Future)

```bash
pip install axis-secrets
```

### From Source

```bash
git clone https://github.com/yourusername/axis-secrets.git
cd axis-secrets
pip install -e .
```

### Dependencies

**YAML Backend:**
```
PyYAML>=6.0
```

**Vault Backend:**
```
hvac>=1.1.0
```

## Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with coverage
pytest --cov=axis_secrets --cov-report=html

# Test YAML backend only
pytest tests/test_yaml_backend.py

# Test Vault backend (requires Vault server)
pytest tests/test_vault_backend.py
```

## Contributing

Contributions welcome! Areas of interest:

1. Additional backends (AWS Secrets Manager, Azure Key Vault)
2. Credential rotation automation
3. CLI tool for camera management
4. Web UI for registry administration
5. Advanced filtering and search
6. Performance optimizations
7. Documentation improvements

## License

MIT License - See LICENSE file

## Related Projects

- **axis-aoa-agent**: AI agent for Axis Object Analytics configuration
- **axis-vms-tools**: Video management system utilities
- **axis-analytics-pipeline**: Event processing and analytics
- Future: axis-ptz-controller, axis-backup-service, axis-firmware-manager

## Version History

### v2.0.0 (ADMZ - Current)
- Rebranded as ADMZ (Axis Device Manager)
- Changed vault paths: `cameras/*` → `devices/*`
- Added device nicknames
- FastAPI REST API with OpenAPI docs
- MCP server for AI agent integration
- Migration script for v1 users
- Enhanced documentation

### v1.0.0 (Legacy)
- Initial release as "Axis Secrets"
- Vault backend with `cameras/*` paths
- Basic Python API
- Multi-account support

## Support

- Issues: https://github.com/yourusername/admz/issues
- Documentation: See [README.md](README.md) and [docs/](docs/)
- Migration Guide: [docs/MIGRATION.md](docs/MIGRATION.md)
- MCP Integration: [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md)
- Discussions: https://github.com/yourusername/admz/discussions

---

**ADMZ: Production-ready device management with Vault, FastAPI, and MCP integration.**
