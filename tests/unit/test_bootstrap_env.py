"""Unit tests for the settings passed to bootstrap-nixos.sh."""

from __future__ import annotations

import subprocess

from tests.provision_module import load

provision = load()


def test_bootstrap_env_exports_without_extra_config():
    assert provision.bootstrap_env_exports("/etc/nixos#default", "host", "user", None) == (
        "export FLAKE_REF='/etc/nixos#default'; "
        "export NIXOS_HOSTNAME=host; "
        "export NIXOS_USERNAME=user"
    )


def test_bootstrap_env_exports_with_extra_config():
    exports = provision.bootstrap_env_exports(
        "/etc/nixos#x86_64", "host", "user", "/tmp/extra-config.nix"
    )
    assert exports.endswith("; export NIXOS_EXTRA_CONFIG=/tmp/extra-config.nix")


def test_bootstrap_env_exports_survive_the_shell():
    """Values with spaces and quotes reach the bootstrap script unchanged."""
    values = {
        "FLAKE_REF": "/etc/nixos#default",
        "NIXOS_HOSTNAME": "it's a host",
        "NIXOS_USERNAME": "user name",
        "NIXOS_EXTRA_CONFIG": "/tmp/my config.nix",
    }
    exports = provision.bootstrap_env_exports(
        values["FLAKE_REF"],
        values["NIXOS_HOSTNAME"],
        values["NIXOS_USERNAME"],
        values["NIXOS_EXTRA_CONFIG"],
    )
    printed = subprocess.run(
        ["bash", "-c", f"{exports}; " + "; ".join(f'printf "%s\\0" "${n}"' for n in values)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert tuple(printed.split("\0")[:-1]) == tuple(values.values())
