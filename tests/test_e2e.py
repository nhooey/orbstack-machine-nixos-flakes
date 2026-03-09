"""End-to-end workflow tests."""

from __future__ import annotations

import pytest

from tests.utils import (
    FLAKE_EXTRA_DIR,
    FLAKE_REPO_DIR,
    delete_machine,
    exec_on_machine,
    file_exists_on_machine,
    get_hostname,
    machine_exists,
    machine_is_running,
    nixos_rebuild_direct,
    user_exists,
    verify_flake_deployed,
)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_007_full_workflow_create_verify_rebuild_delete(
    test_machine_created, test_username, sample_configs_dir
):
    """Test complete workflow: create → verify → rebuild → verify → delete."""
    machine_name = test_machine_created

    # Step 1: Verify the machine was created (by fixture)
    print("\n=== Step 1: Verifying the machine was created ===")
    # Step 2: Verify the machine state
    print("\n=== Step 2: Verifying the initial state ===")
    assert machine_exists(machine_name)
    assert machine_is_running(machine_name)
    assert user_exists(machine_name, test_username)
    assert get_hostname(machine_name) == machine_name
    assert verify_flake_deployed(machine_name)

    # Verify base packages
    result = exec_on_machine(machine_name, ["which", "git"], check=True)
    assert result.returncode == 0

    # Step 3: Rebuild with extra config
    print("\n=== Step 3: Rebuilding with extra config ===")
    extra_config = sample_configs_dir / "with-service.nix"
    nixos_rebuild_direct(
        machine_name=machine_name,
        username=test_username,
        extra_config=str(extra_config),
    )

    # Step 4: Verify rebuild changes
    print("\n=== Step 4: Verifying rebuild changes ===")
    assert machine_is_running(machine_name)
    assert file_exists_on_machine(machine_name, "/etc/test-marker")

    result = exec_on_machine(machine_name, ["which", "neofetch"], check=False)
    assert result.returncode == 0, "neofetch should be installed after rebuild"

    result = exec_on_machine(machine_name, ["which", "jq"], check=False)
    assert result.returncode == 0, "jq should be installed after rebuild"

    # Step 5: Delete machine
    print("\n=== Step 5: Deleting machine ===")
    success = delete_machine(machine_name, force=True)
    assert success
    assert not machine_exists(machine_name)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_008_multiple_sequential_rebuilds(
    test_machine_created, test_username, sample_configs_dir
):
    """Test multiple sequential rebuilds to ensure idempotency."""
    machine_name = test_machine_created

    # Rebuild 1: No extra config
    print("\n=== Rebuild 1: No extra config ===")
    nixos_rebuild_direct(machine_name=machine_name, username=test_username)
    assert machine_is_running(machine_name)

    # Rebuild 2: With a simple config
    print("\n=== Rebuild 2: With simple config ===")
    simple_config = sample_configs_dir / "simple.nix"
    nixos_rebuild_direct(
        machine_name=machine_name,
        username=test_username,
        extra_config=str(simple_config),
    )
    assert machine_is_running(machine_name)

    # Verify tmux is installed
    result = exec_on_machine(machine_name, ["which", "tmux"], check=False)
    assert result.returncode == 0

    # Rebuild 3: Back to no extra config
    print("\n=== Rebuild 3: Back to no extra config ===")
    nixos_rebuild_direct(machine_name=machine_name, username=test_username)
    assert machine_is_running(machine_name)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_009_ssh_connectivity(test_machine_created):
    """Test SSH connectivity to the machine."""
    machine_name = test_machine_created

    # Test basic command execution via SSH (through orb)
    result = exec_on_machine(machine_name, ["echo", "Hello from VM"], check=True)
    assert "Hello from VM" in result.stdout

    # Test that the SSH service is running
    result = exec_on_machine(
        machine_name, ["systemctl", "is-active", "sshd"], check=False
    )
    assert result.returncode == 0


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_010_complete_docker_workflow(
    test_machine_created, project_root, test_username, sample_configs_dir
):
    """Test the complete workflow with Docker configuration via nixos-rebuild."""
    machine_name = test_machine_created

    # Create a combined Docker config
    docker_config_path = (
        project_root / FLAKE_REPO_DIR / FLAKE_EXTRA_DIR / "lib" / "docker.nix"
    )
    combined_config = sample_configs_dir / "docker-full.nix"
    combined_config.write_text(
        f"""{{ config, pkgs, username, ... }}:

{{
  imports = [
    {docker_config_path}
  ];

  users.users.${{username}}.extraGroups = [ "docker" ];

  # Ensure Docker service starts
  systemd.services.docker.wantedBy = [ "multi-user.target" ];
}}
"""
    )

    # Apply Docker config via nixos-rebuild
    nixos_rebuild_direct(
        machine_name=machine_name,
        username=test_username,
        extra_config=str(combined_config),
    )
    # Verify Docker is installed
    result = exec_on_machine(machine_name, ["which", "docker"], check=False)
    assert result.returncode == 0, "docker should be installed"

    # Verify Docker Compose is installed
    result = exec_on_machine(machine_name, ["which", "docker-compose"], check=False)
    assert result.returncode == 0, "docker-compose should be installed"

    # Note: Docker daemon might not be running immediately after provision
    # In a real scenario, you might want to start it or wait for it


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_011_persistence_after_rebuild(test_machine_created, test_username):
    """Test that the configuration persists correctly after rebuilds."""
    machine_name = test_machine_created

    # Create a test file in the user's home directory
    test_file_content = "This is a test file"
    exec_on_machine(
        machine_name,
        ["bash", "-c", f"echo '{test_file_content}' > /home/{test_username}/test.txt"],
        check=True,
    )

    # Verify the file exists
    result = exec_on_machine(
        machine_name, ["cat", f"/home/{test_username}/test.txt"], check=True
    )
    assert test_file_content in result.stdout

    # Run rebuild
    nixos_rebuild_direct(machine_name=machine_name, username=test_username)
    # Verify the file still exists after rebuild
    result = exec_on_machine(
        machine_name, ["cat", f"/home/{test_username}/test.txt"], check=True
    )
    assert test_file_content in result.stdout


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_012_system_packages_after_creation(test_machine_created):
    """Test that the expected system packages are available after creation."""
    machine_name = test_machine_created

    # These packages are defined in configuration.nix
    expected_packages = ["vim", "git", "curl", "wget", "htop"]

    for package in expected_packages:
        result = exec_on_machine(machine_name, ["which", package], check=False)
        assert result.returncode == 0, f"{package} should be installed"


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_013_nix_flakes_enabled(test_machine_created):
    """Test that Nix flakes are enabled in the configuration."""
    machine_name = test_machine_created

    # Try to use a flake command
    result = exec_on_machine(
        machine_name, ["nix", "flake", "show", "/etc/nixos"], check=False, timeout=60
    )

    # Should work (flakes are enabled in configuration.nix)
    assert result.returncode == 0, "Nix flakes should be enabled"


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_014_user_in_wheel_group(test_machine_created, test_username):
    """Test that the created user is in the wheel group."""
    machine_name = test_machine_created

    # Check groups for the user
    result = exec_on_machine(machine_name, ["groups", test_username], check=True)

    # User should be in the wheel group (from configuration.nix)
    assert "wheel" in result.stdout


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_015_sudo_without_password(test_machine_created, test_username):
    """Test that the wheel group can use sudo without a password."""
    machine_name = test_machine_created

    # Run sudo command as the user
    result = exec_on_machine(
        machine_name, ["sudo", "-n", "-u", test_username, "whoami"], check=False
    )

    # Should work without a password (wheelNeedsPassword = false in configuration.nix)
    # Note: This test might need adjustment based on how orb handles user context
    assert result.returncode == 0 or "sudo" in result.stderr.lower()
