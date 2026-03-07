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
# Global State
# ============================================================================

VERBOSE = False


# ============================================================================
# Command Execution
# ============================================================================


def run_command(
    cmd: list[str], check: bool = True, capture_output: bool = False
) -> subprocess.CompletedProcess:
    """Run a shell command."""
    if VERBOSE:
        print(f"[VERBOSE] Running: {' '.join(cmd)}", file=sys.stderr)
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
        if (
            line.startswith(f"{machine_name}\t") or line.startswith(f"{machine_name} ")
        ) and "running" in line:
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
    tmp_base_dir = "/tmp/orbstack-nixos-provision"

    # Determine which files to copy
    flake_dir = Path(flake_repo)
    files_to_copy = []

    for file_name in ["flake.nix", "flake.lock", "configuration.nix"]:
        file_path = flake_dir / file_name
        if file_path.exists():
            files_to_copy.append((file_path, file_name))

    if not files_to_copy:
        print(f"Error: No flake files found in {flake_repo}", file=sys.stderr)
        sys.exit(1)

    # Create temporary directory
    run_command(["orb", "--machine", machine_name, "mkdir", "-p", tmp_base_dir])

    # Create /etc/nixos directory if it doesn't exist
    run_command(["orb", "--machine", machine_name, "sudo", "mkdir", "-p", flake_dest])

    # Copy files one by one to /tmp/orbstack-nixos-provision first, then move to /etc/nixos with sudo
    for file_path, file_name in files_to_copy:
        tmp_path = f"{tmp_base_dir}/{file_name}"
        dest_path = f"{flake_dest}/{file_name}"

        # Push to /tmp/orbstack-nixos-provision (no sudo needed)
        run_command(["orb", "push", "--machine", machine_name, str(file_path), tmp_path])

        # Move to /etc/nixos with sudo
        run_command(["orb", "--machine", machine_name, "sudo", "mv", tmp_path, dest_path])

    return flake_dest


def get_flake_path(machine_name: str) -> str:
    """Get the flake path by copying local files to the machine."""
    # Use orbstack-nix-config directory as flake repository
    return copy_local_flake(machine_name, "orbstack-nix-config")


def copy_bootstrap_script(machine_name: str) -> str:
    """Copy bootstrap script to VM and make it executable. Returns VM script path."""
    # Get the bootstrap script path (relative to this script)
    script_dir = Path(__file__).parent
    bootstrap_script = script_dir / "bootstrap-nixos.sh"
    tmp_base_dir = "/tmp/orbstack-nixos-provision"

    if not bootstrap_script.exists():
        print(f"Error: Bootstrap script not found at {bootstrap_script}", file=sys.stderr)
        sys.exit(1)

    # Create temporary directory
    run_command(["orb", "--machine", machine_name, "mkdir", "-p", tmp_base_dir])

    # Copy bootstrap script to VM
    vm_script_path = f"{tmp_base_dir}/bootstrap-nixos.sh"
    run_command(["orb", "push", "--machine", machine_name, str(bootstrap_script), vm_script_path])

    # Make it executable
    run_command(["orb", "--machine", machine_name, "chmod", "+x", vm_script_path])

    return vm_script_path


def copy_nix_extra_config_dir(machine_name: str) -> None:
    """Recursively copy orbstack-nix-config/extra directory to VM if it exists."""
    script_dir = Path(__file__).parent
    nix_extra_config_dir = script_dir / "orbstack-nix-config" / "extra"
    tmp_base_dir = "/tmp/orbstack-nixos-provision"

    if not nix_extra_config_dir.exists() or not nix_extra_config_dir.is_dir():
        return

    print(f"    Copying orbstack-nix-config/extra directory to VM...")

    # Create the destination directory on VM
    dest_dir = f"{tmp_base_dir}/orbstack-nix-config/extra"
    run_command(["orb", "--machine", machine_name, "mkdir", "-p", dest_dir])

    # Get all files with their relative paths and destination paths
    files = [
        (item, item.relative_to(nix_extra_config_dir))
        for item in nix_extra_config_dir.rglob("*")
        if item.is_file()
    ]

    # Get unique parent directories that need to be created
    parent_dirs = {
        f"{dest_dir}/{rel_path.parent}" for _, rel_path in files if rel_path.parent != Path(".")
    }

    # Create all parent directories
    for parent_dir in parent_dirs:
        run_command(["orb", "--machine", machine_name, "mkdir", "-p", parent_dir])

    # Copy all files
    for src_path, rel_path in files:
        dest_path = f"{dest_dir}/{rel_path}"
        run_command(["orb", "push", "--machine", machine_name, str(src_path), dest_path])


