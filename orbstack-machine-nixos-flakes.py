#!/usr/bin/env python3
"""
OrbStack NixOS Provisioning Script

This script manages NixOS machines in OrbStack, providing commands to create
and rebuild machines using Nix flakes.
"""

from __future__ import annotations

import argparse
import getpass
import subprocess
import sys
import time
from pathlib import Path

# ============================================================================
# Global State
# ============================================================================

# Paths
TMP_BASE_DIR = "/tmp/orbstack-machine-nixos-flakes"
FLAKE_DEST_DIR = "/etc/nixos"
FLAKE_REPO_DIR = "orbstack-nix-config"
FLAKE_EXTRA_DIR = "extra"
BOOTSTRAP_SCRIPT_NAME = "bootstrap-nixos.sh"
EXTRA_CONFIG_FILENAME = "extra-config.nix"

# Script metadata
SCRIPT_NAME = "orbstack-machine-nixos-flakes.py"

DEFAULT_TIMEOUT = 1200

# ============================================================================
# Command Execution
# ============================================================================


def run_command(
    cmd: list[str],
    check: bool = True,
    capture_output: bool = False,
    timeout: int | None = DEFAULT_TIMEOUT,
    verbose: bool = False,
) -> subprocess.CompletedProcess:
    """Run a shell command with an optional timeout."""
    if verbose:
        print(f"[VERBOSE] Running [{timeout}s]: {' '.join(cmd)}", file=sys.stderr)
    if capture_output:
        return subprocess.run(
            cmd, check=check, capture_output=True, text=True, timeout=timeout
        )
    else:
        return subprocess.run(cmd, check=check, text=True, timeout=timeout)


# ============================================================================
# Machine State Queries
# ============================================================================


def machine_exists(
    machine_name: str, verbose: bool = False, timeout: int = DEFAULT_TIMEOUT
) -> bool:
    """Check if the OrbStack machine already exists."""
    result = run_command(
        ["orb", "list"], capture_output=True, verbose=verbose, timeout=timeout
    )
    for line in result.stdout.splitlines():
        if line.startswith(f"{machine_name}\t") or line.startswith(f"{machine_name} "):
            return True
    return False


def machine_is_running(
    machine_name: str, verbose: bool = False, timeout: int = DEFAULT_TIMEOUT
) -> bool:
    """Check if the machine is running."""
    result = run_command(
        ["orb", "list"], capture_output=True, verbose=verbose, timeout=timeout
    )
    for line in result.stdout.splitlines():
        if (
            line.startswith(f"{machine_name}\t") or line.startswith(f"{machine_name} ")
        ) and "running" in line:
            return True
    return False


