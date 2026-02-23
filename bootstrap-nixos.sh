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

# Run nixos-rebuild with environment variables and enable flakes via NIX_CONFIG
echo "Running nixos-rebuild switch with flake: $FLAKE_REF"
export NIX_CONFIG="experimental-features = nix-command flakes"
# Use --impure to allow reading environment variables during build
sudo -E nixos-rebuild switch --flake "$FLAKE_REF" --impure
