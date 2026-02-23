#!/usr/bin/env python3
"""
OrbStack NixOS Provisioning Script

This script manages NixOS machines in OrbStack, providing commands to create
and rebuild machines using Nix flakes.
"""
from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
import time
from pathlib import Path


# ============================================================================
# Command Execution
# ============================================================================

def run_command(
    cmd: list[str],
    check: bool = True,
    capture_output: bool = False
) -> subprocess.CompletedProcess:
    """Run a shell command."""
    if capture_output:
        return subprocess.run(cmd, check=check, capture_output=True, text=True)
    else:
        return subprocess.run(cmd, check=check, text=True)


# ============================================================================
# Machine State Queries
# ============================================================================

def machine_exists(machine_name: str) -> bool:
    """Check if the OrbStack machine already exists."""
    result = run_command(["orb", "list"], capture_output=True)
    for line in result.stdout.splitlines():
        if line.startswith(f"{machine_name}\t") or line.startswith(f"{machine_name} "):
            return True
    return False


def machine_is_running(machine_name: str) -> bool:
    """Check if the machine is running."""
    result = run_command(["orb", "list"], capture_output=True)
    for line in result.stdout.splitlines():
        if (line.startswith(f"{machine_name}\t") or line.startswith(f"{machine_name} ")) and "running" in line:
            return True
    return False


def wait_for_machine_ready(machine_name: str, max_wait: int = 60) -> bool:
    """Wait for machine to be running and SSH-ready."""
    print("==> Waiting for machine to become SSH-ready...")
    elapsed = 0
    while elapsed < max_wait:
        if machine_is_running(machine_name):
            # Give SSH daemon a moment to fully initialize
            time.sleep(2)
            print("    Machine is ready.")
            return True
        time.sleep(2)
        elapsed += 2
    return False


# ============================================================================
# File Operations
# ============================================================================

def copy_local_flake(machine_name: str, flake_repo: str) -> str:
    """Copy local flake files to the machine. Returns flake path on VM."""
    print("==> Copying local flake files to machine...")

    # Use /etc/nixos as the destination since we're provisioning the entire system
    flake_dest = "/etc/nixos"

    # Determine which files to copy
    flake_dir = Path(flake_repo)
    files_to_copy = []

    for file_name in ["flake.nix", "flake.lock", "configuration.nix"]:
        file_path = flake_dir / file_name
        if file_path.exists():
            files_to_copy.append((str(file_path), file_name))

    if not files_to_copy:
        print(f"Error: No flake files found in {flake_repo}", file=sys.stderr)
        sys.exit(1)

    # Create /etc/nixos directory if it doesn't exist
    run_command([
        "orb", "--machine", machine_name, "sudo", "mkdir", "-p", flake_dest
    ])

    # Copy files one by one to /tmp first, then move to /etc/nixos with sudo
    for file_path, file_name in files_to_copy:
        tmp_path = f"/tmp/{file_name}"
        dest_path = f"{flake_dest}/{file_name}"

        # Push to /tmp (no sudo needed)
        run_command(["orb", "push", "--machine", machine_name, file_path, tmp_path])

        # Move to /etc/nixos with sudo
        run_command([
            "orb", "--machine", machine_name, "sudo", "mv", tmp_path, dest_path
        ])

    return flake_dest


def get_flake_path(machine_name: str) -> str:
    """Get the flake path by copying local files to the machine."""
    # Always use current directory as flake repository
    return copy_local_flake(machine_name, ".")


def copy_bootstrap_script(machine_name: str) -> str:
    """Copy bootstrap script to VM and make it executable. Returns VM script path."""
    # Get the bootstrap script path (relative to this script)
    script_dir = Path(__file__).parent
    bootstrap_script = script_dir / "bootstrap-nixos.sh"

    if not bootstrap_script.exists():
        print(f"Error: Bootstrap script not found at {bootstrap_script}", file=sys.stderr)
        sys.exit(1)

    # Copy bootstrap script to VM
    vm_script_path = "/tmp/bootstrap-nixos.sh"
    run_command([
        "orb", "push", "--machine", machine_name,
        str(bootstrap_script), vm_script_path
    ])

    # Make it executable
    run_command([
        "orb", "--machine", machine_name, "chmod", "+x", vm_script_path
    ])

    return vm_script_path


