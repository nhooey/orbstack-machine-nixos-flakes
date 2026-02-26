"""Test utilities for OrbStack NixOS provisioning integration tests."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


def run_command(
    cmd: list[str], check: bool = True, capture_output: bool = True, timeout: int = 300
) -> subprocess.CompletedProcess:
    """Run a shell command with timeout."""
    # Print command for debugging
    print(f"\n[TEST] Running command: {' '.join(cmd)}", file=sys.stderr)
    print(f"[TEST] Timeout: {timeout}s", file=sys.stderr)

    try:
        result = subprocess.run(
            cmd, check=check, capture_output=capture_output, text=True, timeout=timeout
        )
        print(f"[TEST] Command completed with return code: {result.returncode}", file=sys.stderr)
        return result
    except subprocess.TimeoutExpired as e:
        print(f"\n[TEST ERROR] Command timed out after {timeout}s!", file=sys.stderr)
        print(f"[TEST ERROR] Command: {' '.join(cmd)}", file=sys.stderr)
        if e.stdout:
            stdout_str = e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout
            print(f"[TEST ERROR] Partial stdout:\n{stdout_str}", file=sys.stderr)
        if e.stderr:
            stderr_str = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
            print(f"[TEST ERROR] Partial stderr:\n{stderr_str}", file=sys.stderr)
        raise


def machine_exists(machine_name: str) -> bool:
    """Check if an OrbStack machine exists."""
    result = run_command(["orb", "list"], check=False)
    if result.returncode != 0:
        return False

    for line in result.stdout.splitlines():
        if line.startswith(f"{machine_name}\t") or line.startswith(f"{machine_name} "):
            return True
    return False


def machine_is_running(machine_name: str) -> bool:
    """Check if a machine is running."""
    result = run_command(["orb", "list"], check=False)
    if result.returncode != 0:
        return False

    for line in result.stdout.splitlines():
        if (
            line.startswith(f"{machine_name}\t") or line.startswith(f"{machine_name} ")
        ) and "running" in line:
            return True
    return False


def delete_machine(machine_name: str, force: bool = True) -> bool:
    """Delete an OrbStack machine if it exists."""
    if not machine_exists(machine_name):
        return True

    cmd = ["orb", "delete", machine_name]
    if force:
        cmd.insert(2, "-f")

    result = run_command(cmd, check=False)
    return result.returncode == 0


def wait_for_machine_running(machine_name: str, max_wait: int = 60) -> bool:
    """Wait for machine to be in running state."""
    elapsed = 0
    while elapsed < max_wait:
        if machine_is_running(machine_name):
            # Give it an extra moment to stabilize
            time.sleep(2)
            return True
        time.sleep(2)
        elapsed += 2
    return False


def exec_on_machine(
    machine_name: str, command: list[str], check: bool = True, timeout: int = 120
) -> subprocess.CompletedProcess:
    """Execute a command on an OrbStack machine."""
    cmd = ["orb", "--machine", machine_name] + command
    return run_command(cmd, check=check, timeout=timeout)


def file_exists_on_machine(machine_name: str, file_path: str) -> bool:
    """Check if a file exists on the machine."""
    result = exec_on_machine(machine_name, ["test", "-f", file_path], check=False)
    return result.returncode == 0


def read_file_on_machine(machine_name: str, file_path: str) -> str:
    """Read a file from the machine."""
    result = exec_on_machine(machine_name, ["cat", file_path], check=True)
    return str(result.stdout)


def get_installed_packages(machine_name: str) -> list[str]:
    """Get list of installed packages on NixOS machine."""
    result = exec_on_machine(machine_name, ["nix-env", "-q"], check=True)
    return str(result.stdout).strip().splitlines()


def service_is_active(machine_name: str, service_name: str) -> bool:
    """Check if a systemd service is active."""
    result = exec_on_machine(machine_name, ["systemctl", "is-active", service_name], check=False)
    return result.returncode == 0 and result.stdout.strip() == "active"


def get_hostname(machine_name: str) -> str:
    """Get the hostname of the machine."""
    result = exec_on_machine(machine_name, ["hostname"], check=True)
    return str(result.stdout).strip()


def user_exists(machine_name: str, username: str) -> bool:
    """Check if a user exists on the machine."""
    result = exec_on_machine(machine_name, ["id", "-u", username], check=False)
    return result.returncode == 0


def get_nix_system_architecture(machine_name: str) -> str:
    """Get the Nix system architecture string."""
    result = exec_on_machine(
        machine_name,
        ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"],
        check=True,
    )
    return str(result.stdout).strip()


def verify_flake_deployed(machine_name: str, expected_files: list[str] | None = None) -> bool:
    """Verify flake files exist in /etc/nixos/."""
    if expected_files is None:
        expected_files = ["flake.nix", "flake.lock", "configuration.nix"]

    for file in expected_files:
        if not file_exists_on_machine(machine_name, f"/etc/nixos/{file}"):
            return False
    return True


def orbstack_is_installed() -> bool:
    """Check if OrbStack is installed and available."""
    result = run_command(["which", "orb"], check=False)
    return result.returncode == 0


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def import_provision_script():
    """
    Import the orbstack-nixos-provision.py script as a module.

    Returns the module object which can be used to access functions like get_architecture.
    This is needed because the script has a hyphen in the filename.
    """
    import importlib.util
    import sys

    project_root = get_project_root()
    spec = importlib.util.spec_from_file_location(
        "orbstack_nixos_provision", project_root / "orbstack-nixos-provision.py"
    )
    provision_module = importlib.util.module_from_spec(spec)
    sys.modules["orbstack_nixos_provision"] = provision_module
    spec.loader.exec_module(provision_module)

    return provision_module


def create_machine_direct(
    machine_name: str,
    username: str,
    hostname: str | None = None,
    arch: str | None = None,
    extra_config: str | None = None,
    recreate: bool = False,
    flake_attr: str = "default",
) -> None:
    """
    Create a machine by calling the provision script functions directly.

    This allows test output to be visible in real-time instead of being captured.
    """
    provision = import_provision_script()
    provision.create_machine(
        machine_name=machine_name,
        flake_attr=flake_attr,
        hostname=hostname or machine_name,
        username=username,
        arch=arch,
        extra_config=extra_config,
        recreate=recreate,
    )


def nixos_rebuild_direct(
    machine_name: str,
    username: str,
    hostname: str | None = None,
    extra_config: str | None = None,
    flake_attr: str = "default",
) -> None:
    """
    Run nixos-rebuild by calling the provision script functions directly.

    This allows test output to be visible in real-time instead of being captured.
    """
    provision = import_provision_script()
    provision.nixos_rebuild(
        machine_name=machine_name,
        flake_attr=flake_attr,
        hostname=hostname or machine_name,
        username=username,
        extra_config=extra_config,
    )
