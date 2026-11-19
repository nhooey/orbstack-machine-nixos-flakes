#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# NixOS Bootstrap Script
# ============================================================================
# This script runs inside the OrbStack machine to provision NixOS configuration
# from a flake reference.
#
# Environment Variables:
#   FLAKE_REF:          Required. The flake reference to build (e.g., .#default)
#   NIXOS_HOSTNAME:     Optional. Hostname to set; the flake falls back to "nixos".
#   NIXOS_USERNAME:     Optional. User to create; the flake falls back to "nixos".
#   NIXOS_EXTRA_CONFIG: Optional. Path on the machine to an extra Nix module to import.
# ============================================================================

if [[ -z "${FLAKE_REF:-}" ]]; then
    echo "Error: FLAKE_REF environment variable is required" >&2
    exit 1
fi

# A username NixOS can create: lower case, starting with a letter or `_`,
# at most 32 characters. Empty falls back to the flake's default.
if [[ -n "${NIXOS_USERNAME:-}" && ! "$NIXOS_USERNAME" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]]; then
    printf 'Error: NIXOS_USERNAME %q is not a valid username\n' "$NIXOS_USERNAME" >&2
    exit 1
fi

echo "Environment variables received:"
echo "  FLAKE_REF: $FLAKE_REF"
echo "  NIXOS_HOSTNAME: ${NIXOS_HOSTNAME:-<not set>}"
echo "  NIXOS_USERNAME: ${NIXOS_USERNAME:-<not set>}"
echo "  NIXOS_EXTRA_CONFIG: ${NIXOS_EXTRA_CONFIG:-<not set>}"

echo "Running nixos-rebuild switch with flake: $FLAKE_REF"

# `sudo env NAME=value ...` hands each value to root as one argument, so no
# value is read by a shell or a template. The flake reads them with --impure.
sudo env \
    NIX_CONFIG="experimental-features = nix-command flakes" \
    FLAKE_REF="$FLAKE_REF" \
    NIXOS_HOSTNAME="${NIXOS_HOSTNAME:-}" \
    NIXOS_USERNAME="${NIXOS_USERNAME:-}" \
    NIXOS_EXTRA_CONFIG="${NIXOS_EXTRA_CONFIG:-}" \
    nixos-rebuild switch --flake "$FLAKE_REF" --impure
