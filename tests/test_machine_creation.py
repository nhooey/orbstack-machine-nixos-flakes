"""Tests for basic machine creation functionality."""

from __future__ import annotations

import pytest

from tests.utils import (
    machine_exists,
    machine_is_running,
    wait_for_machine_running,
    user_exists,
    get_hostname,
    delete_machine,
    run_command,
    create_machine_direct,
    nixos_rebuild_direct,
)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_create_machine_default_settings(test_machine, project_root, test_username):
    """Test creating a machine with default settings."""
    machine_name = test_machine
    provision_script = project_root / "orbstack-nixos-provision.py"

    # Machine should not exist yet
    assert not machine_exists(machine_name)

    # Create the machine
    create_machine_direct(machine_name=machine_name, username=test_username)

    # Verify machine exists
    assert machine_exists(machine_name)

    # Verify machine is running
    assert machine_is_running(machine_name)

    # Verify hostname matches machine name
    hostname = get_hostname(machine_name)
    assert hostname == machine_name

    # Verify user exists
    assert user_exists(machine_name, test_username)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_create_machine_custom_hostname(test_machine, project_root, test_username):
    """Test creating a machine with custom hostname."""
    machine_name = test_machine
    custom_hostname = f"{machine_name}-custom"
    provision_script = project_root / "orbstack-nixos-provision.py"

    create_machine_direct(
        machine_name=machine_name, username=test_username, hostname=custom_hostname
    )
    assert machine_exists(machine_name)

    # Verify hostname is the custom one
    hostname = get_hostname(machine_name)
    assert hostname == custom_hostname


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_create_machine_custom_username(test_machine, project_root):
    """Test creating a machine with custom username."""
    machine_name = test_machine
    custom_user = "testuser"
    provision_script = project_root / "orbstack-nixos-provision.py"

    create_machine_direct(machine_name=machine_name, username=custom_user)
    assert machine_exists(machine_name)

    # Verify custom user exists
    assert user_exists(machine_name, custom_user)


@pytest.mark.requires_orbstack
def test_create_machine_already_exists(test_machine_created, project_root, test_username):
    """Test that creating an existing machine fails without --recreate."""
    machine_name = test_machine_created

    # Try to create again without --recreate - should raise SystemExit
    with pytest.raises(SystemExit) as exc_info:
        create_machine_direct(machine_name=machine_name, username=test_username)

    # Should exit with non-zero code
    assert exc_info.value.code != 0


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_create_machine_with_recreate(test_machine, project_root, test_username):
    """Test creating a machine with --recreate flag."""
    machine_name = test_machine
    provision_script = project_root / "orbstack-nixos-provision.py"

    # Create machine first time
    create_machine_direct(machine_name=machine_name, username=test_username)
    # Verify it exists
    assert machine_exists(machine_name)

    # Create again with --recreate
    create_machine_direct(machine_name=machine_name, username=test_username, recreate=True)

    # Machine should still exist and be running
    assert machine_exists(machine_name)
    assert machine_is_running(machine_name)


@pytest.mark.requires_orbstack
def test_machine_deletion(unique_machine_name, project_root, test_username):
    """Test machine deletion utility."""
    machine_name = unique_machine_name
    provision_script = project_root / "orbstack-nixos-provision.py"

    # Create a machine
    create_machine_direct(machine_name=machine_name, username=test_username)
    assert machine_exists(machine_name)

    # Delete it
    success = delete_machine(machine_name, force=True)
    assert success

    # Verify it's gone
    assert not machine_exists(machine_name)


@pytest.mark.requires_orbstack
def test_wait_for_machine_running(test_machine, project_root, test_username):
    """Test the wait_for_machine_running utility function."""
    machine_name = test_machine
    provision_script = project_root / "orbstack-nixos-provision.py"

    # Create machine
    create_machine_direct(machine_name=machine_name, username=test_username)

    # Should be running
    is_running = wait_for_machine_running(machine_name, max_wait=10)
    assert is_running
