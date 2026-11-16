"""Integration tests for the architecture a machine is created with and built for."""

from __future__ import annotations

import pytest

from tests.integration.utils import (
    create_machine_direct,
    delete_machine,
    get_nix_system_architecture,
    import_provision_script,
    machine_exists,
    read_file_on_machine,
    run_command,
)

provision = import_provision_script()


def _host_nix_system() -> str:
    """Return the Nix system string for the host's architecture."""
    return f"{provision.normalize_host_arch(run_command(['uname', '-m']).stdout)}-linux"


@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_001_default_architecture_detection(test_machine_created):
    """Without --arch, the machine runs, and is built for, the host's architecture."""
    machine_name = test_machine_created
    expected = _host_nix_system()

    assert get_nix_system_architecture(machine_name) == expected
    assert read_file_on_machine(machine_name, "/run/current-system/system").strip() == expected


def _test_explicit_architecture_helper(
    unique_machine_name: str,
    test_username: str,
    arch_flag: str,
    expected_nix_arch: str,
):
    """Create a machine with an explicit architecture and check the system it runs."""
    if _host_nix_system() == "x86_64-linux" and expected_nix_arch == "aarch64-linux":
        pytest.skip("OrbStack can't run aarch64 machines on an x86_64 host")

    machine_name = unique_machine_name
    try:
        create_machine_direct(machine_name=machine_name, username=test_username, arch=arch_flag)
        assert machine_exists(machine_name)
        assert get_nix_system_architecture(machine_name) == expected_nix_arch
        # The NixOS system the flake built is for the machine's architecture too.
        assert read_file_on_machine(machine_name, "/run/current-system/system").strip() == (
            expected_nix_arch
        )
    finally:
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
def test_002_explicit_arm_architecture(
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
def test_003_explicit_x86_architecture(
    unique_machine_name, test_username, arch_flag, expected_nix_arch
):
    """Test creating machine with explicit x86_64 architecture flags."""
    _test_explicit_architecture_helper(
        unique_machine_name, test_username, arch_flag, expected_nix_arch
    )
