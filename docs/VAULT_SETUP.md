# HashiCorp Vault Setup Guide

This guide walks through setting up HashiCorp Vault for Axis Secrets.

## Prerequisites

- HashiCorp Vault installed (version 1.12+)
- Admin access to Vault
- Understanding of Vault basics (secrets engines, policies)

## Quick Start (Development)

For local development, start a Vault dev server:

```bash
# Start Vault in dev mode (NOT for production!)
vault server -dev

# In another terminal, set environment variables
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='<root-token-from-dev-server>'

# Verify connection
vault status
```

## Production Setup

### Step 1: Enable KV Secrets Engine

```bash
# Enable KV v2 secrets engine at 'secret' mount point
vault secrets enable -version=2 -path=secret kv

# Verify it's enabled
vault secrets list
```

### Step 2: Create Policies for Applications

#### Policy for AOA Agent (Read-Only for aoa-agent accounts)

```bash
# Create policy file: aoa-agent-policy.hcl
cat > aoa-agent-policy.hcl <<EOF
# Allow reading aoa-agent account credentials
path "secret/data/cameras/*/accounts/aoa-agent" {
  capabilities = ["read"]
}

# Allow listing cameras
path "secret/metadata/cameras/*" {
  capabilities = ["list"]
}

# Allow reading device info
path "secret/data/cameras/*/device_info" {
  capabilities = ["read"]
}
EOF

# Upload policy to Vault
vault policy write aoa-agent aoa-agent-policy.hcl
```

#### Policy for Admin Users (Full Access)

```bash
# Create policy file: admin-policy.hcl
cat > admin-policy.hcl <<EOF
# Full access to all camera paths
path "secret/data/cameras/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/cameras/*" {
  capabilities = ["list", "read", "delete"]
}
EOF

# Upload policy to Vault
vault policy write camera-admin admin-policy.hcl
```

#### Policy for Backup Service (Read-Only for backup-service accounts)

```bash
# Create policy file: backup-service-policy.hcl
cat > backup-service-policy.hcl <<EOF
# Allow reading backup-service account credentials
path "secret/data/cameras/*/accounts/backup-service" {
  capabilities = ["read"]
}

# Allow reading device info
path "secret/data/cameras/*/device_info" {
  capabilities = ["read"]
}
EOF

# Upload policy to Vault
vault policy write backup-service backup-service-policy.hcl
```

### Step 3: Create AppRoles for Applications

#### AppRole for AOA Agent

```bash
# Enable AppRole auth method
vault auth enable approle

# Create AppRole for AOA agent
vault write auth/approle/role/aoa-agent \
    token_policies="aoa-agent" \
    token_ttl=1h \
    token_max_ttl=4h

# Get Role ID (like a username)
vault read auth/approle/role/aoa-agent/role-id

# Generate Secret ID (like a password)
vault write -f auth/approle/role/aoa-agent/secret-id

# Save these for your application!
# VAULT_ROLE_ID=<role-id-from-above>
# VAULT_SECRET_ID=<secret-id-from-above>
```

#### AppRole for Backup Service

```bash
# Create AppRole for backup service
vault write auth/approle/role/backup-service \
    token_policies="backup-service" \
    token_ttl=1h \
    token_max_ttl=4h

# Get credentials
vault read auth/approle/role/backup-service/role-id
vault write -f auth/approle/role/backup-service/secret-id
```

### Step 4: Add Cameras to Vault

Use the provided setup script or add manually:

```bash
# Add device info
vault kv put secret/cameras/front-door/device_info \
    host=192.168.1.10 \
    ip_address=192.168.1.10 \
    serial_number=ACCC12345678 \
    mac_address="AC:CC:8E:12:34:56" \
    firmware_version=11.8.67 \
    model="AXIS P3245-LVE" \
    warranty_expiration="2026-12-31" \
    location="Main Entrance" \
    tags="entrance,public"

# Add AOA agent account
vault kv put secret/cameras/front-door/accounts/aoa-agent \
    username=aoa_agent \
    password=secure_password_123 \
    account_type=service \
    purpose="AOA configuration agent" \
    permissions="operator,admin"

# Add admin account
vault kv put secret/cameras/front-door/accounts/admin \
    username=root \
    password=admin_password_456 \
    account_type=admin \
    purpose="Manual configuration" \
    permissions="administrator"

# Verify
vault kv get secret/cameras/front-door/device_info
vault kv get secret/cameras/front-door/accounts/aoa-agent
```

### Step 5: Test Access

