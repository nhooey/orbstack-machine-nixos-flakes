"""Unit tests for bootstrap-nixos.sh, with `sudo` and `nixos-rebuild` stubbed."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.provision_module import PROJECT_ROOT

SCRIPT = PROJECT_ROOT / "bootstrap-nixos.sh"
NAMES = ("FLAKE_REF", "NIXOS_HOSTNAME", "NIXOS_USERNAME", "NIXOS_EXTRA_CONFIG")


def stub(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(0o755)


def run_bootstrap(tmp_path: Path, values: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the script with stubs that record what nixos-rebuild received."""
    stubs = tmp_path / "bin"
    stubs.mkdir()
    stub(stubs, "sudo", 'exec "$@"\n')
    record = tmp_path / "received"
    stub(
        stubs,
        "nixos-rebuild",
        "".join(f'printf "%s\\0" "${{{n}:-}}" >>"{record}"\n' for n in NAMES)
        + f'printf "%s\\0" "$@" >>"{record}.argv"\n',
    )
    env = {**os.environ, "PATH": f"{stubs}:{os.environ['PATH']}", **values}
    return subprocess.run(
        ["bash", str(SCRIPT)], env=env, cwd=tmp_path, capture_output=True, text=True
    )


@pytest.mark.parametrize(
    "hostname",
    [
        "x$(touch pwned)y",
        "x`touch pwned`y",
        'x"; touch pwned; "y',
        "a&b",
        "a|b",
        "a\\b",
    ],
)
def test_values_reach_nixos_rebuild_as_data(tmp_path, hostname):
    """No value is run by the shell or rewritten by sed on its way to root."""
    values = {
        "FLAKE_REF": "/etc/nixos#default",
        "NIXOS_HOSTNAME": hostname,
        "NIXOS_USERNAME": "user",
        "NIXOS_EXTRA_CONFIG": "/tmp/a&b|c.nix",
    }
    result = run_bootstrap(tmp_path, values)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "pwned").exists()
    received = (tmp_path / "received").read_text().split("\0")[:-1]
    assert tuple(received) == tuple(values[n] for n in NAMES)
    argv = (tmp_path / "received.argv").read_text().split("\0")[:-1]
    assert argv == ["switch", "--flake", "/etc/nixos#default", "--impure"]


@pytest.mark.parametrize("username", ["x$(touch pwned)", "Root", "a b", "-x", "a" * 33])
def test_an_invalid_username_is_refused(tmp_path, username):
    values = {"FLAKE_REF": "/etc/nixos#default", "NIXOS_USERNAME": username}
    result = run_bootstrap(tmp_path, values)
    assert result.returncode != 0
    assert "NIXOS_USERNAME" in result.stderr
    assert not (tmp_path / "received").exists()
    assert not (tmp_path / "pwned").exists()
