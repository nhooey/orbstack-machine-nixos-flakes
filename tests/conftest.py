"""Pytest configuration and fixtures for integration tests."""

from __future__ import annotations

import getpass
import time
from typing import Generator

import pytest

from tests.utils import (
    clone_machine,
    create_machine_direct,
    delete_machine,
    get_project_root,
    machine_exists,
    orbstack_is_installed,
)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers",
        "requires_orbstack: marks tests that require OrbStack to be installed",
    )


def pytest_collection_modifyitems(items):
    """Auto-mark tests based on conditions."""
    if not orbstack_is_installed():
        skip_orbstack = pytest.mark.skip(reason="OrbStack not installed")
        for item in items:
            if "requires_orbstack" in item.keywords or item.fspath.basename.startswith(
                "test_"
            ):
                item.add_marker(skip_orbstack)


@pytest.fixture(scope="session")
def project_root():
    """Get the project's root directory."""
    return get_project_root()


@pytest.fixture(scope="session")
def session_timestamp():
    """Generate a single timestamp for the entire test session.

    This timestamp is shared by the template machine and all cloned machines,
    making it easy to identify which test run the machines belong to.
    """
    return int(time.time() * 1000)  # milliseconds


@pytest.fixture(scope="session")
def test_username():
    """Get the username for tests."""
    return getpass.getuser()


@pytest.fixture
def unique_machine_name(request, session_timestamp):
    """Generate a unique machine name for testing.

    Names follow the pattern: test-nixos-{timestamp}-{test_index}
    where the test index is extracted from the test function name.

    Test functions should be named with a numeric index prefix (e.g., test_001_foo).
    """
    import re

    # Get the test name and extract the index number
    test_name = request.node.name

    # Extract the numeric index from the test function name (e.g., test_001_foo -> 001)
    match = re.search(r"test_(\d{3})_", test_name)
    if match:
        test_index = match.group(1)
    else:
        # Fallback if no index is found in the test name
        test_index = "000"

    return f"test-nixos-{session_timestamp}-{test_index}"


@pytest.fixture(scope="session")
def template_machine(session_timestamp, test_username) -> Generator[str, None, None]:
    """
    Session-scoped fixture that creates a master template machine.

    This template is created once per test session and can be cloned
    for individual tests, avoiding the expensive provisioning step.
    The template is stopped after creation to enable cloning.
    """
    import sys

    from tests.utils import stop_machine

    template_name = f"test-MASTER-{session_timestamp}"

    print(f"\n{'=' * 80}", file=sys.stderr)
    print(
        f"[TEST] Creating the master template machine: {template_name}", file=sys.stderr
    )
    print("[TEST] This will be cloned for all tests in this session", file=sys.stderr)
    print(f"{'=' * 80}\n", file=sys.stderr)

    # Create and provision the template machine
    create_machine_direct(machine_name=template_name, username=test_username)

    # Stop the template machine so it can be cloned
    print(
        f"\n[TEST] Stopping the template machine {template_name} to enable cloning...",
        file=sys.stderr,
    )
    if not stop_machine(template_name):
        print(
            f"[TEST] WARNING: Failed to stop the template machine {template_name}",
            file=sys.stderr,
        )

    yield template_name

    # Cleanup: delete the template machine after all tests
    if machine_exists(template_name):
        print(
            f"\n[TEST] Cleaning up the master template machine: {template_name}",
            file=sys.stderr,
        )
        delete_machine(template_name, force=True)


@pytest.fixture
def test_machine(unique_machine_name, template_machine) -> Generator[str, None, None]:
    """
    Fixture that clones a machine from the template and ensures cleanup.

    Clones from the master template machine for much faster test setup.
    """
    import sys

    machine_name = unique_machine_name

    # Clone from the template
    print(
        f"\n[TEST] Cloning the test machine {machine_name} from template {template_machine}",
        file=sys.stderr,
    )
    success = clone_machine(template_machine, machine_name)
    if not success:
        raise RuntimeError(
            f"Failed to clone the machine {machine_name} from {template_machine}"
        )

    yield machine_name

    # Cleanup: delete the machine if it exists
    if machine_exists(machine_name):
        print(f"\n[TEST] Cleaning up the test machine: {machine_name}", file=sys.stderr)
        delete_machine(machine_name, force=True)


@pytest.fixture
def test_machine_created(test_machine, test_username) -> Generator[str, None, None]:
    """
    Fixture that provides a pre-created and fully configured machine for tests.

    The machine is cloned from the template for speed, but we run nixos-rebuild
    to ensure the full Nix configuration from flake.nix and configuration.nix
    is applied with the correct hostname and username, since OrbStack cloning
    doesn't update these parameters.
    """
    import sys

    from tests.utils import nixos_rebuild_direct, start_machine

    machine_name = test_machine

    # Ensure the machine is running
    print(f"\n[TEST] Starting the machine {machine_name}...", file=sys.stderr)
    start_machine(machine_name)

    # Apply the Nix configuration with the correct hostname and username
    # This ensures cloned machines get their unique hostname set correctly
    # Note: nixos_rebuild_direct automatically sets the hostname after rebuild
    print(
        f"\n[TEST] Applying the Nix configuration to {machine_name}...", file=sys.stderr
    )
    nixos_rebuild_direct(
        machine_name=machine_name, hostname=machine_name, username=test_username
    )

    yield machine_name

    # Cleanup is handled by the test_machine fixture


@pytest.fixture(scope="session")
def sample_configs_dir(project_root, tmp_path_factory):
    """Create sample config files for testing."""
    configs_dir = tmp_path_factory.mktemp("sample_configs")

    # Simple config that adds a package
    simple_config = configs_dir / "simple.nix"
    simple_config.write_text(
        """{ config, pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    tmux
  ];
}
"""
    )

    # Config that enables a service
    service_config = configs_dir / "with-service.nix"
    service_config.write_text(
        """{ config, pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    neofetch
    jq
  ];

  # Add a simple marker file to verify this config was applied
  environment.etc."test-marker".text = "extra-config-applied";
}
"""
    )

    # Config that adds a user to the docker group (for use with docker.nix)
    docker_user_config = configs_dir / "docker-user.nix"
    docker_user_config.write_text(
        """{ config, pkgs, username, ... }:

{
  users.users.${username}.extraGroups = [ "docker" ];
}
"""
    )

    # Invalid config (syntax error)
    invalid_config = configs_dir / "invalid.nix"
    invalid_config.write_text(
        """{ config, pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    tmux
  # Missing the closing bracket
}
"""
    )

    return configs_dir
