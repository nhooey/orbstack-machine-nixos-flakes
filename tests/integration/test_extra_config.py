"""Tests for --extra-config functionality."""

from __future__ import annotations

import pytest

from tests.integration.utils import (
    FLAKE_EXTRA_DIR,
    FLAKE_REPO_DIR,
    exec_on_machine,
    file_exists_on_machine,
    machine_exists,
    nixos_rebuild_direct,
)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_012_extra_config_with_simple_package(
    test_machine_created, test_username, sample_configs_dir
):
    """Test --extra-config with a simple config that adds a package via nixos-rebuild."""
    machine_name = test_machine_created
    extra_config = sample_configs_dir / "simple.nix"

    # Apply extra config via nixos-rebuild
    result = nixos_rebuild_direct(
        machine_name=machine_name,
        username=test_username,
        extra_config=str(extra_config),
    )
    assert result.returncode == 0, f"Rebuild failed: {result.stderr}"
    assert machine_exists(machine_name)

    # Verify tmux is installed (from simple.nix)
    result = exec_on_machine(machine_name, ["which", "tmux"], check=False)
    assert result.returncode == 0, "tmux should be installed from extra config"


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_013_extra_config_with_marker_file(test_machine_created, test_username, sample_configs_dir):
    """Test --extra-config creates a marker file to verify it was applied via nixos-rebuild."""
    machine_name = test_machine_created
    extra_config = sample_configs_dir / "with-service.nix"

    result = nixos_rebuild_direct(
        machine_name=machine_name,
        username=test_username,
        extra_config=str(extra_config),
    )
    assert result.returncode == 0, f"Rebuild failed: {result.stderr}"
    # Verify marker file exists (from with-service.nix)
    assert file_exists_on_machine(machine_name, "/etc/test-marker")

    # Verify packages from with-service.nix
    result = exec_on_machine(machine_name, ["which", "neofetch"], check=False)
    assert result.returncode == 0, "neofetch should be installed"

    result = exec_on_machine(machine_name, ["which", "jq"], check=False)
    assert result.returncode == 0, "jq should be installed"


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_015_extra_config_nonexistent_file(test_machine_created, test_username):
    """Test that --extra-config with a non-existent file fails gracefully."""
    machine_name = test_machine_created
    fake_config = "/tmp/nonexistent-config-12345.nix"

    # nixos_rebuild_direct catches SystemExit and returns it as returncode
    result = nixos_rebuild_direct(
        machine_name=machine_name, username=test_username, extra_config=fake_config
    )

    # Should fail with non-zero return code
    assert result.returncode != 0, "Should fail when extra_config file doesn't exist"
    assert f"The user config file was not found: {fake_config}" in result.stderr


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_016_extra_config_relative_path(test_machine_created, project_root, test_username):
    """Test --extra-config with a relative path via nixos-rebuild."""
    import os

    machine_name = test_machine_created

    # Create a config file within the project directory so a relative path works
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

    # Change to the project root and use a relative path
    original_cwd = os.getcwd()
    try:
        os.chdir(project_root)
        # Use a path relative to the project root
        relative_path = extra_config.relative_to(project_root)
        result = nixos_rebuild_direct(
            machine_name=machine_name,
            username=test_username,
            extra_config=str(relative_path),
        )
        assert result.returncode == 0, f"Rebuild failed: {result.stderr}"

        assert machine_exists(machine_name)

        # Verify package from config using a fresh login shell
        result = exec_on_machine(machine_name, ["which", "tmux"], check=False, login_shell=True)
        assert result.returncode == 0
    finally:
        os.chdir(original_cwd)
        # Clean up temp config directory
        if config_dir.exists():
            import shutil

            shutil.rmtree(config_dir)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_017_extra_config_from_nix_extra_config_dir(
    test_machine_created, project_root, test_username, sample_configs_dir
):
    """Test --extra-config with docker.nix from orbstack-nix-config/extra/lib/ directory via nixos-rebuild."""
    machine_name = test_machine_created

    # Use the docker.nix from the project
    docker_config = project_root / FLAKE_REPO_DIR / FLAKE_EXTRA_DIR / "lib" / "docker.nix"

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

    result = nixos_rebuild_direct(
        machine_name=machine_name,
        username=test_username,
        extra_config=str(combined_config),
    )
    assert result.returncode == 0, f"Rebuild failed: {result.stderr}"
    assert machine_exists(machine_name)

    # Verify docker is available
    result = exec_on_machine(machine_name, ["which", "docker"], check=False)
    assert result.returncode == 0, "docker should be installed"

    # Verify docker service is enabled (may not be active immediately)
    result = exec_on_machine(
        machine_name, ["systemctl", "is-enabled", "docker.service"], check=False
    )
    # docker.nix enables Docker, which starts on boot by default.
    assert result.stdout.strip() == "enabled"
