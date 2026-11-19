"""Unit tests for command-line parsing and its defaults."""

from __future__ import annotations

import pytest

from tests.provision_module import load

provision = load()


def test_create_defaults():
    args = provision.parse_args(["create", "machine"])
    assert (args.command, args.machine_name) == ("create", "machine")
    assert args.arch is None
    # No default attribute, so the script picks the one for the architecture.
    assert args.flake_attr is None
    assert args.hostname is None
    assert args.username is None
    assert args.extra_config is None
    assert args.recreate is False
    assert args.timeout == provision.DEFAULT_TIMEOUT
    assert args.verbose is False


def test_nixos_rebuild_defaults():
    args = provision.parse_args(["nixos-rebuild", "machine"])
    assert (args.command, args.machine_name) == ("nixos-rebuild", "machine")
    assert args.flake_attr is None
    assert (args.hostname, args.username, args.extra_config) == (None, None, None)


def test_create_options():
    args = provision.parse_args(
        [
            "--verbose",
            "--timeout",
            "30",
            "create",
            "machine",
            "--arch",
            "amd64",
            "--flake-attr",
            "custom",
            "--hostname",
            "host",
            "--username",
            "user",
            "--extra-config",
            "extra.nix",
            "--recreate",
        ]
    )
    assert (args.verbose, args.timeout) == (True, 30)
    assert (args.arch, args.flake_attr, args.hostname, args.username) == (
        "amd64",
        "custom",
        "host",
        "user",
    )
    assert (args.extra_config, args.recreate) == ("extra.nix", True)


def test_create_rejects_unknown_arch(capsys):
    with pytest.raises(SystemExit) as exc_info:
        provision.parse_args(["create", "machine", "--arch", "riscv64"])
    assert exc_info.value.code == 2
    assert "invalid choice: 'riscv64'" in capsys.readouterr().err


def test_nixos_rebuild_has_no_arch_or_recreate(capsys):
    for option in ("--arch", "--recreate"):
        with pytest.raises(SystemExit):
            provision.parse_args(["nixos-rebuild", "machine", option, "x86_64"])


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        provision.parse_args([])


@pytest.mark.parametrize(
    "username,hostname,expected",
    [
        (None, None, ("me", "machine")),
        ("user", None, ("user", "machine")),
        (None, "host", ("me", "host")),
        ("user", "host", ("user", "host")),
        ("", "", ("me", "machine")),
    ],
)
def test_resolve_identity(username, hostname, expected):
    assert provision.resolve_identity(username, hostname, "machine", "me") == expected


@pytest.mark.parametrize("command", ["create", "nixos-rebuild"])
@pytest.mark.parametrize("username", ["x$(id)", "a|b", "a&b", "Root", "-x", "a" * 33, ""])
def test_an_invalid_username_is_refused(command, username):
    with pytest.raises(SystemExit):
        provision.parse_args([command, "machine", "--username", username])


@pytest.mark.parametrize("username", ["nhooey", "_svc", "a-b_9", "a" * 32])
def test_a_valid_username_is_accepted(username):
    assert provision.parse_args(["create", "machine", "--username", username]).username == username