def copy_user_config(machine_name: str, user_config: str) -> str:
    """Copy user config file to VM. Returns VM path."""
    user_config_path = Path(user_config).resolve()
    if not user_config_path.exists():
        print(f"Error: User config file not found: {user_config}", file=sys.stderr)
        sys.exit(1)

    print(f"    Copying user config to VM: {user_config_path}")
    user_config_vm_path = "/tmp/user-config.nix"
    run_command([
        "orb", "push", "--machine", machine_name,
        str(user_config_path), user_config_vm_path
    ])

    return user_config_vm_path


# ============================================================================
# Architecture Mapping
# ============================================================================

def get_arch_mapping(arch: str) -> tuple[str, str]:
    """Map architecture to OrbStack and Nix system formats."""
    arch_mapping = {
        "aarch64": ("arm64", "aarch64"),
        "arm64": ("arm64", "aarch64"),
        "x86_64": ("amd64", "x86_64"),
        "amd64": ("amd64", "x86_64"),
    }

    if arch not in arch_mapping:
        print(f"Error: Invalid architecture '{arch}'. Use aarch64/arm64 or x86_64/amd64.", file=sys.stderr)
        sys.exit(1)

    return arch_mapping[arch]


# ============================================================================
# NixOS Operations
# ============================================================================

def provision_nixos(
    machine_name: str,
    flake_path: str,
    flake_attr: str,
    hostname: str,
    username: str
) -> None:
    """Provision NixOS configuration using the bootstrap script."""
    print("==> Provisioning NixOS configuration from flake...")

    flake_ref = f"{flake_path}#{flake_attr}"
    vm_script_path = copy_bootstrap_script(machine_name)

    # Run the bootstrap script with environment variables
    run_command([
        "orb", "--machine", machine_name, "bash", "-c",
        f"FLAKE_REF='{flake_ref}' NIXOS_HOSTNAME='{hostname}' NIXOS_USERNAME='{username}' {vm_script_path}"
    ])


def print_provisioning_complete(machine_name: str, username: str) -> None:
    """Print completion message after provisioning."""
    print()
    print("==> Provisioning complete!")
    print()
    print("IMPORTANT: After provisioning, connect to your machine with:")
    print(f"    orb --machine {machine_name}")
    print()
    print("The following user has been configured:")
    print(f"    Username: {username}")
    print(f"    Password: nixos (change after first login)")
    print()
    print("Execute commands directly:")
    print(f"    orb --machine {machine_name} <command>")
    print()


# ============================================================================
# High-Level Commands
# ============================================================================

def create_machine(
    machine_name: str,
    flake_attr: str,
    hostname: str,
    username: str,
    arch: str
) -> None:
    """Create and provision a new OrbStack NixOS machine."""
    # Check if machine already exists and fail early
    if machine_exists(machine_name):
        print(f"Error: Machine '{machine_name}' already exists.", file=sys.stderr)
        print("To update an existing machine, use the 'nixos-rebuild' command instead:", file=sys.stderr)
        print(f"    provision-orbstack.py nixos-rebuild {machine_name}", file=sys.stderr)
        sys.exit(1)

    # Get architecture mapping
    orb_arch, nix_system = get_arch_mapping(arch)

    # Step 1: Create OrbStack machine
    print(f"==> Creating OrbStack NixOS machine: {machine_name} (arch: {nix_system})")
    run_command([
        "orb", "create", "nixos:25.11", machine_name,
        "--arch", orb_arch
    ])

    # Step 2: Wait for machine to be ready
    if not wait_for_machine_ready(machine_name):
        print(f"Error: Machine did not become ready within 60 seconds.", file=sys.stderr)
        sys.exit(1)

    # Step 3: Get flake path (copy local files)
    flake_path = get_flake_path(machine_name)

    # Step 4: Provision NixOS
    provision_nixos(machine_name, flake_path, flake_attr, hostname, username)

    # Done
    print_provisioning_complete(machine_name, username)


