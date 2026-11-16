#!/usr/bin/env python3
"""The project's development commands: tests, formatting, type checks and cleanup.

The dev shell puts this on `PATH` as `dev`. Each command runs from the
repository root, and `dev <command> --help` lists its options. Arguments a
command doesn't know are passed on to the tool it runs (pytest, `nix fmt` or
mypy), so `dev test -k extra_config` works as `pytest -k extra_config` does.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent

# The tests' OrbStack Machines: `test-nixos-<ms timestamp>-<index>` for each
# test, and `test-nixos-MASTER-<ms timestamp>` for the template they clone.
TEST_MACHINE_PATTERN = re.compile(r"test-nixos-(?:\d{13}-\d+|MASTER-\d{13})")

# The pytest arguments each suite adds.
SUITE_ARGS: Mapping[str, tuple[str, ...]] = {
    "all": (),
    "unit": ("tests/unit",),
    "fast": ("-m", "not slow"),
}

COVERAGE_ARGS = ("--cov=.", "--cov-report=html", "--cov-report=term")

# Commands that pass the arguments they don't know on to the tool they run.
PASSTHROUGH_COMMANDS = frozenset({"test", "format", "typecheck"})


# ============================================================================
# Pure functions
# ============================================================================


def pytest_argv(
    suite: str,
    verbose: bool,
    debug: bool,
    parallel: bool,
    coverage: bool,
    extra: Sequence[str],
) -> list[str]:
    """Return the pytest command line for a suite and its options."""
    return [
        "pytest",
        *SUITE_ARGS[suite],
        *(("-v",) if verbose and not debug else ()),
        *(("-s", "-vv") if debug else ()),
        *(("-n", "auto") if parallel else ()),
        *(COVERAGE_ARGS if coverage else ()),
        *extra,
    ]


def format_argv(extra: Sequence[str]) -> list[str]:
    """Return the `nix fmt` command line, passing extra arguments to treefmt."""
    return ["nix", "fmt", "--", *extra]


def python_files(git_ls_files_output: str) -> list[str]:
    """Return the Python files in `git ls-files` output, in its order."""
    return [line for line in git_ls_files_output.splitlines() if line.endswith(".py")]


def mypy_argv(files: Sequence[str], extra: Sequence[str]) -> list[str]:
    """Return the mypy command line for the given files."""
    return ["mypy", *files, *extra]


def leftover_test_machines(orb_list_output: str) -> list[str]:
    """Return the names in `orb list` output that the tests created.

    Each line of `orb list` starts with a machine name.
    """
    return [
        fields[0]
        for fields in (line.split() for line in orb_list_output.splitlines())
        if fields and TEST_MACHINE_PATTERN.fullmatch(fields[0])
    ]


def parse_args(argv: Sequence[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    """Parse the command line, from sys.argv when argv is None.

    Returns the parsed options and the arguments to pass on to the tool the
    command runs. A command that passes nothing on fails on any argument it
    doesn't know.
    """
    parser = argparse.ArgumentParser(
        prog="dev",
        description="Development commands for orbstack-machine-nixos-flakes.",
        allow_abbrev=False,
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # No abbreviated options, so a pytest option such as `--co` isn't read as
    # the start of `--coverage`.
    test = commands.add_parser(
        "test",
        allow_abbrev=False,
        help="Run the tests with pytest",
        description=(
            "Run the tests with pytest. Arguments this command doesn't know, such as test "
            "paths or `-k`, go to pytest."
        ),
    )
    suite = test.add_mutually_exclusive_group()
    suite.add_argument(
        "--unit",
        dest="suite",
        action="store_const",
        const="unit",
        help="Only the unit tests in tests/unit, which need no OrbStack",
    )
    suite.add_argument(
        "--fast",
        dest="suite",
        action="store_const",
        const="fast",
        help="Only the tests not marked slow; none of these creates a machine",
    )
    test.set_defaults(suite="all")
    test.add_argument("--verbose", action="store_true", help="Verbose output (pytest -v)")
    test.add_argument(
        "--debug", action="store_true", help="Real-time output, nothing captured (pytest -s -vv)"
    )
    test.add_argument(
        "--parallel", action="store_true", help="Run tests in parallel (pytest -n auto)"
    )
    test.add_argument(
        "--coverage", action="store_true", help="Report coverage in the terminal and as HTML"
    )

    commands.add_parser(
        "format",
        help="Format the Python and Nix files with treefmt (nix fmt)",
        description="Format the Python and Nix files with treefmt. Other arguments go to treefmt.",
    )
    commands.add_parser(
        "typecheck",
        help="Type-check the Python files with mypy",
        description="Type-check the Python files Git tracks with mypy. Other arguments go to mypy.",
    )
    commands.add_parser(
        "python-files",
        help="List the Python files Git tracks",
        description="List the Python files Git tracks, one per line.",
    )
    cleanup = commands.add_parser(
        "cleanup",
        help="Delete the OrbStack Machines the integration tests left behind",
        description=(
            "Delete every OrbStack Machine named like the integration tests' machines, "
            "test-nixos-<timestamp>-<index> and test-nixos-MASTER-<timestamp>."
        ),
    )
    cleanup.add_argument(
        "--dry-run", action="store_true", help="List the machines without deleting them"
    )

    args, extra = parser.parse_known_args(argv)
    if extra and args.command not in PASSTHROUGH_COMMANDS:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    return args, extra


# ============================================================================
# Commands
# ============================================================================


def run(argv: Sequence[str]) -> int:
    """Run a command from the repository root and return its exit status."""
    return subprocess.run(argv, cwd=REPO_ROOT).returncode


def output_of(argv: Sequence[str]) -> str:
    """Return a command's standard output, failing if the command fails."""
    return subprocess.run(argv, cwd=REPO_ROOT, check=True, capture_output=True, text=True).stdout