def wait_for_machine_ready(
    machine_name: str,
    max_wait: int = 60,
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> bool:
    """Wait for the machine to be running and SSH-ready."""
    print("==> Waiting for machine to become SSH-ready...")
    elapsed = 0
    while elapsed < max_wait:
        if machine_is_running(machine_name, verbose=verbose, timeout=timeout):
            # Give the SSH daemon a moment to fully initialize
            time.sleep(2)
            print("    Machine is ready.")
            return True
        time.sleep(2)
        elapsed += 2
    return False


# ============================================================================
# File Operations
# ============================================================================


def copy_local_flake(
    machine_name: str,
    flake_repo: str,
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Copy local flake files to the machine. Returns flake path on VM."""
    print("==> Copying local flake files to machine...")

    # Use /etc/nixos as the destination since we're provisioning the entire system
    flake_dest = FLAKE_DEST_DIR

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

    # Create a temporary directory
    run_command(
        ["orb", "--machine", machine_name, "mkdir", "-p", TMP_BASE_DIR],
        verbose=verbose,
        timeout=timeout,
    )

    # Create /etc/nixos directory if it doesn't exist
    run_command(
        ["orb", "--machine", machine_name, "sudo", "mkdir", "-p", flake_dest],
        verbose=verbose,
        timeout=timeout,
    )

    for file_path, file_name in files_to_copy:
        tmp_path = f"{TMP_BASE_DIR}/{file_name}"
        dest_path = f"{flake_dest}/{file_name}"
        run_command(
            ["orb", "push", "--machine", machine_name, str(file_path), tmp_path],
            verbose=verbose,
            timeout=timeout,
        )
        run_command(
            ["orb", "--machine", machine_name, "sudo", "mv", tmp_path, dest_path],
            verbose=verbose,
            timeout=timeout,
        )

    return flake_dest


def get_flake_path(
    machine_name: str, verbose: bool = False, timeout: int = DEFAULT_TIMEOUT
) -> str:
    """Get the flake path by copying local files to the machine.

    Args:
        machine_name: Name of the OrbStack machine.
        verbose: Enable verbose output.
        timeout: Command timeout in seconds.

    Returns:
        Path to the flake directory on the machine.
    """
    # Use flake repository directory
    return copy_local_flake(
        machine_name, FLAKE_REPO_DIR, verbose=verbose, timeout=timeout
    )


def copy_bootstrap_script(
    machine_name: str, verbose: bool = False, timeout: int = DEFAULT_TIMEOUT
) -> str:
    """Copy the bootstrap script to VM and make it executable. Returns VM script path."""
    # Get the bootstrap script path (relative to this script)
    script_dir = Path(__file__).parent
    bootstrap_script = script_dir / BOOTSTRAP_SCRIPT_NAME

    if not bootstrap_script.exists():
        print(
            f"Error: Bootstrap script not found at {bootstrap_script}", file=sys.stderr
        )
        sys.exit(1)

    # Create a temporary directory
    run_command(
        ["orb", "--machine", machine_name, "mkdir", "-p", TMP_BASE_DIR],
        verbose=verbose,
        timeout=timeout,
    )

    # Copy bootstrap script to VM
    vm_script_path = f"{TMP_BASE_DIR}/{BOOTSTRAP_SCRIPT_NAME}"
    run_command(
        [
            "orb",
            "push",
            "--machine",
            machine_name,
            str(bootstrap_script),
            vm_script_path,
        ],
        verbose=verbose,
        timeout=timeout,
    )

    # Make it executable
    run_command(
        ["orb", "--machine", machine_name, "chmod", "+x", vm_script_path],
        verbose=verbose,
        timeout=timeout,
    )

    return vm_script_path


def copy_nix_extra_config_dir(
    machine_name: str, verbose: bool = False, timeout: int = DEFAULT_TIMEOUT
) -> None:
    """Recursively copy flake extra directory to VM if it exists."""
    nix_extra_config_dir = Path.cwd() / FLAKE_REPO_DIR / FLAKE_EXTRA_DIR

    if not nix_extra_config_dir.exists() or not nix_extra_config_dir.is_dir():
        return

    print(f"    Copying {FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR} directory to VM...")

    # Create the destination directory on VM
    dest_dir = f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR}"
    run_command(
        ["orb", "--machine", machine_name, "mkdir", "-p", dest_dir],
        verbose=verbose,
        timeout=timeout,
    )

    # Get all the files with their relative paths and destination paths
    files = [
        (item, item.relative_to(nix_extra_config_dir))
        for item in nix_extra_config_dir.rglob("*")
        if item.is_file()
    ]

    # Get the unique parent directories that need to be created
    parent_dirs = {
        f"{dest_dir}/{rel_path.parent}"
        for _, rel_path in files
        if rel_path.parent != Path(".")
    }

    # Create all the parent directories
    for parent_dir in parent_dirs:
        run_command(
            ["orb", "--machine", machine_name, "mkdir", "-p", parent_dir],
            verbose=verbose,
            timeout=timeout,
        )

    # Copy all the files
    for src_path, rel_path in files:
        dest_path = f"{dest_dir}/{rel_path}"
        run_command(
            ["orb", "push", "--machine", machine_name, str(src_path), dest_path],
            verbose=verbose,
            timeout=timeout,
        )


def copy_extra_config(
    machine_name: str,
    extra_config: str,
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Copy the extra config file to the VM. Returns the VM path.

    If the extra config is within orbstack-nix-config/extra/, this function will
    copy the entire orbstack-nixos-config directory to /etc/nixos on the machine
    to ensure that all references work properly.

    If the extra config is outside that directory, it will copy just the single file.
    """
    # Try to resolve as an absolute path first, then relative to the current directory
    extra_config_path = Path(extra_config)
    if not extra_config_path.is_absolute():
        extra_config_path = Path.cwd() / extra_config

    extra_config_path = extra_config_path.resolve()

    if not extra_config_path.exists():
        print(
            f"Error: The user config file was not found: {extra_config}",
            file=sys.stderr,
        )

        # Try to suggest similar files if in orbstack-nix-config/extra directory
        extra_dir_path = f"{FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR}"
        if extra_config.startswith(extra_dir_path):
            script_dir = Path(__file__).parent
            nix_extra_config_dir = script_dir / FLAKE_REPO_DIR / FLAKE_EXTRA_DIR
            if nix_extra_config_dir.exists():
                similar_files = list(nix_extra_config_dir.rglob("*.nix"))
                if similar_files:
                    print(
                        f"\nAvailable .nix files in {extra_dir_path}/:", file=sys.stderr
                    )
                    for f in similar_files:
                        rel_path = f.relative_to(script_dir)
                        print(f"  {rel_path}", file=sys.stderr)
        sys.exit(1)

    print(f"    Copying extra config to VM: {extra_config_path}")

    # Check if the extra config is within orbstack-nix-config/extra/
    script_dir = Path(__file__).parent
    orbstack_nix_config_dir = script_dir / FLAKE_REPO_DIR

    try:
        # Check if the extra config is within orbstack-nix-config/extra/
        rel_to_orbstack = extra_config_path.relative_to(orbstack_nix_config_dir / FLAKE_EXTRA_DIR)
        is_in_extra_dir = True
    except ValueError:
        # Not within orbstack-nix-config/extra/
        is_in_extra_dir = False

    # Create a temporary directory
    run_command(
        ["orb", "--machine", machine_name, "mkdir", "-p", TMP_BASE_DIR],
        verbose=verbose,
        timeout=timeout,
    )

    if is_in_extra_dir:
        # Copy the entire orbstack-nix-config directory to /etc/nixos
        print(f"    Copying entire {FLAKE_REPO_DIR} directory to /etc/nixos...")

        # Create destination directory
        dest_base = f"{FLAKE_DEST_DIR}/{FLAKE_REPO_DIR}"
        run_command(
            ["orb", "--machine", machine_name, "sudo", "mkdir", "-p", dest_base],
            verbose=verbose,
            timeout=timeout,
        )

        # Get all files in orbstack-nix-config directory
        files = [
            (item, item.relative_to(orbstack_nix_config_dir))
            for item in orbstack_nix_config_dir.rglob("*")
            if item.is_file()
        ]

        # Get unique parent directories
        parent_dirs = {
            f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}/{rel_path.parent}"
            for _, rel_path in files
            if rel_path.parent != Path(".")
        }

        # Create all parent directories in temp location
        for parent_dir in parent_dirs:
            run_command(
                ["orb", "--machine", machine_name, "mkdir", "-p", parent_dir],
                verbose=verbose,
                timeout=timeout,
            )

        # Copy all files to temp location
        for src_path, rel_path in files:
            tmp_dest_path = f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}/{rel_path}"
            run_command(
                ["orb", "push", "--machine", machine_name, str(src_path), tmp_dest_path],
                verbose=verbose,
                timeout=timeout,
            )

        # Move from temp to /etc/nixos with sudo
        run_command(
            [
                "orb",
                "--machine",
                machine_name,
                "sudo",
                "mv",
                f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}",
                FLAKE_DEST_DIR,
            ],
            verbose=verbose,
            timeout=timeout,
        )

        # Return the path to the extra config on the VM
        extra_config_vm_path = f"{FLAKE_DEST_DIR}/{FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR}/{rel_to_orbstack}"
    else:
        # Just copy the single file
        extra_config_vm_path = f"{TMP_BASE_DIR}/{EXTRA_CONFIG_FILENAME}"
        run_command(
            [
                "orb",
                "push",
                "--machine",
                machine_name,
                str(extra_config_path),
                extra_config_vm_path,
            ],
            verbose=verbose,
            timeout=timeout,
        )

    return extra_config_vm_path


