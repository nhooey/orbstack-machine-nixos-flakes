"""Unit tests for the path decisions made when copying configuration to a machine."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.provision_module import load

provision = load()


@pytest.mark.parametrize(
    "path,cwd,expected",
    [
        ("{root}/etc/extra.nix", "{root}/home/u", "{root}/etc/extra.nix"),
        ("extra.nix", "{root}/home/u", "{root}/home/u/extra.nix"),
        ("configs/extra.nix", "{root}/home/u", "{root}/home/u/configs/extra.nix"),
        ("../extra.nix", "{root}/home/u/project", "{root}/home/u/extra.nix"),
    ],
)
def test_resolve_host_path(tmp_path, path, cwd, expected):
    """Relative paths resolve against cwd; absolute paths stand as they are."""
    root = tmp_path.resolve()
    assert provision.resolve_host_path(path.format(root=root), Path(cwd.format(root=root))) == Path(
        expected.format(root=root)
    )


@pytest.mark.parametrize(
    "path,base,expected",
    [
        (Path("/r/extra/lib/docker.nix"), Path("/r/extra"), Path("lib/docker.nix")),
        (Path("/r/extra/simple.nix"), Path("/r/extra"), Path("simple.nix")),
        (Path("/tmp/simple.nix"), Path("/r/extra"), None),
        # A sibling directory whose name starts with the base's isn't inside it.
        (Path("/r/extra2/simple.nix"), Path("/r/extra"), None),
    ],
)
def test_path_within(path, base, expected):
    assert provision.path_within(path, base) == expected


def test_parent_dirs_to_create_skips_top_level_and_deduplicates():
    rel_paths = (
        Path("README.md"),
        Path("lib/docker.nix"),
        Path("lib/other.nix"),
        Path("examples/deep/simple.nix"),
    )
    assert provision.parent_dirs_to_create("/tmp/x", rel_paths) == frozenset(
        {"/tmp/x/lib", "/tmp/x/examples/deep"}
    )


def test_parent_dirs_to_create_with_only_top_level_files():
    assert provision.parent_dirs_to_create("/tmp/x", (Path("a.nix"),)) == frozenset()
