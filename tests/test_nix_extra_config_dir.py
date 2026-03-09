"""Tests for orbstack-nix-config/extra directory copying functionality."""

from __future__ import annotations

import shutil

import pytest

from tests.utils import (
    BOOTSTRAP_SCRIPT_NAME,
    FLAKE_EXTRA_DIR,
    FLAKE_REPO_DIR,
    PROVISION_SCRIPT_NAME,
    TMP_BASE_DIR,
    create_machine_direct,
    exec_on_machine,
    file_exists_on_machine,
    machine_exists,
    nixos_rebuild_direct,
)


def _copy_project_files(project_root, test_project):
    """Copy essential project files to the test project directory."""
    for file in [
        PROVISION_SCRIPT_NAME,
        BOOTSTRAP_SCRIPT_NAME,
        "flake.nix",
        "flake.lock",
    ]:
        shutil.copy(project_root / file, test_project / file)

    # Copy all required files from the flake repo subdirectory
    (test_project / FLAKE_REPO_DIR).mkdir(parents=True, exist_ok=True)
    for file in ["flake.nix", "flake.lock", "configuration.nix"]:
        src_file = project_root / FLAKE_REPO_DIR / file
        if src_file.exists():
            shutil.copy(src_file, test_project / FLAKE_REPO_DIR / file)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_025_nix_extra_config_dir_copied(test_machine_created):
    """Test that the orbstack-nix-config/extra directory is copied to the VM."""
    machine_name = test_machine_created

    # Check that the orbstack-nix-config/extra directory was copied
    base_path = f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR}"

    # The directory should exist
    result = exec_on_machine(machine_name, ["test", "-d", base_path], check=False)
    assert result.returncode == 0, (
        "The orbstack-nix-config/extra directory should exist on the VM"
    )


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_026_nix_extra_config_files_present(test_machine_created):
    """Test that the specific files from orbstack-nix-config/extra are present."""
    machine_name = test_machine_created

    # Check for the known files from the orbstack-nix-config/extra directory
    docker_nix = f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR}/lib/docker.nix"

    assert file_exists_on_machine(machine_name, docker_nix), (
        "docker.nix should be copied from orbstack-nix-config/extra/lib/"
    )


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_027_nix_extra_config_nested_structure(test_machine_created):
    """Test that the nested directory structure is preserved."""
    machine_name = test_machine_created

    # Check that the lib/ subdirectory exists
    lib_dir = f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR}/lib"

    result = exec_on_machine(machine_name, ["test", "-d", lib_dir], check=False)
    assert result.returncode == 0, "lib/ subdirectory should exist"

    # List files in the lib directory
    result = exec_on_machine(machine_name, ["ls", "-la", lib_dir], check=True)
    assert "docker.nix" in result.stdout, "docker.nix should be in lib/ subdirectory"


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_028_nix_extra_config_file_content(test_machine_created, project_root):
    """Test that the file content is correctly copied."""
    machine_name = test_machine_created

    # Read docker.nix from source
    source_file = project_root / FLAKE_REPO_DIR / FLAKE_EXTRA_DIR / "lib" / "docker.nix"
    source_content = source_file.read_text()

    # Read docker.nix from VM
    vm_path = f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR}/lib/docker.nix"
    result = exec_on_machine(machine_name, ["cat", vm_path], check=True)
    vm_content = result.stdout

    # Content should match
    assert source_content == vm_content, "File content should match source"


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_029_nix_extra_config_dir_on_rebuild(test_machine_created, test_username):
    """Test that the orbstack-nix-config/extra directory is copied again on rebuild."""
    machine_name = test_machine_created

    # First, delete the orbstack-nix-config/extra directory on the VM
    exec_on_machine(
        machine_name,
        ["rm", "-rf", f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR}"],
        check=True,
    )

    # Verify it's gone
    result = exec_on_machine(
        machine_name,
        ["test", "-d", f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR}"],
        check=False,
    )
    assert result.returncode != 0, "Directory should be deleted"

    # Run rebuild
    nixos_rebuild_direct(machine_name=machine_name, username=test_username)

    # Now the directory should exist again
    result = exec_on_machine(
        machine_name,
        ["test", "-d", f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR}"],
        check=False,
    )
    assert result.returncode == 0, "Directory should be recreated on rebuild"


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_030_nix_extra_config_with_multiple_files(
    unique_machine_name, project_root, test_username, tmp_path
):
    """Test the orbstack-nix-config/extra directory with multiple files in a nested structure."""
    from tests.utils import delete_machine

    # Create a test project directory with custom orbstack-nix-config/extra
    test_project = tmp_path / "test-project"
    test_project.mkdir()

    # Copy essential files
    _copy_project_files(project_root, test_project)

    # Create a custom orbstack-nix-config/extra with a nested structure
    nix_extra_config = test_project / FLAKE_REPO_DIR / FLAKE_EXTRA_DIR
    nix_extra_config.mkdir()

    (nix_extra_config / "README.md").write_text("# Test orbstack-nix-config/extra")

    lib_dir = nix_extra_config / "lib"
    lib_dir.mkdir()
    (lib_dir / "test1.nix").write_text("{ config, pkgs, ... }: {}")
    (lib_dir / "test2.nix").write_text("{ config, pkgs, ... }: {}")

    modules_dir = nix_extra_config / "modules"
    modules_dir.mkdir()
    (modules_dir / "test3.nix").write_text("{ config, pkgs, ... }: {}")

    # Create a machine from this test project
    machine_name = unique_machine_name

    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(test_project)
        create_machine_direct(machine_name=machine_name, username=test_username)

        # Verify all the files were copied
        base = f"{TMP_BASE_DIR}/{FLAKE_REPO_DIR}/{FLAKE_EXTRA_DIR}"

        assert file_exists_on_machine(machine_name, f"{base}/README.md")
        assert file_exists_on_machine(machine_name, f"{base}/lib/test1.nix")
        assert file_exists_on_machine(machine_name, f"{base}/lib/test2.nix")
        assert file_exists_on_machine(machine_name, f"{base}/modules/test3.nix")
    finally:
        os.chdir(original_cwd)
        # Cleanup
        if machine_exists(machine_name):
            delete_machine(machine_name, force=True)


@pytest.mark.requires_orbstack
def test_031_without_nix_extra_config_dir(
    unique_machine_name, project_root, test_username, tmp_path
):
    """Test that provisioning works even without the orbstack-nix-config/extra directory."""
    from tests.utils import delete_machine

    # Create a minimal test project without orbstack-nix-config/extra
    test_project = tmp_path / "minimal-project"
    test_project.mkdir()

    # Copy essential files
    _copy_project_files(project_root, test_project)

    # Do NOT create orbstack-nix-config/extra directory

    machine_name = unique_machine_name

    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(test_project)
        create_machine_direct(machine_name=machine_name, username=test_username)

        # Should succeed even without orbstack-nix-config/extra
        assert machine_exists(machine_name)
    finally:
        os.chdir(original_cwd)
        # Cleanup
        if machine_exists(machine_name):
            delete_machine(machine_name, force=True)
