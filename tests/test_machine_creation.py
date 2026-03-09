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
    get_provision_script_path,
)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_create_machine_default_settings(test_machine_created, test_username):
    """Test that a machine is provisioned with default settings."""
    machine_name = test_machine_created

    # Verify machine exists (cloned from template)
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
def test_create_machine_custom_hostname(unique_machine_name, test_username):
    """Test creating a machine with custom hostname."""
    machine_name = unique_machine_name
    custom_hostname = f"{machine_name}-custom"

    try:
        create_machine_direct(
            machine_name=machine_name, username=test_username, hostname=custom_hostname
        )
        assert machine_exists(machine_name)

        # Verify hostname is the custom one
        hostname = get_hostname(machine_name)
        assert hostname == custom_hostname
    finally:
        # Cleanup
        if machine_exists(machine_name):
            delete_machine(machine_name, force=True)


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
def test_create_machine_with_recreate(unique_machine_name, test_username):
    """Test creating a machine with --recreate flag."""
    machine_name = unique_machine_name

    try:
        # Create machine first time
        create_machine_direct(machine_name=machine_name, username=test_username)
        # Verify it exists
        assert machine_exists(machine_name)

        # Create again with --recreate
        create_machine_direct(machine_name=machine_name, username=test_username, recreate=True)

        # Machine should still exist and be running
        assert machine_exists(machine_name)
        assert machine_is_running(machine_name)
    finally:
        # Cleanup
        if machine_exists(machine_name):
            delete_machine(machine_name, force=True)


@pytest.mark.requires_orbstack
def test_machine_deletion(unique_machine_name, project_root, test_username):
    """Test machine deletion utility."""
    machine_name = unique_machine_name
    provision_script = get_provision_script_path()

    # Create a machine
    create_machine_direct(machine_name=machine_name, username=test_username)
    assert machine_exists(machine_name)

    # Delete it
    success = delete_machine(machine_name, force=True)
    assert success

    # Verify it's gone
    assert not machine_exists(machine_name)


@pytest.mark.requires_orbstack
def test_wait_for_machine_running(test_machine_created):
    """Test the wait_for_machine_running utility function."""
    machine_name = test_machine_created

    # Machine already running (cloned from template)
    # Should be running
    is_running = wait_for_machine_running(machine_name, max_wait=10)
    assert is_running