```bash
# Login with AOA agent AppRole
vault write auth/approle/login \
    role_id=<aoa-agent-role-id> \
    secret_id=<aoa-agent-secret-id>

# Save the client_token from response
export VAULT_TOKEN=<client-token>

# Test reading credentials
vault kv get secret/cameras/front-door/accounts/aoa-agent

# Should succeed!

# Test reading admin account (should fail - not in policy)
vault kv get secret/cameras/front-door/accounts/admin
# Error: permission denied
```

## Python Application Setup

### Using Token Authentication (Development)

```python
from axis_secrets import create_camera_registry
import os

# Set environment variables
os.environ['VAULT_ADDR'] = 'http://127.0.0.1:8200'
os.environ['VAULT_TOKEN'] = 'hvs.xxxxx'

# Create registry
registry = create_camera_registry()

# Get credentials
creds = registry.get_credentials('front-door', 'aoa-agent')
print(creds)
```

### Using AppRole Authentication (Production)

```python
from axis_secrets import create_camera_registry
import os

# Set environment variables
os.environ['VAULT_ADDR'] = 'https://vault.company.com'
os.environ['VAULT_ROLE_ID'] = 'your-role-id'
os.environ['VAULT_SECRET_ID'] = 'your-secret-id'

# Create registry (will auto-authenticate with AppRole)
registry = create_camera_registry()

# Get credentials
creds = registry.get_credentials('front-door', 'aoa-agent')
```

## Bulk Import Script

See `scripts/import_cameras_to_vault.py` for a script to bulk import cameras from a YAML file.

```bash
# Export cameras to YAML
python scripts/export_vault_template.py > cameras.yaml

# Edit cameras.yaml with your camera data

# Import to Vault
python scripts/import_cameras_to_vault.py cameras.yaml
```

## Security Best Practices

### 1. Use AppRole in Production

Never use root tokens in production. Always use AppRole or other auth methods with limited policies.

### 2. Rotate Secret IDs Regularly

```bash
# Revoke old secret IDs
vault list auth/approle/role/aoa-agent/secret-id

# Generate new secret ID
vault write -f auth/approle/role/aoa-agent/secret-id

# Update application with new secret ID
```

### 3. Enable Audit Logging

```bash
# Enable file audit device
vault audit enable file file_path=/var/log/vault-audit.log

# All secret access will be logged
```

### 4. Use TLS in Production

```bash
# Start Vault with TLS
vault server -config=config.hcl

# config.hcl:
# listener "tcp" {
#   address     = "0.0.0.0:8200"
#   tls_cert_file = "/path/to/cert.pem"
#   tls_key_file  = "/path/to/key.pem"
# }
```

### 5. Least Privilege Principle

Create separate policies for each application, granting only the minimum necessary permissions.

## Troubleshooting

### Authentication Failures

```bash
# Check if Vault is sealed
vault status

# Verify token is valid
vault token lookup

# Test policy
vault policy read aoa-agent
```

### Permission Denied Errors

```bash
# Check which policies are attached to your token
vault token lookup

# Test if you can read a specific path
vault kv get secret/cameras/front-door/device_info

# Check audit logs
tail -f /var/log/vault-audit.log
```

### Connection Issues

```bash
# Verify Vault address
echo $VAULT_ADDR

# Test connection
curl $VAULT_ADDR/v1/sys/health

# Check network/firewall
telnet vault.company.com 8200
```

## Advanced Topics

### Namespace Support (Vault Enterprise)

```bash
# Create namespace for cameras
vault namespace create cameras

# Use namespace in policy paths
export VAULT_NAMESPACE=cameras
```

### Dynamic Secrets (Future Enhancement)

Vault can generate temporary credentials on-demand:

```bash
# Configure camera credentials as dynamic secrets
vault write database/config/axis-cameras \
    plugin_name=... \
    connection_url=... \
    allowed_roles="readonly"

# Request temporary credentials (15 min TTL)
vault read database/creds/readonly
```

### Secret Rotation

```bash
# Rotate credentials for an account
NEW_PASSWORD=$(openssl rand -base64 32)

# Update in Vault
vault kv patch secret/cameras/front-door/accounts/aoa-agent \
    password="$NEW_PASSWORD"

# Update on camera (use Axis API)
# ... camera update logic ...

# Verify
vault kv get secret/cameras/front-door/accounts/aoa-agent
```

## Support

For issues with Vault setup, consult:
- [Vault Documentation](https://www.vaultproject.io/docs)
- [Vault GitHub Issues](https://github.com/hashicorp/vault/issues)
- Project issues: https://github.com/yourusername/axis-secrets/issues
