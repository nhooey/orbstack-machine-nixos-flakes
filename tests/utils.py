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


def machine_is_stopped(machine_name: str) -> bool:
    """Check if a machine is stopped."""
    result = run_command(["orb", "list"], check=False)
    if result.returncode != 0:
        return False

    for line in result.stdout.splitlines():
        if (
            line.startswith(f"{machine_name}\t") or line.startswith(f"{machine_name} ")
        ) and "stopped" in line:
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


def start_machine(machine_name: str, max_wait: int = 30) -> bool:
    """Start an OrbStack machine and wait for it to be running."""
    if not machine_exists(machine_name):
        print(f"[TEST] Machine {machine_name} does not exist", file=sys.stderr)
        return False

    if machine_is_running(machine_name):
        print(f"[TEST] Machine {machine_name} is already running", file=sys.stderr)
        return True

    print(f"[TEST] Starting machine {machine_name}...", file=sys.stderr)
    result = run_command(["orb", "start", machine_name], check=False)
    if result.returncode != 0:
        return False

    # Wait for machine to be running
    elapsed = 0
    while elapsed < max_wait:
        if machine_is_running(machine_name):
            # Give SSH daemon a moment to fully initialize
            time.sleep(2)
            print(f"[TEST] Machine {machine_name} is running", file=sys.stderr)
            return True
        time.sleep(2)
        elapsed += 2

    print(f"[TEST] Machine {machine_name} did not start within {max_wait}s", file=sys.stderr)
    return False


def stop_machine(machine_name: str, max_wait: int = 30) -> bool:
    """Stop an OrbStack machine and wait for it to be stopped."""
    if not machine_exists(machine_name):
        print(f"[TEST] Machine {machine_name} does not exist", file=sys.stderr)
        return False

    if machine_is_stopped(machine_name):
        print(f"[TEST] Machine {machine_name} is already stopped", file=sys.stderr)
        return True

    print(f"[TEST] Stopping machine {machine_name}...", file=sys.stderr)
    result = run_command(["orb", "stop", machine_name], check=False)
    if result.returncode != 0:
        return False

    # Wait for machine to be stopped
    elapsed = 0
    while elapsed < max_wait:
        if machine_is_stopped(machine_name):
            print(f"[TEST] Machine {machine_name} stopped successfully", file=sys.stderr)
            return True
        time.sleep(2)
        elapsed += 2

    print(f"[TEST] Machine {machine_name} did not stop within {max_wait}s", file=sys.stderr)
    return False


def clone_machine(source_name: str, dest_name: str, max_wait: int = 60) -> bool:
    """Clone an OrbStack machine from source to destination.

    Ensures source machine is stopped before cloning, then explicitly starts
    the cloned machine and waits for it to be ready.
    """
    if not machine_exists(source_name):
        print(f"[TEST] Source machine {source_name} does not exist", file=sys.stderr)
        return False

    if machine_exists(dest_name):
        print(f"[TEST] Destination machine {dest_name} already exists", file=sys.stderr)
        return False

    # Ensure source machine is stopped
    if not stop_machine(source_name):
        print(f"[TEST] Failed to stop source machine {source_name}", file=sys.stderr)
        return False

    # Clone the machine
    print(f"[TEST] Cloning {source_name} to {dest_name}...", file=sys.stderr)
    result = run_command(["orb", "clone", source_name, dest_name], check=False, timeout=120)
    if result.returncode != 0:
        print(f"[TEST] Failed to clone machine: {result.stderr}", file=sys.stderr)
        return False

    # Verify cloned machine exists
    if not machine_exists(dest_name):
        print(f"[TEST] Cloned machine {dest_name} was not created", file=sys.stderr)
        return False

    # Start the cloned machine (it may be in stopped state after cloning)
    if not machine_is_running(dest_name):
        print(f"[TEST] Starting cloned machine {dest_name}...", file=sys.stderr)
        result = run_command(["orb", "start", dest_name], check=False)
        if result.returncode != 0:
            print(f"[TEST] Failed to start cloned machine: {result.stderr}", file=sys.stderr)
            return False

    # Wait for cloned machine to be ready (running)
    elapsed = 0
    while elapsed < max_wait:
        if machine_is_running(dest_name):
            # Give SSH daemon a moment to fully initialize
            time.sleep(2)
            print(f"[TEST] Cloned machine {dest_name} is ready", file=sys.stderr)
            return True
        time.sleep(2)
        elapsed += 2

    print(f"[TEST] Cloned machine {dest_name} did not become ready within {max_wait}s", file=sys.stderr)
    return False


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


def create_machine_only_direct(
    machine_name: str,
    arch: str | None = None,
    recreate: bool = False,
) -> None:
    """
    Create a machine (without provisioning) by calling the provision script directly.

    This creates a base machine that can be provisioned later or cloned.
    Output is visible in real-time instead of being captured.
    """
    provision = import_provision_script()
    provision.create_machine_only(
        machine_name=machine_name,
        arch=arch,
        recreate=recreate,
    )


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
) -> subprocess.CompletedProcess:
    """
    Run nixos-rebuild by calling the provision script functions directly.

    This allows test output to be visible in real-time instead of being captured.
    Returns a CompletedProcess-like object for consistency with subprocess interface.
    """
    import io
    import sys

    provision = import_provision_script()

    # Capture stderr to return in result
    old_stderr = sys.stderr
    captured_stderr = io.StringIO()

    try:
        sys.stderr = captured_stderr
        provision.nixos_rebuild(
            machine_name=machine_name,
            flake_attr=flake_attr,
            hostname=hostname or machine_name,
            username=username,
            extra_config=extra_config,
        )
        # If we get here, it succeeded
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr=captured_stderr.getvalue(),
        )
    except SystemExit as e:
        # nixos_rebuild calls sys.exit() on error
        return subprocess.CompletedProcess(
            args=[],
            returncode=e.code if e.code is not None else 1,
            stdout="",
            stderr=captured_stderr.getvalue(),
        )
    finally:
        sys.stderr = old_stderr
