# orbstack-machine-nixos-flakes

Provisions and maintains OrbStack Machines running NixOS with Flakes enabled. `orbstack-machine-nixos-flakes.py` creates a machine and runs `nixos-rebuild` in it from the NixOS flake in `orbstack-nix-config/`, optionally merging in a user's extra Nix configuration. `bootstrap-nixos.sh` runs inside the machine. Tests live in `tests/`.

## Build and test

- `nix develop`: the dev shell, with Python and its dev and test dependencies from `uv.lock`, the `provision`, `format`, `typecheck` and `tests*` commands, and the project's skills installed into `.agents/skills/` from the `skills-devshell/` sub-flake.
- `tests-unit` (`pytest tests/unit`) runs the unit tests of the script's pure functions, which need no OrbStack. `tests` (`pytest`) runs every test, and `tests-fast` (`pytest -m 'not slow'`) the ones not marked slow. The integration tests in `tests/integration/` need OrbStack, and are skipped without `orb` on `PATH`; running them creates and deletes real OrbStack Machines, and `tests-cleanup` deletes any left behind.
- `typecheck` (mypy) checks the Python.
- `nix fmt` (treefmt: black and nixfmt) formats the Python and Nix files, as the dev shell's `format` does.
- `nix flake check`: evaluates the dev shell, runs the unit tests and fails on unformatted files. It can't run the integration tests, which need OrbStack.