def copy_extra_config(machine_name: str, extra_config: str) -> str:
    """Copy extra config file to VM. Returns VM path."""
    # Try to resolve as absolute path first, then relative to current directory
    extra_config_path = Path(extra_config)
    if not extra_config_path.is_absolute():
        extra_config_path = Path.cwd() / extra_config

    extra_config_path = extra_config_path.resolve()
    tmp_base_dir = "/tmp/orbstack-nixos-provision"

    if not extra_config_path.exists():
        print(f"Error: User config file not found: {extra_config}", file=sys.stderr)

        # Try to suggest similar files if in orbstack-nix-config/extra directory
        if extra_config.startswith("orbstack-nix-config/extra"):
            script_dir = Path(__file__).parent
            nix_extra_config_dir = script_dir / "orbstack-nix-config" / "extra"
            if nix_extra_config_dir.exists():
                similar_files = list(nix_extra_config_dir.rglob("*.nix"))
                if similar_files:
                    print("\nAvailable .nix files in orbstack-nix-config/extra/:", file=sys.stderr)
                    for f in similar_files:
                        rel_path = f.relative_to(script_dir)
                        print(f"  {rel_path}", file=sys.stderr)
        sys.exit(1)

    print(f"    Copying extra config to VM: {extra_config_path}")

    # Create temporary directory
    run_command(["orb", "--machine", machine_name, "mkdir", "-p", tmp_base_dir])

    extra_config_vm_path = f"{tmp_base_dir}/extra-config.nix"
    run_command(
        ["orb", "push", "--machine", machine_name, str(extra_config_path), extra_config_vm_path]
    )

    return extra_config_vm_path


# ============================================================================
# Architecture Mapping
# ============================================================================


def get_architecture(arch: str | None = None) -> tuple[str, str]:
    """
    Get architecture mapping for OrbStack and Nix.

    Args:
        arch: Architecture string (aarch64/arm64/x86_64/amd64) or None for host detection

    Returns:
        Tuple of (orbstack_arch, nix_arch) e.g. ("arm64", "aarch64")
    """
    # If no arch specified, detect from host
    if arch is None:
        result = run_command(["uname", "-m"], capture_output=True)
        machine = result.stdout.strip()

        # Normalize uname output
        if machine in ["arm64", "aarch64"]:
            arch = "aarch64"
        elif machine in ["x86_64", "amd64"]:
            arch = "x86_64"
        else:
            # Default to aarch64 if unknown
            arch = "aarch64"

    # Map to OrbStack and Nix formats
    arch_mapping = {
        "aarch64": ("arm64", "aarch64"),
        "arm64": ("arm64", "aarch64"),
        "x86_64": ("amd64", "x86_64"),
        "amd64": ("amd64", "x86_64"),
    }

    if arch not in arch_mapping:
        print(
            f"Error: Invalid architecture '{arch}'. Use aarch64/arm64 or x86_64/amd64.",
            file=sys.stderr,
        )
        sys.exit(1)

    return arch_mapping[arch]


# ============================================================================
# NixOS Operations
# ============================================================================


def run_nixos_rebuild(
    machine_name: str,
    flake_attr: str,
    hostname: str,
    username: str,
    extra_config: str | None = None,
    is_initial_provision: bool = False,
) -> None:
    """Run nixos-rebuild switch by executing it on the VM directly."""
    if is_initial_provision:
        print("==> Provisioning NixOS configuration from flake...")
    else:
        print(f"==> Running nixos-rebuild switch for machine: {machine_name}")

    # Get flake path (copy local files)
    flake_path = get_flake_path(machine_name)

    # Copy orbstack-nix-config/extra directory (always, if it exists)
    copy_nix_extra_config_dir(machine_name)

    # Copy extra config if provided
    extra_config_vm_path = None
    if extra_config:
        extra_config_vm_path = copy_extra_config(machine_name, extra_config)
        print(f"    Using extra config on VM: {extra_config_vm_path}")

    # Copy bootstrap script
    vm_script_path = copy_bootstrap_script(machine_name)

    # Build flake reference
    flake_ref = f"{flake_path}#{flake_attr}"

    # Build environment variables for the VM
    env_vars = f"FLAKE_REF='{flake_ref}' NIXOS_HOSTNAME='{hostname}' NIXOS_USERNAME='{username}'"
    if extra_config_vm_path:
        env_vars += f" NIXOS_EXTRA_CONFIG='{extra_config_vm_path}'"

    # Run the bootstrap script with environment variables
    if not is_initial_provision:
        print(f"    Building and deploying: {flake_ref}")
    run_command(["orb", "--machine", machine_name, "bash", "-c", f"{env_vars} {vm_script_path}"])

    if not is_initial_provision:
        print()
        print("==> nixos-rebuild complete!")
        print()


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


