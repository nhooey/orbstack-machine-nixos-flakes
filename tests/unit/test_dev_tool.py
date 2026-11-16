"""Unit tests for the `dev` tool's argument parsing and its pure functions."""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

import pytest

from tests.provision_module import PROJECT_ROOT


def load_dev() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dev_tool", PROJECT_ROOT / "tools" / "dev.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dev_tool"] = module
    spec.loader.exec_module(module)
    return module


dev = load_dev()


# ============================================================================
# Argument parsing
# ============================================================================


def test_test_defaults():
    args, extra = dev.parse_args(["test"])
    assert args.command == "test"
    assert args.suite == "all"
    assert (args.verbose, args.debug, args.parallel, args.coverage) == (False,) * 4
    assert extra == []


@pytest.mark.parametrize("flag,suite", [("--unit", "unit"), ("--fast", "fast")])
def test_test_suite_flags(flag, suite):
    args, _ = dev.parse_args(["test", flag])
    assert args.suite == suite


def test_test_suites_are_exclusive(capsys):
    with pytest.raises(SystemExit) as exit_info:
        dev.parse_args(["test", "--unit", "--fast"])
    assert exit_info.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


def test_test_passes_unknown_arguments_to_pytest():
    args, extra = dev.parse_args(
        ["test", "--unit", "-k", "extra_config", "tests/unit/test_cli.py", "--parallel"]
    )
    assert (args.suite, args.parallel) == ("unit", True)
    assert extra == ["-k", "extra_config", "tests/unit/test_cli.py"]


def test_test_doesnt_read_pytest_options_as_abbreviations():
    args, extra = dev.parse_args(["test", "--co", "--deb"])
    assert (args.coverage, args.debug) == (False, False)
    assert extra == ["--co", "--deb"]


@pytest.mark.parametrize("command", ["format", "typecheck"])
def test_passthrough_commands_keep_unknown_arguments(command):
    args, extra = dev.parse_args([command, "--some-flag", "path"])
    assert args.command == command
    assert extra == ["--some-flag", "path"]


@pytest.mark.parametrize(
    "argv", [["cleanup", "--force"], ["python-files", "extra"], ["cleanup", "name"]]
)
def test_other_commands_reject_unknown_arguments(argv, capsys):
    with pytest.raises(SystemExit) as exit_info:
        dev.parse_args(argv)
    assert exit_info.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_cleanup_dry_run():
    assert dev.parse_args(["cleanup"])[0].dry_run is False
    assert dev.parse_args(["cleanup", "--dry-run"])[0].dry_run is True


def test_a_command_is_required(capsys):
    with pytest.raises(SystemExit) as exit_info:
        dev.parse_args([])
    assert exit_info.value.code == 2


def test_help_lists_every_command(capsys):
    with pytest.raises(SystemExit) as exit_info:
        dev.parse_args(["--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    for command in dev.COMMANDS:
        assert command in out


def test_every_handler_has_a_command():
    for command in dev.COMMANDS:
        args, _ = dev.parse_args([command])
        assert args.command == command


# ============================================================================
# Command lines
# ============================================================================


@pytest.mark.parametrize(
    "suite,options,extra,expected",
    [
        ("all", {}, [], ["pytest"]),
        ("unit", {}, [], ["pytest", "tests/unit"]),
        ("fast", {}, [], ["pytest", "-m", "not slow"]),
        ("all", {"verbose": True}, [], ["pytest", "-v"]),
        # --debug is already verbose, so --verbose adds nothing to it.
        ("all", {"verbose": True, "debug": True}, [], ["pytest", "-s", "-vv"]),
        ("all", {"parallel": True}, [], ["pytest", "-n", "auto"]),
        (
            "unit",
            {"coverage": True},
            ["-k", "cli"],
            ["pytest", "tests/unit", *dev.COVERAGE_ARGS, "-k", "cli"],
        ),
    ],
)
def test_pytest_argv(suite, options, extra, expected):
    flags = {"verbose": False, "debug": False, "parallel": False, "coverage": False, **options}
    assert dev.pytest_argv(suite, extra=extra, **flags) == expected


def test_format_argv():
    assert dev.format_argv([]) == ["nix", "fmt", "--"]
    assert dev.format_argv(["flake.nix"]) == ["nix", "fmt", "--", "flake.nix"]


def test_python_files():
    listing = "README.md\ntools/dev.py\nflake.nix\norbstack-machine-nixos-flakes.py\nnotes.pyc\n"
    assert dev.python_files(listing) == ["tools/dev.py", "orbstack-machine-nixos-flakes.py"]
    assert dev.python_files("") == []


def test_mypy_argv():
    assert dev.mypy_argv(["a.py", "b.py"], ["--strict"]) == ["mypy", "a.py", "b.py", "--strict"]


# ============================================================================
# Leftover test machines
# ============================================================================

ORB_LIST = (
    "test-nixos-1731772800000-019     stopped  nixos  25.11  arm64  3.8 GB\n"
    "test-nixos-MASTER-1731772800000  stopped  nixos  25.11  arm64  3.8 GB\n"
    "nixos-flakes                     running  nixos  25.11  arm64  96.7 GB\n"
    "test-nixos-mine                  running  nixos  25.11  arm64  1 GB\n"
    "my-test-nixos-1731772800000-001  running  nixos  25.11  arm64  1 GB\n"
    "test-nixos-1731772800000-001\trunning\tnixos\t25.11\tamd64\t1 GB\n"
    "\n"
)


def test_leftover_test_machines():
    assert dev.leftover_test_machines(ORB_LIST) == [
        "test-nixos-1731772800000-019",
        "test-nixos-MASTER-1731772800000",
        "test-nixos-1731772800000-001",
    ]


def test_leftover_test_machines_none():
    assert dev.leftover_test_machines("") == []
    assert dev.leftover_test_machines("nixos  running  nixos  25.11  arm64  1 GB\n") == []
