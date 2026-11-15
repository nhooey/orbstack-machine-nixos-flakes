# orbstack-machine-nixos-flakes

Provisions and maintains OrbStack Machines running NixOS with Flakes enabled. `orbstack-machine-nixos-flakes.py` creates a machine and runs `nixos-rebuild` in it from the NixOS flake in `orbstack-nix-config/`, optionally merging in a user's extra Nix configuration. `bootstrap-nixos.sh` runs inside the machine. Tests live in `tests/`.

## Build and test

- `nix develop`: the dev shell, with Python and its dev and test dependencies from `uv.lock`, the `provision`, `format`, `typecheck` and `tests*` commands, and the project's skills installed into `.agents/skills/` from the `skills-devshell/` sub-flake.
- `tests-fast` (`pytest -m 'not slow'`): the tests that don't create OrbStack Machines. `tests` runs them all, which needs OrbStack installed.
- `format` (black) and `typecheck` (mypy) check the Python.
- `nix flake check`: evaluates the dev shell.
