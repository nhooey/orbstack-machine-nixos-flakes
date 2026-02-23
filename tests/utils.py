"""Test utilities for OrbStack NixOS provisioning integration tests."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path


def run_command(
    cmd: list[str],
    check: bool = True,
    capture_output: bool = True,
    timeout: int = 300
) -> subprocess.CompletedProcess:
    """Run a shell command with timeout."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture_output,
        text=True,
        timeout=timeout
    )


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
        if (line.startswith(f"{machine_name}\t") or
            line.startswith(f"{machine_name} ")) and "running" in line:
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
    machine_name: str,
    command: list[str],
    check: bool = True,
    timeout: int = 120
) -> subprocess.CompletedProcess:
    """Execute a command on an OrbStack machine."""
    cmd = ["orb", "--machine", machine_name] + command
    return run_command(cmd, check=check, timeout=timeout)


def file_exists_on_machine(machine_name: str, file_path: str) -> bool:
    """Check if a file exists on the machine."""
    result = exec_on_machine(
        machine_name,
        ["test", "-f", file_path],
        check=False
    )
    return result.returncode == 0


def read_file_on_machine(machine_name: str, file_path: str) -> str:
    """Read a file from the machine."""
    result = exec_on_machine(
        machine_name,
        ["cat", file_path],
        check=True
    )
    return result.stdout


def get_installed_packages(machine_name: str) -> list[str]:
    """Get list of installed packages on NixOS machine."""
    result = exec_on_machine(
        machine_name,
        ["nix-env", "-q"],
        check=True
    )
    return result.stdout.strip().splitlines()


def service_is_active(machine_name: str, service_name: str) -> bool:
    """Check if a systemd service is active."""
    result = exec_on_machine(
        machine_name,
        ["systemctl", "is-active", service_name],
        check=False
    )
    return result.returncode == 0 and result.stdout.strip() == "active"


def get_hostname(machine_name: str) -> str:
    """Get the hostname of the machine."""
    result = exec_on_machine(machine_name, ["hostname"], check=True)
    return result.stdout.strip()


def user_exists(machine_name: str, username: str) -> bool:
    """Check if a user exists on the machine."""
    result = exec_on_machine(
        machine_name,
        ["id", "-u", username],
        check=False
    )
    return result.returncode == 0


def get_nix_system_architecture(machine_name: str) -> str:
    """Get the Nix system architecture string."""
    result = exec_on_machine(
        machine_name,
        ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"],
        check=True
    )
    return result.stdout.strip()


def verify_flake_deployed(machine_name: str, expected_files: list[str] = None) -> bool:
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
        "orbstack_nixos_provision",
        project_root / "orbstack-nixos-provision.py"
    )
    provision_module = importlib.util.module_from_spec(spec)
    sys.modules["orbstack_nixos_provision"] = provision_module
    spec.loader.exec_module(provision_module)

    return provision_module