def tracked_python_files() -> list[str]:
    return python_files(output_of(["git", "ls-files"]))


def command_test(args: argparse.Namespace, extra: Sequence[str]) -> int:
    return run(
        pytest_argv(args.suite, args.verbose, args.debug, args.parallel, args.coverage, extra)
    )


def command_format(args: argparse.Namespace, extra: Sequence[str]) -> int:
    return run(format_argv(extra))


def command_typecheck(args: argparse.Namespace, extra: Sequence[str]) -> int:
    return run(mypy_argv(tracked_python_files(), extra))


def command_python_files(args: argparse.Namespace, extra: Sequence[str]) -> int:
    print("\n".join(tracked_python_files()))
    return 0


def command_cleanup(args: argparse.Namespace, extra: Sequence[str]) -> int:
    machines = leftover_test_machines(output_of(["orb", "list"]))
    if not machines:
        print("No test machines to clean up.")
        return 0
    verb = "Would delete" if args.dry_run else "Deleting"
    print(f"{verb} the following OrbStack Machines:")
    print("\n".join(f"  {name}" for name in machines))
    if args.dry_run:
        return 0
    statuses = [run(["orb", "delete", "-f", name]) for name in machines]
    return next((status for status in statuses if status != 0), 0)


COMMANDS: Mapping[str, Callable[[argparse.Namespace, Sequence[str]], int]] = {
    "test": command_test,
    "format": command_format,
    "typecheck": command_typecheck,
    "python-files": command_python_files,
    "cleanup": command_cleanup,
}


def main(argv: Sequence[str] | None = None) -> int:
    args, extra = parse_args(argv)
    try:
        return COMMANDS[args.command](args, extra)
    except FileNotFoundError as error:
        print(f"dev: {error.filename} is not on PATH; run this from `nix develop`", file=sys.stderr)
        return 127
    except subprocess.CalledProcessError as error:
        print(f"dev: {' '.join(error.cmd)} failed with status {error.returncode}", file=sys.stderr)
        if error.stderr:
            sys.stderr.write(error.stderr)
        return error.returncode


if __name__ == "__main__":
    sys.exit(main())