def nixos_rebuild(
    machine_name: str,
    flake_attr: str,
    hostname: str,
    username: str,
    user_config: str | None = None
) -> None:
    """Run nixos-rebuild switch by executing it on the VM directly."""
    if not machine_exists(machine_name):
        print(f"Error: Machine '{machine_name}' does not exist.", file=sys.stderr)
        print("Create it first with: provision-orbstack.py create", file=sys.stderr)
        sys.exit(1)

    if not machine_is_running(machine_name):
        print(f"Error: Machine '{machine_name}' is not running.", file=sys.stderr)
        sys.exit(1)

    print(f"==> Running nixos-rebuild switch for machine: {machine_name}")

    # Get flake path (copy local files)
    flake_path = get_flake_path(machine_name)

    # Copy user config if provided
    user_config_vm_path = None
    if user_config:
        user_config_vm_path = copy_user_config(machine_name, user_config)
        print(f"    Using user config on VM: {user_config_vm_path}")

    # Copy bootstrap script
    vm_script_path = copy_bootstrap_script(machine_name)

    # Build flake reference
    flake_ref = f"{flake_path}#{flake_attr}"

    # Build environment variables for the VM
    env_vars = f"FLAKE_REF='{flake_ref}' NIXOS_HOSTNAME='{hostname}' NIXOS_USERNAME='{username}'"
    if user_config_vm_path:
        env_vars += f" NIXOS_USER_CONFIG='{user_config_vm_path}'"

    # Run the bootstrap script with environment variables
    print(f"    Building and deploying: {flake_ref}")
    run_command([
        "orb", "--machine", machine_name, "bash", "-c",
        f"{env_vars} {vm_script_path}"
    ])

    print()
    print("==> nixos-rebuild complete!")
    print()


# ============================================================================
# Argument Parsing
# ============================================================================

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Manage OrbStack NixOS machines with Nix flakes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to execute")

    # Create command
    create_parser = subparsers.add_parser(
        "create",
        help="Create and provision a new OrbStack NixOS machine"
    )
    create_parser.add_argument(
        "machine_name",
        help="Name of the OrbStack machine to create"
    )
    create_parser.add_argument(
        "--arch",
        default="aarch64",
        choices=["aarch64", "arm64", "x86_64", "amd64"],
        help="Architecture (default: aarch64)"
    )
    create_parser.add_argument(
        "--flake-attr",
        default="default",
        help="Flake attribute to build (default: default)"
    )
    create_parser.add_argument(
        "--hostname",
        help="Hostname to set (default: same as machine-name)"
    )
    create_parser.add_argument(
        "--username",
        help="Username to create in NixOS (default: current user)"
    )

    # Nixos-rebuild command
    rebuild_parser = subparsers.add_parser(
        "nixos-rebuild",
        help="Run nixos-rebuild switch on an existing machine"
    )
    rebuild_parser.add_argument(
        "machine_name",
        help="Name of the OrbStack machine"
    )
    rebuild_parser.add_argument(
        "--flake-attr",
        default="default",
        help="Flake attribute to build (default: default)"
    )
    rebuild_parser.add_argument(
        "--hostname",
        help="Hostname to set (default: same as machine-name)"
    )
    rebuild_parser.add_argument(
        "--username",
        help="Username to create in NixOS (default: current user)"
    )
    rebuild_parser.add_argument(
        "--user-config",
        help="Path to user config file on host (optional)"
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Get username - default to current user
    username = args.username if (hasattr(args, 'username') and args.username) else getpass.getuser()

    # Get hostname - default to machine name
    hostname = args.hostname if (hasattr(args, 'hostname') and args.hostname) else args.machine_name

    # Execute command
    if args.command == "create":
        create_machine(
            machine_name=args.machine_name,
            flake_attr=args.flake_attr,
            hostname=hostname,
            username=username,
            arch=args.arch
        )
    elif args.command == "nixos-rebuild":
        user_config = args.user_config if hasattr(args, 'user_config') else None
        nixos_rebuild(
            machine_name=args.machine_name,
            flake_attr=args.flake_attr,
            hostname=hostname,
            username=username,
            user_config=user_config
        )
    else:
        print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