# ============================================================================
# Architecture Mapping
# ============================================================================


def get_architecture(
    arch: str | None = None, verbose: bool = False, timeout: int = DEFAULT_TIMEOUT
) -> tuple[str, str]:
    # If no arch specified, detect from host
    if arch is None:
        result = run_command(
            ["uname", "-m"], capture_output=True, verbose=verbose, timeout=timeout
        )
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
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """Run the nixos-rebuild switch by executing it on the VM directly."""
    if is_initial_provision:
        print("==> Provisioning NixOS configuration from flake...")
    else:
        print(f"==> Running nixos-rebuild switch for machine: {machine_name}")

    # Get flake path (copy local files)
    flake_path = get_flake_path(machine_name, verbose=verbose, timeout=timeout)

    # Copy flake extra directory (always, if it exists)
    copy_nix_extra_config_dir(machine_name, verbose=verbose, timeout=timeout)

    # Copy extra config if provided
    extra_config_vm_path = None
    if extra_config:
        extra_config_vm_path = copy_extra_config(
            machine_name, extra_config, verbose=verbose, timeout=timeout
        )
        print(f"    Using extra config on VM: {extra_config_vm_path}")

    # Copy bootstrap script
    vm_bootstrap_script_path = copy_bootstrap_script(
        machine_name, verbose=verbose, timeout=timeout
    )

    # Build flake reference
    flake_ref = f"{flake_path}#{flake_attr}"

    # Build environment variables for the VM
    # Use export to ensure they're available to subprocesses
    env_vars = f"export FLAKE_REF='{flake_ref}'; export NIXOS_HOSTNAME='{hostname}'; export NIXOS_USERNAME='{username}'"
    if extra_config_vm_path:
        env_vars += f"; export NIXOS_EXTRA_CONFIG='{extra_config_vm_path}'"

    # Run the bootstrap script with environment variables
    # Use a long timeout since nixos-rebuild can take a while,
    # especially on the first run when it needs to download packages
    if not is_initial_provision:
        print(f"    Building and deploying: {flake_ref}")
    run_command(
        [
            "orb",
            "--machine",
            machine_name,
            "bash",
            "-c",
            f"{env_vars}; {vm_bootstrap_script_path}",
        ],
        timeout=timeout,
        verbose=verbose,
    )

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
    print("    Password: nixos (change after first login)")
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
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """Create an OrbStack NixOS machine without provisioning it.

    This is useful for creating a base machine that can be cloned later,
    avoiding the expensive provisioning step for each test.
    """
    # Check if the machine already exists
    if machine_exists(machine_name, verbose=verbose, timeout=timeout):
        if recreate:
            print(f"==> Deleting existing machine: {machine_name}")
            run_command(
                ["orb", "delete", "-f", machine_name], verbose=verbose, timeout=timeout
            )
        else:
            print(f"Error: Machine '{machine_name}' already exists.", file=sys.stderr)
            print("Use --recreate to delete and recreate the machine.", file=sys.stderr)
            sys.exit(1)

    # Get architecture mapping
    orb_arch, nix_system = get_architecture(arch, verbose=verbose, timeout=timeout)

    # Step 1: Create OrbStack machine
    print(f"==> Creating OrbStack NixOS machine: {machine_name} (arch: {nix_system})")
    run_command(
        ["orb", "create", "nixos:25.11", machine_name, "--arch", orb_arch],
        verbose=verbose,
        timeout=timeout,
    )

    # Step 2: Wait for the machine to be ready
    if not wait_for_machine_ready(machine_name, verbose=verbose, timeout=timeout):
        print("Error: Machine did not become ready within 60 seconds.", file=sys.stderr)
        sys.exit(1)


