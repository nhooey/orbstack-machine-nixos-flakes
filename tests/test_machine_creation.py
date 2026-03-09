"""Tests for basic machine creation functionality."""

from __future__ import annotations

import pytest

from tests.utils import (
    create_machine_direct,
    delete_machine,
    get_hostname,
    machine_exists,
    machine_is_running,
    user_exists,
    wait_for_machine_running,
)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_019_create_machine_default_settings(test_machine_created, test_username):
    """Test that a machine is provisioned with default settings."""
    machine_name = test_machine_created

    try:
        # Verify the machine exists (cloned from template)
        assert machine_exists(machine_name)

        # Verify the machine is running
        assert machine_is_running(machine_name)

        # Verify the hostname matches the machine name
        hostname = get_hostname(machine_name)
        assert hostname == machine_name

        # Verify the user exists
        assert user_exists(machine_name, test_username)
    finally:
        # Cleanup handled by fixture, but ensure it exists for cleanup
        pass


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_020_create_machine_custom_hostname(unique_machine_name, test_username):
    """Test creating a machine with a custom hostname."""
    machine_name = unique_machine_name
    custom_hostname = f"{machine_name}-custom"

    try:
        create_machine_direct(
            machine_name=machine_name, username=test_username, hostname=custom_hostname
        )
        assert machine_exists(machine_name)

        # Verify the hostname is the custom one
        hostname = get_hostname(machine_name)
        assert hostname == custom_hostname
    finally:
        # Cleanup
        if machine_exists(machine_name):
            delete_machine(machine_name, force=True)


@pytest.mark.requires_orbstack
def test_021_create_machine_already_exists(test_machine_created, test_username):
    """Test that creating an existing machine fails without the --recreate flag."""
    machine_name = test_machine_created

    try:
        # Try to create again without the --recreate flag - should raise SystemExit
        with pytest.raises(SystemExit) as exc_info:
            create_machine_direct(machine_name=machine_name, username=test_username)

        # Should exit with a non-zero code
        assert exc_info.value.code != 0
    finally:
        # Cleanup handled by fixture
        pass


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_022_create_machine_with_recreate(unique_machine_name, test_username):
    """Test creating a machine with the --recreate flag."""
    machine_name = unique_machine_name

    try:
        # Create machine first time
        create_machine_direct(machine_name=machine_name, username=test_username)
        # Verify it exists
        assert machine_exists(machine_name)

        # Create again with --recreate
        create_machine_direct(
            machine_name=machine_name, username=test_username, recreate=True
        )

        # Machine should still exist and be running
        assert machine_exists(machine_name)
        assert machine_is_running(machine_name)
    finally:
        # Cleanup
        if machine_exists(machine_name):
            delete_machine(machine_name, force=True)


@pytest.mark.requires_orbstack
def test_023_machine_deletion(unique_machine_name, test_username):
    """Test machine deletion utility."""
    machine_name = unique_machine_name

    try:
        # Create a machine
        create_machine_direct(machine_name=machine_name, username=test_username)
        assert machine_exists(machine_name)

        # Delete it
        success = delete_machine(machine_name, force=True)
        assert success

        # Verify it's gone
        assert not machine_exists(machine_name)
    finally:
        # Ensure cleanup even if test fails
        if machine_exists(machine_name):
            delete_machine(machine_name, force=True)


@pytest.mark.requires_orbstack
def test_024_wait_for_machine_running(test_machine_created):
    """Test the wait_for_machine_running utility function."""
    machine_name = test_machine_created

    try:
        # Machine already running (cloned from template)
        # Should be running
        is_running = wait_for_machine_running(machine_name, max_wait=10)
        assert is_running
    finally:
        # Cleanup handled by fixture
        pass
