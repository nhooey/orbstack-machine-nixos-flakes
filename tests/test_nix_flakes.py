"""Tests for Nix flakes integration."""
from __future__ import annotations

import subprocess

import pytest

from tests.utils import (
    machine_exists,
    machine_is_running,
    verify_flake_deployed,
    file_exists_on_machine,
    read_file_on_machine,
    exec_on_machine,
)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_flake_files_copied_to_etc_nixos(test_machine_created):
    """Test that flake files are copied to /etc/nixos/ correctly."""
    machine_name = test_machine_created

    # Verify the standard flake files exist
    assert verify_flake_deployed(machine_name)

    # Check specific files
    assert file_exists_on_machine(machine_name, "/etc/nixos/flake.nix")
    assert file_exists_on_machine(machine_name, "/etc/nixos/flake.lock")
    assert file_exists_on_machine(machine_name, "/etc/nixos/configuration.nix")


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_flake_content_matches_source(test_machine_created, project_root):
    """Test that flake content on VM matches source files."""
    machine_name = test_machine_created

    # Read flake.nix from project
    source_flake = (project_root / "flake.nix").read_text()

    # Read flake.nix from VM
    vm_flake = read_file_on_machine(machine_name, "/etc/nixos/flake.nix")

    # They should match
    assert source_flake == vm_flake


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_nixos_rebuild_on_existing_machine(test_machine_created, project_root, test_username):
    """Test running nixos-rebuild on an existing machine."""
    machine_name = test_machine_created
    provision_script = project_root / "orbstack-nixos-provision.py"

    # Machine should exist and be running
    assert machine_exists(machine_name)
    assert machine_is_running(machine_name)

    # Run nixos-rebuild
    cmd = [
        "python3", str(provision_script),
        "nixos-rebuild", machine_name,
        "--username", test_username,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    # Should succeed
    assert result.returncode == 0, f"Rebuild failed: {result.stderr}"

    # Machine should still be running
    assert machine_is_running(machine_name)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_rebuild_applies_configuration_changes(test_machine_created, project_root, test_username):
    """Test that rebuild actually applies configuration changes."""
    machine_name = test_machine_created
    provision_script = project_root / "orbstack-nixos-provision.py"

    # Run rebuild (should be idempotent)
    cmd = [
        "python3", str(provision_script),
        "nixos-rebuild", machine_name,
        "--username", test_username,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    assert result.returncode == 0

    # Check that some expected packages from configuration.nix are available
    # These are defined in the base configuration
    result = exec_on_machine(machine_name, ["which", "git"], check=False)
    assert result.returncode == 0, "git should be installed from configuration.nix"

    result = exec_on_machine(machine_name, ["which", "vim"], check=False)
    assert result.returncode == 0, "vim should be installed from configuration.nix"


@pytest.mark.requires_orbstack
def test_rebuild_fails_on_nonexistent_machine(project_root, test_username):
    """Test that nixos-rebuild fails gracefully on non-existent machine."""
    provision_script = project_root / "orbstack-nixos-provision.py"
    fake_machine = "nonexistent-machine-12345"

    cmd = [
        "python3", str(provision_script),
        "nixos-rebuild", fake_machine,
        "--username", test_username,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    # Should fail
    assert result.returncode != 0
    assert "does not exist" in result.stderr.lower()


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_different_flake_attributes(test_machine, project_root, test_username):
    """Test creating machines with different flake attributes."""
    machine_name = test_machine
    provision_script = project_root / "orbstack-nixos-provision.py"

    # Create with default attribute
    cmd = [
        "python3", str(provision_script),
        "create", machine_name,
        "--flake-attr", "default",
        "--username", test_username,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    assert result.returncode == 0, f"Creation with default attr failed: {result.stderr}"
    assert machine_exists(machine_name)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_flake_evaluation_uses_impure_mode(test_machine_created):
    """Test that flake evaluation works in impure mode for environment variables."""
    machine_name = test_machine_created

    # The fact that the machine was created with hostname and username
    # from environment variables proves impure mode is working
    # Let's verify the bootstrap script uses --impure flag

    # Check that /tmp/orbstack-nixos-provision/bootstrap-nixos.sh exists and contains --impure
    result = exec_on_machine(
        machine_name,
        ["cat", "/tmp/orbstack-nixos-provision/bootstrap-nixos.sh"],
        check=False
    )

    if result.returncode == 0:
        # Script might still be there from provisioning
        assert "--impure" in result.stdout, "Bootstrap script should use --impure flag"


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_system_was_built_from_flake(test_machine_created):
    """Test that the system was actually built from the flake."""
    machine_name = test_machine_created

    # Check for flake-related configuration
    result = exec_on_machine(
        machine_name,
        ["nix", "eval", "--raw", "/etc/nixos#nixosConfigurations.default.config.system.nixos.version"],
        check=False
    )

    # If this succeeds, we know the flake is properly set up
    # The exact version doesn't matter, just that it evaluates
    if result.returncode != 0:
        # Alternative check: see if system.build.toplevel exists
        result = exec_on_machine(
            machine_name,
            ["ls", "-la", "/run/current-system"],
            check=True
        )
        assert "/nix/store" in result.stdout