def create_machine(
    machine_name: str,
    flake_attr: str,
    hostname: str,
    username: str,
    arch: str | None,
    extra_config: str | None = None,
    recreate: bool = False,
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """Create and provision a new OrbStack NixOS machine."""
    # Step 1: Create OrbStack machine (without provisioning)
    create_machine_only(machine_name, arch, recreate, verbose=verbose, timeout=timeout)

    # Step 2: Provision NixOS using the rebuild function
    run_nixos_rebuild(
        machine_name,
        flake_attr,
        hostname,
        username,
        extra_config,
        is_initial_provision=True,
        verbose=verbose,
        timeout=timeout,
    )

    # Done
    print_provisioning_complete(machine_name, username)


def nixos_rebuild(
    machine_name: str,
    flake_attr: str,
    hostname: str,
    username: str,
    extra_config: str | None = None,
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """Run nixos-rebuild switch on an existing machine."""
    if not machine_exists(machine_name, verbose=verbose, timeout=timeout):
        print(f"Error: Machine '{machine_name}' does not exist.", file=sys.stderr)
        print(f"Create it first with: {SCRIPT_NAME} create", file=sys.stderr)
        sys.exit(1)

    if not machine_is_running(machine_name, verbose=verbose, timeout=timeout):
        print(f"Error: Machine '{machine_name}' is not running.", file=sys.stderr)
        sys.exit(1)

    run_nixos_rebuild(
        machine_name,
        flake_attr,
        hostname,
        username,
        extra_config,
        verbose=verbose,
        timeout=timeout,
    )


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
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Timeout in seconds for all operations (default: 600)",
    )

    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Command to execute"
    )

    # Create command
    create_parser = subparsers.add_parser(
        "create", help="Create and provision a new OrbStack NixOS machine"
    )
    create_parser.add_argument(
        "machine_name", help="Name of the OrbStack machine to create"
    )
    create_parser.add_argument(
        "--arch",
        default=None,
        choices=["aarch64", "arm64", "x86_64", "amd64"],
        help="Architecture (default: host architecture)",
    )
    create_parser.add_argument(
        "--flake-attr",
        default="default",
        help="Flake attribute to build (default: default)",
    )
    create_parser.add_argument(
        "--hostname", help="Hostname to set (default: same as machine-name)"
    )
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
        "--flake-attr",
        default="default",
        help="Flake attribute to build (default: default)",
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
    args = parse_args()

    # Get verbose flag
    verbose = args.verbose

    # Get timeout
    timeout = args.timeout

    # Get username - default to current user
    username = (
        args.username
        if (hasattr(args, "username") and args.username)
        else getpass.getuser()
    )

    # Get hostname - default to machine name
    hostname = (
        args.hostname
        if (hasattr(args, "hostname") and args.hostname)
        else args.machine_name
    )

    # Get extra config if provided
    extra_config = (
        args.extra_config
        if (hasattr(args, "extra_config") and args.extra_config)
        else None
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
            verbose=verbose,
            timeout=timeout,
        )
    elif args.command == "nixos-rebuild":
        nixos_rebuild(
            machine_name=args.machine_name,
            flake_attr=args.flake_attr,
            hostname=hostname,
            username=username,
            extra_config=extra_config,
            verbose=verbose,
            timeout=timeout,
        )
    else:
        print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
