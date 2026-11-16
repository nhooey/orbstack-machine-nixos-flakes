"""Unit tests for reading machine states from `orb list` output."""

from __future__ import annotations

import pytest

from tests.provision_module import load

provision = load()

ORB_LIST = (
    "nixos-example-include-lib  starting  nixos  25.11  arm64  3.8 GB   \n"
    "nixos                      stopped   nixos  25.11  arm64  2.1 GB   \n"
    "nixos-flakes               running   nixos  25.11  arm64  96.7 GB  \n"
    "tabbed\trunning\tnixos\t25.11\tamd64\t1 GB\n"
)


@pytest.mark.parametrize(
    "machine_name,expected",
    [
        ("nixos-example-include-lib", "starting"),
        ("nixos", "stopped"),
        ("nixos-flakes", "running"),
        ("tabbed", "running"),
        ("absent", None),
        # A prefix of a listed name isn't a match.
        ("nixos-example", None),
        # A state word isn't a machine name.
        ("running", None),
    ],
)
def test_machine_state(machine_name, expected):
    assert provision.machine_state(ORB_LIST, machine_name) == expected


def test_machine_state_of_a_stopped_machine_is_not_running_from_another_line():
    """A machine is running only if its own line says so."""
    assert provision.machine_state(ORB_LIST, "nixos") != "running"


@pytest.mark.parametrize("output", ["", "\n", "   \n"])
def test_machine_state_with_no_machines(output):
    assert provision.machine_state(output, "nixos") is None
