#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# NixOS Bootstrap Script
# ============================================================================
# This script runs inside the OrbStack machine to provision NixOS configuration
# from a flake reference.
#
# Environment Variables:
#   FLAKE_REF:        Required. The flake reference to build (e.g., .#default)
#   NIXOS_HOSTNAME:   Optional. Hostname to set during provisioning.
# ============================================================================

if [[ -z "${FLAKE_REF:-}" ]]; then
    echo "Error: FLAKE_REF environment variable is required" >&2
    exit 1
fi

# Debug: Print environment variables
echo "Environment variables received:"
echo "  FLAKE_REF: $FLAKE_REF"
echo "  NIXOS_HOSTNAME: ${NIXOS_HOSTNAME:-<not set>}"
echo "  NIXOS_USERNAME: ${NIXOS_USERNAME:-<not set>}"
echo "  NIXOS_EXTRA_CONFIG: ${NIXOS_EXTRA_CONFIG:-<not set>}"

# Run nixos-rebuild with environment variables and enable flakes via NIX_CONFIG
echo "Running nixos-rebuild switch with flake: $FLAKE_REF"

# Create a temporary wrapper script that will run as root with all environment variables set
# This is necessary because sudo doesn't reliably preserve all environment variables,
# especially custom ones like NIXOS_*, even with -E or env command
WRAPPER_SCRIPT="/tmp/nixos-rebuild-wrapper-$$.sh"
cat > "$WRAPPER_SCRIPT" << 'WRAPPER_EOF'
#!/usr/bin/env bash
set -euo pipefail

# Set environment variables for the Nix build
export NIX_CONFIG="experimental-features = nix-command flakes"
export FLAKE_REF="__FLAKE_REF__"
export NIXOS_HOSTNAME="__NIXOS_HOSTNAME__"
export NIXOS_USERNAME="__NIXOS_USERNAME__"
export NIXOS_EXTRA_CONFIG="__NIXOS_EXTRA_CONFIG__"

# Run nixos-rebuild with --impure to allow reading environment variables
nixos-rebuild switch --flake "$FLAKE_REF" --impure
WRAPPER_EOF

# Replace placeholders with actual values
sed -i "s|__FLAKE_REF__|$FLAKE_REF|g" "$WRAPPER_SCRIPT"
sed -i "s|__NIXOS_HOSTNAME__|${NIXOS_HOSTNAME:-}|g" "$WRAPPER_SCRIPT"
sed -i "s|__NIXOS_USERNAME__|${NIXOS_USERNAME:-}|g" "$WRAPPER_SCRIPT"
sed -i "s|__NIXOS_EXTRA_CONFIG__|${NIXOS_EXTRA_CONFIG:-}|g" "$WRAPPER_SCRIPT"

# Make wrapper script executable
chmod +x "$WRAPPER_SCRIPT"

# Run the wrapper script as root
sudo "$WRAPPER_SCRIPT"

# Clean up
rm -f "$WRAPPER_SCRIPT"
