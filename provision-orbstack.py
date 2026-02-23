#!/usr/bin/env python3
"""
OrbStack NixOS Provisioning Script

This script manages NixOS machines in OrbStack, providing commands to create
and rebuild machines using Nix flakes.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


class OrbStackProvisioner:
    """Manages OrbStack NixOS machine provisioning."""

    def __init__(self, machine_name: str, flake_repo: str, flake_attr: str, hostname: str, username: str):
        self.machine_name = machine_name
        self.flake_repo = flake_repo
        self.flake_attr = flake_attr
        self.hostname = hostname if hostname else machine_name
        self.username = username

    def run_command(self, cmd: list[str], check: bool = True, capture_output: bool = False, capture_stderr: bool = False) -> subprocess.CompletedProcess:
        """Run a shell command."""
        if capture_output:
            result = subprocess.run(cmd, check=check, capture_output=True, text=True)
        elif capture_stderr:
            result = subprocess.run(cmd, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        else:
            result = subprocess.run(cmd, check=check, text=True)
        return result

    def machine_exists(self) -> bool:
        """Check if the OrbStack machine already exists."""
        result = self.run_command(["orb", "list"], capture_output=True)
        for line in result.stdout.splitlines():
            if line.startswith(f"{self.machine_name}\t") or line.startswith(f"{self.machine_name} "):
                return True
        return False

    def machine_is_running(self) -> bool:
        """Check if the machine is running."""
        result = self.run_command(["orb", "list"], capture_output=True)
        for line in result.stdout.splitlines():
            if (line.startswith(f"{self.machine_name}\t") or line.startswith(f"{self.machine_name} ")) and "running" in line:
                return True
        return False

    def wait_for_machine_ready(self, max_wait: int = 60) -> bool:
        """Wait for machine to be running and SSH-ready."""
        print("==> Waiting for machine to become SSH-ready...")
        elapsed = 0
        while elapsed < max_wait:
            if self.machine_is_running():
                # Give SSH daemon a moment to fully initialize
                time.sleep(2)
                print("    Machine is ready.")
                return True
            time.sleep(2)
            elapsed += 2
        return False

    def get_vm_home(self) -> str:
        """Get the home directory path in the VM."""
        result = self.run_command(
            ["orb", "--machine", self.machine_name, "bash", "-c", "echo $HOME"],
            capture_output=True
        )
        return result.stdout.strip()

    def copy_local_flake(self) -> str:
        """Copy local flake files to the machine. Returns flake path on VM."""
        print("==> Copying local flake files to machine...")

        # Use /etc/nixos as the destination since we're provisioning the entire system
        flake_dest = "/etc/nixos"

        # Determine which files to copy
        flake_dir = Path(self.flake_repo)
        files_to_copy = []

        for file_name in ["flake.nix", "flake.lock", "configuration.nix"]:
            file_path = flake_dir / file_name
            if file_path.exists():
                files_to_copy.append((str(file_path), file_name))

        if not files_to_copy:
            print(f"Error: No flake files found in {self.flake_repo}", file=sys.stderr)
            sys.exit(1)

        # Create /etc/nixos directory if it doesn't exist
        self.run_command([
            "orb", "--machine", self.machine_name, "sudo", "mkdir", "-p", flake_dest
        ])

        # Copy files one by one to /tmp first, then move to /etc/nixos with sudo
        for file_path, file_name in files_to_copy:
            tmp_path = f"/tmp/{file_name}"
            dest_path = f"{flake_dest}/{file_name}"

            # Push to /tmp (no sudo needed)
            self.run_command(["orb", "push", "--machine", self.machine_name, file_path, tmp_path])

            # Move to /etc/nixos with sudo
            self.run_command([
                "orb", "--machine", self.machine_name, "sudo", "mv", tmp_path, dest_path
            ])

        return flake_dest

    def get_flake_path(self) -> str:
        """Determine the flake path to use (local or remote)."""
        if self.flake_repo.startswith("github:") or self.flake_repo.startswith("git+"):
            return self.flake_repo
        else:
            # Local flake - copy to machine
            return self.copy_local_flake()

    def bootstrap_nixos(self, flake_path: str):
        """Bootstrap NixOS configuration using the bootstrap script."""
        print("==> Bootstrapping NixOS configuration from flake...")

        flake_ref = f"{flake_path}#{self.flake_attr}"

        # Get the bootstrap script path (relative to this script)
        script_dir = Path(__file__).parent
        bootstrap_script = script_dir / "bootstrap-nixos.sh"

        if not bootstrap_script.exists():
            print(f"Error: Bootstrap script not found at {bootstrap_script}", file=sys.stderr)
            sys.exit(1)

        # Copy bootstrap script to VM
        vm_script_path = "/tmp/bootstrap-nixos.sh"
        self.run_command([
            "orb", "push", "--machine", self.machine_name,
            str(bootstrap_script), vm_script_path
        ])

        # Make it executable
        self.run_command([
            "orb", "--machine", self.machine_name, "chmod", "+x", vm_script_path
        ])

        # Run the bootstrap script with environment variables
        env = os.environ.copy()
        env.update({
            "FLAKE_REF": flake_ref,
            "NIXOS_HOSTNAME": self.hostname,
            "NIXOS_USERNAME": self.username,
        })

        self.run_command(
            ["orb", "--machine", self.machine_name, "bash", "-c",
             f"FLAKE_REF='{flake_ref}' NIXOS_HOSTNAME='{self.hostname}' NIXOS_USERNAME='{self.username}' {vm_script_path}"]
        )

    def create_machine(self, arch: str):
        """Create and provision a new OrbStack NixOS machine."""
        # Check if machine already exists and fail early
        if self.machine_exists():
            print(f"Error: Machine '{self.machine_name}' already exists.", file=sys.stderr)
            print("To update an existing machine, use the 'nixos-rebuild' command instead:", file=sys.stderr)
            print(f"    provision-orbstack.py nixos-rebuild {self.machine_name}", file=sys.stderr)
            sys.exit(1)

        # Validate and map architecture
        arch_mapping = {
            "aarch64": ("arm64", "aarch64"),
            "arm64": ("arm64", "aarch64"),
            "x86_64": ("amd64", "x86_64"),
            "amd64": ("amd64", "x86_64"),
        }

        if arch not in arch_mapping:
            print(f"Error: Invalid architecture '{arch}'. Use aarch64/arm64 or x86_64/amd64.", file=sys.stderr)
            sys.exit(1)

        orb_arch, nix_system = arch_mapping[arch]

        # Step 1: Create OrbStack machine
        print(f"==> Creating OrbStack NixOS machine: {self.machine_name} (arch: {nix_system})")
        self.run_command([
            "orb", "create", "nixos:25.11", self.machine_name,
            "--arch", orb_arch
        ])

        # Step 2: Wait for machine to be ready
        if not self.wait_for_machine_ready():
            print(f"Error: Machine did not become ready within 60 seconds.", file=sys.stderr)
            sys.exit(1)

        # Step 3: Get flake path (copy if local)
        flake_path = self.get_flake_path()

        # Step 4: Bootstrap NixOS
        self.bootstrap_nixos(flake_path)

        # Done
        print()
        print("==> Provisioning complete!")
        print()
        print("IMPORTANT: After provisioning, connect to your machine with:")
        print(f"    orb --machine {self.machine_name}")
        print()
        print("The following user has been configured:")
        print(f"    Username: {self.username}")
        print(f"    Password: nixos (change after first login)")
        print()
        print("Execute commands directly:")
        print(f"    orb --machine {self.machine_name} <command>")
        print()

    def nixos_rebuild(self, user_config: str | None = None):
        """Run nixos-rebuild switch by executing it on the VM directly."""
        if not self.machine_exists():
            print(f"Error: Machine '{self.machine_name}' does not exist.", file=sys.stderr)
            print("Create it first with: provision-orbstack.py create", file=sys.stderr)
            sys.exit(1)

        if not self.machine_is_running():
            print(f"Error: Machine '{self.machine_name}' is not running.", file=sys.stderr)
            sys.exit(1)

        print(f"==> Running nixos-rebuild switch for machine: {self.machine_name}")

        # Determine the flake path
        flake_path = self.get_flake_path() if not self.flake_repo.startswith("github:") and not self.flake_repo.startswith("git+") else self.flake_repo

        # If using local flake and user config, copy user config to VM
        user_config_vm_path = None
        if user_config:
            user_config_path = Path(user_config).resolve()
            if not user_config_path.exists():
                print(f"Error: User config file not found: {user_config}", file=sys.stderr)
                sys.exit(1)

            print(f"    Copying user config to VM: {user_config_path}")
            user_config_vm_path = "/tmp/user-config.nix"
            self.run_command([
                "orb", "push", "--machine", self.machine_name,
                str(user_config_path), user_config_vm_path
            ])

        # Get the bootstrap script path (relative to this script)
        script_dir = Path(__file__).parent
        bootstrap_script = script_dir / "bootstrap-nixos.sh"

        if not bootstrap_script.exists():
            print(f"Error: Bootstrap script not found at {bootstrap_script}", file=sys.stderr)
            sys.exit(1)

        # Copy bootstrap script to VM
        vm_script_path = "/tmp/bootstrap-nixos.sh"
        self.run_command([
            "orb", "push", "--machine", self.machine_name,
            str(bootstrap_script), vm_script_path
        ])

        # Make it executable
        self.run_command([
            "orb", "--machine", self.machine_name, "chmod", "+x", vm_script_path
        ])

        # Build flake reference
        flake_ref = f"{flake_path}#{self.flake_attr}"

        # Build environment variables for the VM
        env_vars = f"FLAKE_REF='{flake_ref}' NIXOS_HOSTNAME='{self.hostname}' NIXOS_USERNAME='{self.username}'"
        if user_config_vm_path:
            env_vars += f" NIXOS_USER_CONFIG='{user_config_vm_path}'"
            print(f"    Using user config on VM: {user_config_vm_path}")

        # Run the bootstrap script with environment variables
        print(f"    Building and deploying: {flake_ref}")
        self.run_command([
            "orb", "--machine", self.machine_name, "bash", "-c",
            f"{env_vars} {vm_script_path}"
        ])

        print()
        print("==> nixos-rebuild complete!")
        print()


def main():
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
        "--flake-repo",
        default="github:nhooey/orbstack-nixos-provision",
        help="Flake repository (GitHub URL or local path, default: github:nhooey/orbstack-nixos-provision)"
    )
    create_parser.add_argument(
        "--local",
        action="store_true",
        help="Use current directory as flake repository (overrides --flake-repo)"
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
        "--flake-repo",
        default=".",
        help="Flake repository (GitHub URL or local path, default: current directory)"
    )
    rebuild_parser.add_argument(
        "--local",
        action="store_true",
        help="Use current directory as flake repository (overrides --flake-repo)"
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

    args = parser.parse_args()

    # Handle --local flag
    flake_repo = args.flake_repo
    if hasattr(args, 'local') and args.local:
        flake_repo = "."

    # Get username - default to current user
    import getpass
    username = args.username if hasattr(args, 'username') and args.username else getpass.getuser()

    # Create provisioner instance
    provisioner = OrbStackProvisioner(
        machine_name=args.machine_name,
        flake_repo=flake_repo,
        flake_attr=args.flake_attr,
        hostname=args.hostname if hasattr(args, 'hostname') else None,
        username=username
    )

    # Execute command
    if args.command == "create":
        provisioner.create_machine(arch=args.arch)
    elif args.command == "nixos-rebuild":
        provisioner.nixos_rebuild(user_config=args.user_config if hasattr(args, 'user_config') else None)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
