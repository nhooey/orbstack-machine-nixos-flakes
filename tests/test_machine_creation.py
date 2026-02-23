"""Tests for basic machine creation functionality."""
from __future__ import annotations

import subprocess

import pytest

from tests.utils import (
    machine_exists,
    machine_is_running,
    wait_for_machine_running,
    user_exists,
    get_hostname,
    delete_machine,
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
    cmd = [
        "python3", str(provision_script),
        "create", machine_name,
        "--username", test_username,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    # Check command succeeded
    assert result.returncode == 0, f"Creation failed: {result.stderr}"

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

    cmd = [
        "python3", str(provision_script),
        "create", machine_name,
        "--hostname", custom_hostname,
        "--username", test_username,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    assert result.returncode == 0, f"Creation failed: {result.stderr}"
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

    cmd = [
        "python3", str(provision_script),
        "create", machine_name,
        "--username", custom_user,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    assert result.returncode == 0, f"Creation failed: {result.stderr}"
    assert machine_exists(machine_name)

    # Verify custom user exists
    assert user_exists(machine_name, custom_user)


@pytest.mark.requires_orbstack
def test_create_machine_already_exists(test_machine_created, project_root, test_username):
    """Test that creating an existing machine fails without --recreate."""
    machine_name = test_machine_created
    provision_script = project_root / "orbstack-nixos-provision.py"

    # Try to create again without --recreate
    cmd = [
        "python3", str(provision_script),
        "create", machine_name,
        "--username", test_username,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    # Should fail
    assert result.returncode != 0
    assert "already exists" in result.stderr.lower()


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_create_machine_with_recreate(test_machine, project_root, test_username):
    """Test creating a machine with --recreate flag."""
    machine_name = test_machine
    provision_script = project_root / "orbstack-nixos-provision.py"

    # Create machine first time
    cmd = [
        "python3", str(provision_script),
        "create", machine_name,
        "--username", test_username,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    assert result.returncode == 0

    # Verify it exists
    assert machine_exists(machine_name)

    # Create again with --recreate
    cmd.append("--recreate")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    # Should succeed
    assert result.returncode == 0, f"Recreate failed: {result.stderr}"

    # Machine should still exist and be running
    assert machine_exists(machine_name)
    assert machine_is_running(machine_name)


@pytest.mark.requires_orbstack
def test_machine_deletion(unique_machine_name, project_root, test_username):
    """Test machine deletion utility."""
    machine_name = unique_machine_name
    provision_script = project_root / "orbstack-nixos-provision.py"

    # Create a machine
    cmd = [
        "python3", str(provision_script),
        "create", machine_name,
        "--username", test_username,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    assert result.returncode == 0
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
    cmd = [
        "python3", str(provision_script),
        "create", machine_name,
        "--username", test_username,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    # Should be running
    is_running = wait_for_machine_running(machine_name, max_wait=10)
    assert is_running
