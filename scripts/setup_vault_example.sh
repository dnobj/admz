#!/bin/bash
#
# Example script to set up Vault for Axis Secrets
# This is a demonstration - customize for your environment
#

set -e

echo "=== Axis Secrets Vault Setup ==="
echo

# Check if Vault is available
if ! command -v vault &> /dev/null; then
    echo "Error: vault command not found. Please install Vault first."
    exit 1
fi

# Check if VAULT_ADDR is set
if [ -z "$VAULT_ADDR" ]; then
    echo "Error: VAULT_ADDR environment variable not set"
    echo "Example: export VAULT_ADDR='http://127.0.0.1:8200'"
    exit 1
fi

# Check if VAULT_TOKEN is set
if [ -z "$VAULT_TOKEN" ]; then
    echo "Error: VAULT_TOKEN environment variable not set"
    exit 1
fi

echo "Vault Address: $VAULT_ADDR"
echo

# Step 1: Enable KV v2 secrets engine
echo "Step 1: Enabling KV v2 secrets engine..."
vault secrets enable -version=2 -path=secret kv 2>/dev/null || echo "  (already enabled)"
echo "  ✓ KV v2 enabled at 'secret/'"
echo

# Step 2: Create policies
echo "Step 2: Creating policies..."

# AOA Agent policy
cat > /tmp/aoa-agent-policy.hcl <<EOF
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

vault policy write aoa-agent /tmp/aoa-agent-policy.hcl
echo "  ✓ Created aoa-agent policy"

# Admin policy
cat > /tmp/camera-admin-policy.hcl <<EOF
# Full access to all camera paths
path "secret/data/cameras/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/cameras/*" {
  capabilities = ["list", "read", "delete"]
}
EOF

vault policy write camera-admin /tmp/camera-admin-policy.hcl
echo "  ✓ Created camera-admin policy"
echo

# Step 3: Enable AppRole auth
echo "Step 3: Enabling AppRole authentication..."
vault auth enable approle 2>/dev/null || echo "  (already enabled)"

# Create AppRole for AOA agent
vault write auth/approle/role/aoa-agent \
    token_policies="aoa-agent" \
    token_ttl=1h \
    token_max_ttl=4h \
    > /dev/null

echo "  ✓ Created aoa-agent AppRole"
echo

# Get Role ID and Secret ID
echo "Step 4: Generating credentials..."
ROLE_ID=$(vault read -field=role_id auth/approle/role/aoa-agent/role-id)
SECRET_ID=$(vault write -field=secret_id -f auth/approle/role/aoa-agent/secret-id)

echo "  ✓ Generated AppRole credentials"
echo
echo "  Save these credentials (treat Secret ID like a password):"
echo "  ----------------------------------------"
echo "  export VAULT_ROLE_ID='$ROLE_ID'"
echo "  export VAULT_SECRET_ID='$SECRET_ID'"
echo "  ----------------------------------------"
echo

# Step 5: Add example cameras
echo "Step 5: Adding example cameras..."

# Camera 1: front-door
vault kv put secret/cameras/front-door/device_info \
    host=192.168.1.10 \
    ip_address=192.168.1.10 \
    serial_number=ACCC12345678 \
    mac_address="AC:CC:8E:12:34:56" \
    firmware_version=11.8.67 \
    model="AXIS P3245-LVE" \
    warranty_expiration="2026-12-31" \
    location="Main Entrance" \
    tags="entrance,public" \
    > /dev/null

vault kv put secret/cameras/front-door/accounts/aoa-agent \
    username=aoa_agent \
    password=change_me_123 \
    account_type=service \
    purpose="AOA configuration agent" \
    permissions="operator,admin" \
    > /dev/null

vault kv put secret/cameras/front-door/accounts/admin \
    username=root \
    password=change_me_456 \
    account_type=admin \
    purpose="Manual configuration" \
    permissions="administrator" \
    > /dev/null

echo "  ✓ Added camera: front-door"

# Camera 2: parking-1
vault kv put secret/cameras/parking-1/device_info \
    host=192.168.1.11 \
    ip_address=192.168.1.11 \
    serial_number=ACCC87654321 \
    mac_address="AC:CC:8E:87:65:43" \
    firmware_version=11.8.67 \
    model="AXIS Q1656-LE" \
    warranty_expiration="2025-06-15" \
    location="Parking Lot A" \
    tags="parking,vehicle-detection" \
    > /dev/null

vault kv put secret/cameras/parking-1/accounts/aoa-agent \
    username=aoa_agent \
    password=change_me_789 \
    account_type=service \
    purpose="AOA configuration agent" \
    permissions="operator" \
    > /dev/null

vault kv put secret/cameras/parking-1/accounts/admin \
    username=root \
    password=change_me_101 \
    account_type=admin \
    purpose="Administrative access" \
    permissions="administrator" \
    > /dev/null

echo "  ✓ Added camera: parking-1"
echo

# Step 6: Verify
echo "Step 6: Verifying setup..."
CAMERA_COUNT=$(vault kv list -format=json secret/cameras | jq length)
echo "  ✓ Found $CAMERA_COUNT cameras in Vault"
echo

echo "=== Setup Complete! ==="
echo
echo "Next steps:"
echo "  1. Update the example passwords in Vault"
echo "  2. Configure your application with the AppRole credentials above"
echo "  3. Test connection:"
echo
echo "     export VAULT_ROLE_ID='$ROLE_ID'"
echo "     export VAULT_SECRET_ID='$SECRET_ID'"
echo "     python examples/basic_usage.py"
echo

# Cleanup temp files
rm -f /tmp/aoa-agent-policy.hcl /tmp/camera-admin-policy.hcl
