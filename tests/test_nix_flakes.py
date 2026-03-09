"""Tests for Nix flakes integration."""

from __future__ import annotations

import pytest

from tests.utils import (
    BOOTSTRAP_SCRIPT_NAME,
    FLAKE_REPO_DIR,
    TMP_BASE_DIR,
    exec_on_machine,
    file_exists_on_machine,
    machine_exists,
    machine_is_running,
    nixos_rebuild_direct,
    read_file_on_machine,
    verify_flake_deployed,
)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_032_flake_files_copied_to_etc_nixos(test_machine_created):
    """Test that the flake files are copied to /etc/nixos/ correctly."""
    machine_name = test_machine_created

    # Verify the standard flake files exist
    assert verify_flake_deployed(machine_name)

    # Check specific files
    assert file_exists_on_machine(machine_name, "/etc/nixos/flake.nix")
    assert file_exists_on_machine(machine_name, "/etc/nixos/flake.lock")
    assert file_exists_on_machine(machine_name, "/etc/nixos/configuration.nix")


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_033_nixos_rebuild_on_existing_machine(test_machine_created, test_username):
    """Test running nixos-rebuild on an existing machine."""
    machine_name = test_machine_created

    # Machine should exist and be running
    assert machine_exists(machine_name)
    assert machine_is_running(machine_name)

    # Run nixos-rebuild
    result = nixos_rebuild_direct(machine_name=machine_name, username=test_username)

    # Should succeed
    assert result.returncode == 0, f"Rebuild failed: {result.stderr}"

    # Machine should still be running
    assert machine_is_running(machine_name)


@pytest.mark.requires_orbstack
def test_034_rebuild_fails_on_nonexistent_machine(test_username):
    """Test that nixos-rebuild fails gracefully on a non-existent machine."""
    fake_machine = "nonexistent-machine-12345"

    result = nixos_rebuild_direct(machine_name=fake_machine, username=test_username)

    # Should fail
    assert result.returncode != 0
    assert "does not exist" in result.stderr.lower()


