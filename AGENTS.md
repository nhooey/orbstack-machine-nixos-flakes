# orbstack-machine-nixos-flakes

Provisions and maintains OrbStack Machines running NixOS with Flakes enabled. `orbstack-machine-nixos-flakes.py` creates a machine and runs `nixos-rebuild` in it from the NixOS flake in `orbstack-nix-config/`, optionally merging in a user's extra Nix configuration. `bootstrap-nixos.sh` runs inside the machine. Tests live in `tests/`.

## Build and test

- `nix develop`: the dev shell, with Python and its dev and test dependencies from `uv.lock`, the `provision`, `format`, `typecheck` and `tests*` commands, and the project's skills installed into `.agents/skills/` from the `skills-devshell/` sub-flake.
- `tests` (`pytest`) runs every test, and `tests-fast` (`pytest -m 'not slow'`) the ones not marked slow. Both need OrbStack installed: every test file is skipped without `orb` on `PATH`, and `tests-fast` still creates a machine for the unmarked tests that use the `test_machine_created` fixture. Running them creates and deletes real OrbStack Machines; `tests-cleanup` deletes any left behind.
- `typecheck` (mypy) checks the Python.
- `nix fmt` (treefmt: black and nixfmt) formats the Python and Nix files, as the dev shell's `format` does.
- `nix flake check`: evaluates the dev shell and fails on unformatted files. It runs none of the tests, which need OrbStack.
