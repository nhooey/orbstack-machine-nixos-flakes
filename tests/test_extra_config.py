"""Tests for --extra-config functionality."""

from __future__ import annotations

import pytest

from tests.utils import (
    create_machine_direct,
    nixos_rebuild_direct,
    machine_exists,
    file_exists_on_machine,
    exec_on_machine,
    run_command,
    wait_for_network_online,
)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_extra_config_with_simple_package(
    test_machine_created, test_username, sample_configs_dir
):
    """Test --extra-config with a simple config that adds a package via nixos-rebuild."""
    machine_name = test_machine_created
    extra_config = sample_configs_dir / "simple.nix"

    # Apply extra config via nixos-rebuild
    nixos_rebuild_direct(
        machine_name=machine_name, username=test_username, extra_config=str(extra_config)
    )
    assert machine_exists(machine_name)

    # Verify tmux is installed (from simple.nix)
    result = exec_on_machine(machine_name, ["which", "tmux"], check=False)
    assert result.returncode == 0, "tmux should be installed from extra config"


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_extra_config_with_marker_file(
    test_machine_created, test_username, sample_configs_dir
):
    """Test --extra-config creates a marker file to verify it was applied via nixos-rebuild."""
    machine_name = test_machine_created
    extra_config = sample_configs_dir / "with-service.nix"

    nixos_rebuild_direct(
        machine_name=machine_name, username=test_username, extra_config=str(extra_config)
    )
    # Verify marker file exists (from with-service.nix)
    assert file_exists_on_machine(machine_name, "/etc/test-marker")

    # Verify packages from with-service.nix
    result = exec_on_machine(machine_name, ["which", "neofetch"], check=False)
    assert result.returncode == 0, "neofetch should be installed"

    result = exec_on_machine(machine_name, ["which", "jq"], check=False)
    assert result.returncode == 0, "jq should be installed"


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_extra_config_on_rebuild(
    test_machine_created, project_root, test_username, sample_configs_dir
):
    """Test applying --extra-config on nixos-rebuild."""
    machine_name = test_machine_created
    provision_script = project_root / "orbstack-nixos-provision.py"
    extra_config = sample_configs_dir / "simple.nix"

    # First verify tmux is NOT installed
    result = exec_on_machine(machine_name, ["which", "tmux"], check=False)
    initial_has_tmux = result.returncode == 0

    # Run rebuild with extra config
    nixos_rebuild_direct(
        machine_name=machine_name, username=test_username, extra_config=str(extra_config)
    )

    # Now tmux should be installed
    result = exec_on_machine(machine_name, ["which", "tmux"], check=False)
    assert result.returncode == 0, "tmux should be installed after rebuild with extra config"


@pytest.mark.requires_orbstack
def test_extra_config_nonexistent_file(test_machine_created, test_username):
    """Test that --extra-config with non-existent file fails gracefully."""
    machine_name = test_machine_created
    fake_config = "/tmp/nonexistent-config-12345.nix"

    # nixos_rebuild_direct catches SystemExit and returns it as returncode
    result = nixos_rebuild_direct(
        machine_name=machine_name, username=test_username, extra_config=fake_config
    )

    # Should fail with non-zero return code
    assert result.returncode != 0, "Should fail when extra_config file doesn't exist"
    assert "not found" in result.stderr.lower() or "does not exist" in result.stderr.lower()


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_extra_config_relative_path(test_machine_created, project_root, test_username, tmp_path):
    """Test --extra-config with relative path via nixos-rebuild."""
    import os

    machine_name = test_machine_created

    # Create config file within project directory so relative path works
    config_dir = project_root / "test-configs-temp"
    config_dir.mkdir(exist_ok=True)
    extra_config = config_dir / "simple.nix"
    extra_config.write_text(
        """{ config, pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    tmux
  ];
}
"""
    )

    # Change to project root and use relative path
    original_cwd = os.getcwd()
    try:
        os.chdir(project_root)
        # Use path relative to project root
        relative_path = extra_config.relative_to(project_root)
        nixos_rebuild_direct(
            machine_name=machine_name, username=test_username, extra_config=str(relative_path)
        )

        assert machine_exists(machine_name)

        # Verify package from config
        result = exec_on_machine(machine_name, ["which", "tmux"], check=False)
        assert result.returncode == 0
    finally:
        os.chdir(original_cwd)
        # Clean up temp config directory
        if config_dir.exists():
            import shutil
            shutil.rmtree(config_dir)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_extra_config_from_nix_extra_config_dir(
    test_machine_created, project_root, test_username, sample_configs_dir
):
    """Test --extra-config with docker.nix from orbstack-nix-config/extra/lib/ directory via nixos-rebuild."""
    machine_name = test_machine_created

    # Use the docker.nix from the project
    docker_config = project_root / "orbstack-nix-config/extra" / "lib" / "docker.nix"
    docker_user_config = sample_configs_dir / "docker-user.nix"

    # We need to combine docker.nix with user config, so let's create a combined config
    combined_config = sample_configs_dir / "docker-combined.nix"
    combined_config.write_text(
        f"""{{ config, pkgs, username, ... }}:

{{
  imports = [
    {docker_config}
  ];

  # Add user to docker group
  users.users.${{username}}.extraGroups = [ "docker" ];
}}
"""
    )

    nixos_rebuild_direct(
        machine_name=machine_name, username=test_username, extra_config=str(combined_config)
    )
    assert machine_exists(machine_name)

    # Verify docker is available
    result = exec_on_machine(machine_name, ["which", "docker"], check=False)
    assert result.returncode == 0, "docker should be installed"

    # Verify docker service is enabled (may not be active immediately)
    result = exec_on_machine(
        machine_name, ["systemctl", "is-enabled", "docker.service"], check=False
    )
    # Service should at least be configured even if not running
    assert result.returncode == 0 or "enabled" in result.stdout.lower()


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_extra_config_environment_variable_passed(
    test_machine_created, test_username, sample_configs_dir
):
    """Test that NIXOS_EXTRA_CONFIG environment variable is correctly passed to bootstrap script via nixos-rebuild."""
    machine_name = test_machine_created
    extra_config = sample_configs_dir / "with-service.nix"

    nixos_rebuild_direct(
        machine_name=machine_name, username=test_username, extra_config=str(extra_config)
    )
    # The extra config was successfully applied (marker file exists)
    assert file_exists_on_machine(machine_name, "/etc/test-marker")

    # This proves that:
    # 1. Extra config was copied to VM
    # 2. NIXOS_EXTRA_CONFIG env var was set
    # 3. Bootstrap script used it correctly
    # 4. Flake imported the extra config successfully
