"""Test utilities for OrbStack NixOS provisioning integration tests."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

# Constants
PROVISION_SCRIPT_NAME = "orbstack-machine-nixos-flakes.py"
BOOTSTRAP_SCRIPT_NAME = "bootstrap-nixos.sh"
FLAKE_REPO_DIR = "orbstack-nix-config"
FLAKE_EXTRA_DIR = "extra"
TMP_BASE_DIR = "/tmp/orbstack-machine-nixos-flakes"


def run_command(
    cmd: list[str], check: bool = True, capture_output: bool = True, timeout: int = 300
) -> subprocess.CompletedProcess:
    """Run a shell command with timeout."""
    import shlex

    # Print command for debugging - format as a proper shell command
    cmd_str = " ".join(shlex.quote(arg) for arg in cmd)
    print(f"\n[TEST] Running command [{timeout}s]: {cmd_str}", file=sys.stderr)

    try:
        result = subprocess.run(
            cmd, check=check, capture_output=capture_output, text=True, timeout=timeout
        )
        print(
            f"[TEST] Command completed with return code: {result.returncode}",
            file=sys.stderr,
        )
        return result
    except subprocess.TimeoutExpired as e:
        print(f"\n[TEST ERROR] Command timed out after {timeout}s!", file=sys.stderr)
        print(f"[TEST ERROR] Command: {cmd_str}", file=sys.stderr)
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


def _wait_with_condition(
    machine_name: str,
    max_wait: int,
    condition_func,
    success_msg: str,
    timeout_msg: str,
    stabilize_delay: int = 2,
) -> bool:
    """Helper function to wait for a condition with timeout."""
    elapsed = 0
    while elapsed < max_wait:
        if condition_func(machine_name):
            # Give services a moment to fully initialize
            time.sleep(stabilize_delay)
            print(f"[TEST] {success_msg}", file=sys.stderr)
            return True
        time.sleep(2)
        elapsed += 2

    print(f"[TEST] {timeout_msg}", file=sys.stderr)
    return False


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

    # Wait for the machine to be running
    return _wait_with_condition(
        machine_name,
        max_wait,
        machine_is_running,
        f"Machine {machine_name} is running",
        f"Machine {machine_name} did not start within {max_wait}s",
    )


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

    # Wait for the machine to be stopped
    elapsed = 0
    while elapsed < max_wait:
        if machine_is_stopped(machine_name):
            print(
                f"[TEST] Machine {machine_name} stopped successfully", file=sys.stderr
            )
            return True
        time.sleep(2)
        elapsed += 2

    print(
        f"[TEST] Machine {machine_name} did not stop within {max_wait}s",
        file=sys.stderr,
    )
    return False


def clone_machine(source_name: str, dest_name: str, max_wait: int = 60) -> bool:
    """Clone an OrbStack machine from source to destination.

    Ensures the source machine is stopped before cloning, then explicitly starts
    the cloned machine, then waits for it to be ready.
    """
    if not machine_exists(source_name):
        print(f"[TEST] Source machine {source_name} does not exist", file=sys.stderr)
        return False

    if machine_exists(dest_name):
        print(f"[TEST] Destination machine {dest_name} already exists", file=sys.stderr)
        return False

    # Ensure the source machine is stopped
    if not stop_machine(source_name):
        print(f"[TEST] Failed to stop source machine {source_name}", file=sys.stderr)
        return False

    # Clone the machine
    print(f"[TEST] Cloning {source_name} to {dest_name}...", file=sys.stderr)
    result = run_command(
        ["orb", "clone", source_name, dest_name], check=False, timeout=120
    )
    if result.returncode != 0:
        print(f"[TEST] Failed to clone machine: {result.stderr}", file=sys.stderr)
        return False

    # Verify a cloned machine exists
    if not machine_exists(dest_name):
        print(f"[TEST] Cloned machine {dest_name} was not created", file=sys.stderr)
        return False

    # Start the cloned machine (it may be in stopped state after cloning)
    if not machine_is_running(dest_name):
        print(f"[TEST] Starting cloned machine {dest_name}...", file=sys.stderr)
        result = run_command(["orb", "start", dest_name], check=False)
        if result.returncode != 0:
            print(
                f"[TEST] Failed to start cloned machine: {result.stderr}",
                file=sys.stderr,
            )
            return False

    # Wait for the cloned machine to be ready (running)
    return _wait_with_condition(
        dest_name,
        max_wait,
        machine_is_running,
        f"Cloned machine {dest_name} is ready",
        f"Cloned machine {dest_name} did not become ready within {max_wait}s",
    )


def wait_for_machine_running(machine_name: str, max_wait: int = 60) -> bool:
    """Wait for the machine to be in a running state."""
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
    timeout: int = 120,
    login_shell: bool = False,
) -> subprocess.CompletedProcess:
    """Execute a command on an OrbStack machine."""
    if login_shell:
        import shlex

        cmd_str = " ".join(shlex.quote(str(arg)) for arg in command)
        cmd = ["orb", "--machine", machine_name, "bash", "-lc", cmd_str]
    else:
        cmd = ["orb", "--machine", machine_name] + command
    return run_command(cmd, check=check, timeout=timeout)


def wait_for_network_online(machine_name: str, max_wait: int = 30) -> bool:
    """Wait for the network to be fully online on the machine.

    Waits for network-online.target and verifies DNS resolution works.
    This prevents intermittent DNS failures during nix builds.
    """
    print(
        f"[TEST] Waiting for network to be online on {machine_name}...", file=sys.stderr
    )

    # Wait for network-online.target
    elapsed = 0
    while elapsed < max_wait:
        result = exec_on_machine(
            machine_name,
            ["systemctl", "is-active", "network-online.target"],
            check=False,
            timeout=30,
        )
        if result.returncode == 0:
            print("[TEST] network-online.target is active", file=sys.stderr)
            break
        time.sleep(2)
        elapsed += 2
    else:
        print(
            f"[TEST] WARNING: network-online.target not active after {max_wait}s",
            file=sys.stderr,
        )

    # Verify DNS actually works by pinging cache.nixos.org
    for attempt in range(5):
        result = exec_on_machine(
            machine_name,
            ["ping", "-c", "1", "-W", "2", "cache.nixos.org"],
            check=False,
            timeout=10,
        )
        if result.returncode == 0:
            print(
                "[TEST] DNS resolution verified (cache.nixos.org reachable)",
                file=sys.stderr,
            )
            return True
        print(
            f"[TEST] DNS check attempt {attempt + 1}/5 failed, retrying...",
            file=sys.stderr,
        )
        time.sleep(2)

    print(
        "[TEST] WARNING: DNS resolution still not working after retries",
        file=sys.stderr,
    )
    return False


def file_exists_on_machine(machine_name: str, file_path: str) -> bool:
    """Check if a file exists on the machine."""
    result = exec_on_machine(machine_name, ["test", "-f", file_path], check=False)
    return result.returncode == 0


def read_file_on_machine(machine_name: str, file_path: str) -> str:
    """Read a file from the machine."""
    result = exec_on_machine(machine_name, ["cat", file_path], check=True)
    return str(result.stdout)


def get_installed_packages(machine_name: str) -> list[str]:
    """Get a list of installed packages on the NixOS machine."""
    result = exec_on_machine(machine_name, ["nix-env", "-q"], check=True)
    return str(result.stdout).strip().splitlines()


def service_is_active(machine_name: str, service_name: str) -> bool:
    """Check if a systemd service is active."""
    result = exec_on_machine(
        machine_name, ["systemctl", "is-active", service_name], check=False
    )
    return result.returncode == 0 and result.stdout.strip() == "active"


def get_hostname(machine_name: str) -> str:
    """Get the configured hostname of the machine from /etc/hostname.

    Note: This reads the configured hostname, not the running hostname.
    The running hostname may differ until the machine is rebooted.
    """
    result = exec_on_machine(machine_name, ["cat", "/etc/hostname"], check=True)
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


def verify_flake_deployed(
    machine_name: str, expected_files: list[str] | None = None
) -> bool:
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


def get_provision_script_path() -> Path:
    """Get the path to the provision script."""
    return get_project_root() / PROVISION_SCRIPT_NAME


def import_provision_script():
    """
    Import the provision script as a module.

    Returns the module object which can be used to access functions like get_architecture.
    This is needed because the script has a hyphen in the filename.
    """
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "orbstack_nixos_provision", get_provision_script_path()
    )
    provision_module = importlib.util.module_from_spec(spec)
    sys.modules["orbstack_nixos_provision"] = provision_module
    spec.loader.exec_module(provision_module)

    return provision_module


def create_machine_only_direct(
    machine_name: str,
    arch: str | None = None,
    recreate: bool = False,
    verbose: bool = True,
) -> None:
    """
    Create a machine (without provisioning) by calling the provision script directly.

    This creates a base machine that can be provisioned later or cloned.
    Output is visible in real-time instead of being captured.
    """
    print(f"[TEST] Creating machine (no provision): {machine_name}", file=sys.stderr)
    provision = import_provision_script()
    provision.create_machine_only(
        machine_name=machine_name,
        arch=arch,
        recreate=recreate,
        verbose=verbose,
    )
    print(f"[TEST] Machine created successfully: {machine_name}", file=sys.stderr)


def _print_operation_details(
    operation: str,
    machine_name: str,
    hostname: str,
    username: str,
    flake_attr: str,
    extra_config: str | None = None,
    recreate: bool = False,
) -> None:
    """Helper function to print operation details."""
    print(f"[TEST] {operation} machine: {machine_name}", file=sys.stderr)
    print(f"[TEST]   hostname: {hostname}", file=sys.stderr)
    print(f"[TEST]   username: {username}", file=sys.stderr)
    print(f"[TEST]   flake_attr: {flake_attr}", file=sys.stderr)
    if extra_config:
        print(f"[TEST]   extra_config: {extra_config}", file=sys.stderr)
    if recreate:
        print("[TEST]   recreate: True", file=sys.stderr)


def create_machine_direct(
    machine_name: str,
    username: str,
    hostname: str | None = None,
    arch: str | None = None,
    extra_config: str | None = None,
    recreate: bool = False,
    flake_attr: str = "default",
    verbose: bool = True,
) -> None:
    """
    Create a machine by calling the provision script functions directly.

    This allows test output to be visible in real-time instead of being captured.
    Raises SystemExit on failure (as expected by the provision script).
    """
    actual_hostname = hostname or machine_name
    _print_operation_details(
        "Creating and provisioning",
        machine_name,
        actual_hostname,
        username,
        flake_attr,
        extra_config,
        recreate,
    )

    provision = import_provision_script()
    try:
        provision.create_machine(
            machine_name=machine_name,
            flake_attr=flake_attr,
            hostname=actual_hostname,
            username=username,
            arch=arch,
            extra_config=extra_config,
            recreate=recreate,
            verbose=verbose,
        )
        print(
            f"[TEST] Machine created and provisioned successfully: {machine_name}",
            file=sys.stderr,
        )
    except SystemExit as e:
        # Re-raise SystemExit so pytest can catch it properly
        print(
            f"[TEST] Machine creation failed for {machine_name} with exit code {e.code}",
            file=sys.stderr,
        )
        raise


def nixos_rebuild_direct(
    machine_name: str,
    username: str,
    hostname: str | None = None,
    extra_config: str | None = None,
    flake_attr: str = "default",
    verbose: bool = True,
) -> subprocess.CompletedProcess:
    """
    Run nixos-rebuild by calling the provision script functions directly.

    This allows test output to be visible in real-time instead of being captured.
    Returns a CompletedProcess-like object for consistency with subprocess interface.
    """
    import io

    actual_hostname = hostname or machine_name
    _print_operation_details(
        "Running nixos-rebuild on",
        machine_name,
        actual_hostname,
        username,
        flake_attr,
        extra_config,
    )

    provision = import_provision_script()

    # Wait for the network to be ready to prevent intermittent DNS failures
    wait_for_network_online(machine_name)

    # Capture stderr to return in the result
    old_stderr = sys.stderr
    captured_stderr = io.StringIO()

    try:
        sys.stderr = captured_stderr
        provision.nixos_rebuild(
            machine_name=machine_name,
            flake_attr=flake_attr,
            hostname=actual_hostname,
            username=username,
            extra_config=extra_config,
            verbose=verbose,
        )

        # If we get here, it succeeded
        print(
            f"[TEST] nixos-rebuild completed successfully on {machine_name}",
            file=old_stderr,
        )
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr=captured_stderr.getvalue(),
        )
    except SystemExit as e:
        # nixos_rebuild calls sys.exit() on error
        print(
            f"[TEST] nixos-rebuild failed on {machine_name} with exit code {e.code}",
            file=old_stderr,
        )
        return subprocess.CompletedProcess(
            args=[],
            returncode=e.code if e.code is not None else 1,
            stdout="",
            stderr=captured_stderr.getvalue(),
        )
    finally:
        sys.stderr = old_stderr
