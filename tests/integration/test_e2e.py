"""End-to-end workflow tests."""

from __future__ import annotations

import pytest

from tests.integration.utils import (
    FLAKE_EXTRA_DIR,
    FLAKE_REPO_DIR,
    delete_machine,
    exec_on_machine,
    file_exists_on_machine,
    get_hostname,
    machine_exists,
    machine_is_running,
    nixos_rebuild_direct,
    service_is_active,
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
    result = nixos_rebuild_direct(
        machine_name=machine_name,
        username=test_username,
        extra_config=str(extra_config),
    )
    assert result.returncode == 0, f"Rebuild failed: {result.stderr}"

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
def test_008_multiple_sequential_rebuilds(test_machine_created, test_username, sample_configs_dir):
    """Test multiple sequential rebuilds to ensure idempotency."""
    machine_name = test_machine_created

    # Rebuild 1: No extra config
    print("\n=== Rebuild 1: No extra config ===")
    result = nixos_rebuild_direct(machine_name=machine_name, username=test_username)
    assert result.returncode == 0, f"Rebuild failed: {result.stderr}"
    assert machine_is_running(machine_name)

    # Rebuild 2: With a simple config
    print("\n=== Rebuild 2: With simple config ===")
    simple_config = sample_configs_dir / "simple.nix"
    result = nixos_rebuild_direct(
        machine_name=machine_name,
        username=test_username,
        extra_config=str(simple_config),
    )
    assert result.returncode == 0, f"Rebuild failed: {result.stderr}"
    assert machine_is_running(machine_name)

    # Verify tmux is installed
    result = exec_on_machine(machine_name, ["which", "tmux"], check=False)
    assert result.returncode == 0

    # Rebuild 3: Back to no extra config
    print("\n=== Rebuild 3: Back to no extra config ===")
    result = nixos_rebuild_direct(machine_name=machine_name, username=test_username)
    assert result.returncode == 0, f"Rebuild failed: {result.stderr}"
    assert machine_is_running(machine_name)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_009_openssh_enabled_by_configuration(test_machine_created):
    """configuration.nix enables OpenSSH, so sshd runs on a provisioned machine."""
    assert service_is_active(test_machine_created, "sshd")


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_010_complete_docker_workflow(
    test_machine_created, project_root, test_username, sample_configs_dir
):
    """Test the complete workflow with Docker configuration via nixos-rebuild."""
    machine_name = test_machine_created

    # Create a combined Docker config
    docker_config_path = project_root / FLAKE_REPO_DIR / FLAKE_EXTRA_DIR / "lib" / "docker.nix"
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
    result = nixos_rebuild_direct(
        machine_name=machine_name,
        username=test_username,
        extra_config=str(combined_config),
    )
    assert result.returncode == 0, f"Rebuild failed: {result.stderr}"
    # Verify Docker is installed
    result = exec_on_machine(machine_name, ["which", "docker"], check=False)
    assert result.returncode == 0, "docker should be installed"

    # Verify Docker Compose is installed
    result = exec_on_machine(machine_name, ["which", "docker-compose"], check=False)
    assert result.returncode == 0, "docker-compose should be installed"

    # Note: Docker daemon might not be running immediately after provision
    # In a real scenario, you might want to start it or wait for it
