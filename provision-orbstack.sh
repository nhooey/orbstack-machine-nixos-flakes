#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# OrbStack NixOS Provisioning Script
# ============================================================================
# This script creates and provisions a NixOS machine in OrbStack from a flake.
#
# Usage: ./provision-orbstack.sh <machine-name> [arch] [flake-attr] [hostname]
#   machine-name: Required. Name of the OrbStack machine to create.
#   arch:         Optional. Architecture: aarch64 or x86_64 (default: aarch64)
#   flake-attr:   Optional. Flake attribute to build (default: default)
#   hostname:     Optional. Hostname to set (default: same as machine-name)
# ============================================================================

# Flake repository - can be a GitHub URL or local path
# Examples:
#   - github:nhooey/orbstack-nixos-bootstrap
#   - /path/to/local/flake
#   - . (current directory - for local testing)
readonly FLAKE_REPO="github:nhooey/orbstack-nixos-bootstrap"

# Parse arguments
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <machine-name> [arch] [flake-attr] [hostname]" >&2
    echo "  arch: aarch64 (default) or x86_64" >&2
    echo "  flake-attr: default (default)" >&2
    echo "  hostname: defaults to machine-name" >&2
    exit 1
fi

readonly MACHINE_NAME="$1"
readonly ARCH="${2:-aarch64}"
readonly FLAKE_ATTR="${3:-default}"
readonly HOSTNAME="${4:-$MACHINE_NAME}"

# Validate and map architecture
case "$ARCH" in
    aarch64|arm64)
        readonly ORB_ARCH="arm64"
        readonly NIX_SYSTEM="aarch64"
        ;;
    x86_64|amd64)
        readonly ORB_ARCH="amd64"
        readonly NIX_SYSTEM="x86_64"
        ;;
    *)
        echo "Error: Invalid architecture '$ARCH'. Use aarch64/arm64 or x86_64/amd64." >&2
        exit 1
        ;;
esac

# ============================================================================
# Step 1: Create OrbStack machine
# ============================================================================
echo "==> Creating OrbStack NixOS machine: $MACHINE_NAME (arch: $NIX_SYSTEM)"
if orb list | grep -q "^$MACHINE_NAME\\s"; then
    echo "    Machine '$MACHINE_NAME' already exists. Skipping creation."
else
    orb create nixos:25.11 "$MACHINE_NAME" --arch "$ORB_ARCH"
fi

# ============================================================================
# Step 2: Wait for machine to be ready
# ============================================================================
echo "==> Waiting for machine to become SSH-ready..."
readonly MAX_WAIT=60
elapsed=0
while [[ $elapsed -lt $MAX_WAIT ]]; do
    if orb list | grep "^$MACHINE_NAME\\s" | grep -q "running"; then
        # Give SSH daemon a moment to fully initialize
        sleep 2
        break
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done

if [[ $elapsed -ge $MAX_WAIT ]]; then
    echo "Error: Machine did not become ready within $MAX_WAIT seconds." >&2
    exit 1
fi
echo "    Machine is ready."

# ============================================================================
# Step 3: Copy flake files to machine (if using local flake)
# ============================================================================
if [[ "$FLAKE_REPO" != github:* && "$FLAKE_REPO" != git+* ]]; then
    echo "==> Copying local flake files to machine..."
    # Copy flake files to the machine
    orb push -m "$MACHINE_NAME" "$FLAKE_REPO/flake.nix" "$FLAKE_REPO/flake.lock" "$FLAKE_REPO/configuration.nix" .
    # Get the user's home directory in the VM
    readonly VM_HOME=$(orb -m "$MACHINE_NAME" bash -c 'echo $HOME')
    readonly FLAKE_PATH="$VM_HOME"
else
    readonly FLAKE_PATH="$FLAKE_REPO"
fi

readonly FLAKE_REF="${FLAKE_PATH}#${FLAKE_ATTR}"

# ============================================================================
# Step 4: Bootstrap Nix flakes and rebuild system
# ============================================================================
echo "==> Bootstrapping NixOS configuration from flake..."
orb -m "$MACHINE_NAME" bash <<EOF
set -euo pipefail

# Run nixos-rebuild with environment variables and enable flakes via NIX_CONFIG
echo "Running nixos-rebuild switch..."
export NIXOS_HOSTNAME="$HOSTNAME"
export NIX_CONFIG="experimental-features = nix-command flakes"
sudo -E nixos-rebuild switch --flake "$FLAKE_REF"
EOF

# ============================================================================
# Done
# ============================================================================
echo ""
echo "==> Provisioning complete!"
echo ""
echo "Connect to your machine:"
echo "    orb ssh $MACHINE_NAME"
echo ""
echo "Or execute commands directly:"
echo "    orb -m $MACHINE_NAME <command>"
echo ""