def create_machine_only(
    machine_name: str,
    arch: str | None,
    recreate: bool = False,
) -> None:
    """Create an OrbStack NixOS machine without provisioning it.

    This is useful for creating a base machine that can be cloned later,
    avoiding the expensive provisioning step for each test.
    """
    # Check if machine already exists
    if machine_exists(machine_name):
        if recreate:
            print(f"==> Deleting existing machine: {machine_name}")
            run_command(["orb", "delete", "-f", machine_name])
        else:
            print(f"Error: Machine '{machine_name}' already exists.", file=sys.stderr)
            print("Use --recreate to delete and recreate the machine.", file=sys.stderr)
            sys.exit(1)

    # Get architecture mapping
    orb_arch, nix_system = get_architecture(arch)

    # Step 1: Create OrbStack machine
    print(f"==> Creating OrbStack NixOS machine: {machine_name} (arch: {nix_system})")
    run_command(["orb", "create", "nixos:25.11", machine_name, "--arch", orb_arch])

    # Step 2: Wait for machine to be ready
    if not wait_for_machine_ready(machine_name):
        print(f"Error: Machine did not become ready within 60 seconds.", file=sys.stderr)
        sys.exit(1)


def create_machine(
    machine_name: str,
    flake_attr: str,
    hostname: str,
    username: str,
    arch: str | None,
    extra_config: str | None = None,
    recreate: bool = False,
) -> None:
    """Create and provision a new OrbStack NixOS machine."""
    # Step 1: Create OrbStack machine (without provisioning)
    create_machine_only(machine_name, arch, recreate)

    # Step 2: Provision NixOS using the rebuild function
    run_nixos_rebuild(
        machine_name, flake_attr, hostname, username, extra_config, is_initial_provision=True
    )

    # Done
    print_provisioning_complete(machine_name, username)


def nixos_rebuild(
    machine_name: str,
    flake_attr: str,
    hostname: str,
    username: str,
    extra_config: str | None = None,
) -> None:
    """Run nixos-rebuild switch on an existing machine."""
    if not machine_exists(machine_name):
        print(f"Error: Machine '{machine_name}' does not exist.", file=sys.stderr)
        print("Create it first with: orbstack-nixos-provision.py create", file=sys.stderr)
        sys.exit(1)

    if not machine_is_running(machine_name):
        print(f"Error: Machine '{machine_name}' is not running.", file=sys.stderr)
        sys.exit(1)

    run_nixos_rebuild(machine_name, flake_attr, hostname, username, extra_config)


# ============================================================================
# Argument Parsing
# ============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Manage OrbStack NixOS machines with Nix flakes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print verbose output including all shell invocations",
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to execute")

    # Create command
    create_parser = subparsers.add_parser(
        "create", help="Create and provision a new OrbStack NixOS machine"
    )
    create_parser.add_argument("machine_name", help="Name of the OrbStack machine to create")
    create_parser.add_argument(
        "--arch",
        default=None,
        choices=["aarch64", "arm64", "x86_64", "amd64"],
        help="Architecture (default: host architecture)",
    )
    create_parser.add_argument(
        "--flake-attr", default="default", help="Flake attribute to build (default: default)"
    )
    create_parser.add_argument("--hostname", help="Hostname to set (default: same as machine-name)")
    create_parser.add_argument(
        "--username", help="Username to create in NixOS (default: current user)"
    )
    create_parser.add_argument(
        "--extra-config", help="Path to extra config file on host (optional)"
    )
    create_parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate the machine if it already exists",
    )

    # Nixos-rebuild command
    rebuild_parser = subparsers.add_parser(
        "nixos-rebuild", help="Run nixos-rebuild switch on an existing machine"
    )
    rebuild_parser.add_argument("machine_name", help="Name of the OrbStack machine")
    rebuild_parser.add_argument(
        "--flake-attr", default="default", help="Flake attribute to build (default: default)"
    )
    rebuild_parser.add_argument(
        "--hostname", help="Hostname to set (default: same as machine-name)"
    )
    rebuild_parser.add_argument(
        "--username", help="Username to create in NixOS (default: current user)"
    )
    rebuild_parser.add_argument(
        "--extra-config", help="Path to extra config file on host (optional)"
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    global VERBOSE
    args = parse_args()

    # Set verbose mode
    VERBOSE = args.verbose

    # Get username - default to current user
    username = args.username if (hasattr(args, "username") and args.username) else getpass.getuser()

    # Get hostname - default to machine name
    hostname = args.hostname if (hasattr(args, "hostname") and args.hostname) else args.machine_name

    # Get extra config if provided
    extra_config = (
        args.extra_config if (hasattr(args, "extra_config") and args.extra_config) else None
    )

    # Execute command
    if args.command == "create":
        create_machine(
            machine_name=args.machine_name,
            flake_attr=args.flake_attr,
            hostname=hostname,
            username=username,
            arch=args.arch,
            extra_config=extra_config,
            recreate=args.recreate,
        )
    elif args.command == "nixos-rebuild":
        nixos_rebuild(
            machine_name=args.machine_name,
            flake_attr=args.flake_attr,
            hostname=hostname,
            username=username,
            extra_config=extra_config,
        )
    else:
        print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
