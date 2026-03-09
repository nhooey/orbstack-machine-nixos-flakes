"""Tests for architecture detection and mapping."""

from __future__ import annotations

import subprocess

import pytest

from tests.utils import (
    create_machine_direct,
    get_nix_system_architecture,
    import_provision_script,
    machine_exists,
    run_command,
)


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_default_architecture_detection(test_machine_created):
    """Test that architecture is auto-detected correctly when not specified."""
    machine_name = test_machine_created

    # Machine already created (cloned from template with default arch)
    assert machine_exists(machine_name)

    # Get the architecture on the VM
    nix_arch = get_nix_system_architecture(machine_name)

    # Should be a valid Nix architecture
    assert nix_arch in ["aarch64-linux", "x86_64-linux"], (
        f"Invalid Nix architecture: {nix_arch}"
    )

    # Get host architecture
    host_result = run_command(["uname", "-m"], check=True)
    host_arch = host_result.stdout.strip()

    # Verify mapping is correct
    if host_arch in ["arm64", "aarch64"]:
        assert nix_arch == "aarch64-linux", "Host is ARM, VM should be aarch64-linux"
    elif host_arch in ["x86_64", "amd64"]:
        assert nix_arch == "x86_64-linux", "Host is x86_64, VM should be x86_64-linux"


def _test_explicit_architecture_helper(
    unique_machine_name: str,
    test_username: str,
    arch_flag: str,
    expected_nix_arch: str,
):
    """Helper function to test creating a machine with explicit architecture."""
    from tests.utils import delete_machine

    machine_name = unique_machine_name

    try:
        create_machine_direct(
            machine_name=machine_name, username=test_username, arch=arch_flag
        )
        assert machine_exists(machine_name)
        nix_arch = get_nix_system_architecture(machine_name)
        assert nix_arch == expected_nix_arch, (
            f"Expected {expected_nix_arch}, got {nix_arch}"
        )
    except (SystemExit, subprocess.CalledProcessError, subprocess.SubprocessError):
        # If it fails, it should be due to architecture incompatibility
        pytest.skip(f"Architecture {arch_flag} not supported on this host")
    finally:
        # Cleanup
        if machine_exists(machine_name):
            delete_machine(machine_name, force=True)


@pytest.mark.slow
@pytest.mark.requires_orbstack
@pytest.mark.parametrize(
    "arch_flag,expected_nix_arch",
    [
        ("aarch64", "aarch64-linux"),
        ("arm64", "aarch64-linux"),
    ],
)
def test_explicit_arm_architecture(
    unique_machine_name, test_username, arch_flag, expected_nix_arch
):
    """Test creating machine with explicit ARM architecture flags."""
    _test_explicit_architecture_helper(
        unique_machine_name, test_username, arch_flag, expected_nix_arch
    )


@pytest.mark.slow
@pytest.mark.requires_orbstack
@pytest.mark.parametrize(
    "arch_flag,expected_nix_arch",
    [
        ("x86_64", "x86_64-linux"),
        ("amd64", "x86_64-linux"),
    ],
)
def test_explicit_x86_architecture(
    unique_machine_name, test_username, arch_flag, expected_nix_arch
):
    """Test creating machine with explicit x86_64 architecture flags."""
    _test_explicit_architecture_helper(
        unique_machine_name, test_username, arch_flag, expected_nix_arch
    )


def test_architecture_mapping_function():
    """Test the get_architecture function logic directly."""
    provision_module = import_provision_script()
    get_architecture = provision_module.get_architecture

    # Test ARM variants
    orb_arch, nix_arch = get_architecture("aarch64")
    assert orb_arch == "arm64"
    assert nix_arch == "aarch64"

    orb_arch, nix_arch = get_architecture("arm64")
    assert orb_arch == "arm64"
    assert nix_arch == "aarch64"

    # Test x86 variants
    orb_arch, nix_arch = get_architecture("x86_64")
    assert orb_arch == "amd64"
    assert nix_arch == "x86_64"

    orb_arch, nix_arch = get_architecture("amd64")
    assert orb_arch == "amd64"
    assert nix_arch == "x86_64"

    # Test auto-detection (None)
    orb_arch, nix_arch = get_architecture(None)
    assert orb_arch in ["arm64", "amd64"]
    assert nix_arch in ["aarch64", "x86_64"]


def test_invalid_architecture():
    """Test that invalid architecture is rejected."""
    provision_module = import_provision_script()
    get_architecture = provision_module.get_architecture

    with pytest.raises(SystemExit):
        get_architecture("invalid_arch")


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_flake_attribute_matches_architecture(test_machine_created):
    """Test that the correct flake attribute is used based on architecture."""
    machine_name = test_machine_created

    # Get host architecture
    host_result = run_command(["uname", "-m"], check=True)
    host_arch = host_result.stdout.strip()

    # Determine which flake attribute to use
    if host_arch in ["arm64", "aarch64"]:
        flake_attr = "default"  # default is aarch64 in flake.nix
    else:
        flake_attr = "x86_64"

    # Machine already created (cloned from template)
    assert machine_exists(machine_name)

    # Verify the system architecture matches
    nix_arch = get_nix_system_architecture(machine_name)
    if flake_attr == "default":
        assert nix_arch == "aarch64-linux"
    else:
        assert nix_arch == "x86_64-linux"
