"""Pytest configuration and fixtures for integration tests."""

from __future__ import annotations

import getpass
import time
from typing import Generator

import pytest

from tests.utils import (
    delete_machine,
    machine_exists,
    orbstack_is_installed,
    get_project_root,
    create_machine_direct,
    clone_machine,
)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "requires_orbstack: marks tests that require OrbStack to be installed"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on conditions."""
    if not orbstack_is_installed():
        skip_orbstack = pytest.mark.skip(reason="OrbStack not installed")
        for item in items:
            if "requires_orbstack" in item.keywords or item.fspath.basename.startswith("test_"):
                item.add_marker(skip_orbstack)


@pytest.fixture(scope="session")
def project_root():
    """Get the project root directory."""
    return get_project_root()


@pytest.fixture(scope="session")
def session_timestamp():
    """Generate a single timestamp for the entire test session.

    This timestamp is shared by the template machine and all cloned machines,
    making it easy to identify which test run they belong to.
    """
    return int(time.time() * 1000)  # milliseconds


@pytest.fixture(scope="session")
def test_username():
    """Get username for tests."""
    return getpass.getuser()


@pytest.fixture
def unique_machine_name(request, session_timestamp):
    """Generate a unique machine name for testing.

    Names follow the pattern: test-{normalized_test_name}-{timestamp}
    where the timestamp is shared across all tests in the session.
    """
    # Get test name from request and normalize it
    test_name = request.node.name
    # Remove 'test_' prefix if present
    if test_name.startswith("test_"):
        test_name = test_name[5:]
    # Replace underscores and brackets with hyphens, convert to lowercase
    normalized_name = test_name.replace("_", "-").replace("[", "-").replace("]", "").lower()
    # Remove any trailing hyphens
    normalized_name = normalized_name.rstrip("-")

    return f"test-{normalized_name}-{session_timestamp}"


@pytest.fixture(scope="session")
def template_machine(session_timestamp, test_username) -> Generator[str, None, None]:
    """
    Session-scoped fixture that creates a master template machine.

    This template is created once per test session and can be cloned
    for individual tests, avoiding the expensive provisioning step.
    The template is stopped after creation to enable cloning.
    """
    from tests.utils import stop_machine

    template_name = f"test-MASTER-{session_timestamp}"

    print(f"\n{'='*80}")
    print(f"Creating master template machine: {template_name}")
    print(f"This will be cloned for all tests in this session")
    print(f"{'='*80}\n")

    # Create and provision the template machine
    create_machine_direct(machine_name=template_name, username=test_username)

    # Stop the template machine so it can be cloned
    print(f"\nStopping template machine {template_name} to enable cloning...")
    if not stop_machine(template_name):
        print(f"Warning: Failed to stop template machine {template_name}")

    yield template_name

    # Cleanup: delete template machine after all tests
    if machine_exists(template_name):
        print(f"\nCleaning up master template machine: {template_name}")
        delete_machine(template_name, force=True)


@pytest.fixture
def test_machine(unique_machine_name, template_machine) -> Generator[str, None, None]:
    """
    Fixture that clones a machine from the template and ensures cleanup.

    Clones from the master template machine for much faster test setup.
    """
    machine_name = unique_machine_name

    # Clone from template
    print(f"\nCloning test machine {machine_name} from template {template_machine}")
    success = clone_machine(template_machine, machine_name)
    if not success:
        raise RuntimeError(f"Failed to clone machine {machine_name} from {template_machine}")

    yield machine_name

    # Cleanup: delete machine if it exists
    if machine_exists(machine_name):
        print(f"\nCleaning up test machine: {machine_name}")
        delete_machine(machine_name, force=True)


@pytest.fixture
def test_machine_created(test_machine, test_username) -> Generator[str, None, None]:
    """
    Fixture that provides a pre-created and fully configured machine for tests.

    The machine is cloned from the template for speed, but we run nixos-rebuild
    to ensure the full Nix configuration from flake.nix and configuration.nix
    is applied, since OrbStack cloning doesn't preserve the complete Nix store.
    """
    from tests.utils import nixos_rebuild_direct, start_machine

    machine_name = test_machine

    # Ensure machine is running
    print(f"\nStarting machine {machine_name}...")
    start_machine(machine_name)

    # Apply Nix configuration (cloning doesn't preserve full Nix store)
    print(f"\nApplying Nix configuration to {machine_name}...")
    nixos_rebuild_direct(machine_name=machine_name, username=test_username)

    yield machine_name

    # Cleanup is handled by test_machine fixture


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

    # Config that adds a user to docker group (for use with docker.nix)
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
  # Missing closing bracket
}
"""
    )

    return configs_dir
