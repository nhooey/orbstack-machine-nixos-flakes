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
def test_username():
    """Get username for tests."""
    return getpass.getuser()


@pytest.fixture
def unique_machine_name():
    """Generate a unique machine name for testing."""
    timestamp = int(time.time() * 1000)  # milliseconds
    return f"test-orbstack-{timestamp}"


@pytest.fixture
def test_machine(unique_machine_name) -> Generator[str, None, None]:
    """
    Fixture that provides a unique machine name and ensures cleanup.

    Does NOT create the machine - tests should create it themselves.
    This fixture only handles cleanup.
    """
    machine_name = unique_machine_name

    yield machine_name

    # Cleanup: delete machine if it exists
    if machine_exists(machine_name):
        print(f"\nCleaning up test machine: {machine_name}")
        delete_machine(machine_name, force=True)


@pytest.fixture
def test_machine_created(test_machine, project_root, test_username) -> Generator[str, None, None]:
    """
    Fixture that creates a test machine with default configuration.

    Use this when you need a pre-created machine for your test.
    """
    import subprocess

    machine_name = test_machine
    provision_script = project_root / "orbstack-nixos-provision.py"

    # Create the machine
    cmd = [
        "python3",
        str(provision_script),
        "create",
        machine_name,
        "--username", test_username,
    ]

    # Run with longer timeout since provisioning takes time
    subprocess.run(cmd, check=True, timeout=600)

    yield machine_name

    # Cleanup is handled by test_machine fixture


@pytest.fixture(scope="session")
def sample_configs_dir(project_root, tmp_path_factory):
    """Create sample config files for testing."""
    configs_dir = tmp_path_factory.mktemp("sample_configs")

    # Simple config that adds a package
    simple_config = configs_dir / "simple.nix"
    simple_config.write_text("""{ config, pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    tmux
  ];
}
""")

    # Config that enables a service
    service_config = configs_dir / "with-service.nix"
    service_config.write_text("""{ config, pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    neofetch
    jq
  ];

  # Add a simple marker file to verify this config was applied
  environment.etc."test-marker".text = "extra-config-applied";
}
""")

    # Config that adds a user to docker group (for use with docker.nix)
    docker_user_config = configs_dir / "docker-user.nix"
    docker_user_config.write_text("""{ config, pkgs, username, ... }:

{
  users.users.${username}.extraGroups = [ "docker" ];
}
""")

    # Invalid config (syntax error)
    invalid_config = configs_dir / "invalid.nix"
    invalid_config.write_text("""{ config, pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    tmux
  # Missing closing bracket
}
""")

    return configs_dir
