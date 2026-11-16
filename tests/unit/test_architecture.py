"""Unit tests for architecture detection, mapping and flake attribute choice."""

from __future__ import annotations

import re

import pytest

from tests.provision_module import PROJECT_ROOT, load

provision = load()


@pytest.mark.parametrize(
    "uname_machine,expected",
    [
        ("arm64", "aarch64"),
        ("aarch64", "aarch64"),
        ("aarch64\n", "aarch64"),
        ("x86_64", "x86_64"),
        ("x86_64\n", "x86_64"),
        ("amd64", "x86_64"),
        # An unknown host falls back to aarch64, as the script documents.
        ("riscv64", "aarch64"),
    ],
)
def test_normalize_host_arch(uname_machine, expected):
    assert provision.normalize_host_arch(uname_machine) == expected


@pytest.mark.parametrize(
    "arch,expected",
    [
        ("aarch64", ("arm64", "aarch64")),
        ("arm64", ("arm64", "aarch64")),
        ("x86_64", ("amd64", "x86_64")),
        ("amd64", ("amd64", "x86_64")),
    ],
)
def test_map_architecture(arch, expected):
    assert provision.map_architecture(arch) == expected


@pytest.mark.parametrize("arch", ["invalid_arch", "", "i686", "ARM64"])
def test_map_architecture_rejects_unknown(arch):
    assert provision.map_architecture(arch) is None


def test_get_architecture_exits_on_unknown(capsys):
    with pytest.raises(SystemExit) as exc_info:
        provision.get_architecture("invalid_arch")
    assert exc_info.value.code == 1
    assert "Invalid architecture 'invalid_arch'" in capsys.readouterr().err


def test_every_arch_choice_is_mapped():
    """Each value `create --arch` accepts has an OrbStack and Nix mapping."""
    choices = ("aarch64", "arm64", "x86_64", "amd64")
    assert all(provision.parse_args(["create", "m", "--arch", c]).arch == c for c in choices)
    assert frozenset(provision.ARCH_MAPPING) == frozenset(choices)


@pytest.mark.parametrize(
    "arch,expected",
    [
        ("aarch64", "default"),
        ("arm64", "default"),
        ("x86_64", "x86_64"),
        ("amd64", "x86_64"),
    ],
)
def test_flake_attr_for_arch(arch, expected):
    assert provision.flake_attr_for_arch(arch) == expected


def test_flake_attrs_build_the_matching_system():
    """Each flake attribute the script picks builds a system of its architecture."""
    flake_text = (PROJECT_ROOT / "orbstack-nix-config" / "flake.nix").read_text()
    systems = dict(re.findall(r'^\s*(\w+) = mkSystem "([\w-]+)";', flake_text, re.MULTILINE))
    assert {attr: systems.get(attr) for attr in provision.FLAKE_ATTR_BY_NIX_ARCH.values()} == {
        attr: f"{nix_arch}-linux" for nix_arch, attr in provision.FLAKE_ATTR_BY_NIX_ARCH.items()
    }
